"""Offline check of the agent's confidence score against real accuracy (3.9.2).

For an agent eval run it takes each answered question, derives the candidate
features from the stored trace, and shows how often the answer was right when the
feature held and when it did not. It then applies the acceptance rule from
DECISION.md: the top confidence bucket must beat the bottom one by
CONFIDENCE_MIN_SEPARATION, or the API keeps `confidence` null.

Plain Python on purpose: no stats library, so the production image is unchanged."""

import json
from dataclasses import dataclass

from django.conf import settings

from agent.loop import has_text_filter
from agent.models import AgentRun, AgentStep
from evals import scoring
from evals.models import EvalResult, EvalRun

FEATURES = (
    "no_revision",
    "guard_clean",
    "non_empty",
    "not_truncated",
    "not_single_value",
    "reflect_ok_first",
    "samples_checked",
    "not_edited",
)


@dataclass(frozen=True)
class FeatureRow:
    name: str
    n_true: int
    right_true: int
    n_false: int
    right_false: int

    @property
    def acc_true(self) -> float | None:
        return self.right_true / self.n_true if self.n_true else None

    @property
    def acc_false(self) -> float | None:
        return self.right_false / self.n_false if self.n_false else None

    @property
    def separates(self) -> bool:
        """Right more often when the feature holds, with data on both sides."""
        if self.acc_true is None or self.acc_false is None:
            return False
        return self.acc_true > self.acc_false


@dataclass(frozen=True)
class Analysis:
    answered: int
    right: int
    rows: list[FeatureRow]
    rank_correlation: float | None
    bottom_accuracy: float | None
    top_accuracy: float | None
    passes: bool


def features_of(run: AgentRun) -> dict[str, bool | None]:
    """Candidate features from the stored trace; None where one does not apply."""
    steps = list(run.steps.order_by("index"))
    proposals = [
        s for s in steps if s.kind == AgentStep.KIND_APPROVAL and s.actor == "agent"
    ]
    executes = [
        s for s in steps if s.kind == AgentStep.KIND_EXECUTE and s.status == "ok"
    ]
    reflects = [
        s
        for s in steps
        if s.kind == AgentStep.KIND_REFLECT and s.input.get("trigger") != "error"
    ]
    summary = json.loads(executes[-1].output) if executes else {}
    reflect_ok: bool | None = True
    if reflects:
        reflect_ok = json.loads(reflects[0].output).get("verdict") == "ok"
    sampled = any(
        s.kind == AgentStep.KIND_TOOL and s.tool_name == "sample_values" for s in steps
    )
    return {
        "no_revision": run.revisions == 0,
        "guard_clean": not proposals[-1].input.get("guard_rewrites")
        if proposals
        else None,
        "non_empty": run.row_count > 0,
        "not_truncated": not summary.get("truncated", False),
        "not_single_value": not (
            summary.get("row_count") == 1 and len(summary.get("columns", [])) == 1
        ),
        "reflect_ok_first": reflect_ok,
        "samples_checked": sampled if has_text_filter(run.final_sql) else None,
        "not_edited": not any(e.input.get("edited") for e in executes),
    }


def analyse(run: EvalRun) -> Analysis:
    results = [
        r
        for r in run.results.select_related("agent_run")
        if r.agent_run is not None
        and r.outcome in (EvalResult.OUTCOME_CORRECT, EvalResult.OUTCOME_WRONG)
        and r.agent_run.status == AgentRun.STATUS_SUCCEEDED
    ]
    right = [r.outcome == EvalResult.OUTCOME_CORRECT for r in results]
    per_result = [features_of(r.agent_run) for r in results if r.agent_run]
    rows = []
    for name in FEATURES:
        pairs = [
            (f[name], ok)
            for f, ok in zip(per_result, right, strict=True)
            if f[name] is not None
        ]
        holds = [ok for flag, ok in pairs if flag]
        fails = [ok for flag, ok in pairs if not flag]
        rows.append(FeatureRow(name, len(holds), sum(holds), len(fails), sum(fails)))
    cal = scoring.calibration(run)
    filled = [b for b in cal.buckets if b.count]
    bottom = filled[0].accuracy if filled else None
    top = filled[-1].accuracy if filled else None
    passes = (
        len(filled) >= 2
        and top is not None
        and bottom is not None
        and top - bottom >= settings.CONFIDENCE_MIN_SEPARATION
    )
    return Analysis(
        answered=len(results),
        right=sum(right),
        rows=rows,
        rank_correlation=cal.rank_correlation,
        bottom_accuracy=bottom,
        top_accuracy=top,
        passes=passes,
    )


def _pct(value: float | None) -> str:
    return f"{value:.0%}" if value is not None else "-"


def format_analysis(run: EvalRun, analysis: Analysis) -> str:
    lines = [
        f"Run #{run.pk} ({run.target}, {run.model}, {run.runner}): "
        f"{analysis.answered} answered, {analysis.right} right",
        "",
        f"{'feature':20}{'holds: right/n':>16}{'fails: right/n':>16}  separates",
    ]
    for row in analysis.rows:
        lines.append(
            f"{row.name:20}"
            f"{f'{row.right_true}/{row.n_true} ({_pct(row.acc_true)})':>16}"
            f"{f'{row.right_false}/{row.n_false} ({_pct(row.acc_false)})':>16}"
            f"  {'yes' if row.separates else 'no'}"
        )
    lines += [
        "",
        "Combined score (agent/confidence.py) vs accuracy:",
        f"  rank correlation: {analysis.rank_correlation}",
        f"  bottom bucket accuracy: {_pct(analysis.bottom_accuracy)}, "
        f"top bucket accuracy: {_pct(analysis.top_accuracy)}",
        f"  needs a gap of {settings.CONFIDENCE_MIN_SEPARATION:.0%} "
        f"(CONFIDENCE_MIN_SEPARATION): " + ("PASS" if analysis.passes else "FAIL"),
        "",
        "PASS: set CONFIDENCE_SHOW_SCORE=true and drop any feature that does not separate."
        if analysis.passes
        else "FAIL: leave CONFIDENCE_SHOW_SCORE=false. The API keeps confidence null and "
        "shows the checked / needs_look label.",
    ]
    return "\n".join(lines)

"""The regression gate (step 6): did a change make the eval results worse?

Pure logic on two stored runs. It fails when accuracy on the shared cases drops
by more than EVAL_GATE_MAX_DROP_POINTS percentage points, or when fewer than
EVAL_GATE_MIN_CASES cases are shared (too small to trust). It lists the cases
that flipped and the clusters that dropped, so a failure says where to look."""

from dataclasses import dataclass, field

from django.conf import settings

from evals import run_compare
from evals.models import EvalRun

PASS = "pass"
TOO_FEW_CASES = "too_few_cases"
DROPPED = "accuracy_dropped"


class NotComparable(ValueError):
    pass


@dataclass(frozen=True)
class Verdict:
    passed: bool
    reason: str
    shared: int
    base_accuracy: float
    candidate_accuracy: float
    # Baseline minus candidate in percentage points; negative means it improved.
    drop_points: float
    flips: list[run_compare.Flip] = field(default_factory=list)
    cluster_drops: list[run_compare.ClusterDelta] = field(default_factory=list)


def evaluate(
    candidate: EvalRun,
    baseline: EvalRun,
    *,
    max_drop_points: float | None = None,
    min_cases: int | None = None,
) -> Verdict:
    if max_drop_points is None:
        max_drop_points = settings.EVAL_GATE_MAX_DROP_POINTS
    if min_cases is None:
        min_cases = settings.EVAL_GATE_MIN_CASES
    if not run_compare.comparable(baseline, candidate):
        raise NotComparable("The runs scored different targets.")
    diff = run_compare.compare_runs(baseline, candidate)
    drop = round(-diff.diff_points, 2)
    if diff.shared < min_cases:
        reason = TOO_FEW_CASES
    elif drop > max_drop_points:
        reason = DROPPED
    else:
        reason = PASS
    return Verdict(
        passed=reason == PASS,
        reason=reason,
        shared=diff.shared,
        base_accuracy=diff.base_accuracy,
        candidate_accuracy=diff.other_accuracy,
        drop_points=drop,
        flips=diff.flips,
        cluster_drops=[d for d in diff.clusters if d.other_correct < d.base_correct],
    )


def latest_baseline(candidate_like: EvalRun) -> EvalRun | None:
    """The newest finished run of the same target, split, runner and prompt
    version (never the run itself)."""
    return (
        EvalRun.objects.filter(
            target=candidate_like.target,
            split=candidate_like.split,
            runner=candidate_like.runner,
            prompt_version=candidate_like.prompt_version,
            status=EvalRun.STATUS_DONE,
        )
        .exclude(pk=candidate_like.pk)
        .order_by("-started_at", "-id")
        .first()
    )


def format_verdict(verdict: Verdict, candidate: EvalRun, baseline: EvalRun) -> str:
    head = "GATE PASSED" if verdict.passed else "GATE FAILED"
    lines = [
        f"{head}: run #{candidate.pk} against baseline #{baseline.pk} "
        f"({verdict.shared} shared cases)",
        f"Accuracy on shared cases: {verdict.base_accuracy:.1%} -> "
        f"{verdict.candidate_accuracy:.1%} (drop {verdict.drop_points:+.2f} points, "
        f"allowed {settings.EVAL_GATE_MAX_DROP_POINTS})",
    ]
    if verdict.reason == TOO_FEW_CASES:
        lines.append(
            f"Too few shared cases to trust: {verdict.shared} is under "
            f"EVAL_GATE_MIN_CASES ({settings.EVAL_GATE_MIN_CASES})."
        )
    if verdict.flips:
        lines.append("Flipped cases:")
        lines.extend(
            f"  {f.question_id} {f.direction} ({f.base_outcome} -> {f.other_outcome})"
            f" [{f.cluster_key}]"
            for f in verdict.flips
        )
    if verdict.cluster_drops:
        lines.append("Clusters that dropped:")
        lines.extend(
            f"  {d.cluster_key}: {d.base_correct} -> {d.other_correct} of {d.shared}"
            for d in verdict.cluster_drops
        )
    return "\n".join(lines)

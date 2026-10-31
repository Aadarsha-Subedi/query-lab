"""Numbers for a finished run: accuracy, errors, speed, cost and how well the
confidence score separates right answers from wrong ones."""

import itertools
import math
from dataclasses import dataclass, field

from django.conf import settings

from evals.models import EvalResult, EvalRun


@dataclass(frozen=True)
class Summary:
    total: int
    correct: int
    accuracy: float
    outcomes: dict[str, int]
    by_tag: dict[str, tuple[int, int]]  # tag -> (questions, correct)
    mean_latency_ms: int
    p95_latency_ms: int
    input_tokens: int
    output_tokens: int
    cost_usd: float | None  # None when the model has no price in EVAL_MODEL_PRICES
    # Per question; only the agent runner fills the step counts.
    mean_tokens: int = 0
    mean_steps: float = 0.0
    mean_llm_calls: float = 0.0
    mean_revisions: float = 0.0


@dataclass(frozen=True)
class Bucket:
    low: float
    high: float
    count: int
    correct: int

    @property
    def accuracy(self) -> float | None:
        return self.correct / self.count if self.count else None


@dataclass(frozen=True)
class Calibration:
    buckets: list[Bucket]
    rank_correlation: float | None  # Spearman; None with too little data
    scored: int  # answers that carry a confidence
    extra: dict[str, int] = field(default_factory=dict)


def _percentile(values: list[int], fraction: float) -> int:
    if not values:
        return 0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, math.ceil(fraction * len(ordered)) - 1)]


def summarise(run: EvalRun) -> Summary:
    results = list(run.results.all())
    total = len(results)
    correct = sum(r.outcome == EvalResult.OUTCOME_CORRECT for r in results)
    outcomes: dict[str, int] = {}
    by_tag: dict[str, list[int]] = {}
    for result in results:
        outcomes[result.outcome] = outcomes.get(result.outcome, 0) + 1
        for tag in filter(None, result.tags.split(",")):
            counts = by_tag.setdefault(tag, [0, 0])
            counts[0] += 1
            counts[1] += result.outcome == EvalResult.OUTCOME_CORRECT
    latencies = [r.latency_ms for r in results]
    input_tokens = sum(r.input_tokens for r in results)
    output_tokens = sum(r.output_tokens for r in results)
    price = settings.EVAL_MODEL_PRICES.get(run.model)
    cost = (
        round((input_tokens * price[0] + output_tokens * price[1]) / 1_000_000, 4)
        if price
        else None
    )
    return Summary(
        total=total,
        correct=correct,
        accuracy=correct / total if total else 0.0,
        outcomes=dict(sorted(outcomes.items())),
        by_tag={tag: (c[0], c[1]) for tag, c in sorted(by_tag.items())},
        mean_latency_ms=round(sum(latencies) / total) if total else 0,
        p95_latency_ms=_percentile(latencies, 0.95),
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cost_usd=cost,
        mean_tokens=round((input_tokens + output_tokens) / total) if total else 0,
        mean_steps=round(sum(r.steps for r in results) / total, 2) if total else 0.0,
        mean_llm_calls=(
            round(sum(r.llm_calls for r in results) / total, 2) if total else 0.0
        ),
        mean_revisions=(
            round(sum(r.revisions for r in results) / total, 2) if total else 0.0
        ),
    )


def _ranks(values: list[float]) -> list[float]:
    """1-based ranks, ties sharing their average rank."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start
        while end + 1 < len(order) and values[order[end + 1]] == values[order[start]]:
            end += 1
        for position in range(start, end + 1):
            ranks[order[position]] = (start + end) / 2 + 1
        start = end + 1
    return ranks


def spearman(xs: list[float], ys: list[float]) -> float | None:
    if len(xs) < 3:
        return None
    rx, ry = _ranks(xs), _ranks(ys)
    mean_x, mean_y = sum(rx) / len(rx), sum(ry) / len(ry)
    cov = sum((a - mean_x) * (b - mean_y) for a, b in zip(rx, ry, strict=True))
    var_x = sum((a - mean_x) ** 2 for a in rx)
    var_y = sum((b - mean_y) ** 2 for b in ry)
    if var_x == 0 or var_y == 0:
        return None
    return round(cov / math.sqrt(var_x * var_y), 3)


def calibration(run: EvalRun) -> Calibration:
    """Accuracy per confidence bucket, plus a rank correlation between confidence
    and being right. Only answers that came back with SQL have a confidence."""
    edges = [0.0, *settings.EVAL_CONFIDENCE_BUCKETS, 1.0]
    pairs = [
        (r.confidence, r.outcome == EvalResult.OUTCOME_CORRECT)
        for r in run.results.exclude(confidence=None)
        if r.confidence is not None
    ]
    buckets = []
    for index, (low, high) in enumerate(itertools.pairwise(edges)):
        last = index == len(edges) - 2
        inside = [ok for c, ok in pairs if low <= c < high or (last and c == high)]
        buckets.append(Bucket(low, high, len(inside), sum(inside)))
    return Calibration(
        buckets=buckets,
        rank_correlation=spearman(
            [c for c, _ in pairs], [1.0 if ok else 0.0 for _, ok in pairs]
        ),
        scored=len(pairs),
    )


def format_report(run: EvalRun) -> str:
    summary = summarise(run)
    lines = [
        f"Run #{run.pk}: {run.target}/{run.split}  {run.provider}/{run.model}  "
        f"{run.runner} runner  prompt {run.prompt_version}  [{run.status}]",
        f"Execution accuracy: {summary.accuracy:.1%} "
        f"({summary.correct}/{summary.total})",
        "Outcomes: "
        + ", ".join(f"{name} {count}" for name, count in summary.outcomes.items()),
        f"Latency: mean {summary.mean_latency_ms} ms, p95 {summary.p95_latency_ms} ms",
        f"Tokens: {summary.input_tokens} in, {summary.output_tokens} out"
        + (
            f"  (about ${summary.cost_usd} at EVAL_MODEL_PRICES)"
            if summary.cost_usd is not None
            else "  (no price set for this model)"
        ),
    ]
    if run.runner == EvalRun.RUNNER_AGENT:
        lines.append(
            f"Agent cost per question: {summary.mean_steps} steps, "
            f"{summary.mean_llm_calls} LLM calls, {summary.mean_revisions} revisions, "
            f"{summary.mean_tokens} tokens"
        )
    if summary.by_tag:
        lines.append("By tag:")
        lines.extend(
            f"  {tag}: {correct}/{count}"
            for tag, (count, correct) in summary.by_tag.items()
        )
    cal = calibration(run)
    lines.append(f"Confidence vs accuracy ({cal.scored} answers with a confidence):")
    for bucket in cal.buckets:
        shown = f"{bucket.accuracy:.1%}" if bucket.accuracy is not None else "-"
        lines.append(
            f"  {bucket.low:.2f}-{bucket.high:.2f}: {shown} "
            f"({bucket.correct}/{bucket.count})"
        )
    rho = cal.rank_correlation
    lines.append(
        "  rank correlation: "
        + (
            f"{rho}"
            if rho is not None
            else "n/a (too few answers, or every confidence is the same)"
        )
    )
    return "\n".join(lines)

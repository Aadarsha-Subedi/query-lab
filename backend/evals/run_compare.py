"""Compare two eval runs question by question (step 6). Pure logic on stored
results: which cases flipped, and how each cluster moved. The row comparison
that scores a single answer stays in `evals/compare.py`."""

from dataclasses import dataclass, field

from evals.models import EvalResult, EvalRun

UNCLUSTERED = "unclustered"
TO_WRONG = "to_wrong"
TO_CORRECT = "to_correct"


@dataclass(frozen=True)
class Flip:
    question_id: str
    direction: str  # to_wrong | to_correct
    base_outcome: str
    other_outcome: str
    cluster_key: str
    trace_case_id: int | None
    question: str


@dataclass(frozen=True)
class ClusterDelta:
    cluster_key: str
    shared: int
    base_correct: int
    other_correct: int

    @property
    def diff_points(self) -> float:
        return round(100 * (self.other_correct - self.base_correct) / self.shared, 2)


@dataclass(frozen=True)
class Comparison:
    shared: int
    base_correct: int
    other_correct: int
    only_in_base: int
    only_in_other: int
    flips: list[Flip] = field(default_factory=list)
    clusters: list[ClusterDelta] = field(default_factory=list)

    @property
    def base_accuracy(self) -> float:
        return self.base_correct / self.shared if self.shared else 0.0

    @property
    def other_accuracy(self) -> float:
        return self.other_correct / self.shared if self.shared else 0.0

    @property
    def diff_points(self) -> float:
        """Other minus base, in percentage points, on the shared cases only."""
        return round(100 * (self.other_accuracy - self.base_accuracy), 2)


def comparable(base: EvalRun, other: EvalRun) -> bool:
    return base.target == other.target


def compare_runs(base: EvalRun, other: EvalRun) -> Comparison:
    before = {r.question_id: r for r in base.results.all()}
    after = {r.question_id: r for r in other.results.all()}
    shared_ids = sorted(before.keys() & after.keys())
    flips: list[Flip] = []
    clusters: dict[str, list[int]] = {}
    base_correct = other_correct = 0
    for qid in shared_ids:
        a, b = before[qid], after[qid]
        was = a.outcome == EvalResult.OUTCOME_CORRECT
        now = b.outcome == EvalResult.OUTCOME_CORRECT
        base_correct += was
        other_correct += now
        key = b.cluster_key or a.cluster_key or UNCLUSTERED
        counts = clusters.setdefault(key, [0, 0, 0])
        counts[0] += 1
        counts[1] += was
        counts[2] += now
        if was != now:
            flips.append(
                Flip(
                    question_id=qid,
                    direction=TO_CORRECT if now else TO_WRONG,
                    base_outcome=a.outcome,
                    other_outcome=b.outcome,
                    cluster_key=key,
                    trace_case_id=b.trace_case_id or a.trace_case_id,
                    question=b.question,
                )
            )
    return Comparison(
        shared=len(shared_ids),
        base_correct=base_correct,
        other_correct=other_correct,
        only_in_base=len(before.keys() - after.keys()),
        only_in_other=len(after.keys() - before.keys()),
        flips=flips,
        clusters=[
            ClusterDelta(key, c[0], c[1], c[2]) for key, c in sorted(clusters.items())
        ],
    )

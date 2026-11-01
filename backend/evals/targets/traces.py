"""Approved trace cases as an eval set (step 6).

Same demo schema, guard and reader connection as the Olist target; only the
questions differ. A case is served only once a person approved it: a candidate, a
draft or a rejected case never is. `tags` holds the cluster key."""

from evals import clustering
from evals.models import EvalRun, TraceCase
from evals.targets.base import EvalQuestion
from evals.targets.olist import OlistTarget

NAME = EvalRun.TARGET_TRACES


class TraceTarget(OlistTarget):
    name = NAME

    def questions(self, split: str) -> list[EvalQuestion]:
        if split != EvalRun.SPLIT_ALL:
            raise ValueError("The trace set has no splits; use --split all.")
        clustering.assign_clusters()  # so each result can say which cluster it is in
        approved = TraceCase.objects.filter(status=TraceCase.STATUS_APPROVED).order_by(
            "id"
        )
        return [
            EvalQuestion(
                id=f"trace-{case.pk}",
                question=case.question,
                gold_sql=case.gold_sql,
                tags=case.cluster_key,
                answerable=case.answerable,
                case_id=case.pk,
                cluster=case.cluster_key,
            )
            for case in approved
        ]

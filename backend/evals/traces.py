"""Which stored agent runs the trace workbench may show (step 6).

Only runs on the shared demo that were not kept out of evals. A run on a user's
workspace never appears here, whatever the caller asks for."""

from django.db.models import QuerySet

from agent.models import AgentRun, AgentStep


def workbench_runs() -> QuerySet[AgentRun]:
    """Demo runs only (`workspace_id` null) and none marked `excluded_from_evals`."""
    return AgentRun.objects.filter(workspace_id__isnull=True, excluded_from_evals=False)


def proposed_sql(run: AgentRun) -> str:
    """The SQL the agent proposed first (its earliest approval pause)."""
    step = (
        run.steps.filter(kind=AgentStep.KIND_APPROVAL, actor=AgentStep.ACTOR_AGENT)
        .order_by("index")
        .first()
    )
    return str(step.input.get("sql", "")) if step else ""

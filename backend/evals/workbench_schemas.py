"""API shapes of the staff-only trace workbench."""

from typing import Any

from agent import schemas as agent_schemas
from agent.models import AgentRun
from evals import traces


class TraceDetailOut(agent_schemas.RunDetailOut):
    # The SQL the agent proposed first, and the SQL that finally ran.
    proposed_sql: str
    approved_sql: str
    # True when the person changed the SQL before it ran.
    diff: bool


def trace_detail_dict(run: AgentRun) -> dict[str, Any]:
    base = agent_schemas.run_detail_dict(run)
    return {
        **base,
        "proposed_sql": traces.proposed_sql(run),
        "approved_sql": run.final_sql,
        "diff": base["edited"],
    }

"""The full rows of a finished run, for the analyst screen's result table.

Result rows are never stored (DECISION.md, step 3), so the rows are fetched by
running the run's stored SQL again. This is the only code path where SQL runs
outside the agent loop, so it is narrow on purpose:

- the SQL is always the run's own `final_sql`, never anything from the request;
- only a `succeeded` run has a result;
- the SQL goes through `guard.check` again (the guard or the schema may have
  changed since) and then through `runner.run`, which uses the reader
  connection, a read-only transaction, the statement timeout and the row cap;
- nothing is written: no step, no change to the run, no rows kept.
"""

from dataclasses import asdict
from typing import Any

from agent.errors import RunNotSucceeded
from agent.models import AgentRun
from ask import guard, runner, schema
from workspaces.resolve import resolve


def fetch(run: AgentRun) -> dict[str, Any]:
    if run.status != AgentRun.STATUS_SUCCEEDED or not run.final_sql:
        raise RunNotSucceeded()
    workspace = resolve(run.workspace_id)  # WorkspaceGone once it was deleted
    known = schema.get_schema(workspace, include_samples=True)
    checked = guard.check(run.final_sql, known)
    return {
        "run_id": run.pk,
        "sql": checked.sql,
        **asdict(runner.run(checked.sql, workspace)),
    }

from typing import cast

from django.http import HttpRequest
from ninja import Router
from ninja.security import django_auth

from accounts.models import User
from common.response.domain import SuccessEnvelope, errors, success
from common.throttling.scoped import WorkspaceSqlThrottle
from workspaces import sql
from workspaces.access import writable_workspace
from workspaces.sql_schemas import SqlIn, SqlOut

router = Router(tags=["workspace sql"])


@router.post(
    "/{workspace_id}/sql",
    response={
        200: SuccessEnvelope[SqlOut],
        **errors(400, 401, 404, 409, 422, 429, 504),
    },
    auth=django_auth,
    throttle=[WorkspaceSqlThrottle()],
)
def run_workspace_sql(request: HttpRequest, workspace_id: int, payload: SqlIn) -> dict:
    """Run your own read-only SQL on your own workspace: `SELECT`, `WITH`,
    `EXPLAIN`, `SHOW` or `VALUES`, one or several statements in one read-only
    transaction. Anything that would change data or structure is refused with
    `sql_invalid` before it runs, and the database role cannot write either.
    A failing statement answers 422 `sql_failed` with the Postgres code and
    message; one that runs too long is stopped (`query_timeout`). To change the
    data, import a new dump."""
    workspace = writable_workspace(_user(request), workspace_id)
    return success(sql.run_script(workspace, _user(request), payload.sql))


def _user(request: HttpRequest) -> User:
    return cast(User, request.user)

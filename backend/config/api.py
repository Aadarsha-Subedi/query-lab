"""The one NinjaAPI, mounted at /api/. Default throttles apply to every route:
signed-out callers by IP, signed-in callers by user."""

from ninja import NinjaAPI
from ninja.operation import Operation

from accounts.api import router as accounts_router
from agent.api import router as agent_router
from ask.api import router as ask_router
from ask.schema_api import router as schema_router
from common.exception.handler import install_exception_handlers
from common.throttling.scoped import AnonThrottle, UserThrottle
from core.api import router as core_router
from workspaces.api import router as workspaces_router
from workspaces.tables_api import router as workspace_tables_router


class QuerylabAPI(NinjaAPI):
    def get_openapi_operation_id(self, operation: Operation) -> str:
        """The view function's name (`list_runs`, `get_schema`), so generated client
        methods read well. Function names are unique across the routers."""
        return operation.view_func.__name__


api = QuerylabAPI(
    title="Querylab API",
    version="0.1.0",
    throttle=[AnonThrottle(), UserThrottle()],
    urls_namespace="api",
)
install_exception_handlers(api)

api.add_router("/", core_router)
api.add_router("/", accounts_router)
api.add_router("/", ask_router)
api.add_router("/schema", schema_router)
api.add_router("/agent", agent_router)
api.add_router("/workspaces", workspaces_router)
api.add_router("/workspaces", workspace_tables_router)

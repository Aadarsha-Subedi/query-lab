"""The one NinjaAPI, mounted at /api/. Default throttles apply to every route:
signed-out callers by IP, signed-in callers by user."""

from ninja import NinjaAPI

from accounts.api import router as accounts_router
from ask.api import router as ask_router
from common.exception.handler import install_exception_handlers
from common.throttling.scoped import AnonThrottle, UserThrottle
from core.api import router as core_router

api = NinjaAPI(
    title="Querylab API",
    version="0.1.0",
    throttle=[AnonThrottle(), UserThrottle()],
    urls_namespace="api",
)
install_exception_handlers(api)

api.add_router("/", core_router)
api.add_router("/", accounts_router)
api.add_router("/", ask_router)

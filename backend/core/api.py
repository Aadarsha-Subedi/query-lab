from typing import Literal

from django.http import HttpRequest
from ninja import Router, Schema, Status

from core.health import DEGRADED, OK, run_checks

router = Router(tags=["core"])

CheckStatus = Literal["ok", "fail"]


class HealthOut(Schema):
    status: Literal["ok", "degraded"]
    app_db: CheckStatus
    data_db: CheckStatus
    data_reader: CheckStatus
    redis: CheckStatus
    worker: CheckStatus


@router.get("/health", response={200: HealthOut, 503: HealthOut}, auth=None)
def health(request: HttpRequest) -> Status[dict[str, str]]:
    """Every dependency the backend needs. Not wrapped in the envelope, so
    uptime checks can read `status` directly; 503 when anything fails."""
    results = run_checks()
    healthy = all(value == OK for value in results.values())
    return Status(
        200 if healthy else 503, {"status": OK if healthy else DEGRADED, **results}
    )

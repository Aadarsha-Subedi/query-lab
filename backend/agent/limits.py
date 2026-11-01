"""What is left before the user hits a limit, for the analyst screen. Read only:
it counts, it never spends, expires or changes anything."""

from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.utils import timezone

from accounts.models import User
from agent.models import AgentRun
from agent.stream import STREAMS_KEY
from ask import keys
from ask.models import UserAISetting, UserLLMKey
from common.redis import get_redis


def uses_own_key(user: User) -> bool:
    """True when this user's asks run on their own active key, not QueryLab's."""
    return (
        keys.ai_source(user) == UserAISetting.SOURCE_OWN
        and UserLLMKey.objects.filter(user=user, is_active=True).exists()
    )


def _next_utc_midnight() -> datetime:
    tomorrow = datetime.now(UTC) + timedelta(days=1)
    return tomorrow.replace(hour=0, minute=0, second=0, microsecond=0)


def limits_for(user: User) -> dict[str, Any]:
    allowed = settings.ASK_DEFAULT_KEY_DAILY_LIMIT
    used = keys.default_key_spent_today(user)
    # A pause nobody answered in time no longer counts: the next start expires it.
    stale_before = timezone.now() - timedelta(
        seconds=settings.AGENT_APPROVAL_TTL_SECONDS
    )
    unfinished = (
        AgentRun.objects.filter(user=user, status__in=AgentRun.ACTIVE)
        .exclude(status=AgentRun.STATUS_AWAITING_APPROVAL, updated_at__lt=stale_before)
        .count()
    )
    open_streams = max(int(get_redis().get(STREAMS_KEY) or 0), 0)
    return {
        "default_key": {
            "used": used,
            "allowed": allowed,
            "remaining": allowed - used,
            "resets_at": _next_utc_midnight(),
        },
        "has_own_key": uses_own_key(user),
        "unfinished_runs": {
            "count": unfinished,
            "allowed": settings.AGENT_MAX_CONCURRENT_RUNS_PER_USER,
        },
        "streams": {
            "open": open_streams,
            "allowed": settings.AGENT_MAX_OPEN_STREAMS,
        },
    }

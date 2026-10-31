"""Ninja throttles. Rates come from settings (THROTTLE_*_RATE in .env) and
counters live in the Django cache (Redis), so limits hold across processes.

Keyed on the Django session user rather than ninja's `request.auth`, so a
signed-in visitor on a public route is not counted as anonymous traffic.

- AnonThrottle: signed-out callers, keyed by client IP.
- UserThrottle: signed-in callers, keyed by user id.
- AgentThrottle: the same, for starting agent runs.
- AskThrottle:  the stricter per-route limit for endpoints that call the LLM,
                per user when signed in, per IP otherwise.
"""

from django.conf import settings
from django.http import HttpRequest
from ninja.throttling import SimpleRateThrottle


def _is_signed_in(request: HttpRequest) -> bool:
    user = getattr(request, "user", None)
    return bool(user is not None and user.is_authenticated)


class SettingsRateThrottle(SimpleRateThrottle):
    """Reads its rate from the named setting on every request, so a changed
    setting (or a test's override_settings) applies without a restart."""

    rate_setting: str

    def __init__(self) -> None:
        super().__init__(getattr(settings, self.rate_setting))

    def allow_request(self, request: HttpRequest) -> bool:
        self.rate = getattr(settings, self.rate_setting)
        self.num_requests, self.duration = self.parse_rate(self.rate)
        return super().allow_request(request)


class AnonThrottle(SettingsRateThrottle):
    scope = "anon"
    rate_setting = "THROTTLE_ANON_RATE"

    def get_cache_key(self, request: HttpRequest) -> str | None:
        if _is_signed_in(request):
            return None
        return self.cache_format % {
            "scope": self.scope,
            "ident": self.get_ident(request),
        }


class UserThrottle(SettingsRateThrottle):
    scope = "user"
    rate_setting = "THROTTLE_USER_RATE"

    def get_cache_key(self, request: HttpRequest) -> str | None:
        if not _is_signed_in(request):
            return None
        return self.cache_format % {"scope": self.scope, "ident": request.user.pk}


class AskThrottle(SettingsRateThrottle):
    scope = "ask"
    rate_setting = "THROTTLE_ASK_RATE"

    def get_cache_key(self, request: HttpRequest) -> str | None:
        ident = request.user.pk if _is_signed_in(request) else self.get_ident(request)
        return self.cache_format % {"scope": self.scope, "ident": ident}


class AgentThrottle(AskThrottle):
    scope = "agent"
    rate_setting = "THROTTLE_AGENT_RATE"

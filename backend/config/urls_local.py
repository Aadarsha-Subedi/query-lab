"""Local development URLs: the normal ones plus the dev-only OAuth test page.
Selected by config/settings/local.py; prod and test keep config.urls."""

from django.urls import path

from accounts import dev
from config.urls import urlpatterns as base_urlpatterns

urlpatterns = [
    *base_urlpatterns,
    path("dev/", dev.index, name="dev-index"),
    path("dev/session", dev.session, name="dev-session"),
]

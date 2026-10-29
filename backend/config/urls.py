from django.urls import include, path

from config.api import api

urlpatterns = [
    path("api/", api.urls),
    # allauth headless JSON API for the React app.
    path("_allauth/", include("allauth.headless.urls")),
    # With HEADLESS_ONLY this serves only the OAuth provider callbacks
    # (/accounts/<provider>/login/callback/).
    path("accounts/", include("allauth.urls")),
]

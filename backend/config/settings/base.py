"""Settings shared by every environment.

Every value comes from the environment through django-environ, and none has a
default: `env("NAME")` raises ImproperlyConfigured when NAME is missing, so the
process refuses to start half-configured. The full list of keys lives in
`backend/.env.example`; a test keeps the two in sync.
"""

from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()

# ── Django ────────────────────────────────────────────────────────────────

SECRET_KEY = env.str("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS")
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS")
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS")
FRONTEND_URL = env.str("FRONTEND_URL")

INSTALLED_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "corsheaders",
    "allauth",
    "allauth.account",
    "allauth.socialaccount",
    "allauth.socialaccount.providers.google",
    "allauth.socialaccount.providers.github",
    "allauth.headless",
    "huey.contrib.djhuey",
    "common",
    "core",
    "accounts",
]

MIDDLEWARE = [
    "common.logger.request_id.RequestIdMiddleware",
    "common.observability.timing.RequestTimingMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "common.logger.request_id.UserContextMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
    "common.logger.middleware.RequestLoggingMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── Databases ─────────────────────────────────────────────────────────────
# default:     querylab_app (Django models, migrations, users, sessions)
# data:        querylab as its owner role (bootstrap and demo imports)
# data_reader: querylab as querylab_reader (agent queries; the Neon replica
#              once deployed). Read-only is enforced by the role itself.

DATA_DB_ALIAS = "data"
DATA_READER_DB_ALIAS = "data_reader"

DATABASES = {
    "default": env.db_url("APP_DATABASE_URL"),
    DATA_DB_ALIAS: env.db_url("DATA_PRIMARY_URL"),
    DATA_READER_DB_ALIAS: env.db_url("DATA_READER_URL"),
}
DATABASE_ROUTERS = ["core.routers.AppOnlyRouter"]

READER_STATEMENT_TIMEOUT_MS = env.int("READER_STATEMENT_TIMEOUT_MS")

# infra/sql, applied in order by `bootstrap_data_db`.
DATA_SQL_DIR = env.path("DATA_SQL_DIR")

# Where `load_demo` reads the Olist CSVs from, and how far every date moves.
DEMO_DATA_DIR = env.path("DEMO_DATA_DIR")
DEMO_DATE_SHIFT_DAYS = env.int("DEMO_DATE_SHIFT_DAYS")

# ── Auth ──────────────────────────────────────────────────────────────────

AUTH_USER_MODEL = "accounts.User"

AUTHENTICATION_BACKENDS = [
    "django.contrib.auth.backends.ModelBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]

PASSWORD_MIN_LENGTH = env.int("PASSWORD_MIN_LENGTH")

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
        "OPTIONS": {"min_length": PASSWORD_MIN_LENGTH},
    },
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
    {"NAME": "common.validators.password.MixedCaseValidator"},
]

BLOCK_DISPOSABLE_EMAILS = env.bool("BLOCK_DISPOSABLE_EMAILS")

# allauth, sign-in with Google or GitHub only (owner's choice, 2026-10-30):
# no email/password signup or login, so no verification, reset or other
# account emails. JSON (headless) API only.
SOCIALACCOUNT_ONLY = True
HEADLESS_ONLY = True
# No local login method at all: every sign-in goes through a provider.
ACCOUNT_LOGIN_METHODS: set[str] = set()
ACCOUNT_SIGNUP_FIELDS = ["email*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_VERIFICATION = "none"
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
HEADLESS_FRONTEND_URLS = {
    "socialaccount_login_error": f"{FRONTEND_URL}/auth/callback",
}

# Identity is the provider account (provider + uid), never the email. The same
# email through Google and through GitHub gives two separate users: no
# linking by email (SOCIALACCOUNT_EMAIL_AUTHENTICATION stays off), and emails
# are not unique (ACCOUNT_UNIQUE_EMAIL; the User.email column too).
ACCOUNT_UNIQUE_EMAIL = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION = False
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = False
SOCIALACCOUNT_AUTO_SIGNUP = True

# Checks that assume a local (email/password) login, which Querylab does not
# have: auth.W004 (USERNAME_FIELD email is not unique; it only shows who is
# signed in), account.W001 (no local login method to cross-check against the
# signup fields) and mail.W001 (no mailer, on purpose; see MAILERS below).
SILENCED_SYSTEM_CHECKS = ["auth.W004", "account.W001", "mail.W001"]

SOCIALACCOUNT_PROVIDERS = {
    "google": {
        "APPS": [
            {
                "client_id": env.str("GOOGLE_CLIENT_ID"),
                "secret": env.str("GOOGLE_CLIENT_SECRET"),
            }
        ],
        "SCOPE": ["profile", "email"],
        "VERIFIED_EMAIL": True,
    },
    "github": {
        "APPS": [
            {
                "client_id": env.str("GITHUB_CLIENT_ID"),
                "secret": env.str("GITHUB_CLIENT_SECRET"),
            }
        ],
        "SCOPE": ["user:email"],
        "VERIFIED_EMAIL": True,
    },
}

# ── Rate limits ───────────────────────────────────────────────────────────
# Our endpoints use ninja throttles, counted in the Django cache (Redis), so
# limits hold across every process. allauth's own limits cover only the
# email/password endpoints, which are off (SOCIALACCOUNT_ONLY).

THROTTLE_ANON_RATE = env.str("THROTTLE_ANON_RATE")
THROTTLE_USER_RATE = env.str("THROTTLE_USER_RATE")
THROTTLE_ASK_RATE = env.str("THROTTLE_ASK_RATE")

# Real client IP behind proxies (0 locally, the proxy hops in production).
TRUSTED_PROXY_COUNT = env.int("TRUSTED_PROXY_COUNT")
ALLAUTH_TRUSTED_PROXY_COUNT = TRUSTED_PROXY_COUNT
NINJA_NUM_PROXIES = TRUSTED_PROXY_COUNT

# ── Pagination ────────────────────────────────────────────────────────────

PAGINATION_DEFAULT_LIMIT = env.int("PAGINATION_DEFAULT_LIMIT")
PAGINATION_MAX_LIMIT = env.int("PAGINATION_MAX_LIMIT")

# ── Cache, Redis and Huey ─────────────────────────────────────────────────

CACHES = {"default": env.cache_url("CACHE_URL")}
CACHE_DEFAULT_TIMEOUT_SECONDS = env.int("CACHE_DEFAULT_TIMEOUT_SECONDS")

REDIS_URL = env.str("REDIS_URL")

HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "querylab",
    "url": REDIS_URL,
    "immediate": env.bool("HUEY_IMMEDIATE"),
    "consumer": {
        "workers": env.int("HUEY_WORKERS"),
        "worker_type": "thread",
    },
}

HEALTH_CHECK_TIMEOUT_SECONDS = env.float("HEALTH_CHECK_TIMEOUT_SECONDS")

# ── Email ─────────────────────────────────────────────────────────────────
# Querylab sends no email (sign-in is Google/GitHub only). An explicitly empty
# MAILERS means any attempt to send fails loudly instead of using a default.
MAILERS: dict[str, dict[str, object]] = {}

# ── Secrets at rest and LLM providers ─────────────────────────────────────

# Fernet keys, newest first; the first encrypts, all decrypt.
ENCRYPTION_KEYS = env.list("ENCRYPTION_KEYS")

LLM_REQUEST_TIMEOUT_SECONDS = env.int("LLM_REQUEST_TIMEOUT_SECONDS")
LLM_MAX_OUTPUT_TOKENS = env.int("LLM_MAX_OUTPUT_TOKENS")
LLM_TEMPERATURE = env.float("LLM_TEMPERATURE")
LLM_OPENAI_MODELS = env.list("LLM_OPENAI_MODELS")
LLM_GEMINI_MODELS = env.list("LLM_GEMINI_MODELS")

# ── Workspaces (step 5) ───────────────────────────────────────────────────

MAX_WORKSPACES_PER_USER = env.int("MAX_WORKSPACES_PER_USER")

# ── Logging ───────────────────────────────────────────────────────────────

LOG_LEVEL = env.str("LOG_LEVEL")
LOG_FORMAT = env.str("LOG_FORMAT")  # "json" (production) or "color" (local)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {"request_id": {"()": "common.logger.request_id.RequestIdFilter"}},
    "formatters": {
        "json": {"()": "common.logger.formatters.JSONFormatter"},
        "color": {
            "()": "common.logger.formatters.ColorFormatter",
            "format": "%(asctime)s %(levelname)s %(name)s [%(request_id)s] %(message)s",
        },
    },
    "handlers": {
        "stdout": {
            "class": "logging.StreamHandler",
            "formatter": LOG_FORMAT,
            "filters": ["request_id"],
        }
    },
    "root": {"handlers": ["stdout"], "level": LOG_LEVEL},
}

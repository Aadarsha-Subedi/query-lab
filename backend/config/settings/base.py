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
        "DIRS": [BASE_DIR / "templates"],
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

# allauth: email-only login, mandatory verification, JSON (headless) API only.
ACCOUNT_ADAPTER = "accounts.adapters.AccountAdapter"
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*"]
ACCOUNT_USER_MODEL_USERNAME_FIELD = None
ACCOUNT_UNIQUE_EMAIL = True
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION = True
ACCOUNT_EMAIL_SUBJECT_PREFIX = ""
ACCOUNT_CONFIRM_EMAIL_ON_GET = False

HEADLESS_ONLY = True
HEADLESS_FRONTEND_URLS = {
    "account_confirm_email": f"{FRONTEND_URL}/verify-email/{{key}}",
    "account_reset_password_from_key": f"{FRONTEND_URL}/reset-password/{{key}}",
    "account_signup": f"{FRONTEND_URL}/signup",
    "socialaccount_login_error": f"{FRONTEND_URL}/auth/callback",
}

# Social login links to an existing account by verified email, so one person
# signing in with email and later with Google lands in the same account.
SOCIALACCOUNT_EMAIL_AUTHENTICATION = True
SOCIALACCOUNT_EMAIL_AUTHENTICATION_AUTO_CONNECT = True
SOCIALACCOUNT_EMAIL_REQUIRED = True
SOCIALACCOUNT_QUERY_EMAIL = True
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
# allauth limits its own endpoints; ninja throttles limit ours. Both count in
# the Django cache (Redis), so limits hold across every process.

ACCOUNT_RATE_LIMITS = {
    "login": env.str("RATE_LIMIT_LOGIN"),
    "login_failed": env.str("RATE_LIMIT_LOGIN_FAILED"),
    "signup": env.str("RATE_LIMIT_SIGNUP"),
    "confirm_email": env.str("RATE_LIMIT_CONFIRM_EMAIL"),
    "reset_password": env.str("RATE_LIMIT_RESET_PASSWORD"),
    "change_password": env.str("RATE_LIMIT_CHANGE_PASSWORD"),
}
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

# Django 6.1 mailers (replace the deprecated EMAIL_* settings). The test runner
# swaps the default mailer for the in-memory one, so tests never send mail.
MAILERS = {
    "default": {
        "BACKEND": env.str("EMAIL_BACKEND"),
        "OPTIONS": {
            "host": env.str("EMAIL_HOST"),
            "port": env.int("EMAIL_PORT"),
            "username": env.str("EMAIL_HOST_USER"),
            "password": env.str("EMAIL_HOST_PASSWORD"),
            "use_tls": env.bool("EMAIL_USE_TLS"),
            "timeout": env.int("EMAIL_TIMEOUT_SECONDS"),
        },
    }
}
DEFAULT_FROM_EMAIL = env.str("DEFAULT_FROM_EMAIL")

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

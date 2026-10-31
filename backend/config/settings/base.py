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
# The session cookie and the CSRF header must cross origins (the frontend and the
# API can be on different origins). corsheaders only answers this for the origins
# listed above, so credentials are never offered to any other origin.
CORS_ALLOW_CREDENTIALS = True
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
    "ask",
    "agent",
    "evals",
    "workspaces",
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
THROTTLE_WORKSPACE_RATE = env.str("THROTTLE_WORKSPACE_RATE")
THROTTLE_WORKSPACE_SQL_RATE = env.str("THROTTLE_WORKSPACE_SQL_RATE")

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

# ── Ask: text-to-SQL (step 1) ─────────────────────────────────────────────

ASK_MAX_QUESTION_CHARS = env.int("ASK_MAX_QUESTION_CHARS")
ASK_MAX_ROWS = env.int("ASK_MAX_ROWS")
ASK_MAX_RESULT_BYTES = env.int("ASK_MAX_RESULT_BYTES")
ASK_MAX_REPAIR_ATTEMPTS = env.int("ASK_MAX_REPAIR_ATTEMPTS")
ASK_SCHEMA_CACHE_SECONDS = env.int("ASK_SCHEMA_CACHE_SECONDS")
ASK_SAMPLE_VALUES_MAX = env.int("ASK_SAMPLE_VALUES_MAX")
ASK_SAMPLE_VALUES_MAX_DISTINCT = env.int("ASK_SAMPLE_VALUES_MAX_DISTINCT")
ASK_DENIED_FUNCTIONS = [name.lower() for name in env.list("ASK_DENIED_FUNCTIONS")]
ASK_DEFAULT_KEY_DAILY_LIMIT = env.int("ASK_DEFAULT_KEY_DAILY_LIMIT")

# QueryLab's own key, used when a user has not saved one. Never stored in the
# database or logged.
LLM_DEFAULT_GEMINI_API_KEY = env.str("LLM_DEFAULT_GEMINI_API_KEY")
LLM_DEFAULT_MODEL = env.str("LLM_DEFAULT_MODEL")

# Confidence heuristic (shared by /ask and the agent). The model's own rating is
# not an input: it sat near 1.0 on every answer.
CONFIDENCE_WEIGHT_CLEAN_GUARD = env.float("CONFIDENCE_WEIGHT_CLEAN_GUARD")
CONFIDENCE_WEIGHT_NO_REVISION = env.float("CONFIDENCE_WEIGHT_NO_REVISION")
CONFIDENCE_WEIGHT_NON_EMPTY = env.float("CONFIDENCE_WEIGHT_NON_EMPTY")
CONFIDENCE_WEIGHT_REFLECT_OK = env.float("CONFIDENCE_WEIGHT_REFLECT_OK")
CONFIDENCE_WEIGHT_SAMPLES_CHECKED = env.float("CONFIDENCE_WEIGHT_SAMPLES_CHECKED")
CONFIDENCE_PENALTY_TRUNCATED = env.float("CONFIDENCE_PENALTY_TRUNCATED")
CONFIDENCE_MIN_SEPARATION = env.float("CONFIDENCE_MIN_SEPARATION")
CONFIDENCE_SHOW_SCORE = env.bool("CONFIDENCE_SHOW_SCORE")

# ── Agent (step 3) ────────────────────────────────────────────────────────

AGENT_MAX_STEPS = env.int("AGENT_MAX_STEPS")
AGENT_MAX_LLM_CALLS = env.int("AGENT_MAX_LLM_CALLS")
AGENT_MAX_TOKENS = env.int("AGENT_MAX_TOKENS")
AGENT_MAX_REVISIONS = env.int("AGENT_MAX_REVISIONS")
AGENT_MAX_PARSE_RETRIES = env.int("AGENT_MAX_PARSE_RETRIES")
AGENT_RUN_TIMEOUT_SECONDS = env.int("AGENT_RUN_TIMEOUT_SECONDS")
AGENT_STATE_TTL_SECONDS = env.int("AGENT_STATE_TTL_SECONDS")
AGENT_APPROVAL_TTL_SECONDS = env.int("AGENT_APPROVAL_TTL_SECONDS")
AGENT_RESULT_PREVIEW_ROWS = env.int("AGENT_RESULT_PREVIEW_ROWS")
AGENT_STEP_OUTPUT_MAX_CHARS = env.int("AGENT_STEP_OUTPUT_MAX_CHARS")
AGENT_SAMPLE_VALUES_LIMIT = env.int("AGENT_SAMPLE_VALUES_LIMIT")
AGENT_FULL_SCHEMA_START = env.bool("AGENT_FULL_SCHEMA_START")
AGENT_REFLECT_ALWAYS = env.bool("AGENT_REFLECT_ALWAYS")
AGENT_MAX_CONCURRENT_RUNS_PER_USER = env.int("AGENT_MAX_CONCURRENT_RUNS_PER_USER")
AGENT_MAX_OPEN_STREAMS = env.int("AGENT_MAX_OPEN_STREAMS")
AGENT_SSE_HEARTBEAT_SECONDS = env.int("AGENT_SSE_HEARTBEAT_SECONDS")
AGENT_SSE_READ_BLOCK_MS = env.int("AGENT_SSE_READ_BLOCK_MS")
AGENT_SSE_MAX_SECONDS = env.int("AGENT_SSE_MAX_SECONDS")
AGENT_EVENTS_MAXLEN = env.int("AGENT_EVENTS_MAXLEN")
THROTTLE_AGENT_RATE = env.str("THROTTLE_AGENT_RATE")

# ── Analyst API (step 4) ──────────────────────────────────────────────────

SCHEMA_API_INCLUDE_SAMPLES = env.bool("SCHEMA_API_INCLUDE_SAMPLES")
THROTTLE_RESULT_RATE = env.str("THROTTLE_RESULT_RATE")

# ── Evals (step 2) ────────────────────────────────────────────────────────

EVAL_ROW_COMPARE_PRECISION = env.int("EVAL_ROW_COMPARE_PRECISION")
EVAL_MAX_COMPARE_ROWS = env.int("EVAL_MAX_COMPARE_ROWS")
EVAL_QUERY_TIMEOUT_MS = env.int("EVAL_QUERY_TIMEOUT_MS")
EVAL_OPENAI_API_KEY = env.str("EVAL_OPENAI_API_KEY")
EVAL_SPIDER_DIR = env.path("EVAL_SPIDER_DIR")
EVAL_CONFIDENCE_BUCKETS = sorted(
    float(edge) for edge in env.list("EVAL_CONFIDENCE_BUCKETS")
)
EVAL_LLM_RETRIES = env.int("EVAL_LLM_RETRIES")
EVAL_RETRY_BACKOFF_SECONDS = env.int("EVAL_RETRY_BACKOFF_SECONDS")
EVAL_CALL_DELAY_SECONDS = env.float("EVAL_CALL_DELAY_SECONDS")
EVAL_CONFIRM_ABOVE_CALLS = env.int("EVAL_CONFIRM_ABOVE_CALLS")
# model -> (input, output) USD per million tokens; an estimate for reports only.
EVAL_MODEL_PRICES = {
    name: (float(price_in), float(price_out))
    for name, price_in, price_out in (
        entry.split(":") for entry in env.list("EVAL_MODEL_PRICES")
    )
}

# ── Workspaces (step 5) ───────────────────────────────────────────────────

MAX_WORKSPACES_PER_USER = env.int("MAX_WORKSPACES_PER_USER")
WORKSPACE_MAX_TABLES = env.int("WORKSPACE_MAX_TABLES")
WORKSPACE_MAX_RELATIONS = env.int("WORKSPACE_MAX_RELATIONS")
WORKSPACE_MAX_BYTES = env.int("WORKSPACE_MAX_BYTES")
USER_MAX_BYTES = env.int("USER_MAX_BYTES")
WORKSPACE_MAX_ROWS_PER_EDIT = env.int("WORKSPACE_MAX_ROWS_PER_EDIT")
WORKSPACE_NAME_MAX_LENGTH = env.int("WORKSPACE_NAME_MAX_LENGTH")
WORKSPACE_DESCRIPTION_MAX_LENGTH = env.int("WORKSPACE_DESCRIPTION_MAX_LENGTH")
QUOTA_CACHE_SECONDS = env.int("QUOTA_CACHE_SECONDS")
WORKSPACE_SQL_MAX_CHARS = env.int("WORKSPACE_SQL_MAX_CHARS")
WORKSPACE_SQL_MAX_STATEMENTS = env.int("WORKSPACE_SQL_MAX_STATEMENTS")
WORKSPACE_SQL_MAX_ROWS = env.int("WORKSPACE_SQL_MAX_ROWS")
WORKSPACE_SQL_MAX_CONCURRENT = env.int("WORKSPACE_SQL_MAX_CONCURRENT")

WORKSPACE_MAX_COLUMNS = env.int("WORKSPACE_MAX_COLUMNS")
WORKSPACE_DDL_TIMEOUT_MS = env.int("WORKSPACE_DDL_TIMEOUT_MS")

MASTER_WORKSPACE_SECRET = env.str("MASTER_WORKSPACE_SECRET")
WORKSPACE_PRIMARY_CONNINFO = env.str("WORKSPACE_PRIMARY_CONNINFO")
WORKSPACE_READER_CONNINFO = env.str("WORKSPACE_READER_CONNINFO")
WORKSPACE_STATEMENT_TIMEOUT_MS = env.int("WORKSPACE_STATEMENT_TIMEOUT_MS")
WORKSPACE_IDLE_TX_TIMEOUT_MS = env.int("WORKSPACE_IDLE_TX_TIMEOUT_MS")
WORKSPACE_RW_CONNECTION_LIMIT = env.int("WORKSPACE_RW_CONNECTION_LIMIT")
WORKSPACE_RO_CONNECTION_LIMIT = env.int("WORKSPACE_RO_CONNECTION_LIMIT")

# ── Trace-driven evals (step 6) ───────────────────────────────────────────

TRACES_CANDIDATE_MAX_AGE_DAYS = env.int("TRACES_CANDIDATE_MAX_AGE_DAYS")
TRACES_CLUSTER_SIMILARITY = env.float("TRACES_CLUSTER_SIMILARITY")
TRACES_CLUSTER_MAX_RUNS = env.int("TRACES_CLUSTER_MAX_RUNS")
TRACES_DRAFT_MODEL = env.str("TRACES_DRAFT_MODEL")
TRACES_DRAFT_MAX_PER_BATCH = env.int("TRACES_DRAFT_MAX_PER_BATCH")
TRACES_PAGE_SIZE_MAX = env.int("TRACES_PAGE_SIZE_MAX")
EVAL_GATE_MAX_DROP_POINTS = env.float("EVAL_GATE_MAX_DROP_POINTS")
EVAL_GATE_MIN_CASES = env.int("EVAL_GATE_MIN_CASES")

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

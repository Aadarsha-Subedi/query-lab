# Backend: FLOW.md

## Request path

```
browser ──> Vite dev proxy (/api, /_allauth, /accounts)  [prod: same domain, Cloudflare]
        ──> Django
              RequestIdMiddleware        X-Request-ID on every response and log line
              RequestTimingMiddleware    Server-Timing header (total, db, cpu)
              CorsMiddleware, Security, Session, Common, Csrf, Auth
              UserContextMiddleware      user id into the log context
              allauth AccountMiddleware
              RequestLoggingMiddleware   one redacted log line per request
        ──> urls.py
              /api/        NinjaAPI (config/api.py)
                             default throttles: AnonThrottle (IP) + UserThrottle (user)
                             routers: core (/health), accounts (/me)
                             errors -> common/exception/handler.py -> error envelope
              /_allauth/   allauth headless JSON API (browser client)
              /accounts/   OAuth provider callbacks only (HEADLESS_ONLY)
```

Responses: `{success, status_code, message, data, meta}` or
`{success: false, status_code, message, code, errors: [{field, message}]}`.
`/api/health` is the exception: it returns its fields directly.

## Auth flow (allauth headless)

Email signup:

```
POST /_allauth/browser/v1/auth/signup {email, password}
  -> AccountAdapter.clean_email (refuses disposable domains)
  -> password validators (length from PASSWORD_MIN_LENGTH, mixed case, common, numeric)
  -> confirmation email: templates/account/email/* rendered as text,
     AccountAdapter.render_mail adds the HTML version (common/email/render.py)
  <- 401 with flows: [verify_email pending]   (verification is mandatory)
user clicks FRONTEND_URL/verify-email/<key>
  frontend POST /_allauth/browser/v1/auth/email/verify {key}
  <- 200, signed in (ACCOUNT_LOGIN_ON_EMAIL_CONFIRMATION)
```

Login: `POST /_allauth/browser/v1/auth/login` (blocked with 401 until the
address is verified; 429 after RATE_LIMIT_LOGIN_FAILED). Logout:
`DELETE /_allauth/browser/v1/auth/session`. Session cookie + CSRF cookie are
shared by the frontend and API (same origin through the proxy).

Google / GitHub:

```
frontend form POST /_allauth/browser/v1/auth/provider/redirect
     {provider, callback_url: FRONTEND_URL/auth/callback, process: login}
  -> provider consent screen
  -> GET /accounts/<provider>/login/callback/   (through the same origin)
  -> existing verified email? log in to that account and connect the provider
     (SOCIALACCOUNT_EMAIL_AUTHENTICATION + AUTO_CONNECT); otherwise sign up
  -> redirect to callback_url; the frontend calls /api/me
```

`GET /api/me` returns the user or 401; the frontend's route guards use it. It
also sets the `csrftoken` cookie (`ensure_csrf_cookie`), signed in or not: the
frontend calls it at every boot, so its first POST already has a token.

## Rate limits

```
allauth endpoints  -> ACCOUNT_RATE_LIMITS (RATE_LIMIT_* from .env) -> Django cache (Redis)
ninja endpoints    -> AnonThrottle / UserThrottle (+ AskThrottle per route) -> Django cache
throttled          -> 429 + Retry-After
client IP          -> TRUSTED_PROXY_COUNT hops (allauth + ninja)
```

## Background jobs (Huey)

```
web process: task() ──enqueue──> Redis (REDIS_URL) <──consume── run_huey (thread workers: HUEY_WORKERS)
                                     results in Redis
tests: HUEY_IMMEDIATE=true -> tasks run inline, in memory
```

Locally the worker is its own compose service; in production `entrypoint.sh`
runs `run_huey` beside gunicorn in the same container.

## Health

`GET /api/health` runs five checks in parallel threads with one shared
deadline (HEALTH_CHECK_TIMEOUT_SECONDS): `SELECT 1` on default, data and
data_reader, Redis `PING`, and the `common.tasks.ping` Huey task round trip.
Any failure: `status: degraded`, HTTP 503.

## Database topology

```
                    ┌──────────────────────── Postgres ────────────────────────┐
Django default ───> │ querylab_app   users, sessions, allauth, (later) runs     │
 (migrations)       │                PUBLIC has no CONNECT                       │
                    │                                                            │
Django data ──────> │ querylab       schema demo (Olist, from infra/sql/010)     │
 (owner role;       │                no Django migrations, ever                  │
  bootstrap, load)  │                                                            │
                    │                                                            │
Django data_reader >│ querylab       as querylab_reader:                         │
 (the agent)        │                USAGE on demo, SELECT on its tables,        │
                    │                default_transaction_read_only = on,         │
                    │                statement_timeout = READER_STATEMENT_TIMEOUT_MS,
                    │                no CREATE anywhere, no TEMP                 │
                    └────────────────────────────────────────────────────────────┘
Deployed: the same, on Neon; data_reader points at the Neon read replica.
```

## Data setup

```
make migrate        Django migrations on querylab_app
make bootstrap-db   infra/sql/001_roles.sql -> 010_demo_schema.sql -> 020_reader_grants.sql
                    (placeholders filled from settings by core/datadb.py; one transaction)
make load-demo      core/demo.py: TRUNCATE demo.*, then per CSV:
                    COPY -> temp text table -> INSERT ... SELECT (translate categories,
                    shift dates by DEMO_DATE_SHIFT_DAYS); one transaction
```

## Trying the API by hand

`backend/postman/` holds a Postman collection for every endpoint and a local
environment (see its README). Run *Get CSRF cookie and current user* first; the
collection then sends the CSRF token on every write.

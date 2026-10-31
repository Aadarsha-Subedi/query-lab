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

## Auth flow (allauth headless, social only)

Sign-in is Google or GitHub only (`SOCIALACCOUNT_ONLY`): there is no email or
password signup, login, verification or reset, and the backend sends no email.

```
frontend form POST /_allauth/browser/v1/auth/provider/redirect
     {provider, callback_url: FRONTEND_URL/auth/callback, process: login}
  -> provider consent screen
  -> GET /accounts/<provider>/login/callback/   (through the same origin)
  -> SocialAccount (provider, uid) exists? sign in as its user
     otherwise create a new user (SOCIALACCOUNT_AUTO_SIGNUP) with the provider's email
  -> redirect to callback_url; the frontend calls /api/me
```

Identity is the provider account (provider + uid), never the email: the same
email through Google and through GitHub gives two separate users, and nothing
links accounts by email (`SOCIALACCOUNT_EMAIL_AUTHENTICATION` is off, emails are
not unique).

Logout: `DELETE /_allauth/browser/v1/auth/session`. Session cookie + CSRF cookie
are shared by the frontend and API (same origin through the proxy).

`GET /api/me` returns the user (with `providers`: `google` or `github`) or 401;
the frontend's route guards use it. It also sets the `csrftoken` cookie
(`ensure_csrf_cookie`), signed in or not: the frontend calls it at every boot,
so its first POST already has a token.

## Dev sign-in page (local only)

```
open http://localhost:8000/dev/            (config/urls_local.py, set by settings/local.py)
  -> Continue with Google/GitHub           form POST /_allauth/browser/v1/auth/provider/redirect
                                           callback_url=/dev/, process=login
  -> provider -> /accounts/<provider>/login/callback/ -> back to /dev/
  -> page GETs /dev/session                {authenticated, session_key, email}
  -> textarea shows the session key        Postman sends it as Cookie: sessionid=<key>
```

`prod` and `test` use `config.urls`, which has no `/dev/` routes. The OAuth
callback returns to the host you opened, so the provider apps need
`http://localhost:8000/accounts/<provider>/login/callback/` as a redirect URI.

## Rate limits

```
ninja endpoints    -> AnonThrottle / UserThrottle (+ AskThrottle per route) -> Django cache
throttled          -> 429 + Retry-After
client IP          -> TRUSTED_PROXY_COUNT hops (ninja; allauth's IP lookup too)
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

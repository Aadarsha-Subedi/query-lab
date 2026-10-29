# Backend: DECISION.md

One entry per decision: what, why, and what it costs. Newest at the bottom.

## Django + django-ninja

Django gives the ORM, migrations, sessions and allauth; django-ninja gives typed
request/response schemas (pydantic) and OpenAPI without DRF's serializer layer.
Ninja is smaller and faster to write for a JSON-only API. Cost: DRF-specific
code from resolve-ai / Pro-Goal had to be rewritten (exception handler,
response envelope, pagination, throttles).

## uv, Python 3.12, dependency groups

`uv` for a fast, locked install (`uv.lock`). Python 3.12 (pinned `>=3.12,<3.13`).
The production image installs only `[project].dependencies` (the plan's "main"
set). Groups: `test` (pytest, pytest-django) is added in the dev image; `lint`
(ruff, mypy, django-stubs, pre-commit) runs on the host and in CI only, so the
dev image no longer downloads ~35 MB of tools it never runs; `offline` (heavy
tools: clustering, dataset building, benchmarks, training) never reaches any
image. `uv sync` on the host installs `test` and `lint`.

## Two databases on one Postgres

`querylab_app` holds Django's own tables (users, sessions, later runs and evals),
managed by migrations. `querylab` holds the data the agent queries (the `demo`
schema, later per-user schemas). Keeping them apart means the reader role can be
locked out of app data entirely (PUBLIC has no CONNECT on `querylab_app`), and a
bad agent query can never touch users or sessions.

Django sees three aliases: `default` (querylab_app), `data` (querylab as owner, for
bootstrap and imports) and `data_reader` (querylab as `querylab_reader`).
`AppOnlyRouter` routes every model to `default` and migrates only `default`.

## Schema per tenant (from step 5)

Each user's own workspaces will be schemas in `querylab`, next to the shared
read-only `demo`. Schemas give real isolation through grants and a simple
`search_path`, without a database per user.

## Read-only boundary enforced by the role

`querylab_reader` gets USAGE on `demo` and SELECT on its tables, nothing else: no
CREATE on any schema, no TEMP on the database, no CONNECT on `querylab_app`.
`default_transaction_read_only = on` and `statement_timeout` are role defaults
(a session could SET them back), so they stop accidents and runaway reads; the
privileges are what stop writes. Tests check both, including after switching
read-only off.

## Read replica in production, no local replica

Deployed, `DATA_READER_URL` points at the Neon read replica, so agent queries
never load the primary. Locally there is no replica: `DATA_READER_URL` points at
the local `querylab` database with the reader role. The rules live in the role,
so local behaviour matches production.

## Strict environment: no defaults, no magic numbers

Every setting is `env.<type>("KEY")` with no default, so a missing key raises
`ImproperlyConfigured` at startup instead of running half-configured. Every
timeout, limit, size and rate lives in `.env`. `core/tests/test_env.py` scans the
code for every key it reads and fails unless `.env.example` (and `.env.test`)
list exactly those keys.

`DJANGO_SETTINGS_MODULE` has no default either: `manage.py`, `wsgi.py` and
`asgi.py` refuse to start without it.

## Test settings load a committed `.env.test`

`config.settings.test` loads `backend/.env.test` with `overwrite=True`, so tests
never use a developer's real Gmail or OAuth values even when the container has
them. The file holds throwaway values only and is committed. Its reader role is
`querylab_reader_test`, so bootstrapping for tests never changes the dev reader's
password or timeout. CI runs inside a container with service containers named
`postgres` and `redis`, so the same file works there.

The data DB is not a Django test database: tests run against the bootstrapped
`querylab` (as CI does: `bootstrap_data_db` before `pytest`). Tests that change
it (the Olist loader) work in a throwaway schema and drop it.

## allauth in headless mode

The React app talks to allauth's JSON API (`/_allauth/browser/v1/...`); Django
renders no auth pages (`HEADLESS_ONLY`). Email login only, verification mandatory,
Google and GitHub configured from `.env` (no SocialApp rows). Social logins link to
an existing account with the same verified email
(`SOCIALACCOUNT_EMAIL_AUTHENTICATION` + `AUTO_CONNECT`). Custom email-based `User`
model created before the first migration.

## Styled emails: Pro-Goal's renderer + css-inline (not premailer)

Every allauth email is written as plain text (`templates/account/email/*.txt`);
`AccountAdapter.render_mail` adds an HTML version built by
`common/email/render.py`: the first link becomes a button, and the layout's CSS
is moved inline. The plan named `premailer`; we use `css-inline` instead: one
Rust wheel with no dependencies, versus premailer's lxml + cssutils + requests
stack (~25 MB). The email palette is a placeholder until the design system is
approved.

## Huey, not Celery

Background jobs (eval runs, CSV imports, emails) use Huey on Redis: one small
package, thread workers, no separate beat process. Celery is far heavier than a
1/4 vCPU, 1 GiB container can afford. Tests run Huey in immediate mode
(`HUEY_IMMEDIATE`).

## Rate limits: allauth + ninja throttles, counted in Redis

allauth limits its own endpoints (`ACCOUNT_RATE_LIMITS`, every rate from `.env`).
Our endpoints use ninja throttles: `AnonThrottle` (signed out, by IP) and
`UserThrottle` (signed in, by user) on the whole API, `AskThrottle` per route for
LLM calls. They key on Django's session user rather than ninja's `request.auth`,
so a signed-in visitor on a public route is not counted as anonymous. Rates are
read from settings on every request. Both systems count in the Django cache
(Redis), so limits hold across processes. `TRUSTED_PROXY_COUNT` sets the real
client IP for both.

## One response envelope; `/api/health` is unwrapped

Every endpoint returns `{success, status_code, message, data, meta}`; every error
`{success: false, status_code, message, code, errors}` (from resolve-ai /
Pro-Goal). `/api/health` returns its fields directly so uptime checks can read
`status` without unwrapping.

## Reused `common` app (resolve-ai, Pro-Goal)

Copied as-is (constants moved to `.env`): logger, request id, timing, typed
exceptions, Fernet crypto, cache manager, model mixins, validators, email
renderer, LLM providers. Rewritten for ninja: exception handler, response
envelope, pagination, ordering, filters, throttles. Dropped: Sentry and Celery
hooks (no Sentry; Huey instead), embeddings and the "app's own key" LLM path
(bring-your-own-key only; embeddings return with step 8), DRF serializers,
storage, search, documents.

## Olist as the demo dataset

Source: [Olist Brazilian e-commerce dataset on Kaggle](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce),
licence **CC BY-NC-SA 4.0** (non-commercial, attribution, share-alike). About 100k
real orders from 2016 to 2018 with customers, items, payments, reviews, products
and sellers: realistic joins, dates and messy values. One shared, read-only copy
in `demo` that every signed-up user sees. The CSVs live in `infra/data/olist/`
(git-ignored, never committed).

Loaded by `load_demo`: COPY into a temp text table, then INSERT ... SELECT into
typed tables. Category names are translated to English (two categories have no
translation and keep their Portuguese name); every date moves forward by
`DEMO_DATE_SHIFT_DAYS` (2922, so the newest order lands on 2026-10-17), fixed so
eval answers stay reproducible. Fixes on the way: the source's `*_lenght` columns
are `*_length`; `geolocation` gets a surrogate key; `order_reviews` uses
`(review_id, order_id)` because a few reviews cover several orders.

## SQL for the data DB lives in `infra/sql`, applied by `bootstrap_data_db`

Numbered files, applied in order in one transaction, idempotent. Placeholders in
braces are filled with psycopg's `sql.Identifier` / `sql.Literal` (never string
formatting) from settings: role name and password from `DATA_READER_URL`, timeout
from `READER_STATEMENT_TIMEOUT_MS`. The folder path is `DATA_SQL_DIR`.

## Deployment target: Cloudflare Container, basic

1/4 vCPU, 1 GiB RAM, 4 GB disk; sleeps after ~10 idle minutes; disk wiped on restart.

- **Image:** multi-stage `Dockerfile` on `python:3.12-slim`; the build stage runs
  `uv sync --frozen --no-dev`, the final stage copies only the virtualenv and the
  code and runs as a non-root user. Budget: under 300 MB (checked in CI with
  `IMAGE_SIZE_BUDGET_MB`).
- **Web server:** gunicorn with threaded WSGI workers (`gthread`), with
  `WEB_CONCURRENCY` workers and `WEB_THREADS` threads. The plan said uvicorn
  workers; we chose gthread because the API is synchronous Django: under ASGI,
  sync views run through `sync_to_async(thread_sensitive=True)`, which serializes
  them on one thread, and we have no async code to gain from. It also drops the
  uvicorn dependency. Target idle memory for web + worker: under 500 MB.
- **Jobs:** `entrypoint.sh` starts `run_huey` beside gunicorn in the same
  container; a separate worker container would sleep without requests and stop
  consuming jobs. If either process exits, the container exits and restarts.
- **No local disk:** logs to stdout, uploads stream into Postgres (R2 later).
- **No heavy work in the container:** Spider runs, clustering and LoRA training run
  locally, in CI or on Colab and write results to the database.
- **Frontend is not in the container:** a static Vite build on Cloudflare (Workers
  static assets or Pages) on the same domain as the API, so session cookies work.
- **LLM SDKs:** `openai` and `google-genai` are runtime dependencies (the agent
  calls them from the web process). Both are pure Python over httpx.

## Image builds that survive a slow network

Docker Desktop's VM on the development machine downloads from PyPI very slowly,
and the first `make dev` timed out. The build now: installs no lint tools in
the dev image; builds the dev image once (`querylab-backend:dev`) and runs the
worker from the same image instead of building it twice in parallel; takes
`UV_HTTP_TIMEOUT` and `UV_CONCURRENT_DOWNLOADS` as required build args from the
root `.env` (the Dockerfile refuses to build without them); and keeps uv's cache
in a named BuildKit cache mount with `sharing=locked`, so a failed build resumes
from the wheels it already has and two builds never contend for the cache.
`network: host` on the build was considered but not added (it changes nothing on
Docker Desktop's VM and only matters on native Docker Engine).

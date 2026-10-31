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
renders no auth pages (`HEADLESS_ONLY`). Google and GitHub are configured from
`.env` (no SocialApp rows). Custom `User` model created before the first
migration.

## Sign-in with Google or GitHub only; one user per provider account (2026-10-30, owner's choice)

Email/password accounts were dropped (`SOCIALACCOUNT_ONLY`): no signup form,
password login, verification, reset or change-password endpoints (allauth does
not even mount them), and so no email at all. That also removed the Gmail SMTP
settings (every `EMAIL_*` key and `DEFAULT_FROM_EMAIL`), the styled email
templates and renderer, `css-inline`, `send_test_emails` and allauth's
`RATE_LIMIT_*` keys, which only covered the email/password endpoints.
`MAILERS` is empty on purpose, so an accidental send fails loudly.

Accounts are **not** merged: the same email through Google and through GitHub
creates two separate users. Identity is the provider account (provider + uid).
`SOCIALACCOUNT_EMAIL_AUTHENTICATION` is off, `ACCOUNT_UNIQUE_EMAIL` is false and
`User.email` is no longer unique (migration `0002_email_not_unique`; it stays
indexed). Email is still `USERNAME_FIELD` for display; with no password logins
nothing authenticates by it, so Django's `auth.W004` warning is silenced, as are
allauth's `account.W001` (no local login method) and Django's `mail.W001` (no
mailer). `/api/me` reports the user's provider in `providers`.

## Huey, not Celery

Background jobs (eval runs, CSV imports) use Huey on Redis: one small
package, thread workers, no separate beat process. Celery is far heavier than a
1/4 vCPU, 1 GiB container can afford. Tests run Huey in immediate mode
(`HUEY_IMMEDIATE`).

## Rate limits: ninja throttles, counted in Redis

Our endpoints use ninja throttles: `AnonThrottle` (signed out, by IP) and
`UserThrottle` (signed in, by user) on the whole API, `AskThrottle` per route for
LLM calls. They key on Django's session user rather than ninja's `request.auth`,
so a signed-in visitor on a public route is not counted as anonymous. Rates are
read from settings on every request. They count in the Django cache (Redis), so limits
hold across processes. `TRUSTED_PROXY_COUNT` sets the real client IP.

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
  `IMAGE_SIZE_BUDGET_MB`). Measured on 2026-10-30: 291 MB of files (83 MB
  compressed). The build drops every non-English translation the packages
  ship (about 20 MB; the app is English only) and keeps the compiled
  bytecode (about 40 MB) for faster cold starts after the container sleeps.
  CI measures the image's files with `du` inside it, because
  `docker image inspect` reports different sizes on different image stores.
- **Web server:** gunicorn with threaded WSGI workers (`gthread`), with
  `WEB_CONCURRENCY` workers and `WEB_THREADS` threads. The plan said uvicorn
  workers; we chose gthread because the API is synchronous Django: under ASGI,
  sync views run through `sync_to_async(thread_sensitive=True)`, which serializes
  them on one thread, and we have no async code to gain from. It also drops the
  uvicorn dependency. Target idle memory for web + worker: under 500 MB; measured about 300 MB
  (gunicorn master + 2 gthread workers + run_huey).
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

## Dev-only OAuth test page for Postman

**What:** `GET /dev/` (a plain HTML page) starts the normal allauth Google/GitHub
sign-in and then shows the `sessionid` in a textarea; `GET /dev/session` returns
it as JSON. Both exist only in `config/urls_local.py`, selected by
`settings/local.py`.

**Why:** OAuth finishes only in a browser and the session cookie is HttpOnly, so
Postman could not get a signed-in session without opening devtools. The page
uses the real browser flow, so what Postman tests is the real session auth. It
is gated by the URL conf (not by `DEBUG` or an env flag), so prod and test
cannot serve it, and it adds no setting.

**Cost:** the session key is shown in the page; fine on localhost, which is why
it must never be routed in prod (a test checks `config.urls` has no `/dev/`).
Using it needs `http://localhost:8000/accounts/<provider>/login/callback/` in the
Google and GitHub OAuth apps.

## Text-to-SQL core (step 1)

**Guard with sqlglot, backed by the reader role.** Model SQL is untrusted (wrong,
or steered by a prompt injection in the question). `ask/guard.py` parses it as
PostgreSQL with sqlglot and checks the syntax tree, never the text: one
statement, SELECT/WITH only, no write/DDL/COPY/SET/locking nodes anywhere
(including in CTEs), only known `demo` tables and columns (via sqlglot's
`qualify`), a function denylist from `.env` plus any `pg_*`/`lo_*` function, and
a forced `LIMIT`. The query that runs is regenerated from the checked tree, so
it is exactly what was checked. Alternatives: regex/keyword filters (easy to
bypass with comments, casing, quoting) and a hand-written parser (more code,
more bugs). The guard may be wrong in rare cases because the reader role
(read-only, SELECT on `demo`, statement timeout) is the actual wall, and the
guard's second job is giving the model a precise error to repair from. Cost:
sqlglot, pure Python, about 5 MB, no native code, so it fits the 1 GiB container.

**Three layers:** guard, reader role, resource caps (statement timeout, row and
byte caps, `AskThrottle`). Any one of them alone stops a write.

**What the model sees:** rules, the schema text (names, types, keys, `COMMENT ON`
text), a few example values for low-cardinality text columns, and the question.
On a repair, also the failed SQL and one trimmed error line. Never result rows.
Example values come from `pg_stats` (most common values Postgres already keeps,
refreshed by `ANALYZE` at the end of `load_demo`), not from scanning tables. They
are sent for the shared demo schema only; step 5 must turn them off, or make them
opt-in, for user uploads.

**Keys:** QueryLab provides a default Gemini key from `.env` (never in the
database), capped per user per day (`ASK_DEFAULT_KEY_DAILY_LIMIT`, counted in
Redis) so a shared key cannot be drained. A user may save their own OpenAI or
Gemini key; it is checked with the provider, stored encrypted with
`common.crypto`, never returned (only the last four characters), and takes
priority over the default and over its cap. The default key is Gemini only.

**Confidence score:** a weighted blend (weights in `.env`) of the model's own
rating, a guard that changed nothing, no repair retry and a non-empty result,
minus a penalty when truncated. A missing LIMIT does not count as a change. It
is a heuristic, not a calibrated probability: step 2's eval will compare it with
real execution accuracy.

**Synchronous ask.** The request waits for the LLM (a few seconds); gunicorn's
threads absorb it. No Huey job until step 3's agent loop needs one.

**AskLog:** one row per ask (question, final SQL, status, error code, attempts,
provider, model, key source, tokens, latency, confidence, row count), success or
failure, never the result rows. They are raw material for traces in steps 3 and
6. A failed log write is logged and never fails the ask. No retention policy yet;
decide before real users arrive.

**Repair retry:** at most `ASK_MAX_REPAIR_ATTEMPTS` (1). Timeouts are not
retried (the same query would time out again).


## Eval harness (step 2)

**Execution accuracy.** A question is correct when the model's SQL and the gold
SQL return the same rows on the same database. We store gold SQL, never gold
rows, and run both at eval time. Limits we accept: two different queries can
return the same rows by chance; an `ORDER BY ... LIMIT` with ties at the cut can
return different valid rows (Spider's official scorer has the same weakness; the
Olist gold SQL uses explicit tie-breaks); column names are ignored on purpose.
Comparison is an unordered multiset, ordered only when the gold SQL orders. Spider is the exception: its official scorer compares results as sets (duplicates ignored), so the Spider target does too, otherwise an `EXCEPT` answer fails against a duplicate-producing gold query (seen in baseline run #8).

**Two targets.** Olist (about 40 hand-written questions, 4 unanswerable) goes
through the real guard and reader role, so it measures the product. Spider (dev
set, 1,034 questions) runs on read-only SQLite for a number comparable with the
literature; the Postgres guard does not apply there, so the wall is the file
opened `mode=ro` plus `query_only`, a read-only authorizer, a time limit and a row
cap. Spider confidence has no guard signal (the guard is not run), so the
confidence-versus-accuracy table is only meaningful on Olist.

**Held-out split by database.** Spider dev is split once by database into `tune`
and `held-out` (committed). Prompt changes are judged on `tune`; the headline score
is `held-out`, so the number is not tuned to itself. The initial split was written
from the known dev database names and is checked by `check_spider` against the
unpacked data; rebuild it with `spider.build_split` if they differ.

**`answer()` split.** `generate_and_run` is the user-free core (prompt, LLM, parse,
check, execute, repair). `answer()` keeps the key, limit and `AskLog` handling. The
harness uses the same core so it measures the code path users hit. The prompt takes
a dialect (`postgres`, `sqlite`) and carries `PROMPT_VERSION`, stored on each run.

**No new runtime dependency.** Spider uses the standard `sqlite3`; scoring and
comparison are plain Python plus sqlglot (already present). The only additions to the
image are the `evals` app, two small tables and management commands. Evals run in
the dev container, one question at a time, and never in the production container.

**Rate limits.** `run_eval` pauses `EVAL_CALL_DELAY_SECONDS` between questions so a free-tier key stays under its requests-per-minute limit, and retries 429, 503 and timeouts with doubling backoff (`EVAL_RETRY_BACKOFF_SECONDS`, `EVAL_LLM_RETRIES`). No Claude provider: the baselines are Gemini and OpenAI only (owner's choice, 2026-10-31).

**Keys.** The Gemini baseline reuses `LLM_DEFAULT_GEMINI_API_KEY`; the OpenAI
baseline uses `EVAL_OPENAI_API_KEY`. Both live only in `.env`. `EVAL_MODEL_PRICES`
is an estimate for reports, not billing.

**Baseline results (recorded 2026-10-31, prompt `v1`, Gemini 3.5 flash-lite).**
- *Olist golden set* (run #7, 41 questions): **95.1%** (39/41), all 4 unanswerable questions declined. Misses: olist-26 (sorted by item count, not by score: a real error) and olist-18 (added `order_status = 'delivered'`, a defensible reading; wording to tighten later). An earlier run on `gemini-3.5-flash` (10 questions) scored 8/10 and is too small to compare.
- *Spider held-out* (run #9, stopped at 430 of 443 questions; 12 calls failed on provider 429s, so 418 were scored): **86.6%** (362/418; 84.2% if the failures count as wrong). A 20-question smoke run (#8) scored 90%. The 25 unscored questions were not re-run.
- *Reading the 50 misses by hand:* about 8 to 10 are real model errors (for example an AND of two directors written as IN, an area code taken from the phone number). The rest is Spider noise: gold SQL that answers a different question than the text (about 15), ties at `LIMIT 1` (about 9), inner versus left join (about 6) and an extra column in the model's answer (about 8). The headline number understates the model, and tuning the prompt against these would overfit.
- *Confidence:* it does not separate right from wrong. On Olist every answer got 1.0 (the model always reports full self-confidence and the other factors are almost always clean). On Spider held-out the buckets were 86.1% (0.70 to 0.85) and 88.0% (0.85 to 1.00), rank correlation 0.09. **Follow-up for steps 3 and 6:** do not show this score as a probability. Candidates: drop the self-rating, add agreement between two samples, or score by features that did vary (row count, result shape, repair attempts).
- *Not done:* a second model (the Claude and OpenAI baselines were dropped because paid API keys are billed separately), the Spider `tune` half, and the last 25 held-out questions.

## Agent (step 3)

**A run, not a request.** `POST /api/agent/runs` starts a run; the loop (`agent/loop.py`, plain Python, no agent framework) plans, calls typed tools, proposes SQL and pauses. A framework (LangGraph, an agent SDK) would add dependencies to an image near its 300 MB limit and hide the one thing we must control: where execution happens. The loop is about 400 lines and every rule in it is a test.

**Always pause; execution is not a tool.** The agent only gets `list_tables`, `describe_table`, `sample_values`, `propose_sql`, `finish` and `give_up`. `propose_sql` runs the guard and stores the checked SQL; it executes nothing. After the user approves (or edits), the loop itself calls `ask.runner.run` on the reader connection. So a prompt injection can at worst produce a wrong proposal that a person sees. The approval is not for safety (the guard, the reader role, the timeout and the row cap already stop writes and runaway reads): it catches wrong-but-valid SQL, such as a different reading of the question, and lets the user edit it. An edited SQL goes through the same guard, is kept in the trace (`actor=user`, `edited=true`) and is raw material for step 6's expected-SQL set. A per-user auto-run toggle can come with the frontend.

**State.** Postgres holds the durable trace (`AgentRun`, `AgentStep`, written first, then published as an event). Redis holds only working state (`agent:run:{id}`, TTL `AGENT_STATE_TTL_SECONDS`), the event stream and a per-run lock. A paused run holds no thread and no worker. If the Redis key is gone (TTL, flush, container restart) a paused run is rebuilt from its steps, so **a paused run survives a restart** (the container sleeping after ten idle minutes is the normal case). A run that was mid-turn when its worker died cannot be rebuilt: the periodic `expire_stale_runs` task fails it (`agent_worker_lost`, trace kept) after twice `AGENT_RUN_TIMEOUT_SECONDS`, and ends paused runs after `AGENT_APPROVAL_TTL_SECONDS` as `expired`. One lock per run (non-blocking) makes an approve click and a worker unable to race: a second approve is a typed 409, and a test runs two threads to prove the SQL runs once.

**Budgets.** Steps, LLM calls, tokens (input plus output), SQL revisions and active time all come from `.env`. Steps count every stored step (plan, tool, approval, execute, reflect), the closing `final` step is exempt so a failed trace is always closed. The wall-clock budget counts time the agent works, not the wait for the user. Hitting the revision cap fails the run (`agent_revisions_exceeded`) rather than quietly finishing with a result the reflect step disliked. A bad JSON reply is retried `AGENT_MAX_PARSE_RETRIES` times and each retry is an LLM call; a query timeout is never retried.

**One run is one spend of the default key**, however many LLM calls it makes; `AGENT_MAX_LLM_CALLS` bounds the real cost. The per-user cap on unfinished runs (`AGENT_MAX_CONCURRENT_RUNS_PER_USER`) is counted from Postgres under a row lock on the user, not in Redis as the plan first said: the database is authoritative, a crashed worker cannot leave a stale counter, and the same query expires stale paused runs first.

**SSE, not polling, and what it costs.** `GET /runs/{id}/events` streams stored steps (event id = step index, `Last-Event-ID` resumes), then waits on a Redis stream and sends a heartbeat comment. Each open stream holds one gunicorn thread, so streams are capped (`AGENT_MAX_OPEN_STREAMS`, counted in Redis with a self-healing key), each lives at most `AGENT_SSE_MAX_SECONDS`, and over the cap the client gets 429 `agent_stream_limit` and polls `GET /runs/{id}`. The stream **also closes when the run pauses for approval** (the plan said "terminal status" only): a person thinking for 10 minutes must not pin a thread. The client reopens it after it decides. The Redis stream is a nudge; the steps themselves are read from Postgres, so a trimmed or lost entry only delays a client by one read block. Checked on 2026-10-31: under gunicorn `gthread` (the production worker class) a generator response reaches the client chunk by chunk, one second apart, with `X-Accel-Buffering: no` and `Cache-Control: no-cache` set; worker timeout does not kill a long stream because gthread's heartbeat runs on the main thread. **Not checked:** Cloudflare's edge passing chunks through for this app; check it once on the deployed container (step 10).

**Compact schema start.** The first prompt carries table names, comments and row estimates only; the agent fetches columns with `describe_table` and filter spellings with `sample_values`. This saves tokens but costs steps. `AGENT_FULL_SCHEMA_START=true` switches to the full schema text of step 1 without a code change; whether the compact start costs accuracy is judged by the Olist run in 3.10.3 (owner), and if it does, the fallback becomes the default and is recorded here.

**Reflect.** A cheap rule check after execution (error, empty, truncated, one value) decides whether the model reads the result; a clean result goes straight to `finish` with no extra LLM call. `AGENT_REFLECT_ALWAYS=true` reviews every result (more accurate maybe, more calls): a knob for the 3.10.3 run. The reflect prompt names the three failure shapes seen in the step 2 baseline. The model sees a result *summary* only (columns, row count, first `AGENT_RESULT_PREVIEW_ROWS` rows), never the full table.

**What is stored.** Result rows are never stored. An `execute` step keeps the columns, row count, a truncated flag and the preview rows, trimmed to `AGENT_STEP_OUTPUT_MAX_CHARS`, so a replay shows what the user saw without running any SQL. Consequence for step 4: the stored trace has the preview, not the full table; the analyst API will need a way to show full rows (re-running the approved SQL on demand through the guard and reader is the cheap option).

**Not answerable.** `give_up` ends the run as `failed` with `error_code=not_answerable`; the reason is the final step's output. It replaces step 1's `answerable: false`.

**`PROMPT_VERSION`.** `/api/ask` keeps `v1`. The agent prompts carry their own `v2-agent` (`agent/prompts.py`), stored on every run and every agent eval run.

**Confidence, replaced.** The model's self-rating is gone from the score (it sat near 1.0 on every answer; rank correlation 0.09 on Spider). One function, `agent/confidence.py`, serves `/api/ask` and the agent: weights for guard-clean, no revision, non-empty, reflect-ok-first, sample-values-checked, a penalty for truncation; features that do not apply (`/api/ask` has no reflect step) drop out and the rest scale up. `/api/ask` now uses it too (its `confidence` and a new `check` field follow the same rule below). **Acceptance rule, fixed before the result is known:** on the Olist agent run, the accuracy of the top confidence bucket must beat the bottom bucket by `CONFIDENCE_MIN_SEPARATION`; only then is `CONFIDENCE_SHOW_SCORE` set to true and the API returns a number. Until then (and today: the analysis has not been run yet) `confidence` is `null` and every response carries a plain `check` label, `checked` or `needs_look`, from the guard report, row count, truncation and the reflect verdict. The raw score is still stored on each run so `confidence_report` can measure it. With 41 Olist questions and about two misses, the analysis is thin; the offline script says which features separate and the owner decides which to keep (3.9.3).

**Agent eval.** `run_eval --runner agent` (Olist only) starts a run per question, approves every pause as `actor=eval`, and scores the final SQL with the step 2 comparison. The approved SQL is executed once more by the harness to get rows for the comparison, since rows are not stored. The report adds steps, LLM calls, revisions and tokens per question. Spider stays on `--runner ask`: the agent loop uses the Postgres guard and reader, and running it on SQLite would mean abstracting the tools, guard and prompts by dialect, which this step does not need. So the plan's Spider-through-agent items (3.9.2 second half, 3.10.4) are not done.

**Image size.** No new runtime dependency (`pyproject.toml` and `uv.lock` are unchanged); the `agent` app adds about 4 MB with its bytecode. Measured 2026-10-31 with CI's method: **295 MB against the 300 MB budget** (291 MB after step 2). The headroom is now small; the next step that adds code should check it before anything else.

**Results.** *Pending (owner):* the Olist agent run (3.10.3) and the confidence analysis (3.9.2) need the live Gemini key and have not been run. Fill in here: run id, accuracy against the 95.1% baseline, extra cost per question (steps, LLM calls, tokens, latency), and the confidence verdict.

## Analyst API (step 4)

Backend only: the surface the analyst screen (step 9) needs, so the screen is only drawing. Plan: `docs/plan/04-analyst-api.md`.

**Image size, before any code.** Measured 2026-10-31 on the step 3 branch with CI's method (`du -sxm /` in the prod image): **295 MB against the 300 MB budget**, so 5 MB of headroom, above the plan's 3 MB stop line. Step 4 adds no dependency; it is a few small modules and one JSON file.

**Open questions, answered (the plan's recommendations).** (1) No auto-run toggle: every run pauses, as decided in step 3. (2) No run deletion: a delete would remove a human correction that step 6 wants as raw material; if it is ever needed, the cheap shape is a `hidden_at` flag. (3) Full rows come from re-running the stored SQL (see below), not from storing rows.

**Approval payload (4.4.1).** When the loop pauses (`agent/loop.py` `_pause`) it writes one `approval` step with actor `agent` whose `input` already holds everything the screen needs: `sql`, `rationale`, `assumptions`, `guard_rewrites` and `revision`. So `pending` is not new state: `agent.schemas.pending_dict` reads the newest agent `approval` step of a run that is `awaiting_approval`, and returns null otherwise. No migration, nothing extra to keep in sync, and a replay of a paused run shows the same block. `expires_at` is `updated_at` plus `AGENT_APPROVAL_TTL_SECONDS`, the same clock `service._expired` uses. `guard` is the guard's rewrite codes (`limit_clamped`, `qualified_tables`); a LIMIT the guard simply adds is not reported by the guard today. The SSE `status` event carries the same block, so the screen needs no extra request at the pause.

**Why an edit refusal names the reason (4.4.4).** The user typed that SQL, so the reason ("Only SELECT queries are allowed.", "The table x does not exist.") only names what they wrote. It goes in `errors: [{field: "sql", message}]` of the 400 `guard_rejected`. The same guard error on `/result` and `/ask` stays generic: there the SQL is not the user's. The run stays paused and no step is written.

**History (4.5).** `GET /runs` filters with a ninja `FilterSchema` (`status` repeatable and validated against the six statuses, `q` as `question__icontains`, `created_after` / `created_before`) and orders through the `common/order` allowlist (`created_at`, `latency_ms`; the id breaks ties so pages do not shuffle). `meta.count` is the filtered count. `has_result` is just `status == succeeded`. `edited` is an `Exists` over the run's approval steps, annotated on the list so a page costs one query, not one per row (the detail and create paths ask once). **No new index (4.5.3):** `(user, -created_at)` from step 3 already serves the default list, and a user has few runs (the per-user cap and the daily default-key limit bound them), so a status or text filter is a cheap filter over that user's rows. The `ILIKE` on `question` has no index either; add a trigram index only if history grows large.

**The error list (4.6.2, 4.6.3).** `backend/API_ERRORS.md` is the one list of error codes with their HTTP status, meaning and what the screen should do, in two tables: HTTP errors, and the codes a failed run carries. It lives in `backend/` (not `docs/`) because the dev container mounts only `backend/`, and `common/tests/test_error_list.py` must read it there. The test fails when an `AppException` subclass has no row, when a row names a code that no source file has any more, and when a failed-run `CODE_*` constant is not in the run table. Codes are found by scanning source for `error_code=` / `code =` / `*CODE* =` string assignments, which also catches codes raised ad hoc (`BadRequestException(..., error_code="key_invalid")`).

**Retry hint on every 429 (4.6.4).** The error envelope gains `retry_after_seconds` on 429s only. For the ninja throttles it is the wait ninja computes, rounded up (and the handler now sets `Retry-After` itself). `default_key_limit` waits until midnight UTC, the moment the daily count restarts. `agent_run_limit` and `agent_stream_limit` are not about time, so they say `null` and the list tells the screen what to do instead. `common/tests/test_retry_after.py` finds every throttle class by subclass walk and fails if one has no case, so a new throttle cannot skip the hint.

**OpenAPI contract (4.7).** `backend/openapi.json` is written by `make openapi` (`manage.py export_openapi`: our own small command, because ninja's built-in `export_openapi_schema` needs `ninja` in `INSTALLED_APPS` and cannot sort mixed keys). Output is sorted and indented, so a changed endpoint is a small diff. CI regenerates it to a temp file and `diff`s (the job image has no git); `core/tests/test_openapi.py` does the same check locally, and also asserts every response uses a named model, every error response is `ErrorEnvelope`, every route declares 401 and 429 (the default throttles apply everywhere), and operation ids are unique. Operation ids are the view function names (`list_runs`, `get_schema`) so a generated client reads well. Error statuses are declared per route with `errors(...)` from `common/response/domain.py`. Known rough edge: generic envelopes get names like `SuccessEnvelope_list_RunOut__`; they are named, just not pretty.

**CORS with credentials (4.7.6).** `CORS_ALLOW_CREDENTIALS = True` was missing, so a credentialed cross-origin `fetch` or `EventSource` would have failed in a browser even for the listed origin. It is now on; `django-cors-headers` only answers for `CORS_ALLOWED_ORIGINS`, and `core/tests/test_cors.py` checks that a listed origin gets the credentials header (also on a preflight that asks for `X-CSRFToken`) and that an unlisted origin, `null` included, gets no CORS header at all. **Still to do (4.7.5, owner):** the real-browser check against the dev servers (see FLOW.md, "Browser path check").

**Why rows are re-run and not stored (4.3).** Step 3 decided that result rows never go in the database: they are the user's data, can be large, and would turn the trace table into a copy of the demo data. So the result view runs the stored SQL again. Cost: one more query per view, bounded by the same row cap, byte cap and statement timeout, plus the `ResultThrottle`. Risk: the data may have changed since the run, so the table can differ from what the agent summarised; the demo data is static, so this is accepted and documented in the endpoint. The SQL is re-guarded on every fetch because the guard or the schema may have changed, and the endpoint takes no SQL from the request, so it cannot become a way to run arbitrary queries.

**Why the screen uses runs and not `/ask`.** Every screen action maps to a run: a pause the user can approve or edit, a trace to replay, history to filter. `/ask` has none of these and stays as the one-shot endpoint for scripts and the step 2 evals. Two paths into the screen would mean two shapes of "an answer" to render.

**Schema ETag (4.2.4).** The plan said to build the tag from the cache key and its refresh time. The cached `Schema` object carries no refresh time, and adding one would change what step 1 caches. The tag is instead a hash of the response body, which changes exactly when the schema, or the samples setting, does. It costs a hash of a small JSON document per request; the database is not touched either way (the schema is cached).

**Pending items (owner).** 4.7.5 (the real-browser CORS, CSRF and SSE check) is not run: it needs the OAuth login. The steps are in FLOW.md, "Browser path check".

**Image size, after step 4 (4.8.5).** Measured 2026-10-31 with CI's method: **295 MB against the 300 MB budget**, the same as before step 4 (the new modules and `openapi.json` are under 1 MB together; no dependency was added, `pyproject.toml` and `uv.lock` are unchanged). Headroom stays at about 5 MB.



## User workspaces (step 5)

**Image size, before any code (5.1.1).** Measured 2026-10-31 on the step 5 branch with CI's method (`du -sxm /` in the prod image): **295 MB against the 300 MB budget**, 5 MB of headroom, above the plan's 3 MB stop line. Step 5 adds no dependency.

**Two login roles per workspace, no `SET ROLE` (5.2.4, 5.2.4a).** `ws_<id>_rw` owns the schema (the user's SQL, imports, row and table APIs, primary only) and `ws_<id>_ro` has `SELECT` on it (the agent, replica in production). The earlier idea of `SET LOCAL ROLE` on one pooled connection is dropped: user SQL can run `RESET ROLE`, and PgBouncer in transaction mode makes session state unsafe. The login identity is the boundary. Roles are `NOINHERIT`, members of nothing, with a connection limit, a statement timeout, an idle-in-transaction timeout, a one-schema `search_path`, no `TEMP` and no database `CREATE`. Passwords are `HMAC-SHA256(MASTER_WORKSPACE_SECRET, id, kind, credential_version)`: nothing is stored, and bumping `credential_version` plus re-provisioning rotates them. The schema and role names are properties of the `Workspace` id, not stored columns (the plan listed `schema_name` and `role_name` as fields): one source of truth, and nothing a request could ever set.

**Connect per request (5.2.4a).** No pool of our own. Locally, 20 sequential connect-and-`SELECT 1` runs as a workspace role average **11 ms** on the Docker Postgres. The Neon number (pooled PgBouncer endpoint) is not measured yet: **owner task 5.9.7**. Add a cache only if that number is bad.

**Capacity (5.2.4b).** Local Postgres `max_connections` = 100. Worst case from our own limits is `(WORKSPACE_RW_CONNECTION_LIMIT + WORKSPACE_RO_CONNECTION_LIMIT)` per workspace (4 + 4 = 8 by default), so 3 workspaces of one user hold at most 24 connections, and `test_connections.py` proves the role limits hold (the 5th connection of a role is refused) and that a burst across three workspaces stays under the ceiling. **To verify on Neon (owner):** `SHOW max_connections` on the primary and on the replica at the compute size you will run, then keep `users x workspaces x (rw + ro limits)` of concurrent traffic below it; through the pooled endpoint the server-side count is what matters, not the client-side one.

**Things only a real Neon project can confirm (flagged to the owner).** (a) A non-superuser owner (`neondb_owner`) can `CREATE ROLE`, `ALTER ROLE ... SET`, `DROP OWNED BY` and `DROP ROLE` for roles it created: provisioning grants itself membership with `WITH INHERIT TRUE, SET TRUE` when it is not a superuser (PostgreSQL 16 syntax), and `test_neon_like_owner.py` rehearses this locally with a `CREATEROLE` role that is not a superuser. (b) `pg_terminate_backend` of a workspace role's sessions as that owner (needs `pg_signal_backend` or a superuser; the drop still works without it if no session is open, and the delete path retries). (c) Any limit on the number of roles per project. (d) `REVOKE CONNECT ... FROM PUBLIC` on the database being allowed for the project owner.

**What a workspace role can still see in the catalogs (5.3.2).** Every Postgres role can read `pg_catalog`, and Neon does not let the project owner revoke that. Measured as `ws_A_rw` and `ws_A_ro` (`test_catalog_visibility.py` pins it): other workspaces' **schema names (`ws_<id>`), role names, table names, column names and table / column descriptions (`COMMENT ON`) are readable**; **rows, statistics (`pg_stats`, `pg_statistic`), other sessions' queries, and password hashes are not**, and `information_schema` shows only what the role may use (nothing of another workspace). Accepted because ids are small integers anyway and names alone reveal no data, **with one caveat the owner should decide on: a description is user-written text, and today another signed-in user who enumerates `pg_namespace` could read it with raw SQL in their own SQL console.** Mitigation if that is not acceptable: keep descriptions in an app table instead of `COMMENT ON` (the schema reader would merge them), or revoke `SELECT ON pg_description` from PUBLIC on a database where that is allowed (it is locally, probably not on Neon). Not done; flagged.

**A session can raise its own `statement_timeout` (5.3.1).** Role-level `statement_timeout` is a default: the user's SQL can `SET statement_timeout = 0` (`test_isolation.py` documents it). The agent role cannot do this because the guard refuses `SET`. For the user's own SQL console and for imports the deadline is therefore also enforced from outside (the application cancels the running statement), see 5.6a.

**The SQL console is the user's own, and the role is its wall (5.6a).** `POST /api/workspaces/{id}/sql` runs a script as `ws_<id>_rw` with no guard. The statements are split by a small lexer (`workspaces/sqltext.py`: quotes, dollar quotes and comments only; it is not a security check) and run one by one in **one transaction per request**, so any failure rolls back everything. `BEGIN`, `COMMIT`, `ROLLBACK`, `SAVEPOINT` and `COPY` are refused: a user could otherwise split or leave the transaction, and `COPY ... STDIN` would hang the request. Structural statements are written to `workspace_ddl_log`; data statements are only counted in the response. **A caveat that cannot be fixed in Postgres:** `statement_timeout` is a user-level setting, so a script can `SET statement_timeout = 0`. A watchdog timer therefore cancels the running statement when the request's total time (`WORKSPACE_STATEMENT_TIMEOUT_MS`) is over; this is tested with exactly that script. Behind PgBouncer a cancel request needs the pooler to forward it, **to verify on Neon (owner)**.

**Quota checks after the write, and a full workspace can delete its way out (5.6a.2).** Size is measured inside the writer's transaction after the statements ran and the request rolls back with `workspace_full` / `user_storage_full` when it grew past a cap. A request that did not grow the workspace always passes, because `DELETE` does not shrink `pg_total_relation_size` until vacuum, and a full workspace must still be able to free space (`DROP TABLE` and `TRUNCATE` do shrink it). Known cost: a rolled-back oversize insert leaves dead space until autovacuum, so the measured size stays high for a while; `statement_timeout` bounds how much one request can write, and Neon storage (not the container disk) holds it. **Idle cleanup and the Neon storage ceiling are out of scope (5.8.4)**: `USER_MAX_BYTES` times the expected number of users must stay under the project's storage limit.

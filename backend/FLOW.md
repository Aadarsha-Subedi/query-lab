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
                             routers: core (/health), accounts (/me), ask (/ask, /llm-keys),
                             agent (/agent/runs...)
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

## Ask: question to SQL to result (step 1)

`POST /api/ask {question}` (signed in; `AskThrottle`; synchronous):

```
question
  -> validate (length, control chars, our own tags removed)           ask/prompt.py
  -> resolve LLM key: user's own (OpenAI/Gemini) else the default     ask/keys.py
       Gemini key; default key counts against a per-user daily cap
  -> schema text (tables, columns, keys, COMMENT ON text, sample      ask/schema.py
       values for low-cardinality columns), cached in Redis
  -> prompt (rules + schema + <question>) -> LLM -> JSON reply        common/llm
       {sql, rationale, self_confidence (read, no longer scored)}
  -> GUARD (sqlglot, Postgres dialect)                                ask/guard.py
       one statement, SELECT/WITH only, known demo tables/columns,
       no denied functions, LIMIT forced; returns the SQL to run
  -> RUN on data_reader: read-only transaction, statement timeout,    ask/runner.py
       row and byte caps, JSON-safe values
  -> confidence score + check label, AskLog row, response             agent/confidence.py
       (score is null until CONFIDENCE_SHOW_SCORE; the label is always there)
```

If the model says the question cannot be answered (`answerable: false`, e.g. a request to delete data or something outside the schema), nothing runs and the API
returns 422 `not_answerable` with the model's one-line explanation.

Repair loop: if the guard rejects the SQL or Postgres errors, the failed SQL and
the first line of the error go back to the model once (`ASK_MAX_REPAIR_ATTEMPTS`).
A timeout is not retried.

Trust boundary: everything the model returns is untrusted. Three layers, any one
of which stops a write: the guard (parsed tree, not text), the reader role
(SELECT on `demo` only, read-only, `statement_timeout`), and the resource caps.

```
 user ──question──> Django ──schema+question──> LLM provider (Gemini / OpenAI)
                      ^                              │
                      │                        SQL (untrusted)
                      │                              v
                  rows + sql <── data_reader <── sqlglot guard
                  (rows never go back to the LLM)
```

What the model sees: rules, schema text, the question (and on a repair, the bad
SQL plus one error line). Never result rows or other users' data.

Errors: 400 `question_invalid` / `guard_rejected`, 422 `query_failed` / `not_answerable`, 429
`throttled` / `default_key_limit`, 502 `llm_*`, 504 `query_timeout`. A signed-out
POST without a CSRF token gets 403 from Django's CSRF check before the 401.

## Evals: question set to accuracy (step 2)

Run on a dev machine only: `make eval ARGS="run_eval --target olist|spider --model <name>"`.

```
question set (olist_golden.jsonl | Spider dev.json + spider_split.json)
  -> for each question, one at a time:
       schema text (Postgres demo | SQLite file)      target.schema_text
       -> ask.service.generate_and_run                 the same core path as /api/ask
            prompt -> LLM -> parse -> check -> execute, with the repair loop
            (Olist: sqlglot guard + reader connection; Spider: read-only SQLite)
       -> run the gold SQL on the same database        target.gold_rows
       -> compare rows                                 evals/compare.py
       -> EvalResult row (SQL, outcome, reason, confidence, tokens, latency)
  -> EvalRun totals -> scoring: accuracy, outcomes, latency, cost, confidence buckets
```

Comparison: values are normalised (numbers rounded to `EVAL_ROW_COMPARE_PRECISION`,
dates as ISO text, booleans kept apart from numbers); column names are ignored and
columns may be reordered when their values line up; rows are an unordered multiset
unless the gold SQL has a top-level `ORDER BY`. Outcomes: `correct`, `wrong`,
`error`, `timeout`, `guard_rejected`, `not_answerable` (declined an answerable
question), `llm_failed`. Declining an unanswerable question is `correct`.

Spider is split once by database into `tune` and `held-out`
(`evals/targets/spider_split.json`); report the `held-out` number. `check_spider`
verifies the unpacked data against the split. `review_golden` shows each Olist gold
query with its rows; only reviewed questions run unless `--include-unreviewed`.

## Agent: a run with an approval checkpoint (step 3)

`POST /api/agent/runs {question}` (signed in; `AgentThrottle`). The API validates the
question, checks the per-user cap, resolves the key (one default-key spend per run),
stores an `AgentRun` and enqueues `start_run`. Huey runs `loop.advance(run_id)`:

```
advance(run)                       takes the run's Redis lock (non-blocking), loads state
  PLAN     LLM -> {plan, assumptions}                      step: plan
  ACT      LLM -> one tool call {"tool", "input"}          step: tool (ok or error)
             list_tables / describe_table / sample_values   read the cached schema (no DB hit)
             propose_sql  -> guard.check -> stores checked SQL
             finish / give_up                               end of the run on the agent's side
           unknown tool, bad input, guard refusal = ToolError, shown to the model, counted
  PAUSE    after propose_sql: step approval (sql, assumptions, guard report);
           status awaiting_approval; state saved to Redis; advance() RETURNS
           (no thread, no worker waits)                                  <- the checkpoint
--- user: POST /runs/{id}/approve | /edit {sql} | /cancel -------------------------
  DECIDE   service.decide (lock): edit -> guard.check again (refusal = 400, run stays
           paused); step approval (actor user); status running; enqueue resume_run
  EXECUTE  loop only: runner.run(sql) on the reader connection        step: execute
           (summary stored: columns, row count, preview rows; never the full table)
  CHECK    rules: error / empty / truncated / 1x1 (or AGENT_REFLECT_ALWAYS) -> REFLECT
           otherwise straight to finish
  REFLECT  LLM -> {verdict ok|revise, reason, revised_sql}         step: reflect
           revise -> propose_sql again -> PAUSE again (up to AGENT_MAX_REVISIONS)
  FINISH   confidence score + check label, status succeeded        step: final
```

Budgets (steps, LLM calls, tokens, revisions, active time) are checked before every
call; any overrun, an LLM error or a query timeout ends the run as `failed` with a
typed `error_code` and a closed trace. Expiry: a paused run past
`AGENT_APPROVAL_TTL_SECONDS` becomes `expired` (on a late click and by the periodic
`expire_stale_runs` task); a running run whose worker died is failed as
`agent_worker_lost`. If Redis lost a paused run's state, `decide` rebuilds it from the
stored steps.

```
POST /runs        -> run (running / awaiting_approval)       GET /runs, GET /runs/{id}
POST /runs/{id}/approve | edit | cancel   409 unless awaiting_approval (typed codes)
GET  /runs/{id}/replay   stored steps in order; no LLM, no query on demo
GET  /runs/{id}/events   SSE
```

SSE flow:

```
client ──GET /events (Last-Event-ID: n)──> view checks owner, takes a stream slot
                                           (AGENT_MAX_OPEN_STREAMS, else 429 agent_stream_limit)
  loop:  read run status, then steps with index > n from Postgres -> `event: step`, `id: index`
         status not `running` (paused or terminal) -> `event: status`, close
         else block on Redis stream agent:events:{id} (AGENT_SSE_READ_BLOCK_MS),
         heartbeat comment every AGENT_SSE_HEARTBEAT_SECONDS,
         close with `event: timeout` after AGENT_SSE_MAX_SECONDS
worker: every step is written to Postgres FIRST, then XADDed (the stream is only a nudge)
client reconnects after approve/edit with the last id it saw
```

Errors added: 400 `guard_rejected` (edit), 404 `run_not_found` (also for another
user's run), 409 `run_not_awaiting_approval` / `run_expired` / `run_busy`, 429
`agent_run_limit` / `agent_stream_limit` / `throttled` / `default_key_limit`. Failed
runs carry `error_code`: `agent_steps_exceeded`, `agent_llm_calls_exceeded`,
`agent_tokens_exceeded`, `agent_revisions_exceeded`, `agent_timeout`,
`agent_worker_lost`, `llm_key_changed`, `not_answerable`, `query_failed`,
`query_timeout`, `llm_*`, `agent_internal_error`.

What the agent's model sees: the question, the tool list, the plan, a trimmed history of
tool results (schema text, sample values, error lines) and a result *summary* at reflect
time. Never other users' data, and never more than `AGENT_RESULT_PREVIEW_ROWS` rows.

## Agent evals (step 3)

`make eval ARGS="run_eval --target olist --runner agent --model <name> --yes"`: for each
Olist question the harness creates an `AgentRun` (owner: an `evals@querylab.invalid` user),
advances it, approves each pause as `actor=eval`, then scores the final SQL like step 2
(it re-executes the approved SQL to get rows to compare). `EvalResult` links the run and
records steps, LLM calls and revisions. `confidence_report --run <id>` lists which
confidence features separate right from wrong and applies the acceptance rule.

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

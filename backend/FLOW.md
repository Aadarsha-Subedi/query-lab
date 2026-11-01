# Backend: FLOW.md

## The analyst screen's contract (step 4)

Everything the analyst screen (step 9) calls, all under `/api` and signed in unless
noted. Rows marked _new_ are step 4; the rest exist. Since step 5, `schema`, `ask`,
`agent/runs` and `agent/limits` take an optional `workspace` (see "Workspaces").

| The screen needs                               | Endpoint                                                                                                                                                                                                                                                                                                 | State                                        |
| ---------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------- |
| Who am I, CSRF cookie                          | `GET /me` (401 when signed out)                                                                                                                                                                                                                                                                          | exists                                       |
| Sign in / out                                  | `/_allauth/browser/v1/...`                                                                                                                                                                                                                                                                               | exists                                       |
| Schema panel (tables, columns, keys, comments) | `GET /schema`, `GET /schema/tables/{name}`                                                                                                                                                                                                                                                               | new (4.2)                                    |
| Does the user have their own key               | `GET /llm-keys` (provider, last4, model, is_active, updated_at), `PUT/DELETE /llm-keys/{provider}`, `PUT /llm-keys/{provider}/model`, `PUT /llm-keys/{provider}/activate`, `GET /llm-keys-models`, `GET/PUT /llm-settings` (source: querylab or own; querylab_model: the Gemini model on QueryLab's key) | exists                                       |
| What is left before a limit                    | `GET /agent/limits`                                                                                                                                                                                                                                                                                      | new (4.6)                                    |
| Ask a question                                 | `POST /agent/runs {question}`                                                                                                                                                                                                                                                                            | exists                                       |
| Live progress                                  | `GET /agent/runs/{id}/events` (SSE)                                                                                                                                                                                                                                                                      | exists; `status` event gains `pending` (4.4) |
| Render the approval card without parsing steps | `pending` on `GET /agent/runs/{id}`                                                                                                                                                                                                                                                                      | new (4.4)                                    |
| Approve / edit SQL / cancel                    | `POST /agent/runs/{id}/approve \| edit \| cancel`                                                                                                                                                                                                                                                        | exists; a guard refusal now says why (4.4)   |
| Full result table of a finished run            | `GET /agent/runs/{id}/result`                                                                                                                                                                                                                                                                            | new (4.3)                                    |
| History, filtered and ordered                  | `GET /agent/runs?status=&q=&created_after=&created_before=&ordering=`                                                                                                                                                                                                                                    | extended (4.5)                               |
| Replay a run                                   | `GET /agent/runs/{id}/replay`                                                                                                                                                                                                                                                                            | exists                                       |
| What every error code means, and what to do    | `backend/API_ERRORS.md`                                                                                                                                                                                                                                                                                  | new (4.6)                                    |
| Generated client types                         | `backend/openapi.json` (`make openapi`)                                                                                                                                                                                                                                                                  | new (4.7)                                    |

Not in this step: an auto-run toggle, deleting runs, CSV export. Workspaces came in step 5 (below).

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
                             schema (/schema...), agent (/agent/runs..., /agent/limits)
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

`GET /api/me` returns the user (with `providers`: `google` or `github`, and `is_staff`, which the screens use to show the workbench) or 401;
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

## Trace-driven evals: what a `traces` target provides (step 6)

`evals/runner.py` (`ask` runner) and `evals/agent_runner.py` (`agent` runner) both take a
`Target` (`evals/targets/base.py`) and a list of `EvalQuestion`, and both end in
`runner._judge`, which calls `compare.compare` on gold rows and predicted rows. The
`OlistTarget` loads questions from `olist_golden.jsonl`; a `TraceTarget` loads them from
approved `TraceCase` rows instead, and nothing else about the harness changes.

| Member                      | What `OlistTarget` does                           | What `TraceTarget` must do                                                                    |
| --------------------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------- |
| `name`                      | `"olist"` (stored on `EvalRun.target`)            | `"traces"`                                                                                    |
| `dialect`, `compare_as_set` | Postgres, `False`                                 | the same                                                                                      |
| `questions(split)`          | the reviewed golden items; only `all`             | the `TraceCase` rows with `status=approved`; only `all`; `tags` = cluster key; `id` = case id |
| `schema_text(q)`            | `schema.render(get_schema(include_samples=True))` | the same demo schema text                                                                     |
| `check(q)`                  | `guard.check(sql, schema)`                        | the same                                                                                      |
| `execute(q)`                | `runner.run` on the reader, native values         | the same                                                                                      |
| `gold_rows(q)`              | runs `gold_sql` on the reader                     | runs the approved `gold_sql` on the reader                                                    |
| unanswerable                | `answerable=False`: declining is correct          | a case marked unanswerable: declining is correct                                              |

The model never sees `gold_sql` or gold rows. `run_eval --target traces` serves only
`approved` cases.

## The workbench contract (step 6, for the step 9 screens)

All routes are under `/api/workbench/`, answer in the envelope, and need a signed-in
staff user (401 signed out, 403 `staff_only` otherwise).

```
runs (AgentRun, demo only)            cases (TraceCase)                eval results
GET /runs        list + filters        GET  /cases       list, filter      GET /eval/runs
GET /runs/{id}   steps, proposed vs    GET  /cases/{id}  + rows preview    GET /eval/runs/{id}  + by_cluster
                 approved SQL, diff    POST /cases/draft queue a batch     GET /eval/compare?base=&other=
GET /clusters    label, size,          POST /cases/{id}/approve | reject | mark-unanswerable
                 representative, counts per status
```

The review loop, end to end:

```
people use the agent (demo)           run.feedback 👍/👎 (PUT /api/agent/runs/{id}/feedback)
  -> make eval ARGS="build_trace_cases"   rules: edited SQL, 👎, failed, revised, declined, needs_look
       (one TraceCase per run, reasons recorded; user workspaces and eval-harness runs skipped)
  -> clustering: key = outcome + tables + SQL shape, merged when questions overlap
  -> POST /cases/draft  (or draft_trace_cases): ONE LLM call per cluster representative,
       guard + run on the reader; failure stored in draft_error
  -> GET /cases/{id}: staff sees the draft, a rows preview (run now, never stored) and the trace link
  -> approve (optionally edit question/sql; guarded + run again) | reject | mark-unanswerable
  -> make eval ARGS="run_eval --target traces --model M [--runner agent] [--gate]"
  -> GET /eval/runs, /eval/runs/{id} (by_cluster), /eval/compare (flips)
```

Case status: `candidate` (picked) -> `drafted` (a draft or its error waits; a failed draft
needs an edited `sql` to approve) -> `approved` (gold; only these are scored) | `rejected`.
Errors the screens branch on: `staff_only`, `case_not_found`, `case_not_reviewable` (409),
`draft_unusable` (422), `eval_run_not_found`, `eval_runs_not_comparable` (422),
`run_not_finished` (409, feedback), plus `guard_rejected` with `errors[0].field = "sql"`.

Postman, folder "9. Workbench (staff only)": run _List traces_ and _List cases_ first
(they save `traceRunId` / `traceCaseId`), then _Get a case with a rows preview_,
_Approve a case_. Sign in as a staff user (`createsuperuser`, or `is_staff` in the admin).

## The regression gate (step 6)

```
run_eval --target olist|traces --model M --gate [--baseline ID]
  -> score the questions as usual                      (run #N)
  -> baseline = --baseline, else the latest done run of the same
     target, split, runner and prompt version          (run #B)
  -> evals/gate.py compares #N with #B on the cases both have
       fail: accuracy dropped by more than EVAL_GATE_MAX_DROP_POINTS points
       fail: fewer than EVAL_GATE_MIN_CASES shared cases (too small to trust)
  -> prints GATE PASSED/FAILED, the flipped cases and the clusters that dropped
  -> exit status 0 (passed) or 1 (failed, no baseline, other target)
```

`make eval-gate MODEL=<name> RUNNER=ask|agent` runs it for the Olist golden set and then
the trace set. It needs the live key, which exists only in the dev environment, so CI does
not run it: CI runs the gate logic (`evals/tests/test_gate.py`) with a scripted model. A
first run has no baseline and fails the gate; run once without `--gate`, or pass
`--baseline`. The read-only views of the same numbers are `GET /api/workbench/eval/runs`,
`/eval/runs/{id}` and `/eval/compare`.

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
tool results (schema text, sample values, error lines) and a result _summary_ at reflect
time. Never other users' data, and never more than `AGENT_RESULT_PREVIEW_ROWS` rows.

## Analyst API: the screen's calls (step 4)

```
Schema panel   GET /schema            ETag + If-None-Match -> 304; tables, columns, keys, comments,
                                      row estimates; samples only if SCHEMA_API_INCLUDE_SAMPLES
               GET /schema/tables/{name}   404 table_not_found for an unknown name
Limits         GET /agent/limits      default key used/allowed/remaining/resets_at, has_own_key,
                                      unfinished runs vs cap, open streams vs cap (read only)
History        GET /agent/runs?status=&q=&created_after=&created_before=&ordering=&limit=&offset=
                                      rows carry has_result and edited; meta.count = matches
```

**The approval payload.** While a run is `awaiting_approval`, `GET /agent/runs/{id}` (and
replay) has a `pending` block, and the SSE `status` event that announces the pause carries
the same block; it is null in every other state:

```
pending: {sql, rationale, assumptions: [str], guard: [str], revision, expires_at}
```

It is read from the newest agent `approval` step, so there is nothing extra to store. `guard`
holds the guard's rewrite codes (`limit_clamped`, `qualified_tables`). Edit with SQL the guard
refuses answers 400 `guard_rejected` with `errors: [{field: "sql", message}]` and the run stays paused.

**The result fetch.**

```
GET /agent/runs/{id}/result     owner only; ResultThrottle
  run is not succeeded                      -> 409 run_not_succeeded
  guard.check(run.final_sql) again          -> 400 guard_rejected if it would be refused now
  runner.run(checked sql) on the reader     -> {run_id, sql, columns, rows, row_count, truncated}
                                               rows capped by ASK_MAX_ROWS / ASK_MAX_RESULT_BYTES
  query error / timeout                     -> 422 query_failed / 504 query_timeout (run untouched)
```

Rows are not stored (step 3), so this runs the SQL again; the numbers can differ from the first
run if the data changed. The request carries no SQL.

**Contract file and errors.** `backend/openapi.json` (`make openapi`) is what the frontend
generates its types from; CI fails when it is stale. Error codes and what the screen does about
each are in `backend/API_ERRORS.md`. Every 429 has `retry_after_seconds` (null when waiting does
not help: `agent_run_limit`, `agent_stream_limit`).

**A whole screen session**, in calls: `GET /me` (sets the CSRF cookie) -> `GET /schema` ->
`POST /agent/runs` -> open `GET /agent/runs/{id}/events` (SSE) -> the `status` event shows
`pending` -> `POST .../approve` or `.../edit {sql}` -> reopen the stream with `Last-Event-ID`
-> `GET .../result` -> `GET /agent/runs?...` for history -> `GET .../replay` to review.

## Browser path check (pending, owner task 4.7.5)

Credentialed CORS (`CORS_ALLOW_CREDENTIALS`, listed origins only) is tested with the test
client, but a real browser needs the OAuth login, so check it once with both dev servers up,
from a page on the frontend origin (`http://localhost:3000`) calling the API origin
(`http://localhost:8000`): (1) `fetch(url + "/api/me", {credentials: "include"})` returns 200 and
sets `csrftoken`; (2) `fetch(url + "/api/agent/runs", {method: "POST", credentials: "include",
headers: {"X-CSRFToken": <cookie>, "Content-Type": "application/json"}, body: ...})` returns 200;
(3) `new EventSource(url + "/api/agent/runs/<id>/events", {withCredentials: true})` receives
events. Note any `.env` change it needs (`CORS_ALLOWED_ORIGINS`, `CSRF_TRUSTED_ORIGINS`, cookie
`SameSite`) and record it in DECISION.md. Result: _not run yet._

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

## Step 5: every place that hard-coded `demo` (5.1.3), and what became of it

Read before step 5 changed anything. Each row was a change in task 5.4 (or the task
named); all are done and tested.

| Where                                                        | What is hard-coded                                                                                                               | Change                                                                                         |
| ------------------------------------------------------------ | -------------------------------------------------------------------------------------------------------------------------------- | ---------------------------------------------------------------------------------------------- |
| `core/datadb.DEMO_SCHEMA`                                    | the constant, the default for the three below                                                                                    | stays; `workspaces.context.DEMO` wraps it (5.2.1)                                              |
| `ask/schema.read_schema`                                     | schema name defaults to `demo`; always connects with the `data_reader` alias                                                     | takes a workspace; connects as that workspace's reader (5.4.1, 5.4.3)                          |
| `ask/schema.get_schema` / `cache_key` / `clear_schema_cache` | default `demo`; key `ask:schema:<schema>:<samples>` has no version                                                               | key holds workspace id and a Redis schema version (5.4.1, 5.4.2)                               |
| `ask/runner.run`                                             | always the `data_reader` alias and `READER_STATEMENT_TIMEOUT_MS`                                                                 | takes a workspace; user workspaces open `ws_<id>_ro` per request (5.4.3)                       |
| `ask/guard._check_tables`                                    | the schema comes from the `Schema` object, so any other qualifier is already refused; `SET`/`RESET` already in `FORBIDDEN_NODES` | add refusals for `pg_catalog` / `information_schema`, test quoted spellings (5.4.4)            |
| `ask/service._answer`                                        | `schema.get_schema(include_samples=True)`, `execute=runner.run`                                                                  | take the workspace (5.4.6)                                                                     |
| `ask/prompt.py` (`DIALECT_POSTGRES` naming text)             | example `demo.orders`                                                                                                            | uses the active schema name (5.4.6)                                                            |
| `ask/schema_api._current` and both handlers                  | `get_schema(include_samples=...)` for the demo                                                                                   | `workspace` query parameter, one ownership dependency (5.4.6)                                  |
| `agent/prompts.py` (rules text)                              | `schema "demo"`, `demo.orders`                                                                                                   | schema name filled in per run (5.4.6)                                                          |
| `agent/loop._connect`                                        | `schema.get_schema(include_samples=True)`                                                                                        | schema of `run.workspace_id` (5.4.7)                                                           |
| `agent/loop._execute`                                        | `runner.run(sql)`                                                                                                                | `runner.run(sql, workspace)` (5.4.3)                                                           |
| `agent/service.decide` (edit)                                | `guard.check(sql, get_schema(...))`                                                                                              | the run's workspace schema (5.4.6)                                                             |
| `agent/result.py`                                            | `guard.check(...)`, `runner.run(...)` for the run                                                                                | the run's workspace; a deleted workspace gives a typed error (5.4.6)                           |
| `agent/tools/*`                                              | `ToolContext.schema` only; `describe_table.strip_schema` strips `<schema>.`                                                      | already workspace-neutral; the context is filled from the run, never from model output (5.4.7) |
| `evals/targets/olist.py`, `review_golden`                    | `get_schema(include_samples=True)`, `runner.run`                                                                                 | keep working on the demo through defaults (5.4.9)                                              |
| `core/health.py`                                             | `data_reader` alias                                                                                                              | unchanged                                                                                      |
| `infra/sql/001_roles.sql` / `020_reader_grants.sql`          | `demo` through the `{schema}` placeholder                                                                                        | unchanged; `002_workspace_roles.sql` is new (5.2.3)                                            |

## Workspaces: the lifecycle and a query's path (step 5)

```
POST /api/workspaces {name}                       (WorkspaceThrottle, cap MAX_WORKSPACES_PER_USER)
  lock the user row ─> check cap and name ─> Workspace row (creating)
  ─> owner connection: CREATE ROLE ws_<id>_rw / ws_<id>_ro, CREATE SCHEMA ws_<id> AUTHORIZATION ws_<id>_rw,
     GRANT CONNECT, default privileges (SELECT on future tables to _ro)     [workspaces/provisioning.py]
  ─> status ready (any failure: drop what was made, delete the row, 503 workspace_provisioning_failed)
DELETE /api/workspaces/{id}
  status deleting ─> terminate its sessions ─> DROP SCHEMA CASCADE, DROP OWNED, DROP ROLE x2
  ─> delete the row, forget the schema version. AgentRun rows stay with their workspace_id (a tombstone).
```

How a request reaches a workspace schema (nothing from the request or the model is a name):

```
?workspace=7 / body.workspace ─> workspaces.access.workspace_for(user, 7): Workspace owned by user and ready, else 404
   ├─ schema panel / ask / agent tools ─> ask.schema.get_schema(ref): cache key holds id + Redis schema version
   │      introspection as ws_7_ro (bound schema name); `_row_id` is hidden from it
   ├─ agent SQL ─> guard.check(sql, schema ws_7)  (only that qualifier; SET/RESET refused)
   │              ─> runner.run(sql, ref) ─> connection opened AS ws_7_ro (read-only txn, statement timeout, row/byte caps)
   ├─ table / column / key / relation / row APIs and the SQL console ─> connection AS ws_7_rw, one transaction,
   │      DDL logged to workspace_ddl_log, schema version bumped, size caps checked before and after
   └─ the demo (no workspace) ─> querylab_reader as before
```

A run remembers its workspace: `AgentRun.workspace_id` (null = demo), `excluded_from_evals` (true for any user workspace).
`GET /runs/{id}/result` and the loop resolve it again; a deleted workspace ends a run `workspace_gone`.

### Changing a workspace

| Call                                            | What happens                                                                                       | Errors you will see                                                                               |
| ----------------------------------------------- | -------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------- |
| `POST /workspaces/{id}/tables`                  | `CREATE TABLE` with hidden `_row_id` identity key, `COMMENT ON` for descriptions                   | `table_name_taken`, `table_limit_reached`, `column_limit_reached`, `invalid_spec`, `invalid_name` |
| `PATCH/DELETE .../tables/{t}`, `.../columns`    | rename, describe, add, drop; retype = `ALTER ... TYPE ... USING` after a `pg_input_is_valid` check | `cast_failed` (names the row), `constraint_violation`, `column_name_taken`                        |
| `PUT .../primary-key`, `POST/DELETE /relations` | real constraints; existing rows checked first                                                      | `constraint_violation` (names the row), `relation_invalid`, `relation_limit_reached`              |
| `GET/POST/PATCH/DELETE .../rows`                | by `_row_id`, values coerced and bound, all or nothing, size guard                                 | `row_invalid` (`rows[i].col`), `constraint_violation`, `workspace_full`                           |
| `POST /workspaces/{id}/sql`                     | the user's own SQL as `_rw`, one transaction, watchdog deadline                                    | `sql_failed` (SQLSTATE), `sql_invalid`, `sql_busy`, `query_timeout`, `workspace_full`             |

### Filling a workspace

CSV import was planned (5.7) and dropped; see DECISION.md. A user fills tables through `POST .../rows` (up to `WORKSPACE_MAX_ROWS_PER_EDIT` rows per call) or the SQL console (`INSERT`, or `INSERT ... SELECT`).

## Fine-tuning and scoring a model from a file (step 7)

`/data/finetune` in the container is `infra/data/finetune/` on your machine (git-ignored; added to the compose volumes, so run `docker compose ... up -d` again once to pick it up). These are Django management commands, so run them through `make eval`, not `python file.py`. Everything here is offline: the Django commands run in the dev container, training runs in Google Colab, and nothing touches the production image.

```
make eval ARGS="build_finetune_data"            -> FINETUNE_OUTPUT_DIR/{train,validation}.jsonl + manifest.json
make eval ARGS="export_benchmark --out /data/finetune/bench.jsonl"  -> prompts only (no gold SQL, no rows)
Colab: finetune/colab/train.ipynb   (data/*.jsonl on Drive -> run/adapter + train_config.json, W&B)
Colab: finetune/colab/predict.ipynb (data/bench.jsonl + adapter -> predictions-base-*.jsonl, predictions-tuned-*.jsonl)
make eval ARGS="run_eval --target spider --split held-out --predictions /data/finetune/predictions-tuned-....jsonl"
make eval ARGS="run_eval --target olist --predictions /data/finetune/predictions-tuned-....jsonl"
```

**Your setup (once):** put `train_spider.json` next to `dev.json` in `infra/data/spider/` (`database/` already holds every database); create a W&B account; in Colab add the secret `WANDB_API_KEY` and mount Drive. Copy the new `FINETUNE_*` lines from `.env.example` to `.env`. Upload `train.jsonl`, `validation.jsonl`, `manifest.json` and `bench.jsonl` to `MyDrive/querylab/data/`.

**Training data:** each record is the product's own chat: SQLite system prompt, `<schema>`/`<question>` user prompt (schema text read from the Spider SQLite file, sample values included, exactly as in eval), and the assistant reply `{"answerable": true, "sql": ..., "rationale": "", "self_confidence": 1.0}` which `ask.prompt.parse_reply` reads. Validation is whole databases.

**Predictions file** (JSONL): line 1 `{"header": {"label": ..., "adapter_sha256": ..., "train_config": ...}}`; then `{"prompt_sha256", "raw_reply", "input_tokens", "output_tokens"}` per prompt. `run_eval --predictions` stores an `EvalRun` with `provider=file`, `model=<label>`, so `eval_report`, the compare API and `--gate` work on it unchanged. A file model gets no repair retry: the same reply is replayed, so its first answer decides (the Gemini baselines do get the repair loop).

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
                    │                                                            │
 workspace roles ──>│ querylab       schema ws_<id>, owned by ws_<id>_rw;        │
 (ws_<id>_rw primary│                ws_<id>_ro has SELECT only. Both: members   │
  ws_<id>_ro reader)│                of nothing, one-schema search_path, no TEMP, │
                    │                CONNECT on querylab only, nothing on demo,   │
                    │                public or querylab_app (infra/sql/002)       │
                    └────────────────────────────────────────────────────────────┘
Deployed: the same, on Neon; data_reader and every ws_<id>_ro connection point at the read
replica (pooled endpoint), every ws_<id>_rw connection at the primary (pooled endpoint).
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
environment (see its README). Run _Get CSRF cookie and current user_ first; the
collection then sends the CSRF token on every write.

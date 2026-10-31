# Step 1: Text-to-SQL core

**Goal:** `POST /api/ask` takes a plain-English question about the Olist `demo` schema and returns the SQL that ran, the result table and a confidence score. Backend only; every screen is step 9.

**Done when:**
- A signed-in user can `POST /api/ask {question}` and get `{sql, columns, rows, row_count, truncated, confidence, model, latency_ms}`.
- The model's SQL is never run unchecked: a sqlglot guard validates it first, and it only ever runs on the read-only reader connection (see "Trust model").
- A guard rejection or a Postgres error triggers at most `ASK_MAX_REPAIR_ATTEMPTS` repair retries; after that the API returns a typed error.
- QueryLab's default Gemini key works with no user setup; a user can save their own OpenAI or Gemini key and it is used instead.
- Every ask writes one `AskLog` row.
- The guard test suite (including injection-style cases) passes, and the end-to-end tests pass with the fake LLM.
- `backend/CLAUDE.md`, `FLOW.md` and `DECISION.md` are updated, and step 1 is ticked in the README.

**Scope:** only the shared read-only `demo` schema. User workspaces are step 5, the multi-step agent is step 3, and benchmark scoring is step 2. The confidence score is a heuristic; step 2's eval measures how well it tracks correctness.

**Trust model.** The SQL the LLM returns is untrusted input (it can be wrong, or steered by a prompt injection in the question). Three independent layers, any one of which stops a write or an escape:
1. **sqlglot guard** (before running): parses the SQL as Postgres and checks the syntax tree.
2. **Reader role** (the real wall): `querylab_reader` can only SELECT from `demo`, runs read-only with a statement timeout, and cannot connect to `querylab_app` (proven in step 0.5.5).
3. **Resource caps**: statement timeout, row and byte caps, and the ask throttle.

**What goes to the LLM:** a fixed rules prompt, the schema (table and column names, types, keys and `COMMENT ON` descriptions), a few example values for low-cardinality columns (demo schema only), and the question. On a repair retry, also the failed SQL and the first line of the error. **Never** result rows, other users' questions or user data.

**Container budget (1/4 vCPU, 1 GiB):** the only new runtime dependency is `sqlglot` (pure Python, about 5 MB, no native code). It goes into the `main` group. No ML libraries. Schema text is cached in Redis, and a result is capped before it is built in memory.

Each atomic task is one small commit with a Conventional Commit message. (In practice the commits follow the numbered groups, e.g. one for 1.1 and 1.2, one for 1.8 to 1.10.) **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 1.1 Settings (strict, no fallbacks)

Every number and name goes into `.env` and `.env.example`, never into code (rule 0.2.6). The test in 0.2.5 keeps both in sync.

- [x] **1.1.1** `ASK_MAX_QUESTION_CHARS` (question length limit).
- [x] **1.1.2** `ASK_MAX_ROWS` (rows returned and the forced `LIMIT`), `ASK_MAX_RESULT_BYTES` (stop reading rows past this size).
- [x] **1.1.3** `ASK_MAX_REPAIR_ATTEMPTS` (repair retries after a guard or database error, 1).
- [x] **1.1.4** `ASK_SCHEMA_CACHE_SECONDS` (how long the rendered schema stays in Redis).
- [x] **1.1.5** `ASK_SAMPLE_VALUES_MAX` and `ASK_SAMPLE_VALUES_MAX_DISTINCT` (how many example values to show per column, and the distinct-count ceiling for a column to count as low-cardinality).
- [x] **1.1.6** `ASK_DENIED_FUNCTIONS` (comma list: `pg_sleep`, `pg_read_file`, `set_config`, `dblink`, and the like).
- [x] **1.1.7** Confidence weights: `CONFIDENCE_WEIGHT_SELF`, `CONFIDENCE_WEIGHT_CLEAN_GUARD`, `CONFIDENCE_WEIGHT_NO_RETRY`, `CONFIDENCE_WEIGHT_NON_EMPTY`, `CONFIDENCE_PENALTY_TRUNCATED`.
- [x] **1.1.8** Default key and model: `LLM_DEFAULT_PROVIDER` (`gemini`), `LLM_DEFAULT_GEMINI_API_KEY`, and `LLM_DEFAULT_MODEL` (must be in `LLM_GEMINI_MODELS`). The default key lives only in `.env`, never in the database or logs.
- [x] **1.1.9** `ASK_DEFAULT_KEY_DAILY_LIMIT` (asks per user per day on the default key; users on their own key are exempt) so the shared key cannot be drained.
- [x] **1.1.10** Read each with `django-environ` and no default; add them to the test `.env`; the sync test passes.

## 1.2 The `ask` app and dependency

- [x] **1.2.1** Add `sqlglot` to the `main` dependency group and refresh `uv.lock`.
- [x] **1.2.2** `python manage.py startapp ask` with the layout `schema.py`, `prompt.py`, `guard.py`, `runner.py`, `confidence.py`, `service.py`, `api.py`, `models.py`, `tests/`. Register it in `INSTALLED_APPS`.
- [x] **1.2.3** Check the production image still builds and stays under `IMAGE_SIZE_BUDGET_MB`. Measured 295 MB of files with sqlglot (was 291 MB), against the 300 MB budget: only 5 MB of headroom is left, so the next runtime dependency needs a real look.

## 1.3 Schema reader

- [x] **1.3.1** Dataclasses for the schema: `Table` (name, comment, columns, primary key), `Column` (name, type, nullable, comment), `ForeignKey`.
- [x] **1.3.2** `read_schema(schema="demo")`: query `information_schema` and `pg_description` through the reader connection only. Skips tables the role cannot select.
- [x] **1.3.3** Sample values: for each text column whose distinct count is at most `ASK_SAMPLE_VALUES_MAX_DISTINCT`, read up to `ASK_SAMPLE_VALUES_MAX` values. Only for the shared demo schema; it must be a parameter, so step 5 can turn it off for user data.
- [x] **1.3.4** Render compact DDL-style text (a `CREATE TABLE` per table, comments as SQL comments, foreign keys listed, sample values in a trailing comment).
- [x] **1.3.5** Cache the rendered text in Redis for `ASK_SCHEMA_CACHE_SECONDS`, keyed by schema name; a function to clear it.
- [x] **1.3.6** Tests: all 9 Olist tables appear with their comments and foreign keys, the output is stable between calls, and the cache is used on the second call.

## 1.4 Prompt builder

- [x] **1.4.1** System prompt as a constant: Postgres dialect, one SELECT/WITH statement, only the listed tables, fully qualified `demo.` names, no explanations outside the JSON.
- [x] **1.4.2** Reply contract: JSON `{"sql": str, "rationale": str, "self_confidence": 0..1}`; ask the provider for JSON output.
- [x] **1.4.3** `build_prompt(question, schema_text)` and `build_repair_prompt(question, schema_text, bad_sql, error_first_line)`. Trim the error to its first line and a length limit.
- [x] **1.4.4** Question hygiene: reject over `ASK_MAX_QUESTION_CHARS`, strip control characters; the question goes in a clearly delimited block so it cannot pass for instructions.
- [x] **1.4.5** Reply parser: extract the JSON, tolerate a fenced code block, reject missing or wrong-typed fields with a typed `LLMBadResponseError`.
- [x] **1.4.6** Tests: prompt snapshots, parser cases (clean, fenced, missing field, not JSON), and a check that no result rows or user data can reach a prompt.

## 1.5 sqlglot guard

Parses with `read="postgres"` and works on the syntax tree, never on text matching. It returns the rewritten SQL that will actually run.

- [x] **1.5.1** Typed `GuardRejected` error with a stable code and a short, safe reason.
- [x] **1.5.2** Exactly one statement; reject empty input and a trailing second statement.
- [x] **1.5.3** Root must be `SELECT`, a set operation of SELECTs, or `WITH ... SELECT`. Reject INSERT, UPDATE, DELETE, MERGE, DDL, COPY, SET, CALL, EXPLAIN ANALYZE and `SELECT ... INTO`.
- [x] **1.5.4** Every table must resolve to `demo.<known table>` (CTE names excluded). Reject `pg_catalog`, `information_schema`, `public` and any other schema. Qualify bare table names.
- [x] **1.5.5** Unknown columns are rejected using the schema from 1.3 (catches hallucinated columns before Postgres does, so the repair prompt can be exact).
- [x] **1.5.6** Function denylist from `ASK_DENIED_FUNCTIONS`, plus reject any function whose name starts with `pg_` or `lo_`; reject `FOR UPDATE` / `FOR SHARE` locking clauses.
- [x] **1.5.7** Force a limit: add `LIMIT ASK_MAX_ROWS` when absent and clamp a larger one down.
- [x] **1.5.8** Return the normalised SQL string and a small report (`clean`, list of rewrites) that the confidence score uses.
- [x] **1.5.9** Table-driven tests, about 40 cases: valid joins, CTEs, window functions, aggregates and date functions pass; stacked statements, writes, DDL, catalog access, other schemas, `pg_sleep`, `pg_read_file`, comment tricks, Unicode lookalikes, quoted identifiers and `SELECT INTO` all fail.
- [x] **1.5.10** Injection test questions with a fake LLM that returns hostile SQL; the guard must reject each one.

## 1.6 Runner

- [x] **1.6.1** Run guarded SQL on `data_reader` only; assert in code that the alias is the reader's.
- [x] **1.6.2** Open a read-only transaction and set `statement_timeout` from `READER_STATEMENT_TIMEOUT_MS` for the call, in addition to the role's own setting.
- [x] **1.6.3** Fetch with a server-side cursor in batches; stop at `ASK_MAX_ROWS` or `ASK_MAX_RESULT_BYTES` and set `truncated`.
- [x] **1.6.4** JSON-safe values: `Decimal` to string, dates and times to ISO, `UUID` to string, `bytes` refused.
- [x] **1.6.5** Map failures to typed errors: timeout (`query_timeout`), database error (`query_failed`, with the first line of the message for the repair step only).
- [x] **1.6.6** Tests against the real reader role: a working query, a timeout (`pg_sleep` is blocked by the guard, so use a heavy cross join at the runner level), the row cap, the byte cap, and serialisation of each type.

## 1.7 Provider selection and user keys

- [x] **1.7.1** `UserLLMKey` model in `accounts` (or `ask`): user, provider, `encrypted_key`, last four characters, model, created, updated. One row per user per provider. Uses `common.crypto`.
- [x] **1.7.2** `GET /api/llm-keys` lists the user's keys as provider, last four characters and model (never the key). `PUT /api/llm-keys/{provider}` saves a key and model (validated against `allowed_models`). `DELETE /api/llm-keys/{provider}` removes it.
- [x] **1.7.3** Optional cheap key check on save (a tiny request), mapping `LLMInvalidKeyError` to a clear 400. Keys are never logged or echoed.
- [x] **1.7.4** `resolve_provider(user)`: the user's saved key (OpenAI or Gemini, their chosen model) if any, else the default Gemini key from `.env`. Returns the provider and whether it is the default key.
- [x] **1.7.5** Daily limit for the default key, counted in Redis per user per day (`ASK_DEFAULT_KEY_DAILY_LIMIT`); over the limit returns a typed 429 telling the user to add their own key.
- [x] **1.7.6** Tests: save, list (no secret in the response), delete, key chosen correctly, the default limit counted, a user cannot see another user's keys.

## 1.8 Confidence score

- [x] **1.8.1** `score(self_confidence, guard_report, attempts, row_count, truncated)` returns 0 to 1 as a weighted blend using the 1.1.7 weights: the model's own rating, a clean guard (no rewrites needed), no repair retry, a non-empty result; a penalty when truncated. Clamped to 0..1.
- [x] **1.8.2** Document the meaning in `backend/DECISION.md`: it is a heuristic, not a calibrated probability; step 2 compares it with real execution accuracy.
- [x] **1.8.3** Tests: each factor moves the score the expected way, bounds hold, weights are read from settings.

## 1.9 Orchestration service

- [x] **1.9.1** `answer(user, question)`: read schema, build the prompt, call the LLM, parse, guard, run. On `GuardRejected` or a database error, build a repair prompt and retry up to `ASK_MAX_REPAIR_ATTEMPTS`; then fail with the last error.
- [x] **1.9.2** Timing for each stage (schema, LLM, guard, run) using the existing `observability/timing.py`, summed into `latency_ms`.
- [x] **1.9.3** `AskResult` dataclass returned to the API; errors are the typed domain exceptions from `common/exception`.
- [x] **1.9.4** Tests with the fake provider: first-try success, repair success, repair exhausted, hostile SQL rejected, LLM errors passed through as typed errors.

## 1.10 `AskLog`

- [x] **1.10.1** `AskLog` model in the app database: user, question, final SQL, status (`ok`, `guard_rejected`, `query_failed`, `llm_failed`, `timeout`), attempts, provider, model, key source (default or own), input and output tokens, latency, confidence, row count, error code, created.
- [x] **1.10.2** Migration on the `default` database only (the router already guarantees this).
- [x] **1.10.3** Write one row per ask, success or failure, in the service. Result rows are never stored.
- [x] **1.10.4** Retention note in `DECISION.md` (these rows seed the trace work in steps 3 and 6).
- [x] **1.10.5** Tests: a row for each outcome, no result data in the row, and a failure while writing the log does not break the ask.

## 1.11 API

- [x] **1.11.1** `POST /api/ask` (signed in only): input schema `{question}`, response schema as in "Done when", using the project's response envelope.
- [x] **1.11.2** Apply `AskThrottle` (`THROTTLE_ASK_RATE`).
- [x] **1.11.3** Map errors to HTTP codes and stable error codes: 400 (bad question, `guard_rejected`), 401, 422 (`query_failed`), 429 (throttle or default-key limit), 502 (`llm_*`), 504 (`query_timeout`). Messages stay generic.
- [x] **1.11.4** OpenAPI docs: the routes and schemas are in `/api/openapi.json` (a test checks it); the error codes are listed in the route docstring, `backend/FLOW.md` and the Postman collection. Per-error response examples were not added.
- [x] **1.11.5** Tests: signed-out gets 401, success, each error code, a throttled request gets 429 with `Retry-After`.

## 1.12 End-to-end checks

- [x] **1.12.1** Fixture set of about 15 Olist questions (counts, joins, dates, top-N, category names) with a fake LLM that returns known-good SQL; the full request path returns the expected rows.
- [x] **1.12.2** Postman collection in `backend/postman/`: sign in, save a key, ask, an ask that is guard-rejected, an ask over the limit. Run it against `make dev`.
- [ ] **1.12.3** (You) With your real Gemini key in `backend/.env`, ask 5 real questions and check the SQL and answers. This is the first time a real model touches the pipeline; report anything wrong and we fix the prompt.
- [x] **1.12.4** Memory check: dev web 202 MiB + worker 73 MiB idle (dev server, not gunicorn). The production-profile check with gunicorn is still to do at deploy time (step 10).

## 1.13 Project documents

- [x] **1.13.1** `backend/CLAUDE.md`: the `ask` app layout, the rule "SQL from an LLM only runs after the guard and only on the reader connection", and the new `.env` keys.
- [x] **1.13.2** `backend/FLOW.md`: the ask request path (question to schema to prompt to LLM to guard to runner to log to response, with the repair loop) and a trust-boundary diagram.
- [x] **1.13.3** `backend/DECISION.md`: sqlglot over a regex or a parser of our own, a three-layer guard, the heuristic confidence score, a default Gemini key with a daily cap plus bring-your-own key, sample values for the demo only, and a synchronous ask.
- [x] **1.13.4** `frontend/` docs get one line each noting the new endpoints the screens will use in step 9 (no code changes).
- [x] **1.13.5** Tick step 1 in the root README and update its status line.

---

## Decisions

- Sync request, no Huey job: LLM calls take a few seconds and the gthread workers absorb them. Step 3's agent loop revisits this.
- sqlglot is the only new runtime dependency.
- The reader role is the security boundary; the guard is a second layer and a better error source for the repair step.
- Default Gemini key from `.env` with a per-user daily cap; a user's own OpenAI or Gemini key takes priority and is exempt from the cap.
- Sample column values go to the LLM for the shared demo only.
- One `AskLog` row per ask, without result rows.

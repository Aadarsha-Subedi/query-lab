# Step 4: Analyst API

**Goal:** finish the backend surface the analyst screen (step 9) will need, so the frontend is only drawing. Steps 1 and 3 already give ask, runs, approve / edit / cancel, replay and SSE. What is missing: a schema browser, full result rows for a finished run, an approval payload the screen can render without parsing steps, a history that can be filtered, a typed error list, and a committed OpenAPI file the frontend generates its types from. Backend only; no screen.

**Done when:**
- `GET /api/schema` returns the demo schema (tables, columns, types, keys, comments, row estimates) for the schema panel.
- `GET /api/agent/runs/{id}/result` returns the full (capped) rows of a succeeded run by re-running its final SQL through the guard on the reader connection.
- A run that is `awaiting_approval` carries a `pending` block: the proposed SQL, the plan's assumptions and the guard report, so the screen needs no step parsing.
- `GET /api/agent/runs` can be filtered by status, searched by question text and ordered, within the existing pagination.
- `GET /api/agent/limits` tells the screen what is left before it hits a limit (default-key spends today, unfinished runs, open streams).
- Every error code the API can return is in one documented list, and a test fails when a code is missing from it.
- `backend/openapi.json` is committed, `make openapi` regenerates it, and CI fails when it is out of date.
- The browser path works cross-origin: credentialed CORS, CSRF on the POSTs, and SSE with cookies (checked with a real browser request, not only the test client).
- The image still passes the size check (295 MB against 300 MB today), with no new dependency.
- `backend/CLAUDE.md`, `FLOW.md` and `DECISION.md` are updated and step 4 is ticked in the root README.

**Decisions already made:** the screen uses the agent runs API, not `/api/ask` (which stays as the one-shot endpoint); every run pauses for approval; the confidence number stays `null` with a `check` label until the owner's step 3 analysis passes; every screen waits for step 9.

**Out of scope:** any screen (step 9), workspaces and a `workspace` parameter (step 5; every endpoint here is demo-only and says so in its docs), trace clustering and the eval dashboard (step 6), an auto-run toggle (needs a decision, see the open questions), CSV export of results, deleting runs.

**Open questions for the owner** (recommendation first; the plan below assumes the first answer):
1. *Auto-run toggle:* not in this step. Every run pauses, as decided in step 3. Add later only if the screen feels slow.
2. *Deleting a run from history:* not in this step. A delete would remove a human correction that step 6 wants as raw material; if you want it, the cheap shape is a `hidden_at` flag that hides a run from the user but keeps the trace.
3. *Full rows by re-running the SQL* (4.2) rather than storing rows: recommended, because step 3 decided that result rows are never stored. The cost is one more query per result view, bounded by the same row cap and timeout.

**Container budget (1/4 vCPU, 1 GiB, image 295 of 300 MB):** no new dependencies. The schema endpoint reads the cached `ask.schema.get_schema`; the result endpoint reuses `ask.runner.run`. The image-size check runs first (4.1.1) and again at the end (4.8.5).

**Trust model:** unchanged. The result endpoint never takes SQL from the request: it re-runs the SQL stored on a run the caller owns, through `guard.check` and `runner.run` on the reader connection, and only for a `succeeded` run. Sample values are shown for the demo schema only (rule from step 1).

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 4.1 Preparation

- [x] **4.1.1** Run the image-size check on the branch and record the number in `DECISION.md`. If headroom is under 3 MB, stop and trim before adding code.
- [x] **4.1.2** Branch `feat/step-4-analyst-api` from the step 3 branch (or from `main` once step 3 is merged).
- [x] **4.1.3** List every endpoint the screen will call and map each to an existing or new endpoint in a short table at the top of `FLOW.md` (the screen's contract). Gaps in that table are exactly 4.2 to 4.6.

## 4.2 Schema browser

- [x] **4.2.1** Settings: `SCHEMA_API_INCLUDE_SAMPLES` (show sample values in the browser, default off in `.env.test`), in `.env.example` and settings with no default.
- [x] **4.2.2** `GET /api/schema`: tables with name, comment, row estimate, primary key, foreign keys, and columns with type, nullability, comment (and samples if enabled). Built from `ask.schema.get_schema`, so it hits the cache; auth required; demo schema only.
- [x] **4.2.3** `GET /api/schema/tables/{name}`: one table, same shape; unknown name is a typed 404 listing nothing the caller could not already see.
- [x] **4.2.4** Cache headers (`ETag` from the cache key and its refresh time) so the panel can revalidate cheaply.
- [x] **4.2.5** Tests: auth required, shape, unknown table, samples off by default, no write or DDL possible through it.

## 4.3 Full result of a finished run

- [x] **4.3.1** Settings: a throttle rate for the result endpoint (`THROTTLE_RESULT_RATE`), next to the other scoped rates.
- [x] **4.3.2** `GET /api/agent/runs/{id}/result`: owner only; only for `succeeded` runs (otherwise a typed 409); runs `final_sql` through `guard.check` again, then `runner.run`; returns columns, rows, row count and the truncated flag. Never accepts SQL from the request.
- [x] **4.3.3** Failure mapping: a query error or timeout gives the same typed errors as `/api/ask`; the stored run is not changed.
- [x] **4.3.4** Tests: another user's run is a 404; a `failed` / `cancelled` / `awaiting_approval` run is a 409; a SQL that the guard would now refuse is refused; rows are capped by `ASK_MAX_ROWS`; throttle works; the endpoint never stores rows.

## 4.4 Approval payload

- [x] **4.4.1** Check how the `approval` step stores the SQL, assumptions and guard report (`agent/loop.py`, `agent/trace.py`), and write the finding in `DECISION.md`.
- [x] **4.4.2** Add `pending` to `RunDetailOut` and to `GET /runs/{id}`: present only while `awaiting_approval`, with `sql`, `rationale`, `assumptions` (list of strings), `guard` (changes the guard made, such as an added `LIMIT`) and `expires_at` (created from `AGENT_APPROVAL_TTL_SECONDS`).
- [x] **4.4.3** The SSE `status` event carries the same `pending` block when it announces a pause, so the screen needs no extra request.
- [x] **4.4.4** Edited SQL that the guard refuses returns the refusal reason in the typed error body (for example the offending statement type), and the run stays paused. Test that the body never echoes more than the SQL the user sent.
- [x] **4.4.5** Tests: `pending` exists only while paused, matches the approval step, disappears after approve / edit / cancel; the SSE pause event includes it; `expires_at` is correct.

## 4.5 History

- [x] **4.5.1** `GET /runs` filters: `status` (one or more), `q` (case-insensitive match on the question), `created_after` / `created_before`; ordering by `created_at` or `latency_ms` through the existing `common/order` allowlist. Pagination stays as it is.
- [x] **4.5.2** Add `has_result` (true when `succeeded`) and `edited` (true when the user changed the SQL) to `RunOut`, so a list row can show them without loading steps.
- [x] **4.5.3** Index on `(user, created_at)` and, if the plan shows a scan, on `(user, status)`. Migration on `default` only.
- [x] **4.5.4** Tests: each filter alone and combined, ordering allowlist rejects other fields, another user's runs never appear, the count in `meta` matches the filter.

## 4.6 Limits and errors the screen must handle

- [x] **4.6.1** `GET /api/agent/limits`: default-key spends used and allowed today, unfinished runs and the cap, whether the user has their own key saved, and the open-stream cap. Read-only; computed from Postgres and Redis.
- [x] **4.6.2** One list of API error codes (`docs/api-errors.md`, or a section in `FLOW.md`): code, HTTP status, meaning, what the screen should do (retry later, poll, ask for a key, show the reason). Include `agent_stream_limit`, the guard refusals, the throttle, the daily default-key limit and `not_answerable`.
- [x] **4.6.3** Test that walks all `AppException` subclasses and fails when one has no entry in the list, or the list names a code that no longer exists.
- [x] **4.6.4** The 429 body carries a `retry_after_seconds` the screen can show; test that every throttle returns it.

## 4.7 OpenAPI contract and browser path

- [x] **4.7.1** `make openapi` writes `backend/openapi.json` from the one `NinjaAPI`, sorted so diffs are small.
- [ ] **4.7.2** CI step: regenerate and fail if the file differs from the committed one (this is what keeps the frontend's generated types honest).
- [x] **4.7.3** Check that every response model is named and every error response is declared (so the generated client has types for them); fix gaps.
- [ ] **4.7.4** Update `backend/postman/collection.json` for every new or changed endpoint.
- [ ] **4.7.5** Cross-origin check with the real dev servers: from a page on the frontend origin, `fetch` with credentials to `/api/me`, a POST with the CSRF header, and an `EventSource` with credentials to `/runs/{id}/events`. Record the result and any `.env` change it needed (CORS, CSRF trusted origins, cookie `SameSite`). **(You)** run it once in a browser, since it needs the OAuth login.
- [ ] **4.7.6** Test that CORS refuses an origin not in `CORS_ALLOWED_ORIGINS` and that credentials are allowed only for the listed ones.

## 4.8 Tests, docs and wrap-up

- [ ] **4.8.1** One end-to-end test with the fake LLM: sign in, read the schema, create a run, see `pending`, edit the SQL, approve, read `result`, find the run in a filtered history, replay it.
- [ ] **4.8.2** `backend/CLAUDE.md`: new endpoints and files in the layout; the rule that `/result` re-runs stored SQL only and never takes SQL from the request.
- [ ] **4.8.3** `backend/FLOW.md`: the screen's contract table (4.1.3), the approval payload and the result fetch.
- [ ] **4.8.4** `backend/DECISION.md`: why rows are re-run and not stored; why the screen uses runs and not `/ask`; the open questions' answers; the error list; the image-size number.
- [ ] **4.8.5** Full test suite, `ruff`, `mypy`, the `.env` sync test and the image-size check pass.
- [ ] **4.8.6** Tick step 4 in the root `README.md`, add a link to this plan, and update the step 9 row so it points at the contract in `FLOW.md`.

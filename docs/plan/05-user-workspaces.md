# Step 5: User workspaces

**Goal:** let a signed-in user own up to `MAX_WORKSPACES_PER_USER` (3) workspaces next to the shared read-only Olist demo. A workspace is a private schema in the `querylab` database. The user fills it by uploading CSVs (a Huey job with live SSE progress) or by creating tables and rows by hand, and can edit it freely afterwards (rows, columns, descriptions). The agent then answers questions against it with the same guard, approval and replay as the demo. Backend only; tested through Postman. The screens are step 9.

**Done when:**

- A user can create, rename and delete workspaces, up to the cap, and always also sees the shared demo workspace.
- ~~A CSV upload returns a job id at once; a Huey job loads it with `COPY`; SSE progress; a bad file leaves nothing behind.~~ Dropped (5.7).
- A user can create a table from a column spec, insert, edit and delete rows, add / rename / drop / retype columns, drop tables, and describe tables and columns.
- `schema`, `ask` and `agent/runs` take a workspace; the schema panel, the agent's tools and the SQL it runs only ever see that workspace's schema.
- One user can never read, write, list or guess another user's workspace, in the API or in SQL (proved by tests against real roles).
- Size, row, column, table and job caps are enforced and typed errors say which cap was hit.
- Deleting a workspace drops its schema and role, and keeps its run traces.
- No new dependency; the image stays at or under 300 MB (295 today).
- `backend/CLAUDE.md`, `FLOW.md`, `DECISION.md` are updated and step 5 is ticked in the root README.

**Decisions already made:** schema-per-workspace in `querylab`, raw SQL, no Django models there; two LOGIN roles per workspace (`_rw` for the user's full SQL control, `_ro` for the agent) with no role membership between workspaces; agent queries use the reader connection (replica in production); import is a Huey background job with SSE (owner's answer); editing rows and columns after upload is allowed (owner's answer); column and table descriptions are supported (owner's answer); runs on user workspaces are excluded from step 6 eval data by default.

**Out of scope:** any screen (step 9), sharing a workspace with another user, importing from URLs or other databases, XLSX / JSON import, export, undo history for edits, multi-statement user SQL, schema-RAG (step 8). The README row says "one free workspace", which is stale; 5.9.4 fixes it to "up to 3".

**Open questions for the owner** (recommendation first; the plan assumes the first answer):

1. _Where the upload waits for the worker:_ spool it to a temp file in `UPLOAD_TMP_DIR` on the container disk (4 GB, web and worker share it). Cost: if the container sleeps or restarts before the job runs, the job is marked `failed: upload lost` and the user re-uploads. Alternative: keep bytes in Redis (cap size, memory cost on a small Redis).
2. _Row identity for editing:_ every user table gets a hidden primary key `_row_id` (bigint identity) so rows can be edited and deleted by id; it is shown in results as an ordinary column but excluded from the schema the agent sees. Alternative: require the user to pick a key column. The hidden key is simpler.
3. _Retyping a column:_ allowed only through `ALTER ... TYPE ... USING cast`, inside a transaction, so a failing cast changes nothing. Allowed types are a short list (5.2.2).

**Container budget (1/4 vCPU, 1 GiB, image 295 of 300 MB):** stdlib `csv`, psycopg `COPY`, existing Huey, Redis and SSE code. Parsing streams row batches (never the whole file in memory); one import runs at a time per container (`IMPORT_MAX_CONCURRENT`). The image-size check runs first (5.1.1) and last (5.9.5).

**Trust model:**

- Identifiers (schema, role, table, column names) are never concatenated: the schema and role names are generated (`ws_<id>`, `ws_<id>_ro`), user table and column names are sanitized to a safe slug and passed through `psycopg.sql.Identifier`.
- The platform owner role only provisions and drops workspaces. Imports, the SQL console and row / table APIs connect as the workspace's own `ws_<id>_rw`; the agent connects as `ws_<id>_ro`. No `SET ROLE` is used: a pooled `SET ROLE` can be undone with `RESET ROLE` by user SQL, so the login identity itself is the boundary (this replaces the earlier `SET LOCAL ROLE` idea).
- The agent's guard additionally refuses any schema qualifier other than the active workspace's. Grants are the real boundary, the guard is the second line.
- Two workspaces can both have a `customer` table because each is `ws_<id>.customer` in its own schema. The user never picks a schema name, the app maps workspace id to schema, and each connection's `search_path` holds only its own schema, so an unqualified `customer` always means that workspace's table.
- Cell values are only ever bound parameters or `COPY` data, never SQL text.
- Every generated DDL statement is written to a `workspace_ddl_log` row (workspace, actor, statement, time) for audit.

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 5.1 Preparation

- [x] **5.1.1** Run the image-size check on the branch and record the number in `DECISION.md`. If headroom is under 3 MB, stop and trim first.
- [x] **5.1.2** Branch `feat/step-5-workspaces` from `feat/step-4-analyst-api` (or from `main` once step 4 is merged).
- [x] **5.1.3** Read how `ask.schema.get_schema`, `ask.runner.run`, the guard, the agent tools and the SSE stream take the schema and the connection today. Write a short table in `FLOW.md` of every place that hard-codes `demo`; each row is a change in 5.4.
- [x] **5.1.4** Settings, in `.env.example`, `.env` and settings with no defaults, plus the `.env` sync test: `IMPORT_MAX_FILE_BYTES`, `IMPORT_MAX_ROWS`, `IMPORT_MAX_COLUMNS`, `IMPORT_MAX_CONCURRENT`, `IMPORT_BATCH_ROWS`, `IMPORT_STATEMENT_TIMEOUT_MS`, `UPLOAD_TMP_DIR`, `WORKSPACE_MAX_TABLES`, `WORKSPACE_MAX_RELATIONS`, `WORKSPACE_MAX_BYTES`, `USER_MAX_BYTES`, `WORKSPACE_MAX_ROWS_PER_EDIT`, `WORKSPACE_NAME_MAX_LENGTH`. `MAX_WORKSPACES_PER_USER` already exists.

## 5.2 Workspace model and lifecycle

- [x] **5.2.1** App `workspaces` with models in `querylab_app`: `Workspace` (owner, name, `schema_name`, `role_name`, status `creating | ready | deleting | failed`, created / updated), unique `(owner, name)`, index on owner. The shared demo is not a row; it is a constant `DEMO` workspace id handled in one place. _(done: `schema_name` and `role_name` are properties of the id, not stored columns; see DECISION.md)_
- [x] **5.2.2** Sanitizer module `workspaces/naming.py`: workspace names, table names and column names to safe slugs (lowercase, ASCII, no leading digit, no reserved words, length limit, de-duplicated with a numeric suffix), plus the allowed column type list: `text`, `integer`, `bigint`, `numeric`, `boolean`, `date`, `timestamp`. Unit tests with hostile names (quotes, semicolons, unicode, `pg_*`, `information_schema`, reserved words, empty).
- [x] **5.2.3** `infra/sql/002_workspace_roles.sql`: `REVOKE CONNECT ON DATABASE querylab_app FROM PUBLIC` (platform data unreachable for workspace roles), `REVOKE CONNECT ON DATABASE querylab FROM PUBLIC` with explicit grants only to the platform, reader and workspace roles, and `REVOKE ALL` on schemas `public` and `demo` and their tables and sequences from `PUBLIC` (workspace roles get no grant on `demo`; the Olist demo is queried only as `querylab_reader`); revoke `CREATE` on every non-workspace schema from `PUBLIC`; no role other than the platform owner is ever a member of a workspace role (so no `SET ROLE` path exists between workspaces); document that the owner role creates all of them. Verify on Neon that creating many LOGIN roles by SQL works and note any role-count limit. _(done locally; the Neon part is on the 5.9.7 checklist in DECISION.md)_
- [x] **5.2.4** `workspaces/provisioning.py` (owner connection): `create_workspace_schema(id)` creates the schema and **two LOGIN roles that are members of nothing**: `ws_<id>_rw` (owns the schema; used by the user's SQL console, imports and row / table APIs; primary only) and `ws_<id>_ro` (SELECT on that schema only, `default_transaction_read_only = on`; used by the agent on the replica). Both: `NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION NOBYPASSRLS`, a per-role `statement_timeout`, `idle_in_transaction_session_timeout`, a connection limit, `search_path` fixed to the workspace schema, no `TEMP`, no `CREATE` on the database, no access to any other schema. Passwords are derived (HMAC of a master secret and the workspace id and a rotation counter), never stored. Idempotent. `drop_workspace_schema(id)` terminates its sessions, then `DROP OWNED BY`, `DROP SCHEMA ... CASCADE` and `DROP ROLE` for both roles.
- [x] **5.2.4a** `workspaces/connections.py`: open a connection as `ws_<id>_rw` (primary) or `ws_<id>_ro` (reader / replica) for one request and close it at the end. No cache of our own: in production the URLs point at Neon's PgBouncer (pooled) endpoint, which keeps the server connections, so connecting per request is cheap. Locally (plain Postgres in Docker) the same code connects directly. Because PgBouncer runs in transaction mode: no session state is relied on (no `SET ROLE`, no session `SET`), psycopg uses `prepare_threshold=None`, and every request ends with its transaction committed or rolled back. Settings `MASTER_WORKSPACE_SECRET` and the pooled-host templates, no defaults. Measure per-request connect time on Neon and record it; add a cache only if the number justifies it. _(done; connect time is 11 ms locally, the Neon figure is on the 5.9.7 checklist)_
- [x] **5.2.4b** Capacity check: Neon's connection ceiling depends on compute size (small on the minimum compute). Record `max_connections` on the primary and the replica, set `IMPORT_MAX_CONCURRENT` and the per-role connection limit so one user cannot exhaust them, and test that a burst of requests from several workspaces stays under the ceiling. _(done locally; `max_connections` on Neon is on the 5.9.7 checklist)_
- [x] **5.2.5** `POST /api/workspaces`, `GET /api/workspaces` (the demo first, then the caller's own, with table counts and bytes used), `GET /api/workspaces/{id}`, `PATCH /api/workspaces/{id}` (rename), `DELETE /api/workspaces/{id}`. Typed errors: `workspace_limit_reached`, `workspace_name_taken`, `workspace_not_found` (always the same 404 for "not yours" and "missing"). Create runs provisioning in one step and marks `failed` and cleans up if it breaks.
- [x] **5.2.6** Delete: mark `deleting`, cancel running imports, drop schema and role, then remove the row; the `AgentRun` rows stay, pointing at a tombstone (`workspace_id` kept, schema gone). Test that traces survive and can still be replayed.
- [x] **5.2.7** `workspace_ddl_log` model and a helper every provisioning / table / column operation calls. Test that each DDL path writes a row.
- [x] **5.2.8** Throttle scope `workspace` for create / delete (`THROTTLE_WORKSPACE_RATE`).
- [x] **5.2.9** Tests: cap enforced, another user's workspace is a 404, demo cannot be renamed or deleted, create-then-delete leaves no schema or role behind, concurrent creates cannot exceed the cap.

## 5.3 Isolation proof (before any data goes in)

- [x] **5.3.1** Boundary tests connected as `ws_A_ro` and again as `ws_A_rw` (two real workspaces, each with a `customer` table holding different rows): unqualified `customer` returns only A's rows; `ws_B.customer`, `demo.*`, `public.*` and `querylab_app` fail with permission errors; as `_ro`, `INSERT`, `UPDATE`, `DELETE`, `CREATE`, `DROP` fail; as either role `SET ROLE`, `RESET ROLE`, `SET SESSION AUTHORIZATION`, `SET search_path = ws_B` give no access; `CREATE EXTENSION`, `COPY ... PROGRAM`, `COPY` to or from server files, `CREATE FUNCTION ... LANGUAGE C`, large objects from files, `ALTER SYSTEM`, `CREATE ROLE`, `CREATE DATABASE`, `CREATE SCHEMA`, `pg_read_file`, `dblink` all fail; a `SECURITY DEFINER` function created by the user runs with the user's own rights only; `pg_sleep` and a runaway query are cancelled by the timeout; a temp table is refused.
- [x] **5.3.2** `information_schema` / `pg_catalog` leakage check: list what a workspace role can see about other schemas and roles; hide or restrict what can be hidden, and record in `DECISION.md` what remains visible (names only) and why it is accepted.
- [x] **5.3.3** Workspace roles have no access to `demo`, `public` or `querylab_app` (the demo is queried only through the demo workspace, never mixed); test that `ws_A_rw` cannot connect to `querylab_app`, cannot `SELECT` or alter anything in `demo` or `public`, and cannot grant itself access.

## 5.4 Make the existing paths workspace-aware

- [x] **5.4.1** `ask.schema.get_schema(workspace)`: cache key includes the workspace id and a schema version; the introspection query takes the schema name as a bound parameter. Demo behaviour unchanged.
- [x] **5.4.2** Schema cache invalidation: every table / column / description change and every import bumps the workspace's schema version in Redis, so the next read re-introspects. Test staleness after each kind of change.
- [x] **5.4.3** `runner.run(sql, workspace)`: for a user workspace connect as `ws_<id>_ro` (replica in production) using 5.2.4a; the demo keeps `querylab_reader`. No `SET ROLE` anywhere: the connecting identity is the boundary. Test that a workspace connection can never be handed to another workspace.
- [x] **5.4.4** Agent guard (agent-generated SQL only, which stays single-statement read-only): take the allowed schema as a parameter and refuse any other qualifier (quoted and mixed-case spellings, `pg_catalog`, `information_schema`), and refuse `SET`, `RESET`, `SET ROLE`. This is a second line; the role is the real boundary. Add the new refusals to the error list.
- [x] **5.4.5** `AgentRun.workspace_id` (nullable = demo) and `excluded_from_evals` (true for non-demo), migration on `default` only, index `(user, workspace_id, created_at)`.
- [x] **5.4.6** `GET /api/schema`, `GET /api/schema/tables/{name}`, `POST /api/ask`, `POST /api/agent/runs`, `GET /api/agent/runs` (filter), `GET /api/agent/limits` take `workspace` (default: the demo). Ownership is checked once in one dependency, not per endpoint.
- [x] **5.4.7** Agent tools (`list_tables`, `describe_table`, sample values, and so on) receive the workspace from the run, never from model output. Test that a model asking for a table in another schema gets "no such table".
- [x] **5.4.8** Sample values: shown to the agent for the user's own workspace (their data, their key); still governed by `SCHEMA_API_INCLUDE_SAMPLES` for the schema endpoint.
- [x] **5.4.9** Re-run the step 1 to 4 test suites unchanged to prove demo behaviour did not move.

## 5.5 Tables, columns and descriptions

- [x] **5.5.1** `POST /api/workspaces/{id}/tables`: create a table from a spec (`name`, `description`, columns with name, type from the allowed list, nullable, description). Adds the hidden `_row_id` identity key; refuses an empty spec, duplicates, over `WORKSPACE_MAX_TABLES` / `IMPORT_MAX_COLUMNS`. Grants `SELECT` to the workspace role. DDL logged.
- [x] **5.5.2** `DELETE /api/workspaces/{id}/tables/{table}` and `PATCH ...` (rename, description).
- [x] **5.5.3** Columns: `POST /columns` (add, with nullable or default), `PATCH /columns/{name}` (rename, description, nullability), `DELETE /columns/{name}`.
- [x] **5.5.4** Retype a column: `PATCH` with `type`, executed as `ALTER ... TYPE ... USING col::newtype` in a transaction with the import statement timeout; a failing cast returns a typed error naming the first bad value's row id and changes nothing.
- [x] **5.5.5** Descriptions stored as Postgres `COMMENT ON` (so `get_schema` already picks them up) and surfaced in the schema panel and the agent prompt. Cap their length. Test they reach the prompt.
- [x] **5.5.6** Schema output hides `_row_id` from the agent's schema text but the table API shows it.
- [x] **5.5.7** Keys and relations, stored as real Postgres constraints in the workspace schema (so `get_schema` and the agent see joins with no extra metadata): `PUT /tables/{table}/primary-key` (one or more columns; enforces uniqueness, fails with the first duplicate's row id), `POST /relations` (child table + column(s), parent table + column(s), same workspace only, parent side must be a primary key or unique; `ON DELETE` restricted to `NO ACTION` or `CASCADE`), `GET /relations`, `DELETE /relations/{name}`. Existing data is validated when the constraint is added; a violation returns a typed error naming the first orphan row and changes nothing. Caps: `WORKSPACE_MAX_RELATIONS`.
- [-] **5.5.8** CSV import can optionally declare a primary key and relations in the preview step (5.7.3); relations are added after the table loads, in the same job, and a failure fails the job and rolls back.
- [x] **5.5.9** Row edits (5.6) respect constraints: a violating insert / update / delete returns a typed error naming the constraint; `CASCADE` deletes are counted in the response.
- [x] **5.5.10** Tests: each operation's happy path, hostile names, caps, another user's table is a 404, DDL logged, schema cache bumped, the reader still cannot write, relations across workspaces are refused, the agent's schema text lists the keys and joins.

## 5.6a User SQL console (full SQL control)

The user's own SQL is not the agent's. It runs as `ws_<id>_rw` on the primary and can do anything a schema owner can do inside the workspace: `CREATE` / `ALTER` / `DROP`, `INSERT` / `UPDATE` / `DELETE`, views, indexes, constraints, `SELECT`, multiple statements. The guard is not used here; the role is the boundary (5.3).

- [x] **5.6a.1** `POST /api/workspaces/{id}/sql`: owner only; body is the SQL text; runs in one transaction by default with `statement_timeout` and the workspace's row and byte caps; returns, per statement, the command tag, row count, and for a `SELECT` the capped rows and columns. A failing statement rolls back the whole request and returns the Postgres error code and message (message scrubbed of other schemas' names).
- [x] **5.6a.2** Size and quota: after a request that wrote data, measure the workspace size inside the transaction and roll back with `workspace_full` when over `WORKSPACE_MAX_BYTES` or `USER_MAX_BYTES`. Cap statement count, SQL length and result rows.
- [x] **5.6a.3** Every DDL statement the console runs is recorded in `workspace_ddl_log` (user, statement, time); data statements are not logged (only counted).
- [x] **5.6a.4** After DDL, bump the workspace schema version (5.4.2) so the agent and schema panel see the change.
- [x] **5.6a.5** Throttle scope `workspace_sql` (`THROTTLE_WORKSPACE_SQL_RATE`) and a per-user cap on concurrent console queries.
- [x] **5.6a.6** Tests: DDL and DML work; a multi-statement failure rolls back; a user-created view, function, trigger and index work and stay inside the workspace; attempts to reach another workspace, to escape the role or to use the forbidden features in 5.3.1 are refused; a workspace is full before it can fill the disk.

## 5.6 Row editing

- [x] **5.6.1** `GET /api/workspaces/{id}/tables/{table}/rows`: paginated, ordered by `_row_id` or a chosen column from an allowlist (existing `common/order`), simple filters per column (equals, contains), run on the reader connection.
- [x] **5.6.2** `POST .../rows`: insert up to `WORKSPACE_MAX_ROWS_PER_EDIT` rows; values are coerced by column type and bound as parameters; a bad value returns a typed error naming row index and column; all-or-nothing.
- [x] **5.6.3** `PATCH .../rows/{row_id}` (partial update) and `DELETE .../rows/{row_id}`; bulk `DELETE` by a list of ids (capped). Never accepts a `WHERE` from the request.
- [x] **5.6.4** Size guard: every write checks `WORKSPACE_MAX_BYTES` and `USER_MAX_BYTES` (5.7.4) and refuses with `workspace_full` before writing.
- [x] **5.6.5** Each write bumps the schema version only when the table's shape or row estimate class changes (not on every cell edit); cell edits do not invalidate the schema cache.
- [x] **5.6.6** Tests: type coercion table (ints, floats, dates, booleans, empty, null), injection strings stored as plain data, over-cap batch, other user's row is a 404, concurrent edits to the same row, the agent sees edited data on its next run.

## 5.7 CSV import (Huey job + SSE) — DROPPED

> **Dropped by the owner on 2026-10-31.** The import was built, tested and measured (see git history before the commit that drops it), then removed: the spool-to-container-disk design ties uploads to one container's disk and an unrelated restart loses them. It may return later with uploads going to Cloudflare R2 object storage (the file lives in the bucket, the job reads it from there, no shared local disk, no upload size middleware). Until then users fill tables with the row API or the SQL console. Everything below is kept as the design record; 5.5.8 (key and relations in an import) and the import parts of 5.2.6, 5.8 and 5.9.1 went with it.

- [-] **5.7.1** `ImportJob` model in `querylab_app`: workspace, table name, status `queued | running | succeeded | failed | cancelled`, progress counters (bytes read, rows loaded), error code and message, timestamps, temp file path.
- [-] **5.7.2** `POST /api/workspaces/{id}/imports` (multipart): checks workspace ownership, caps (`IMPORT_MAX_FILE_BYTES` while streaming, not after), `IMPORT_MAX_CONCURRENT` per user, free space; spools to `UPLOAD_TMP_DIR`; creates the job; enqueues the Huey task; returns `202` with the job id and the events URL.
- [-] **5.7.3** Sniffing before the job is queued: encoding (UTF-8 with or without BOM, otherwise a typed error), delimiter, header row, column count and names; refuse binary files and empty files. Returned in a `preview` (first rows, inferred names and types) from `POST .../imports/preview`, so a screen can confirm before importing.
- [-] **5.7.4** `POST .../imports` accepts an optional column override (names, types, skip) from the preview step. Without it, inference runs in the job.
- [-] **5.7.5** Huey task `run_import(job_id)`: in one transaction on the owner connection, create the table, `COPY` the file in batches of `IMPORT_BATCH_ROWS`, with `IMPORT_STATEMENT_TIMEOUT_MS`, updating progress in Redis every batch (not Postgres). Type inference uses a bounded sample then verifies all rows; a value that breaks the inferred type widens it to `text` or fails with its row number, per the override.
- [-] **5.7.6** Cleanup: always delete the temp file; on any error roll back, drop the half-made table, record the error code. A job found `running` after a restart is marked `failed: interrupted` by a startup sweep.
- [-] **5.7.7** `GET /api/workspaces/{id}/imports/{job}` (status) and `GET .../events` (SSE) reusing the step 3 stream helper: `progress`, `succeeded` (with table name, row count, bytes), `failed`. Cookie auth, owner only, open-stream cap shared with the agent streams.
- [-] **5.7.8** `POST .../imports/{job}/cancel`: cooperative cancel checked between batches.
- [-] **5.7.9** After success: bump schema version, check size caps (roll back and fail with `workspace_full` if over), log DDL, set `COMMENT ON` from the header if requested.
- [-] **5.7.10** Fixtures and tests: clean file, BOM, semicolon delimiter, quoted newlines, ragged rows, duplicate and empty headers, huge cell, over-cap file, over-cap rows, a 100-column file, mixed types, a hostile header (`"; DROP TABLE x;--`), cancel mid-way, worker killed mid-way, two imports at once. Run the Huey task in immediate mode for tests plus one test with the real worker. _(the "one test with the real worker" was run by hand through the dev worker with curl and a session cookie, because the pytest database is not the one the worker uses; see DECISION.md)_
- [-] **5.7.11** Measure memory and time for a cap-sized file on a 1 GiB container (Docker memory limit 1 GiB, 0.25 CPU); record the numbers in `DECISION.md` and tune `IMPORT_BATCH_ROWS` and the caps.

## 5.8 Quotas and limits

- [x] **5.8.1** Size accounting: `pg_total_relation_size` per workspace, cached briefly in Redis; `GET /api/workspaces` returns used and allowed bytes.
- [x] **5.8.2** `workspace_full` and `user_storage_full` typed errors, checked before inserts and imports and re-checked after an import commits.
- [x] **5.8.3** `GET /api/workspaces/limits`: workspaces used / allowed, bytes used / allowed, running imports and the cap. Read-only.
- [x] **5.8.4** Idle cleanup is out of scope; note in `DECISION.md` that Neon storage is the real ceiling and `USER_MAX_BYTES` times expected users must stay under it.
- [x] **5.8.5** Tests for each cap and for the error bodies.

## 5.9 Tests, docs and wrap-up

- [x] **5.9.1** One end-to-end test with the fake LLM: sign in, create a workspace, import a CSV and follow the SSE events, edit a row, add a column description, ask a question in that workspace, see `pending`, approve, read `result`, check the run is flagged `excluded_from_evals`, then ask in the demo and confirm it cannot see the user's table, then delete the workspace and replay the old run.
- [x] **5.9.2** Update `backend/postman/collection.json` and `backend/openapi.json` (`make openapi`) for every new endpoint; check every response and error model is named.
- [x] **5.9.3** Update `docs/api-errors.md` / the error list for the new codes; the drift test must pass.
- [x] **5.9.4** `backend/CLAUDE.md` (layout, the rules: owner role only in provisioning and imports, identifiers never concatenated, workspace comes from the run not the model), `backend/FLOW.md` (workspace lifecycle, import flow with SSE, how a query reaches a workspace schema), `backend/DECISION.md` (schema-per-workspace and `SET ROLE`, hidden `_row_id`, temp-file spool, free editing, caps and the memory / time numbers, what stays visible in the catalog, image size). Fix the README roadmap row to "up to 3 workspaces" and say all editing is allowed.
- [x] **5.9.5** Full test suite, `ruff`, `mypy`, the `.env` sync test and the image-size check pass.
- [x] **5.9.6** Tick step 5 in the root `README.md` and link this plan.
- [ ] **5.9.7** **(You)** Run once against the real Neon project with a replica: create two users, confirm user B cannot see user A's data through the agent, and confirm a freshly created workspace is queryable on the replica (replica lag check).

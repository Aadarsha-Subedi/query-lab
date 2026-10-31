# Step 3: Agent

**Goal:** turn the one-shot `/ask` into a run: the agent plans, looks at the schema with typed tools, proposes SQL, **pauses for the user's approval**, runs it on the read-only replica, reflects on the result, and finishes. Every run streams its steps live (SSE) and is stored as a trace that can be replayed. We also replace the confidence score, which was about 1.0 on every answer. Backend only; the screen is step 4.

**Done when:**
- `POST /api/agent/runs` starts a run; `GET /api/agent/runs/{id}/events` streams its steps (SSE); `GET /api/agent/runs/{id}` returns the stored run and steps; `GET /api/agent/runs/{id}/replay` returns the trace in order without calling any LLM.
- Every run pauses before any SQL executes. `POST .../approve`, `.../edit` (new SQL, guarded again) and `.../cancel` resume or end it.
- Tools are typed (Pydantic), listed in one registry, and each call is logged as a step.
- Run state lives in Redis (TTL); the durable trace lives in Postgres (`AgentRun`, `AgentStep`). A paused run holds no thread and no worker.
- The agent never exceeds its step, LLM-call, token, revision and wall-clock budgets (all from `.env`).
- The Olist golden set run through the agent scores **no worse than the step 2 baseline (95.1%, 39/41)**, and the report shows the extra cost (steps, tokens, latency).
- The new confidence score is checked against Olist and Spider results. If it does not separate right from wrong, the API stops returning a number (see 3.9).
- `backend/CLAUDE.md`, `FLOW.md` and `DECISION.md` are updated and step 3 is ticked in the README.

**Decisions already made (2026-10-31):** progress over **SSE**; **always pause** before running SQL; fix **confidence in this step**; hand-rolled loop, no agent framework; Huey runs the loop.

**What the approval is for.** Not safety: the guard, the reader role, the timeout and the caps already stop writes and runaway reads. The checkpoint catches *wrong-but-valid* SQL (a different reading of the question, an assumption the user did not ask for) and lets the user edit it. A user-edited SQL is kept in the trace as a human correction; those are raw material for step 6's expected-SQL set.

**Out of scope:** any screen (step 4), user workspaces (step 5), clustering and the eval dashboard (step 6), schema-RAG and the semantic cache (step 8), auto-run without approval (a per-user toggle can come with step 4 if wanted).

**Container budget (1/4 vCPU, 1 GiB, image near its 300 MB limit):** no new dependencies. Redis streams come through `django-redis`'s raw client; SSE is a plain `StreamingHttpResponse`; the loop is plain Python. Each open SSE stream occupies one gunicorn thread, so concurrent streams are capped (3.7.3) and a dropped stream resumes from the stored steps.

**Trust model:** the model still only returns JSON that we parse. It cannot execute anything itself: tools run in our code, `run_sql` goes through `guard.check` then `runner.run` on the reader alias, and only after approval. Edited SQL from the user goes through the same guard (the user is not trusted to bypass it). Tool inputs are validated; tool outputs fed back to the model are trimmed and never contain more than the row cap allows.

**What goes to the LLM:** the question, the plan so far, tool results (schema text, sample values, a result *summary*: columns, row count, first few rows capped by `AGENT_RESULT_PREVIEW_ROWS`), and error lines. Same rule as step 1: sample values for the shared demo schema only.

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 3.1 Settings (strict, no fallbacks)

- [x] **3.1.1** Budgets: `AGENT_MAX_STEPS`, `AGENT_MAX_LLM_CALLS`, `AGENT_MAX_TOKENS` (input plus output per run), `AGENT_MAX_REVISIONS` (times it may propose new SQL after a reflect), `AGENT_RUN_TIMEOUT_SECONDS`.
- [x] **3.1.2** State and pause: `AGENT_STATE_TTL_SECONDS` (Redis), `AGENT_APPROVAL_TTL_SECONDS` (how long a paused run waits before it expires).
- [x] **3.1.3** Output size: `AGENT_RESULT_PREVIEW_ROWS` (rows shown to the model), `AGENT_STEP_OUTPUT_MAX_CHARS` (trim stored tool output), `AGENT_SAMPLE_VALUES_LIMIT`.
- [x] **3.1.4** Limits: `AGENT_MAX_CONCURRENT_RUNS_PER_USER`, `AGENT_MAX_OPEN_STREAMS`, `AGENT_SSE_HEARTBEAT_SECONDS`, `AGENT_SSE_READ_BLOCK_MS`, and the throttle rate for run creation (next to the existing `AskThrottle` rate).
- [x] **3.1.5** Confidence weights for the new score (3.9), with the old self-rating weight removed from `.env.example`.
- [x] **3.1.6** Read each with `django-environ` and no default; add to `.env.example` and the test env; the sync test passes.
- [ ] **3.1.7** Decide how the default-key daily limit counts: **one run = one spend**, however many LLM calls it makes, bounded by `AGENT_MAX_LLM_CALLS`. Note in `DECISION.md` (3.12).

## 3.2 Models and migration

- [x] **3.2.1** New Django app `agent` (layout: `models.py`, `tools/`, `loop.py`, `state.py`, `events.py`, `tasks.py`, `confidence.py`, `api.py`, `tests/`). Register in `INSTALLED_APPS`.
- [ ] **3.2.2** `AgentRun`: user, question, status (`running`, `awaiting_approval`, `succeeded`, `failed`, `cancelled`, `expired`), error code, provider, model, key source, prompt version, plan text, final SQL, row count, confidence (nullable), steps/LLM calls/tokens/latency totals, revisions, finished at.
- [ ] **3.2.3** `AgentStep`: run, index, kind (`plan`, `tool`, `approval`, `execute`, `reflect`, `final`), tool name, input JSON, output summary (trimmed), status, error code, tokens, latency, `actor` (`agent` or `user`, for edits and approvals). Unique `(run, index)`.
- [ ] **3.2.4** Migration on `default` only. Result rows are never stored; a step keeps columns, row count and a preview capped by `AGENT_STEP_OUTPUT_MAX_CHARS`. Decide and note: the preview is stored, so replay can show what the user saw without re-running SQL.
- [ ] **3.2.5** Tests: relations, the unique index, status transitions rejected when illegal (for example `succeeded` back to `running`).

## 3.3 Tool registry

One file per tool in `agent/tools/`; each has a Pydantic input model, a Pydantic output model, and a pure `run(context, input)`.

- [ ] **3.3.1** Registry and base: name, description for the prompt, input/output schemas, `needs_approval` flag. Unknown tool names and invalid inputs are a typed `ToolError` fed back to the model, counted against the budget.
- [ ] **3.3.2** `list_tables`: names, row estimates and table comments from the cached step 1 schema (`schema.get_schema`).
- [ ] **3.3.3** `describe_table(table)`: columns, types, keys, comments. Unknown table gives the model the list of valid names.
- [ ] **3.3.4** `sample_values(table, column)`: from `pg_stats`, as in step 1; capped by `AGENT_SAMPLE_VALUES_LIMIT`; demo schema only.
- [ ] **3.3.5** `propose_sql(sql, rationale)`: guard-checks the SQL (`guard.check`), stores the checked SQL, and ends the act phase with a pause (3.6). It does **not** execute anything.
- [ ] **3.3.6** `finish(answer)` and `give_up(reason)`: the only ways to end a run on the agent's side; `give_up` covers unanswerable questions (replaces step 1's `answerable: false`).
- [ ] **3.3.7** Execution is not a tool the model can call. After approval the loop itself runs `runner.run` on the reader alias (the replica in production), so the model can never skip the checkpoint.
- [ ] **3.3.8** Tests per tool, and one that proves no tool can reach `runner.run` except through the approved path.

## 3.4 Prompts and parsing

- [ ] **3.4.1** Agent system prompt: role, rules (read-only, demo schema, qualified names), the tool list with schemas, the output format (one JSON object per turn: `{"tool": ..., "input": {...}}`), and the budget in plain words.
- [ ] **3.4.2** Plan prompt: ask for a short numbered plan and a list of assumptions it is making about the question. Assumptions are shown to the user at the approval step.
- [ ] **3.4.3** Reflect prompt: given the SQL, the result summary and the question, return `{verdict: "ok"|"revise", reason, revised_sql?}`. The model is told to look for the three known failure shapes from the step 2 baseline (wrong sort key, filter the question did not ask for, extra columns).
- [ ] **3.4.4** Compact start: the first prompt carries table names and comments only; the agent fetches columns with `describe_table`. Judged by the eval gate in 3.10; if it costs accuracy, fall back to the full schema text and record it in `DECISION.md`.
- [ ] **3.4.5** Parser: tolerant of code fences, rejects more than one tool call per turn, bounded retries on malformed JSON (counts as an LLM call).
- [ ] **3.4.6** Bump `PROMPT_VERSION` to `v2-agent` so eval runs are tied to it.
- [ ] **3.4.7** Tests with a fake LLM: valid turns, bad JSON, two tool calls in one turn, unknown tool, prompt-injection text in the question (must not change the tool list or skip approval).

## 3.5 Run state (Redis) and trace (Postgres)

- [ ] **3.5.1** `state.py`: save and load a run's working state (plan, message history trimmed to budget, pending SQL, counters) as JSON under `agent:run:{id}` with `AGENT_STATE_TTL_SECONDS`. One writer at a time: a Redis lock per run so an approve click and the worker cannot race.
- [ ] **3.5.2** Step writer: every step is written to `AgentStep` first, then published as an event (3.7), so the stored trace is the source of truth.
- [ ] **3.5.3** Expiry: a paused run past `AGENT_APPROVAL_TTL_SECONDS` becomes `expired` (checked on resume and by a Huey periodic task); expired and cancelled runs keep their trace.
- [ ] **3.5.4** Per-user concurrency cap (`AGENT_MAX_CONCURRENT_RUNS_PER_USER`) counted in Redis; a second run while at the cap is refused with a typed error.
- [ ] **3.5.5** Tests: state round trip, TTL expiry, lock prevents a double resume, cap refuses the extra run.

## 3.6 The loop

`loop.py` is a function `advance(run_id)`: load state, take turns until it must stop, save state. It stops on `propose_sql` (pause), `finish`, `give_up`, a budget limit, or an error.

- [ ] **3.6.1** Plan turn, then act turns. Each LLM call and each tool call is one step; budgets are checked before every call.
- [ ] **3.6.2** On `propose_sql`: status becomes `awaiting_approval`, an `approval` step records the SQL, the plan's assumptions and the guard report, and `advance` returns. No thread waits.
- [ ] **3.6.3** `resume(run_id, decision)`: `approve` runs the checked SQL; `edit` guards the new SQL (refusal gives the user a typed error and the run stays paused); `cancel` ends the run. The `execute` step records who acted (`user`) and whether the SQL was edited.
- [ ] **3.6.4** After execute, a cheap rule check first: error, empty result, truncated, 1 by 1. A flag, or a result the model should read, triggers the reflect call; a clean result goes straight to `finish`.
- [ ] **3.6.5** `revise` from reflect starts a new `propose_sql` and pauses again (always pause), up to `AGENT_MAX_REVISIONS`. A query error follows the same path, with the one-line error as the reflect input (this replaces step 1's repair loop for runs; `/api/ask` keeps its own).
- [ ] **3.6.6** Failure mapping: LLM errors, guard refusals, timeouts and budget overruns each get a typed error code and a final `failed` status with the trace kept. Timeouts are not retried (same rule as step 1).
- [ ] **3.6.7** Tests with a scripted fake LLM: straight path, pause then approve, edit then approve, edit refused by the guard, cancel, revise loop hitting the cap, each budget limit, query error then revise, `give_up`.

## 3.7 Jobs and SSE

- [ ] **3.7.1** Huey tasks `start_run(run_id)` and `resume_run(run_id, decision)`; both call `loop`. Tests run Huey in immediate mode as before.
- [ ] **3.7.2** `events.py`: publish each step to a Redis stream `agent:events:{run_id}` (trimmed, TTL). Event ids are the step index, so a client can resume with `Last-Event-ID`.
- [ ] **3.7.3** `GET /api/agent/runs/{id}/events`: `StreamingHttpResponse` of `text/event-stream`. On connect it first sends any stored steps after `Last-Event-ID` from Postgres, then reads the stream with a blocking read (`AGENT_SSE_READ_BLOCK_MS`), sends a heartbeat comment every `AGENT_SSE_HEARTBEAT_SECONDS`, and closes on a terminal status. Owner only. Refused over `AGENT_MAX_OPEN_STREAMS` with a typed error the client can answer by polling `GET /runs/{id}`.
- [ ] **3.7.4** Headers that keep proxies from buffering (`Cache-Control: no-cache`, `X-Accel-Buffering: no`); check that gunicorn's `gthread` worker and Cloudflare pass chunks through (manual check on the local container; recorded in `DECISION.md`).
- [ ] **3.7.5** Tests: stream replays stored steps, resumes from `Last-Event-ID`, ends on terminal status, enforces the open-stream cap, and refuses another user's run.

## 3.8 API

All under `/api/agent`, session auth (`django_auth`), the usual envelope, and a run-creation throttle.

- [ ] **3.8.1** `POST /runs` (question): validates with `prompt.validate_question`, resolves the key (`keys.resolve_provider`, one default-key spend per run), creates the run, enqueues `start_run`, returns the run.
- [ ] **3.8.2** `GET /runs` (own runs, newest first, paginated) and `GET /runs/{id}` (run plus steps). Owner only; someone else's id is a 404.
- [ ] **3.8.3** `POST /runs/{id}/approve`, `/edit` (body: `sql`), `/cancel`. Only valid while `awaiting_approval`; otherwise a typed 409.
- [ ] **3.8.4** `GET /runs/{id}/replay`: the steps in order, as stored, with no LLM and no database query against `demo`.
- [ ] **3.8.5** Schemas in the OpenAPI doc; update the Postman collection in `backend/postman/`.
- [ ] **3.8.6** Tests: auth required, ownership, state rules, throttle, envelope shape, and one end-to-end test with the fake LLM from `POST /runs` through approve to `succeeded`.

## 3.9 Confidence, replaced

Step 2 showed the old score at about 1.0 for every Olist answer (rank correlation 0.09 on Spider). The model's own rating carried almost all of the weight and never moved.

- [x] **3.9.1** Remove the self-rating from the score. Candidate features that do vary: repair/revise count, whether the user edited the SQL, guard changes, whether the agent checked `sample_values` for the filters it used, result shape (empty, one row, truncated), and whether the reflect verdict was `ok` on the first pass.
- [ ] **3.9.2** Offline analysis first: run the Olist golden set and the Spider held-out set through the agent, then compute each candidate feature against correct/wrong with a small script in `evals` (no new dependency; Spearman in plain Python). **(You)** read the result table.
- [x] **3.9.3** Keep only features that separate right from wrong. Write the new `agent/confidence.py` with weights from `.env`.
- [ ] **3.9.4** Acceptance rule, decided now so the result cannot be argued afterwards: if accuracy in the top bucket is not higher than the bottom by `CONFIDENCE_MIN_SEPARATION` (an `.env` value) on the Olist run, the API returns `confidence: null` and the UI shows a plain "checked" or "needs a look" label from reflect and guard instead of a number.
- [ ] **3.9.5** Tests for the score function; update the `/api/ask` path to use the same function, or leave it and say so in `DECISION.md`.

## 3.10 Evaluate the agent against the baseline

- [ ] **3.10.1** New eval target mode `--runner agent` for `run_eval`: starts a run, auto-approves (an eval has no human; recorded as `actor=eval`), and scores the final SQL with the existing comparison.
- [ ] **3.10.2** Report extra columns: steps, LLM calls, tokens and latency per question, and revisions.
- [ ] **3.10.3** (You) Run the Olist golden set with `gemini-3.5-flash-lite`. Gate: at least the 95.1% baseline. If it falls below, look at the failing traces before touching prompts, and try 3.4.4's fallback first.
- [ ] **3.10.4** Run Spider held-out only if a spare day of free-tier quota exists (the agent makes several calls per question); otherwise a fixed 100-question sample, recorded as such.
- [ ] **3.10.5** Record the results in `backend/DECISION.md`.

## 3.11 Safety and abuse checks

- [ ] **3.11.1** Tests that a prompt injection in the question or in a stored value (`sample_values` output) cannot reach `runner.run` before approval, cannot add a tool, and cannot raise a budget.
- [ ] **3.11.2** Test that approving or editing someone else's run fails, and that two simultaneous approves run the SQL once.
- [ ] **3.11.3** Check a stalled worker: the container sleeps with a run paused; on wake the run is still there (state in Redis may be gone, so `resume` rebuilds from `AgentStep`). Decide and record whether a run survives a restart.

## 3.12 Docs and wrap-up

- [ ] **3.12.1** `backend/CLAUDE.md`: the `agent` app layout, the rule that execution only happens in the loop after approval, how to run the agent eval.
- [ ] **3.12.2** `backend/FLOW.md`: the run flow (start, plan, tools, propose, pause, approve or edit, execute, reflect, finish) and the SSE flow.
- [ ] **3.12.3** `backend/DECISION.md`: SSE over polling and its cost; always-pause and what the approval is for; one spend per run; compact schema start; confidence replacement and the measured result; no agent framework.
- [ ] **3.12.4** Tick step 3 in the root `README.md` and add a link to this plan.
- [ ] **3.12.5** Full test suite, `ruff`, `mypy` and the `.env` sync test pass; the image-size check still passes.

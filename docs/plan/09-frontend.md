# Step 9: Frontend

**Goal:** the whole product UI, built on the approved design system and against the backend contract (`backend/FLOW.md`: "The analyst screen's contract", "Workspaces", "The workbench contract"; `backend/API_ERRORS.md`; generated `backend/openapi.json`). A signed-in user asks a question in plain English, watches the agent work, approves or edits the SQL, reads the result, and reviews past runs. They can also manage their own workspaces and LLM key. Staff also get the trace viewer and the eval dashboard.

**Done when:**
- Types for every endpoint are generated from `backend/openapi.json`; CI fails when they are stale.
- Sign-in page (Continue with Google / GitHub), logout, landing page, and the route guards work against the real backend.
- Analyst chat: schema panel, ask, live progress, approval card (approve / edit / cancel), result table, feedback.
- History with filters and ordering, and a replay view.
- Workspaces: list, create, delete, switch; tables, columns, primary key, relations, rows, SQL console. No CSV upload.
- LLM keys settings page and a limits indicator.
- Staff only: trace viewer (runs, clusters, case review) and eval dashboard (runs, by-cluster, compare).
- Every component that fetches has loading, error, empty and success states (design-system.md §13). No automatic retries, no refetch on focus or reconnect, anywhere.
- No new runtime dependency unless listed in this plan; `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build` pass and `/design` still never ships.
- `frontend/CLAUDE.md`, `FLOW.md`, `DECISION.md` are updated and step 9 is ticked in the root README.

**Decisions already made (owner, 2026-11-01):**
1. Step 8 (schema-RAG, semantic cache) is skipped; nothing here depends on it.
2. **No CSV upload.** CSV import was dropped in 5.7. Workspaces are filled through the rows API and the SQL console.
3. **A dedicated LLM-keys settings page**, not a dialog.
4. **No retries of failed requests, ever.** A failed fetch shows its `ErrorState`; the user reloads the page (or uses the component's own Try again, which is a single manual refetch) to get new data. This matches the existing rule (no `retry`, no refetch on focus/reconnect). It also covers the live stream: if the event stream drops, the UI says so and offers a manual "Reconnect" button; it never reconnects on a timer or with backoff.

**Out of scope:** CSV upload, step 8 features, an auto-run toggle, deleting runs, CSV export of results (backend has none), a public eval dashboard and deploy (step 10), mobile-first redesign (we stay responsive down to phone width but do not design phone-only flows), i18n.

**Container budget:** the frontend is a static build served from Cloudflare, not in the 1 GiB backend container. The browser budget still matters: route-level code splitting (TanStack Router `autoCodeSplitting`) so the workbench and workspace editor load only when opened; a result table never renders more rows than the backend caps (`ASK_MAX_ROWS`); no charting library unless 9.12 shows a need (then a small one, decided in `DECISION.md`).

**Trust model (frontend):**
- The server decides what staff may see. The UI hides workbench links for non-staff, but a direct URL still shows the 403 `staff_only` as an `ErrorState`, never as a crash.
- SQL from the agent and results are rendered as text, never as HTML. Free-text questions are escaped the same way.
- No API keys, tokens or secrets in the bundle or in local storage. The user's LLM key is sent once to `PUT /llm-keys/{provider}`, never stored client side, and the page only shows whether a key is set.
- State rule stays: server data in TanStack Query; UI-only state (sidebar, open panels, draft SQL text) in Zustand. The only exception is the live run, see 9.4.

**Conventions to hold in every task:** `queryOptions` in `features/<name>/api.ts`; `useQuery` in the component that shows the data, rendered through `<QueryBoundary>`; mutations show errors by `code` (see 9.1.4); every button has a Hugeicons icon; tokens only, no raw hex or one-off px; each task adds or updates tests; no skipping failing tests.

Each atomic task is one small commit (Conventional Commits). **(You)** marks a task only you can do. Claude commits locally and never pushes.

---

## 9.1 Preparation and the typed client

- [x] **9.1.1** Branch `feat/step-9-frontend` from `feat/step-7-lora-finetune` (done when this plan is committed). Record the baseline: `pnpm test`, `lint`, `typecheck`, `build` all pass; note the build size in `DECISION.md`.
- [x] **9.1.2** Add `openapi-typescript` as a dev dependency. `pnpm gen:api` writes `src/lib/api/schema.gen.ts` from `../backend/openapi.json` (committed, never edited by hand, like `routeTree.gen.ts`).
- [x] **9.1.3** Test/CI: `pnpm gen:api:check` regenerates to a temp file and fails when the committed one differs. Added to the frontend CI job.
- [x] **9.1.4** `lib/api/errors.ts`: a typed map from API error `code` to a user message and an action (`API_ERRORS.md` is the source). Unknown codes fall back to the server's message. Test: every code in `API_ERRORS.md` has an entry (a drift test, like the backend's).
- [x] **9.1.5** Extend the client with `put` and `patch` (needed for keys, feedback, workspace edits) with the same envelope, CSRF and 429 handling and no retry. Tests for each verb, including a CSRF header and a 429 toast.
- [x] **9.1.6** Add the missing base components from shadcn, restyled with tokens and `<Icon>`, each shown on `/design` in light and dark: `select`, `textarea`, `checkbox`, `switch`, `scroll-area`, `sheet`, `popover`, `alert-dialog`, `pagination`/`data-table` helper (built on `table`). Tests per component.
- [x] **9.1.7** `lib/format.ts`: durations, relative times, numbers, byte sizes, one place, using `Intl`. Tests.

## 9.2 App shell, sign-in, landing

- [x] **9.2.1** (the staff-only nav entries wait for a staff flag on `/api/me`, which it lacks today; see DECISION.md) App layout (`_app.tsx`): header with logo, nav, workspace switcher slot, theme toggle, user menu (avatar, logout); a collapsible side nav (Zustand `ui` store); responsive down to phone width. Nav items for staff only appear when `/me` says staff (confirm the field name in `openapi.json`; if missing, ask the backend owner, do not guess).
- [x] **9.2.2** Sign-in page (`_public/signin`): Continue with Google / GitHub using the allauth headless provider redirect (FLOW.md "Auth flow"), error states for a denied or failed sign-in, link back to landing. The local dev sign-in page stays backend-only.
- [x] **9.2.3** Logout: allauth session delete, then clear the query cache and go to `/`. Test the guard flow both ways.
- [x] **9.2.4** Landing page (`_public/index`): what QueryLab is, a three-step "ask, approve, measure" explainer, the sign-in buttons, the demo dataset note (Olist, CC BY-NC-SA 4.0 credit). No marketing images that need hosting.
- [x] **9.2.5** 404 and 403 pages inside the shell; route `errorComponent` that never shows a stack trace.
- [x] **9.2.6** `Limits` indicator in the header from `GET /agent/limits` (used / allowed / remaining / resets_at, has_own_key). Its own loading/error box; no polling. Test the over-limit state.

## 9.3 Schema panel

- [x] **9.3.1** `features/schema`: `schemaQuery(workspace?)` using `ETag`/`If-None-Match` through the browser cache; nothing custom. Types from the generated file.
- [x] **9.3.2** `SchemaPanel`: tables as a collapsible list with column name, type, key and relation badges, comments as tooltips, row estimates. Search box filters locally. Zustand holds which tables are open.
- [x] **9.3.3** Table detail from `GET /schema/tables/{name}` in a side sheet; `table_not_found` as an `ErrorState`.
- [x] **9.3.4** Tests: loading, error with Try again, empty (no tables), filter, collapsed state persisted per session.

## 9.4 Analyst chat: ask, live run, approval

- [x] **9.4.1** `features/ask/api.ts`: `useCreateRun` (`POST /agent/runs {question, workspace?}`), `runQuery(id)` (`GET /agent/runs/{id}`, includes `pending`). Typed errors: `agent_run_limit`, rate limit, missing key.
- [x] **9.4.2** `useRunStream(runId)`: an `EventSource`-style reader (fetch + stream, because we need the CSRF/cookies and `Last-Event-ID`) that feeds events into the Query cache entry for the run. States: connecting, live, paused (awaiting approval), done, **dropped**. On drop it stops and shows "Connection lost. Reconnect" (manual button resends with `Last-Event-ID`); no timer, no backoff. Handles `agent_stream_limit`. Pure reducer for events, fully unit tested, plus tests for drop and manual reconnect.
- [x] **9.4.3** `AskBox`: textarea, send button with icon, length limit from `.env`, disabled while a run is unfinished (`agent_run_limit` shown if the cap is hit), keyboard shortcut. Question text is plain text.
- [x] **9.4.4** `RunTimeline`: the agent's steps as a vertical list (plan, act, reflect, tool calls) with status icons, collapsible details. Never shows secrets or raw model prompts; shows what the API gives.
- [x] **9.4.5** `ApprovalCard`: renders `pending` (SQL in `CodeBlock`, rationale, assumptions, guard codes as badges with plain-language tooltips, revision, an `expires_at` countdown that only displays, never auto-acts). Buttons: Approve, Edit SQL, Cancel, each with an icon.
- [x] **9.4.6** Edit SQL flow: inline editor (monospace textarea, no heavy editor dependency), submit to `POST .../edit`; a 400 `guard_rejected` shows `errors[0].message` under the field and keeps the run paused. Draft text lives in Zustand so a tab switch does not lose it.
- [x] **9.4.7** Approve / cancel mutations; after success the stream is reopened (manual user action is not needed here: it is the same user-initiated step) and the card moves to a done state. Expired approval and already-resolved states handled by `code`.
- [x] **9.4.8** `ResultTable`: `GET /agent/runs/{id}/result`; columns, rows, `row_count`, `truncated` banner, the executed SQL with a Copy button, the "numbers can differ if data changed" note. Errors `run_not_succeeded`, `query_failed`, `query_timeout`, `guard_rejected` each get a plain message. Table is virtualised only if rows exceed what the DOM handles; the cap is small, so default to a plain table and measure first.
- [x] **9.4.9** Feedback 👍/👎 (`PUT/DELETE .../feedback`) on finished runs; `run_not_finished` handled; optimistic UI is not used (wait for the server).
- [x] **9.4.10** Chat page `_app/ask`: schema panel left, conversation centre, `?run=` search param so a run is linkable; the page keeps only the active run id in the URL. Test the whole flow with a mocked server: ask, pending, edit, approve, result, feedback.
- [x] **9.4.11** Empty state with three clickable example questions for the demo workspace (static text in a constants file). Failure states for `failed` and `cancelled` runs.

## 9.5 History and replay

- [x] **9.5.1** `features/history/api.ts`: `runsQuery(filters)` for `GET /agent/runs` with `status`, `q`, `created_after`, `created_before`, `ordering`, `limit`, `offset`. Filters live in the URL search params (validated with Zod), so a refresh keeps them.
- [x] **9.5.2** `HistoryTable`: question, status badge, workspace, created time, `edited`, `has_result`; sort, filter bar, pagination from `meta.count`. Empty and error states.
- [x] **9.5.3** Row click opens `/ask?run=<id>` (finished runs show the saved view; result is re-fetched on demand).
- [x] **9.5.4** Replay page `_app/runs/$runId/replay`: `GET .../replay` as a step-by-step stepper (previous / next), showing each step's payload as it was.
- [x] **9.5.5** Tests: filter-to-URL sync, pagination, replay stepping, 404 for a run that is not yours.

## 9.6 Workspaces

- [ ] **9.6.1** `features/workspaces/api.ts`: list, limits (`GET /workspaces/limits`), create, rename, delete. The demo is the default and read-only; `PATCH /workspaces/demo` handled only if the contract says what it does (check `openapi.json`; otherwise leave it out and note it in `DECISION.md`).
- [ ] **9.6.2** Workspace switcher in the header and `/workspaces` page: cards for the demo and up to the cap; create dialog (name validation from API errors `invalid_name`, `workspace_limit_reached`); delete with `alert-dialog` and a typed-name confirmation. Active workspace id lives in the URL search param `workspace`, not Zustand, so every query key includes it.
- [ ] **9.6.3** Workspace detail `/workspaces/$id`: tabs Tables, Relations, SQL console. Size and count usage bars from the limits endpoint.
- [ ] **9.6.4** Tables tab: list, create table form (columns, types, descriptions) with react-hook-form + Zod, errors `table_name_taken`, `table_limit_reached`, `column_limit_reached`, `invalid_spec`, `invalid_name` mapped to fields.
- [ ] **9.6.5** Table editor: rename, describe, add/drop/rename/retype a column, set primary key. Destructive actions use `alert-dialog`. `cast_failed` and `constraint_violation` show which row the server named.
- [ ] **9.6.6** Relations tab: list, add, delete; `relation_invalid`, `relation_limit_reached`.
- [ ] **9.6.7** Rows grid: paged rows by `_row_id`, add row form from column types, inline edit, delete; `row_invalid` errors addressed as `rows[i].col`; `workspace_full`. All-or-nothing batch insert up to `WORKSPACE_MAX_ROWS_PER_EDIT` (value in `.env`).
- [ ] **9.6.8** SQL console: textarea, run, results in the same `ResultTable`; `sql_failed` shows SQLSTATE and message, `sql_busy`, `sql_invalid`, `query_timeout`, `workspace_full`. A short note says it runs as the workspace's own role.
- [ ] **9.6.9** After any change the schema query for that workspace is invalidated once (a mutation's own `onSuccess`, not a poll).
- [ ] **9.6.10** Tests for each tab with a mocked server, including every typed error above.

## 9.7 LLM keys settings

- [ ] **9.7.1** `features/llm-keys/api.ts`: `GET /llm-keys`, `PUT/DELETE /llm-keys/{provider}`.
- [ ] **9.7.2** `_app/settings/keys` page: one card per provider the API lists, shows set / not set (never the key), a password-type input to set or replace, a Remove button with confirmation. The key is cleared from the form state right after submit.
- [ ] **9.7.3** Explain on the page what a key changes (it moves the user from the shared default key's limits to their own; text from `FLOW.md`) and link to it from the limits indicator (9.2.6) and the `agent_run_limit` / missing-key errors.
- [ ] **9.7.4** Tests: validation errors from the API, key never rendered, replace and remove flows.

## 9.8 Staff workbench: trace viewer

- [ ] **9.8.1** Staff route group `_app/workbench/*` guarded in its layout `beforeLoad` by the `/me` staff flag; a signed-in non-staff user lands on the 403 page. Test both users.
- [ ] **9.8.2** `features/workbench/api.ts`: runs, run detail, clusters, cases, case detail, draft, approve, reject, mark-unanswerable. Errors `case_not_found`, `case_not_reviewable`, `draft_unusable`, `staff_only`.
- [ ] **9.8.3** Runs list `/workbench/runs`: filters from the contract, table, link to detail. Run detail: steps, proposed vs approved SQL as a side-by-side diff (small hand-written line diff; no diff library unless it fails the budget), the user's feedback.
- [ ] **9.8.4** Clusters view: label, size, representative question, counts per status; click filters the cases list.
- [ ] **9.8.5** Cases list and case detail: status badge, drafted SQL, `draft_error`, a rows preview ("run now, never stored" note), a link to the source trace.
- [ ] **9.8.6** Review actions: Approve (optionally edit question and SQL first), Reject, Mark unanswerable, Draft a batch. After approving, show the guarded-and-run result; `guard_rejected` on `sql` shown under the SQL field. A failed draft requires an edited SQL before Approve is enabled (matches the case-status rules).
- [ ] **9.8.7** Tests: the whole review loop with a mocked server; non-reviewable status; unusable draft.

## 9.9 Staff workbench: eval dashboard

- [ ] **9.9.1** Eval runs list `/workbench/evals`: filters (target, runner, model, prompt version), accuracy, cost per question, finished time.
- [ ] **9.9.2** Eval run detail: per-case results (question, gold, predicted, outcome, reason, link to the trace) with outcome filter; `by_cluster` accuracy as a table with inline bars.
- [ ] **9.9.3** Compare view `?base=&other=`: pick two runs; accuracy difference, flipped-to-wrong and flipped-to-correct lists, per-cluster difference; `eval_runs_not_comparable` as a clear message.
- [ ] **9.9.4** Chart decision: tables with inline bars first. Add a chart library only if a tracked-over-time view proves necessary; record the choice and bundle impact in `DECISION.md`. Follow the `dataviz` guidance and token colours if one is added.
- [ ] **9.9.5** Tests: filters, detail, compare with flips in both directions, not-comparable error.

## 9.10 Quality: states, accessibility, responsive

- [ ] **9.10.1** Audit every fetching component against §13: loading skeleton, error with Try again, empty, success, same box size. A test per feature renders each of the four states.
- [ ] **9.10.2** Grep-based test: no `retry`, `refetchOnWindowFocus`, `refetchInterval`, `setInterval`, `setTimeout`-driven refetch or `EventSource` auto-reconnect in `src/`; the one allowed manual reconnect is named in an allowlist. This enforces decision 4.
- [ ] **9.10.3** Keyboard and screen-reader pass: focus order, dialog focus trap, live region for run status changes (`aria-live=polite`), approval buttons reachable, tables with headers and captions. `eslint-plugin-jsx-a11y` rules via the existing lint config only if it adds no peer conflicts; otherwise manual checklist in `DECISION.md`.
- [ ] **9.10.4** Responsive pass at 375 px, 768 px, desktop for ask, history, workspaces, workbench; no horizontal page scroll (tables scroll inside their box).
- [ ] **9.10.5** Dark and light check of every new screen; add each new composite component to `/design` where it is reusable (`ApprovalCard`, `ResultTable`, status badges).
- [ ] **9.10.6** Route-level code splitting verified: the production build's main chunk size is recorded; workbench and workspace chunks are separate; `build.test.ts` still proves `/design` is absent.

## 9.11 Run it against the real backend

- [ ] **9.11.1** `make dev`, sign in with the local dev sign-in, and click through the whole path in the built-in browser: ask, approve, edit, result, history, replay, a workspace with a table and rows, keys page, workbench as staff. Fix what breaks; record findings in `DECISION.md`.
- [ ] **9.11.2** **(You)** The real-browser CORS and OAuth checks that were left over from 4.7.5 and 0.8.5-0.8.6 (Google and GitHub sign-in) need your credentials; with them done, test the sign-in page end to end. Needs the live Gemini key for a real agent run.

## 9.12 Close-out

- [ ] **9.12.1** `pnpm lint`, `typecheck`, `test`, `build`, `gen:api:check` all pass, run locally with the same commands the CI frontend job uses (nothing is pushed).
- [ ] **9.12.2** Update `frontend/CLAUDE.md` (layout of new features, new conventions), `frontend/FLOW.md` (the run's live flow, approval flow, staff guard, manual-reconnect rule) and `frontend/DECISION.md` (each decision above, bundle sizes, anything deferred).
- [ ] **9.12.3** Tick step 9 in the root README with a note of what remains for you (9.11.2).

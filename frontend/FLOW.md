# Frontend: FLOW.md

## App boot

```
index.html            boot screen (plain HTML + tokens.css + boot.css), themed before any JS
  -> src/main.tsx
     1. parseEnv(import.meta.env)       invalid -> remove boot screen, <EnvErrorScreen/>
     2. initApi + createQueryClient     retry: false, no refetch on focus/reconnect
     3. queryClient.query(meQuery)      GET /api/me (also sets the csrftoken cookie)
          200 -> user, 401 -> null (signed out)
          anything else / no answer -> failBoot(): "Querylab can't reach the server" + Reload page
        (skipped for /design in dev: the showcase needs no backend)
     4. router.load()                   guards reuse the cached /api/me answer
     5. render <QueryClientProvider><RouterProvider/></...>, finishBoot()
          boot screen: removed at once if boot took < --boot-delay, else kept until
          --boot-delay + --boot-min-visible, then faded out over --duration-base
```

## Routes (src/routes, file-based; src/routeTree.gen.ts is generated)

```
__root            ThemeController, TooltipProvider, Toaster; not-found and error pages (RouteStatus)
_public           beforeLoad: signed in -> redirect /ask
  /                 landing: navbar, hero with a static product preview, how it works, features, baseline scores, FAQ, sign-in band, footer (no request but the boot's /api/me)
  /login            Continue with Google / GitHub (real form POSTs to allauth)
  /auth/callback    only seen when a sign-in did not finish (a finished one is moved on to /ask by the guard)
_app              beforeLoad: signed out -> redirect /; adds { me }; renders AppShell (header: logo, workspace picker on Ask only, avatar menu with theme and sign out; side nav)
  /ask              ?tab=ask|schema|import|sql&table=&run=&workspace=&question=   tabs (the workspace picker is in the top bar): the shared demo has Ask and Schema; every workspace has Ask and Schema; on a private workspace the Schema page also has a three-dots menu (`WorkspaceMenu`) with View storage capacity (modal), Import dump (popup: upload form and a table of past imports) and Run query (a side sheet with the read-only SQL box; the last query is kept per workspace in `stores/query-draft.ts`, localStorage). Tables and rows are not editable in the app. Old `?tab=import` / `?tab=sql` links open Schema. A tab that does not exist for the chosen workspace falls back to its nearest one. Ask is a chat built from the shadcn AI elements: Message Scroller (keeps your place while the reply streams, with a scroll-to-end button) around one run, the question as a Message with a muted Bubble, the agent's side as a Message (Reasoning on Trace while it works, Confirmation on Item for the SQL approval, then the result and the thumbs), and below it Suggestions (they wrap onto new lines) and the Prompt Input (Input Group: textarea with the send icon inside; Enter sends, Shift+Enter new line; `?question=` pre-fills it). One centred column (`--chat-max`); the page itself does not scroll on this tab. Schema: table list on the left (a dropdown on phones); for the chosen table its name and description, then the data as a table whose headers carry the column's name, type and PK/FK badges plus an info button (popover: the column's notes, primary key, foreign key target); rows from GET /schema/tables/{name}/rows, manual Previous/Next
  /settings         AI settings (no visible page header; the nav item names it): a row with title and description on the left and a QueryLab AI / Custom AI dropdown on the right (GET/PUT /llm-settings). With QueryLab AI chosen, a second row (same pattern) picks the Gemini model used on the shared key (`querylab_model`). A Usage section at the end shows what is left before a limit, as shadcn Progress bars (questions today on the shared key, open questions, live views). Only for Custom AI: a table of saved keys (provider, in-use radio, model dropdown, replace, remove) or an empty state whose Add new API key button opens a modal (provider dropdown with logos from src/assets/providers, key, model)
  /history          ?status=&q=&ordering=&offset=&workspace=   your runs; rows link to /ask?run=; each row has Replay and Ask again as icon buttons
  /runs/$runId/replay   stored trace, one step at a time
  /workspaces       the demo and your private workspaces (no visible page header); create; the card opens its workspace in Ask on Schema; per-card actions menu: Ask, Import a dump (the Import tab), Delete (typed name)
  /workspaces/$id   old link only: redirects to /ask?workspace=<id>&tab=tables|relations|sql&table=
  /workbench        staff only (beforeLoad: me.is_staff, else a 403 "Not available" page)
    /runs, /runs/$runId        traces and one trace (proposed vs approved SQL)
    /cases, /cases/$caseId     clusters, cases, the review form
    /evals, /evals/$runId, /evals/compare?base=&other=
_site             no guard: open signed in and signed out; navbar (signed in: only Open the app) and footer
  /privacy          Privacy Policy
  /terms            Terms
/design           dev only (notFound in production; the page is not in the bundle)
```

## Data in a component

```
component -> useQuery(xQuery) -> <QueryBoundary query loading errorTitle isEmpty empty>
  pending / retrying -> its skeleton (aria-busy)
  error              -> ErrorState in the component's box; Try again -> query.refetch() (this query only)
  empty              -> EmptyState
  success            -> children(data)
api client: credentials include, X-CSRFToken on writes, envelope -> data | ApiError
            (status, code, field errors, request id); 429 -> toast with Retry-After; never retries
```

## Requests in development

```
browser (localhost:FRONTEND_PORT)
  /api, /_allauth, /accounts -> Vite proxy -> API_PROXY_TARGET (http://backend:8000 on querylab-network)
  everything else            -> Vite (HMR)
```

The proxy keeps the browser's Host header (`changeOrigin: false`), so Django
sees one origin: session and CSRF cookies are same-origin, and allauth builds
OAuth callback URLs on the frontend origin. In production the static build and
the API share one domain, so the same paths work without a proxy.

## Sign-in (screens built in step 9, against allauth's headless API)

Google or GitHub only; there are no email/password accounts.

```
/login   "Continue with Google" | "Continue with GitHub"
         form POST /_allauth/browser/v1/auth/provider/redirect
           {provider, process: login, callback_url: <origin>/auth/callback, csrfmiddlewaretoken}
  -> provider -> /accounts/<provider>/login/callback/ (proxied) -> /auth/callback
  -> refetch /api/me -> /app
logout   DELETE /_allauth/browser/v1/auth/session -> /
```

The same email through Google and through GitHub is two different users;
`/api/me` says which provider (`providers`).

Every request goes through `src/lib/api` (see "Data in a component").

## Endpoints the step 9 screens will use (from backend step 1)

- `POST /api/ask {question}` returns `{sql, columns, rows, row_count, truncated, confidence, rationale, model, latency_ms}`; errors carry a stable `code` (`question_invalid`, `guard_rejected`, `query_failed`, `query_timeout`, `default_key_limit`, `llm_*`) and 429 has `Retry-After`.
- `GET /api/llm-keys`, `PUT` / `DELETE /api/llm-keys/{provider}` manage the user's own OpenAI or Gemini key (the key is never returned; only `key_last4`).

## Evals (from backend step 2, used by step 6 and 9)

- Eval runs are stored in the app database (`EvalRun`, `EvalResult`); step 6 exposes them through an API for the eval dashboard. No frontend change in step 2.

## A question, end to end (the ask page)

```
AskBox  POST /agent/runs {question, workspace}      -> navigate ?run=<id>
RunView(runId)
  useQuery(runQuery)          GET /agent/runs/{id}  (run, steps so far, `pending`)
  useRunStream(runId)         fetch GET /agent/runs/{id}/events  (SSE; cookies; Last-Event-ID)
      step   -> steps in local state, shown at once
      status -> the server closes the stream (paused or finished): fetch the stored run ONCE
      drop / timeout / agent_stream_limit -> "Reconnect" button (user action only)
  status awaiting_approval -> ApprovalCard(pending)
      Approve | Edit SQL (400 guard_rejected: reason under the editor, run stays paused) | Cancel
      success -> invalidate the run, reopen the stream (Last-Event-ID = last step seen)
  status succeeded -> ResultTable (rows first, SQL in a collapsible block; GET /result runs the SQL again), Feedback (icon-only thumbs, says what a vote does). The question is a right-aligned message bubble with no status tag; the steps list and the follow-up buttons are gone from Ask (History has the replay and an Ask again link). When the stream ends the usage numbers are invalidated (an event, not a timer)
  failed / expired / cancelled -> the error_code in plain words (describeError)
```

The stream never reopens by itself. There is no timer, no backoff and no polling anywhere in
`src/` (`no-retry.test.ts` fails the build if one appears). `API_ERRORS.md` suggests polling after
`agent_stream_limit`; this app shows the message and a Reconnect button instead (owner's rule).

## Staff

`GET /api/me` returns `is_staff`. The nav entry and the `/workbench` guard use it; the API still
answers 403 `staff_only`, which the error page shows as "Not available". The review loop is
`Draft a batch -> cases (drafted) -> case page: edit question / SQL, preview rows ->
Approve | Reject | Mark unanswerable`. A failed draft cannot be approved until the reviewer writes SQL.

## Workspaces

Every query that depends on a workspace puts its id in the key (`['schema', id]`,
`['workspace', id, ...]`). After any change `invalidateWorkspace` marks its tables, rows, schema panel
and the workspace list (sizes) stale once; nothing polls. The rows grid page size is the API's
`max_rows_per_edit` from `GET /workspaces/limits`.

## Dump import (2026-11-03; replaces the table and row editors)

Workspaces are read-only copies of a `pg_dump`. The Import dump popup (`ImportDialog` in `ImportPanel.tsx`, opened from the Schema page) is the only way to add or change tables:

```
choose file (.sql / .sql.gz, <= limits.max_dump_bytes, checked before upload)
Import ─> POST /workspaces/{id}/imports {filename, size, replace}  -> upload_url
       ─> XMLHttpRequest PUT the file to upload_url (progress bar; straight to R2)
       ─> POST .../imports/{job}/start                            -> status queued
       ─> GET  .../imports/{job} once; the user presses "Check progress" to look again (no polling, owner rule)
status succeeded -> "Imported N tables" and the workspace queries are invalidated; failed -> the server message with
"Statement N, line L." and "Nothing was changed". "Replace the tables already here" shows only when the workspace has tables.
GET .../imports -> Past imports table in the same popup (own loading / error / empty box)
```

The Run query sheet (`SqlConsole`) runs `POST /workspaces/{id}/sql`: read-only SELECT / WITH / EXPLAIN / SHOW. Removed: `TablesTab`, `TableEditor`, `ColumnsPanel`, `CreateTableDialog`, `RowsGrid`, `RowDialog`, `RelationsTab`, `contract.ts`. `/workspaces/$id` still redirects old links to Ask on Schema (or Query).

## Production build and serving

`make build-frontend-prod` runs `pnpm build` with `VITE_API_BASE_URL`, `VITE_APP_NAME` and `VITE_QUERY_STALE_TIME_MS` set in the shell; those win over `frontend/.env`. The Worker in `backend/cloudflare` uploads `dist/` as static assets. Any path except `/api/*`, `/_allauth/*` and `/accounts/*` gets a file, or `index.html` so the router can take it, without waking the backend container. A first API call after 3 idle minutes waits for the container to start (about 30 to 60 seconds measured locally).

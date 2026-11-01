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
_public           beforeLoad: signed in -> redirect /app
  /                 landing: what it is, ask / approve / measure, dataset licence
  /login            Continue with Google / GitHub (real form POSTs to allauth)
  /auth/callback    only seen when a sign-in did not finish (a finished one is moved on to /app by the guard)
_app              beforeLoad: signed out -> redirect /; adds { me }; renders AppShell (header, nav, limits chip)
  /app              home: ask button, how it works, last 3 questions (RecentRuns); skip link targets every page's <main id="main">
  /ask              ?tab=ask|schema&table=&run=&workspace=&question=   workspace picker above two sub-tabs. Ask is a chat: the run (or a short prompt) fills the page, and the composer sits at the bottom (example questions above it, send icon inside the box, Enter sends, Shift+Enter new line; question pre-fills the box: Ask again). Schema: table list on the left (a dropdown on phones), and for the chosen table its metadata, column headers (type, PK/FK) and a read-only page of its rows (GET /schema/tables/{name}/rows, manual Previous/Next)
  /settings         AI settings (no visible page header; the nav item names it): a row with title and description on the left and a QueryLab AI / Custom AI dropdown on the right (GET/PUT /llm-settings). With QueryLab AI chosen, a second row (same pattern) picks the Gemini model used on the shared key (`querylab_model`). Only for Custom AI: a table of saved keys (provider, in-use radio, model dropdown, replace, remove) or an empty state whose Add new API key button opens a modal (provider dropdown with logos from src/assets/providers, key, model)
  /history          ?status=&q=&ordering=&offset=&workspace=   your runs; rows link to /ask?run= and the replay
  /runs/$runId/replay   stored trace, one step at a time
  /workspaces       the demo and your private workspaces (no visible page header); create; per-card actions menu: Ask, Edit tables, Delete (typed name)
  /workspaces/$id   ?tab=tables|relations|sql &table=   tables, columns, key, rows, relations, SQL console
  /workbench        staff only (beforeLoad: me.is_staff, else a 403 "Not available" page)
    /runs, /runs/$runId        traces and one trace (proposed vs approved SQL)
    /cases, /cases/$caseId     clusters, cases, the review form
    /evals, /evals/$runId, /evals/compare?base=&other=
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
  status succeeded -> ResultTable (rows first, SQL in a collapsible block; GET /result runs the SQL again), Feedback (says what a vote does), Ask again / New question, collapsed step list. When the stream ends the limits chip is invalidated (an event, not a timer)
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

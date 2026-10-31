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
__root            ThemeController, TooltipProvider, Toaster
_public           beforeLoad: signed in -> redirect /app
  /                 landing (placeholder)
  /login            sign-in placeholder (Google / GitHub buttons in step 9)
  /auth/callback    OAuth return
_app              beforeLoad: signed out -> redirect /; adds { me } to the route context
  /app              workspaces (placeholder) + HealthPanel
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

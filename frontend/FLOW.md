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
  /login /signup    placeholders (0.10d)
  /verify-email     "check your email";  /verify-email/$key  confirmation
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

## Login flows (built in 0.10d, against allauth's headless API)

Email:

```
/signup  POST /_allauth/browser/v1/auth/signup {email, password}
         <- 401 + pending flow verify_email -> /verify-email (check your inbox)
email link FRONTEND_URL/verify-email/<key>
         POST /_allauth/browser/v1/auth/email/verify {key} -> signed in -> /app
/login   POST /_allauth/browser/v1/auth/login {email, password}
         400 email_password_mismatch | 400 too_many_login_attempts | 401 unverified | 200
logout   DELETE /_allauth/browser/v1/auth/session -> /
```

Google / GitHub:

```
"Continue with ..." -> form POST /_allauth/browser/v1/auth/provider/redirect
     {provider, process: login, callback_url: <origin>/auth/callback}
  -> provider -> /accounts/<provider>/login/callback/ (proxied) -> /auth/callback
  -> refetch /api/me -> /app
```

Every request goes through `src/lib/api` (see "Data in a component").

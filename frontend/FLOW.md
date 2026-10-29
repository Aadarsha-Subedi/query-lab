# Frontend: FLOW.md

## App boot

```
index.html -> src/main.tsx
  parseEnv(import.meta.env)          Zod: VITE_API_BASE_URL, VITE_APP_NAME
    invalid -> <EnvErrorScreen/>     hard stop, lists every bad key
    valid, DEV and path /design -> dynamic import DesignPage (dev only)
    valid   -> <App env/>
  <ThemeController/> keeps <html class="dark"> in sync with the theme store
  (index.html already applied the stored theme before first paint)
               (0.10c) QueryClient + Router
                 GET /api/me (TanStack Query)
                   200 -> signed in  -> (app) routes; public routes redirect to /app
                   401 -> signed out -> (public) routes; app routes redirect to /
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

Every request sends cookies (`credentials: 'include'`) and the `X-CSRFToken`
header from the `csrftoken` cookie. 429 responses show a toast with the
`Retry-After` time.

# Step 0: Foundation

**Goal:** a working skeleton that runs fully on your machine in Docker. One command starts everything. Users can sign up and log in. A health endpoint proves the backend can reach every service. The read-only boundary is tested, the design system exists, and CI is green.

**Done when:**
- `make dev` starts everything in Docker (Postgres, Redis, the Django server, the background worker and the React dev server), with hot reload, all on one Docker network, `querylab-network`.
- The backend refuses to start if any variable in `.env` is missing. No setting has a fallback value.
- A visitor can sign up with email (with verification), Google or GitHub, log in and log out. Every email is a styled HTML email with a plain-text fallback.
- Everyone must sign up; there is no anonymous demo. After signup, a user sees the Olist demo workspace (shared, read-only).
- The landing page and the app are separate route groups: signed-in users are redirected away from the landing page, and signed-out users are redirected away from the app.
- The design system (tokens and base components) is drafted and visible on a showcase page before any product UI is built.
- `GET /api/health` reports `ok` for `querylab_app`, `querylab`, the reader connection, Redis and the Huey worker.
- Tests prove the reader role can SELECT from `demo` and cannot write or create anything.
- The Olist dataset is loaded into the `demo` schema.
- CI runs lint, type checks and tests for backend and frontend on every PR.
- CLAUDE.md, FLOW.md and DECISION.md exist in `backend/` and `frontend/`.

**Local vs deployed:** locally, nothing touches Neon. Postgres and Redis run in Docker. At deploy time (step 9), only the values in `.env` change to point at Neon and hosted Redis.

Each atomic task is one small commit. **(You)** marks a task only you can do (accounts, consoles, GitHub settings).

**How changes land:** Claude works in your local `query-lab` folder and makes one local commit per atomic task, with a Conventional Commit message. Claude never pushes or touches the remote repository (no pushes, PRs or merges). You review each commit and push it yourself.

---

## 0.1 Repository and conventions

- [ ] **0.1.1** (You) Create the GitHub repo `querylab` and clone it into the local `query-lab` folder (see 0.13 for GitHub steps).
- [ ] **0.1.2** Add root files: `.gitignore` (Python, Node, `.env` but not `.env.example`), `.editorconfig`, `LICENSE` (MIT).
- [ ] **0.1.3** Create top-level folders: `backend/`, `frontend/`, `infra/` (Docker Compose, SQL), `docs/` (plans, diagrams).
- [ ] **0.1.4** Agree conventions: `main` is protected, work happens on branches, commits use Conventional Commits (`feat:`, `fix:`, `docs:`). Claude commits locally; you review and push. These go in both CLAUDE.md files (0.12).

## 0.2 Environment variables (strict, no fallbacks)

- [ ] **0.2.1** Create `backend/.env.example` listing every variable with placeholder values only. Grouped as:
      - Django: `DJANGO_SECRET_KEY`, `DJANGO_DEBUG`, `DJANGO_ALLOWED_HOSTS`, `DJANGO_SETTINGS_MODULE`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS`, `FRONTEND_URL`
      - Databases: `APP_DATABASE_URL`, `DATA_PRIMARY_URL`, `DATA_READER_URL`
      - Reader limits: `READER_STATEMENT_TIMEOUT_MS`
      - Redis and Huey: `REDIS_URL`, `HUEY_WORKERS`, `HUEY_IMMEDIATE`
      - Email: `EMAIL_BACKEND`, `EMAIL_HOST`, `EMAIL_PORT`, `EMAIL_HOST_USER`, `EMAIL_HOST_PASSWORD`, `EMAIL_USE_TLS`, `DEFAULT_FROM_EMAIL`
      - OAuth: `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`
      - Cache: `CACHE_URL`
      - Rate limits: `RATE_LIMIT_LOGIN`, `RATE_LIMIT_LOGIN_FAILED`, `RATE_LIMIT_SIGNUP`, `RATE_LIMIT_CONFIRM_EMAIL`, `RATE_LIMIT_RESET_PASSWORD`, `RATE_LIMIT_CHANGE_PASSWORD`, `THROTTLE_ANON_RATE`, `THROTTLE_USER_RATE`, `THROTTLE_ASK_RATE`, `TRUSTED_PROXY_COUNT`
      - Health: `HEALTH_CHECK_TIMEOUT_SECONDS`
      - Workspaces: `MAX_WORKSPACES_PER_USER` (3; used from step 5)
- [ ] **0.2.2** Create `frontend/.env.example` with `VITE_API_BASE_URL` and `VITE_APP_NAME`.
- [ ] **0.2.3** In settings, read every value with `django-environ` and **no default**. A missing key raises `ImproperlyConfigured` at startup, so the server never runs half-configured.
- [ ] **0.2.4** Frontend: validate `import.meta.env` with a Zod schema at startup; a missing variable shows a hard error screen and stops the app.
- [ ] **0.2.5** Test (backend and frontend): the keys the code reads exactly match the keys in `.env.example`, so the example can never drift out of date.
- [ ] **0.2.6** Rule for every later step: any new timeout, limit or size goes into `.env` and `.env.example`, never as a number in code. This rule goes in both CLAUDE.md files.

## 0.3 Local services (Docker)

- [ ] **0.3.1** `infra/docker-compose.yml` with services:
      - `postgres` (16) with a named volume,
      - `redis` (7),
      - `backend` (Django dev server, built from `backend/Dockerfile` dev stage, code bind-mounted for hot reload),
      - `worker` (background jobs, same image as `backend`),
      - `frontend` (Vite dev server, `frontend/Dockerfile.dev`, code bind-mounted, `node_modules` in a volume).
      Email isn't a container: local dev sends through your Gmail SMTP from `.env`.
- [ ] **0.3.1a** One Docker network, `querylab-network`, shared by every service. Services reach each other by service name (`postgres`, `redis`, `backend`, `frontend`).
- [ ] **0.3.1b** The Vite proxy targets `http://backend:<port>` (the service name on `querylab-network`), with the target from `.env`.
- [ ] **0.3.2** Postgres init script that creates databases `querylab_app` and `querylab`.
- [ ] **0.3.3** Compose reads its ports and passwords from the root `.env`, with no defaults in the compose file either.
- [ ] **0.3.4** Healthchecks on each container so `make dev` waits until they're ready.
- [ ] **0.3.5** There's no local replica. `DATA_READER_URL` points at the local `querylab` database using the reader role. The read-only rules are enforced by the role, so local behaviour matches production. Recorded in `backend/DECISION.md`.

## 0.4 Backend scaffold (Django + django-ninja)

- [ ] **0.4.1** Initialise `backend/` with `uv` and Python 3.12 (`pyproject.toml`, lockfile).
- [ ] **0.4.2** Runtime dependencies: `django`, `django-ninja`, `django-environ`, `psycopg[binary]`, `redis`, `huey`, `django-allauth`, `django-cors-headers`.
- [ ] **0.4.3** Dev dependencies: `pytest`, `pytest-django`, `ruff`, `mypy`, `django-stubs`, `pre-commit`.
- [ ] **0.4.4** `django-admin startproject config .`, then split settings into `config/settings/base.py`, `local.py`, `test.py`, `prod.py`.
- [ ] **0.4.5** Create the `core` app (health checks, shared utilities).
- [ ] **0.4.6** Create the `accounts` app with a custom `User` model (email as the login field, no username). **This must happen before the first migration**, because swapping the user model later is painful.
- [ ] **0.4.7** One `NinjaAPI` in `config/api.py`, mounted at `/api/`.
- [ ] **0.4.8** CORS and CSRF set for the frontend origin (values from `.env`), with session cookies shared between frontend and API.
- [ ] **0.4.9** Configure `ruff` and `mypy` (Django plugin) in `pyproject.toml`, and add `pre-commit` hooks.
- [ ] **0.4.10** Configure `pytest-django` with `config.settings.test` and a test `.env` file; add one passing smoke test.

## 0.4b Reuse the `common` app from resolve-ai and Pro-Goal

Both projects have a `backend/common` app. Querylab gets its own `common` app built from them. Rules when copying: anything tied to DRF is rewritten for django-ninja, every hard-coded number (for example `REQUEST_TIMEOUT_SECONDS = 60`, `DEFAULT_TIMEOUT = 300`) moves to `.env`, and each piece arrives with its tests.

**Copy as-is, then move constants to `.env`:**
- [ ] **0.4.11** `logger/` (request ID, request logging middleware, JSON formatters, secret redaction) and `observability/timing.py`.
- [ ] **0.4.12** `exception/domain.py` (typed app exceptions with error codes). It has no DRF dependency.
- [ ] **0.4.13** `crypto.py` (Fernet encryption with key rotation). We'll use it to encrypt users' own LLM API keys at rest. Adds `ENCRYPTION_KEYS` to `.env`.
- [ ] **0.4.14** `cache/manager.py`, with its timeout from `.env` instead of the 300-second default.
- [ ] **0.4.15** `models/` (timestamps, soft delete, bulk helpers) and `validators/` (email, disposable email, password, date) from Pro-Goal.
- [ ] **0.4.16** `email/render.py` + `templates/email/base.html` from Pro-Goal: plain text in, branded HTML plus text out. This replaces the email layout in 0.8.3a, restyled to Querylab's design system and with Querylab's link-to-button labels.
- [ ] **0.4.17** `llm/` from resolve-ai (provider interface, typed errors, OpenAI and Gemini providers, factory, fake provider for tests). It already builds a provider from a user's own key, which is exactly our bring-your-own-key model. Model lists and limits (timeout, max tokens, temperature) move to `.env`; the "app's own key" path is dropped unless we want one.

**Rewrite for django-ninja (keep the idea, not the code):**
- [ ] **0.4.18** `exception/handler.py` → a ninja exception handler that returns the same error shape.
- [ ] **0.4.19** `response/domain.py` envelope (`success`, `message`, `data`) → ninja response schemas.
- [ ] **0.4.20** `pagination/`, `order/`, `filter/` → ninja `@paginate` with a custom paginator, and `FilterSchema`.
- [ ] **0.4.21** `throttling/scoped.py` → the ninja throttles in 0.8b.

**Not now:**
- `storage/` (local/memory/R2): later, if we store files. Local disk isn't an option on Cloudflare, so only the R2 and memory backends would come over.
- `search/` (hybrid search) from resolve-ai: a strong starting point for step 8 (schema-RAG).
- `documents/` (PDF/DOCX parsing), `serializers/`, `openapi.py`, `views.py`: DRF- or ResolveAI-specific, not needed.

## 0.5 Databases and the read-only boundary

- [ ] **0.5.1** Configure Django `DATABASES`:
      - `default` → `querylab_app` (models, migrations, users, sessions),
      - `data` → `querylab` as the owner role (setup and, later, imports),
      - `data_reader` → `querylab` as `querylab_reader` (agent queries; points at the Neon replica once deployed).
- [ ] **0.5.2** Database router: models only use `default`; `allow_migrate` is true only for `default`.
- [ ] **0.5.3** `infra/sql/001_roles.sql` (idempotent, run on `querylab`):
      - create the `demo` schema,
      - create login role `querylab_reader` with `USAGE` on `demo`, `SELECT` on its tables, and default privileges for future tables,
      - `ALTER ROLE querylab_reader SET default_transaction_read_only = on`,
      - `ALTER ROLE querylab_reader SET statement_timeout` to the value of `READER_STATEMENT_TIMEOUT_MS` (passed in by the bootstrap command, not hard-coded),
      - revoke `CREATE` on schema `public` from `PUBLIC`.
- [ ] **0.5.4** Management command `bootstrap_data_db`: applies `infra/sql/*.sql` in order, fills in values from settings, and can be re-run safely.
- [ ] **0.5.5** Boundary tests as `querylab_reader`:
      - `SELECT` from a `demo` table works,
      - `INSERT`, `UPDATE`, `DELETE`, `CREATE TABLE` and `DROP` all fail,
      - a query longer than the timeout is cancelled,
      - connecting to `querylab_app` fails.

## 0.6 Demo dataset: Olist

**Why we need it.** Every signed-up user gets the Olist data as a ready-made demo workspace, so they can ask questions right away before building workspaces of their own (up to 3 each, step 5). It's shared and read-only: one copy in the `demo` schema, not a copy per user. It's also where the agent produces the traces that become our own eval set (step 6). Spider is for benchmarking only; Olist is the realistic "production" data. It's real e-commerce data (about 100k orders, 2016 to 2018) with customers, orders, items, payments, reviews, products and sellers, which gives the agent believable questions with joins, dates and messy values.

- [ ] **0.6.1** (You) Create a Kaggle account and download the Olist dataset (9 CSV files) into `infra/data/olist/`, which is git-ignored.
- [ ] **0.6.2** Record the source and its licence (CC BY-NC-SA 4.0, non-commercial) in `backend/DECISION.md` and the README.
- [ ] **0.6.3** `infra/sql/010_demo_schema.sql`: tables `customers`, `sellers`, `products`, `product_category_translation`, `orders`, `order_items`, `order_payments`, `order_reviews`, `geolocation`, with primary keys, foreign keys and indexes on foreign keys.
- [ ] **0.6.4** `COMMENT ON TABLE/COLUMN` for every table and column in plain English. Step 1 puts these into the prompt.
- [ ] **0.6.5** Management command `load_demo`: truncates, then loads each CSV with `COPY`; safe to re-run.
- [ ] **0.6.6** Translate product category names to English during load, using the translation table.
- [ ] **0.6.7** Shift all dates forward by a fixed offset so the newest order lands in a recent month. The offset is an env var (`DEMO_DATE_SHIFT_DAYS`) so eval answers stay reproducible.
- [ ] **0.6.8** Tests: row count per table matches the CSVs, no orphaned foreign keys.

## 0.7 Redis and Huey (background jobs)

**Why a job queue now.** Later steps have jobs that shouldn't block a web request: eval runs (step 2), CSV imports (step 5) and emails. Huey was chosen over Celery because it's tiny and Redis-backed, which fits the ¼ vCPU, 1 GiB Cloudflare instance.

- [ ] **0.7.1** `common/redis.py`: one Redis client built from `REDIS_URL`.
- [ ] **0.7.2** Add `huey` and configure `HUEY` in settings (Redis connection from `.env`; worker type `thread` and worker count from `HUEY_WORKERS`). In test settings, Huey runs tasks immediately (`immediate` mode, set via `.env`).
- [ ] **0.7.3** The `worker` service runs `python manage.py run_huey`.
- [ ] **0.7.4** A `common.tasks.ping` task that returns `"pong"`, used by the health check.
- [ ] **0.7.5** Test: the ping task returns `"pong"` in immediate mode.

## 0.8 Authentication (django-allauth)

- [ ] **0.8.1** Install allauth in **headless** mode (JSON API for a React app instead of Django-rendered pages), with `allauth.account`, `allauth.socialaccount`, and the Google and GitHub providers.
- [ ] **0.8.2** Account settings: login by email only, email required and unique, verification **mandatory** before first login.
- [ ] **0.8.3** Email backend from `EMAIL_BACKEND`: SMTP with your Gmail settings locally and in production (a Gmail App Password, which needs 2-step verification on the account; Gmail allows roughly 500 emails a day). Test settings use Django's in-memory backend, so tests never send real mail.
- [ ] **0.8.3a** Styled emails, built on Pro-Goal's renderer (0.4.16): one base HTML layout (`templates/email/base.html`) using the design system's colors and type, with CSS inlined at render time (`premailer`) so Gmail and Outlook show it correctly, plus a plain-text version of every email.
- [ ] **0.8.3b** Override every allauth email with that layout: email confirmation, password reset, password changed, email changed, account already exists, and login code if enabled.
- [ ] **0.8.3c** Management command `send_test_emails <address>` that sends each template once, so you can check them in your own inbox.
- [ ] **0.8.3d** Tests: each email renders both HTML and text versions, and the HTML contains no `<style>` blocks left uninlined.
- [ ] **0.8.4** Configure the Google and GitHub providers from env (`*_CLIENT_ID`, `*_CLIENT_SECRET`), with no database setup needed.
- [ ] **0.8.5** (You) Create a Google OAuth client in Google Cloud Console with redirect URI `http://localhost:<backend port>/accounts/google/login/callback/`.
- [ ] **0.8.6** (You) Create a GitHub OAuth App (Settings → Developer settings → OAuth Apps) with callback `http://localhost:<backend port>/accounts/github/login/callback/`.
- [ ] **0.8.7** Social signup links accounts by verified email, so someone who signed up with email and later uses Google with the same address lands in one account.
- [ ] **0.8.8** `GET /api/me` (ninja) returns the current user or 401. The frontend uses it to decide which routes to allow.
- [ ] **0.8.9** Tests: email signup sends a verification email, login is blocked until verified, `/api/me` returns 401 when logged out and the user when logged in.

## 0.8b Rate limits and throttling

allauth only rate-limits **its own** endpoints (login, signup, password reset, email confirmation). Our own API endpoints need django-ninja's throttling. Both count requests in Redis, so the limits hold across every server process.

- [ ] **0.8.10** Set Django's cache to Redis (`CACHE_URL` from `.env`). Both allauth and ninja store their counters there.
- [ ] **0.8.11** allauth limits via `ACCOUNT_RATE_LIMITS`, with every rate from `.env`: `RATE_LIMIT_LOGIN`, `RATE_LIMIT_LOGIN_FAILED`, `RATE_LIMIT_SIGNUP`, `RATE_LIMIT_CONFIRM_EMAIL`, `RATE_LIMIT_RESET_PASSWORD`, `RATE_LIMIT_CHANGE_PASSWORD`.
- [ ] **0.8.12** ninja throttles on the `NinjaAPI` as defaults:
      - public endpoints (signed out, keyed by IP): `AnonRateThrottle` with `THROTTLE_ANON_RATE`,
      - private endpoints (signed in, keyed by user): `AuthRateThrottle` with `THROTTLE_USER_RATE`.
- [ ] **0.8.13** A stricter named throttle for expensive endpoints (from step 1, asking a question calls the LLM): `THROTTLE_ASK_RATE`, applied per route.
- [ ] **0.8.14** Real client IP: set allauth's trusted proxy settings and ninja's IP lookup from `.env` (`TRUSTED_PROXY_COUNT`), so limits key on the visitor and not the load balancer. This is 0 locally.
- [ ] **0.8.15** Throttled requests return HTTP 429 with a `Retry-After` header; the frontend shows a toast saying when to retry.
- [ ] **0.8.16** Tests: the 6th failed login inside the window is blocked, an anonymous client gets 429 past its rate, and a signed-in user's limit is counted separately from anonymous traffic.

## 0.9 Health endpoint

- [ ] **0.9.1** `GET /api/health` returns a typed ninja schema: `{status, app_db, data_db, data_reader, redis, worker}`.
- [ ] **0.9.2** Each check (`SELECT 1`, Redis `PING`, Huey ping task) has a timeout of `HEALTH_CHECK_TIMEOUT_SECONDS`. Any failure makes `status` `degraded` and returns HTTP 503.
- [ ] **0.9.3** Tests: all-ok response and one failing dependency (mocked).

## 0.10 Frontend foundation

### 0.10a Project and tooling
- [ ] **0.10.1** Vite + React + TypeScript in `frontend/`, with `strict: true` and the `@/` path alias.
- [ ] **0.10.2** Tailwind CSS, then `shadcn/ui` init. This is only the base layer Animate UI needs: it reads `components.json` and builds on those primitives.
- [ ] **0.10.2a** Install Animate UI (`@animate-ui/react`, `motion`) and its CLI, and add Hugeicons (`@hugeicons/react` + the free icon set) as the only icon library.
- [ ] **0.10.2b** Check that Animate UI works with Vite (its docs show Next.js-style examples) before building on it. If it doesn't, stop and decide again.
- [ ] **0.10.3** ESLint, Prettier and scripts `lint`, `format`, `typecheck`.
- [ ] **0.10.4** Vitest and React Testing Library, with one smoke test.
- [ ] **0.10.5** Vite dev proxy: `/api` and `/accounts` go to the Django server, so cookies work same-origin locally.

### 0.10b Design system (before any product UI)
- [ ] **0.10.6** Draft `frontend/docs/design-system.md`: brand feel, color palette (light and dark), typography scale, spacing scale, radius, shadows, motion, iconography (Hugeicons), and voice for UI copy. **You review and approve this before any implementation.**
- [ ] **0.10.7** Implement tokens as CSS variables in `src/styles/tokens.css` and map them into the Tailwind theme and the shadcn/Animate UI theme variables.
- [ ] **0.10.8** Load fonts and define typography components (`Heading`, `Text`, `Code` for SQL).
- [ ] **0.10.9** Add the Animate UI components we know we'll need into `src/components/ui/`, so the app only imports from there: button, input, label, form, card, dialog, dropdown-menu, table, tabs, badge, toast (sonner), skeleton, avatar, separator, tooltip.
- [ ] **0.10.10** Light/dark theme toggle, with the choice stored in a Zustand store persisted to localStorage.
- [ ] **0.10.11** A dev-only `/design` route that shows every token and component in each state. It isn't included in production builds.

### 0.10c App structure, state and routing
- [ ] **0.10.12** Folder layout: `src/routes/`, `src/features/<feature>/`, `src/components/ui/`, `src/lib/`, `src/stores/`.
- [ ] **0.10.13** TanStack Query client, plus one typed `apiClient` (fetch with credentials and the CSRF header).
- [ ] **0.10.14** TanStack Router with two route groups:
      - `(public)`: landing, login, signup, verify-email, OAuth callback,
      - `(app)`: the authenticated app. For now it shows the user's workspace list with the Olist demo workspace, plus a health panel.
- [ ] **0.10.15** Route guards in the router's `beforeLoad`, using the `/api/me` query:
      - signed in and opening a public route → redirect to `/app`,
      - signed out and opening an app route → redirect to `/`.
- [ ] **0.10.16** State rule: server data (user, health, later runs) lives in TanStack Query; UI-only state (theme, sidebar, modals) lives in Zustand. This goes in `frontend/CLAUDE.md`.
- [ ] **0.10.17** Tests for both redirect rules.

### 0.10d Auth screens (using the design system)
- [ ] **0.10.18** Login page: email + password, plus "Continue with Google" and "Continue with GitHub".
- [ ] **0.10.19** Signup page with form validation (react-hook-form + Zod).
- [ ] **0.10.20** "Check your email" and email-verification landing pages.
- [ ] **0.10.21** Logout from the app shell's user menu.
- [ ] **0.10.22** A placeholder landing page (real landing content comes in step 4) and a placeholder app page that shows `/api/health`.

## 0.10e Fit for Cloudflare Containers (basic: 1/4 vCPU, 1 GiB RAM, 4 GB disk)

The backend will deploy as one Cloudflare Container on the basic instance. Containers sleep after about 10 minutes without requests, and their disk is wiped on every restart. Step 0 sets up the rules now, so nothing heavy creeps in later.

- [ ] **0.10.23** Split Python dependencies into groups: `main` (what runs in the container), `dev` (tests, lint), and `offline` (clustering, dataset building, eval benchmarks, anything with numpy/scikit-learn/torch). Only `main` goes into the image.
- [ ] **0.10.24** `backend/Dockerfile`: multi-stage build on `python:3.12-slim`, `uv sync --no-dev --group main` in the build stage, copy only the virtualenv and code into the final stage, run as a non-root user. Target image under 300 MB.
- [ ] **0.10.25** Run the web server with gunicorn + uvicorn workers. Worker count and threads come from `.env` (`WEB_CONCURRENCY`, `WEB_THREADS`). Target idle memory for web + background worker together under 500 MB, leaving headroom inside 1 GiB.
- [ ] **0.10.26** Background jobs run inside the same container as a second, light process (`run_huey`), started next to gunicorn by a tiny entrypoint script. No separate worker container, because a container with no incoming requests would go to sleep and stop consuming jobs.
- [ ] **0.10.27** Nothing is stored on local disk. Uploads stream straight into Postgres (or to R2 later if we need files), and logs go to stdout.
- [ ] **0.10.28** Heavy work never runs in the container: Spider benchmark runs, trace clustering and LoRA training run locally, in CI or on Colab, and write their results to the database.
- [ ] **0.10.29** The frontend is not in the container. It's a static Vite build served from Cloudflare (Workers static assets or Pages) on the same domain as the API, so session cookies keep working.
- [ ] **0.10.30** CI check: build the image and fail if it's over the size budget (`IMAGE_SIZE_BUDGET_MB` in the workflow).
- [ ] **0.10.31** Record all of the above in `backend/DECISION.md` as "Deployment target: Cloudflare Container, basic".

## 0.11 One-command local run (Makefile)

- [ ] **0.11.1** Everything runs through Docker Compose (0.3), so no process runner is needed.
- [ ] **0.11.2** Root `Makefile` targets:
      - `make setup`: install backend and frontend dependencies, copy `.env.example` files to `.env` if missing,
      - `make up` / `make down`: start or stop the Docker services,
      - `make dev`: `docker compose up` for every service in one terminal, with logs prefixed per service; Ctrl+C stops everything,
      - `make migrate`, `make bootstrap-db`, `make load-demo`,
      - `make test`, `make lint`, `make typecheck`.
- [ ] **0.11.3** Check that a fresh clone gets from zero to a working login with `make setup`, filling in `.env`, then `make dev`.

## 0.12 Project documents

- [ ] **0.12.1** `backend/CLAUDE.md`: commands, layout, conventions, and hard rules (no fallback settings; the agent only ever uses the reader connection; Django never migrates `querylab`; never commit secrets).
- [ ] **0.12.2** `backend/FLOW.md`: request path (Django → ninja → apps), auth flow (allauth headless), Huey job flow, and a database topology diagram.
- [ ] **0.12.3** `backend/DECISION.md`: one entry per decision (Django + ninja, two databases, schema-per-tenant, read replica, no local replica, strict env, allauth headless, Huey, Olist, uv).
- [ ] **0.12.4** `frontend/CLAUDE.md`: commands, folder layout, state rule, route guard rule, "use the design system, never ad-hoc styles".
- [ ] **0.12.5** `frontend/FLOW.md`: app boot (env check → `/api/me` → route group), login flows (email, Google, GitHub).
- [ ] **0.12.6** `frontend/DECISION.md`: Vite + React + TS, Tailwind + shadcn base + Animate UI + Hugeicons, TanStack Router + Query, Zustand, design-system-first.
- [ ] **0.12.7** Tick step 0 in the root README.

## 0.13 CI (GitHub Actions)

### What the workflow does

Claude writes and commits `.github/workflows/ci.yml` locally. The workflow only runs once **you** push it.
- [ ] **0.13.1** Backend job: start Postgres and Redis as service containers, write a CI `.env` from the workflow's `env:` block, then `uv sync`, `ruff check`, `ruff format --check`, `mypy`, `migrate`, `bootstrap_data_db`, `pytest`.
- [ ] **0.13.2** Frontend job: `npm ci`, `lint`, `typecheck`, `vitest run`, `build`.
- [ ] **0.13.3** Triggers on pull requests and pushes to `main`, with path filters per folder.

CI uses its own throwaway values (fake OAuth IDs, a dummy secret key). It never needs your real Google, GitHub or Neon credentials, so **no GitHub secrets are needed for step 0**.

### What you need to do in GitHub (You)
- [x] **0.13.4** Create the repo and link it to the local folder. Done: `Aadarsha-Subedi/query-lab`.
- On the Actions tab, **don't pick any suggested workflow** (the Django or Python templates). Our own `.github/workflows/ci.yml` runs automatically once you push it.
- [ ] **0.13.5** Check that Actions is allowed: **Settings → Actions → General → "Allow all actions"**. This is the default for new repos.
- [ ] **0.13.6** **Order matters:** push the first commits to `main` **before** creating the ruleset. A ruleset that requires pull requests also blocks the very first push to an empty `main`.
- [ ] **0.13.6a** Then **Settings → Rules → Rulesets → New branch ruleset**, enforcement **Active**, target the default branch, and set:
      - Restrict deletions: on. Block force pushes: on.
      - Require a pull request before merging: on.
          - Required approvals: **0** (GitHub never lets you approve your own PR, so 1 would lock you out as a solo developer).
          - Dismiss stale approvals, review from specific teams, review from Code Owners, approval of the most recent push, extra approval for Copilot PRs: **off**.
          - Require conversation resolution: **on** (cheap, and stops review comments being forgotten).
          - Allowed merge methods: **Squash only**, so each PR becomes one clean commit on `main`.
      - Require status checks to pass: on.
          - Require branches to be up to date: **on**.
          - Do not require status checks on creation: **on**.
          - Required checks: add `backend` and `frontend`. They only show up in the search box after the CI workflow has run once, so this part waits until after the first push.
- [ ] **0.13.6b** Working pattern from then on: Claude commits locally on a branch (for example `feat/0.4-backend-scaffold`), you push the branch and open the PR, CI runs, you squash-merge.
- [ ] **0.13.7** Optional: **Settings → Code security** → turn on Dependabot alerts and secret scanning (free for public repos).
- [ ] **0.13.8** Later, in step 9 only: add deploy secrets (Neon URLs, OAuth secrets) under **Settings → Secrets and variables → Actions**.

---

## Decisions

- Component library: Animate UI (on a shadcn base layer) + Hugeicons. Check it works with Vite first (0.10.2b).
- Design system showcase: a dev-only `/design` route, not Storybook.
- Background jobs: Huey.
- Docker: every service on one network, `querylab-network`.
- TanStack Router + TanStack Query; Gmail SMTP; signup required, Olist as a shared demo workspace, max 3 own workspaces per user.

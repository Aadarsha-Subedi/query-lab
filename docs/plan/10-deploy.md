# Step 10a: Deploy to Cloudflare

**Status:** live at `https://querylab.aadarsha-subedi.com.np` since 2026-11-03. What is left is F.7 to F.10, which need a signed-in browser or a real dump.

**Owner decisions (2026-11-03):** sub-domain `querylab.aadarsha-subedi.com.np`; the container sleeps after 3 idle minutes; the first deploy runs migrations and every management command itself; the owner creates Neon and Redis and fills in the secrets before deploying.

**Goal:** Querylab runs at `https://querylab.aadarsha-subedi.com.np`. One Worker serves the locally built frontend as static assets and forwards the backend paths to one basic Cloudflare Container (Django + Huey).

**Scope:** the deploy only. The rest of README step 10 (public read-only eval dashboard, demo script, final results) is a separate plan.

**Rules that apply:** commit locally, never push. No `.env*` file is added. Nothing is deployed and no Neon, Redis, R2 or OAuth setting is touched until the owner says go.

## What is copied from project-management and resolve-ai

- `backend/cloudflare/` with `wrangler.jsonc`, `src/index.ts`, `package.json`, `tsconfig.json`, `.gitignore`, `secrets.example.json`, and a git-ignored `secrets.json` loaded with `wrangler secret bulk`.
- `BackendContainer` (`@cloudflare/containers`) on port 8080, `basic` instance, `max_instances: 1`, region `APAC`.
- `syncSettings`: restart the container when a settings fingerprint changes; only the hash is stored.
- The Worker refuses to start the container when a setting is missing or still holds a placeholder, and names the settings, never their values.
- The Worker sets `X-Forwarded-Proto` and `X-Forwarded-For`; `TRUSTED_PROXY_COUNT=1`.
- `frontend/dist` served through `assets`, with SPA fallback for every path that is not a backend path.
- `r2-cors.json` beside the Worker, as in project-management.

## What must differ, and why

1. **Settings cannot all be Worker secrets.** The reference projects put every setting in a Worker secret. Querylab reads 138 settings and a Worker allows 128 variables (Cloudflare limits page, paid plan), so that pattern fails here. Instead:
   - `backend/cloudflare/settings.json`: non-secret tuning values, committed, bundled into the Worker.
   - `backend/cloudflare/secrets.json`: real secrets and connection strings only (about 20), git-ignored, loaded as Worker secrets.
   - `backend/cloudflare/secrets.example.json`: the committed template. The Worker reads its key names, so the secret names are not listed a second time.
2. **Three backend path groups, not two.** `run_worker_first` is `/api/*`, `/_allauth/*` and `/accounts/*`. Without `/accounts/*`, OAuth callbacks would get the React app. No frontend route uses these paths (checked). Querylab has no Django admin, so `/admin/*` is left out.
3. **Own domain instead of `workers.dev`.** `routes` with `custom_domain: true`, and `workers_dev: false` so the app has one origin. The zone is on Cloudflare nameservers and the sub-domain has no record yet (checked with `dig`); wrangler creates the DNS record and certificate.
4. **`.dockerignore` must exclude `cloudflare`.** The Worker folder sits inside the build context and the Dockerfile runs `COPY . .`. Without this, `secrets.json` would be baked into the image, along with `node_modules`.
5. **Build arguments.** The Dockerfile requires `UV_HTTP_TIMEOUT` and `UV_CONCURRENT_DOWNLOADS`; they go in `image_vars` in `wrangler.jsonc`.
6. **The first deploy seeds itself.** `load_demo` needs the Olist CSVs and `bootstrap_data_db` needs `infra/sql`, and neither is in the image or its build context. `make deploy-first` copies both into `backend/.first-deploy/` (git-ignored) for that one image build, and the entrypoint runs `migrate`, `bootstrap_data_db` and `load_demo` when that folder exists. A plain `make deploy` removes the folder, so the same entrypoint then starts web and worker only, with no file to edit back. That one image is 425 MB, over the 400 MB budget, which is accepted because it lives for minutes; CI never builds it.
7. **`sleepAfter` is 3 minutes (owner).** Container activity counts requests only, so a running job does not keep it awake. `make keep-awake` covers the seed. A long dump import with no request arriving can still be killed; the job then shows `dump_interrupted` and the user retries. The 50 MB measurement (F.9) shows whether this happens in practice.

## Known behaviour to accept

- `expire_stale_runs` and queued jobs run only while the container is awake. A stale run expires on the next wake, which is harmless.
- Redis: managed services usually offer database 0 only, so `REDIS_URL` and `CACHE_URL` both use `/0` over TLS (`rediss://`). Keys do not collide (Huey, cache and `agent:` keys have their own prefixes), and `cache.clear()` is called only in tests.
- Redis command use: Huey's workers poll Redis while the container is awake, roughly a couple of commands a second (estimate, not measured). On a free tier with a monthly command limit, check usage after the first week.

## Measured (2026-11-03, 1 GiB and 0.25 CPU, throwaway Postgres and Redis on the same machine)

- Image files: 305 MB normal, 425 MB first deploy. No `cloudflare` folder inside.
- Seed (migrate, bootstrap, load 99,441 orders): 135 seconds from container start. Neon over the network will be slower. Peak memory about 375 MiB.
- With 1 gunicorn worker (4 threads) and 2 Huey workers, the owner's choice to match the other projects: cold start to `/api/health` 200 took 33 and 55 seconds on two runs; idle memory 249 MiB (budget 500). With 2 gunicorn workers: 40 seconds, 363 MiB.
- A stop signal shuts the container down in 1 second.

## First deploy on real Neon (2026-11-03)

- `bootstrap_data_db` failed at first: on Postgres 18, a non-superuser may not even name `NOSUPERUSER` in `ALTER ROLE` ("Only roles with the SUPERUSER attribute may change the SUPERUSER attribute"). The clause is gone from `infra/sql/001_roles.sql`. Local Postgres never showed this because the local owner is a superuser.
- With the fix, the seed took about 4.5 minutes through Neon's pooled endpoint from container start.
- `querylab_reader` checked directly on the replica: not a superuser, no extra attributes, member of nothing, and `CREATE TABLE` is refused, also after `SET default_transaction_read_only = off` (the replica itself refuses, so this does not prove the grants; the local isolation tests do).
- The container library pings with `Host: ping`, so each start logs a few harmless `DisallowedHost` errors.

## Atomic steps

### A. Container (mine)

- [x] A.1 `backend/.dockerignore`: add `cloudflare` and `postman`.
- [x] A.2 `backend/entrypoint.sh`: web first, seed when `.first-deploy` exists, then Huey; the reference's `trap` so a stop signal reaches both, and kill the survivor when one exits.
- [x] A.3 Build the `prod` target and check: size under the 400 MB budget with CI's `du` method, no `cloudflare` folder inside.
- [x] A.4 Run it limited to 1 GiB and 0.25 CPU with `settings.json` plus throwaway secrets and the compose databases; `GET /api/health` answers 200 and idle memory stays under 500 MB.

### B. Worker folder (mine)

- [x] B.1 `backend/cloudflare/package.json`, `tsconfig.json`, `.gitignore`, pnpm lockfile (same versions as the references: `@cloudflare/containers` ^0.3.7, `wrangler` ^4.149.0).
- [x] B.2 `wrangler.jsonc`: name `querylab`, `compatibility_date` `2026-10-01`, container (`../Dockerfile`, context `..`, `basic`, 1 instance, `APAC`, `image_vars`), assets with the three backend paths, observability, Durable Object binding, route, `workers_dev: false`.
- [x] B.3 `settings.json`: every non-secret key, starting from `.env.example` with production values: `DJANGO_SETTINGS_MODULE=config.settings.prod`, `DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS`, `CSRF_TRUSTED_ORIGINS`, `CORS_ALLOWED_ORIGINS` and `FRONTEND_URL` on the new domain, `TRUSTED_PROXY_COUNT=1`, `LOG_FORMAT=json`, `PORT=8080`, `HUEY_IMMEDIATE=false`, `EVAL_OPENAI_API_KEY` empty (Cloudflare refuses an empty secret).
- [x] B.4 `secrets.example.json` with `FILL_ME` values: `DJANGO_SECRET_KEY`, `APP_DATABASE_URL`, `DATA_PRIMARY_URL`, `DATA_READER_URL`, `WORKSPACE_PRIMARY_CONNINFO`, `WORKSPACE_READER_CONNINFO`, `MASTER_WORKSPACE_SECRET`, `ENCRYPTION_KEYS`, `REDIS_URL`, `CACHE_URL`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET`, `LLM_DEFAULT_GEMINI_API_KEY`, `R2_ENDPOINT_URL`, `R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_BUCKET_NAME`, `R2_PUBLIC_BASE_URL`.
- [x] B.5 `secrets.json`: the same file for the owner to fill in. Confirm with `git check-ignore` that it is ignored before it is created. Add it to the root `.gitignore` too.
- [x] B.6 `src/index.ts`: reference Worker, with container env = `settings.json` + the secrets named by `secrets.example.json`, and `sleepAfter = "3m"`.
- [x] B.7 `r2-cors.json`: `PUT`, `GET` and `HEAD` from the new origin, `ETag` exposed.
- [x] B.8 `backend/core/tests/test_env.py`: `settings.json` keys + `secrets.example.json` keys equal the keys the code reads, with no overlap. Later settings cannot be forgotten in production.
- [x] B.9 `pnpm types` and `wrangler deploy --dry-run` pass.

### C. Build and operate scripts (mine)

- [x] C.1 Makefile `build-frontend-prod`: `pnpm build` with `VITE_API_BASE_URL`, `VITE_APP_NAME` and `VITE_QUERY_STALE_TIME_MS` given in the shell. They override `frontend/.env`, so no `.env.production` is needed.
- [x] C.2 Makefile `deploy`: `build-frontend-prod`, then `wrangler deploy`.
- [x] C.3 Makefile `deploy-first` and `keep-awake`. For later migrations, `backend/cloudflare/prod-manage.sh` and Makefile `prod-manage ARGS=...`: run the prod image with `settings.json` + `secrets.json` in the environment (process substitution, no file written), mounting `infra/sql` and `infra/data/olist` read-only.
- [x] C.4 Check the frontend build holds the production origin and not `localhost`.

### D. Documentation (mine)

- [x] D.1 `backend/CLAUDE.md`: commands, and the rule that a new setting goes in `.env.example`, `.env.test`, and `settings.json` or the secrets template.
- [x] D.2 `backend/FLOW.md`: request path (browser, Worker, assets or container) and the deploy flow.
- [x] D.3 `backend/DECISION.md`: the differences listed above, and correct the stale deployment section (300 MB budget, frontend hosting).
- [x] D.4 `frontend/CLAUDE.md`, `FLOW.md`, `DECISION.md`: production build values and same-origin serving.
- [x] D.5 README: status, and a deploy section with the owner runbook (part E).
- [x] D.6 One local commit per group (A, B, C, D). No push.

### E. Owner tasks before deploy (yours)

- [ ] E.1 Neon: copy direct connection strings for `querylab_app` and `querylab`, the `querylab-replica` string for the reader role, and pooled hosts for `WORKSPACE_*_CONNINFO` (with `sslmode=require`).
- [ ] E.2 Redis: create a TLS database in Asia Pacific and fill `REDIS_URL` and `CACHE_URL`.
- [ ] E.3 GitHub: create a new OAuth app for production (a GitHub OAuth app has one callback URL). Callback: `https://querylab.aadarsha-subedi.com.np/accounts/github/login/callback/`.
- [ ] E.4 Google: add origin `https://querylab.aadarsha-subedi.com.np` and redirect URI `https://querylab.aadarsha-subedi.com.np/accounts/google/login/callback/`.
- [ ] E.5 R2: create the bucket, then `wrangler r2 bucket cors set <bucket> --file r2-cors.json`, add a 1-day lifecycle rule on `dumps/`, and create an API token for that bucket.
- [ ] E.6 Generate new production values for `DJANGO_SECRET_KEY`, `MASTER_WORKSPACE_SECRET` and `ENCRYPTION_KEYS`; do not reuse the local ones. Keep `MASTER_WORKSPACE_SECRET` and `ENCRYPTION_KEYS` safe: losing them breaks workspace passwords and saved API keys.
- [ ] E.7 Fill in `backend/cloudflare/secrets.json`.

### F. First deploy (after your go, run by whichever of us you choose)

- [x] F.1 `wrangler whoami`: the logged-in account owns the `aadarsha-subedi.com.np` zone.
- [x] F.2 `make deploy-first`. Until secrets exist, the Worker answers 500 and names what is missing, so no half-configured app is public.
- [x] F.3 `pnpm wrangler secret bulk secrets.json` in `backend/cloudflare`.
- [x] F.4 `make keep-awake` in a second terminal. Watch the container logs in the dashboard until `Demo data loaded.` appears. `/api/health` may answer 503 until the databases are ready.
- [x] F.5 Straight after: stop `keep-awake` and run `make deploy`. Until then every container start repeats the load.
- [x] F.6 Smoke test: `GET /api/health` is 200; the landing page and a deep link load.
- [ ] F.7 Sign in with Google and with GitHub.
- [ ] F.8 Ask a demo question: the agent reads through the replica, the SSE stream stays open, approve and replay work.
- [ ] F.9 Create a workspace and import a real dump through R2 (closes D.10 of the dump import plan and 5.9.7's real-Neon checks), then measure a 50 MB dump (closes D.11) and tune `DUMP_STATEMENT_TIMEOUT_MS`.
- [ ] F.10 Let the container sleep and record the real cold start.

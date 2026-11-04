# Querylab

> Ask your database in plain English, then measure how well the AI answered.

**Status:** Complete · Live at [querylab.aadarsha-subedi.com.np](https://querylab.aadarsha-subedi.com.np)

Querylab is a text-to-SQL analyst agent with its own evaluation and fine-tuning loop. Visitors ask questions about a database in plain English and get a result table, the exact SQL that ran, and a replayable trace of how the agent got there. Behind it, a staff workbench turns those traces into an eval set, scores every model version, and can benchmark a LoRA fine-tuned model against its base.

## Features

- **Plan / act / reflect agent** — typed tools, Redis state, an approval checkpoint before any SQL runs, step logs and one-step-at-a-time replay
- **SQL guard** — sqlglot parse; one `SELECT` on known tables; runs only on a read-only role with a statement timeout
- **Shared demo + private workspaces** — every user gets the Olist demo; up to 3 private workspaces, each a read-only copy of a `pg_dump` (≤ 50 MB)
- **Bring your own LLM key** — shared Mistral key with a daily limit, or your encrypted Gemini / OpenAI key
- **Trace-driven evals** — staff workbench clusters demo runs, drafts expected SQL, hand-reviews cases, scores models and gates regressions
- **Offline LoRA loop** — build an instruction dataset, train on Colab, score predictions with the same harness (never in the production container)

## Baseline scores

Execution accuracy: a question is correct when the model's SQL returns the same rows as the reference. Measured on one direct question-to-SQL call with `gemini-3.5-flash-lite`, prompt `v1`, on 2026-10-31. Numbers live in [`backend/DECISION.md`](backend/DECISION.md) and on the landing page.

| Target | Score | Detail |
|--------|-------|--------|
| Olist golden set | **95.1%** | 39 of 41 questions |
| Spider held-out | **86.6%** | 362 of 418 scored; 84.2% if the 12 failed provider calls count as wrong |

## Stack

| Layer | Choice |
|-------|--------|
| API | Django 6 + django-ninja, Python 3.12 (`uv`) |
| UI | Vite, React 19, TypeScript, TanStack Router + Query, Tailwind 4 |
| Data | Postgres (app DB + data DB), Redis, Huey |
| Auth | django-allauth headless — Google and GitHub only |
| Hosting | One Cloudflare Worker (static frontend + container proxy) and one basic Container |

## Quick start

Needs Docker, and on the host: `uv` (backend editor tooling) and `pnpm` (frontend).

```bash
make setup          # copies .env examples; uv sync + pnpm install
# Fill in backend/.env: Google/GitHub OAuth apps, LLM_DEFAULT_API_KEY (Mistral), …
# Download Olist CSVs into infra/data/olist/ (see Demo data)

make up             # or `make dev` for foreground logs
make migrate
make bootstrap-db   # demo schema, reader role, grants
make load-demo      # Olist into the shared demo workspace
```

Open `http://localhost:3000`. Sign in with Google or GitHub (callback URLs must include `http://localhost:3000/accounts/<provider>/login/callback/`).

Useful checks:

| Task | Command |
|------|---------|
| Tests | `make test` |
| Lint / types / format | `make lint` · `make typecheck` · `make format` |
| Refresh OpenAPI | `make openapi` (then `cd frontend && pnpm gen:api`) |
| Eval (dev container only) | `make eval ARGS="run_eval --target olist --model …"` |

## Layout

```
backend/     Django API, agent, workspaces, evals, finetune tooling, Cloudflare Worker
frontend/    React app (same origin as the API in production)
infra/       Compose, Postgres init, data-DB SQL, Olist/Spider/finetune data dirs
docs/plan/   Milestone plans (foundation → deploy)
```

Deeper notes: [`backend/CLAUDE.md`](backend/CLAUDE.md), [`frontend/CLAUDE.md`](frontend/CLAUDE.md), flows in `FLOW.md`, decisions in `DECISION.md`, errors in [`backend/API_ERRORS.md`](backend/API_ERRORS.md), Postman in [`backend/postman/`](backend/postman/).

## Demo data

Every signed-up user gets a shared, read-only demo workspace built from the
[Olist Brazilian e-commerce dataset](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce)
(about 100k orders, 2016 to 2018, dates shifted forward to recent months).
Licence: [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) (non-commercial).
The CSVs go into `infra/data/olist/` and are never committed.

## Deploy

Production is one Cloudflare Worker at `https://querylab.aadarsha-subedi.com.np`: it serves the frontend build and forwards `/api`, `/_allauth` and `/accounts` to one basic container. Worker sources live in `backend/cloudflare/`. The full runbook is in [`docs/plan/10-deploy.md`](docs/plan/10-deploy.md).

Before the first deploy:

1. Neon, Asia Pacific: databases `querylab_app` and `querylab`, plus a read replica of `querylab`.
2. Redis, Asia Pacific, with TLS.
3. GitHub OAuth app with callback `https://querylab.aadarsha-subedi.com.np/accounts/github/login/callback/`. In Google, add that origin and `.../accounts/google/login/callback/`.
4. An R2 bucket: from `backend/cloudflare`, `pnpm wrangler r2 bucket cors set <bucket> --file r2-cors.json`; 1-day lifecycle on `dumps/`; API token for that bucket.
5. Fill `backend/cloudflare/secrets.json` (git-ignored):

| Key | Value |
|-----|-------|
| `APP_DATABASE_URL`, `DATA_PRIMARY_URL` | Neon direct (non-pooled) URLs for `querylab_app` and `querylab`, with `?sslmode=require` |
| `DATA_READER_URL` | `postgres://querylab_reader:<password>@<replica host>/querylab?sslmode=require`; `bootstrap_data_db` creates the role with this password |
| `WORKSPACE_PRIMARY_CONNINFO`, `WORKSPACE_READER_CONNINFO` | `host=<pooled host> port=5432 dbname=querylab sslmode=require`, for primary and replica |
| `REDIS_URL`, `CACHE_URL` | Same `rediss://...` URL, database 0 |
| `DJANGO_SECRET_KEY`, `MASTER_WORKSPACE_SECRET` | New long random strings (`openssl rand -base64 48`), not the local ones |
| `ENCRYPTION_KEYS` | A new Fernet key. Losing this or the master secret breaks saved API keys and workspace passwords |
| `GOOGLE_*`, `GITHUB_*`, `LLM_DEFAULT_API_KEY` | From the providers (`LLM_DEFAULT_API_KEY` is a Mistral key) |
| `R2_*` | `R2_ENDPOINT_URL` is `https://<account id>.r2.cloudflarestorage.com` |

First deploy, in order:

```bash
make deploy-first
cd backend/cloudflare && pnpm wrangler secret bulk secrets.json
make keep-awake
```

Watch the container logs until `Demo data loaded.` appears, stop `keep-awake`, then replace the seeding image (it would reload on every start):

```bash
make deploy
```

Later deploys are `make deploy`. For a new migration: `make prod-manage ARGS="migrate"` first.

## What was built

| # | Milestone | Notes |
|---|-----------|--------|
| 0 | Foundation | Repo, Compose, two DBs + reader, Redis + Huey, OAuth, CI, design system |
| 1 | Text-to-SQL core | Schema prompt, guard, reader run, confidence / check label |
| 2 | Eval harness | Spider held-out split, execution accuracy, Gemini baseline |
| 3 | Agent | Plan / act / reflect, tools, Redis state, approval, replay |
| 4 | Analyst API | Ask, history, approve / edit / cancel, schema browser, result rows |
| 5 | User workspaces | Demo + up to 3 private schemas from a dump; SQL console; quotas |
| 6 | Trace-driven evals | Clustering, LLM-drafted gold, review, gate |
| 7 | LoRA fine-tune *(stretch)* | Dataset builder + Colab notebooks + `--predictions` scoring; Colab training results are offline |
| 9 | Frontend | Landing, ask / schema / workspaces, history, replay, settings, staff workbench |
| 10 | Deploy | Live on Cloudflare Container + Worker |

Step 8 (schema-RAG + semantic cache) stayed optional and was not built. Milestone plans are under [`docs/plan/`](docs/plan/).

## License

MIT — see [LICENSE](LICENSE). Demo data remains CC BY-NC-SA 4.0 (non-commercial).

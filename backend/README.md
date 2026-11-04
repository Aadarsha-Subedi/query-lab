# Backend

Django + django-ninja API for Querylab. Python 3.12, managed with `uv`. Runs in Docker Compose locally; deploys as one Cloudflare Container behind the Worker in `cloudflare/`.

## Run it

From the **repo root** (everything goes through Compose):

```bash
make setup && make up
make migrate && make bootstrap-db && make load-demo
```

API: `http://localhost:8000` (`/api/health`, `/api/docs`). The UI proxies here from port 3000.

| Task | Command |
|------|---------|
| Tests | `make test-backend` |
| Lint / format / types | `make lint-backend` · `make format` · `make typecheck-backend` |
| OpenAPI → `openapi.json` | `make openapi` |
| Evals (dev only) | `make eval ARGS="…"` |
| Deploy | `make deploy` / `make deploy-first` (see root README) |

## Layout

```
config/       settings, the one NinjaAPI, urls
core/         health, DB router, demo loader, bootstrap
accounts/     User, /api/me, OAuth (Google / GitHub only)
ask/          one-shot text-to-SQL, schema browser, LLM keys
agent/        plan / act / reflect loop, tools, SSE, replay
workspaces/   demo + private schemas, dump import (R2), read-only SQL
evals/        harness, Olist / Spider / traces targets, gate
finetune/     offline dataset + Colab notebooks (never in prod)
common/       envelope, errors, throttles, LLM providers, crypto
cloudflare/   Worker + container deploy (secrets git-ignored)
postman/      collection + local environment
```

## Docs in this folder

| File | What it is |
|------|------------|
| [`CLAUDE.md`](CLAUDE.md) | Commands, layout, hard rules |
| [`FLOW.md`](FLOW.md) | Request paths, agent / workspace / workbench contracts |
| [`DECISION.md`](DECISION.md) | Why each choice, baseline numbers |
| [`API_ERRORS.md`](API_ERRORS.md) | Every error code and HTTP status |
| [`openapi.json`](openapi.json) | Contract the frontend generates types from |
| [`postman/`](postman/) | Manual API checks |

Sign-in is Google or GitHub only. Agent SQL always runs on a reader role after the guard. Workspaces are read-only copies of a dump — structure and data change only through the import job.

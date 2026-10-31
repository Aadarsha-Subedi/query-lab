# Backend: CLAUDE.md

Django + django-ninja API for Querylab. Python 3.12, managed with `uv`.
Runs in Docker Compose locally; deploys as one Cloudflare Container (basic:
1/4 vCPU, 1 GiB RAM, 4 GB disk).

## Commands

Run from the repo root (everything goes through Docker Compose):

| Task | Command |
|------|---------|
| Start everything (logs in this terminal) | `make dev` |
| Start in the background / stop | `make up` / `make down` |
| Apply Django migrations (`querylab_app`) | `make migrate` |
| Create the demo schema, reader role and grants (`querylab`) | `make bootstrap-db` |
| Load the Olist CSVs into `demo` | `make load-demo` |
| Tests (re-bootstraps the test reader role first) | `make test-backend` |
| Lint / format | `make lint-backend` / `make format` |
| Types (on the host) | `make typecheck-backend` |

Lint and types run on the host (`uv sync`, then `uv run ruff ...` and
`uv run mypy .`); the dev image has only runtime + `test` dependencies. Tests
need the compose Postgres and Redis, so they run in the container.

## Layout

```
config/            settings/{base,local,test,prod}.py, api.py (the one NinjaAPI), urls.py,
                   urls_local.py (urls.py + /dev/, local only), gunicorn.py
core/              health checks, DB router, data-DB SQL (datadb.py), Olist loader (demo.py),
                   commands bootstrap_data_db and load_demo
ask/               text-to-SQL (step 1): schema.py, prompt.py, guard.py (sqlglot), runner.py,
                   confidence.py, keys.py (own/default LLM key), service.py, api.py (/ask, /llm-keys),
                   models UserLLMKey and AskLog
accounts/          User model (one per Google/GitHub account; email not unique), /api/me,
                   dev.py + templates/dev (dev-only OAuth test page, see FLOW.md)
common/            shared building blocks (from resolve-ai / Pro-Goal, rewritten for ninja):
  exception/       typed AppExceptions + ninja handlers (error envelope)
  response/        success/error envelope schemas
  pagination/ order/ filter/   ninja paginator, ?ordering= allowlist, FilterSchemas
  throttling/      AnonThrottle, UserThrottle, AskThrottle (rates from settings)
  logger/ observability/       request id, request logging, JSON logs, Server-Timing
  email/utils.py   normalize_email, mask_email
  llm/             provider interface, OpenAI + Gemini, fake provider (bring-your-own-key)
  models/ validators/ cache/ crypto.py redis.py tasks.py
postman/           Postman collection + local environment for every endpoint
../infra/sql/      SQL applied to the data DB by bootstrap_data_db, in numeric order
```

## Conventions

- `main` is protected; work happens on branches; Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Claude commits locally only. It never pushes, opens PRs or merges; Aadarsha reviews each commit and pushes.
- One small commit per atomic task.
- Every new or changed endpoint is added to `postman/collection.json` in the same commit.
- Every endpoint (except `/api/health`) answers in the envelope from `common/response/domain.py`; errors raise an `AppException` subclass.
- New dependencies: runtime ones only if they fit the container budget (image < 300 MB, idle web + worker < 500 MB). Test tools go in `test`, lint/type/hook tools in `lint` (host and CI only), heavy tools in `offline`.

## Hard rules

0. **Sign-in is Google or GitHub only** (`SOCIALACCOUNT_ONLY`). No email/password accounts and no outgoing email. Identity is the provider account: never look users up, merge or link them by email.

1. **No fallback settings.** Every setting is read with `env.<type>("KEY")` and no default. A missing key stops startup. Never add `default=`.
2. **No magic numbers.** Any new timeout, limit, size or rate goes into `.env.example`, `.env.test` and settings. `core/tests/test_env.py` fails if the code and `.env.example` disagree.
3. **The agent only ever uses the reader connection** (`data_reader` / `querylab_reader`). Never run agent SQL on `default` or `data`.
4. **Django never migrates `querylab`.** `core.routers.AppOnlyRouter` allows migrations on `default` only; the data DB schema lives in `infra/sql/` and is applied by `bootstrap_data_db`.
5. **Never commit secrets.** `.env` files are git-ignored; only `.env.example` and the throwaway `.env.test` are committed. `infra/data/` (the Olist CSVs) is never committed.
6. **No local disk writes** in app code: logs go to stdout, uploads stream to Postgres (or R2 later).
7. Don't skip or disable failing tests; fix the cause.
8. **SQL from an LLM is untrusted.** It runs only after `ask.guard.check` and only through `ask.runner.run`, which uses the reader connection. Never execute model SQL any other way, never loosen the guard to make a test pass, and never put result rows into a prompt or an `AskLog`.
9. **Keys:** a user's LLM key is stored only encrypted (`common.crypto`) and never returned, logged or echoed (only its last four characters). QueryLab's default key lives only in `.env` (`LLM_DEFAULT_GEMINI_API_KEY`).
10. **`ask` settings** (`ASK_*`, `CONFIDENCE_*`, `LLM_DEFAULT_*`) follow rule 2: add new ones to `.env.example`, `.env.test` and settings together.

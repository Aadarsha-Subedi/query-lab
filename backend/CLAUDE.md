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
| Eval commands in the dev container (step 2) | `make eval ARGS="run_eval --target olist --model gemini-3.5-flash"` |
| Agent eval (step 3, Olist only, up to AGENT_MAX_LLM_CALLS calls per question) | `make eval ARGS="run_eval --target olist --runner agent --model gemini-3.5-flash-lite --yes"` |
| Does the confidence score separate right from wrong? | `make eval ARGS="confidence_report --run <id>"` |
| Rewrite `backend/openapi.json` after any endpoint change (CI and a test fail when it is stale) | `make openapi` |
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
                   keys.py (own/default LLM key), service.py, api.py (/ask, /llm-keys),
                   schema_api.py (/schema, /schema/tables/{name}: the schema browser, step 4),
                   models UserLLMKey and AskLog
agent/             the agent (step 3): loop.py (plan, act, pause, execute, reflect), tools/ (one file
                   per typed tool + the registry), prompts.py (v2-agent), state.py (Redis state, lock,
                   rebuild), trace.py (AgentStep writer), events.py + stream.py (SSE), service.py
                   (create, approve/edit/cancel, expiry), tasks.py (Huey), confidence.py, api.py
                   (/agent/runs..., /agent/limits), models AgentRun and AgentStep.
                   Step 4: result.py (rows of a finished run, by re-running its stored SQL),
                   limits.py (what is left before a limit), `pending` block in schemas.py,
                   history filters in api.py
evals/             eval harness (step 2, agent runner step 3): compare.py (execution accuracy), runner.py,
                   agent_runner.py, confidence_analysis.py, scoring.py,
                   targets/{olist,spider}.py + olist_golden.jsonl + spider_split.json,
                   commands run_eval, eval_report, review_golden, check_spider, confidence_report,
                   models EvalRun and EvalResult
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
openapi.json       the API contract the frontend generates its types from (`make openapi`)
API_ERRORS.md      every error code, its HTTP status and what the screen should do
../infra/sql/      SQL applied to the data DB by bootstrap_data_db, in numeric order
```

## Conventions

- `main` is protected; work happens on branches; Conventional Commits (`feat:`, `fix:`, `docs:`, `chore:`, `test:`).
- Claude commits locally only. It never pushes, opens PRs or merges; Aadarsha reviews each commit and pushes.
- One small commit per atomic task.
- Every new or changed endpoint is added to `postman/collection.json` in the same commit, and `make openapi` is re-run so `openapi.json` matches. New error codes go in `API_ERRORS.md` (a test checks it).
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
11. **Evals run in the dev container, never in the production one** (`make eval ARGS=...`). Gold SQL and gold rows never reach a prompt, and `EvalResult` stores SQL, never result rows. Spider is read from `EVAL_SPIDER_DIR` and never committed or put in the image. The Olist target goes through the real guard and reader connection; Spider runs on a read-only SQLite file (`mode=ro`, `query_only`, a read-only authorizer). New `EVAL_*` settings follow rule 2 (`.env.example`, `.env.test`, settings together).
12. **Agent execution happens only in the loop, after approval** (step 3). The model's tools (`agent/tools/`) never import `ask.runner` or a database connection; `propose_sql` only guards and stores SQL, and `agent/loop.py` alone calls `runner.run`, for SQL a person approved, edited (and the guard accepted) or the eval harness auto-approved (`actor=eval`). Never add a tool that executes SQL, never skip the pause, and never store or send result rows beyond the preview capped by `AGENT_RESULT_PREVIEW_ROWS` and `AGENT_STEP_OUTPUT_MAX_CHARS`. Run state in Redis is a cache: the stored `AgentStep` rows are the source of truth, and a paused run must stay rebuildable from them. The one other place SQL runs is `/result` (rule 14).
13. **`agent` settings** (`AGENT_*`, `CONFIDENCE_*`, `THROTTLE_AGENT_RATE`) follow rule 2. The confidence number is hidden (`confidence: null`) until `CONFIDENCE_SHOW_SCORE` is set after the offline analysis passes (DECISION.md); responses always carry the `check` label.
14. **`GET /api/agent/runs/{id}/result` re-runs stored SQL and nothing else** (step 4). It is the one place SQL runs outside the agent loop, so it is narrow: the SQL is always the run's own `final_sql` (never anything from the request), only for a `succeeded` run the caller owns, through `guard.check` again and `runner.run` on the reader connection, behind `ResultThrottle`. It writes nothing: no step, no change to the run, no rows kept (rule 12 still holds: rows are never stored). `GET /api/schema` reads the cached `ask.schema.get_schema` and has no write path; sample values show only when `SCHEMA_API_INCLUDE_SAMPLES` is on.
15. **`SCHEMA_API_*` and `THROTTLE_RESULT_RATE`** follow rule 2. A new endpoint also needs: its error statuses declared with `errors(...)`, a Postman request, a regenerated `openapi.json`, and any new `AppException` code in `API_ERRORS.md`. Every 429 carries `retry_after_seconds` (null when waiting does not help).

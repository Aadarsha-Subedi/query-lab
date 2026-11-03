# Querylab: one command per task. Everything runs in Docker Compose.

COMPOSE := docker compose --project-directory . --env-file .env -f infra/docker-compose.yml
BACKEND := $(COMPOSE) exec backend
FRONTEND := $(COMPOSE) exec frontend

.PHONY: setup up down dev logs migrate bootstrap-db load-demo createsuperuser \
        eval eval-gate openapi test test-backend test-frontend lint lint-backend lint-frontend \
        typecheck typecheck-backend typecheck-frontend format \
        build-frontend-prod deploy deploy-first keep-awake prod-manage

PROD_ORIGIN := https://querylab.aadarsha-subedi.com.np

## setup: install local dependencies (for editors) and create .env files from the examples
setup:
	@for f in .env backend/.env frontend/.env; do \
		if [ ! -f $$f ]; then cp $$f.example $$f; echo "created $$f (fill it in)"; fi; \
	done
	cd backend && uv sync
	cd frontend && pnpm install

## up / down: start or stop the services in the background
up:
	$(COMPOSE) up --build --detach --wait

down:
	$(COMPOSE) down

## dev: every service in this terminal, logs prefixed per service; Ctrl+C stops all
dev:
	$(COMPOSE) up --build

logs:
	$(COMPOSE) logs --follow

migrate:
	$(BACKEND) python manage.py migrate

bootstrap-db:
	$(BACKEND) python manage.py bootstrap_data_db

load-demo:
	$(BACKEND) python manage.py load_demo

createsuperuser:
	$(BACKEND) python manage.py createsuperuser

## eval: run an evals command in the dev container, e.g.
##   make eval ARGS="run_eval --target olist --model gemini-3.5-flash"
eval:
	$(BACKEND) python manage.py $(ARGS)

## eval-gate: the regression gate on the Olist golden set and the approved trace cases.
## Each run is compared with the latest earlier run of the same target, runner and prompt
## version, and the command fails when accuracy drops by more than EVAL_GATE_MAX_DROP_POINTS.
## Needs the live key, so it runs in the dev container only:
##   make eval-gate MODEL=gemini-3.5-flash RUNNER=ask
MODEL ?= gemini-3.5-flash
RUNNER ?= ask
eval-gate:
	$(BACKEND) python manage.py run_eval --target olist --model $(MODEL) --runner $(RUNNER) --yes --gate
	$(BACKEND) python manage.py run_eval --target traces --model $(MODEL) --runner $(RUNNER) --yes --gate

## openapi: write backend/openapi.json from the one NinjaAPI (sorted, so diffs are small).
## CI regenerates it and fails when it differs from the committed file.
openapi:
	$(BACKEND) python manage.py export_openapi

## test: backend tests run in the container against the compose postgres/redis.
## lint and typecheck run on the host (the dev image has no lint tools).
test: test-backend test-frontend

test-backend:
	$(BACKEND) sh -c "DJANGO_SETTINGS_MODULE=config.settings.test python manage.py bootstrap_data_db && pytest"

test-frontend:
	$(FRONTEND) pnpm test

lint: lint-backend lint-frontend

lint-backend:
	cd backend && uv run ruff check . && uv run ruff format --check .

lint-frontend:
	cd frontend && pnpm lint

typecheck: typecheck-backend typecheck-frontend

typecheck-backend:
	cd backend && uv run mypy .

typecheck-frontend:
	cd frontend && pnpm typecheck

format:
	cd backend && uv run ruff format . && uv run ruff check --fix .
	cd frontend && pnpm format

## build-frontend-prod: static files for the Worker. Shell variables win over frontend/.env.
build-frontend-prod:
	cd frontend && VITE_API_BASE_URL=$(PROD_ORIGIN) VITE_APP_NAME=Querylab VITE_QUERY_STALE_TIME_MS=30000 pnpm build

## deploy: the normal deploy. Removes the seed files, so the container only starts web + worker.
deploy: build-frontend-prod
	rm -rf backend/.first-deploy
	cd backend/cloudflare && pnpm run deploy

## deploy-first: the first deploy only. The image also holds infra/sql and the Olist CSVs, and
## every start runs migrate, bootstrap_data_db and load_demo. Run `make keep-awake` while it
## seeds, then `make deploy` straight after, because a restart repeats the load.
deploy-first: build-frontend-prod
	rm -rf backend/.first-deploy
	mkdir -p backend/.first-deploy
	cp -r infra/sql backend/.first-deploy/sql
	cp -r infra/data/olist backend/.first-deploy/olist
	cd backend/cloudflare && pnpm run deploy; status=$$?; rm -rf ../../backend/.first-deploy; exit $$status

## keep-awake: one request a minute, because the container sleeps after 3 idle minutes and that
## would kill a running load_demo. Stop with Ctrl+C.
keep-awake:
	while true; do curl -s -o /dev/null -w '%{http_code}\n' $(PROD_ORIGIN)/api/health; sleep 60; done

## prod-manage: one manage.py command against production, e.g. make prod-manage ARGS="migrate"
prod-manage:
	backend/cloudflare/prod-manage.sh $(ARGS)

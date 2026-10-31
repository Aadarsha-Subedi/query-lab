# Querylab: one command per task. Everything runs in Docker Compose.

COMPOSE := docker compose --project-directory . --env-file .env -f infra/docker-compose.yml
BACKEND := $(COMPOSE) exec backend
FRONTEND := $(COMPOSE) exec frontend

.PHONY: setup up down dev logs migrate bootstrap-db load-demo createsuperuser \
        eval test test-backend test-frontend lint lint-backend lint-frontend \
        typecheck typecheck-backend typecheck-frontend format

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

# Infra

Local Docker Compose stack and the SQL / data the backend mounts. Run everything from the **repo root** with `make` (the Makefile passes `--project-directory . --env-file .env`).

## Compose

[`docker-compose.yml`](docker-compose.yml) starts:

| Service | Role |
|---------|------|
| `postgres` | Postgres 16 — databases `querylab_app` (Django) and `querylab` (demo + workspaces) |
| `redis` | Huey, caches, agent run state |
| `backend` | Django runserver (`:8000`) |
| `worker` | Same image, `run_huey` |
| `frontend` | Vite HMR (`:3000`) |

Root `.env` supplies host ports and the Postgres superuser (no defaults: a missing key stops compose). Backend/frontend settings live in `backend/.env` and `frontend/.env`.

```bash
make up      # background
make down
make dev     # foreground logs
make logs
```

## Postgres init

[`postgres/init-databases.sql`](postgres/init-databases.sql) runs once on a fresh volume and creates `querylab_app` and `querylab`. Django migrates only `querylab_app`.

## Data-DB SQL

[`sql/`](sql/) is applied by `make bootstrap-db` (`bootstrap_data_db`), in numeric order:

| File | Purpose |
|------|---------|
| `001_roles.sql` | `querylab_reader` role |
| `002_workspace_roles.sql` | Wall around workspace schemas |
| `010_demo_schema.sql` | Shared `demo` schema |
| `020_reader_grants.sql` | SELECT grants for the reader |

Never migrate `querylab` with Django.

## Data directories

| Path | Contents |
|------|----------|
| `data/olist/` | Olist CSVs for `make load-demo` (not committed; CC BY-NC-SA 4.0) |
| `data/spider/` | Spider download for evals / finetune (not committed) |
| `data/finetune/` | Offline dataset and prediction files from step 7 |

Download Olist into `data/olist/` before `make load-demo`. See the root README for licence and date-shift notes.

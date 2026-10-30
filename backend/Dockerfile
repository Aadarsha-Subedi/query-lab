# syntax=docker/dockerfile:1

# ── base: Python + uv ────────────────────────────────────────────────────
FROM python:3.12-slim AS base
COPY --from=ghcr.io/astral-sh/uv:0.11.26 /uv /usr/local/bin/uv
# uv download tuning for slow links. Required build args (no defaults): docker
# compose passes them from the root .env; a plain `docker build` needs
# --build-arg for both.
ARG UV_HTTP_TIMEOUT
ARG UV_CONCURRENT_DOWNLOADS
RUN test -n "$UV_HTTP_TIMEOUT" && test -n "$UV_CONCURRENT_DOWNLOADS" \
    || { echo "Build args UV_HTTP_TIMEOUT and UV_CONCURRENT_DOWNLOADS are required" >&2; exit 1; }
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_PROJECT_ENVIRONMENT=/opt/venv \
    UV_LINK_MODE=copy \
    UV_HTTP_TIMEOUT=${UV_HTTP_TIMEOUT} \
    UV_CONCURRENT_DOWNLOADS=${UV_CONCURRENT_DOWNLOADS} \
    PATH="/opt/venv/bin:$PATH"
WORKDIR /app

# ── dev: runtime + test dependencies; code is bind-mounted by compose ────
# Lint and type tools (ruff, mypy, pre-commit) run on the host, not here.
# The uv cache mount survives failed builds, so a re-run resumes downloads;
# sharing=locked stops two builds from fighting over it.
FROM base AS dev
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=querylab-uv,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project --no-default-groups --group test
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]

# ── build: runtime dependencies only ─────────────────────────────────────
FROM base AS build
ENV UV_COMPILE_BYTECODE=1
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,id=querylab-uv,target=/root/.cache/uv,sharing=locked \
    uv sync --frozen --no-install-project --no-default-groups
# The app is English only (LANGUAGE_CODE en-us): drop every other translation
# that the packages ship (about 20 MB), to stay inside the image budget.
RUN find /opt/venv/lib/python3.12/site-packages -type d -path '*/locale/*' -prune \
        ! -name 'en' ! -name 'en_*' -exec rm -rf {} +
COPY . .

# ── prod: the virtualenv and the code, run as a non-root user ────────────
FROM python:3.12-slim AS prod
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/opt/venv/bin:$PATH"
RUN useradd --create-home --uid 10001 app
WORKDIR /app
COPY --from=build /opt/venv /opt/venv
COPY --from=build --chown=app:app /app /app
USER app
CMD ["./entrypoint.sh"]

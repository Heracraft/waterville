# One image for both the web app (default command) and the weekly refresh job.

# Stage 1: build the SvelteKit app (web/) into static files.
FROM node:24-slim AS web
WORKDIR /web
ENV CI=1 COREPACK_ENABLE_DOWNLOAD_PROMPT=0
# corepack installs the pnpm version pinned in web/package.json ("packageManager").
RUN corepack enable
COPY web/package.json web/pnpm-lock.yaml web/pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile
COPY web/ ./
RUN pnpm build

# Stage 2: the Python app. FastAPI serves the built UI from /srv/web/build
# (config.web_dir() looks for web/build next to the app package).
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH=/srv/.venv/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ecode ecode
COPY app app
COPY --from=web /web/build web/build
# Fixtures for FAKE_AZURE=1, so the image can be smoke-tested with no Azure access.
COPY tests/fixtures tests/fixtures
COPY infra/refresh.sh /usr/local/bin/refresh
RUN chmod +x /usr/local/bin/refresh && useradd --uid 10001 --create-home appuser
# Without STORAGE_TABLE_ENDPOINT the store is SQLite at /srv/.data (lost on restart;
# fine for a FAKE_AZURE smoke test, Azure deployments set the Table endpoint).
RUN mkdir -p /srv/.data && chown appuser:appuser /srv/.data
USER appuser

EXPOSE 8000
# --no-access-log: app.main logs each request with its path only (no query string).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20", "--no-access-log"]

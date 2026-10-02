# One image for both the web app (default command) and the weekly refresh job.
FROM python:3.12-slim

COPY --from=ghcr.io/astral-sh/uv:0.8 /uv /usr/local/bin/uv
ENV UV_COMPILE_BYTECODE=1 UV_LINK_MODE=copy UV_PYTHON_DOWNLOADS=never \
    PATH=/srv/.venv/bin:$PATH PYTHONUNBUFFERED=1
WORKDIR /srv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY ecode ecode
COPY app app
COPY infra/refresh.sh /usr/local/bin/refresh
RUN chmod +x /usr/local/bin/refresh && useradd --uid 10001 --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-graceful-shutdown", "20"]

"""Waterville City Code Q&A: FastAPI app, routers and the built web UI.

Modules:
  config      every environment variable
  azure_auth  managed identity or key auth for Azure, shared HTTP client
  search      retrieval, filters, citation lookup, facets
  llm         Azure OpenAI streaming and one-shot completions
  prompts     public and staff system prompts
  ratelimit   public, staff and login limits
  auth        staff sign-in, sessions, require_staff
  store       Azure Table storage or SQLite
  pii         scrub() for question logs
  routers/*   the API (see each module's docstring; chat.py documents the SSE contract)

The web UI is the SvelteKit static build (web/build, or /srv/web in the
image), served with an SPA fallback to index.html for any non-API path.
"""

from __future__ import annotations

import base64
import hashlib
import logging
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response

from . import config, store
from .azure_auth import http
from .routers import chat, checklists, deadlines, drafts, insights, lookup, notebooks, staff

log = logging.getLogger("app")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
# Request log without query strings: staff searches carry names and addresses
# in ?q=, and uvicorn's own access log (switched off in the Dockerfile with
# --no-access-log) would ship them to Log Analytics.
access_log = logging.getLogger("app.access")


class _NoQueryAccessLog(logging.Filter):
    """Drop the query string from uvicorn access lines, for runs that keep uvicorn's access log on."""

    def filter(self, record: logging.LogRecord) -> bool:
        args = record.args
        if isinstance(args, tuple) and len(args) >= 3 and isinstance(args[2], str) and "?" in args[2]:
            record.args = (*args[:2], args[2].split("?", 1)[0], *args[3:])
        return True


logging.getLogger("uvicorn.access").addFilter(_NoQueryAccessLog())

ROUTERS = (chat, staff, lookup, notebooks, drafts, deadlines, checklists, insights)
IMMUTABLE_PREFIX = "/_app/immutable/"

NOT_BUILT = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Frontend not built</title>
<style>body{margin:0;padding:48px 16px;background:#eaeaea;color:#032c3c;font:16px/1.5 Inter,system-ui,sans-serif}
main{max-width:560px;margin:0 auto;border-top:1px solid #032c3c;padding-top:16px}code{font-size:14px}</style></head>
<body><main><h1>Frontend not built</h1>
<p>The API is running. Build the web UI with <code>cd web &amp;&amp; pnpm install &amp;&amp; pnpm build</code>, then reload.</p>
</main></body></html>
"""


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("starting: env=%s fake_azure=%s web=%s", config.APP_ENV, config.FAKE_AZURE, config.web_dir())
    yield
    s = store._store
    if s is not None:
        await s.close()
    await http.aclose()


app = FastAPI(title="Waterville Codes RAG", docs_url=None, redoc_url=None, openapi_url=None, lifespan=lifespan)


# Content Security Policy. Scripts come only from this origin plus the inline
# scripts of the built index.html (the theme script in app.html and SvelteKit's
# bootstrap), allowed by hash. The hashes are read from the file, so a rebuild
# needs no code change.
_CSP_BASE = (
    "default-src 'self'; style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com; img-src 'self' data: blob:; connect-src 'self'; "
    "worker-src 'self'; manifest-src 'self'; object-src 'none'; base-uri 'self'; form-action 'self'"
)
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.S | re.I)
_hash_cache: dict[str, object] = {"key": None, "value": ""}


def _script_hashes() -> str:
    root = config.web_dir()
    if root is None:
        return ""
    index = root / "index.html"
    try:
        key = (str(index), index.stat().st_mtime_ns)
    except OSError:
        return ""
    if _hash_cache["key"] != key:
        html = index.read_text(encoding="utf-8")
        hashes = sorted(
            {
                "'sha256-" + base64.b64encode(hashlib.sha256(body.encode()).digest()).decode() + "'"
                for body in _INLINE_SCRIPT.findall(html)
            }
        )
        _hash_cache.update(key=key, value=" ".join(hashes))
    return str(_hash_cache["value"])


def content_security_policy(frame_ancestors: str) -> str:
    """The full policy; frame-ancestors is always the last directive."""
    script = " ".join(x for x in ("'self'", _script_hashes()) if x)
    return f"{_CSP_BASE}; script-src {script}; frame-ancestors {frame_ancestors}"


def _private(request: Request, path: str) -> bool:
    """Responses that hold staff data: never kept by a browser or proxy cache."""
    if path.startswith("/api/staff/") or path == "/api/staff":
        return True
    # A staff answer streams from /api/chat; the cookie marks a staff caller.
    return path == "/api/chat" and config.SESSION_COOKIE in request.cookies


@app.middleware("http")
async def headers(request: Request, call_next):
    started = time.perf_counter()
    response = await call_next(request)
    path = request.url.path
    if _private(request, path):
        response.headers["Cache-Control"] = "no-store"
        response.headers.setdefault("Pragma", "no-cache")
    if request.method in ("GET", "HEAD") and not path.startswith("/api/"):
        if path.startswith(IMMUTABLE_PREFIX) and response.status_code == 200:
            # SvelteKit puts a content hash in every file name under _app/immutable.
            response.headers["Cache-Control"] = "public, max-age=31536000, immutable"
        else:
            # Everything else carries an ETag; no-cache makes browsers revalidate
            # so a new deploy takes effect on the next page load.
            response.headers.setdefault("Cache-Control", "no-cache")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    # Only /embed may be framed, and only by EMBED_ORIGINS (A6). Every other
    # page refuses framing, so the public chat cannot be iframed elsewhere.
    if path == "/embed" or path.startswith("/embed/"):
        ancestors = " ".join(["'self'", *config.EMBED_ORIGINS])
        response.headers.setdefault("Content-Security-Policy", content_security_policy(ancestors))
    else:
        response.headers.setdefault("Content-Security-Policy", content_security_policy("'none'"))
        response.headers.setdefault("X-Frame-Options", "DENY")
    if path.startswith("/staff") or path.startswith("/api/") or config.APP_ENV == "preview":
        response.headers.setdefault("X-Robots-Tag", "noindex")
    if path != "/healthz":
        # Path only: query strings can hold names and addresses.
        access_log.info(
            "%s %s %d %.0fms", request.method, path, response.status_code, (time.perf_counter() - started) * 1000
        )
    return response


@app.exception_handler(store.StoreError)
async def store_error(request: Request, exc: store.StoreError):
    # Validation inside the store (size, keys) is the caller's input, not a server fault.
    if "too large" in str(exc):
        return JSONResponse({"detail": "That is too large to save. Shorten the text and try again."}, status_code=413)
    return JSONResponse({"detail": "That could not be saved."}, status_code=422)


@app.get("/healthz")
async def healthz():
    return {"ok": True}


for module in ROUTERS:
    app.include_router(module.router)


@app.api_route("/api/{rest:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE", "HEAD"], include_in_schema=False)
async def api_not_found(rest: str):
    return JSONResponse({"detail": "Not Found"}, status_code=404)


def _static_file(root: Path, path: str) -> Path | None:
    """A file under root for a URL path, or None. Refuses paths outside root."""
    rel = path.lstrip("/")
    candidates = [rel] if rel else []
    if rel and not rel.endswith("/"):
        candidates += [f"{rel}.html", f"{rel}/index.html"]
    elif rel:
        candidates.append(f"{rel}index.html")
    for c in candidates:
        try:
            p = (root / c).resolve()
        except (OSError, ValueError):
            continue
        if p.is_file() and p.is_relative_to(root):
            return p
    return None


def _file(request: Request, path: Path) -> Response:
    """FileResponse, or 304 when the browser's ETag still matches."""
    response = FileResponse(path, stat_result=path.stat())
    etag = response.headers.get("etag")
    inm = request.headers.get("if-none-match")
    if etag and inm and etag in [t.strip() for t in inm.split(",")]:
        return Response(status_code=304, headers={"ETag": etag})
    return response


@app.api_route("/{path:path}", methods=["GET", "HEAD"], include_in_schema=False)
async def web(path: str, request: Request):
    root = config.web_dir()
    if root is None:
        return HTMLResponse(NOT_BUILT, status_code=503)
    if f := _static_file(root, path):
        return _file(request, f)
    last = path.rstrip("/").rsplit("/", 1)[-1]
    if "." in last or path.startswith("_app/"):
        # A missing asset is a 404, not the app shell.
        return Response("Not Found", status_code=404, media_type="text/plain")
    return _file(request, root / "index.html")

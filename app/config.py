"""Every environment variable the app reads, in one place.

Other modules read these as `config.NAME` at call time (never
`from .config import NAME`), so tests can monkeypatch a single attribute.
"""

from __future__ import annotations

import json
import logging
import os
import secrets
from pathlib import Path

log = logging.getLogger("app.config")


def _int(name: str, default: int) -> int:
    return int(os.environ.get(name, str(default)))


def _float(name: str, default: float) -> float:
    return float(os.environ.get(name, str(default)))


ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- environment

APP_ENV = os.environ.get("APP_ENV", "local").strip().lower() or "local"
if APP_ENV not in ("production", "preview", "local"):
    log.warning("unknown APP_ENV %r, treating it as production", APP_ENV)
    APP_ENV = "production"
IS_LOCAL = APP_ENV == "local"

# FAKE_AZURE=1 serves search results and model output from tests/fixtures,
# so the app runs with no Azure access (UI work, e2e tests, screenshots).
FAKE_AZURE = os.environ.get("FAKE_AZURE", "") == "1"
FIXTURES_DIR = Path(os.environ.get("FAKE_FIXTURES_DIR") or ROOT / "tests" / "fixtures")
# Seconds between fake streamed chunks, so the UI shows streaming.
FAKE_STREAM_DELAY = _float("FAKE_STREAM_DELAY", 0.02)

# ---------------------------------------------------------------- Azure AI Search

SEARCH_ENDPOINT = os.environ.get("AZURE_SEARCH_ENDPOINT", "").rstrip("/")
SEARCH_INDEX = os.environ.get("AZURE_SEARCH_INDEX", "waterville-code")
SEARCH_API = "2024-07-01"
LOCAL_K = _int("LOCAL_K", 5)
STATE_K = _int("STATE_K", 4)
STAFF_K_LOCAL = _int("STAFF_K_LOCAL", 8)
STAFF_K_STATE = _int("STAFF_K_STATE", 6)
MIN_RERANKER_SCORE = _float("MIN_RERANKER_SCORE", 1.0)  # semantic ranker scale is 0-4

# ---------------------------------------------------------------- Azure OpenAI

AOAI_ENDPOINT = os.environ.get("AZURE_OPENAI_ENDPOINT", "").rstrip("/")
AOAI_API = "2024-10-21"
CHAT_DEPLOYMENT = os.environ.get("AZURE_OPENAI_CHAT_DEPLOYMENT", "chat")
REASONING_EFFORT = os.environ.get("CHAT_REASONING_EFFORT")  # set only for reasoning models
MAX_ANSWER_TOKENS = _int("MAX_ANSWER_TOKENS", 1500)
STAFF_MAX_ANSWER_TOKENS = _int("STAFF_MAX_ANSWER_TOKENS", 4000)

# ---------------------------------------------------------------- public limits

MAX_QUESTION_CHARS = _int("MAX_QUESTION_CHARS", 1000)
PER_IP_PER_MINUTE = _int("RATE_LIMIT_PER_MINUTE", 6)
PER_IP_PER_DAY = _int("RATE_LIMIT_PER_DAY", 60)
GLOBAL_PER_DAY = _int("GLOBAL_LIMIT_PER_DAY", 3000)

# ---------------------------------------------------------------- staff

STAFF_PER_MINUTE = _int("STAFF_RATE_LIMIT_PER_MINUTE", 60)
LOGIN_ATTEMPTS = _int("LOGIN_ATTEMPTS_PER_WINDOW", 10)
LOGIN_WINDOW_SECONDS = _int("LOGIN_WINDOW_SECONDS", 15 * 60)
SESSION_HOURS = _float("SESSION_HOURS", 12)
SESSION_COOKIE = "wv_session"
CSRF_HEADER = "X-Requested-With"
CSRF_VALUE = "wv"


def _staff_users() -> dict[str, str]:
    raw = os.environ.get("STAFF_USERS", "").strip()
    if not raw:
        return {}
    try:
        users = json.loads(raw)
    except json.JSONDecodeError:
        log.error("STAFF_USERS is not valid JSON; staff login is disabled")
        return {}
    if not isinstance(users, dict) or not all(isinstance(k, str) and isinstance(v, str) for k, v in users.items()):
        log.error("STAFF_USERS must be a JSON object of username to hash; staff login is disabled")
        return {}
    return users


STAFF_USERS: dict[str, str] = _staff_users()

SESSION_SECRET_SET = bool(os.environ.get("SESSION_SECRET"))
# Random per process when unset. That logs staff out on every restart and
# breaks with more than one replica, so outside local dev staff login stays
# off until SESSION_SECRET is set (see auth.login_enabled).
SESSION_SECRET: bytes = (os.environ.get("SESSION_SECRET") or secrets.token_urlsafe(32)).encode()
# Secure cookies everywhere except local http.
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0" if IS_LOCAL else "1") == "1"

# ---------------------------------------------------------------- store

STORAGE_TABLE_ENDPOINT = os.environ.get("STORAGE_TABLE_ENDPOINT", "").rstrip("/")
# Local dev against Azurite only; Azure uses the endpoint plus managed identity.
STORAGE_CONNECTION_STRING = os.environ.get("STORAGE_CONNECTION_STRING", "")
STORE_SQLITE_PATH = Path(os.environ.get("STORE_SQLITE_PATH") or ROOT / ".data" / "store.sqlite")
QUESTION_LOG = os.environ.get("QUESTION_LOG", "0") == "1"
# Days a logged public question is kept; older days are deleted. 0 keeps them.
QUESTION_LOG_RETENTION_DAYS = _int("QUESTION_LOG_RETENTION_DAYS", 365)

# ---------------------------------------------------------------- web

EMBED_ORIGINS = os.environ.get(
    "EMBED_ORIGINS", "https://waterville-me.gov https://www.waterville-me.gov"
).split()


def web_dir() -> Path | None:
    """The built SvelteKit app: WEB_DIR, else web/build in the repo, else /srv/web in the image."""
    candidates = [os.environ.get("WEB_DIR"), ROOT / "web" / "build", "/srv/web"]
    for c in candidates:
        if c and (Path(c) / "index.html").is_file():
            return Path(c).resolve()
    return None

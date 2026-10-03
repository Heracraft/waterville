"""Staff sign-in: scrypt password hashes, HMAC-signed session cookies, require_staff.

STAFF_USERS holds {"username": "scrypt$N$r$p$salt_b64$hash_b64"}. Make a hash with

    python -m app.auth hash            # reads the password on stdin, prints the hash
    python -m app.auth hash alice      # prints {"alice": "<hash>"} for STAFF_USERS
    python -m app.auth secret          # prints a fresh SESSION_SECRET value

The session cookie `wv_session` is `username.expiry.signature`, where the
signature is HMAC-SHA256 over `username.expiry` with SESSION_SECRET. It is
HttpOnly, SameSite=Strict, Secure outside local dev, and lasts SESSION_HOURS.
Removing a user from STAFF_USERS ends their sessions on the next request.

CSRF: SameSite=Strict, plus every staff POST/PUT/PATCH/DELETE must carry
`X-Requested-With: wv`, which a cross-site form cannot send.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import re
import secrets
import sys
import time

from fastapi import HTTPException, Request, Response

from . import config

log = logging.getLogger("app.auth")

USERNAME_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
SCRYPT_N, SCRYPT_R, SCRYPT_P = 2**15, 8, 1
SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}


# ---------------------------------------------------------------- passwords


def _b64(b: bytes) -> str:
    return base64.urlsafe_b64encode(b).decode().rstrip("=")


def _unb64(s: str) -> bytes:
    return base64.urlsafe_b64decode(s + "=" * (-len(s) % 4))


def _scrypt(password: str, salt: bytes, n: int, r: int, p: int) -> bytes:
    return hashlib.scrypt(password.encode(), salt=salt, n=n, r=r, p=p, maxmem=256 * 1024 * 1024, dklen=32)


def hash_password(password: str, n: int = SCRYPT_N, r: int = SCRYPT_R, p: int = SCRYPT_P) -> str:
    salt = secrets.token_bytes(16)
    return f"scrypt${n}${r}${p}${_b64(salt)}${_b64(_scrypt(password, salt, n, r, p))}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = encoded.split("$")
        if scheme != "scrypt":
            return False
        n_, r_, p_ = int(n), int(r), int(p)
        if n_ > 2**20 or r_ > 32 or p_ > 16:
            return False
        got = _scrypt(password, _unb64(salt), n_, r_, p_)
        return hmac.compare_digest(got, _unb64(digest))
    except (ValueError, TypeError):
        return False


# Spent on unknown usernames, so a wrong name takes as long as a wrong password.
_DUMMY_HASH = None


def _dummy_hash() -> str:
    global _DUMMY_HASH
    if _DUMMY_HASH is None:
        _DUMMY_HASH = hash_password(secrets.token_urlsafe(16))
    return _DUMMY_HASH


def login_enabled() -> bool:
    """Staff sign-in needs users, and outside local dev a fixed SESSION_SECRET."""
    if not config.STAFF_USERS:
        return False
    if not config.IS_LOCAL and not config.SESSION_SECRET_SET:
        log.error("SESSION_SECRET is not set; staff login is disabled outside local dev")
        return False
    return True


def check_credentials(username: str, password: str) -> bool:
    encoded = config.STAFF_USERS.get(username) if USERNAME_RE.match(username or "") else None
    ok = verify_password(password or "", encoded or _dummy_hash())
    return ok and encoded is not None


# ---------------------------------------------------------------- sessions


def _sign(payload: str) -> str:
    return _b64(hmac.new(config.SESSION_SECRET, payload.encode(), hashlib.sha256).digest())


def make_session(username: str, now: float | None = None) -> tuple[str, int]:
    """(cookie value, expiry unix time)."""
    expiry = int((now if now is not None else time.time()) + config.SESSION_HOURS * 3600)
    payload = f"{username}.{expiry}"
    return f"{payload}.{_sign(payload)}", expiry


def read_session(value: str | None, now: float | None = None) -> tuple[str, int] | None:
    """(username, expiry) for a valid, unexpired cookie of a current user, else None."""
    if not value or len(value) > 256:
        return None
    parts = value.split(".")
    if len(parts) != 3:
        return None
    username, expiry, sig = parts
    if not USERNAME_RE.match(username) or not expiry.isdigit():
        return None
    if not hmac.compare_digest(sig, _sign(f"{username}.{expiry}")):
        return None
    if int(expiry) <= (now if now is not None else time.time()):
        return None
    if username not in config.STAFF_USERS:
        return None
    return username, int(expiry)


def set_session_cookie(response: Response, username: str) -> int:
    value, expiry = make_session(username)
    response.set_cookie(
        config.SESSION_COOKIE,
        value,
        max_age=int(config.SESSION_HOURS * 3600),
        httponly=True,
        secure=config.COOKIE_SECURE,
        samesite="strict",
        path="/",
    )
    return expiry


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        config.SESSION_COOKIE, path="/", httponly=True, secure=config.COOKIE_SECURE, samesite="strict"
    )


def current_staff(request: Request) -> str | None:
    """The signed-in staff username, or None. Never raises."""
    if not config.STAFF_USERS:
        return None
    s = read_session(request.cookies.get(config.SESSION_COOKIE))
    return s[0] if s else None


def check_csrf(request: Request) -> None:
    if request.method not in SAFE_METHODS and request.headers.get(config.CSRF_HEADER) != config.CSRF_VALUE:
        raise HTTPException(403, "Missing request header.")


async def require_staff(request: Request) -> str:
    """FastAPI dependency: the staff username, or 401. Enforces the CSRF header on writes."""
    user = current_staff(request)
    if not user:
        raise HTTPException(401, "Staff sign-in required.")
    check_csrf(request)
    return user


# ---------------------------------------------------------------- CLI


def _cli(argv: list[str]) -> int:
    if not argv or argv[0] not in ("hash", "secret"):
        print("usage: python -m app.auth hash [username] < password\n       python -m app.auth secret", file=sys.stderr)
        return 2
    if argv[0] == "secret":
        print(secrets.token_urlsafe(48))
        return 0
    if sys.stdin.isatty():
        import getpass

        password = getpass.getpass("Password: ")
    else:
        password = sys.stdin.readline().rstrip("\r\n")
    if len(password) < 12:
        print("Use a password of at least 12 characters.", file=sys.stderr)
        return 1
    encoded = hash_password(password)
    if len(argv) > 1:
        if not USERNAME_RE.match(argv[1]):
            print("Usernames use letters, digits, - and _ only.", file=sys.stderr)
            return 1
        print(json.dumps({argv[1]: encoded}))
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv[1:]))

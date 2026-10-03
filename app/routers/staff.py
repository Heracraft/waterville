"""Staff session endpoints.

POST /api/staff/login   {"username", "password"} -> {"username", "expires"} + cookie
POST /api/staff/logout  -> {"ok": true}, clears the cookie
GET  /api/staff/me      -> {"username", "expires", "env", "stamp"} or 401

Both POSTs need the X-Requested-With: wv header. Login is limited per IP
(LOGIN_ATTEMPTS per LOGIN_WINDOW_SECONDS, default 10 per 15 minutes) and
answers 503 when staff login is not configured.
"""

from __future__ import annotations

import asyncio
import hashlib
import logging

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from .. import auth, config, prompts, ratelimit

log = logging.getLogger("app.staff")

router = APIRouter(tags=["staff"])


class LoginRequest(BaseModel):
    username: str = Field(max_length=64)
    password: str = Field(max_length=256)


@router.post("/api/staff/login")
async def login(req: LoginRequest, request: Request, response: Response):
    auth.check_csrf(request)
    if not auth.login_enabled():
        raise HTTPException(503, "Staff sign-in is not set up on this server.")
    ip = ratelimit.client_ip(request)
    if msg := ratelimit.login_limiter.check(ip):
        raise HTTPException(429, msg)
    username = req.username.strip()
    # scrypt is CPU-bound; keep the event loop free.
    ok = await asyncio.to_thread(auth.check_credentials, username, req.password)
    if not ok:
        # Not the username itself: people type passwords into the wrong field.
        tag = hashlib.sha256(username.encode()).hexdigest()[:8] if username else "-"
        log.warning("staff login failed for a username of %d characters (sha256 %s) from %s", len(username), tag, ip)
        raise HTTPException(401, "Wrong username or password.")
    expires = auth.set_session_cookie(response, username)
    log.info("staff login %s from %s", username, ip)
    return {"username": username, "expires": expires}


@router.post("/api/staff/logout")
async def logout(request: Request, response: Response):
    auth.check_csrf(request)
    auth.clear_session_cookie(response)
    return {"ok": True}


@router.get("/api/staff/me")
async def me(request: Request):
    session = auth.read_session(request.cookies.get(config.SESSION_COOKIE)) if config.STAFF_USERS else None
    if not session:
        raise HTTPException(401, "Staff sign-in required.")
    username, expires = session
    return {"username": username, "expires": expires, "env": config.APP_ENV, "stamp": prompts.RESEARCH_AID_STAMP}

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from app import auth, config
from conftest import CSRF, PASSWORD

REPO = Path(__file__).resolve().parents[1]


def test_hash_roundtrip():
    h = auth.hash_password("s3cret-password", n=2**10)
    assert h.startswith("scrypt$1024$8$1$")
    assert auth.verify_password("s3cret-password", h)
    assert not auth.verify_password("wrong", h)
    assert not auth.verify_password("s3cret-password", "bcrypt$x")
    assert not auth.verify_password("s3cret-password", "garbage")
    # Two hashes of one password differ (random salt).
    assert h != auth.hash_password("s3cret-password", n=2**10)


def test_default_hash_parameters():
    h = auth.hash_password("another password")
    assert h.split("$")[1:4] == [str(2**15), "8", "1"]


def test_login_sets_cookie_and_me(client):
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 200
    assert r.json()["username"] == "alice"
    cookie = r.headers["set-cookie"]
    assert "wv_session=" in cookie
    assert "HttpOnly" in cookie
    assert "SameSite=strict" in cookie or "samesite=strict" in cookie.lower()
    me = client.get("/api/staff/me")
    assert me.status_code == 200
    body = me.json()
    assert body["username"] == "alice"
    assert body["expires"] > time.time() + 11 * 3600
    assert body["stamp"].startswith("Research aid")


def test_secure_cookie_outside_local(client, monkeypatch):
    monkeypatch.setattr(config, "COOKIE_SECURE", True)
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert "Secure" in r.headers["set-cookie"]


def test_bad_password(client):
    r = client.post("/api/staff/login", json={"username": "alice", "password": "nope"}, headers=CSRF)
    assert r.status_code == 401
    assert "set-cookie" not in r.headers
    assert client.get("/api/staff/me").status_code == 401


def test_unknown_user(client):
    r = client.post("/api/staff/login", json={"username": "mallory", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 401
    r = client.post("/api/staff/login", json={"username": "../etc", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 401


def test_login_needs_csrf_header(client):
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD})
    assert r.status_code == 403
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers={"X-Requested-With": "XMLHttpRequest"})
    assert r.status_code == 403


def test_login_disabled_without_users(client, monkeypatch):
    monkeypatch.setattr(config, "STAFF_USERS", {})
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 503


def test_login_disabled_without_secret_outside_local(client, monkeypatch):
    monkeypatch.setattr(config, "IS_LOCAL", False)
    monkeypatch.setattr(config, "SESSION_SECRET_SET", False)
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 503


def test_login_rate_limit(client):
    for _ in range(10):
        r = client.post("/api/staff/login", json={"username": "alice", "password": "x"}, headers=CSRF)
        assert r.status_code == 401
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 429


def test_cookie_tamper(staff_client):
    value = staff_client.cookies.get("wv_session")
    user, expiry, sig = value.split(".")
    for bad in (
        f"bob.{expiry}.{sig}",
        f"{user}.{int(expiry) + 3600}.{sig}",
        f"{user}.{expiry}.{sig[:-2]}AA",
        f"{user}.{expiry}",
        "",
        "a.b.c.d",
    ):
        staff_client.cookies.set("wv_session", bad)
        assert staff_client.get("/api/staff/me").status_code == 401, bad


def test_cookie_wrong_secret(staff_client, monkeypatch):
    monkeypatch.setattr(config, "SESSION_SECRET", b"another-secret")
    assert staff_client.get("/api/staff/me").status_code == 401


def test_expiry():
    value, expiry = auth.make_session("alice", now=1000.0)
    assert expiry == 1000 + 12 * 3600
    assert auth.read_session(value, now=1000.0 + 60) == ("alice", expiry)
    assert auth.read_session(value, now=expiry) is None
    assert auth.read_session(value, now=expiry + 1) is None


def test_expired_cookie_rejected_by_api(client):
    value, _ = auth.make_session("alice", now=time.time() - 13 * 3600)
    client.cookies.set("wv_session", value)
    assert client.get("/api/staff/me").status_code == 401


def test_removed_user_loses_session(staff_client, monkeypatch):
    monkeypatch.setattr(config, "STAFF_USERS", {"bob": "scrypt$1$1$1$a$b"})
    assert staff_client.get("/api/staff/me").status_code == 401


def test_logout(staff_client):
    assert staff_client.post("/api/staff/logout").status_code == 403
    r = staff_client.post("/api/staff/logout", headers=CSRF)
    assert r.status_code == 200
    assert "wv_session" in r.headers["set-cookie"]
    assert staff_client.get("/api/staff/me").status_code == 401


def test_require_staff_signed_out(client):
    client.cookies.clear()
    assert client.get("/api/staff/cases").status_code == 401


def test_cli_hash():
    out = subprocess.run(
        [sys.executable, "-m", "app.auth", "hash", "carol"],
        input="a long enough password\n",
        capture_output=True,
        text=True,
        check=True,
        cwd=REPO,
    )
    users = json.loads(out.stdout)
    assert auth.verify_password("a long enough password", users["carol"])


def test_cli_rejects_short_password():
    out = subprocess.run(
        [sys.executable, "-m", "app.auth", "hash"], input="short\n", capture_output=True, text=True, cwd=REPO
    )
    assert out.returncode == 1

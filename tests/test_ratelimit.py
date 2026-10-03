from __future__ import annotations

from app import config, ratelimit
from conftest import CSRF

Q = {"messages": [{"role": "user", "content": "Can I keep backyard chickens?"}]}


def test_public_per_minute_limit():
    rl = ratelimit.RateLimiter(per_minute=2, per_day=10, global_per_day=100)
    assert rl.check("1.1.1.1") is None
    assert rl.check("1.1.1.1") is None
    assert "Too many questions" in rl.check("1.1.1.1")
    assert rl.check("2.2.2.2") is None


def test_public_daily_and_global_limits():
    rl = ratelimit.RateLimiter(per_minute=100, per_day=1, global_per_day=2)
    assert rl.check("a") is None
    assert "daily question limit" in rl.check("a")
    assert rl.check("b") is None
    assert "reached its daily question limit" in rl.check("c")


def test_staff_limiter():
    wl = ratelimit.WindowLimiter(2, 60, "slow")
    assert wl.check("alice") is None and wl.check("alice") is None
    assert wl.check("alice") == "slow"
    assert wl.check("bob") is None


def test_client_ip_uses_last_forwarded_entry(client):
    seen = []

    from fastapi import Request

    class R:
        headers = {"x-forwarded-for": "6.6.6.6, 10.0.0.1"}
        client = None

    seen.append(ratelimit.client_ip(R()))
    assert seen == ["10.0.0.1"]


def test_chat_public_limit_then_staff_bypass(client, monkeypatch):
    monkeypatch.setattr(config, "PER_IP_PER_MINUTE", 1)
    assert client.post("/api/chat", json=Q).status_code == 200
    r = client.post("/api/chat", json=Q)
    assert r.status_code == 429
    assert "Too many questions" in r.json()["detail"]
    # Same IP, signed in: the per-IP limit no longer applies.
    from conftest import PASSWORD

    client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF).status_code == 200
    assert client.post("/api/chat", json=Q).status_code == 200


def test_staff_have_their_own_limit(staff_client, monkeypatch):
    monkeypatch.setattr(config, "STAFF_PER_MINUTE", 2)
    for _ in range(2):
        assert staff_client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF).status_code == 200
    assert staff_client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF).status_code == 429


def test_forwarded_ip_limits_separately(client, monkeypatch):
    monkeypatch.setattr(config, "PER_IP_PER_MINUTE", 1)
    assert client.post("/api/chat", json=Q, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 200
    assert client.post("/api/chat", json=Q, headers={"X-Forwarded-For": "1.2.3.4"}).status_code == 429
    assert client.post("/api/chat", json=Q, headers={"X-Forwarded-For": "1.2.3.4, 5.6.7.8"}).status_code == 200

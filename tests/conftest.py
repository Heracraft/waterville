"""Shared test setup. No network: Azure calls go to FAKE_AZURE fixtures or httpx mocks."""

from __future__ import annotations

import json
import os

import pytest

# Before app modules load: never pick up a developer's real Azure or staff settings.
for _var in ("STAFF_USERS", "SESSION_SECRET", "STORAGE_TABLE_ENDPOINT", "STORAGE_CONNECTION_STRING", "QUESTION_LOG", "WEB_DIR"):
    os.environ.pop(_var, None)
os.environ["APP_ENV"] = "local"

from fastapi.testclient import TestClient  # noqa: E402

from app import auth, config, ratelimit, store  # noqa: E402

PASSWORD = "correct horse battery staple"
CSRF = {"X-Requested-With": "wv"}


def parse_sse(text: str) -> list[tuple[str, object]]:
    events = []
    for block in text.split("\n\n"):
        if not block.strip():
            continue
        lines = block.split("\n")
        assert lines[0].startswith("event: "), block
        assert lines[1].startswith("data: "), block
        events.append((lines[0][7:], json.loads(lines[1][6:])))
    return events


@pytest.fixture(scope="session")
def alice_hash() -> str:
    # Small N keeps the suite fast; production hashes use auth.SCRYPT_N.
    return auth.hash_password(PASSWORD, n=2**10)


@pytest.fixture(autouse=True)
def env(monkeypatch, tmp_path, alice_hash):
    monkeypatch.setattr(config, "APP_ENV", "local")
    monkeypatch.setattr(config, "IS_LOCAL", True)
    monkeypatch.setattr(config, "FAKE_AZURE", True)
    monkeypatch.setattr(config, "FAKE_STREAM_DELAY", 0)
    monkeypatch.setattr(config, "STAFF_USERS", {"alice": alice_hash})
    monkeypatch.setattr(config, "SESSION_SECRET", b"test-secret")
    monkeypatch.setattr(config, "SESSION_SECRET_SET", True)
    monkeypatch.setattr(config, "COOKIE_SECURE", False)
    monkeypatch.setattr(config, "QUESTION_LOG", False)
    monkeypatch.setenv("WEB_DIR", str(tmp_path / "no-build"))
    monkeypatch.setattr(config, "ROOT", tmp_path)  # so web_dir() never finds a real build
    db = store.SqliteStore(tmp_path / "store.sqlite")
    store.set_store(db)
    ratelimit.reset_all()
    yield
    store.set_store(None)
    ratelimit.reset_all()


@pytest.fixture
def client():
    from app.main import app

    # Not used as a context manager: lifespan shutdown would close the shared httpx client.
    return TestClient(app)


@pytest.fixture
def staff_client(client):
    r = client.post("/api/staff/login", json={"username": "alice", "password": PASSWORD}, headers=CSRF)
    assert r.status_code == 200, r.text
    return client

from __future__ import annotations

import pytest

from app import config


@pytest.fixture
def build(tmp_path, monkeypatch):
    root = tmp_path / "build"
    (root / "_app" / "immutable" / "chunks").mkdir(parents=True)
    (root / "index.html").write_text("<!doctype html><title>shell</title>")
    (root / "_app" / "immutable" / "chunks" / "app.abc123.js").write_text("console.log(1)")
    (root / "_app" / "version.json").write_text('{"version":"1"}')
    (root / "favicon.svg").write_text("<svg/>")
    (root / "about.html").write_text("prerendered about")
    (tmp_path / "secret.txt").write_text("outside")
    monkeypatch.setenv("WEB_DIR", str(root))
    return root


def test_healthz(client):
    assert client.get("/healthz").json() == {"ok": True}


def test_not_built_page(client):
    r = client.get("/")
    assert r.status_code == 503
    assert "Frontend not built" in r.text
    assert client.get("/healthz").status_code == 200


def test_index_and_spa_fallback(client, build):
    r = client.get("/")
    assert r.status_code == 200 and "shell" in r.text
    assert r.headers["cache-control"] == "no-cache"
    for path in ("/staff", "/staff/cases/abc", "/permits", "/embed"):
        r = client.get(path)
        assert r.status_code == 200 and "shell" in r.text, path


def test_prerendered_page(client, build):
    assert client.get("/about").text == "prerendered about"


def test_immutable_assets_cached_long(client, build):
    r = client.get("/_app/immutable/chunks/app.abc123.js")
    assert r.status_code == 200
    assert r.headers["cache-control"] == "public, max-age=31536000, immutable"
    r = client.get("/_app/version.json")
    assert r.headers["cache-control"] == "no-cache"
    r = client.get("/favicon.svg")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-cache"


def test_missing_asset_is_404(client, build):
    assert client.get("/_app/immutable/chunks/gone.js").status_code == 404
    assert client.get("/nope.png").status_code == 404


def test_etag_revalidation(client, build):
    r = client.get("/")
    etag = r.headers["etag"]
    r2 = client.get("/", headers={"If-None-Match": etag})
    assert r2.status_code == 304


def test_path_traversal(client, build):
    for p in ("/../secret.txt", "/%2e%2e/secret.txt", "/_app/../../secret.txt"):
        r = client.get(p)
        assert "outside" not in r.text


def test_unknown_api_is_json_404(client, build):
    r = client.get("/api/does-not-exist")
    assert r.status_code == 404 and r.json() == {"detail": "Not Found"}
    assert client.post("/api/does-not-exist").status_code == 404


def test_security_headers(client, build):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "strict-origin-when-cross-origin"
    # Only /embed may be framed (A6); full coverage in tests/test_public_deflection.py.
    assert r.headers["content-security-policy"].split("; ")[-1] == "frame-ancestors 'none'"
    r = client.get("/embed")
    csp = r.headers["content-security-policy"].split("; ")[-1]
    assert csp.startswith("frame-ancestors 'self' ")
    assert all(o in csp for o in config.EMBED_ORIGINS)
    r = client.get("/staff")
    assert r.headers["x-frame-options"] == "DENY"
    assert r.headers["x-robots-tag"] == "noindex"


def test_preview_is_noindex(client, build, monkeypatch):
    monkeypatch.setattr(config, "APP_ENV", "preview")
    assert client.get("/").headers["x-robots-tag"] == "noindex"


@pytest.mark.parametrize(
    "path,status",
    [
        ("/api/lookup", 501),
        ("/api/deadlines", 501),
        ("/api/checklists", 501),
        ("/api/staff/cases", 401),
        ("/api/staff/drafts", 401),
        ("/api/staff/insights", 401),
    ],
)
def test_router_stubs_registered(client, path, status):
    # Feature stages replace these placeholders; the paths must keep resolving to a router.
    assert client.get(path).status_code in (status, 200, 400, 422)
    assert client.get(path).status_code != 404

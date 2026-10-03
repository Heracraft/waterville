"""Regression tests for the review findings fixed on 2026-10-03."""

from __future__ import annotations

import asyncio
import datetime as dt

from conftest import CSRF

from app import config
from app import store as app_store
from app.routers import chat as chat_router
from app.routers import notebooks
from app.store import encode_entity, decode_entity, get_store


# ---------------------------------------------------------------- chat


def test_long_staff_answer_does_not_break_followup(staff_client):
    body = {"mode": "staff", "messages": [
        {"role": "user", "content": "What does 205-7 say?"},
        {"role": "assistant", "content": "x" * 16_000},
        {"role": "user", "content": "and the penalty?"},
    ]}
    r = staff_client.post("/api/chat", json=body, headers=CSRF)
    assert r.status_code == 200, r.text[:300]
    assert r.headers["cache-control"] == "no-store"


def test_user_message_cap_still_holds(client):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "x" * 9000}]})
    assert r.status_code == 422


def test_question_log_purge(monkeypatch):
    monkeypatch.setattr(config, "QUESTION_LOG_RETENTION_DAYS", 30)
    monkeypatch.setattr(chat_router, "_purged_through", None)
    today = dt.date(2026, 10, 3)

    async def go():
        s = get_store()
        await s.put("questions", "2026-08-01", "a", {"question": "old"})
        await s.put("questions", "2026-09-10", "b", {"question": "recent"})
        n = await chat_router.purge_questions(today)
        return n, await s.query("questions")

    n, left = asyncio.run(go())
    assert n == 1 and [r["_rk"] for r in left] == ["b"]


# ---------------------------------------------------------------- drafts


def test_docx_export_with_control_characters(staff_client):
    tid = staff_client.get("/api/staff/drafts/templates").json()["templates"][0]["id"]
    r = staff_client.post(
        "/api/staff/drafts",
        json={"template": tid, "values": {}, "title": "T\x01", "body": "Line one\x0bline two\x0c\x01 end\n"},
        headers=CSRF,
    )
    assert r.status_code == 201, r.text
    d = r.json()
    assert "\x0b" not in d["body"] and "\x01" not in d["body"] and "Line one\nline two" in d["body"]
    r = staff_client.get(f"/api/staff/drafts/{d['id']}/export.docx")
    assert r.status_code == 200


def test_docx_export_of_a_stored_dirty_draft(staff_client):
    tid = staff_client.get("/api/staff/drafts/templates").json()["templates"][0]["id"]
    d = staff_client.post("/api/staff/drafts", json={"template": tid, "values": {}}, headers=CSRF).json()

    async def dirty():
        s = get_store()
        e = await s.get("drafts", "draft", d["id"])
        e["body"] = "Old\x0bdraft\x02"
        await s.put("drafts", "draft", d["id"], e)

    asyncio.run(dirty())
    assert staff_client.get(f"/api/staff/drafts/{d['id']}/export.docx").status_code == 200


def test_prior_conviction_text_follows_violation_type(staff_client):
    from app.routers import drafts as d

    t = d.get_template("nov-1")
    zoning = d.render(t, {"violation_type": "zoning_specific", "prior_conviction": "yes"}).body
    assert "§ 275-6.1A(3)(b)" in zoning
    pm = d.render(t, {"violation_type": "property_maintenance", "prior_conviction": "yes"}).body
    assert "may not exceed $25,000" not in pm and "[VERIFY: a prior conviction was marked" in pm


# ---------------------------------------------------------------- store


def test_table_chunks_fit_utf16_limits():
    e = encode_entity("p", "r", {"answer": "\U0001F4CC" * 40_000 + "ab"})
    for i in range(e["chunks"]):
        assert len(e[f"data_{i}"].encode("utf-16-le")) <= 64_000
    assert decode_entity(e)["answer"] == "\U0001F4CC" * 40_000 + "ab"


def test_too_large_entity_is_413(staff_client, monkeypatch):
    # Counted in UTF-16 units: 120,000 emoji are 240,000 units.
    monkeypatch.setattr(app_store, "MAX_JSON", 200_000)
    tid = staff_client.get("/api/staff/drafts/templates").json()["templates"][0]["id"]
    r = staff_client.post(
        "/api/staff/drafts", json={"template": tid, "values": {}, "body": "\U0001F4CC" * 120_000}, headers=CSRF
    )
    assert r.status_code == 413, r.status_code


# ---------------------------------------------------------------- case notebooks


class SlowStore:
    """Wraps the SQLite store and yields to the loop on every call."""

    def __init__(self, inner, item_delay=0.05):
        self.inner = inner
        self.item_delay = item_delay

    async def put(self, table, *a, **k):
        await asyncio.sleep(self.item_delay if table == "caseitems" else 0.05)
        return await self.inner.put(table, *a, **k)

    async def get(self, *a, **k):
        await asyncio.sleep(0.05)
        return await self.inner.get(*a, **k)

    async def query(self, *a, **k):
        await asyncio.sleep(0.05)
        return await self.inner.query(*a, **k)

    async def delete(self, *a, **k):
        await asyncio.sleep(0.05)
        return await self.inner.delete(*a, **k)


def _run_with(store, coro_fn):
    inner = get_store()
    app_store.set_store(store(inner))
    try:
        return asyncio.run(coro_fn(inner))
    finally:
        app_store.set_store(inner)


def test_patch_not_lost_while_item_saved():
    async def go(inner):
        case = await notebooks.create_case(notebooks.CaseIn(address="1 Main St"), user="alice")
        cid = case["id"]
        add = asyncio.create_task(notebooks.add_item(cid, notebooks.NoteIn(kind="note", text="hi"), user="alice"))
        await asyncio.sleep(0.06)
        await notebooks.update_case(cid, notebooks.CasePatch(status="closed"), user="bob")
        await add
        return await inner.get("cases", "case", cid)

    final = _run_with(SlowStore, go)
    assert final["status"] == "closed"


def test_deleted_case_stays_deleted_during_item_save():
    async def go(inner):
        case = await notebooks.create_case(notebooks.CaseIn(address="1 Main St"), user="alice")
        cid = case["id"]
        add = asyncio.create_task(notebooks.add_item(cid, notebooks.NoteIn(kind="note", text="hi"), user="alice"))
        await asyncio.sleep(0.1)
        await notebooks.delete_case(cid, user="alice")
        try:
            await add
        except Exception:  # noqa: BLE001
            pass
        return await inner.get("cases", "case", cid), await inner.query("caseitems", pk=cid)

    left, items = _run_with(lambda s: SlowStore(s, item_delay=0.3), go)
    assert left is None and items == []


def test_next_deadline_uses_maine_date(monkeypatch):
    class Fixed(dt.datetime):
        @classmethod
        def now(cls, tz=None):
            # 22:30 in Maine on Oct 3 is 02:30 UTC on Oct 4.
            return dt.datetime(2026, 10, 4, 2, 30, tzinfo=dt.timezone.utc).astimezone(tz)

    monkeypatch.setattr(notebooks, "datetime", Fixed)
    counts = notebooks._counts([{"kind": "deadline", "date": "2026-10-03", "label": "today"}])
    assert counts["next_deadline"] == {"date": "2026-10-03", "label": "today"}


# ---------------------------------------------------------------- headers and logs


def test_staff_api_is_no_store_and_logs_no_query(staff_client, caplog):
    caplog.set_level("INFO", logger="app.access")
    r = staff_client.get("/api/staff/cases?q=Jane+Doe+44+Elm")
    assert r.headers["cache-control"] == "no-store"
    lines = [rec.getMessage() for rec in caplog.records if rec.name == "app.access"]
    assert any("/api/staff/cases" in x for x in lines) and not any("Jane" in x for x in lines)


def test_failed_login_does_not_log_the_username(client, caplog):
    caplog.set_level("WARNING", logger="app.staff")
    client.post("/api/staff/login", json={"username": "MyS3cretPassw0rd!", "password": "x"}, headers=CSRF)
    text = " ".join(rec.getMessage() for rec in caplog.records)
    assert "staff login failed" in text and "MyS3cretPassw0rd" not in text


def test_csp_covers_scripts(client):
    csp = client.get("/").headers["content-security-policy"]
    assert "script-src 'self'" in csp and "object-src 'none'" in csp
    assert csp.endswith("frame-ancestors 'none'")


# ---------------------------------------------------------------- lookup and refresh


def test_court_rule_citation_forms():
    from app.search import normalize_citation

    for c in ("Me. R. Civ. P. 80K", "Maine Rules of Civil Procedure 80K", "M.R. Civ. P. 80K"):
        assert normalize_citation(c).citation == "M.R. Civ. P. 80K", c


def test_change_alert_read_failure_does_not_stop_the_push(monkeypatch, tmp_path):
    from ecode import azure

    calls = []

    def boom(*a, **k):
        raise RuntimeError("403 Forbidden")

    monkeypatch.setattr(azure, "index_rows", boom)

    class R:
        status_code = 200
        headers: dict = {}

        def __init__(self, body=None):
            self._b = body or {"value": []}

        def json(self):
            return self._b

        text = ""

    def fake_put(url, **k):
        calls.append(("put", url))
        return R()

    def fake_post(url, json=None, **k):
        calls.append(("post", url))
        if "/docs/index" in url:
            return R({"value": [{"status": True} for _ in json["value"]]})
        if "/embeddings" in url:
            return R({"data": [{"index": i, "embedding": [0.0]} for i in range(len(json["input"]))]})
        return R({"value": []})

    monkeypatch.setattr(azure.requests, "put", fake_put)
    monkeypatch.setattr(azure.requests, "post", fake_post)
    for k, v in {
        "AZURE_SEARCH_ENDPOINT": "https://s", "AZURE_SEARCH_API_KEY": "k", "AZURE_OPENAI_ENDPOINT": "https://o",
        "AZURE_OPENAI_API_KEY": "k", "AZURE_OPENAI_EMBEDDING_DEPLOYMENT": "e", "AZURE_SEARCH_INDEX": "idx",
    }.items():
        monkeypatch.setenv(k, v)
    chunks = tmp_path / "chunks.jsonl"
    chunks.write_text('{"id": "code-1", "content": "x", "source_type": "code"}\n')
    azure.main(["push", "--chunks", str(chunks), "--changes-to", "print", "--index-update", "never"])
    assert not any(c[0] == "put" for c in calls), "never mode must not PUT the index"
    assert any("/docs/index" in c[1] for c in calls)

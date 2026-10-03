"""Case notebooks: /api/staff/cases ... (app/routers/notebooks.py)."""

from __future__ import annotations

import asyncio

import pytest

from app import store
from tests.conftest import CSRF

CASE = {
    "address": "12 Main Street",
    "map_lot": "041-112",
    "owner": "Main Place LLC",
    "tags": ["zoning", "building", "zoning"],
    "status": "open",
    "summary": "Shed built inside the side setback.",
}


def make_case(c, **over) -> dict:
    r = c.post("/api/staff/cases", json={**CASE, **over}, headers=CSRF)
    assert r.status_code == 201, r.text
    return r.json()


def add(c, case_id: str, body: dict, code: int = 201) -> dict:
    r = c.post(f"/api/staff/cases/{case_id}/items", json=body, headers=CSRF)
    assert r.status_code == code, r.text
    return r.json()


# ---------------------------------------------------------------- auth and CSRF

ENDPOINTS = [
    ("GET", "/api/staff/cases"),
    ("POST", "/api/staff/cases"),
    ("GET", "/api/staff/cases/2026-abcdef"),
    ("PATCH", "/api/staff/cases/2026-abcdef"),
    ("DELETE", "/api/staff/cases/2026-abcdef"),
    ("GET", "/api/staff/cases/2026-abcdef/items"),
    ("POST", "/api/staff/cases/2026-abcdef/items"),
    ("DELETE", "/api/staff/cases/2026-abcdef/items/1-abc"),
    ("GET", "/api/staff/cases/2026-abcdef/export.md"),
    ("GET", "/api/staff/case-options"),
]


@pytest.mark.parametrize("method,path", ENDPOINTS)
def test_needs_session(client, method, path):
    r = client.request(method, path, json={} if method in ("POST", "PATCH") else None, headers=CSRF)
    assert r.status_code == 401
    assert r.json()["detail"] == "Staff sign-in required."


@pytest.mark.parametrize("method,path", [e for e in ENDPOINTS if e[0] != "GET"])
def test_writes_need_csrf_header(staff_client, method, path):
    r = staff_client.request(method, path, json=CASE if method in ("POST", "PATCH") else None)
    assert r.status_code == 403
    assert store.get_store() is not None
    assert staff_client.get("/api/staff/cases").json()["cases"] == []


def test_csrf_on_real_case(staff_client):
    case = make_case(staff_client)
    cid = case["id"]
    assert staff_client.patch(f"/api/staff/cases/{cid}", json={"status": "closed"}).status_code == 403
    assert staff_client.post(f"/api/staff/cases/{cid}/items", json={"kind": "note", "text": "x"}).status_code == 403
    assert staff_client.delete(f"/api/staff/cases/{cid}").status_code == 403
    got = staff_client.get(f"/api/staff/cases/{cid}").json()
    assert got["status"] == "open" and got["items"] == []


# ---------------------------------------------------------------- cases


def test_create_and_get(staff_client):
    case = make_case(staff_client)
    assert case["id"].startswith("20") and len(case["id"]) == 11
    assert case["address"] == "12 Main Street"
    assert case["tags"] == ["building", "zoning"]  # canonical order, no repeats
    assert case["created_by"] == "alice" and case["updated_by"] == "alice"
    assert case["created_at"] and case["updated_at"]
    assert not any(k.startswith("_") for k in case)

    got = staff_client.get(f"/api/staff/cases/{case['id']}").json()
    assert got["owner"] == "Main Place LLC"
    assert got["items"] == [] and got["item_count"] == 0 and got["next_deadline"] is None


def test_create_defaults_and_strip(staff_client):
    r = staff_client.post("/api/staff/cases", json={"address": "  3 Elm St  "}, headers=CSRF)
    assert r.status_code == 201
    assert r.json()["address"] == "3 Elm St"
    assert r.json()["status"] == "open" and r.json()["tags"] == []


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"address": ""},
        {"address": "   "},
        {"address": "x" * 201},
        {"address": "1 A St", "status": "pending"},
        {"address": "1 A St", "tags": ["arson"]},
        {"address": "1 A St", "unknown": 1},
    ],
)
def test_create_validation(staff_client, body):
    assert staff_client.post("/api/staff/cases", json=body, headers=CSRF).status_code == 422


def test_get_missing(staff_client):
    assert staff_client.get("/api/staff/cases/2026-000000").status_code == 404
    assert staff_client.get("/api/staff/cases/bad%23id").status_code == 404


def test_list_search_and_filters(staff_client):
    a = make_case(staff_client)
    b = make_case(staff_client, address="224 County Road", owner="Unknown", tags=["dangerous-building"], status="monitoring")
    c = make_case(staff_client, address="6 Main Place", map_lot="019-020", tags=["property-maintenance"], status="closed")
    make_case(staff_client, address="1 Elm St", owner="", summary="", tags=["property-maintenance"])

    def ids(**params):
        r = staff_client.get("/api/staff/cases", params=params)
        assert r.status_code == 200, r.text
        return {x["id"] for x in r.json()["cases"]}

    assert len(ids()) == 4
    assert ids(status="open") - {a["id"]} and a["id"] in ids(status="open")
    assert ids(status="monitoring") == {b["id"]}
    assert ids(q="main") == {a["id"], c["id"]}
    assert ids(q="MAIN place") == {a["id"], c["id"]}  # owner of a is Main Place LLC
    assert ids(q="019-020") == {c["id"]}
    assert ids(q="county", status="closed") == set()
    assert ids(q=b["id"]) == {b["id"]}
    assert ids(tag="dangerous-building") == {b["id"]}
    assert ids(q="dangerous") == set()  # tags are filtered with tag=, not searched
    assert staff_client.get("/api/staff/cases", params={"status": "nope"}).status_code == 422
    assert staff_client.get("/api/staff/cases").json()["total"] == 4


def test_list_sorted_by_last_change_with_counts(staff_client):
    a = make_case(staff_client)
    b = make_case(staff_client, address="2 B St")
    add(staff_client, a["id"], {"kind": "deadline", "label": "Re-inspect", "date": "2999-01-02", "citation": "§ 205-7"})
    add(staff_client, a["id"], {"kind": "deadline", "label": "Old", "date": "2000-01-02"})
    add(staff_client, a["id"], {"kind": "note", "text": "Called owner."})
    cases = staff_client.get("/api/staff/cases").json()["cases"]
    first = cases[0]
    assert first["id"] == a["id"]  # touched last
    assert first["item_count"] == 3
    assert first["kinds"] == {"deadline": 2, "note": 1}
    assert first["next_deadline"] == {"date": "2999-01-02", "label": "Re-inspect"}
    assert next(x for x in cases if x["id"] == b["id"])["item_count"] == 0


def test_patch(staff_client, monkeypatch):
    case = make_case(staff_client)
    r = staff_client.patch(
        f"/api/staff/cases/{case['id']}", json={"status": "monitoring", "tags": ["shoreland"], "owner": ""}, headers=CSRF
    )
    assert r.status_code == 200, r.text
    got = r.json()
    assert got["status"] == "monitoring" and got["tags"] == ["shoreland"] and got["owner"] == ""
    assert got["address"] == "12 Main Street"  # untouched
    assert got["created_at"] == case["created_at"] and got["created_by"] == "alice"
    assert got["updated_by"] == "alice"


@pytest.mark.parametrize(
    "body",
    [{"status": "gone"}, {"address": ""}, {"address": None}, {"tags": ["x"]}, {"id": "other"}, {"created_by": "mallory"}],
)
def test_patch_validation(staff_client, body):
    case = make_case(staff_client)
    assert staff_client.patch(f"/api/staff/cases/{case['id']}", json=body, headers=CSRF).status_code == 422


def test_patch_missing(staff_client):
    assert staff_client.patch("/api/staff/cases/2026-000000", json={"status": "closed"}, headers=CSRF).status_code == 404


def test_delete_case_removes_items(staff_client):
    case = make_case(staff_client)
    other = make_case(staff_client, address="9 Other Rd")
    add(staff_client, case["id"], {"kind": "note", "text": "one"})
    add(staff_client, case["id"], {"kind": "note", "text": "two"})
    add(staff_client, other["id"], {"kind": "note", "text": "keep"})
    r = staff_client.delete(f"/api/staff/cases/{case['id']}", headers=CSRF)
    assert r.status_code == 200 and r.json() == {"ok": True, "items_deleted": 2}
    assert staff_client.get(f"/api/staff/cases/{case['id']}").status_code == 404
    assert asyncio.run(store.get_store().query("caseitems", pk=case["id"])) == []
    assert len(staff_client.get(f"/api/staff/cases/{other['id']}/items").json()["items"]) == 1
    assert staff_client.delete(f"/api/staff/cases/{case['id']}", headers=CSRF).status_code == 404


# ---------------------------------------------------------------- items


def test_note_item(staff_client):
    case = make_case(staff_client)
    item = add(staff_client, case["id"], {"kind": "note", "text": "  Site visit: shed still there.  "})
    assert item["kind"] == "note" and item["text"] == "Site visit: shed still there."
    assert item["created_by"] == "alice" and item["case_id"] == case["id"] and item["id"]
    items = staff_client.get(f"/api/staff/cases/{case['id']}/items").json()["items"]
    assert [i["id"] for i in items] == [item["id"]]
    after = staff_client.get(f"/api/staff/cases/{case['id']}").json()
    assert after["updated_at"] >= case["updated_at"]


def test_items_keep_order(staff_client):
    case = make_case(staff_client)
    ids = [add(staff_client, case["id"], {"kind": "note", "text": f"n{i}"})["id"] for i in range(4)]
    got = [i["id"] for i in staff_client.get(f"/api/staff/cases/{case['id']}/items").json()["items"]]
    assert got == ids


def test_deadline_item_contract(staff_client):
    case = make_case(staff_client)
    body = {"kind": "deadline", "label": "Appeal period ends", "date": "2026-11-02", "citation": "§ 275-6.2"}
    item = add(staff_client, case["id"], body)
    assert {k: item[k] for k in body} == body
    add(staff_client, case["id"], {**body, "date": "02/11/2026"}, code=422)
    add(staff_client, case["id"], {**body, "date": "2026-02-30"}, code=422)
    add(staff_client, case["id"], {**body, "label": ""}, code=422)
    add(staff_client, case["id"], {"kind": "deadline", "label": "x"}, code=422)


def test_unknown_kind(staff_client):
    case = make_case(staff_client)
    add(staff_client, case["id"], {"kind": "upload", "file": "x"}, code=422)
    add(staff_client, case["id"], {"kind": "note", "text": "x", "extra": 1}, code=422)
    add(staff_client, case["id"], {"kind": "note", "text": ""}, code=422)


def test_item_on_missing_case(staff_client):
    add(staff_client, "2026-000000", {"kind": "note", "text": "x"}, code=404)
    assert staff_client.get("/api/staff/cases/2026-000000/items").status_code == 404


def test_answer_item_from_stored_answer(staff_client):
    case = make_case(staff_client)
    # A staff chat stores its answer under table `answers` (pk = user).
    r = staff_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "What are the side setbacks?"}], "mode": "staff", "case_id": case["id"]},
        headers=CSRF,
    )
    assert r.status_code == 200
    meta = next(line for line in r.text.split("\n\n") if line.startswith("event: meta"))
    import json

    answer_id = json.loads(meta.split("data: ", 1)[1])["answer_id"]
    item = add(staff_client, case["id"], {"kind": "answer", "answer_id": answer_id, "note": "For the NOV."})
    assert item["kind"] == "answer" and item["answer_id"] == answer_id
    assert item["question"] == "What are the side setbacks?"
    assert item["answer"] and item["sources"] and "n" in item["sources"][0]
    assert item["note"] == "For the NOV." and item["stamp"].startswith("Research aid")


def test_answer_item_inline_and_errors(staff_client):
    case = make_case(staff_client)
    srcs = [{"n": 1, "citation": "§ 205-7", "title": "Notice", "url": "https://ecode360.com/x", "junk": "ignored"}]
    item = add(staff_client, case["id"], {"kind": "answer", "question": "Q", "answer": "A [1]", "sources": srcs})
    assert item["sources"] == [{"n": 1, "citation": "§ 205-7", "title": "Notice", "url": "https://ecode360.com/x"}]
    # Unknown id with no inline text: 404. Nothing at all: 422.
    add(staff_client, case["id"], {"kind": "answer", "answer_id": "ab" * 16}, code=404)
    add(staff_client, case["id"], {"kind": "answer"}, code=422)
    add(staff_client, case["id"], {"kind": "answer", "answer_id": "not-hex"}, code=422)
    # Unknown id with inline text falls back to the inline copy.
    item = add(staff_client, case["id"], {"kind": "answer", "answer_id": "cd" * 16, "answer": "B", "question": "Q2"})
    assert item["answer"] == "B" and item["answer_id"] == "cd" * 16


def test_answer_of_another_user_is_not_found(staff_client):
    case = make_case(staff_client)
    asyncio.run(store.get_store().put("answers", "bob", "ef" * 16, {"question": "q", "answer": "secret", "sources": []}))
    add(staff_client, case["id"], {"kind": "answer", "answer_id": "ef" * 16}, code=404)


def test_draft_item(staff_client):
    case = make_case(staff_client)
    item = add(staff_client, case["id"], {"kind": "draft", "draft_id": "d-123", "title": "First NOV", "template": "nov1"})
    assert item["draft_id"] == "d-123" and item["title"] == "First NOV"
    add(staff_client, case["id"], {"kind": "draft", "draft_id": "bad/id"}, code=422)


def test_delete_item(staff_client):
    case = make_case(staff_client)
    a = add(staff_client, case["id"], {"kind": "note", "text": "a"})
    b = add(staff_client, case["id"], {"kind": "note", "text": "b"})
    r = staff_client.delete(f"/api/staff/cases/{case['id']}/items/{a['id']}", headers=CSRF)
    assert r.status_code == 200 and r.json() == {"ok": True}
    items = staff_client.get(f"/api/staff/cases/{case['id']}/items").json()["items"]
    assert [i["id"] for i in items] == [b["id"]]
    assert staff_client.delete(f"/api/staff/cases/{case['id']}/items/{a['id']}", headers=CSRF).status_code == 404
    assert staff_client.delete(f"/api/staff/cases/2026-000000/items/{b['id']}", headers=CSRF).status_code == 404


def test_item_limit(staff_client, monkeypatch):
    from app.routers import notebooks

    monkeypatch.setattr(notebooks, "ITEM_LIMIT", 2)
    case = make_case(staff_client)
    add(staff_client, case["id"], {"kind": "note", "text": "a"})
    add(staff_client, case["id"], {"kind": "note", "text": "b"})
    add(staff_client, case["id"], {"kind": "note", "text": "c"}, code=409)


# ---------------------------------------------------------------- export and options


def test_export_markdown(staff_client):
    case = make_case(staff_client, title="Shed in setback")
    add(staff_client, case["id"], {"kind": "note", "text": "Called the owner."})
    add(staff_client, case["id"], {"kind": "deadline", "label": "Compliance due", "date": "2026-11-02", "citation": "§ 205-7"})
    add(
        staff_client,
        case["id"],
        {"kind": "answer", "question": "Setback?", "answer": "Ten feet [1].", "sources": [{"n": 1, "citation": "§ 275-5", "url": "https://e/x"}]},
    )
    add(staff_client, case["id"], {"kind": "draft", "draft_id": "d1", "title": "First NOV"})
    r = staff_client.get(f"/api/staff/cases/{case['id']}/export.md")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/markdown")
    assert f'filename="case-{case["id"]}.md"' in r.headers["content-disposition"]
    md = r.text
    assert md.startswith(f"# Case {case['id']}: Shed in setback\n")
    for want in (
        "- **Address:** 12 Main Street",
        "- **Map/lot:** 041-112",
        "- **Type:** Building, Zoning",
        "## Deadlines",
        "- **2026-11-02**: Compliance due (§ 205-7)",
        "## Drafts",
        "Called the owner.",
        "**Question:** Setback?",
        "1. § 275-5 <https://e/x>",
        "*Research aid",
    ):
        assert want in md, want
    assert "—" not in md  # no em dashes


def test_export_missing(staff_client):
    assert staff_client.get("/api/staff/cases/2026-000000/export.md").status_code == 404


def test_case_options(staff_client):
    r = staff_client.get("/api/staff/case-options").json()
    assert [t["value"] for t in r["tags"]][:3] == ["building", "zoning", "property-maintenance"]
    assert len(r["tags"]) == 11
    assert r["statuses"] == ["open", "monitoring", "closed"]

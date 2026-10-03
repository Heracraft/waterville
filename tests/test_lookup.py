"""Citation lookup (B3) and facets (B4): GET /api/lookup?cite= and GET /api/facets."""

from __future__ import annotations

import json

import httpx
import pytest

from app import config, search
from app.routers import lookup as lookup_router


@pytest.fixture(autouse=True)
def fresh():
    search.clear_facet_cache()
    lookup_router.public_limiter.reset()
    yield
    search.clear_facet_cache()
    lookup_router.public_limiter.reset()


# ------------------------------------------------ normalization


@pytest.mark.parametrize(
    "raw,kind,citation,sub",
    [
        # City Code sections
        ("205-7", "section", "§ 205-7", ""),
        ("sec. 205-7", "section", "§ 205-7", ""),
        ("Sec 205-7", "section", "§ 205-7", ""),
        ("section 205-7", "section", "§ 205-7", ""),
        ("§ 205-7", "section", "§ 205-7", ""),
        ("§205-7", "section", "§ 205-7", ""),
        ("§§ 205-7", "section", "§ 205-7", ""),
        ("§ 205-7A", "section", "§ 205-7", "A"),
        ("§ 205-7 A", "section", "§ 205-7", "A"),
        ("205-7a", "section", "§ 205-7", "A"),
        ("205-7.", "section", "§ 205-7", ""),
        ("205 - 7", "section", "§ 205-7", ""),
        ("§ 205–7", "section", "§ 205-7", ""),
        ("205-07", "section", "§ 205-7", ""),
        ("275-4.27K(3)", "section", "§ 275-4.27", "K(3)"),
        ("275-4.27 k (3)", "section", "§ 275-4.27", "K(3)"),
        ("§ 275-6.2E(4)(g)", "section", "§ 275-6.2", "E(4)(g)"),
        ("§ 205-7(A)(1)", "section", "§ 205-7", "A(1)"),
        ("§ 205-4C", "section", "§ 205-4", "C"),
        ("275-4.9.1", "section", "§ 275-4.9.1", ""),
        ("§ DL-1", "section", "§ DL-1", ""),
        ("dl-2", "section", "§ DL-2", ""),
        ("Waterville City Code § 205-7", "section", "§ 205-7", ""),
        ("City Code, § 275-4.33", "section", "§ 275-4.33", ""),
        ("Code § 1-12", "section", "§ 1-12", ""),
        # Charter
        ("Charter Art. IV, § 9", "charter", "Charter Art. IV, § 9", ""),
        ("charter art iv sec 9", "charter", "Charter Art. IV, § 9", ""),
        ("Charter Article 4, Section 9", "charter", "Charter Art. IV, § 9", ""),
        ("City Charter Art. XI § 2", "charter", "Charter Art. XI, § 2", ""),
        ("Art. IX, § 13", "charter", "Charter Art. IX, § 13", ""),
        # Maine statutes
        ("30-A M.R.S. § 4452", "statute", "30-A M.R.S. § 4452", ""),
        ("30-A §4452", "statute", "30-A M.R.S. § 4452", ""),
        ("30-A § 4452(3)", "statute", "30-A M.R.S. § 4452", "(3)"),
        ("30-A M.R.S.A. § 4452(3)(B)", "statute", "30-A M.R.S. § 4452", "(3)(B)"),
        ("30-a mrsa 4452", "statute", "30-A M.R.S. § 4452", ""),
        ("30-A MRS 4452", "statute", "30-A M.R.S. § 4452", ""),
        ("Title 30-A, section 4452", "statute", "30-A M.R.S. § 4452", ""),
        ("17 M.R.S. § 2851", "statute", "17 M.R.S. § 2851", ""),
        ("38 MRS 436-a", "statute", "38 M.R.S. § 436-A", ""),
        ("38 M.R.S. § 436-A", "statute", "38 M.R.S. § 436-A", ""),
        # Maine rules
        ("16-642 CMR ch. 3", "rule", "16-642 CMR ch. 3", ""),
        ("16-642 C.M.R. c. 3", "rule", "16-642 CMR ch. 3", ""),
        ("08-003 CMR chapter 1", "rule", "08-003 CMR ch. 1", ""),
        ("10-144 CMR 241", "rule", "10-144 CMR ch. 241", ""),
        # Chapters and new laws
        ("Chapter 205", "chapter", "Chapter 205", ""),
        ("ch. 275", "chapter", "Chapter 275", ""),
        ("Chapter 205. Property Maintenance", "chapter", "Chapter 205", ""),
        ("Chapter C", "chapter", "Chapter C", ""),
        ("Ord. No. 167-2026", "ordinance", "Ord. No. 167-2026", ""),
        ("ordinance 167-2026", "ordinance", "Ord. No. 167-2026", ""),
    ],
)
def test_normalize_citation(raw, kind, citation, sub):
    c = search.normalize_citation(raw)
    assert (c.kind, c.citation, c.subsection) == (kind, citation, sub)


@pytest.mark.parametrize(
    "raw",
    [
        "",
        "   ",
        "205",
        "hello world",
        "Charter Art. IV",
        "205-7 and 205-8",
        "205-7' or 1 eq 1 or '",
        "§ 205-7') or (citation eq 'x",
        "x" * 81,
        "Charter Art. MMMM, § 1",
    ],
)
def test_normalize_citation_rejects(raw):
    with pytest.raises(ValueError):
        search.normalize_citation(raw)


def test_citation_odata_escapes_quotes():
    assert search.Citation("section", "§ O'Brien").odata() == "citation eq '§ O''Brien'"
    assert search.Citation("chapter", "Chapter 2'", chapter="2'").odata() == (
        "chapter_number eq '2''' and node_type eq 'chapter'"
    )


def test_parents():
    c = search.normalize_citation("275-4.9.1.2")
    assert [p.citation for p in c.parents()] == ["§ 275-4.9.1", "§ 275-4.9"]
    assert search.normalize_citation("205-7").parents() == []


# ------------------------------------------------ GET /api/lookup


def test_lookup_single_chunk(client):
    r = client.get("/api/lookup", params={"cite": "sec. 205-7"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["citation"] == "§ 205-7" and body["kind"] == "section"
    assert body["chunk_count"] == 1 and body["chunks"][0]["chunk_index"] == 0
    assert body["url"] == "https://ecode360.com/38529530"
    assert body["legislation_through"] == "08-05-2026"
    assert body["chapter_title"] == "Property Maintenance"
    assert body["text"] and not body["text"].startswith("City of Waterville")
    assert body["parent"] is False


def test_lookup_returns_every_chunk_in_order(client):
    r = client.get("/api/lookup", params={"cite": "§ 275-3.2"})
    body = r.json()
    assert body["chunk_count"] == 15
    assert [c["chunk_index"] for c in body["chunks"]] == list(range(15))
    assert body["text"] == "\n\n".join(c["text"] for c in body["chunks"])


def test_lookup_keeps_subsection(client):
    body = client.get("/api/lookup", params={"cite": "275-6.2E(4)(g)"}).json()
    assert body["citation"] == "§ 275-6.2" and body["subsection"] == "E(4)(g)"
    assert body["chunk_count"] == 6


def test_lookup_falls_back_to_parent(client):
    body = client.get("/api/lookup", params={"cite": "§ 275-6.2.1.3"}).json()
    assert body["citation"] == "§ 275-6.2"
    assert body["requested"] == "§ 275-6.2.1.3" and body["parent"] is True


def test_lookup_chapter_lists_sections_in_code_order(client):
    body = client.get("/api/lookup", params={"cite": "ch. 127"}).json()
    assert body["kind"] == "chapter" and body["citation"] == "Chapter 127. Building and Energy Code"
    cites = [s["citation"] for s in body["sections"]]
    assert cites == [f"§ 127-{i}" for i in range(1, 11)]


def test_lookup_new_law(client):
    body = client.get("/api/lookup", params={"cite": "Ord 167-2026"}).json()
    assert body["citation"] == "Ord. No. 167-2026" and body["source_type"] == "new_law"
    assert body["label"] == "New Law, not yet codified"


def test_lookup_missing_is_404(client):
    r = client.get("/api/lookup", params={"cite": "§ 205-99"})
    assert r.status_code == 404
    assert r.json()["detail"] == "§ 205-99 is not in the sources."
    r = client.get("/api/lookup", params={"cite": "30-A §4451"})
    assert r.status_code == 404 and "30-A M.R.S. § 4451" in r.json()["detail"]


@pytest.mark.parametrize("cite", ["", "hello", "205-7' or 1 eq 1 or '"])
def test_lookup_bad_citation_is_400(client, cite):
    r = client.get("/api/lookup", params={"cite": cite})
    assert r.status_code == 400
    assert r.json()["detail"]


def test_lookup_too_long_is_422(client):
    assert client.get("/api/lookup", params={"cite": "x" * 300}).status_code == 422


def _with_staff_note(monkeypatch):
    docs = search.fake_docs()
    docs.append(
        {
            "id": "staffnote-1-0",
            "source_type": "staff_note",
            "citation": "§ 205-7",
            "title": "Staff note on § 205-7",
            "content": "Staff note\nNotes\n\nCheck the mortgagee notice.",
            "chunk_index": 1,
            "chapter_number": "205",
        }
    )
    monkeypatch.setattr(search, "_fixture_docs", lambda: tuple(docs))


def test_staff_notes_only_for_staff(client, staff_client, monkeypatch):
    _with_staff_note(monkeypatch)
    staff_body = staff_client.get("/api/lookup", params={"cite": "205-7"}).json()
    assert staff_body["chunk_count"] == 2
    staff_client.post("/api/staff/logout", headers={"X-Requested-With": "wv"})
    client.cookies.clear()
    public_body = client.get("/api/lookup", params={"cite": "205-7"}).json()
    assert public_body["chunk_count"] == 1
    assert all("Staff note" not in c["text"] for c in public_body["chunks"])


def test_public_lookup_rate_limited(client, monkeypatch):
    monkeypatch.setattr(lookup_router.public_limiter, "_limit", 2)
    assert client.get("/api/lookup", params={"cite": "205-7"}).status_code == 200
    assert client.get("/api/lookup", params={"cite": "205-7"}).status_code == 200
    assert client.get("/api/lookup", params={"cite": "205-7"}).status_code == 429


def test_staff_lookup_skips_public_limit(staff_client, monkeypatch):
    monkeypatch.setattr(lookup_router.public_limiter, "_limit", 0)
    assert staff_client.get("/api/lookup", params={"cite": "205-7"}).status_code == 200


async def test_real_lookup_is_filter_only(monkeypatch):
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(
            200,
            json={"value": [
                {"id": "b", "citation": "§ 205-7", "content": "two", "chunk_index": 1},
                {"id": "a", "citation": "§ 205-7", "content": "one", "chunk_index": 0},
            ]},
        )

    monkeypatch.setattr(config, "FAKE_AZURE", False)
    monkeypatch.setattr(config, "SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setattr(search.search_auth, "key", "test-key")
    monkeypatch.setattr(search, "http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    cite, result = await search.lookup_citation("§ 205-7A")
    assert cite.subsection == "A"
    body = seen[0]
    assert body["search"] == "*" and body["filter"] == "citation eq '§ 205-7'"
    assert body["orderby"] == "chunk_index"
    assert "queryType" not in body and "vectorQueries" not in body
    assert "legislation_through" in body["select"].split(",")
    assert [c["text"] for c in result["chunks"]] == ["one", "two"]


# ------------------------------------------------ GET /api/facets


def test_facets(client):
    r = client.get("/api/facets")
    assert r.status_code == 200
    body = r.json()
    chapters = body["chapters"]
    values = [c["value"] for c in chapters]
    assert values == sorted(values, key=lambda v: int(v))
    by = {c["value"]: c for c in chapters}
    assert by["205"]["title"] == "Property Maintenance"
    # No chapter heading row in the fixtures: the title comes from a section.
    assert by["173"]["title"] == "Licenses and Permits"
    assert by["275"]["count"] > 10
    types = {t["value"]: t for t in body["source_types"]}
    # Public facets never list staff notes, though the fixtures hold one.
    order = ["code", "attachment", "new_law", "city_form", "state_statute", "state_rule"]
    assert set(types) == set(order)
    assert types["code"]["name"] == "City Code"
    assert [t["value"] for t in body["source_types"]] == order
    assert body["legislation_through"] == "08-05-2026"


def test_facets_hide_staff_notes_from_public(client, staff_client, monkeypatch):
    _with_staff_note(monkeypatch)
    staff_types = [t["value"] for t in staff_client.get("/api/facets").json()["source_types"]]
    assert "staff_note" in staff_types
    staff_client.post("/api/staff/logout", headers={"X-Requested-With": "wv"})
    client.cookies.clear()
    public_types = [t["value"] for t in client.get("/api/facets").json()["source_types"]]
    assert "staff_note" not in public_types


def test_facets_cached(client, monkeypatch):
    client.get("/api/facets")
    calls = []

    async def boom(*a, **k):
        calls.append(1)
        raise AssertionError("not cached")

    monkeypatch.setattr(search, "facets", boom)
    assert client.get("/api/facets").status_code == 200
    assert not calls

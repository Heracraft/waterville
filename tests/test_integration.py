"""Cross-feature checks added at integration: court rule citations and
renumbered rule fallback in the desk lookup."""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app import search
from app.routers import lookup as lookup_router


@pytest.mark.parametrize(
    "raw, citation, sub",
    [
        ("M.R. Civ. P. 80K", "M.R. Civ. P. 80K", ""),
        ("MRCivP 80k(c)", "M.R. Civ. P. 80K", "(c)"),
        ("M.R.Civ.P. 80E", "M.R. Civ. P. 80E", ""),
        ("Rule 80B", "M.R. Civ. P. 80B", ""),
        ("civil rule 80K(b)(2)", "M.R. Civ. P. 80K", "(b)(2)"),
    ],
)
def test_court_rule_citations(raw, citation, sub):
    c = search.normalize_citation(raw)
    assert (c.kind, c.citation, c.subsection) == ("rule", citation, sub)


@pytest.mark.parametrize(
    "raw, new",
    [
        ("16-642 CMR ch. 1", "08-003 CMR ch. 2"),
        ("16-642 CMR ch. 3", "08-003 CMR ch. 4"),
        ("16-642 CMR ch. 7", "08-003 CMR ch. 8"),
        ("16-219 CMR ch. 52", "08-003 CMR ch. 1"),
    ],
)
def test_renumbered_rules_fall_back(raw, new):
    assert [p.citation for p in search.normalize_citation(raw).parents()] == [new]


def test_current_rules_have_no_fallback():
    assert search.normalize_citation("08-003 CMR ch. 4").parents() == []
    assert search.normalize_citation("10-144 CMR ch. 241").parents() == []


# ------------------------------------------------ against the FAKE_AZURE fixture rows
# tests/fixtures/extra_docs.json adds real § 4452, Rule 80K, city form and
# staff note chunks to the fixtures, so these run on real text.


@pytest.fixture(autouse=True)
def fresh():
    search.clear_facet_cache()
    lookup_router.public_limiter.reset()
    yield
    search.clear_facet_cache()


def _public() -> TestClient:
    from app.main import app

    return TestClient(app)


def test_lookup_state_statute_every_chunk():
    r = _public().get("/api/lookup", params={"cite": "30-a mrsa 4452(3)"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["citation"] == "30-A M.R.S. § 4452"
    assert body["subsection"] == "(3)"
    assert body["chunk_count"] == 4
    assert [c["chunk_index"] for c in body["chunks"]] == [0, 1, 2, 3]
    assert "penalt" in body["text"].lower()


def test_lookup_court_rule():
    r = _public().get("/api/lookup", params={"cite": "M.R. Civ. P. 80K"})
    assert r.status_code == 200, r.text
    assert r.json()["citation"] == "M.R. Civ. P. 80K"
    assert r.json()["source_type"] == "state_rule"


def test_lookup_unknown_court_rule_is_404():
    r = _public().get("/api/lookup", params={"cite": "Rule 80Z"})
    assert r.status_code == 404


async def test_staff_note_only_in_staff_search():
    q = "civil penalties 4452 paragraphs apart"
    public = await search.search(q, mode="public")
    staff = await search.search(q, mode="staff")
    assert not any(d.get("source_type") == "staff_note" for d in public)
    assert any(d.get("source_type") == "staff_note" for d in staff)


async def test_city_form_in_public_city_bucket():
    docs = await search.search("building permit application form", mode="public")
    assert any(d.get("source_type") == "city_form" for d in docs)


async def test_penalty_pin_with_real_text():
    docs = await search.search("chicken violation", mode="staff", k_state=0)
    pinned = [d for d in docs if d.get("citation") == "30-A M.R.S. § 4452"]
    assert 1 <= len(pinned) <= search.MAX_PINNED
    assert all("penalt" in (d.get("content") or "").lower() for d in pinned)

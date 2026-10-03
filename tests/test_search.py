from __future__ import annotations

import json

import httpx
import pytest

from app import config, search


def test_odata_string_escaping():
    assert search.odata_str("275") == "'275'"
    assert search.odata_str("O'Brien") == "'O''Brien'"
    assert search.odata_str("a'' or 1 eq 1 or 'x") == "'a'''' or 1 eq 1 or ''x'"


def test_bucket_odata_escapes_chapters():
    b = search.Bucket(("code",), chapters=("275", "it's"))
    assert b.odata() == "search.in(source_type, 'code') and (chapter_number eq '275' or chapter_number eq 'it''s')"


def test_public_default_filters():
    local, state = search.buckets("public")
    assert local.odata() == "search.in(source_type, 'code,attachment,new_law,city_form')"
    assert state.odata() == "not search.in(source_type, 'code,attachment,new_law,city_form,staff_note')"


def test_staff_sees_staff_notes():
    local, state = search.buckets("staff")
    assert "staff_note" in local.types and not local.exclude
    assert state.exclude and "staff_note" in state.types


def test_source_type_filter_splits_buckets():
    local, state = search.buckets("staff", {"source_types": ["code", "state_statute"], "chapters": ["275"]})
    assert local.odata() == "search.in(source_type, 'code') and (chapter_number eq '275')"
    assert state.odata() == "search.in(source_type, 'state_statute')"
    local, state = search.buckets("public", {"source_types": ["state_rule"]})
    assert local is None and state.types == ("state_rule",)
    local, state = search.buckets("public", {"source_types": ["attachment"]})
    assert state is None


def test_chapters_only_limit_city_bucket():
    local, state = search.buckets("public", {"chapters": ["275", "127"]})
    assert "chapter_number eq '127'" in local.odata()
    assert "chapter_number" not in state.odata()


@pytest.mark.parametrize(
    "filters",
    [
        {"source_types": ["code", "evil"]},
        {"source_types": ["code') or true or ('"]},
        {"chapters": ["275' or 1 eq 1 or '"]},
        {"chapters": ["x" * 30]},
        {"chapters": [""]},
        {"chapters": "275"},
        {"chapters": [str(i) for i in range(60)]},
    ],
)
def test_filter_validation_rejects(filters):
    with pytest.raises(ValueError):
        search.validate_filters(filters, "staff")


def test_staff_note_is_staff_only():
    with pytest.raises(ValueError):
        search.validate_filters({"source_types": ["staff_note"]}, "public")
    assert search.validate_filters({"source_types": ["staff_note"]}, "staff") == {"source_types": ["staff_note"]}


async def test_fake_search_ranks_real_chunks():
    docs = await search.search("Can I keep backyard chickens?")
    assert docs[0]["citation"] == "§ 275-4.33"
    assert set(search.SELECT.split(",")) <= set(docs[0])
    docs = await search.search("chickens", filters={"chapters": ["115"], "source_types": ["code"]})
    assert docs and all(d["citation"].startswith("§ 115") or "115" in d["citation"] for d in docs)


async def test_fake_search_staff_depth():
    docs = await search.search("building permit penalties", mode="staff")
    assert 3 <= len(docs) <= config.STAFF_K_LOCAL + config.STAFF_K_STATE


async def test_fake_lookup_and_facets():
    rows = await search.lookup(f"citation eq {search.odata_str('§ 275-4.33')}")
    assert rows and all(r["citation"] == "§ 275-4.33" for r in rows)
    rows = await search.lookup("(chapter_number eq '215' or chapter_number eq '205') and source_type eq 'code'", order_by="id")
    assert {r["chapter_number"] for r in rows} == {"215", "205"}
    f = await search.facets(["chapter_number", "source_type"])
    assert {"value": "new_law", "count": 1} in f["source_type"]
    assert any(x["value"] == "275" for x in f["chapter_number"])


async def test_real_search_sends_escaped_filters(monkeypatch):
    seen = []

    def handler(req: httpx.Request):
        body = json.loads(req.content)
        seen.append(body)
        return httpx.Response(200, json={"value": [{"id": str(len(seen)), "content": "x", "@search.rerankerScore": 2.0}]})

    monkeypatch.setattr(config, "FAKE_AZURE", False)
    monkeypatch.setattr(config, "SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setattr(search.search_auth, "key", "test-key")
    monkeypatch.setattr(search, "http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))
    await search.search("q", mode="staff", filters={"chapters": ["275"], "source_types": ["code", "state_rule"]})
    filters = sorted(b["filter"] for b in seen)
    assert filters == [
        "search.in(source_type, 'code') and (chapter_number eq '275')",
        "search.in(source_type, 'state_rule')",
    ]
    assert {b["top"] for b in seen} == {config.STAFF_K_LOCAL, config.STAFF_K_STATE}


async def test_real_search_error_is_502(monkeypatch):
    monkeypatch.setattr(config, "FAKE_AZURE", False)
    monkeypatch.setattr(config, "SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setattr(search.search_auth, "key", "test-key")
    monkeypatch.setattr(
        search, "http", httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(500, text="no")))
    )
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as e:
        await search.search("q")
    assert e.value.status_code == 502


def test_format_sources_shape():
    docs = [
        {"citation": "§ 1", "title": "T", "content": "City of Waterville, ME Code\nCh > § 1\n\nBody.", "breadcrumb": "Ch > § 1",
         "source_type": "new_law", "url": "https://x/a.pdf", "page_start": 3, "page_end": 4},
    ]
    context, meta = search.format_sources(docs)
    assert context.startswith("[1] § 1 (New Law, not yet codified)\n")
    assert meta[0]["text"] == "Body."
    assert meta[0]["open_url"] == "https://x/a.pdf#page=3"
    assert list(meta[0]) == ["n", "citation", "title", "breadcrumb", "url", "source_type", "page_start", "page_end",
                             "label", "open_url", "text"]

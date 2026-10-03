from __future__ import annotations

import os

import pytest

from app import config, store


@pytest.fixture
def db(tmp_path):
    s = store.SqliteStore(tmp_path / "s.sqlite")
    yield s


async def test_put_get_roundtrip(db):
    saved = await db.put("cases", "2026", "c1", {"address": "12 Main St", "tags": ["fence"], "n": 3})
    assert saved["_pk"] == "2026" and saved["_rk"] == "c1" and saved["_updated"]
    got = await db.get("cases", "2026", "c1")
    assert got["address"] == "12 Main St"
    assert got["tags"] == ["fence"]
    assert got["n"] == 3
    assert await db.get("cases", "2026", "missing") is None
    assert await db.get("drafts", "2026", "c1") is None


async def test_put_replaces(db):
    await db.put("cases", "p", "r", {"a": 1, "b": 2})
    await db.put("cases", "p", "r", {"a": 5, "_pk": "ignored"})
    got = await db.get("cases", "p", "r")
    assert got["a"] == 5 and "b" not in got and got["_pk"] == "p"


async def test_query_and_filter(db):
    await db.put("caseitems", "case1", "002", {"kind": "note", "text": "b"})
    await db.put("caseitems", "case1", "001", {"kind": "answer", "text": "a"})
    await db.put("caseitems", "case2", "001", {"kind": "note", "text": "c"})
    items = await db.query("caseitems", pk="case1")
    assert [i["_rk"] for i in items] == ["001", "002"]
    assert len(await db.query("caseitems")) == 3
    notes = await db.query("caseitems", filter={"kind": "note"})
    assert [n["text"] for n in notes] == ["b", "c"]
    picked = await db.query("caseitems", filter=lambda e: e["text"] > "a")
    assert len(picked) == 2


async def test_delete(db):
    await db.put("drafts", "alice", "d1", {"body": "x"})
    assert await db.delete("drafts", "alice", "d1") is True
    assert await db.delete("drafts", "alice", "d1") is False
    assert await db.get("drafts", "alice", "d1") is None


async def test_large_field(db):
    body = "word " * 30_000  # 150K chars
    await db.put("drafts", "alice", "big", {"body": body})
    assert (await db.get("drafts", "alice", "big"))["body"] == body


async def test_too_large(db):
    with pytest.raises(store.StoreError):
        await db.put("drafts", "alice", "huge", {"body": "x" * 500_000})


@pytest.mark.parametrize("pk", ["", "a/b", "a#b", "a?b", "a\\b", "a\nb", "x" * 600])
async def test_bad_keys(db, pk):
    with pytest.raises(store.StoreError):
        await db.put("cases", pk, "r", {})


@pytest.mark.parametrize("table", ["", "ab", "1abc", "bad-name", "a b"])
async def test_bad_table(db, table):
    with pytest.raises(store.StoreError):
        await db.put(table, "p", "r", {})


async def test_persists_across_instances(tmp_path):
    path = tmp_path / "p.sqlite"
    a = store.SqliteStore(path)
    await a.put("feedback", "d", "1", {"ok": True})
    await a.close()
    b = store.SqliteStore(path)
    assert (await b.get("feedback", "d", "1"))["ok"] is True


def test_table_encoding_chunks_large_entities():
    body = "é" * 70_000
    raw = store.encode_entity("pk", "rk", {"body": body, "n": 1})
    assert raw["PartitionKey"] == "pk" and raw["RowKey"] == "rk"
    assert raw["chunks"] == 3
    assert all(len(raw[f"data_{i}"]) <= store.CHUNK for i in range(raw["chunks"]))
    back = store.decode_entity(raw)
    assert back["body"] == body and back["n"] == 1 and back["_pk"] == "pk" and back["_rk"] == "rk"


def test_table_encoding_small_entity():
    raw = store.encode_entity("p", "r", {})
    assert raw["chunks"] == 1
    assert store.decode_entity(raw)["_rk"] == "r"


def test_get_store_defaults_to_sqlite(tmp_path, monkeypatch):
    store.set_store(None)
    monkeypatch.setattr(config, "STORAGE_TABLE_ENDPOINT", "")
    monkeypatch.setattr(config, "STORE_SQLITE_PATH", tmp_path / "sub" / "d.sqlite")
    s = store.get_store()
    assert isinstance(s, store.SqliteStore)
    assert store.get_store() is s
    assert (tmp_path / "sub" / "d.sqlite").exists()


def test_get_store_uses_tables_when_configured(monkeypatch):
    store.set_store(None)
    monkeypatch.setattr(config, "STORAGE_TABLE_ENDPOINT", "https://example.table.core.windows.net")
    s = store.get_store()
    assert isinstance(s, store.TableStore)
    store.set_store(None)


# ------------------------------------------------ Azure Table backend against Azurite (optional)
#   docker run -d -p 10002:10002 mcr.microsoft.com/azure-storage/azurite azurite-table --tableHost 0.0.0.0
#   AZURITE_CONNECTION_STRING='DefaultEndpointsProtocol=http;AccountName=devstoreaccount1;AccountKey=<well-known Azurite key>;TableEndpoint=http://127.0.0.1:10002/devstoreaccount1;' uv run pytest -q

AZURITE = os.environ.get("AZURITE_CONNECTION_STRING")


@pytest.mark.skipif(not AZURITE, reason="set AZURITE_CONNECTION_STRING to test the Table backend")
async def test_table_store_against_azurite():
    import uuid

    s = store.TableStore(connection_string=AZURITE)
    table = "t" + uuid.uuid4().hex[:12]
    try:
        big = "x" * 100_000
        await s.put(table, "p1", "r2", {"body": big, "kind": "note"})
        await s.put(table, "p1", "r1", {"kind": "answer"})
        await s.put(table, "p2", "r1", {"kind": "note"})
        assert (await s.get(table, "p1", "r2"))["body"] == big
        assert await s.get(table, "p1", "missing") is None
        assert [e["_rk"] for e in await s.query(table, pk="p1")] == ["r1", "r2"]
        assert len(await s.query(table, filter={"kind": "note"})) == 2
        # Replacing with a shorter entity drops the old chunks.
        await s.put(table, "p1", "r2", {"body": "short"})
        assert (await s.get(table, "p1", "r2"))["body"] == "short"
        assert await s.delete(table, "p1", "r2") is True
        assert await s.delete(table, "p1", "r2") is False
    finally:
        await s._service.delete_table(table)
        await s.close()

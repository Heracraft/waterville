"""Small document store: Azure Table storage in Azure, a SQLite file locally and in tests.

    from app.store import get_store
    store = get_store()
    await store.put("cases", pk="2026", rk=case_id, entity={...})
    await store.get("cases", "2026", case_id)              -> dict | None
    await store.query("cases", pk="2026")                  -> [dict, ...] (sorted by pk, rk)
    await store.query("cases", filter={"status": "open"})  -> equality match on top-level fields
    await store.query("cases", filter=lambda e: ...)       -> any predicate
    await store.delete("cases", "2026", case_id)           -> bool

Entities are JSON-serializable dicts. Returned dicts carry three extra keys:
`_pk`, `_rk` and `_updated` (ISO UTC). Keys may not contain / \\ # ? or
control characters (Azure Table rules apply to both backends).

The Table backend stores the whole entity as one JSON string split into
`data_0..data_n` properties of at most 32,000 UTF-16 code units each (64,000
bytes, under the 64 KiB property limit), so large fields (drafts, answers)
fit. An entity's JSON may be up to 480,000 UTF-16 code units (960,000 bytes,
under the 1 MiB entity limit). Azure counts strings in UTF-16, so a character
outside the Basic Multilingual Plane (most emoji) counts twice; both backends
measure the same way. A too-large entity raises StoreError("entity too
large"), which the app answers with 413.
Filters run in Python after the partition (or table) is read; tables here
are small. It authenticates with DefaultAzureCredential and needs the
Storage Table Data Contributor role.

Tables in use: cases, caseitems, drafts, questions, changes, feedback, answers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import sqlite3
import threading
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from . import config

log = logging.getLogger("app.store")

TABLES = ("cases", "caseitems", "drafts", "questions", "changes", "feedback", "answers")
TABLE_RE = re.compile(r"^[A-Za-z][A-Za-z0-9]{2,62}$")
BAD_KEY = re.compile(r"[/\\#?\x00-\x1f\x7f-\x9f]")
CHUNK = 32_000
MAX_JSON = 480_000

Filter = dict[str, Any] | Callable[[dict], bool] | None


class StoreError(ValueError):
    pass


def utf16_len(s: str) -> int:
    """Length in UTF-16 code units, the unit Azure Table storage limits."""
    if s.isascii():
        return len(s)
    return len(s.encode("utf-16-le", "surrogatepass")) // 2


def _encode_json(entity: dict) -> str:
    data = json.dumps(_clean(entity), ensure_ascii=False)
    if utf16_len(data) > MAX_JSON:
        raise StoreError("entity too large")
    return data


def split_utf16(data: str, limit: int = CHUNK) -> list[str]:
    """data in pieces of at most `limit` UTF-16 code units, never splitting a surrogate pair."""
    if not data:
        return [""]
    if data.isascii() or max(data) <= "\uffff":
        return [data[i : i + limit] for i in range(0, len(data), limit)]
    parts: list[str] = []
    start = units = 0
    for i, ch in enumerate(data):
        w = 2 if ord(ch) > 0xFFFF else 1
        if units + w > limit:
            parts.append(data[start:i])
            start, units = i, 0
        units += w
    parts.append(data[start:])
    return parts


def _check(table: str, pk: str | None = None, rk: str | None = None) -> None:
    if not TABLE_RE.match(table or ""):
        raise StoreError(f"bad table name: {table!r}")
    for k in (pk, rk):
        if k is None:
            continue
        if not isinstance(k, str) or not k or len(k) > 512 or BAD_KEY.search(k):
            raise StoreError(f"bad key: {k!r}")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _matches(entity: dict, filter_: Filter) -> bool:
    if filter_ is None:
        return True
    if callable(filter_):
        return bool(filter_(entity))
    return all(entity.get(k) == v for k, v in filter_.items())


def _clean(entity: dict) -> dict:
    if not isinstance(entity, dict):
        raise StoreError("entity must be a dict")
    return {k: v for k, v in entity.items() if k not in ("_pk", "_rk", "_updated")}


class Store(ABC):
    @abstractmethod
    async def put(self, table: str, pk: str, rk: str, entity: dict) -> dict:
        """Insert or replace. Returns the stored entity with _pk, _rk, _updated."""

    @abstractmethod
    async def get(self, table: str, pk: str, rk: str) -> dict | None: ...

    @abstractmethod
    async def query(self, table: str, pk: str | None = None, filter: Filter = None) -> list[dict]: ...

    @abstractmethod
    async def delete(self, table: str, pk: str, rk: str) -> bool:
        """True if something was deleted."""

    async def close(self) -> None:
        return None


# ---------------------------------------------------------------- SQLite


class SqliteStore(Store):
    def __init__(self, path: str | Path):
        self.path = str(path)
        if self.path != ":memory:":
            Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.execute("PRAGMA journal_mode=WAL" if self.path != ":memory:" else "PRAGMA journal_mode=MEMORY")
        self._db.execute(
            "CREATE TABLE IF NOT EXISTS entities ("
            " tbl TEXT NOT NULL, pk TEXT NOT NULL, rk TEXT NOT NULL,"
            " data TEXT NOT NULL, updated TEXT NOT NULL,"
            " PRIMARY KEY (tbl, pk, rk))"
        )
        self._db.commit()

    def _run(self, sql: str, args: tuple = ()) -> list[tuple]:
        with self._lock:
            cur = self._db.execute(sql, args)
            rows = cur.fetchall()
            self._db.commit()
            return rows if sql.lstrip().upper().startswith("SELECT") else [(cur.rowcount,)]

    @staticmethod
    def _row(pk: str, rk: str, data: str, updated: str) -> dict:
        return {**json.loads(data), "_pk": pk, "_rk": rk, "_updated": updated}

    async def put(self, table: str, pk: str, rk: str, entity: dict) -> dict:
        _check(table, pk, rk)
        data = _encode_json(entity)
        updated = _now()
        await asyncio.to_thread(
            self._run,
            "INSERT OR REPLACE INTO entities (tbl, pk, rk, data, updated) VALUES (?, ?, ?, ?, ?)",
            (table, pk, rk, data, updated),
        )
        return self._row(pk, rk, data, updated)

    async def get(self, table: str, pk: str, rk: str) -> dict | None:
        _check(table, pk, rk)
        rows = await asyncio.to_thread(
            self._run, "SELECT pk, rk, data, updated FROM entities WHERE tbl=? AND pk=? AND rk=?", (table, pk, rk)
        )
        return self._row(*rows[0]) if rows else None

    async def query(self, table: str, pk: str | None = None, filter: Filter = None) -> list[dict]:
        _check(table, pk)
        if pk is None:
            sql, args = "SELECT pk, rk, data, updated FROM entities WHERE tbl=? ORDER BY pk, rk", (table,)
        else:
            sql, args = "SELECT pk, rk, data, updated FROM entities WHERE tbl=? AND pk=? ORDER BY rk", (table, pk)
        rows = await asyncio.to_thread(self._run, sql, args)
        out = [self._row(*r) for r in rows]
        return [e for e in out if _matches(e, filter)]

    async def delete(self, table: str, pk: str, rk: str) -> bool:
        _check(table, pk, rk)
        rows = await asyncio.to_thread(
            self._run, "DELETE FROM entities WHERE tbl=? AND pk=? AND rk=?", (table, pk, rk)
        )
        return rows[0][0] > 0

    async def close(self) -> None:
        with self._lock:
            self._db.close()


# ---------------------------------------------------------------- Azure Table


def encode_entity(pk: str, rk: str, entity: dict) -> dict:
    """The Azure Table entity for a dict: JSON split into data_0..data_n."""
    data = _encode_json(entity)
    parts = split_utf16(data)
    out: dict[str, Any] = {"PartitionKey": pk, "RowKey": rk, "chunks": len(parts), "updated": _now()}
    for i, p in enumerate(parts):
        out[f"data_{i}"] = p
    return out


def decode_entity(raw: dict) -> dict:
    n = int(raw.get("chunks") or 0)
    data = "".join(raw.get(f"data_{i}") or "" for i in range(n))
    return {**json.loads(data or "{}"), "_pk": raw["PartitionKey"], "_rk": raw["RowKey"], "_updated": raw.get("updated")}


class TableStore(Store):
    def __init__(self, endpoint: str = "", credential=None, connection_string: str = ""):
        from azure.data.tables.aio import TableServiceClient

        if connection_string:
            # Azurite or a key-based account (local dev and tests only).
            self._credential = None
            self._service = TableServiceClient.from_connection_string(connection_string)
        else:
            if credential is None:
                from azure.identity.aio import DefaultAzureCredential

                credential = DefaultAzureCredential()
            self._credential = credential
            self._service = TableServiceClient(endpoint=endpoint, credential=credential)
        self._ready: set[str] = set()
        self._lock = asyncio.Lock()

    async def _table(self, table: str):
        if table not in self._ready:
            async with self._lock:
                if table not in self._ready:
                    from azure.core.exceptions import HttpResponseError

                    try:
                        await self._service.create_table_if_not_exists(table)
                    except HttpResponseError as e:
                        # An identity granted one table only (the preview refresh
                        # job writes `changes`) may not create tables; infra
                        # creates them, so go on and let the data call decide.
                        if e.status_code != 403:
                            raise
                        log.info("store: no right to create table %s; assuming it exists", table)
                    self._ready.add(table)
        return self._service.get_table_client(table)

    async def put(self, table: str, pk: str, rk: str, entity: dict) -> dict:
        from azure.data.tables import UpdateMode

        _check(table, pk, rk)
        raw = encode_entity(pk, rk, entity)
        client = await self._table(table)
        # Replace, so stale data_n chunks from a longer earlier version vanish.
        await client.upsert_entity(raw, mode=UpdateMode.REPLACE)
        return decode_entity(raw)

    async def get(self, table: str, pk: str, rk: str) -> dict | None:
        from azure.core.exceptions import ResourceNotFoundError

        _check(table, pk, rk)
        client = await self._table(table)
        try:
            return decode_entity(await client.get_entity(pk, rk))
        except ResourceNotFoundError:
            return None

    async def query(self, table: str, pk: str | None = None, filter: Filter = None) -> list[dict]:
        _check(table, pk)
        client = await self._table(table)
        if pk is None:
            pages = client.list_entities()
        else:
            pages = client.query_entities("PartitionKey eq @pk", parameters={"pk": pk})
        out = [decode_entity(e) async for e in pages]
        out.sort(key=lambda e: (e["_pk"], e["_rk"]))
        return [e for e in out if _matches(e, filter)]

    async def delete(self, table: str, pk: str, rk: str) -> bool:
        _check(table, pk, rk)
        client = await self._table(table)
        if await self.get(table, pk, rk) is None:
            return False
        await client.delete_entity(pk, rk)
        return True

    async def close(self) -> None:
        await self._service.close()
        close = getattr(self._credential, "close", None)
        if close:
            await close()


# ---------------------------------------------------------------- singleton

_store: Store | None = None


def get_store() -> Store:
    """The process-wide store (also usable as a FastAPI dependency)."""
    global _store
    if _store is None:
        if config.STORAGE_CONNECTION_STRING:
            log.info("store: Azure Table storage from STORAGE_CONNECTION_STRING")
            _store = TableStore(connection_string=config.STORAGE_CONNECTION_STRING)
        elif config.STORAGE_TABLE_ENDPOINT:
            log.info("store: Azure Table storage at %s", config.STORAGE_TABLE_ENDPOINT)
            _store = TableStore(config.STORAGE_TABLE_ENDPOINT)
        else:
            log.info("store: SQLite at %s", config.STORE_SQLITE_PATH)
            _store = SqliteStore(config.STORE_SQLITE_PATH)
    return _store


def set_store(store: Store | None) -> None:
    """Swap the process-wide store (tests)."""
    global _store
    _store = store

"""Code change alerts (B12): what changed in the city sources since the last push.

Before the refresh pushes new chunks, it reads `id` and `content_hash` (plus
the citation fields) of the city chunks already in the target index and
compares them with the new chunks. Each changed, added or removed citation
becomes one row in the store table `changes`, which `GET /api/staff/changes`
lists for the staff insights page.

    python -m ecode.changes --old OLD.jsonl --new NEW.jsonl [--to print|store]

compares two chunk files without touching an index (useful locally, and to
seed the store for a demo). `python -m ecode.azure push` and
`python -m ecode.azure changes` run the same diff against the index.

Store layout, table `changes`:
  pk = run id (UTC, "20261003T070000Z"), rk = "run" for the run summary
  {kind: "run", run_at, index, baseline, counts, chunks}, and rk = a hash of
  (source_type, citation) for each change {kind: changed|added|removed,
  citation, title, source_type, url, chapter_number, chapter_title,
  section_title, history, legislation_through, previous_legislation_through,
  chunks, run_at, index}.
"""

from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import hashlib
import json
import os
import sys
from collections import defaultdict
from pathlib import Path

from .export import content_hash

# City sources whose edits staff want to hear about. State law and manuals are
# left out: they change rarely and are not what the code office administers.
CHANGE_TYPES = ("code", "attachment", "new_law", "city_form")
# Fields read from the index for the comparison.
INDEX_FIELDS = (
    "id",
    "content_hash",
    "citation",
    "title",
    "url",
    "source_type",
    "chapter_number",
    "chapter_title",
    "section_title",
    "legislation_through",
    "history",
)
TABLE = "changes"
KINDS = ("changed", "added", "removed")


def _key(row: dict) -> tuple[str, str]:
    return (row.get("source_type") or "", row.get("citation") or row.get("title") or row.get("id") or "")


def diff(old_rows: list[dict], new_chunks: list[dict], types: tuple[str, ...] = CHANGE_TYPES) -> dict:
    """Compare index rows with new chunks, grouped by citation.

    Returns {"baseline": bool, "changes": [...], "counts": {...}}. When the
    index has no city rows, or none of them carries a content_hash (an index
    built before the field existed), the run is a baseline: nothing is
    reported, and the next run compares against the hashes this push stores.
    A row whose old hash is missing is treated as unknown, not as changed.
    """
    old = [r for r in old_rows if r.get("source_type") in types]
    new = [c for c in new_chunks if c.get("source_type") in types]
    counts = {k: 0 for k in KINDS}
    if not old or not any(r.get("content_hash") for r in old):
        return {"baseline": True, "changes": [], "counts": counts}

    old_by: dict[tuple, list[dict]] = defaultdict(list)
    new_by: dict[tuple, list[dict]] = defaultdict(list)
    for r in old:
        old_by[_key(r)].append(r)
    for c in new:
        new_by[_key(c)].append(c)

    changes = []
    for k in sorted(set(old_by) | set(new_by)):
        o, n = old_by.get(k, []), new_by.get(k, [])
        if not o:
            kind = "added"
        elif not n:
            kind = "removed"
        else:
            o_hash = {r["id"]: r.get("content_hash") for r in o}
            n_hash = {c["id"]: c.get("content_hash") or content_hash(c) for c in n}
            if set(o_hash) != set(n_hash):
                kind = "changed"
            elif any(o_hash[i] and o_hash[i] != n_hash[i] for i in n_hash):
                kind = "changed"
            else:
                continue
        ref = (n or o)[0]
        prev = o[0] if o else {}
        changes.append(
            {
                "kind": kind,
                "citation": ref.get("citation"),
                "title": ref.get("title"),
                "source_type": ref.get("source_type"),
                "url": ref.get("url"),
                "chapter_number": ref.get("chapter_number"),
                "chapter_title": ref.get("chapter_title"),
                "section_title": ref.get("section_title"),
                "history": ref.get("history"),
                "legislation_through": (n[0].get("legislation_through") if n else None),
                "previous_legislation_through": prev.get("legislation_through"),
                "chunks": len(n),
                "previous_chunks": len(o),
            }
        )
        counts[kind] += 1
    return {"baseline": False, "changes": changes, "counts": counts}


def run_id(now: dt.datetime | None = None) -> tuple[str, str]:
    now = (now or dt.datetime.now(dt.timezone.utc)).astimezone(dt.timezone.utc).replace(microsecond=0)
    return now.strftime("%Y%m%dT%H%M%SZ"), now.isoformat().replace("+00:00", "Z")


def change_rk(change: dict) -> str:
    return hashlib.sha256(f"{change.get('source_type')}|{change.get('citation')}".encode()).hexdigest()[:24]


def records(result: dict, index: str, total_chunks: int, now: dt.datetime | None = None) -> list[tuple[str, str, dict]]:
    """(pk, rk, entity) rows for the store: one run summary plus one row per change."""
    pk, at = run_id(now)
    rows = [
        (
            pk,
            "run",
            {
                "kind": "run",
                "run_at": at,
                "index": index,
                "baseline": result["baseline"],
                "counts": result["counts"],
                "chunks": total_chunks,
            },
        )
    ]
    for c in result["changes"]:
        rows.append((pk, change_rk(c), {**c, "run_at": at, "index": index}))
    return rows


def store_configured() -> bool:
    return bool(os.environ.get("STORAGE_TABLE_ENDPOINT") or os.environ.get("STORAGE_CONNECTION_STRING"))


def record(result: dict, index: str, total_chunks: int, to: str = "auto", now: dt.datetime | None = None, out=None) -> str:
    """Write the run to the store table `changes`, or print it as JSON lines.

    to: "auto" (the store when STORAGE_TABLE_ENDPOINT or
    STORAGE_CONNECTION_STRING is set, else print), "store" (app.store,
    which falls back to the local SQLite file), "print" or "none".
    Returns where the rows went.
    """
    if to == "none":
        return "none"
    rows = records(result, index, total_chunks, now)
    if to == "auto":
        to = "store" if store_configured() else "print"
    if to == "print":
        out = out or sys.stdout
        for pk, rk, e in rows:
            out.write(json.dumps({"table": TABLE, "pk": pk, "rk": rk, **e}, ensure_ascii=False) + "\n")
        return "print"
    asyncio.run(_put_all(rows))
    return "store"


async def _put_all(rows: list[tuple[str, str, dict]]) -> None:
    from app import store as app_store

    # A store someone else opened (the web app, a test) stays open.
    created = app_store._store is None
    store = app_store.get_store()
    try:
        for pk, rk, e in rows:
            await store.put(TABLE, pk, rk, e)
    finally:
        if created:
            await store.close()
            app_store.set_store(None)


def summary(result: dict) -> str:
    if result["baseline"]:
        return "change alerts: baseline run (the index had no content hashes for city sources); nothing reported"
    c = result["counts"]
    return f"change alerts: {c['changed']} changed, {c['added']} added, {c['removed']} removed citations"


def _read_jsonl(path: Path) -> list[dict]:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Compare two chunk files and record city code changes.")
    ap.add_argument("--old", type=Path, required=True, help="previous chunks.jsonl (or index rows as JSON lines)")
    ap.add_argument("--new", type=Path, required=True, help="new chunks.jsonl")
    ap.add_argument("--to", choices=["auto", "store", "print", "none"], default="print")
    ap.add_argument("--index", default="local", help="label stored with the run")
    args = ap.parse_args(argv)
    old = _read_jsonl(args.old)
    for r in old:
        r.setdefault("content_hash", content_hash(r) if r.get("content") else None)
    new = _read_jsonl(args.new)
    result = diff(old, new)
    where = record(result, args.index, len(new), args.to)
    print(summary(result) + f" ({where})", file=sys.stderr)


if __name__ == "__main__":
    main()

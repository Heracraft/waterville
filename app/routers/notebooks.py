"""Case notebooks for staff: /api/staff/cases ...

    GET    /api/staff/cases?q=&status=&tag=     -> {"cases": [case + counts], "total": n}
    POST   /api/staff/cases                     -> case (201)
    GET    /api/staff/cases/{id}                -> case + {"items": [...]}
    PATCH  /api/staff/cases/{id}                -> case
    DELETE /api/staff/cases/{id}                -> {"ok": true, "items_deleted": n}
    GET    /api/staff/cases/{id}/items          -> {"items": [...]}
    POST   /api/staff/cases/{id}/items          -> item (201)
    DELETE /api/staff/cases/{id}/items/{item}   -> {"ok": true}
    GET    /api/staff/cases/{id}/export.md      -> text/markdown attachment

Every route needs a staff session (require_staff), and writes need the
X-Requested-With: wv header. Cases are shared by the whole office: any staff
user can read and change any case, and each record carries who made it and
who changed it last.

Store layout (app.store):
  cases      pk "case",   rk case id ("2026-3f9a1c")   one partition; the table is small
  caseitems  pk case id,  rk item id (ms timestamp + random), so a partition
             read returns the timeline in order

Item kinds (POST body, `kind` picks the shape):
  {"kind": "note", "text"}
  {"kind": "answer", "answer_id"}                     copies the caller's stored
       staff answer (table `answers`, written by POST /api/chat) into the case;
       or {"kind": "answer", "question", "answer", "sources"} for an answer the
       store did not keep
  {"kind": "deadline", "label", "date": "YYYY-MM-DD", "citation", "note"?, "trigger"?}
       sent by the deadline calculator
  {"kind": "draft", "draft_id", "title"?, "template"?} links a document draft
"""

from __future__ import annotations

import asyncio
import re
import secrets
import time
import datetime as dt
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Annotated, Any, Literal, Union
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator

from .. import prompts
from ..auth import require_staff
from ..store import get_store

router = APIRouter(tags=["notebooks"])

CASES = "cases"
ITEMS = "caseitems"
CASE_PK = "case"

TAGS = (
    "building",
    "zoning",
    "property-maintenance",
    "shoreland",
    "floodplain",
    "rental",
    "complaint",
    "dangerous-building",
    "plumbing",
    "subsurface",
    "other",
)
STATUSES = ("open", "monitoring", "closed")
TAG_LABELS = {
    "building": "Building",
    "zoning": "Zoning",
    "property-maintenance": "Property maintenance",
    "shoreland": "Shoreland",
    "floodplain": "Floodplain",
    "rental": "Rental",
    "complaint": "Complaint",
    "dangerous-building": "Dangerous building",
    "plumbing": "Plumbing",
    "subsurface": "Subsurface",
    "other": "Other",
}

ID_RE = r"^[A-Za-z0-9_\-]{1,64}$"
CaseId = Annotated[str, Field(pattern=ID_RE)]
ITEM_LIMIT = 500  # items per case
SOURCE_FIELDS = (
    "n",
    "citation",
    "title",
    "breadcrumb",
    "url",
    "open_url",
    "source_type",
    "page_start",
    "page_end",
    "label",
    "text",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def _new_case_id() -> str:
    return f"{datetime.now(timezone.utc).year}-{secrets.token_hex(3)}"


def _new_item_id() -> str:
    return f"{int(time.time() * 1000):013d}-{secrets.token_hex(3)}"


# ---------------------------------------------------------------- models


class _Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


def _check_tags(v: list[str] | None) -> list[str] | None:
    if v is None:
        return v
    bad = [t for t in v if t not in TAGS]
    if bad:
        raise ValueError(f"unknown type tag: {', '.join(bad)}")
    # Keep the canonical order and drop repeats.
    return [t for t in TAGS if t in v]


class CaseIn(_Strict):
    address: str = Field(min_length=1, max_length=200)
    map_lot: str = Field(default="", max_length=64)
    owner: str = Field(default="", max_length=200)
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=4000)
    tags: list[str] = Field(default_factory=list, max_length=len(TAGS))
    status: Literal["open", "monitoring", "closed"] = "open"

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        return _check_tags(v)


class CasePatch(_Strict):
    address: str | None = Field(default=None, min_length=1, max_length=200)
    map_lot: str | None = Field(default=None, max_length=64)
    owner: str | None = Field(default=None, max_length=200)
    title: str | None = Field(default=None, max_length=200)
    summary: str | None = Field(default=None, max_length=4000)
    tags: list[str] | None = Field(default=None, max_length=len(TAGS))
    status: Literal["open", "monitoring", "closed"] | None = None

    @field_validator("tags")
    @classmethod
    def _tags(cls, v):
        return _check_tags(v)


class NoteIn(_Strict):
    kind: Literal["note"]
    text: str = Field(min_length=1, max_length=20_000)


class SourceIn(BaseModel):
    model_config = ConfigDict(extra="ignore")
    n: int = Field(ge=1, le=99)
    citation: str | None = Field(default=None, max_length=300)
    title: str | None = Field(default=None, max_length=500)
    breadcrumb: str | None = Field(default=None, max_length=1000)
    url: str | None = Field(default=None, max_length=2000)
    open_url: str | None = Field(default=None, max_length=2000)
    source_type: str | None = Field(default=None, max_length=40)
    page_start: int | None = None
    page_end: int | None = None
    label: str | None = Field(default=None, max_length=200)
    text: str | None = Field(default=None, max_length=20_000)


class AnswerIn(_Strict):
    kind: Literal["answer"]
    answer_id: str | None = Field(default=None, pattern=r"^[A-Fa-f0-9]{8,64}$")
    question: str | None = Field(default=None, max_length=4000)
    answer: str | None = Field(default=None, max_length=60_000)
    sources: list[SourceIn] | None = Field(default=None, max_length=40)
    note: str = Field(default="", max_length=4000)


class DeadlineIn(_Strict):
    kind: Literal["deadline"]
    label: str = Field(min_length=1, max_length=300)
    date: dt.date
    citation: str = Field(default="", max_length=300)
    note: str = Field(default="", max_length=4000)
    trigger: str = Field(default="", max_length=300)


class DraftIn(_Strict):
    kind: Literal["draft"]
    draft_id: str = Field(pattern=ID_RE)
    title: str = Field(default="", max_length=300)
    template: str = Field(default="", max_length=64)


ItemIn = Annotated[Union[NoteIn, AnswerIn, DeadlineIn, DraftIn], Field(discriminator="kind")]


# ---------------------------------------------------------------- helpers


def _public_case(e: dict) -> dict:
    return {k: v for k, v in e.items() if not k.startswith("_")}


def _public_item(e: dict) -> dict:
    return {k: v for k, v in e.items() if not k.startswith("_")}


async def _load_case(case_id: str) -> dict:
    if not re.match(ID_RE, case_id):
        raise HTTPException(404, "No such case.")
    case = await get_store().get(CASES, CASE_PK, case_id)
    if not case:
        raise HTTPException(404, "No such case.")
    return case


async def _items(case_id: str) -> list[dict]:
    return [_public_item(e) for e in await get_store().query(ITEMS, pk=case_id)]


# Writes to one case (PATCH, adding or deleting an item, deleting the case)
# run one at a time per process, so a slow item save cannot write back a stale
# copy of the case over a PATCH or bring a deleted case back. The preview runs
# one replica (preview.bicep maxReplicas = 1); _touch also re-reads the case
# right before writing, which narrows the window across replicas.
_case_locks: dict[str, tuple[asyncio.Lock, int]] = {}


@asynccontextmanager
async def case_lock(case_id: str):
    lock, users = _case_locks.get(case_id, (None, 0))
    if lock is None:
        lock = asyncio.Lock()
    _case_locks[case_id] = (lock, users + 1)
    try:
        async with lock:
            yield
    finally:
        lock, users = _case_locks[case_id]
        if users <= 1:
            del _case_locks[case_id]
        else:
            _case_locks[case_id] = (lock, users - 1)


async def _touch(case_id: str, user: str, changes: dict | None = None) -> dict | None:
    """Stamp the case as changed by user (and apply changes) on a fresh read. None when the case is gone."""
    store = get_store()
    fresh = await store.get(CASES, CASE_PK, case_id)
    if not fresh:
        return None
    case = _public_case(fresh)
    case.update(changes or {})
    case["updated_at"] = _now()
    case["updated_by"] = user
    return _public_case(await store.put(CASES, CASE_PK, case_id, case))


def _matches(case: dict, q: str) -> bool:
    if not q:
        return True
    hay = " ".join(
        str(case.get(k) or "") for k in ("id", "address", "map_lot", "owner", "title", "summary")
    ).lower()
    # Type tags have their own filter; "main" should not match "property-maintenance".
    return all(word in hay for word in q.lower().split())


OFFICE_TZ = ZoneInfo("America/New_York")


def _counts(items: list[dict]) -> dict:
    # Deadlines are Maine wall-clock dates; the container runs in UTC.
    today = datetime.now(OFFICE_TZ).date().isoformat()
    kinds: dict[str, int] = {}
    upcoming = None
    for it in items:
        kinds[it.get("kind", "")] = kinds.get(it.get("kind", ""), 0) + 1
        d = it.get("date") if it.get("kind") == "deadline" else None
        if d and d >= today and (upcoming is None or d < upcoming["date"]):
            upcoming = {"date": d, "label": it.get("label", "")}
    return {"item_count": len(items), "kinds": kinds, "next_deadline": upcoming}


# ---------------------------------------------------------------- cases


@router.get("/api/staff/cases")
async def list_cases(
    q: str = Query(default="", max_length=200),
    status: Literal["open", "monitoring", "closed", "all", ""] = "",
    tag: str = Query(default="", max_length=40),
    user: str = Depends(require_staff),
):
    store = get_store()
    cases = [_public_case(c) for c in await store.query(CASES, pk=CASE_PK)]
    total = len(cases)
    if status and status != "all":
        cases = [c for c in cases if c.get("status") == status]
    if tag:
        cases = [c for c in cases if tag in (c.get("tags") or [])]
    q = q.strip()
    cases = [c for c in cases if _matches(c, q)]
    if cases:
        wanted = {c["id"] for c in cases}
        by_case: dict[str, list[dict]] = {}
        for it in await store.query(ITEMS, filter=lambda e: e.get("_pk") in wanted):
            by_case.setdefault(it["_pk"], []).append(it)
        for c in cases:
            c.update(_counts(by_case.get(c["id"], [])))
    cases.sort(key=lambda c: c.get("updated_at") or "", reverse=True)
    return {"cases": cases, "total": total}


@router.post("/api/staff/cases", status_code=201)
async def create_case(body: CaseIn, user: str = Depends(require_staff)):
    store = get_store()
    case_id = _new_case_id()
    while await store.get(CASES, CASE_PK, case_id):
        case_id = _new_case_id()
    now = _now()
    case = {
        "id": case_id,
        **body.model_dump(),
        "created_by": user,
        "created_at": now,
        "updated_by": user,
        "updated_at": now,
    }
    return _public_case(await store.put(CASES, CASE_PK, case_id, case))


@router.get("/api/staff/cases/{case_id}")
async def get_case(case_id: str, user: str = Depends(require_staff)):
    case = _public_case(await _load_case(case_id))
    items = await _items(case_id)
    return {**case, **_counts(items), "items": items}


@router.patch("/api/staff/cases/{case_id}")
async def update_case(case_id: str, body: CasePatch, user: str = Depends(require_staff)):
    changes = body.model_dump(exclude_unset=True)
    if any(v is None for v in changes.values()):
        raise HTTPException(422, "Fields cannot be set to null.")
    async with case_lock(case_id):
        await _load_case(case_id)
        case = await _touch(case_id, user, changes)
    if case is None:
        raise HTTPException(404, "No such case.")
    return case


@router.delete("/api/staff/cases/{case_id}")
async def delete_case(case_id: str, user: str = Depends(require_staff)):
    async with case_lock(case_id):
        await _load_case(case_id)
        store = get_store()
        # The case first, so an item save that slips in from another replica
        # finds no case to touch.
        await store.delete(CASES, CASE_PK, case_id)
        items = await store.query(ITEMS, pk=case_id)
        for it in items:
            await store.delete(ITEMS, case_id, it["_rk"])
    return {"ok": True, "items_deleted": len(items)}


# ---------------------------------------------------------------- items


@router.get("/api/staff/cases/{case_id}/items")
async def list_items(case_id: str, user: str = Depends(require_staff)):
    await _load_case(case_id)
    return {"items": await _items(case_id)}


async def _answer_entity(body: AnswerIn, user: str) -> dict:
    if body.answer_id:
        rec = await get_store().get("answers", user, body.answer_id.lower())
        if rec:
            if rec.get("failed") and not rec.get("answer"):
                raise HTTPException(409, "That answer failed and has nothing to save.")
            return {
                "answer_id": body.answer_id.lower(),
                "question": rec.get("question", ""),
                "answer": rec.get("answer", ""),
                "sources": [{k: s.get(k) for k in SOURCE_FIELDS if s.get(k) is not None} for s in rec.get("sources") or []],
                "cited": rec.get("cited") or [],
                "asked_at": rec.get("ts"),
            }
        if not body.answer:
            raise HTTPException(404, "That answer is no longer stored. Ask it again, then save it.")
    if not body.answer:
        raise HTTPException(422, "Send answer_id, or the question, answer and sources.")
    return {
        "answer_id": (body.answer_id or "").lower() or None,
        "question": body.question or "",
        "answer": body.answer,
        "sources": [s.model_dump(exclude_none=True) for s in body.sources or []],
        "cited": [],
        "asked_at": None,
    }


@router.post("/api/staff/cases/{case_id}/items", status_code=201)
async def add_item(case_id: str, item: ItemIn, user: str = Depends(require_staff)):
    async with case_lock(case_id):
        return await _add_item(case_id, item, user)


async def _add_item(case_id: str, item: ItemIn, user: str) -> dict:
    await _load_case(case_id)
    store = get_store()
    if len(await store.query(ITEMS, pk=case_id)) >= ITEM_LIMIT:
        raise HTTPException(409, f"A case holds at most {ITEM_LIMIT} items.")
    entity: dict[str, Any] = {"kind": item.kind}
    if isinstance(item, NoteIn):
        entity["text"] = item.text
    elif isinstance(item, AnswerIn):
        entity.update(await _answer_entity(item, user))
        entity["note"] = item.note
        entity["stamp"] = prompts.RESEARCH_AID_STAMP
    elif isinstance(item, DeadlineIn):
        entity.update(
            label=item.label, date=item.date.isoformat(), citation=item.citation, note=item.note, trigger=item.trigger
        )
    elif isinstance(item, DraftIn):
        entity.update(draft_id=item.draft_id, title=item.title, template=item.template)
    item_id = _new_item_id()
    now = _now()
    entity.update(id=item_id, case_id=case_id, created_by=user, created_at=now, updated_at=now)
    saved = await store.put(ITEMS, case_id, item_id, entity)
    if await _touch(case_id, user) is None:
        # The case was deleted while the item was saved: drop the orphan.
        await store.delete(ITEMS, case_id, item_id)
        raise HTTPException(404, "No such case.")
    return _public_item(saved)


@router.delete("/api/staff/cases/{case_id}/items/{item_id}")
async def delete_item(case_id: str, item_id: str, user: str = Depends(require_staff)):
    async with case_lock(case_id):
        await _load_case(case_id)
        if not re.match(ID_RE, item_id) or not await get_store().delete(ITEMS, case_id, item_id):
            raise HTTPException(404, "No such item.")
        await _touch(case_id, user)
    return {"ok": True}


# ---------------------------------------------------------------- export


def _when(iso: str | None) -> str:
    try:
        return datetime.fromisoformat(iso or "").astimezone(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    except ValueError:
        return iso or ""


def _md_escape_line(s: str) -> str:
    return " ".join(str(s or "").split())


def case_markdown(case: dict, items: list[dict]) -> str:
    out: list[str] = []
    title = case.get("title") or case.get("address") or case["id"]
    out.append(f"# Case {case['id']}: {_md_escape_line(title)}")
    out.append("")
    rows = [
        ("Address", case.get("address")),
        ("Map/lot", case.get("map_lot")),
        ("Owner", case.get("owner")),
        ("Status", (case.get("status") or "").capitalize()),
        ("Type", ", ".join(TAG_LABELS.get(t, t) for t in case.get("tags") or [])),
        ("Opened", f"{_when(case.get('created_at'))} by {case.get('created_by', '')}"),
        ("Last change", f"{_when(case.get('updated_at'))} by {case.get('updated_by', '')}"),
    ]
    for k, v in rows:
        if v:
            out.append(f"- **{k}:** {_md_escape_line(v)}")
    if case.get("summary"):
        out += ["", case["summary"].strip()]

    deadlines = sorted((i for i in items if i.get("kind") == "deadline"), key=lambda i: i.get("date", ""))
    if deadlines:
        out += ["", "## Deadlines", ""]
        for d in deadlines:
            cite = f" ({_md_escape_line(d['citation'])})" if d.get("citation") else ""
            out.append(f"- **{d.get('date')}**: {_md_escape_line(d.get('label'))}{cite}")

    drafts = [i for i in items if i.get("kind") == "draft"]
    if drafts:
        out += ["", "## Drafts", ""]
        for d in drafts:
            out.append(f"- {_md_escape_line(d.get('title') or d.get('template') or 'Draft')} (draft {d.get('draft_id')})")

    out += ["", "## Timeline", ""]
    if not items:
        out.append("Nothing saved to this case yet.")
    for it in items:
        when = _when(it.get("created_at"))
        kind = it.get("kind")
        who = it.get("created_by", "")
        if kind == "note":
            out += [f"### Note, {when}, {who}", "", it.get("text", "").strip(), ""]
        elif kind == "answer":
            out += [f"### Saved answer, {when}, {who}", ""]
            if it.get("question"):
                out += [f"**Question:** {_md_escape_line(it['question'])}", ""]
            out += [it.get("answer", "").strip(), ""]
            if it.get("note"):
                out += [f"**Note:** {it['note'].strip()}", ""]
            srcs = it.get("sources") or []
            if srcs:
                out.append("Sources:")
                out.append("")
                for s in srcs:
                    name = _md_escape_line(s.get("citation") or s.get("title") or "")
                    extra = _md_escape_line(s.get("title")) if s.get("citation") and s.get("title") else ""
                    url = s.get("open_url") or s.get("url") or ""
                    line = f"{s.get('n')}. {name}"
                    if extra and extra != name:
                        line += f", {extra}"
                    if url:
                        line += f" <{url}>"
                    out.append(line)
                out.append("")
            out += [f"*{it.get('stamp') or prompts.RESEARCH_AID_STAMP}*", ""]
        elif kind == "deadline":
            cite = f" ({_md_escape_line(it['citation'])})" if it.get("citation") else ""
            out += [f"### Deadline added, {when}, {who}", "", f"**{it.get('date')}**: {_md_escape_line(it.get('label'))}{cite}"]
            if it.get("trigger"):
                out.append(f"Trigger: {_md_escape_line(it['trigger'])}")
            if it.get("note"):
                out += ["", it["note"].strip()]
            out.append("")
        elif kind == "draft":
            out += [
                f"### Draft linked, {when}, {who}",
                "",
                f"{_md_escape_line(it.get('title') or it.get('template') or 'Draft')} (draft {it.get('draft_id')})",
                "",
            ]
    out.append(f"Exported {_when(_now())}.")
    return "\n".join(out).rstrip() + "\n"


@router.get("/api/staff/cases/{case_id}/export.md")
async def export_case(case_id: str, user: str = Depends(require_staff)):
    case = _public_case(await _load_case(case_id))
    md = case_markdown(case, await _items(case_id))
    return PlainTextResponse(
        md,
        media_type="text/markdown; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="case-{case_id}.md"', "Cache-Control": "no-store"},
    )


@router.get("/api/staff/case-options")
async def case_options(user: str = Depends(require_staff)):
    """Tag and status vocabularies, so other pages need not hard-code them."""
    return {"tags": [{"value": t, "label": TAG_LABELS[t]} for t in TAGS], "statuses": list(STATUSES)}


__all__ = ["router", "case_markdown", "TAGS", "STATUSES"]

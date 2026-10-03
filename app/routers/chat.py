"""POST /api/chat: public and staff (cite-it) answers as Server-Sent Events.

Request body:
  {"messages": [{"role": "user"|"assistant", "content": str}, ...],
   "mode": "public" | "staff",                       (default "public")
   "filters": {"chapters": [str], "source_types": [str]},   (optional)
   "case_id": str}                                   (optional, staff)

Events, in order:
  event: meta     data: {"mode": "public"|"staff", "answer_id": "<32 hex>"}
  event: sources  data: [{"n": 1, "citation": ..., "title": ..., "breadcrumb": ...,
                          "url": ..., "open_url": ..., "source_type": ..., "label": ...,
                          "page_start": ..., "page_end": ..., "text": ...}, ...]
  event: delta    data: {"text": "..."}          (repeated)
  event: error    data: {"message": "..."}
  event: triage   data: {id, kind, title, lines, links}   (public, at most one, before done)
  event: checklist data: {id, title, sections, forms, bring, ...} (public, instead of triage)
  event: done     data: {}

Staff mode needs a staff session (401 without) and the X-Requested-With: wv
header (403 without). Staff skip the per-IP limits. The UI adds the
research-aid stamp to staff answers; the model never writes it.

Logging: with QUESTION_LOG=1, public questions are scrubbed (app.pii) and
stored in the `questions` table (pk = UTC date, rk = answer_id) with the cited
source numbers and ids and a no_answer flag. Days older than
QUESTION_LOG_RETENTION_DAYS (default 365) are deleted after a new question is
logged. Staff answers are stored in the
`answers` table (pk = username, rk = answer_id) so a case notebook can save
them by id.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field, model_validator

from .. import auth, config, llm, prompts, ratelimit, search
from ..pii import scrub
from ..store import get_store
from . import checklists

log = logging.getLogger("app.chat")

router = APIRouter(tags=["chat"])


# Questions are capped at MAX_QUESTION_CHARS below. Earlier assistant turns can
# be long (a 4,000-token staff answer runs to about 16,000 characters) and are
# trimmed to 2,000 characters before they reach the model, so they get a
# looser cap; a follow-up after a long answer must not fail validation.
MAX_USER_CONTENT = 8000
MAX_ASSISTANT_CONTENT = 40_000


class Message(BaseModel):
    role: str = Field(pattern="^(user|assistant)$")
    content: str = Field(max_length=MAX_ASSISTANT_CONTENT)

    @model_validator(mode="after")
    def _user_length(self):
        if self.role == "user" and len(self.content) > MAX_USER_CONTENT:
            raise ValueError(f"user messages are limited to {MAX_USER_CONTENT} characters")
        return self


class Filters(BaseModel):
    chapters: list[str] | None = Field(default=None, max_length=search.MAX_FILTER_VALUES)
    source_types: list[str] | None = Field(default=None, max_length=search.MAX_FILTER_VALUES)


class ChatRequest(BaseModel):
    messages: list[Message] = Field(min_length=1, max_length=20)
    mode: Literal["public", "staff"] = "public"
    filters: Filters | None = None
    case_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_\-]{1,64}$")


def sse(event: str, data) -> str:
    return f"event: {event}\ndata: {json.dumps(data)}\n\n"


CITE_RE = re.compile(r"\[(\d+)(?:\.[^\]]*)?\]")
NO_ANSWER_RE = re.compile(r"could not find|not in the sources", re.I)


def cited_numbers(answer: str) -> list[int]:
    return sorted({int(n) for n in CITE_RE.findall(answer)})


@router.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    mode = req.mode
    staff_user = auth.current_staff(request)
    if mode == "staff":
        if not staff_user:
            raise HTTPException(401, "Staff sign-in required.")
        auth.check_csrf(request)

    messages = [m.model_dump() for m in req.messages][-6:]
    if messages[-1]["role"] != "user":
        raise HTTPException(400, "The last message must be from the user.")
    question = messages[-1]["content"].strip()
    if not question:
        raise HTTPException(400, "Please enter a question.")
    if len(question) > config.MAX_QUESTION_CHARS:
        raise HTTPException(400, f"Please keep questions under {config.MAX_QUESTION_CHARS} characters.")
    filters = req.filters.model_dump(exclude_none=True) if req.filters else None
    try:
        search.validate_filters(filters, mode)
    except ValueError as e:
        raise HTTPException(400, str(e))
    if msg := ratelimit.check_request(request, staff_user):
        raise HTTPException(429, msg)

    docs = await search.search(search.retrieval_query(messages), mode=mode, filters=filters)
    context, sources = search.format_sources(docs, mode)
    # Staff: tell the model which filters narrowed the search, so a gap reads as out of scope.
    scope = prompts.staff_scope(search.validate_filters(filters, mode)) if mode == "staff" else ""
    # Public: a permit checklist (A1) or a triage card (A2) matched by keyword,
    # sent just before `done`. Clients that do not know the event ignore it.
    # The model is told about a checklist so the answer does not repeat it.
    cards = checklists.chat_cards(question) if mode == "public" else []
    if any(name == "checklist" for name, _ in cards):
        scope += prompts.CHECKLIST_NOTE
    # Earlier assistant turns are trimmed so old answers don't crowd out sources.
    history = [{"role": m["role"], "content": m["content"][:2000]} for m in messages[:-1]]
    chat_messages = (
        [{"role": "system", "content": prompts.system_prompt(mode) + scope + "\n\nSources:\n\n" + context}]
        + history
        + [{"role": "user", "content": question}]
    )
    max_tokens = config.STAFF_MAX_ANSWER_TOKENS if mode == "staff" else config.MAX_ANSWER_TOKENS
    events = await llm.open_stream(chat_messages, max_tokens, kind=mode)
    answer_id = uuid.uuid4().hex

    async def stream():
        yield sse("meta", {"mode": mode, "answer_id": answer_id})
        yield sse("sources", sources)
        parts: list[str] = []
        failed = False
        async for event, data in events:
            if event == "delta":
                parts.append(data["text"])
            elif event == "error":
                failed = True
            elif event == "done":
                for name, card in cards:
                    yield sse(name, card)
            yield sse(event, data)
        await _record(mode, staff_user, answer_id, question, "".join(parts), sources, failed, req.case_id)

    return StreamingResponse(
        stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _record(
    mode: str,
    user: str | None,
    answer_id: str,
    question: str,
    answer: str,
    sources: list[dict],
    failed: bool,
    case_id: str | None,
) -> None:
    """Best-effort logging after the stream ends. Never breaks a response."""
    try:
        now = datetime.now(timezone.utc)
        cited = [n for n in cited_numbers(answer) if 1 <= n <= len(sources)]
        if mode == "staff" and user:
            await get_store().put(
                "answers",
                user,
                answer_id,
                {
                    "question": question,
                    "answer": answer,
                    "sources": sources,
                    "cited": cited,
                    "case_id": case_id,
                    "failed": failed,
                    "ts": now.isoformat(timespec="seconds"),
                },
            )
        elif mode == "public" and config.QUESTION_LOG:
            await get_store().put(
                "questions",
                now.strftime("%Y-%m-%d"),
                answer_id,
                {
                    "question": scrub(question),
                    "cited": cited,
                    "cited_citations": [sources[n - 1].get("citation") for n in cited],
                    "source_citations": [s.get("citation") for s in sources],
                    "no_answer": bool(NO_ANSWER_RE.search(answer)) or not cited,
                    "failed": failed,
                    "answer_chars": len(answer),  # insights: answer length
                    "mode": mode,
                    "ts": now.isoformat(timespec="seconds"),
                },
            )
            # In the background, so the first purge after a start never holds the stream open.
            task = asyncio.create_task(_purge_quietly(now.date()))
            _tasks.add(task)
            task.add_done_callback(_tasks.discard)
    except Exception:  # noqa: BLE001
        log.exception("could not record %s answer %s", mode, answer_id)


_tasks: set[asyncio.Task] = set()


async def _purge_quietly(today: date) -> None:
    try:
        await purge_questions(today)
    except Exception:  # noqa: BLE001
        log.exception("question log purge failed")


# Day partitions already checked by this process. The first purge after a
# start looks back PURGE_LOOKBACK days past the cutoff; later ones only the
# days since the last run.
_purged_through: date | None = None
PURGE_LOOKBACK = 400


async def purge_questions(today: date) -> int:
    """Delete logged questions older than QUESTION_LOG_RETENTION_DAYS. Returns the rows deleted."""
    global _purged_through
    days = config.QUESTION_LOG_RETENTION_DAYS
    if days <= 0:
        return 0
    cutoff = today - timedelta(days=days)  # partitions before this date go
    last = cutoff - timedelta(days=1)
    if _purged_through is not None and _purged_through >= last:
        return 0
    start = _purged_through + timedelta(days=1) if _purged_through else cutoff - timedelta(days=PURGE_LOOKBACK)
    _purged_through = last
    store = get_store()
    deleted = 0
    d = start
    while d <= last:
        pk = d.isoformat()
        for row in await store.query("questions", pk=pk):
            if await store.delete("questions", pk, row["_rk"]):
                deleted += 1
        d += timedelta(days=1)
    if deleted:
        log.info("question log: deleted %d questions older than %d days", deleted, days)
    return deleted

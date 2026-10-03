"""Azure OpenAI chat completions: SSE-ready streaming and a non-streaming helper.

With config.FAKE_AZURE, both return canned text from tests/fixtures/answers.json,
filled with quotes from the first two numbered sources in the prompt.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
from functools import lru_cache
from typing import AsyncIterator

import httpx
from fastapi import HTTPException

from . import config
from .azure_auth import aoai_auth, http

log = logging.getLogger("app.llm")

Event = tuple[str, dict]

BUSY = "The assistant is busy right now. Please try again in a minute."
UNAVAILABLE = "The assistant could not answer right now. Please try again later."
FILTERED = "That request was blocked by the content filter."
INTERRUPTED = "The connection to the assistant was interrupted."


def _url() -> str:
    return (
        f"{config.AOAI_ENDPOINT}/openai/deployments/{config.CHAT_DEPLOYMENT}"
        f"/chat/completions?api-version={config.AOAI_API}"
    )


def _body(messages: list[dict], max_tokens: int, stream: bool) -> dict:
    body = {"messages": messages, "stream": stream, "max_completion_tokens": max_tokens}
    if config.REASONING_EFFORT:
        body["reasoning_effort"] = config.REASONING_EFFORT
    return body


async def open_stream(messages: list[dict], max_tokens: int, kind: str = "public") -> AsyncIterator[Event]:
    """Fetch credentials now (errors surface before the response starts), then
    return an async iterator of (event, data) pairs: "delta", "error", "done".

    An HTTP error status from Azure yields one "error" and ends without "done",
    as the original endpoint did. `kind` picks the FAKE_AZURE template.
    """
    if config.FAKE_AZURE:
        return _fake_stream(messages, kind)
    headers = await aoai_auth.headers()
    return _stream(messages, max_tokens, headers)


async def _stream(messages: list[dict], max_tokens: int, headers: dict) -> AsyncIterator[Event]:
    body = _body(messages, max_tokens, True)
    try:
        async with http.stream("POST", _url(), headers=headers, json=body) as r:
            if r.status_code >= 300:
                text = (await r.aread()).decode(errors="replace")
                log.error("chat failed %s %s", r.status_code, text[:500])
                yield "error", {"message": BUSY if r.status_code == 429 else UNAVAILABLE}
                return
            async for line in r.aiter_lines():
                if not line.startswith("data: "):
                    continue
                payload = line[6:]
                if payload == "[DONE]":
                    break
                chunk = json.loads(payload)
                for choice in chunk.get("choices", []):
                    if choice.get("finish_reason") == "content_filter":
                        yield "error", {"message": FILTERED}
                    text = (choice.get("delta") or {}).get("content")
                    if text:
                        yield "delta", {"text": text}
    except httpx.HTTPError as e:
        log.error("chat stream error: %s", e)
        yield "error", {"message": INTERRUPTED}
    yield "done", {}


async def complete(messages: list[dict], max_tokens: int = 1500, kind: str = "complete") -> str:
    """One non-streaming completion. Raises HTTPException(502/503) on failure."""
    if config.FAKE_AZURE:
        return fake_answer(messages, kind)
    r = await http.post(_url(), headers=await aoai_auth.headers(), json=_body(messages, max_tokens, False))
    if r.status_code >= 300:
        log.error("completion failed %s %s", r.status_code, r.text[:500])
        raise HTTPException(503 if r.status_code == 429 else 502, BUSY if r.status_code == 429 else UNAVAILABLE)
    choice = (r.json().get("choices") or [{}])[0]
    if choice.get("finish_reason") == "content_filter":
        raise HTTPException(422, FILTERED)
    return (choice.get("message") or {}).get("content") or ""


# ---------------------------------------------------------------- fake model


@lru_cache(maxsize=1)
def _templates() -> dict:
    return json.loads((config.FIXTURES_DIR / "answers.json").read_text())


_BLOCK = re.compile(r"^\[(\d+)\] (.+?)\n(.*)", re.S)


def _first_sentence(text: str, limit: int = 220) -> str:
    lines = text.split("\n")
    # Skip the two-line context header (corpus label, breadcrumb) when present.
    if len(lines) >= 3 and not lines[2].strip():
        lines = lines[3:]
    # The first real line of text: skip history notes like "*[Amended ...]*" and headings.
    body = ""
    for line in lines:
        t = line.strip()
        if not t or t.startswith(("*[", "[", "#", "|")) or len(t) < 25:
            continue
        body = re.sub(r"[*_`\[\]]", "", t.lstrip(">- ").strip())
        break
    body = body or re.sub(r"[*_`\[\]]", "", " ".join(l.strip() for l in lines if l.strip()))
    # End at a sentence break that is not an abbreviation (Ord., No., M.R.S.).
    m = re.match(r"(.{30,}?(?<!\b[A-Z])(?<!\bNo)(?<!\bOrd)(?<!\bSec)[.;:])(\s+[A-Z(]|$)", body)
    s = m.group(1) if m else body
    return s if len(s) <= limit else s[: limit - 3].rsplit(" ", 1)[0] + "..."


def fake_answer(messages: list[dict], kind: str) -> str:
    system = messages[0]["content"] if messages and messages[0].get("role") == "system" else ""
    sources = system.split("\n\nSources:\n\n", 1)[1] if "\n\nSources:\n\n" in system else ""
    found = []
    for block in sources.split("\n\n---\n\n"):
        m = _BLOCK.match(block)
        if m:
            found.append((m.group(2), _first_sentence(m.group(3))))
    while len(found) < 2:
        found.append(("The code", "No source text was retrieved."))
    template = _templates().get(kind) or _templates()["public"]
    return template.format(label1=found[0][0], quote1=found[0][1], label2=found[1][0], quote2=found[1][1])


async def _fake_stream(messages: list[dict], kind: str) -> AsyncIterator[Event]:
    text = fake_answer(messages, kind)
    for piece in re.findall(r"\S+\s*|\s+", text):
        if config.FAKE_STREAM_DELAY:
            await asyncio.sleep(config.FAKE_STREAM_DELAY)
        yield "delta", {"text": piece}
    yield "done", {}

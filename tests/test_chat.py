from __future__ import annotations

import json
import re

import httpx
import pytest

from app import config, llm, prompts, store
from conftest import CSRF, parse_sse

Q = {"messages": [{"role": "user", "content": "Can I keep backyard chickens?"}]}
SOURCE_KEYS = ["n", "citation", "title", "breadcrumb", "url", "source_type", "page_start", "page_end", "label", "open_url", "text"]


def test_public_sse_shape(client):
    r = client.post("/api/chat", json=Q)
    assert r.status_code == 200
    assert r.headers["content-type"].startswith("text/event-stream")
    assert r.headers["cache-control"] == "no-cache"
    assert r.headers["x-accel-buffering"] == "no"
    events = parse_sse(r.text)
    names = [e for e, _ in events]
    assert names[0] == "meta" and names[1] == "sources" and names[-1] == "done"
    # "chickens" also matches the A1 checklist, sent once just before done.
    assert set(names[2:-2]) == {"delta"} and names[-2] == "checklist"
    meta = events[0][1]
    assert meta["mode"] == "public" and re.fullmatch(r"[0-9a-f]{32}", meta["answer_id"])
    sources = events[1][1]
    assert sources and [s["n"] for s in sources] == list(range(1, len(sources) + 1))
    assert list(sources[0]) == SOURCE_KEYS
    assert sources[0]["citation"] == "§ 275-4.33"
    answer = "".join(d["text"] for e, d in events if e == "delta")
    assert "[1]" in answer and "[2]" in answer
    assert "six female chickens" in answer
    assert events[-1][1] == {}


def test_public_ignores_unknown_fields(client):
    r = client.post("/api/chat", json={**Q, "extra": 1})
    assert r.status_code == 200


@pytest.mark.parametrize(
    "body,status",
    [
        ({"messages": []}, 422),
        ({"messages": [{"role": "system", "content": "x"}]}, 422),
        ({"messages": [{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}]}, 400),
        ({"messages": [{"role": "user", "content": "   "}]}, 400),
        ({"messages": [{"role": "user", "content": "x" * 1001}]}, 400),
        ({**Q, "mode": "admin"}, 422),
        ({**Q, "filters": {"source_types": ["evil"]}}, 400),
        ({**Q, "filters": {"source_types": ["staff_note"]}}, 400),
        ({**Q, "filters": {"chapters": ["275' or '1"]}}, 400),
    ],
)
def test_public_validation(client, body, status):
    assert client.post("/api/chat", json=body).status_code == status


def test_public_filters_apply(client):
    r = client.post("/api/chat", json={**Q, "filters": {"chapters": ["115"], "source_types": ["code"]}})
    sources = parse_sse(r.text)[1][1]
    assert sources and all("115" in s["citation"] for s in sources)


def test_staff_mode_needs_session(client):
    client.cookies.clear()
    r = client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF)
    assert r.status_code == 401


def test_staff_mode_needs_csrf_header(staff_client):
    r = staff_client.post("/api/chat", json={**Q, "mode": "staff"})
    assert r.status_code == 403


def test_staff_mode_streams_and_records(staff_client):
    r = staff_client.post("/api/chat", json={**Q, "mode": "staff", "case_id": "case-1"}, headers=CSRF)
    assert r.status_code == 200
    events = parse_sse(r.text)
    meta = events[0][1]
    assert meta["mode"] == "staff"
    answer = "".join(d["text"] for e, d in events if e == "delta")
    assert answer.startswith("**§ 275-4.33")
    assert "> " in answer and "[1]" in answer and "[2]" in answer
    assert prompts.RESEARCH_AID_STAMP not in answer
    import asyncio

    saved = asyncio.run(store.get_store().get("answers", "alice", meta["answer_id"]))
    assert saved["question"] == Q["messages"][0]["content"]
    assert saved["case_id"] == "case-1"
    assert saved["cited"] == [1, 2]
    assert saved["sources"][0]["citation"] == "§ 275-4.33"


def test_staff_mode_uses_staff_prompt_and_depth(staff_client, monkeypatch):
    captured = {}

    async def fake_open(messages, max_tokens, kind="public"):
        captured.update(messages=messages, max_tokens=max_tokens, kind=kind)

        async def gen():
            yield "delta", {"text": "ok [1]"}
            yield "done", {}

        return gen()

    monkeypatch.setattr(llm, "open_stream", fake_open)
    staff_client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF)
    assert captured["messages"][0]["content"].startswith(prompts.STAFF_SYSTEM_PROMPT + "\n\nSources:\n\n[1] ")
    assert captured["max_tokens"] == config.STAFF_MAX_ANSWER_TOKENS
    assert captured["kind"] == "staff"
    staff_client.post("/api/chat", json=Q)
    assert captured["messages"][0]["content"].startswith(prompts.PUBLIC_SYSTEM_PROMPT)
    assert "\n\nSources:\n\n[1] " in captured["messages"][0]["content"]
    assert prompts.STAFF_SYSTEM_PROMPT not in captured["messages"][0]["content"]
    assert captured["max_tokens"] == config.MAX_ANSWER_TOKENS


def test_history_trimmed_like_before(client, monkeypatch):
    captured = {}

    async def fake_open(messages, max_tokens, kind="public"):
        captured["messages"] = messages

        async def gen():
            yield "done", {}

        return gen()

    monkeypatch.setattr(llm, "open_stream", fake_open)
    msgs = []
    for i in range(5):
        msgs += [{"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": "a" * 3000}]
    msgs.append({"role": "user", "content": "  last question  "})
    client.post("/api/chat", json={"messages": msgs})
    sent = captured["messages"]
    assert len(sent) == 7  # system + 5 history + question (last 6 messages kept)
    assert all(len(m["content"]) <= 2000 for m in sent[1:-1])
    assert sent[-1] == {"role": "user", "content": "last question"}


def test_question_log(client, monkeypatch):
    monkeypatch.setattr(config, "QUESTION_LOG", True)
    body = {"messages": [{"role": "user", "content": "My name is John Smith, can I keep chickens at 12 Elm Street?"}]}
    r = client.post("/api/chat", json=body)
    answer_id = parse_sse(r.text)[0][1]["answer_id"]
    import asyncio

    rows = asyncio.run(store.get_store().query("questions"))
    assert len(rows) == 1
    row = rows[0]
    assert row["_rk"] == answer_id
    assert "John" not in row["question"] and "12 Elm" not in row["question"]
    assert "chickens" in row["question"]
    assert row["cited"] == [1, 2] and row["no_answer"] is False


def test_no_question_log_by_default(client):
    client.post("/api/chat", json=Q)
    import asyncio

    assert asyncio.run(store.get_store().query("questions")) == []


# ------------------------------------------------ the real Azure OpenAI stream, mocked transport


def _aoai(monkeypatch, handler):
    monkeypatch.setattr(config, "AOAI_ENDPOINT", "https://aoai.example")
    monkeypatch.setattr(llm.aoai_auth, "key", "test-key")
    monkeypatch.setattr(llm, "http", httpx.AsyncClient(transport=httpx.MockTransport(handler)))


def _sse_body(chunks):
    return "".join(f"data: {json.dumps(c)}\n\n" for c in chunks) + "data: [DONE]\n\n"


async def _collect(it):
    return [e async for e in it]


async def test_llm_stream_parses_azure(monkeypatch):
    monkeypatch.setattr(config, "FAKE_AZURE", False)
    seen = {}

    def handler(req):
        seen["body"] = json.loads(req.content)
        seen["headers"] = req.headers
        return httpx.Response(200, text=_sse_body([
            {"choices": []},
            {"choices": [{"delta": {"content": "Hi "}}]},
            {"choices": [{"delta": {"content": "there [1]."}, "finish_reason": None}]},
            {"choices": [{"delta": {}, "finish_reason": "content_filter"}]},
        ]))

    _aoai(monkeypatch, handler)
    monkeypatch.setattr(config, "REASONING_EFFORT", "low")
    events = await _collect(await llm.open_stream([{"role": "user", "content": "q"}], 77))
    assert events == [
        ("delta", {"text": "Hi "}),
        ("delta", {"text": "there [1]."}),
        ("error", {"message": llm.FILTERED}),
        ("done", {}),
    ]
    assert seen["body"]["max_completion_tokens"] == 77 and seen["body"]["stream"] is True
    assert seen["body"]["reasoning_effort"] == "low"
    assert seen["headers"]["api-key"] == "test-key"


async def test_llm_stream_http_error_has_no_done(monkeypatch):
    monkeypatch.setattr(config, "FAKE_AZURE", False)
    _aoai(monkeypatch, lambda r: httpx.Response(429, text="slow down"))
    events = await _collect(await llm.open_stream([{"role": "user", "content": "q"}], 10))
    assert events == [("error", {"message": llm.BUSY})]
    _aoai(monkeypatch, lambda r: httpx.Response(500, text="boom"))
    events = await _collect(await llm.open_stream([{"role": "user", "content": "q"}], 10))
    assert events == [("error", {"message": llm.UNAVAILABLE})]


async def test_llm_stream_transport_error(monkeypatch):
    monkeypatch.setattr(config, "FAKE_AZURE", False)

    def handler(req):
        raise httpx.ConnectError("down")

    _aoai(monkeypatch, handler)
    events = await _collect(await llm.open_stream([{"role": "user", "content": "q"}], 10))
    assert events == [("error", {"message": llm.INTERRUPTED}), ("done", {})]


async def test_llm_complete(monkeypatch):
    assert "offline" in await llm.complete([{"role": "user", "content": "q"}])
    monkeypatch.setattr(config, "FAKE_AZURE", False)
    _aoai(monkeypatch, lambda r: httpx.Response(200, json={"choices": [{"message": {"content": "text"}, "finish_reason": "stop"}]}))
    assert await llm.complete([{"role": "user", "content": "q"}]) == "text"

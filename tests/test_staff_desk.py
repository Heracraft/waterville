"""Staff research desk (B1): the cite-it prompt, retrieval depth, edition labels and the § 4452 penalty pin."""

from __future__ import annotations

import pytest

from app import config, llm, prompts, search
from conftest import CSRF, parse_sse

Q = {"messages": [{"role": "user", "content": "Can I keep backyard chickens?"}]}
ENFORCE_Q = {"messages": [{"role": "user", "content": "What penalty applies to a property maintenance violation?"}]}


@pytest.fixture
def capture(monkeypatch):
    captured: dict = {}

    async def fake_open(messages, max_tokens, kind="public"):
        captured.update(messages=messages, max_tokens=max_tokens, kind=kind)

        async def gen():
            yield "delta", {"text": "**§ 275-4.33**\n\n> text [1]"}
            yield "done", {}

        return gen()

    monkeypatch.setattr(llm, "open_stream", fake_open)
    return captured


def _system(captured) -> str:
    return captured["messages"][0]["content"]


# ------------------------------------------------ the prompt


def test_staff_prompt_rules():
    p = prompts.STAFF_SYSTEM_PROMPT
    # Prose with sections named and cited inline; no pasted source blocks.
    assert "Name each section in the sentence that relies on it" in p
    assert "Do not paste blocks of source text" in p
    assert '"> "' not in p
    # The enforcement chain with the § 4452(3) tier as the sources state it.
    assert "Enforcement chain" in p and "30-A M.R.S. § 4452(3)" in p and "Rule 80K" in p
    assert "Never carry a figure from one paragraph to another" in p
    assert "A repeat complaint or a second notice of violation is not a conviction" in p
    # Conflicts and stale editions named; plain "not in the sources".
    assert "Conflicts and currency" in p and "stale" in p
    assert '"Not in the sources."' in p
    # No Clerk fallback and no stamp or disclaimer from the model.
    assert "Do not refer the user to the City Clerk" in p
    assert "207-680-4200" not in p
    assert prompts.RESEARCH_AID_STAMP not in p
    # The prompt has no em dashes (house style).
    assert "—" not in p


def test_system_prompt_picks_mode():
    assert prompts.system_prompt("staff") is prompts.STAFF_SYSTEM_PROMPT
    assert prompts.system_prompt("public") is prompts.PUBLIC_SYSTEM_PROMPT


def test_staff_scope_note():
    assert prompts.staff_scope(None) == ""
    assert prompts.staff_scope({}) == ""
    note = prompts.staff_scope({"chapters": ["205", "275"], "source_types": ["code"]})
    assert "City Code chapters 205, 275" in note and "source types code" in note


def test_staff_chat_uses_staff_prompt(staff_client, capture):
    r = staff_client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF)
    assert r.status_code == 200
    parse_sse(r.text)
    assert capture["kind"] == "staff"
    assert _system(capture).startswith(prompts.STAFF_SYSTEM_PROMPT + "\n\nSources:\n\n[1] ")
    assert capture["max_tokens"] == config.STAFF_MAX_ANSWER_TOKENS


def test_public_chat_never_gets_staff_prompt(staff_client, capture):
    # Signed-in staff asking without mode=staff get the public prompt.
    staff_client.post("/api/chat", json=Q)
    assert capture["kind"] == "public"
    assert _system(capture).startswith(prompts.PUBLIC_SYSTEM_PROMPT + prompts.CHECKLIST_NOTE + "\n\nSources:\n\n[1] ")
    assert "STAFF" not in _system(capture) and "Enforcement chain" not in _system(capture)


def test_checklist_note_only_with_a_checklist_card(client, capture):
    # A matched checklist card tells the model not to repeat it.
    client.post("/api/chat", json={"messages": [{"role": "user", "content": "How tall can my fence be?"}]})
    assert prompts.CHECKLIST_NOTE in _system(capture)
    # No card, no note.
    client.post("/api/chat", json={"messages": [{"role": "user", "content": "When does the city council meet?"}]})
    assert prompts.CHECKLIST_NOTE not in _system(capture)


def test_staff_filters_reach_prompt(staff_client, capture):
    body = {**Q, "mode": "staff", "filters": {"chapters": ["275"], "source_types": ["code"]}}
    staff_client.post("/api/chat", json=body, headers=CSRF)
    system = _system(capture)
    assert system.startswith(prompts.STAFF_SYSTEM_PROMPT + prompts.staff_scope({"chapters": ["275"], "source_types": ["code"]}))
    assert "\n\nSources:\n\n[1] § 275-" in system


def test_staff_sources_carry_edition(staff_client, capture):
    r = staff_client.post("/api/chat", json={**Q, "mode": "staff"}, headers=CSRF)
    sources = parse_sse(r.text)[1][1]
    assert sources[0]["legislation_through"] == "08-05-2026"
    system = _system(capture)
    assert "\n\nSources:\n\n[1] § 275-4.33\n" in system
    assert "\n(Edition: legislation through 08-05-2026)\n\n---\n\n[2] " in system


def test_public_sources_unchanged(client, capture):
    r = client.post("/api/chat", json=Q)
    sources = parse_sse(r.text)[1][1]
    assert "legislation_through" not in sources[0]
    assert "Edition:" not in _system(capture)


# ------------------------------------------------ retrieval depth


async def test_staff_depth_from_config(monkeypatch):
    monkeypatch.setattr(config, "MIN_RERANKER_SCORE", 0.0)
    monkeypatch.setattr(config, "STAFF_K_LOCAL", 7)
    monkeypatch.setattr(config, "STAFF_K_STATE", 0)
    docs = await search.search("building permit", mode="staff")
    assert len(docs) == 7
    monkeypatch.setattr(config, "STAFF_K_LOCAL", 11)
    assert len(await search.search("building permit", mode="staff")) == 11
    public = await search.search("building permit", mode="public")
    assert len([d for d in public if d.get("source_type") in search.LOCAL_TYPES]) == config.LOCAL_K


# ------------------------------------------------ § 4452 penalty pin


def _with_4452(monkeypatch):
    # The fixtures carry the real § 4452 text; swap it for these short chunks.
    docs = [d for d in search.fake_docs() if d.get("citation") != "30-A M.R.S. § 4452"]
    head = "Maine Revised Statutes\nTitle 30-A > 30-A M.R.S. § 4452. Enforcement of land use laws and ordinances\n\n"
    for i, body in enumerate(
        [
            "1. Powers. A municipal code enforcement officer may enter any property at reasonable hours.",
            "3. Civil penalties. The following provisions apply to violations of the laws and ordinances.",
            "5. Applicability. This section applies to the enforcement of land use laws.",
        ]
    ):
        docs.append(
            {
                "id": f"ext-mrs-30a-4452-{i}",
                "source_type": "state_statute",
                "citation": "30-A M.R.S. § 4452",
                "title": "30-A M.R.S. § 4452. Enforcement of land use laws and ordinances",
                "breadcrumb": "Title 30-A > 30-A M.R.S. § 4452. Enforcement of land use laws and ordinances",
                "url": "https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html",
                "content": head + body,
                "chunk_index": i,
                "chunk_count": 3,
            }
        )
    monkeypatch.setattr(search, "_fixture_docs", lambda: tuple(docs))


async def test_enforcement_question_pins_penalty_text(monkeypatch):
    _with_4452(monkeypatch)
    # Ranks low on "chickens", so only the pin can bring it in.
    docs = await search.search("chicken violation", mode="staff", k_state=0)
    pinned = [d for d in docs if d.get("citation") == "30-A M.R.S. § 4452"]
    assert [d["id"] for d in pinned] == ["ext-mrs-30a-4452-1"]
    assert docs[-1]["id"] == "ext-mrs-30a-4452-1"


async def test_no_pin_for_public_or_other_questions(monkeypatch):
    _with_4452(monkeypatch)
    for docs in (
        await search.search("chicken violation", mode="public", k_state=0),
        await search.search("chickens in the yard", mode="staff", k_state=0),
        await search.search("chicken violation", mode="staff", k_state=0, filters={"source_types": ["code"]}),
    ):
        assert not any(d.get("citation") == "30-A M.R.S. § 4452" for d in docs)


async def test_pin_not_duplicated(monkeypatch):
    _with_4452(monkeypatch)
    docs = await search.search("civil penalties enforcement 4452", mode="staff")
    ids = [d.get("id") for d in docs]
    assert len(ids) == len(set(ids))


def test_staff_enforcement_answer_gets_statute_source(staff_client, capture, monkeypatch):
    _with_4452(monkeypatch)
    r = staff_client.post("/api/chat", json={**ENFORCE_Q, "mode": "staff"}, headers=CSRF)
    sources = parse_sse(r.text)[1][1]
    assert any(s["citation"] == "30-A M.R.S. § 4452" and "Civil penalties" in s["text"] for s in sources)
    assert "30-A M.R.S. § 4452 (Maine statute)" in _system(capture)

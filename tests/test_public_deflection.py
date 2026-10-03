"""Public deflection features: A1 checklists, A2 triage and prompt rules,
A3 permit router, A4 fee estimator, A6 frame headers."""

from __future__ import annotations

import pytest

from app import config, prompts
from app.routers import checklists
from conftest import CSRF, parse_sse

TOPICS = {
    "fence",
    "shed",
    "deck",
    "pool",
    "sign",
    "home_occupation",
    "conversion",
    "chickens",
    "short_term_rental",
    "demolition",
    "solar",
    "heat_pump",
}
CONFIRM = "Confirm with Code Enforcement (207-680-4208) before you build."


# ------------------------------------------------------------------ data


def test_every_topic_has_a_checklist():
    ids = [c["id"] for c in checklists.data()["checklist"]]
    assert set(ids) == TOPICS and len(ids) == len(TOPICS)


@pytest.mark.parametrize("cid", sorted(TOPICS))
def test_checklist_card_is_complete(cid):
    card = checklists.card(checklists._checklist(cid))
    assert card["confirm_line"] == CONFIRM
    assert card["sections"], "each checklist cites its controlling sections"
    for s in card["sections"]:
        assert s["citation"].startswith("§ ") and s["url"].startswith("https://ecode360.com/") and s["says"]
    assert card["bring"]
    for f in card["forms"] + [card["fire_review"]["form"]]:
        assert f["url"].startswith("https://www.waterville-me.gov/DocumentCenter/View/")
    if card["building_permit"]:
        # Mirrors the building permit application's fields.
        joined = " ".join(card["bring"])
        for field in ("Map and lot", "Foundation type", "Setbacks", "site plan drawn to scale", "construction cost"):
            assert field in joined
    assert card["fire_review"]["status"] in ("yes", "likely", "maybe", "no")


def test_data_follows_writing_rules():
    text = checklists.DATA_PATH.read_text(encoding="utf-8")
    assert "—" not in text and "–" not in text
    # Never tell a resident a permit is not needed.
    lowered = text.lower()
    for phrase in ("no permit is needed", "no permit needed", "does not need a permit", "don't need a permit"):
        assert phrase not in lowered


# ------------------------------------------------------------------ matching (A1)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("How tall can a fence be in a residential zone?", "fence"),
        ("Do I need a fence around my in-ground pool?", "pool"),
        ("Can I build a shed in my backyard?", "shed"),
        ("What are the setbacks for a detached garage?", "shed"),
        ("Do I need a permit to build a deck?", "deck"),
        ("Can I put up a sign for my shop?", "sign"),
        ("What size business sign is allowed downtown?", "sign"),
        ("Can I run a business out of my home?", "home_occupation"),
        ("What are the rules for a home occupation?", "home_occupation"),
        ("Can I convert my house into three apartments?", "conversion"),
        ("Is a triplex allowed in R-B?", "conversion"),
        ("Can I keep chickens in my backyard?", "chickens"),
        ("How many hens can I have?", "chickens"),
        ("Can I list my house on Airbnb?", "short_term_rental"),
        ("What does a short-term rental license cost?", "short_term_rental"),
        ("I want to tear down my old garage", "demolition"),
        ("Do I need a permit to demolish a house?", "demolition"),
        ("Can I put solar panels on my roof?", "solar"),
        ("Do I need a permit to install a mini-split heat pump?", "heat_pump"),
    ],
)
def test_checklist_matching(question, expected):
    assert checklists.match_triage(question) is None
    c = checklists.match_checklist(question)
    assert c and c["id"] == expected


@pytest.mark.parametrize(
    "question",
    [
        "Are consumer fireworks allowed in Waterville?",
        "When is the City Council meeting?",
        "Do I have to sign the form in person?",
        "What is the design standard for downtown?",
    ],
)
def test_no_checklist_for_unrelated_questions(question):
    assert checklists.match_checklist(question) is None


# ------------------------------------------------------------------ triage (A2)


@pytest.mark.parametrize(
    "question,expected",
    [
        ("My apartment has no heat and it's January", "life_safety"),
        ("There is sewage in my basement", "life_safety"),
        ("The porch is sagging and looks like it could collapse", "life_safety"),
        ("My neighbor's house is a fire hazard", "life_safety"),
        ("My landlord is trying to evict me and the furnace is broken", "life_safety"),
        ("Can my landlord keep my security deposit?", "out_of_scope"),
        ("How do I evict a tenant?", "out_of_scope"),
        ("We have a boundary dispute with the neighbor", "out_of_scope"),
        ("My neighbor's fence encroaches on my property", "out_of_scope"),
    ],
)
def test_triage(question, expected):
    t = checklists.match_triage(question)
    assert t and t["id"] == expected
    cards = checklists.chat_cards(question)
    assert [name for name, _ in cards] == ["triage"], "triage replaces the checklist"


def test_life_safety_card_routes_to_code_and_fire():
    card = dict(checklists.chat_cards("no heat in my apartment"))["triage"]
    text = " ".join(card["lines"])
    assert "911" in text and "207-680-4208" in text and "§ 210-10" in text
    assert card["kind"] == "urgent"
    assert {"label": "Prepare a complaint sheet", "href": "/complaint"} in card["links"]


def test_out_of_scope_card_still_routes_hazards():
    card = dict(checklists.chat_cards("how do I evict my tenant"))["triage"]
    text = " ".join(card["lines"])
    assert "does not give landlord-tenant or legal advice" in text
    assert "no heat" in text and "207-680-4208" in text


# ------------------------------------------------------------------ prompt rules (A1, A2)


def test_public_prompt_rules():
    p = prompts.PUBLIC_SYSTEM_PROMPT
    assert "Never state that no permit, license or approval is needed as a final answer" in p
    assert CONFIRM in p
    assert "does not give landlord-tenant or legal advice" in p
    assert "licensed land surveyor" in p
    assert "Never turn away a report of unsafe or unsanitary conditions" in p
    for hazard in ("no heat", "sewage", "structural damage", "fire hazard"):
        assert hazard in p
    assert "Fire Department" in p and "911" in p
    assert "Never say the city cannot help" in p
    # The old rules stay.
    assert "Use only the numbered sources below." in p and "207-680-4200" in p
    assert "—" not in p


def test_staff_prompt_unchanged_by_public_rules():
    assert CONFIRM not in prompts.STAFF_SYSTEM_PROMPT
    assert prompts.system_prompt("public") is prompts.PUBLIC_SYSTEM_PROMPT


def test_public_chat_sends_public_prompt_with_rules(client, monkeypatch):
    seen = {}

    async def fake_open_stream(messages, max_tokens, kind="public"):
        seen["system"] = messages[0]["content"]

        async def gen():
            yield "delta", {"text": "Answer [1]."}
            yield "done", {}

        return gen()

    from app import llm

    monkeypatch.setattr(llm, "open_stream", fake_open_stream)
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": "Can I build a deck?"}]})
    assert r.status_code == 200
    assert CONFIRM in seen["system"] and "Never turn away" in seen["system"]


# ------------------------------------------------------------------ SSE (A1)


def _chat(client, q):
    r = client.post("/api/chat", json={"messages": [{"role": "user", "content": q}]})
    assert r.status_code == 200, r.text
    return parse_sse(r.text)


def test_chat_emits_checklist_before_done(client):
    events = _chat(client, "Can I keep backyard chickens?")
    names = [e for e, _ in events]
    assert names[:2] == ["meta", "sources"] and names[-2:] == ["checklist", "done"]
    assert names.count("checklist") == 1
    card = events[-2][1]
    assert card["id"] == "chickens" and card["confirm_line"] == CONFIRM
    assert card["permit_guide"] == "/permits?project=chickens"
    assert any("$25" in s["says"] for s in card["sections"])


def test_chat_emits_triage_for_life_safety(client):
    events = _chat(client, "There is no heat in my apartment and the landlord won't fix it")
    names = [e for e, _ in events]
    assert names[-2:] == ["triage", "done"] and "checklist" not in names
    assert events[-2][1]["id"] == "life_safety"


def test_chat_without_match_is_unchanged(client):
    events = _chat(client, "Are consumer fireworks allowed?")
    names = [e for e, _ in events]
    assert names[0] == "meta" and names[1] == "sources" and names[-1] == "done"
    assert set(names[2:-1]) == {"delta"}


def test_staff_chat_gets_no_cards(staff_client):
    r = staff_client.post(
        "/api/chat",
        json={"messages": [{"role": "user", "content": "Can I keep backyard chickens?"}], "mode": "staff"},
        headers=CSRF,
    )
    names = [e for e, _ in parse_sse(r.text)]
    assert "checklist" not in names and "triage" not in names and names[-1] == "done"


def test_no_cards_when_stream_has_no_done(client, monkeypatch):
    from app import llm

    async def broken(messages, max_tokens, kind="public"):
        async def gen():
            yield "error", {"message": llm.UNAVAILABLE}

        return gen()

    monkeypatch.setattr(llm, "open_stream", broken)
    names = [e for e, _ in _chat(client, "Can I build a shed?")]
    assert names == ["meta", "sources", "error"]


# ------------------------------------------------------------------ checklist API


def test_checklist_api(client):
    r = client.get("/api/checklists")
    assert r.status_code == 200
    body = r.json()
    assert {c["id"] for c in body["checklists"]} == TOPICS
    assert body["office_phone"] == "207-680-4208" and body["confirm_line"] == CONFIRM
    assert client.get("/api/checklists/fence").json()["title"] == "Fence"
    assert client.get("/api/checklists/nope").status_code == 404
    m = client.get("/api/checklists/match", params={"q": "Can I build a deck?"}).json()
    assert m["checklist"]["id"] == "deck" and m["triage"] is None
    m = client.get("/api/checklists/match", params={"q": "sewage in the yard"}).json()
    assert m["checklist"] is None and m["triage"]["id"] == "life_safety"
    assert client.get("/api/checklists/match", params={"q": ""}).status_code == 422
    assert client.get("/api/checklists/match", params={"q": "x" * 1001}).status_code == 422


# ------------------------------------------------------------------ permit router (A3)


def _route(client, project, **answers):
    r = client.post("/api/permit-router", json={"project": project, "answers": answers})
    assert r.status_code == 200, r.text
    return r.json()


def test_router_options(client):
    body = client.get("/api/permit-router").json()
    ids = {p["id"] for p in body["projects"]}
    assert TOPICS <= ids
    fire = {q["id"] for q in body["questions"] if q["fire"]}
    assert fire == {"new_construction", "renovation_over_75", "life_safety_change", "change_of_occupancy", "solar"}


def test_router_solar_needs_fire_review(client):
    r = _route(client, "solar")
    assert r["fire_review"]["status"] == "required"
    assert "A solar system" in r["fire_review"]["reasons"]
    assert {p["id"] for p in r["permits"]} == {"building", "electrical"}
    assert r["checklist"]["id"] == "solar" and r["confirm_line"] == CONFIRM


@pytest.mark.parametrize("flag", ["new_construction", "renovation_over_75", "life_safety_change", "change_of_occupancy", "solar"])
def test_router_each_fire_trigger(client, flag):
    r = _route(client, "renovation", **{flag: True})
    assert r["fire_review"]["status"] == "required" and len(r["fire_review"]["reasons"]) == 1


def test_router_conversion(client):
    r = _route(client, "conversion")
    assert r["fire_review"]["status"] == "required"
    assert {p["id"] for p in r["permits"]} == {"building", "change_of_use"}


def test_router_fence_never_says_no_permit(client):
    r = _route(client, "fence")
    assert r["permits"] == []
    assert "Ask the office whether your fence needs a building permit" in r["ask_office"]
    assert r["fire_review"]["status"] == "not_indicated"
    assert "makes the final call" in r["fire_review"]["text"]


def test_router_answers_override_defaults(client):
    r = _route(client, "deck", new_construction=False)
    assert r["fire_review"]["status"] == "ask"


def test_router_extra_permits_and_reviews(client):
    r = _route(client, "addition", electrical=True, plumbing=True, historic=True, shoreland=True)
    assert [p["id"] for p in r["permits"]] == ["building", "electrical", "plumbing"]
    titles = {a["title"] for a in r["also"]}
    assert titles == {"Certificate of appropriateness", "Shoreland zone review"}
    shore = next(a for a in r["also"] if a["title"] == "Shoreland zone review")
    assert "Planning Board approves" in shore["why"]


def test_router_rejects_bad_input(client):
    assert client.post("/api/permit-router", json={"project": "moat"}).status_code == 400
    assert client.post("/api/permit-router", json={"project": "deck", "answers": {"lava": True}}).status_code == 400
    assert client.post("/api/permit-router", json={"project": "deck", "x": 1}).status_code == 422


# ------------------------------------------------------------------ fees (A4)


def test_fee_schedule(client):
    body = client.get("/api/fees").json()
    assert body["building"]["published"] is False
    assert "not published online" in body["building"]["note"]
    assert body["building"]["citation"] == "§ 127-3A"
    assert body["life_safety"]["rate"] == "0.0015"
    mins = {m["id"]: m["cents"] for m in body["electrical"]["minimum"]}
    assert mins == {"single_family": 4500, "two_family": 7500, "temporary": 2700}
    items = {i["id"]: i["cents"] for i in body["electrical"]["items"]}
    assert items["service_800"] == 7500 and items["service_801"] == 8500 and items["opening"] == 50
    assert items["photovoltaic"] == 7500


@pytest.mark.parametrize("cost,cents", [(100_000, 15000), (33_333.33, 5000), (0, 0), (1234.56, 185)])
def test_life_safety_estimate(client, cost, cents):
    r = client.post("/api/fees/estimate", json={"life_safety": {"construction_cost": cost}})
    assert r.status_code == 200
    body = r.json()
    assert body["estimate"] is True
    assert body["life_safety"]["estimate_cents"] == cents


def test_electrical_estimate_line_items(client):
    r = client.post(
        "/api/fees/estimate",
        json={"electrical": {"occupancy": "single_family", "items": {"opening": 20, "service_800": 1, "pool": 0}}},
    ).json()["electrical"]
    assert r["subtotal_cents"] == 20 * 50 + 7500
    assert r["estimate_cents"] == 8500 and r["basis"] == "line_items"
    assert [x["id"] for x in r["lines"]] == ["service_800", "opening"]


def test_electrical_estimate_minimum(client):
    r = client.post(
        "/api/fees/estimate", json={"electrical": {"occupancy": "single_family", "items": {"opening": 10}}}
    ).json()["electrical"]
    assert r["subtotal_cents"] == 500 and r["estimate_cents"] == 4500 and r["basis"] == "minimum"


def test_fee_estimate_rejects_bad_input(client):
    post = lambda body: client.post("/api/fees/estimate", json=body).status_code  # noqa: E731
    assert post({"electrical": {"items": {"moat": 1}}}) == 400
    assert post({"electrical": {"items": {"opening": -1}}}) == 400
    assert post({"electrical": {"occupancy": "castle"}}) == 400
    assert post({"life_safety": {"construction_cost": -5}}) == 422
    assert post({"building": {}}) == 422


# ------------------------------------------------------------------ frame headers (A6)


@pytest.fixture
def build(tmp_path, monkeypatch):
    root = tmp_path / "build"
    root.mkdir()
    (root / "index.html").write_text("<!doctype html><title>shell</title>")
    monkeypatch.setenv("WEB_DIR", str(root))
    return root


@pytest.mark.parametrize("path", ["/", "/permits", "/fees", "/complaint", "/staff", "/staff/login", "/embedded", "/api/checklists"])
def test_frames_denied_outside_embed(client, build, path):
    r = client.get(path)
    assert r.headers["x-frame-options"] == "DENY", path
    assert r.headers["content-security-policy"].split("; ")[-1] == "frame-ancestors 'none'", path


@pytest.mark.parametrize("path", ["/embed", "/embed/"])
def test_embed_frame_ancestors(client, build, path):
    r = client.get(path)
    assert r.status_code == 200
    assert "x-frame-options" not in r.headers
    csp = r.headers["content-security-policy"].split("; ")[-1]
    assert csp == "frame-ancestors 'self' " + " ".join(config.EMBED_ORIGINS)


def test_embed_origins_from_env(client, build, monkeypatch):
    monkeypatch.setattr(config, "EMBED_ORIGINS", ["https://city.example"])
    csp = client.get("/embed").headers["content-security-policy"].split("; ")[-1]
    assert csp == "frame-ancestors 'self' https://city.example"

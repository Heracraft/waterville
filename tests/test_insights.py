from __future__ import annotations

import asyncio
import datetime as dt

import pytest

from app import config, store
from app.routers import insights
from tests.conftest import CSRF, parse_sse

TODAY = dt.datetime.now(dt.timezone.utc).date()


@pytest.fixture(autouse=True)
def _reset_feedback_limit():
    insights.feedback_limiter.reset()
    yield
    insights.feedback_limiter.reset()


def put(table, pk, rk, entity):
    return asyncio.run(store.get_store().put(table, pk, rk, entity))


def q(day: dt.date, rk: str, question: str, cited=(), no_answer=False, failed=False, chars=400):
    put(
        "questions",
        day.isoformat(),
        rk,
        {
            "question": question,
            "cited": list(range(1, len(cited) + 1)),
            "cited_citations": list(cited),
            "no_answer": no_answer,
            "failed": failed,
            "answer_chars": chars,
            "mode": "public",
            "ts": f"{day.isoformat()}T12:00:{len(rk) % 60:02d}+00:00",
        },
    )


# ---------------------------------------------------------------- topics


@pytest.mark.parametrize(
    "text,topic",
    [
        ("How tall can a fence be in a residential zone?", "fences"),
        ("Can I keep chickens in my backyard?", "animals"),
        ("What does a short-term rental license cost?", "str"),
        ("Do I need a permit for a 10 x 12 shed?", "sheds"),
        ("My landlord won't return my security deposit", "rental"),
        ("Can I turn my house into a duplex?", "units"),
        ("Are consumer fireworks allowed in Waterville?", "fireworks"),
        ("What is the setback from the property line?", "setbacks"),
        ("Neighbor has junk cars and trash everywhere", "maintenance"),
        ("Can I build a dock on Messalonskee Stream?", "shoreland"),
        ("How big can a sign be downtown?", "signs"),
        ("Do I need a building permit to finish my basement?", "permits"),
        ("My apartment has no heat and mold", "unsafe"),
    ],
)
def test_topic_of(text, topic):
    assert insights.topic_of(text)[0] == topic


def test_topic_of_no_match():
    assert insights.topic_of("Who is the mayor?") is None


def test_cluster_groups_and_orders():
    rows = [
        {"question": "fence height in front yard", "ts": "2026-10-01T10:00:00"},
        {"question": "Fence height in front yard", "ts": "2026-10-02T10:00:00"},
        {"question": "fence along the road", "ts": "2026-10-03T10:00:00", "no_answer": True},
        {"question": "chickens allowed?", "ts": "2026-10-01T11:00:00"},
        {"question": "Who is the mayor?", "ts": "2026-10-01T12:00:00"},
        {"question": "When does the mayor hold office hours?", "ts": "2026-10-01T13:00:00"},
        {"question": "What day is trash pickup?", "ts": "2026-10-01T14:00:00"},
        {"question": "Qwerty zxcv", "ts": "2026-10-01T15:00:00"},
    ]
    out = insights.cluster(rows)
    assert out[0]["id"] == "fences" and out[0]["count"] == 3 and out[0]["unanswered"] == 1
    # Newest first, duplicates (ignoring case) shown once.
    assert out[0]["examples"] == ["fence along the road", "Fence height in front yard"]
    ids = [g["id"] for g in out]
    assert "word:mayor" in ids
    mayor = next(g for g in out if g["id"] == "word:mayor")
    assert mayor["count"] == 2 and mayor["label"] == 'Other: "mayor"'
    assert ids[-1] == "other"  # leftovers sink to the bottom
    assert next(g for g in out if g["id"] == "other")["count"] == 1


def test_cluster_limit():
    rows = [{"question": f"{t} question", "ts": ""} for t in ("fence", "shed", "deck", "sign", "chickens")]
    assert len(insights.cluster(rows, limit=3)) == 3


# ---------------------------------------------------------------- summarize


def test_summarize_numbers():
    days = [TODAY - dt.timedelta(days=2), TODAY - dt.timedelta(days=1), TODAY]
    questions = [
        {"_pk": days[0].isoformat(), "_rk": "a" * 32, "question": "fence?", "cited_citations": ["§ 275-4.12", "§ 275-4.12"],
         "no_answer": False, "failed": False, "answer_chars": 300, "ts": days[0].isoformat() + "T01:00:00"},
        {"_pk": days[2].isoformat(), "_rk": "b" * 32, "question": "mayor?", "cited_citations": [],
         "no_answer": True, "failed": False, "answer_chars": 100, "ts": days[2].isoformat() + "T01:00:00"},
        {"_pk": days[2].isoformat(), "_rk": "c" * 32, "question": "shed?", "cited_citations": ["§ 275-4.12", "§ 127-3"],
         "no_answer": True, "failed": True, "ts": days[2].isoformat() + "T02:00:00"},
    ]
    votes = [
        {"_pk": days[2].isoformat(), "_rk": "a" * 32, "helpful": True, "ts": "x2"},
        {"_pk": days[2].isoformat(), "_rk": "b" * 32, "helpful": False, "ts": "x1"},
        {"_pk": days[2].isoformat(), "_rk": "f" * 32, "helpful": False, "ts": "x3"},  # question not logged
    ]
    out = insights.summarize(questions, votes, days)
    t = out["totals"]
    assert t == {
        "questions": 3,
        "answered": 1,
        "unanswered": 1,
        "failed": 1,
        "unanswered_rate": 0.5,
        "avg_answer_chars": 200,
    }
    assert [d["count"] for d in out["volume"]] == [1, 0, 2]
    assert out["volume"][2] == {"date": days[2].isoformat(), "count": 2, "unanswered": 1, "failed": 1}
    # A citation counts once per question.
    assert out["top_sections"] == [{"citation": "§ 275-4.12", "count": 2}, {"citation": "§ 127-3", "count": 1}]
    assert out["unanswered_examples"] == [{"date": days[2].isoformat(), "question": "mayor?", "times": 1}]
    fb = out["feedback"]
    assert (fb["yes"], fb["no"], fb["total"]) == (1, 2, 3)
    assert fb["helpful_rate"] == pytest.approx(0.3333, abs=1e-4)
    assert fb["not_helpful"] == [{"date": days[2].isoformat(), "question": "mayor?", "cited": [], "times": 1}]


def test_summarize_empty():
    out = insights.summarize([], [], [TODAY])
    assert out["totals"]["questions"] == 0
    assert out["totals"]["unanswered_rate"] is None
    assert out["feedback"]["helpful_rate"] is None
    assert out["topics"] == [] and out["top_sections"] == []


# ---------------------------------------------------------------- endpoint


def test_insights_needs_staff(client):
    assert client.get("/api/staff/insights").status_code == 401
    assert client.get("/api/staff/reports").status_code == 401
    assert client.get("/api/staff/reports/lpi").status_code == 401


def test_insights_endpoint(staff_client):
    q(TODAY, "1" * 32, "fence height?", cited=["§ 275-4.12"])
    q(TODAY - dt.timedelta(days=3), "2" * 32, "chickens?", no_answer=True)
    q(TODAY - dt.timedelta(days=40), "3" * 32, "old question")
    r = staff_client.get("/api/staff/insights", params={"days": 7})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["range"] == {"start": (TODAY - dt.timedelta(days=6)).isoformat(), "end": TODAY.isoformat(), "days": 7}
    assert len(data["volume"]) == 7
    assert data["totals"]["questions"] == 2
    assert data["totals"]["unanswered_rate"] == 0.5
    assert data["logging"] == {"enabled": False}
    assert {g["id"] for g in data["topics"]} == {"fences", "animals"}

    data = staff_client.get("/api/staff/insights", params={"days": 60}).json()
    assert data["totals"]["questions"] == 3


def test_insights_params(staff_client):
    assert staff_client.get("/api/staff/insights", params={"days": 0}).status_code == 422
    assert staff_client.get("/api/staff/insights", params={"days": 400}).status_code == 422
    assert staff_client.get("/api/staff/insights", params={"end": "yesterday"}).status_code == 400
    r = staff_client.get("/api/staff/insights", params={"days": 2, "end": "2026-01-01"})
    assert r.json()["range"]["start"] == "2025-12-31"


def test_chat_log_feeds_insights(client, staff_client, monkeypatch):
    monkeypatch.setattr(config, "QUESTION_LOG", True)
    r = client.post(
        "/api/chat", json={"messages": [{"role": "user", "content": "Can I keep chickens at 12 Elm Street? Call 207-555-0100"}]}
    )
    events = parse_sse(r.text)
    assert events[0][0] == "meta"
    rows = asyncio.run(store.get_store().query("questions"))
    assert len(rows) == 1
    row = rows[0]
    assert row["mode"] == "public"
    assert isinstance(row["answer_chars"], int) and row["answer_chars"] > 0
    assert "12 Elm" not in row["question"] and "555" not in row["question"]
    data = staff_client.get("/api/staff/insights").json()
    assert data["totals"]["questions"] == 1
    assert data["logging"] == {"enabled": True}
    assert data["topics"][0]["id"] == "animals"
    assert data["top_sections"]


def test_staff_chat_not_logged(staff_client, monkeypatch):
    monkeypatch.setattr(config, "QUESTION_LOG", True)
    staff_client.post(
        "/api/chat", json={"mode": "staff", "messages": [{"role": "user", "content": "fence height"}]}, headers=CSRF
    )
    assert asyncio.run(store.get_store().query("questions")) == []


# ---------------------------------------------------------------- feedback


def test_feedback_roundtrip(client, staff_client):
    aid = "ab" * 16
    q(TODAY, aid, "fence?", cited=["§ 275-4.12"])
    assert client.post("/api/feedback", json={"answer_id": aid, "helpful": True}).json() == {"ok": True}
    assert client.post("/api/feedback", json={"answer_id": aid, "helpful": False}).status_code == 200
    rows = asyncio.run(store.get_store().query("feedback"))
    assert len(rows) == 1 and rows[0]["helpful"] is False  # the second vote replaced the first
    assert set(rows[0]) <= {"helpful", "ts", "_pk", "_rk", "_updated"}  # nothing about the voter
    fb = staff_client.get("/api/staff/insights").json()["feedback"]
    assert (fb["yes"], fb["no"]) == (0, 1)
    assert fb["not_helpful"][0]["question"] == "fence?"


def test_feedback_replaces_yesterdays_vote(client):
    aid = "cd" * 16
    put("feedback", (TODAY - dt.timedelta(days=1)).isoformat(), aid, {"helpful": True, "ts": "x"})
    client.post("/api/feedback", json={"answer_id": aid, "helpful": False})
    rows = asyncio.run(store.get_store().query("feedback"))
    assert [(r["_pk"], r["helpful"]) for r in rows] == [(TODAY.isoformat(), False)]


@pytest.mark.parametrize(
    "body",
    [
        {"answer_id": "xyz", "helpful": True},
        {"answer_id": "AB" * 16, "helpful": True},
        {"answer_id": "ab" * 16},
        {"answer_id": "ab" * 16, "helpful": "maybe"},
        {"answer_id": "ab" * 16, "helpful": True, "comment": "my address is 4 Elm St"},
    ],
)
def test_feedback_validation(client, body):
    assert client.post("/api/feedback", json=body).status_code == 422


def test_feedback_rate_limit(client, monkeypatch):
    monkeypatch.setattr(insights.feedback_limiter, "_limit", 3)
    codes = [client.post("/api/feedback", json={"answer_id": f"{i:032x}", "helpful": True}).status_code for i in range(5)]
    assert codes == [200, 200, 200, 429, 429]


# ---------------------------------------------------------------- reports


def _case(cid, tags, status="open", created="2026-02-01", updated="2026-03-01", address="1 Test Way"):
    put(
        "cases",
        "case",
        cid,
        {
            "id": cid,
            "address": address,
            "map_lot": "9-9",
            "owner": "Owner Name",
            "title": f"Case {cid}",
            "tags": tags,
            "status": status,
            "created_at": f"{created}T10:00:00.000+00:00",
            "updated_at": f"{updated}T10:00:00.000+00:00",
        },
    )


def _item(cid, rid, kind, created, **extra):
    put("caseitems", cid, rid, {"id": rid, "case_id": cid, "kind": kind, "created_at": f"{created}T10:00:00.000+00:00", **extra})


@pytest.fixture
def seeded():
    _case("2026-000001", ["shoreland", "complaint"])
    _item("2026-000001", "1", "draft", "2026-02-10", template="nov-1", draft_id="d1", title="NOV")
    _item("2026-000001", "2", "draft", "2026-03-10", template="80k-packet", draft_id="d2")
    _item("2026-000001", "3", "deadline", "2026-03-11", label="Appeal to ZBA", date="2026-04-10", trigger="")
    _item("2026-000001", "4", "note", "2026-03-12", text="site visit")
    _item("2026-000001", "5", "draft", "2023-01-01", template="nov-2", draft_id="d0")  # outside the period
    _case("2026-000002", ["shoreland"], created="2025-05-01", updated="2025-06-01")
    _item("2026-000002", "1", "draft", "2025-05-02", template="decision", draft_id="d3")
    _item("2026-000002", "2", "draft", "2025-05-03", template="zba-hearing", draft_id="d4")
    _case("2026-000003", ["shoreland"], status="closed", created="2020-01-01", updated="2021-01-01")  # closed before
    _case("2026-000004", ["zoning"])  # not shoreland
    _case("2026-000005", ["plumbing", "complaint"])
    _item("2026-000005", "1", "draft", "2026-02-02", template="stop-work", draft_id="d5")
    _case("2026-000006", ["subsurface"], status="closed", created="2026-01-05", updated="2026-02-05")
    _case("2026-000007", ["plumbing"], created="2027-01-05", updated="2027-01-05")  # after the year


def test_shoreland_report(staff_client, seeded):
    r = staff_client.get("/api/staff/reports/shoreland", params={"start": "2025-01-01", "end": "2026-12-31"})
    assert r.status_code == 200, r.text
    rep = r.json()
    assert [c["id"] for c in rep["cases"]] == ["2026-000002", "2026-000001"]
    assert "source of truth" in rep["note"]
    assert rep["citation"] == "Waterville City Code § 275-6.1B"
    rows = {s["label"]: s["count"] for s in rep["summary"]}
    assert rows["Applications submitted"] is None and rows["Fees collected"] is None
    assert rows["Permits granted or denied"] == 1
    assert rows["Variances granted or denied"] == 1
    assert rows["Appeals"] == 1
    assert rows["Court actions"] == 1
    assert rows["Violations investigated"] == 1
    assert rows["Violations found"] == 1
    first = rep["cases"][1]
    assert first["actions"] == ["NOV 1 (2026-02-10)", "80K packet (2026-03-10)"]
    assert first["notes"] == 1 and first["deadlines"] == 1
    assert "owner" not in first  # names stay in the notebook
    assert rep["status"] == {"open": 2, "monitoring": 0, "closed": 0}


def test_lpi_report(staff_client, seeded):
    rep = staff_client.get("/api/staff/reports/lpi", params={"year": 2026}).json()
    assert [c["id"] for c in rep["cases"]] == ["2026-000006", "2026-000005"]
    rows = {s["label"]: s["count"] for s in rep["summary"]}
    assert rows["Plumbing cases"] == 1
    assert rows["Subsurface wastewater cases"] == 1
    assert rows["Complaints investigated"] == 1
    assert rows["Work rejected or changes ordered"] == 1
    assert rows["Permits issued"] is None
    assert rep["start"] == "2026-01-01" and rep["end"] == "2026-12-31"
    assert "[VERIFY]" in rep["verify"]
    assert rep["status"]["closed"] == 1


def test_report_params(staff_client):
    assert staff_client.get("/api/staff/reports/shoreland", params={"start": "2026-05-01", "end": "2026-01-01"}).status_code == 400
    assert staff_client.get("/api/staff/reports/shoreland", params={"start": "2010-01-01", "end": "2026-01-01"}).status_code == 400
    assert staff_client.get("/api/staff/reports/shoreland", params={"start": "nope"}).status_code == 400
    assert staff_client.get("/api/staff/reports/lpi", params={"year": 1900}).status_code == 422
    listing = staff_client.get("/api/staff/reports").json()
    assert [r["id"] for r in listing["reports"]] == ["shoreland", "lpi"]
    empty = staff_client.get("/api/staff/reports/lpi").json()
    assert empty["cases"] == [] and empty["start"].endswith("-01-01")


def test_distinct_counts_repeats():
    rows = [{"date": "2026-10-0%d" % i, "question": q} for i, q in enumerate(["Mayor?", "mayor? ", "fence?", "MAYOR?"], 1)]
    out = insights._distinct(rows)
    assert out == [
        {"date": "2026-10-01", "question": "Mayor?", "times": 3},
        {"date": "2026-10-03", "question": "fence?", "times": 1},
    ]
    assert len(insights._distinct([{"question": str(i)} for i in range(20)], limit=5)) == 5

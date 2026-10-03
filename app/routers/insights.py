"""Staff insights (A7b), reports (B13), public feedback, and code change alerts.

    GET  /api/staff/insights?days=30&end=YYYY-MM-DD   question digest (staff)
    GET  /api/staff/reports                           report list (staff)
    GET  /api/staff/reports/shoreland?start=&end=     DEP biennial shoreland summary (staff)
    GET  /api/staff/reports/lpi?year=                 LPI annual summary (staff)
    POST /api/feedback  {"answer_id", "helpful"}      "Was this helpful?" (public, rate limited)
    GET  /api/staff/changes                           code change alerts (corpus agent, under "# changes")

Store tables read here:
  questions  pk = UTC date, rk = answer_id. Written by app/routers/chat.py when
             QUESTION_LOG=1: scrubbed question, cited numbers and citations,
             no_answer, failed, answer_chars, ts. Public questions only.
  feedback   pk = UTC date of the vote, rk = answer_id: {helpful, ts}. One vote
             per answer; a second vote replaces the first. Nothing about the
             voter is kept.
  cases, caseitems  case notebooks (app/routers/notebooks.py), for the reports.

Topics are found by keyword (TOPICS below), with no model call: each question
goes to the topic whose patterns match most often, and questions that match no
topic are grouped by their most common shared word.
"""

from __future__ import annotations

import asyncio
import datetime as dt
import os
import re
from collections import Counter
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

from .. import config, ratelimit
from ..auth import require_staff
from ..store import get_store

router = APIRouter(tags=["insights"])

QUESTIONS = "questions"
FEEDBACK = "feedback"
MAX_DAYS = 366

SOURCE_OF_TRUTH = (
    "The city's permit records are the source of truth. This summary counts only what staff saved in "
    "case notebooks, so use it as a cross-check and a list of files to pull, and take permit, fee and "
    "inspection figures from the permit records."
)


def _today() -> dt.date:
    return datetime.now(timezone.utc).date()


def _date(value: str | None, name: str) -> dt.date | None:
    if not value:
        return None
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        raise HTTPException(400, f"{name} must be a date like 2026-10-03.")


def _days(start: dt.date, end: dt.date) -> list[dt.date]:
    return [start + dt.timedelta(days=i) for i in range((end - start).days + 1)]


async def _by_days(table: str, days: list[dt.date]) -> list[dict]:
    """Every entity in a date-partitioned table for the given days."""
    store = get_store()
    parts = await asyncio.gather(*(store.query(table, pk=d.isoformat()) for d in days))
    return [e for part in parts for e in part]


# ================================================================ topics

# (id, label, patterns). Order breaks ties: a fence question that names a
# permit counts as a fence question.
TOPICS: list[tuple[str, str, str]] = [
    ("fences", "Fences and walls", r"fenc\w*|retaining wall|privacy wall|hedges?"),
    ("sheds", "Sheds, garages and accessory buildings", r"sheds?|garages?|carports?|accessory (?:building|structure)s?|outbuildings?|barns?|greenhouses?"),
    ("decks", "Decks, porches and pools", r"decks?|porch\w*|patios?|pools?|hot tubs?|gazebos?"),
    ("animals", "Chickens and animals", r"chickens?|hens?|roosters?|coops?|goats?|livestock|bees?|beekeep\w*|ducks?|horses?|pigs?|dogs?|kennels?|animals?"),
    ("str", "Short-term rentals", r"short[- ]term|airbnb|vrbo|str licen[sc]e|vacation rental"),
    ("rental", "Rentals and landlord-tenant", r"landlords?|tenants?|evict\w*|renters?|rental (?:registration|housing|unit|propert\w*)|lease|security deposit"),
    ("units", "Housing units, conversions and ADUs", r"duplex\w*|apartments?|adus?|accessory dwelling\w*|in-law|units?|multi-?family|convert\w*|conversion"),
    ("home-business", "Home businesses", r"home (?:business|occupation|office)|business from (?:my|our|a) home|daycare|day care|run a business"),
    ("signs", "Signs", r"signs?|signage|billboards?|banners?"),
    ("setbacks", "Setbacks, lot size and frontage", r"setbacks?|lot (?:size|line|width|coverage)|frontage|property line|boundar\w*|how close|how far"),
    ("zoning", "Zoning districts and allowed uses", r"zon(?:e|es|ed|ing)|district|allowed use|permitted use|special exception|variance|rezon\w*"),
    ("maintenance", "Property maintenance, junk and trash", r"junk\w*|trash|garbage|debris|rubbish|unregistered|abandoned|overgrown|grass|weeds?|rodents?|rats?|blight\w*|eyesore"),
    ("unsafe", "Unsafe or unsanitary conditions", r"unsafe|dangerous|hazard\w*|no heat|mold|sewage|collaps\w*|condemn\w*|smoke detectors?|carbon monoxide"),
    ("parking", "Parking and vehicles", r"park(?:ing|ed)?|driveways?|rvs?|campers?|boats?|trailers?|vehicles?"),
    ("shoreland", "Shoreland, flood and wetlands", r"shoreland|flood\w*|wetlands?|river|stream|messalonskee|kennebec|waterfront|shoreline"),
    ("septic", "Plumbing, septic and sewer", r"septic|plumb\w*|sewer|wastewater|subsurface|leach ?field"),
    ("energy", "Solar, heat pumps and energy", r"solar|heat pumps?|wind turbines?|generators?|ev charg\w*"),
    ("trees", "Trees and vegetation", r"trees?|clearing|vegetation|cut(?:ting)? down"),
    ("demolition", "Demolition", r"demoli\w*|tear(?:ing)? down|raze"),
    ("noise", "Noise and nuisance", r"nois\w*|loud|barking|nuisance"),
    ("fireworks", "Fireworks and burning", r"firework\w*|burn\w*|fire ?pits?|bonfires?|campfires?"),
    ("cannabis", "Cannabis", r"cannabis|marijuana|dispensar\w*"),
    ("snow", "Snow and sidewalks", r"snow|plow\w*|sidewalks?|ice"),
    ("fees", "Fees and costs", r"fees?|costs?|how much|price|charge"),
    ("permits", "Building permits in general", r"permits?|build\w*|construct\w*|addition|renovat\w*|remodel\w*|inspection\w*"),
]
_TOPIC_RE = [(tid, label, re.compile(r"\b(?:" + pat + r")\b", re.I)) for tid, label, pat in TOPICS]

_STOP = set(
    """a about above after again against all allowed also am an and any are as at be been before being below
    between both but by can could did do does doing down during each few for from further had has have having
    here how i if in into is it its just me more most my need needs no nor not of off on once only or other our
    out over own same should so some such than that the their them then there these they this those through to
    too under until up very was we were what when where which while who whom why will with would you your yes
    get got put make want wants like know tell help please thanks thank hi hello waterville maine city code
    rule rules regulation regulations ordinance ordinances allow does doesnt dont cant much many way there
    name email phone address parcel zip""".split()
)


def _words(text: str) -> list[str]:
    out = []
    for w in re.findall(r"[a-z][a-z'\-]+", (text or "").lower()):
        w = w.strip("'-")
        if w.endswith("'s"):
            w = w[:-2]
        if len(w) >= 4 and w not in _STOP:
            out.append(w[:-1] if w.endswith("s") and not w.endswith("ss") else w)
    return out


def topic_of(question: str) -> tuple[str, str] | None:
    """The best matching (id, label), or None when no topic pattern matches."""
    best, hits = None, 0
    for tid, label, rx in _TOPIC_RE:
        n = len(rx.findall(question or ""))
        if n > hits:
            best, hits = (tid, label), n
    return best


def cluster(questions: list[dict], limit: int = 12, examples: int = 3) -> list[dict]:
    """Group question records into topics: [{id, label, count, unanswered, examples}], largest first.

    `questions` are store records with `question`, `no_answer`, `failed` and `ts`.
    """
    groups: dict[str, dict] = {}
    leftovers: list[dict] = []

    def add(tid: str, label: str, q: dict) -> None:
        g = groups.setdefault(tid, {"id": tid, "label": label, "count": 0, "unanswered": 0, "_qs": []})
        g["count"] += 1
        g["unanswered"] += 1 if _unanswered(q) else 0
        g["_qs"].append(q)

    for q in questions:
        hit = topic_of(q.get("question", ""))
        if hit:
            add(hit[0], hit[1], q)
        else:
            leftovers.append(q)

    # Questions no topic matched: group by the word they share most widely.
    df = Counter(w for q in leftovers for w in set(_words(q.get("question", ""))))
    for q in leftovers:
        words = sorted(set(_words(q.get("question", ""))), key=lambda w: (-df[w], w))
        if words and df[words[0]] >= 2:
            add("word:" + words[0], f'Other: "{words[0]}"', q)
        else:
            add("other", "Other questions", q)

    out = []
    for g in groups.values():
        qs = sorted(g.pop("_qs"), key=lambda q: q.get("ts") or "", reverse=True)
        seen, ex = set(), []
        for q in qs:
            text = q.get("question", "")
            if text.lower() not in seen:
                seen.add(text.lower())
                ex.append(text)
            if len(ex) >= examples:
                break
        g["examples"] = ex
        out.append(g)
    # "Other questions" sinks to the bottom whatever its size.
    out.sort(key=lambda g: (g["id"] == "other", -g["count"], g["label"]))
    return out[:limit]


def _distinct(rows: list[dict], limit: int = 10) -> list[dict]:
    """Newest first, one row per question text (ignoring case), with `times` asked."""
    out: dict[str, dict] = {}
    for r in rows:
        key = r["question"].strip().lower()
        if key in out:
            out[key]["times"] += 1
        elif len(out) < limit:
            out[key] = {**r, "times": 1}
    return list(out.values())


def _unanswered(q: dict) -> bool:
    return bool(q.get("no_answer")) and not q.get("failed")


# ================================================================ insights


def summarize(questions: list[dict], votes: list[dict], days: list[dt.date]) -> dict:
    """The digest for a set of question records and feedback votes over `days`."""
    per_day = {d.isoformat(): {"date": d.isoformat(), "count": 0, "unanswered": 0, "failed": 0} for d in days}
    cited: Counter = Counter()
    for q in questions:
        day = per_day.get(q.get("_pk") or (q.get("ts") or "")[:10])
        if day:
            day["count"] += 1
            day["unanswered"] += 1 if _unanswered(q) else 0
            day["failed"] += 1 if q.get("failed") else 0
        for c in set(filter(None, q.get("cited_citations") or [])):
            cited[c] += 1

    total = len(questions)
    failed = sum(1 for q in questions if q.get("failed"))
    unanswered = [q for q in questions if _unanswered(q)]
    completed = total - failed
    by_id = {q.get("_rk"): q for q in questions}

    yes = sum(1 for v in votes if v.get("helpful") is True)
    no = sum(1 for v in votes if v.get("helpful") is False)
    not_helpful = _distinct(
        [
            {"date": (q.get("ts") or "")[:10], "question": q.get("question", ""), "cited": q.get("cited_citations") or []}
            for v in sorted(votes, key=lambda v: v.get("ts") or "", reverse=True)
            if v.get("helpful") is False and (q := by_id.get(v.get("_rk")))
        ]
    )

    answer_chars = [q["answer_chars"] for q in questions if isinstance(q.get("answer_chars"), int) and not q.get("failed")]
    return {
        "totals": {
            "questions": total,
            "answered": completed - len(unanswered),
            "unanswered": len(unanswered),
            "failed": failed,
            "unanswered_rate": round(len(unanswered) / completed, 4) if completed else None,
            "avg_answer_chars": round(sum(answer_chars) / len(answer_chars)) if answer_chars else None,
        },
        "volume": list(per_day.values()),
        "topics": cluster(questions),
        "top_sections": [{"citation": c, "count": n} for c, n in sorted(cited.items(), key=lambda x: (-x[1], x[0]))[:15]],
        "unanswered_examples": _distinct(
            [{"date": (q.get("ts") or q.get("_pk") or "")[:10], "question": q.get("question", "")}
             for q in sorted(unanswered, key=lambda q: q.get("ts") or "", reverse=True)]
        ),
        "feedback": {
            "yes": yes,
            "no": no,
            "total": yes + no,
            "helpful_rate": round(yes / (yes + no), 4) if yes + no else None,
            "not_helpful": not_helpful,
        },
    }


@router.get("/api/staff/insights")
async def insights(
    days: int = Query(30, ge=1, le=MAX_DAYS),
    end: str | None = Query(None, max_length=10),
    user: str = Depends(require_staff),
):
    last = _date(end, "end") or _today()
    span = _days(last - dt.timedelta(days=days - 1), last)
    questions, votes = await asyncio.gather(_by_days(QUESTIONS, span), _by_days(FEEDBACK, span))
    out = summarize(questions, votes, span)
    out["range"] = {"start": span[0].isoformat(), "end": span[-1].isoformat(), "days": days}
    out["logging"] = {"enabled": config.QUESTION_LOG}
    return out


# ================================================================ feedback


class FeedbackIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    answer_id: str = Field(pattern=r"^[a-f0-9]{32}$")
    helpful: bool


feedback_limiter = ratelimit.WindowLimiter(
    int(os.environ.get("FEEDBACK_RATE_LIMIT_PER_HOUR", "30")),
    3600,
    "Too many responses in a short time. Thank you, your earlier answers were saved.",
)


@router.post("/api/feedback")
async def feedback(body: FeedbackIn, request: Request):
    if msg := feedback_limiter.check(ratelimit.client_ip(request)):
        raise HTTPException(429, msg)
    store = get_store()
    now = datetime.now(timezone.utc)
    # One vote per answer: a changed mind replaces the earlier vote, even across midnight.
    yesterday = (now.date() - dt.timedelta(days=1)).isoformat()
    if await store.get(FEEDBACK, yesterday, body.answer_id):
        await store.delete(FEEDBACK, yesterday, body.answer_id)
    await store.put(
        FEEDBACK, now.date().isoformat(), body.answer_id, {"helpful": body.helpful, "ts": now.isoformat(timespec="seconds")}
    )
    return {"ok": True}


# ================================================================ reports

ENFORCEMENT_TEMPLATES = {"nov-1", "nov-2", "nov-3", "stop-work"}
COURT_TEMPLATES = {"80k-packet", "80k-memo"}
TEMPLATE_LABELS = {
    "nov-1": "NOV 1",
    "nov-2": "NOV 2",
    "nov-3": "Final NOV",
    "stop-work": "Stop-work order",
    "decision": "Permit decision",
    "zba-hearing": "ZBA hearing notice",
    "abutter-se": "Abutter notice",
    "abutter-se-decision": "Abutter decision letter",
    "80k-packet": "80K packet",
    "80k-memo": "80K memo",
}

REPORTS = {
    "shoreland": {
        "id": "shoreland",
        "title": "DEP biennial shoreland summary",
        "tags": ["shoreland"],
        "citation": "Waterville City Code § 275-6.1B",
        "quote": (
            "The Code Enforcement Officer shall keep a complete record of all essential transactions within "
            "the shoreland zone, including applications submitted, permits granted or denied, variances granted "
            "or denied, revocation actions, revocation of permits, appeals, court actions, violations "
            "investigated, violations found and fees collected. On a biennial basis, a summary of this record "
            "shall be submitted to the Director of the Bureau of Land and Water Quality within the Department "
            "of Environmental Protection."
        ),
        "recipient": "Director, Bureau of Land and Water Quality, Maine Department of Environmental Protection",
    },
    "lpi": {
        "id": "lpi",
        "title": "LPI annual report",
        "tags": ["plumbing", "subsurface"],
        "citation": "30-A M.R.S. § 4221(3)(D), (E)",
        "quote": (
            "Plumbing inspectors shall: ... D. Keep an accurate account of all fees collected and transfer those "
            "fees to the municipal treasurer; E. Keep a complete record of all essential transactions of the office;"
        ),
        "recipient": "Municipal officers",
        "verify": (
            "[VERIFY] The research notes list an annual LPI report to the municipal officers. The statute text "
            "read for this build requires the records but sets no report format; confirm the expected contents "
            "with the office and DHHS."
        ),
    },
}


def _iso_day(value: str | None) -> str:
    return (value or "")[:10]


def _in(day: str, start: dt.date, end: dt.date) -> bool:
    return bool(day) and start.isoformat() <= day <= end.isoformat()


def build_report(kind: str, cases: list[dict], items_by_case: dict[str, list[dict]], start: dt.date, end: dt.date) -> dict:
    """Report rows and summary for cases tagged for `kind`, over [start, end]."""
    spec = REPORTS[kind]
    tags = set(spec["tags"])
    s, e = start.isoformat(), end.isoformat()
    rows = []
    for c in cases:
        ctags = set(c.get("tags") or [])
        if not ctags & tags:
            continue
        opened, last = _iso_day(c.get("created_at")), _iso_day(c.get("updated_at"))
        # In the period: opened by its end, and still open or touched since its start.
        if not opened or opened > e or (c.get("status") == "closed" and last < s):
            continue
        items = [it for it in items_by_case.get(c.get("id", ""), []) if _in(_iso_day(it.get("created_at")), start, end)]
        drafts = [it for it in items if it.get("kind") == "draft"]
        templates = [it.get("template") or "" for it in drafts]
        deadlines = [it for it in items if it.get("kind") == "deadline"]
        actions = [
            f"{TEMPLATE_LABELS.get(it.get('template') or '', it.get('title') or 'Draft')} ({_iso_day(it.get('created_at'))})"
            for it in drafts
        ]
        rows.append(
            {
                "id": c.get("id"),
                "address": c.get("address", ""),
                "map_lot": c.get("map_lot", ""),
                "title": c.get("title", ""),
                "tags": [t for t in c.get("tags") or [] if t in tags or t == "complaint"],
                "status": c.get("status", "open"),
                "opened": opened,
                "last_activity": last,
                "opened_in_period": _in(opened, start, end),
                "notes": sum(1 for it in items if it.get("kind") == "note"),
                "research": sum(1 for it in items if it.get("kind") == "answer"),
                "deadlines": len(deadlines),
                "actions": actions,
                "complaint": "complaint" in ctags,
                "enforcement": any(t in ENFORCEMENT_TEMPLATES for t in templates),
                "court": any(t in COURT_TEMPLATES for t in templates),
                "decisions": sum(1 for t in templates if t == "decision"),
                "zba": sum(1 for t in templates if t == "zba-hearing"),
                "appeal_clocks": sum(
                    1 for d in deadlines if "appeal" in f"{d.get('label', '')} {d.get('trigger', '')}".lower()
                ),
            }
        )
    rows.sort(key=lambda r: (r["opened"], r["id"] or ""))

    def count(pred) -> int:
        return sum(1 for r in rows if pred(r))

    investigated = count(lambda r: r["complaint"] or r["enforcement"] or r["court"])
    found = count(lambda r: r["enforcement"])
    court = count(lambda r: r["court"])
    records = "Permit records"
    if kind == "shoreland":
        summary = [
            {"label": "Applications submitted", "count": None, "basis": "Not kept in case notebooks", "confirm": records},
            {"label": "Permits granted or denied", "count": sum(r["decisions"] for r in rows),
             "basis": "Permit decision letters drafted", "confirm": records},
            {"label": "Variances granted or denied", "count": sum(r["zba"] for r in rows),
             "basis": "ZBA hearing notices drafted", "confirm": "ZBA minutes and decisions"},
            {"label": "Revocation actions", "count": None, "basis": "Not kept in case notebooks", "confirm": records},
            {"label": "Appeals", "count": sum(r["appeal_clocks"] for r in rows),
             "basis": "Appeal deadlines tracked", "confirm": "ZBA and court records"},
            {"label": "Court actions", "count": court, "basis": "Cases with a Rule 80K packet or memo drafted",
             "confirm": "Court filings"},
            {"label": "Violations investigated", "count": investigated,
             "basis": "Cases tagged complaint or with an enforcement draft", "confirm": "Complaint log"},
            {"label": "Violations found", "count": found, "basis": "Cases with a notice of violation or stop-work order drafted",
             "confirm": "Issued notices"},
            {"label": "Fees collected", "count": None, "basis": "Not kept in case notebooks", "confirm": "Treasurer's receipts"},
        ]
    else:
        summary = [
            {"label": "Plumbing cases", "count": count(lambda r: "plumbing" in r["tags"]),
             "basis": "Cases tagged plumbing", "confirm": records},
            {"label": "Subsurface wastewater cases", "count": count(lambda r: "subsurface" in r["tags"]),
             "basis": "Cases tagged subsurface", "confirm": "HHE-200 applications"},
            {"label": "Permits issued", "count": None, "basis": "Not kept in case notebooks", "confirm": records},
            {"label": "Inspections made", "count": None, "basis": "Not kept in case notebooks", "confirm": "Inspection log"},
            {"label": "Certificates of approval", "count": None, "basis": "Not kept in case notebooks", "confirm": records},
            {"label": "Complaints investigated", "count": count(lambda r: r["complaint"]),
             "basis": "Cases tagged complaint", "confirm": "Complaint log"},
            {"label": "Work rejected or changes ordered", "count": found,
             "basis": "Cases with a notice of violation or stop-work order drafted", "confirm": "Issued notices"},
            {"label": "Court actions", "count": court, "basis": "Cases with a Rule 80K packet or memo drafted",
             "confirm": "Court filings"},
            {"label": "Fees collected and sent to the treasurer", "count": None, "basis": "Not kept in case notebooks",
             "confirm": "Treasurer's receipts"},
        ]
    status = Counter(r["status"] for r in rows)
    return {
        **{k: v for k, v in spec.items() if k != "tags"},
        "tags": spec["tags"],
        "start": s,
        "end": e,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "note": SOURCE_OF_TRUTH,
        "summary": summary,
        "status": {k: status.get(k, 0) for k in ("open", "monitoring", "closed")},
        "opened_in_period": count(lambda r: r["opened_in_period"]),
        "cases": rows,
    }


async def _report(kind: str, start: dt.date, end: dt.date) -> dict:
    if end < start:
        raise HTTPException(400, "The end date is before the start date.")
    if (end - start).days > 366 * 3:
        raise HTTPException(400, "Pick a period of three years or less.")
    store = get_store()
    cases = await store.query("cases", pk="case")
    tags = set(REPORTS[kind]["tags"])
    wanted = [c for c in cases if set(c.get("tags") or []) & tags]
    parts = await asyncio.gather(*(store.query("caseitems", pk=c["id"]) for c in wanted if c.get("id")))
    items = {c["id"]: p for c, p in zip([c for c in wanted if c.get("id")], parts)}
    return build_report(kind, wanted, items, start, end)


@router.get("/api/staff/reports")
async def reports(user: str = Depends(require_staff)):
    today = _today()
    return {
        "reports": [
            {"id": "shoreland", "title": REPORTS["shoreland"]["title"], "period": "biennial",
             "default": {"start": f"{today.year - 1}-01-01", "end": f"{today.year}-12-31"}},
            {"id": "lpi", "title": REPORTS["lpi"]["title"], "period": "annual", "default": {"year": today.year}},
        ],
        "note": SOURCE_OF_TRUTH,
    }


@router.get("/api/staff/reports/shoreland")
async def shoreland_report(
    start: str | None = Query(None, max_length=10),
    end: str | None = Query(None, max_length=10),
    user: str = Depends(require_staff),
):
    today = _today()
    s = _date(start, "start") or dt.date(today.year - 1, 1, 1)
    e = _date(end, "end") or dt.date(today.year, 12, 31)
    return await _report("shoreland", s, e)


@router.get("/api/staff/reports/lpi")
async def lpi_report(year: int | None = Query(None, ge=2000, le=2100), user: str = Depends(require_staff)):
    y = year or _today().year
    return await _report("lpi", dt.date(y, 1, 1), dt.date(y, 12, 31))


# changes
# GET /api/staff/changes goes below this line (corpus agent).

# Written by the refresh job before each index push (ecode/changes.py): one
# "run" row per push and one row per changed, added or removed city citation.
CHANGES = "changes"
CHANGE_KINDS = ("changed", "added", "removed")
MAX_RUNS = 20


def _natural_key(text: str | None) -> list:
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", text or "") if p]


def _change_summary(e: dict) -> str:
    new, old = e.get("legislation_through"), e.get("previous_legislation_through")
    if e.get("kind") == "changed":
        return f"Text changed between the editions of {old} and {new}." if new and old and new != old else "Text changed."
    if e.get("kind") == "added":
        return f"New in the edition of {new}." if new else "New in this refresh."
    return "Not found in the latest crawl."


def _change_view(e: dict) -> dict:
    out = {k: v for k, v in e.items() if not k.startswith("_")}
    out["run_id"] = e.get("_pk")
    out["detected_at"] = e.get("run_at")  # the name the insights page reads
    if e.get("kind") in CHANGE_KINDS:
        out["summary"] = _change_summary(e)
    return out


@router.get("/api/staff/changes")
async def code_changes(
    kind: str | None = Query(None, pattern="^(changed|added|removed)$"),
    since: str | None = None,
    limit: int = Query(200, ge=1, le=1000),
    user: str = Depends(require_staff),
):
    """Code change alerts, newest run first.

    Returns {runs, changes, total, last_run}. `runs` are the last refresh
    pushes ({run_id, run_at, index, baseline, counts, chunks}); a baseline run
    had no earlier hashes to compare with, so it reports nothing. Each change
    has kind (changed, added, removed), citation, title, source_type, url,
    chapter_number, chapter_title, section_title, history,
    legislation_through, previous_legislation_through, chunks, run_id, run_at.
    """
    start = _date(since, "since")
    runs, changes = [], []
    for e in await get_store().query(CHANGES):
        if start and (e.get("run_at") or "")[:10] < start.isoformat():
            continue
        if e.get("kind") == "run":
            runs.append(_change_view(e))
        elif e.get("kind") in CHANGE_KINDS and (kind is None or e["kind"] == kind):
            changes.append(_change_view(e))
    runs.sort(key=lambda r: r.get("run_at") or "", reverse=True)
    changes.sort(key=lambda c: (_natural_key(c.get("citation")), CHANGE_KINDS.index(c["kind"])))
    changes.sort(key=lambda c: c.get("run_at") or "", reverse=True)
    return {
        "runs": runs[:MAX_RUNS],
        "changes": changes[:limit],
        "total": len(changes),
        "last_run": runs[0] if runs else None,
    }

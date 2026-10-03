"""Public permit tools and staff project gates.

Public (A1, A2, A3, A4), data in app/data/checklists.toml:
  GET  /api/checklists              topic list, confirm line, office phone
  GET  /api/checklists/match?q=     the checklist or triage card a question matches
  GET  /api/checklists/{id}         one checklist card
  GET  /api/permit-router           projects and questions for /permits
  POST /api/permit-router           {project, answers} -> permits, forms, Fire review
  GET  /api/fees                    the published fee formulas
  POST /api/fees/estimate           {electrical?, life_safety?} -> estimates in cents

The chat router calls chat_cards() and sends the result as a `triage` or
`checklist` SSE event before `done` (public mode only).

Staff (B8), data in app/data/gates.toml: /api/staff/gates, at the end of
this file.

No answer here ever says a permit is not needed. Every card carries the
confirm line, and every fee figure is an estimate.
"""

from __future__ import annotations

import re
import tomllib
from decimal import ROUND_HALF_UP, Decimal
from functools import lru_cache
from pathlib import Path

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["checklists"])

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "checklists.toml"

FIRE_LABELS = {
    "yes": "The Fire Department's General Life Safety Review applies to this project type.",
    "likely": "The Fire Department's General Life Safety Review likely applies. Ask the office.",
    "maybe": "The Fire Department's General Life Safety Review may apply, for example to new construction or an addition. Ask the office.",
    "no": "The Fire Department's form does not list this project type. The Fire Department makes the final call.",
}

HISTORIC_URL = "https://ecode360.com/45005630"
SHORELAND_URL = "https://ecode360.com/38456897"


@lru_cache(maxsize=1)
def data() -> dict:
    with DATA_PATH.open("rb") as f:
        d = tomllib.load(f)
    for entry in d.get("checklist", []) + d.get("triage", []):
        entry["_re"] = [re.compile(p, re.IGNORECASE) for p in entry.get("patterns", [])]
    return d


def _checklist(cid: str) -> dict | None:
    return next((c for c in data()["checklist"] if c["id"] == cid), None)


def _project(pid: str) -> dict | None:
    return next((p for p in data()["project"] if p["id"] == pid), None)


def _form(fid: str) -> dict:
    f = data()["forms"][fid]
    return {"id": fid, "title": f["title"], "url": f["url"], "who": f["who"]}


def card(c: dict) -> dict:
    """The public JSON for one checklist."""
    d = data()
    bring_building = bool(c.get("bring_building"))
    bring = list(c.get("bring", []))
    if bring_building:
        bring += d["bring"]["building"]
    status = c.get("fire_review", "no")
    project = _project(c["id"])
    return {
        "id": c["id"],
        "title": c["title"],
        "summary": c.get("summary", ""),
        "sections": [{"citation": s["citation"], "url": s["url"], "says": s["says"]} for s in c.get("sections", [])],
        "forms": [_form(f) for f in c.get("forms", [])],
        "bring": bring,
        "building_permit": bring_building,
        "survey_note": d["bring"]["survey_note"] if bring_building else None,
        "inspections": d["bring"]["inspections"] if bring_building else None,
        "notes": list(c.get("notes", [])),
        "fire_review": {"status": status, "label": FIRE_LABELS[status], "form": _form("life_safety")},
        "permit_guide": f"/permits?project={project['id']}" if project else "/permits",
        "confirm_line": d["confirm_line"],
        "office_phone": d["office_phone"],
        "applications_page": d["applications_page"],
        "checked": d["checked"],
    }


def _triage_card(t: dict) -> dict:
    return {
        "id": t["id"],
        "kind": t["kind"],
        "title": t["title"],
        "lines": list(t["lines"]),
        "links": [dict(x) for x in t.get("links", [])],
        "office_phone": data()["office_phone"],
    }


def _score(entry: dict, text: str) -> int:
    return sum(1 for r in entry["_re"] if r.search(text))


def match_checklist(text: str) -> dict | None:
    """The checklist whose patterns best match the text. Ties go to the earlier entry."""
    best, best_score = None, 0
    for c in data()["checklist"]:
        s = _score(c, text)
        if s > best_score:
            best, best_score = c, s
    return best


def match_triage(text: str) -> dict | None:
    """The first triage entry that matches. Life safety is listed first, so it wins."""
    return next((t for t in data()["triage"] if _score(t, text)), None)


def chat_cards(question: str) -> list[tuple[str, dict]]:
    """SSE events to send after a public answer, before `done`.

    A triage match (life safety, or a matter the office does not handle)
    replaces the permit checklist: a resident with no heat needs a phone
    number, not a list of documents.
    """
    if t := match_triage(question):
        return [("triage", _triage_card(t))]
    if c := match_checklist(question):
        return [("checklist", card(c))]
    return []


# ------------------------------------------------------------------ checklists (A1, A2)


@router.get("/api/checklists")
async def list_checklists():
    d = data()
    return {
        "checklists": [{"id": c["id"], "title": c["title"], "summary": c.get("summary", "")} for c in d["checklist"]],
        "confirm_line": d["confirm_line"],
        "office": d["office"],
        "office_phone": d["office_phone"],
        "office_hours": d["office_hours"],
        "applications_page": d["applications_page"],
        "checked": d["checked"],
    }


@router.get("/api/checklists/match")
async def match(q: str = Query(min_length=1, max_length=1000)):
    t = match_triage(q)
    c = None if t else match_checklist(q)
    return {"checklist": card(c) if c else None, "triage": _triage_card(t) if t else None}


@router.get("/api/checklists/{cid}")
async def get_checklist(cid: str):
    c = _checklist(cid)
    if not c:
        raise HTTPException(404, "No checklist by that name.")
    return card(c)


# ------------------------------------------------------------------ permit router (A3)


class RouterRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    project: str = Field(max_length=40)
    answers: dict[str, bool] = Field(default_factory=dict, max_length=20)


@router.get("/api/permit-router")
async def router_options():
    d = data()
    return {
        "projects": [
            {"id": p["id"], "label": p["label"], "checklist": p.get("checklist"), "defaults": dict(p.get("defaults", {}))}
            for p in d["project"]
        ],
        "questions": [
            {"id": q["id"], "label": q["label"], "help": q.get("help", ""), "fire": bool(q.get("fire"))}
            for q in d["question"]
        ],
        "confirm_line": d["confirm_line"],
        "office_phone": d["office_phone"],
        "applications_page": d["applications_page"],
    }


def route(project_id: str, answers: dict[str, bool]) -> dict:
    """Which permits and forms a project needs, and whether the Fire review applies."""
    d = data()
    p = _project(project_id)
    if not p:
        raise HTTPException(400, "Unknown project type.")
    questions = {q["id"] for q in d["question"]}
    if unknown := sorted(set(answers) - questions):
        raise HTTPException(400, f"Unknown question: {unknown[0]}.")
    a = {**{k: bool(v) for k, v in p.get("defaults", {}).items()}, **answers}

    permits = [{**_form(f), "why": "The application for this project type."} for f in p.get("permits", [])]
    have = {x["id"] for x in permits}
    if a.get("electrical") and "electrical" not in have:
        permits.append(
            {
                **_form("electrical"),
                "why": "Electrical work at a one- or two-family home. Other buildings follow state electrical permitting (§ 127-10A).",
            }
        )
    if a.get("plumbing"):
        permits.append({**_form("plumbing"), "why": "Plumbing work is permitted by the Local Plumbing Inspector."})

    also = []
    if a.get("historic"):
        also.append(
            {
                "title": "Certificate of appropriateness",
                "who": "Historic Preservation Commission",
                "why": "Exterior changes visible from the street, new construction, demolition, and items such as signs, solar panels and heat pumps on a historic property may need one. When a building permit is also needed, the certificate comes first.",
                "citation": "§ 161-6; § 161-7A",
                "url": HISTORIC_URL,
            }
        )
    if a.get("shoreland"):
        also.append(
            {
                "title": "Shoreland zone review",
                "who": "Planning Board and Code Enforcement",
                "why": (
                    "In the shoreland zone no structure may be erected, expanded or moved, and no land filled or cleared, until the Planning Board approves the plans."
                    if a.get("new_construction")
                    else "The shoreland zoning rules apply to work within the zone. Ask the office what your project needs."
                ),
                "citation": "§ 275-4.27",
                "url": SHORELAND_URL,
            }
        )

    reasons = [q["label"] for q in d["question"] if q.get("fire") and a.get(q["id"])]
    checklist = _checklist(p["checklist"]) if p.get("checklist") else None
    if reasons:
        status = "required"
        text = "The Fire Department's General Life Safety Review applies. Its fee is 0.15% of the adjusted construction cost."
    elif checklist and checklist.get("fire_review") in ("yes", "likely", "maybe"):
        status = "ask"
        text = FIRE_LABELS[checklist["fire_review"]]
    else:
        status = "not_indicated"
        text = "None of the triggers on the Fire Department's form are selected. The Fire Department makes the final call."

    return {
        "project": {"id": p["id"], "label": p["label"]},
        "answers": a,
        "permits": permits,
        "also": also,
        "ask_office": p.get("ask_office"),
        "fire_review": {"status": status, "text": text, "reasons": reasons, "form": _form("life_safety")},
        "checklist": card(checklist) if checklist else None,
        "confirm_line": d["confirm_line"],
        "office_phone": d["office_phone"],
        "applications_page": d["applications_page"],
    }


@router.post("/api/permit-router")
async def permit_router(body: RouterRequest):
    return route(body.project, body.answers)


# ------------------------------------------------------------------ fees (A4)


class ElectricalInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    occupancy: str | None = Field(default=None, max_length=40)
    items: dict[str, int] = Field(default_factory=dict, max_length=40)


class LifeSafetyInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    construction_cost: float = Field(ge=0, le=1_000_000_000)


class FeeRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    electrical: ElectricalInput | None = None
    life_safety: LifeSafetyInput | None = None


@router.get("/api/fees")
async def fee_schedule():
    d = data()
    f = d["fees"]
    return {
        "building": {
            "published": False,
            "note": f["building_note"],
            "quote": f["building_quote"],
            "citation": f["building_citation"],
            "url": f["building_url"],
        },
        "after_the_fact": f["after_the_fact"],
        "life_safety": {k: f["life_safety"][k] for k in ("title", "rate", "source", "source_url", "formula", "excludes")},
        "electrical": {
            **{k: f["electrical"][k] for k in ("title", "source", "source_url", "scope", "minimum_note")},
            "minimum": [dict(m) for m in f["electrical"]["minimum"]],
            "items": [dict(i) for i in f["electrical"]["item"]],
        },
        "fixed": [dict(x) for x in f.get("fixed", [])],
        "office_phone": d["office_phone"],
        "checked": d["checked"],
    }


def _cents(x: Decimal) -> int:
    return int((x * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))


def estimate_fees(body: FeeRequest) -> dict:
    f = data()["fees"]
    out: dict = {"estimate": True}
    if body.life_safety is not None:
        rate = Decimal(f["life_safety"]["rate"])
        cost = Decimal(str(body.life_safety.construction_cost))
        out["life_safety"] = {
            "construction_cost_cents": _cents(cost),
            "rate": f["life_safety"]["rate"],
            "estimate_cents": _cents(cost * rate),
        }
    if body.electrical is not None:
        e = f["electrical"]
        items = {i["id"]: i for i in e["item"]}
        minimums = {m["id"]: m for m in e["minimum"]}
        occ = body.electrical.occupancy
        if occ and occ not in minimums:
            raise HTTPException(400, "Unknown occupancy.")
        lines = []
        for iid, qty in body.electrical.items.items():
            if iid not in items:
                raise HTTPException(400, f"Unknown fee item: {iid}.")
            if not 0 <= qty <= 10_000:
                raise HTTPException(400, "Quantities must be between 0 and 10,000.")
            if qty:
                it = items[iid]
                lines.append({"id": iid, "label": it["label"], "qty": qty, "unit_cents": it["cents"], "cents": it["cents"] * qty})
        order = list(items)
        lines.sort(key=lambda x: order.index(x["id"]))
        subtotal = sum(x["cents"] for x in lines)
        m = minimums.get(occ) if occ else None
        minimum = m["cents"] if m else 0
        out["electrical"] = {
            "lines": lines,
            "subtotal_cents": subtotal,
            "minimum": {"id": m["id"], "label": m["label"], "cents": m["cents"]} if m else None,
            "estimate_cents": max(subtotal, minimum),
            "basis": "minimum" if m and minimum > subtotal else "line_items",
        }
    return out


@router.post("/api/fees/estimate")
async def fees_estimate(body: FeeRequest):
    return estimate_fees(body)


# gates
# Project gate checklist (B8), owned by the deadlines-gates feature. The rules
# and their evaluator live in app/data/gates.toml and app/gates.py; these two
# staff routes are the only part kept in this shared file.

from fastapi import Depends as _gates_Depends  # noqa: E402

from .. import gates as _gates  # noqa: E402
from ..auth import require_staff as _gates_require_staff  # noqa: E402


@router.get("/api/staff/gates/options")
async def gates_options(user: str = _gates_Depends(_gates_require_staff)):
    """Vocabularies for the gate form: project types, uses, historic status, districts, phases."""
    return _gates.options()


@router.post("/api/staff/gates")
async def gates_check(body: _gates.GateInput, user: str = _gates_Depends(_gates_require_staff)):
    """The approvals a project needs, ordered by phase, each with its citation and quote."""
    return _gates.evaluate(body)

"""Project gate checklist (B8): which approvals a project needs, in order.

The rules live in app/data/gates.toml; this module parses their small
condition language, derives the helper fields and evaluates a project. The
route is POST /api/staff/gates in app/routers/checklists.py.

A condition is "field op value": op is one of == != > >= < <= in, and the
value is a number, true/false, a 'quoted string' or a ['list']. Nothing is
evaluated with eval().
"""

from __future__ import annotations

import ast
import operator
import re
import string
import tomllib
from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

DATA_PATH = Path(__file__).resolve().parent / "data" / "gates.toml"

PROJECT_TYPES = {
    "new_building": "New building",
    "addition": "Addition",
    "alteration": "Alteration or renovation",
    "change_of_use": "Change of use",
    "demolition": "Demolition",
    "site_work": "Site work only (paving, fill, grading)",
}
USES = {
    "one_two_family": "One- or two-family",
    "multifamily": "Multifamily (3 or more units)",
    "commercial": "Commercial",
    "industrial": "Industrial",
    "institutional": "Institutional",
    "mixed": "Mixed use",
}
HISTORIC = {
    "none": "Not historic",
    "contributing": "Contributing property in a historic district",
    "noncontributing": "Noncontributing property in a historic district",
    "landmark": "Historic landmark, site or individual property",
}
# § 275-2.3, plus "unknown" for a parcel not yet looked up.
DISTRICTS = {
    "unknown": "Not looked up",
    "R-A": "Low-Density Residential (R-A)",
    "R-B": "Medium-Density Residential (R-B)",
    "R-C": "General Residential (R-C)",
    "R-D": "General Residential (R-D)",
    "R-R": "Rural Residential (R-R)",
    "INST": "Institutional (INST)",
    "C-A": "Commercial (C-A)",
    "C-B": "General Commercial (C-B)",
    "C-C": "Heavy Commercial (C-C)",
    "C-C1": "Commercial (C-C1)",
    "C-D": "Highway Commercial (C-D)",
    "IND": "General Industrial (IND)",
    "I-P": "Industrial Park (I-P)",
    "A-I": "Airport Industrial (A-I)",
    "D-I": "Downtown Industrial (D-I)",
    "RP": "Resource Protection (RP)",
    "T": "Transitional (T)",
    "CZD": "Contract Zoned District (CZD)",
    "AIR": "Airport (AIR)",
    "SMU": "Suburban Mixed Use",
    "SF": "Solar Farm District",
}

MAX_AREA = 100_000_000  # sq ft; anything larger is a typo


class GateInput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_type: Literal["new_building", "addition", "alteration", "change_of_use", "demolition", "site_work"]
    use: Literal["one_two_family", "multifamily", "commercial", "industrial", "institutional", "mixed"]
    district: str = Field(default="unknown", max_length=8)
    units: int = Field(default=0, ge=0, le=10_000)
    footprint: int = Field(default=0, ge=0, le=MAX_AREA)
    impervious: int = Field(default=0, ge=0, le=MAX_AREA)
    construction_cost: int = Field(default=0, ge=0, le=10_000_000_000)
    historic: Literal["none", "contributing", "noncontributing", "landmark"] = "none"
    visible_from_street: bool = True
    shoreland: bool = False
    flood_zone: bool = False
    subdivision: bool = False
    use_requires_site_plan: bool = False
    needs_variance: bool = False
    private_road: bool = False
    plumbing: bool = False
    subsurface: bool = False
    electrical: bool = False
    demolition: bool = False
    renovation_over_75: bool = False
    life_safety_change: bool = False
    solar: bool = False
    sprinkler_alarm: bool = False
    sewer_water: bool = False
    street_work: bool = False
    new_driveway: bool = False
    state_road: bool = False
    near_protected_resource: bool = False

    @field_validator("district")
    @classmethod
    def _known_district(cls, v: str) -> str:
        if v not in DISTRICTS:
            raise ValueError("unknown zoning district")
        return v


# ---------------------------------------------------------------- conditions

_OPS = {
    "==": operator.eq,
    "!=": operator.ne,
    ">=": operator.ge,
    "<=": operator.le,
    ">": operator.gt,
    "<": operator.lt,
    "in": lambda a, b: a in b,
}
_COND_RE = re.compile(r"^\s*([a-z_][a-z0-9_]*)\s*(==|!=|>=|<=|>|<|in)\s*(.+?)\s*$")


class GateRuleError(ValueError):
    pass


def parse_condition(text: str) -> tuple[str, str, Any]:
    m = _COND_RE.match(text)
    if not m:
        raise GateRuleError(f"cannot read condition {text!r}")
    field, op, raw = m.groups()
    raw = {"true": "True", "false": "False"}.get(raw, raw)
    try:
        value = ast.literal_eval(raw)
    except (ValueError, SyntaxError):
        raise GateRuleError(f"bad value in condition {text!r}") from None
    if op == "in" and not isinstance(value, (list, tuple)):
        raise GateRuleError(f"'in' needs a list: {text!r}")
    return field, op, value


def derive(inp: GateInput) -> dict[str, Any]:
    f = inp.model_dump()
    construction = inp.project_type in ("new_building", "addition")
    demolishing = inp.project_type == "demolition" or inp.demolition
    f.update(
        footprint_plus_impervious=inp.footprint + inp.impervious,
        construction=construction,
        demolishing=demolishing,
        building_work=construction or demolishing or inp.project_type in ("alteration", "change_of_use"),
        nonresidential=inp.use != "one_two_family",
        historic_any=inp.historic != "none",
    )
    return f


FIELDS = set(GateInput.model_fields) | {
    "footprint_plus_impervious",
    "construction",
    "demolishing",
    "building_work",
    "nonresidential",
    "historic_any",
}


def holds(cond: tuple[str, str, Any], facts: dict[str, Any]) -> bool:
    field, op, value = cond
    return bool(_OPS[op](facts[field], value))


def fill(template: str, facts: dict[str, Any]) -> str:
    """Put facts into a reason; numbers get thousands separators."""
    out = []
    for literal, name, _spec, _conv in string.Formatter().parse(template):
        out.append(literal)
        if name is None:
            continue
        v = facts.get(name, "")
        out.append(f"{v:,}" if isinstance(v, int) and not isinstance(v, bool) else str(v))
    return "".join(out)


# ---------------------------------------------------------------- data


@lru_cache(maxsize=1)
def load_gates(path: Path = DATA_PATH) -> dict:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    phases = {p["n"] for p in data.get("phase", [])}
    ids = set()
    for g in data.get("gate", []):
        gid = g.get("id", "?")
        if gid in ids:
            raise GateRuleError(f"duplicate gate {gid}")
        ids.add(gid)
        for key in ("phase", "authority", "title", "citation", "url"):
            if key not in g:
                raise GateRuleError(f"{gid}: missing {key}")
        if g["phase"] not in phases:
            raise GateRuleError(f"{gid}: unknown phase {g['phase']}")
        if not isinstance(g.get("verified"), bool):
            raise GateRuleError(f"{gid}: verified must be true or false")
        if g.get("verified") and not g.get("quote"):
            raise GateRuleError(f"{gid}: a verified gate needs its quote")
        if not g.get("when"):
            raise GateRuleError(f"{gid}: no when")
        g["_when"] = []
        for w in g["when"]:
            conds = [parse_condition(c) for c in w["all"]]
            for c in conds:
                if c[0] not in FIELDS:
                    raise GateRuleError(f"{gid}: unknown field {c[0]}")
            g["_when"].append((conds, w["reason"]))
        g["_unless"] = [parse_condition(c) for c in g.get("unless", [])]
        for c in g["_unless"]:
            if c[0] not in FIELDS:
                raise GateRuleError(f"{gid}: unknown field {c[0]}")
    return data


def public_gate(g: dict) -> dict:
    keep = ("id", "phase", "authority", "title", "citation", "url", "source", "quote", "verified", "blocks", "note")
    out = {k: g[k] for k in keep if k in g}
    out["scope"] = g.get("scope", "city")
    return out


# ---------------------------------------------------------------- evaluate


def evaluate(inp: GateInput) -> dict:
    data = load_gates()
    facts = derive(inp)
    phases = {p["n"]: p for p in data["phase"]}
    gates, exempt = [], []
    for g in data["gate"]:
        reasons = [fill(reason, facts) for conds, reason in g["_when"] if all(holds(c, facts) for c in conds)]
        if not reasons:
            continue
        if g["_unless"] and all(holds(c, facts) for c in g["_unless"]):
            exempt.append({**public_gate(g), "reasons": reasons, "exempt_reason": g.get("exempt_reason", "")})
            continue
        gates.append({**public_gate(g), "reasons": reasons})
    gates.sort(key=lambda x: x["phase"])  # stable: TOML order within a phase
    for i, g in enumerate(gates, 1):
        g["order"] = i
        g["phase_label"] = phases[g["phase"]]["label"]
    notes = [n for n in data.get("district_note", []) if n["district"] == inp.district]
    assumptions = [
        "Shoreland, flood zone and historic status come from what you entered. The zoning map, shoreland map and flood insurance rate map are not in the corpus.",
        "Footprint means the new building's or addition's footprint; impervious means new impervious surface, both in square feet.",
    ]
    if inp.shoreland and inp.use == "one_two_family" and not inp.subdivision and inp.units <= 2:
        assumptions.append("Site plan review exemptions for one- and two-family homes do not reach the shoreland zone, where § 275-4.27C to G apply.")
    return {
        "input": inp.model_dump(),
        "phases": data["phase"],
        "gates": gates,
        "exempt": exempt,
        "district_notes": notes,
        "assumptions": assumptions,
        "unverified": sum(1 for g in gates if not g["verified"]),
        "checked": data.get("checked_default"),
    }


def options() -> dict:
    return {
        "project_types": [{"value": k, "label": v} for k, v in PROJECT_TYPES.items()],
        "uses": [{"value": k, "label": v} for k, v in USES.items()],
        "historic": [{"value": k, "label": v} for k, v in HISTORIC.items()],
        "districts": [{"value": k, "label": v} for k, v in DISTRICTS.items()],
        "phases": load_gates()["phase"],
    }

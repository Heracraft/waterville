"""Project gate checklist (B8): conditions, thresholds, ordering and the API."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import gates
from app.gates import (
    GateInput,
    GateRuleError,
    evaluate,
    fill,
    load_gates,
    parse_condition,
)

ROOT = Path(__file__).resolve().parent.parent
CSRF = {"X-Requested-With": "wv"}


def ids(**kw) -> list[str]:
    return [g["id"] for g in evaluate(GateInput(**kw))["gates"]]


def gate(gid: str, **kw) -> dict | None:
    return next((g for g in evaluate(GateInput(**kw))["gates"] if g["id"] == gid), None)


# ---------------------------------------------------------------- condition language


@pytest.mark.parametrize(
    "text,parsed",
    [
        ("footprint >= 4000", ("footprint", ">=", 4000)),
        ("use == 'one_two_family'", ("use", "==", "one_two_family")),
        ("shoreland == true", ("shoreland", "==", True)),
        ("subdivision == false", ("subdivision", "==", False)),
        ("historic in ['contributing', 'landmark']", ("historic", "in", ["contributing", "landmark"])),
    ],
)
def test_parse_condition(text, parsed):
    assert parse_condition(text) == parsed


@pytest.mark.parametrize("text", ["footprint >>= 1", "__import__('os') == 1", "x in 3", "footprint == open('x')", ""])
def test_parse_condition_rejects(text):
    with pytest.raises(GateRuleError):
        parse_condition(text)


def test_fill_formats_numbers():
    assert fill("{footprint} sq ft, ${construction_cost}", {"footprint": 12500, "construction_cost": 50000}) == "12,500 sq ft, $50,000"


def test_table_loads():
    data = load_gates()
    assert {p["n"] for p in data["phase"]} == set(range(1, 9))
    assert len(data["gate"]) >= 20


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("‑", "-")
    return re.sub(r"\s+", " ", s).strip()


@pytest.mark.parametrize("g", [g for g in load_gates()["gate"] if (g.get("source") or "").startswith("output/")], ids=lambda g: g["id"])
def test_city_gate_quotes_are_verbatim(g):
    path = ROOT / g["source"]
    if not path.exists():
        pytest.skip("crawl output not present")
    assert _norm(g["quote"]) in _norm(path.read_text(encoding="utf-8"))


def test_state_and_utility_gates_are_unverified():
    for g in load_gates()["gate"]:
        if g.get("scope") in ("state", "utility"):
            assert g["verified"] is False, g["id"]
            assert g["phase"] == 4, g["id"]


# ---------------------------------------------------------------- site plan thresholds (§ 275-6.4C)

BASE = dict(project_type="new_building", use="commercial", district="C-A")


@pytest.mark.parametrize(
    "kw,needed",
    [
        (dict(footprint=3999, impervious=0), False),
        (dict(footprint=4000, impervious=0), True),  # C(2): 4,000 or more
        (dict(footprint=3000, impervious=2000), False),  # exactly 5,000 is not "exceeds"
        (dict(footprint=3000, impervious=2001), True),  # C(1)
        (dict(footprint=0, impervious=7999, project_type="site_work"), False),
        (dict(footprint=0, impervious=8000, project_type="site_work"), True),  # C(4)
        (dict(footprint=1999, project_type="addition"), False),
        (dict(footprint=2000, project_type="addition"), True),  # C(3)
        (dict(footprint=3500, project_type="alteration"), False),
        (dict(project_type="change_of_use", use_requires_site_plan=True), True),  # C(6)
        (dict(project_type="alteration", use_requires_site_plan=True), True),  # C(5)
    ],
)
def test_site_plan_thresholds(kw, needed):
    assert ("pb-site-plan" in ids(**{**BASE, **kw})) is needed


def test_site_plan_reasons_cite_subsections():
    g = gate("pb-site-plan", **BASE, footprint=4500, impervious=3000)
    assert any("7,500" in r and "C(1)" in r for r in g["reasons"])
    assert any("4,500" in r and "C(2)" in r for r in g["reasons"])


def test_one_two_family_exempt_from_site_plan():
    r = evaluate(GateInput(project_type="new_building", use="one_two_family", units=2, footprint=6000))
    assert "pb-site-plan" not in [g["id"] for g in r["gates"]]
    (ex,) = r["exempt"]
    assert ex["id"] == "pb-site-plan" and "§ 275-6.4B" in ex["exempt_reason"]


def test_exemption_lost_in_subdivision_or_with_three_units():
    assert "pb-site-plan" in ids(project_type="new_building", use="one_two_family", footprint=6000, subdivision=True)
    assert "pb-site-plan" in ids(project_type="new_building", use="one_two_family", footprint=6000, units=3)


def test_site_plan_blocks_building_permit():
    g = gate("pb-site-plan", **BASE, footprint=5000)
    assert "§ 244-2.2B" in g["citation"] and "No building permit" in g["blocks"]


# ---------------------------------------------------------------- other city gates


def test_shoreland_planning_board():
    assert "pb-shoreland" in ids(project_type="addition", use="one_two_family", shoreland=True)
    assert "pb-shoreland" in ids(project_type="site_work", use="one_two_family", shoreland=True)
    assert "pb-shoreland" not in ids(project_type="alteration", use="one_two_family", shoreland=True)
    r = evaluate(GateInput(project_type="new_building", use="one_two_family", shoreland=True))
    assert any("shoreland zone" in a for a in r["assumptions"])


@pytest.mark.parametrize(
    "kw,needed",
    [
        (dict(historic="contributing", project_type="alteration"), True),
        (dict(historic="contributing", project_type="alteration", visible_from_street=False), False),
        (dict(historic="landmark", project_type="demolition"), True),
        (dict(historic="noncontributing", project_type="demolition"), False),
        (dict(historic="noncontributing", project_type="new_building"), True),
        (dict(historic="none", project_type="new_building"), False),
        (dict(historic="contributing", project_type="site_work", solar=True), True),
        (dict(historic="contributing", project_type="site_work", solar=True, visible_from_street=False), False),
    ],
)
def test_certificate_of_appropriateness(kw, needed):
    assert ("coa" in ids(use="one_two_family", **kw)) is needed


def test_coa_must_precede_building_permit():
    order = ids(use="one_two_family", project_type="alteration", historic="contributing")
    assert order.index("coa") < order.index("building-permit")
    assert "§ 161-7" in gate("coa", use="one_two_family", project_type="alteration", historic="contributing")["citation"]


@pytest.mark.parametrize(
    "kw,needed",
    [
        (dict(project_type="new_building"), True),
        (dict(project_type="addition"), True),
        (dict(project_type="alteration"), False),
        (dict(project_type="alteration", renovation_over_75=True), True),
        (dict(project_type="alteration", life_safety_change=True), True),
        (dict(project_type="change_of_use"), True),
        (dict(project_type="alteration", solar=True), True),
    ],
)
def test_fire_life_safety_review(kw, needed):
    assert ("fire-lsr" in ids(use="commercial", **kw)) is needed


def test_plumbing_and_subsurface_and_electrical():
    assert "plumbing" in ids(project_type="alteration", use="one_two_family", plumbing=True)
    g = gate("plumbing", project_type="alteration", use="one_two_family", plumbing=True, shoreland=True)
    assert any("§ 275-4.27H(12)(b)" in r for r in g["reasons"])
    assert "subsurface" in ids(project_type="site_work", use="one_two_family", subsurface=True)
    assert "electrical" in ids(project_type="alteration", use="one_two_family", electrical=True)
    assert "electrical-state" in ids(project_type="alteration", use="commercial", electrical=True)
    assert "electrical" not in ids(project_type="alteration", use="commercial", electrical=True)


def test_floodplain_permit_and_certificate():
    got = ids(project_type="new_building", use="one_two_family", flood_zone=True)
    assert got.index("floodplain") < got.index("building-permit") < got.index("floodplain-coc")


def test_private_road_variance_subdivision():
    got = ids(project_type="new_building", use="one_two_family", private_road=True, needs_variance=True, subdivision=True)
    assert {"pb-private-road", "zba-variance", "pb-subdivision"} <= set(got)


def test_demolition():
    got = ids(project_type="demolition", use="commercial", historic="contributing")
    assert {"coa", "dep-asbestos", "building-permit"} <= set(got)
    assert "inspections-co" not in got
    assert "dep-asbestos" in ids(project_type="alteration", use="commercial", demolition=True)


# ---------------------------------------------------------------- state gates


def test_state_gates_unverified_for_waterville():
    r = evaluate(GateInput(project_type="new_building", use="commercial", construction_cost=60000, state_road=True, near_protected_resource=True, sewer_water=True))
    state = [g for g in r["gates"] if g["scope"] in ("state", "utility")]
    assert {g["id"] for g in state} == {"state-fire-marshal", "barrier-free", "mainedot-entrance", "dep-nrpa", "utility-sewer-water"}
    assert all(g["verified"] is False for g in state)
    assert r["unverified"] == len(state)


def test_barrier_free_threshold():
    assert "barrier-free" not in ids(project_type="alteration", use="commercial", construction_cost=49999)
    assert "barrier-free" in ids(project_type="alteration", use="commercial", construction_cost=50000)
    assert "barrier-free" not in ids(project_type="alteration", use="one_two_family", construction_cost=500000)


# ---------------------------------------------------------------- ordering and notes


def test_order_follows_phases():
    r = evaluate(GateInput(project_type="new_building", use="commercial", district="C-A", footprint=5000, historic="contributing", shoreland=True, flood_zone=True, plumbing=True, electrical=True, sprinkler_alarm=True, sewer_water=True))
    phases = [g["phase"] for g in r["gates"]]
    assert phases == sorted(phases)
    assert [g["order"] for g in r["gates"]] == list(range(1, len(r["gates"]) + 1))
    assert r["gates"][-1]["phase"] == 8
    assert all(g["phase_label"] for g in r["gates"])


def test_district_notes():
    assert evaluate(GateInput(project_type="new_building", use="one_two_family", district="RP"))["district_notes"]
    assert evaluate(GateInput(project_type="new_building", use="one_two_family"))["district_notes"][0]["district"] == "unknown"
    assert evaluate(GateInput(project_type="new_building", use="one_two_family", district="R-C"))["district_notes"] == []


def test_input_validation():
    with pytest.raises(ValueError):
        GateInput(project_type="castle", use="commercial")
    with pytest.raises(ValueError):
        GateInput(project_type="new_building", use="commercial", district="Z-9")
    with pytest.raises(ValueError):
        GateInput(project_type="new_building", use="commercial", footprint=-1)
    with pytest.raises(ValueError):
        GateInput(project_type="new_building", use="commercial", surprise=True)


# ---------------------------------------------------------------- API


def test_gates_need_staff(client):
    assert client.post("/api/staff/gates", json={"project_type": "new_building", "use": "commercial"}, headers=CSRF).status_code == 401
    assert client.get("/api/staff/gates/options").status_code == 401


def test_gates_need_csrf_header(staff_client):
    r = staff_client.post("/api/staff/gates", json={"project_type": "new_building", "use": "commercial"})
    assert r.status_code == 403


def test_gates_api(staff_client):
    r = staff_client.post("/api/staff/gates", json={"project_type": "new_building", "use": "commercial", "footprint": 4200, "district": "C-B"}, headers=CSRF)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["gates"][0]["id"] == "pb-site-plan"
    for key in ("order", "phase", "phase_label", "authority", "title", "citation", "url", "verified", "reasons", "scope"):
        assert key in body["gates"][0]


def test_gates_api_rejects_bad_input(staff_client):
    r = staff_client.post("/api/staff/gates", json={"project_type": "new_building", "use": "commercial", "district": "nope"}, headers=CSRF)
    assert r.status_code == 422


def test_gates_options(staff_client):
    r = staff_client.get("/api/staff/gates/options")
    assert r.status_code == 200
    body = r.json()
    assert {d["value"] for d in body["districts"]} >= {"R-A", "C-A", "RP", "unknown"}
    assert len(body["phases"]) == 8
    assert {"project_types", "uses", "historic"} <= set(body)
    assert gates.DISTRICTS.keys() == {d["value"] for d in body["districts"]}

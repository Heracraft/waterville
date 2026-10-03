"""Deadline calculator (B7): calendars, date math, the rule table and the API."""

from __future__ import annotations

import re
from datetime import date, datetime, time, timedelta
from pathlib import Path

import pytest

from app.routers import deadlines as dl
from app.routers.deadlines import (
    RuleTableError,
    add_calendar_days,
    add_hours,
    add_months,
    add_rule6a,
    add_working_days,
    before_days,
    city_closed,
    compute,
    court_closed,
    legal_holidays,
    load_table,
    next_annual,
    validate_table,
)

ROOT = Path(__file__).resolve().parent.parent
D = date.fromisoformat


# ---------------------------------------------------------------- holidays


def test_2026_holidays_match_4_mrs_1051():
    h = {d.isoformat(): n for d, n in legal_holidays(2026).items()}
    assert h == {
        "2026-01-01": "New Year's Day",
        "2026-01-19": "Martin Luther King, Jr., Day",
        "2026-02-16": "Washington's Birthday (Presidents' Day)",
        "2026-04-20": "Patriot's Day",
        "2026-05-25": "Memorial Day",
        "2026-06-19": "Juneteenth",
        "2026-07-04": "Independence Day",
        "2026-09-07": "Labor Day",
        "2026-10-12": "Indigenous Peoples Day",
        "2026-11-11": "Veterans Day",
        "2026-11-26": "Thanksgiving Day",
        "2026-12-25": "Christmas Day",
    }


@pytest.mark.parametrize(
    "day,observed",
    [
        ("2027-07-04", "2027-07-05"),  # Independence Day on a Sunday
        ("2029-11-11", "2029-11-12"),  # Veterans Day on a Sunday
        ("2033-06-19", "2033-06-20"),  # Juneteenth on a Sunday
        ("2028-12-25", None),  # Monday: no extra day
        ("2033-01-01", None),  # Saturday: not moved (4 M.R.S. § 1051 moves Sundays only)
    ],
)
def test_sunday_holidays_observed_monday(day, observed):
    hol = legal_holidays(D(day).year)
    assert D(day) in hol
    nxt = D(day) + timedelta(days=1)
    if observed:
        assert nxt == D(observed) and hol[nxt].endswith("(observed)")
    else:
        assert nxt not in hol


@pytest.mark.parametrize(
    "year,mlk,memorial,labor,indig,thanks",
    [
        (2025, "2025-01-20", "2025-05-26", "2025-09-01", "2025-10-13", "2025-11-27"),
        (2027, "2027-01-18", "2027-05-31", "2027-09-06", "2027-10-11", "2027-11-25"),
        (2028, "2028-01-17", "2028-05-29", "2028-09-04", "2028-10-09", "2028-11-23"),
        (2030, "2030-01-21", "2030-05-27", "2030-09-02", "2030-10-14", "2030-11-28"),
    ],
)
def test_floating_holidays(year, mlk, memorial, labor, indig, thanks):
    h = legal_holidays(year)
    for d, name in [(mlk, "Martin"), (memorial, "Memorial"), (labor, "Labor"), (indig, "Indigenous"), (thanks, "Thanksgiving")]:
        assert h[D(d)].startswith(name)


def test_court_and_city_calendars():
    assert court_closed(D("2026-10-03")) == "Saturday"
    assert court_closed(D("2026-10-04")) == "Sunday"
    assert court_closed(D("2026-10-12")) == "Indigenous Peoples Day"
    assert court_closed(D("2026-10-09")) is None  # Friday: courts open
    assert city_closed(D("2026-10-09")) == "Friday, City Hall closed"
    assert city_closed(D("2026-10-12")) == "Indigenous Peoples Day"
    assert city_closed(D("2026-12-25")) == "Christmas Day"  # a Friday holiday names the holiday
    for d in ("2026-10-05", "2026-10-06", "2026-10-07", "2026-10-08"):
        assert city_closed(D(d)) is None


# ---------------------------------------------------------------- Rule 6(a)


def test_rule6a_plain():
    c = add_rule6a(D("2026-10-03"), 45)  # Saturday + 45 = Tuesday Nov 17
    assert c.end == D("2026-11-17") and c.raw is None


def test_rule6a_last_day_saturday_rolls_to_monday():
    c = add_rule6a(D("2026-09-02"), 45)  # Oct 17, 2026 is a Saturday
    assert c.raw == D("2026-10-17") and c.end == D("2026-10-19")


def test_rule6a_weekend_then_holiday():
    # Day 30 lands Sat Oct 10, 2026; Sunday, then Indigenous Peoples Day Monday.
    c = add_rule6a(D("2026-09-10"), 30)
    assert c.raw == D("2026-10-10") and c.end == D("2026-10-13")
    assert any("legal holiday" in s for s in c.steps)


def test_rule6a_holiday_on_weekday():
    c = add_rule6a(D("2026-10-27"), 15)  # Nov 11, 2026, Veterans Day (Wednesday)
    assert c.end == D("2026-11-12")


def test_rule6a_observed_monday_holiday():
    c = add_rule6a(D("2027-06-20"), 15)  # Jul 5, 2027: Independence Day observed
    assert c.raw == D("2027-07-05") and c.end == D("2027-07-06")


def test_rule6a_new_year_crossing():
    c = add_rule6a(D("2026-12-02"), 30)  # Jan 1, 2027: Friday holiday -> Monday Jan 4
    assert c.end == D("2027-01-04")


def test_rule6a_short_period_skips_intermediate_closed_days():
    # 5 days from Thursday Oct 8, 2026: skip Sat, Sun, Mon holiday.
    c = add_rule6a(D("2026-10-08"), 5)
    assert c.end == D("2026-10-16")
    assert add_rule6a(D("2026-10-08"), 6).end == D("2026-10-19")
    # 7 days is not "less than 7": plain count, then roll.
    assert add_rule6a(D("2026-10-08"), 7).end == D("2026-10-15")


def test_rule6a_long_period_does_not_skip_intermediate_days():
    assert add_rule6a(D("2026-10-01"), 10).end == D("2026-10-13")  # Sun Oct 11 -> Mon holiday -> Tue


# ---------------------------------------------------------------- calendar days and months


def test_calendar_days_do_not_roll():
    c = add_calendar_days(D("2026-10-03"), 7)
    assert c.end == D("2026-10-10")  # a Saturday; the date stands


def test_calendar_days_leap_year():
    assert add_calendar_days(D("2028-02-01"), 30).end == D("2028-03-02")
    assert add_calendar_days(D("2027-02-01"), 30).end == D("2027-03-03")
    assert add_calendar_days(D("2027-12-15"), 90).end == D("2028-03-14")


@pytest.mark.parametrize(
    "start,n,end",
    [
        ("2026-01-31", 1, "2026-02-28"),
        ("2028-01-31", 1, "2028-02-29"),
        ("2026-08-31", 6, "2027-02-28"),
        ("2027-08-31", 6, "2028-02-29"),
        ("2028-02-29", 12, "2029-02-28"),
        ("2028-02-29", 48, "2032-02-29"),
        ("2026-10-31", 6, "2027-04-30"),
        ("2026-12-15", 1, "2027-01-15"),
        ("2026-03-31", 24, "2028-03-31"),
        ("2026-05-31", 1, "2026-06-30"),
        ("2026-10-03", 6, "2027-04-03"),
    ],
)
def test_calendar_months(start, n, end):
    assert add_months(D(start), n).end == D(end)


def test_month_clamp_is_explained():
    steps = add_months(D("2026-01-31"), 1).steps
    assert any("no day 31" in s for s in steps)


# ---------------------------------------------------------------- working days


def test_city_working_days_skip_fridays_and_holidays():
    # Thu Nov 5, 2026: Veterans Day (Wed) and Fridays skipped; Thanksgiving after day 10.
    c = add_working_days(D("2026-11-05"), 10)
    assert c.end == D("2026-11-25")


def test_city_working_days_from_a_friday():
    assert add_working_days(D("2026-10-09"), 1).end == D("2026-10-13")  # Mon is a holiday
    assert add_working_days(D("2026-10-09"), 4).end == D("2026-10-19")


def test_city_working_days_over_christmas_and_new_year():
    # Wed Dec 23, 2026 + 5: Thu 24, (Fri 25 Christmas, weekend) Mon 28, Tue 29, Wed 30, Thu 31.
    assert add_working_days(D("2026-12-23"), 5).end == D("2026-12-31")
    assert add_working_days(D("2026-12-23"), 6).end == D("2027-01-04")


def test_weekday_count_alternative_is_earlier():
    c = add_working_days(D("2026-11-05"), 10, dl.weekday_closed)
    assert c.end == D("2026-11-20")


def test_working_days_end_on_open_days():
    start = D("2025-01-01")
    for i in range(0, 800, 3):
        for n in (1, 5, 10):
            e = add_working_days(start + timedelta(days=i), n).end
            assert city_closed(e) is None


def test_working_days_rejects_zero():
    with pytest.raises(ValueError):
        add_working_days(D("2026-10-05"), 0)


# ---------------------------------------------------------------- before, annual, hours


def test_before_days_open_day():
    c = before_days(D("2026-11-19"), 14)  # Thu -> Thu Nov 5
    assert c.end == D("2026-11-05") and c.raw is None


def test_before_days_moves_back_from_closed_day():
    c = before_days(D("2026-11-20"), 14)  # Nov 6 is a Friday -> Thu Nov 5
    assert c.raw == D("2026-11-06") and c.end == D("2026-11-05")
    c = before_days(D("2026-10-26"), 14)  # Oct 12 holiday Monday -> Thu Oct 8
    assert c.end == D("2026-10-08")


@pytest.mark.parametrize(
    "start,end",
    [("2026-10-03", "2026-10-31"), ("2026-10-31", "2026-10-31"), ("2026-11-01", "2027-10-31"), ("2026-01-01", "2026-10-31")],
)
def test_next_annual(start, end):
    assert next_annual(D(start), 10, 31).end == D(end)


def test_hours_cross_midnight_and_weekend():
    assert add_hours(datetime(2026, 10, 2, 16, 0), 72) == datetime(2026, 10, 5, 16, 0)
    assert add_hours(datetime(2026, 10, 2, 23, 30), 24) == datetime(2026, 10, 3, 23, 30)
    assert add_hours(datetime(2026, 10, 5, 9, 0), -24) == datetime(2026, 10, 4, 9, 0)


@pytest.mark.skipif(dl.LOCAL_TZ is None, reason="no tz database")
def test_hours_across_daylight_saving():
    # 72 elapsed hours over the fall-back night read an hour earlier on the clock.
    assert add_hours(datetime(2026, 10, 31, 12, 0), 72) == datetime(2026, 11, 3, 11, 0)
    assert add_hours(datetime(2026, 3, 7, 12, 0), 72) == datetime(2026, 3, 10, 13, 0)


# ---------------------------------------------------------------- the rule table


def test_table_loads_and_validates():
    data = load_table()
    assert len(data["rule"]) >= 50
    triggers = {t["id"] for t in data["trigger"]}
    for r in data["rule"]:
        assert set(r["triggers"]) <= triggers


def _norm(s: str) -> str:
    s = s.replace("’", "'").replace("“", '"').replace("”", '"').replace("‑", "-")
    return re.sub(r"\s+", " ", s).strip()


def _local_quotes():
    data = load_table()
    for r in data["rule"]:
        yield r["id"], r.get("source"), r["quote"]
        for a in r.get("also", []):
            yield f"{r['id']} also", a.get("source"), a["quote"]
    for cid, c in {**data["conventions"], **data["calendar"]}.items():
        if c.get("quote"):
            yield cid, c.get("source"), c["quote"]


@pytest.mark.parametrize("rid,source,quote", [q for q in _local_quotes() if (q[1] or "").startswith("output/")])
def test_city_code_quotes_are_verbatim(rid, source, quote):
    path = ROOT / source
    if not path.exists():
        pytest.skip("crawl output not present")
    assert _norm(quote) in _norm(path.read_text(encoding="utf-8")), rid


def test_every_rule_names_a_source_and_status():
    for r in load_table()["rule"]:
        assert r["url"].startswith("https://"), r["id"]
        assert (r.get("source") or "").startswith(("output/markdown/", "https://")), r["id"]
        assert isinstance(r["verified"], bool)
        assert "\u2014" not in r["label"] + r["quote"] + r.get("note", "") + r.get("caution", ""), r["id"]


def test_unverified_rules_explain_why():
    for r in load_table()["rule"]:
        if not r["verified"] or r.get("applies") == "check":
            assert r.get("caution"), r["id"]


def test_requested_clocks_are_present():
    rules = {r["id"]: r for r in load_table()["rule"]}
    expect = {
        "zba-hearing-45": (45, "days"),
        "zba-mailing-14": (14, "days"),
        "zba-admin-appeal-30": (30, "days"),
        "fp-ec-72h": (72, "hours"),
        "fp-coc-10wd": (10, "working_days"),
        "sl-expansion-record-90": (90, "days"),
        "casualty-secure-24h": (24, "hours"),
        "casualty-permit-90": (90, "days"),
        "casualty-work-120": (120, "days"),
        "bp-void-6mo": (6, "months"),
        "zba-commence-6mo": (6, "months"),
        "atf-fee-30": (30, "days"),
        "bp-refusal-30": (30, "days"),
        "zba-80b-45": (45, "days"),
        "hhe-reject-14": (14, "days"),
        "hhe-issue-20": (20, "days"),
        "sl-model-decision-35": (35, "days"),
        "80k-appeal-21": (21, "days"),
        "80e-execute-10": (10, "days"),
    }
    for rid, (n, unit) in expect.items():
        assert (rules[rid]["amount"], rules[rid]["unit"]) == (n, unit), rid
    assert rules["rental-expire-oct31"]["unit"] == "annual"
    assert "§ 275-4.27K(3)" in rules["sl-expansion-record-90"]["citation"]
    assert "§ 205-6" in rules["casualty-work-120"]["citation"]
    assert "§ 127-3B" in rules["atf-fee-30"]["citation"]
    assert rules["bp-refusal-30"]["applies"] == "check"
    # 30-A M.R.S. § 4482-A(1): 30 days from the vote on the final decision (finality under § 4482-B).
    assert rules["pb-site-plan-appeal"]["verified"] is True
    assert rules["pb-site-plan-appeal"]["applies"] == "check"
    assert "4482-A" in rules["pb-site-plan-appeal"]["citation"]
    assert rules["zba-reconsider-request-10"]["actor"] == "Any party"
    assert rules["pb-reconsider-petition-10wd"]["unit"] == "working_days"


@pytest.mark.parametrize(
    "mutate,msg",
    [
        (lambda d: d["rule"][0].update(convention="nope"), "unknown convention"),
        (lambda d: d["rule"][0].update(unit="weeks"), "bad unit"),
        (lambda d: d["rule"][0].update(triggers=["nope"]), "unknown trigger"),
        (lambda d: d["rule"][0].pop("quote"), "missing quote"),
        (lambda d: d["rule"][0].update(verified="yes"), "verified"),
        (lambda d: d["rule"][0].update(amount=0), "positive"),
        (lambda d: d["rule"].append(dict(d["rule"][0])), "duplicate"),
        (lambda d: d["rule"][0].update(unit="hours"), "does not fit"),
    ],
)
def test_validate_table_rejects_bad_rules(mutate, msg):
    import copy
    import tomllib

    data = tomllib.loads((ROOT / "app/data/deadlines.toml").read_text())
    bad = copy.deepcopy(data)
    mutate(bad)
    with pytest.raises((RuleTableError, KeyError)) as e:
        validate_table(bad)
    assert msg.split()[0] in str(e.value)


# ---------------------------------------------------------------- compute


def test_compute_zba_grant():
    r = compute("zba-grant", D("2026-10-03"))
    by = {x["id"]: x for x in r["results"]}
    assert by["zba-80b-45"]["date"] == "2026-11-17"
    assert by["zba-written-decision-7"]["date"] == "2026-10-10"
    assert by["zba-written-decision-7"]["closed"] == "Saturday"
    assert by["zba-written-decision-7"]["plan_by"] == "2026-10-08"
    assert by["zba-variance-record-90"]["date"] == "2027-01-01"
    assert by["zba-variance-record-90"]["plan_by"] == "2026-12-31"
    assert by["zba-commence-6mo"]["date"] == "2027-04-03"
    assert by["zba-complete-1yr"]["date"] == "2027-10-03"
    dates = [x["date"] for x in r["results"]]
    assert dates == sorted(dates)
    assert "zba-reapply-bar-1yr" not in by  # a denial clock


def test_compute_floodplain_working_days_with_alt():
    r = compute("fp-completion-notice", D("2026-11-05"))
    (x,) = r["results"]
    assert x["date"] == "2026-11-25"
    assert x["alt"] == {"date": "2026-11-20", "basis": "Monday to Friday, less Maine legal holidays"}


def test_compute_hours_with_and_without_time():
    r = compute("casualty", D("2026-10-03"), time(14, 30))
    by = {x["id"]: x for x in r["results"]}
    assert (by["casualty-secure-24h"]["date"], by["casualty-secure-24h"]["time"]) == ("2026-10-04", "14:30")
    assert by["casualty-permit-90"]["date"] == "2027-01-01"
    assert by["casualty-work-120"]["date"] == "2027-01-31"
    r = compute("fp-part1-ec-received", D("2026-10-02"))
    assert r["results"][0]["time"] == "00:00"
    assert "12:00 am" in r["results"][0]["steps"][0]


def test_compute_before_hours():
    r = compute("subsurface-ready", D("2026-10-06"), time(8, 0))
    x = r["results"][0]
    assert (x["date"], x["time"]) == ("2026-10-05", "08:00")


def test_compute_hearing_notices():
    r = compute("zba-hearing", D("2026-11-19"))
    by = {x["id"]: x for x in r["results"]}
    assert by["zba-mailing-14"]["date"] == "2026-11-05"
    assert by["zba-publication-14"]["date"] == "2026-11-05"
    assert by["zba-shoreland-dep-20"]["date"] == "2026-10-29"  # Oct 30 is a Friday


def test_compute_rental_annual():
    r = compute("rental-cycle", D("2026-11-02"))
    assert r["results"][0]["date"] == "2027-10-31"
    assert r["results"][0]["closed"] == "Sunday"
    assert r["results"][0]["plan_by"] == "2027-10-28"


def test_every_trigger_every_day_of_a_year():
    data = load_table()
    start = D("2026-01-01")
    for t in data["trigger"]:
        for i in range(0, 366, 1):
            day = start + timedelta(days=i)
            r = compute(t["id"], day, time(9, 0) if t.get("needs_time") else None)
            assert r["results"], t["id"]
            for x in r["results"]:
                end = D(x["date"])
                conv = x["convention"]["id"]
                if x["direction"] == "before":
                    assert end < day or (x["unit"] == "hours" and end <= day)
                elif x["unit"] == "annual":
                    assert end >= day
                else:
                    assert end > day or x["unit"] == "hours"
                if conv in ("rule6a", "app1a"):
                    assert court_closed(end) is None, (x["id"], day)
                if conv in ("city_working_days", "city_before"):
                    assert city_closed(end) is None, (x["id"], day)
                if x["plan_by"]:
                    assert city_closed(D(x["plan_by"])) is None and D(x["plan_by"]) < end


def test_unknown_trigger():
    with pytest.raises(KeyError):
        compute("nope", D("2026-10-05"))


# ---------------------------------------------------------------- API

CSRF = {"X-Requested-With": "wv"}


def test_rule_table_is_public(client):
    r = client.get("/api/deadlines")
    assert r.status_code == 200
    body = r.json()
    assert {"conventions", "calendars", "triggers", "rules", "range"} <= set(body)
    one = next(x for x in body["rules"] if x["id"] == "zba-hearing-45")
    assert one["offset"] == "45 days after"
    assert one["verified"] is True and one["applies"] == "waterville"


def test_calendar_endpoint(client):
    r = client.get("/api/deadlines/calendar?year=2027")
    assert r.status_code == 200
    days = [h["date"] for h in r.json()["holidays"]]
    assert "2027-07-05" in days and "2027-07-04" in days
    assert client.get("/api/deadlines/calendar?year=1999").status_code == 422


def test_compute_needs_staff(client):
    r = client.get("/api/deadlines/compute?trigger=zba-decision&date=2026-10-05")
    assert r.status_code == 401


def test_compute_api(staff_client):
    r = staff_client.get("/api/deadlines/compute?trigger=zba-decision&date=2026-10-05")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["trigger"]["id"] == "zba-decision"
    assert body["weekday"] == "Monday"
    ids = [x["id"] for x in body["results"]]
    assert "zba-80b-45" in ids and "zba-variance-record-90" not in ids
    x = body["results"][0]
    for key in ("label", "date", "weekday", "citation", "url", "source", "quote", "verified", "convention", "steps", "offset"):
        assert key in x


def test_compute_api_with_time(staff_client):
    r = staff_client.get("/api/deadlines/compute?trigger=casualty&date=2026-10-03&time=14:30")
    assert r.status_code == 200
    assert r.json()["time"] == "14:30"


@pytest.mark.parametrize(
    "qs,status",
    [
        ("trigger=nope&date=2026-10-05", 404),
        ("trigger=zba-decision&date=2026-13-05", 400),
        ("trigger=zba-decision&date=2024-12-31", 400),
        ("trigger=zba-decision&date=2100-01-01", 400),
        ("trigger=zba-decision&date=10/05/2026", 400),
        ("trigger=casualty&date=2026-10-05&time=25:00", 400),
        ("trigger=zba-decision", 422),
    ],
)
def test_compute_api_errors(staff_client, qs, status):
    assert staff_client.get(f"/api/deadlines/compute?{qs}").status_code == status


def test_deadline_saves_to_case(staff_client):
    """The calculator's save shape is the notebook's deadline item."""
    c = staff_client.post("/api/staff/cases", json={"address": "1 Main St", "title": "Deadline test"}, headers=CSRF)
    assert c.status_code in (200, 201), c.text
    cid = c.json()["id"]
    x = compute("zba-decision", D("2026-10-05"))["results"][0]
    item = {"kind": "deadline", "label": x["label"], "date": x["date"], "citation": x["citation"], "trigger": "ZBA decision (vote on the original application), Oct 5, 2026", "note": x["steps"][-1]}
    r = staff_client.post(f"/api/staff/cases/{cid}/items", json=item, headers=CSRF)
    assert r.status_code in (200, 201), r.text
    got = staff_client.get(f"/api/staff/cases/{cid}").json()
    assert any(i["kind"] == "deadline" and i["date"] == x["date"] for i in got["items"])

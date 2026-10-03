"""Legal clocks (B7): /api/deadlines ...

Rules, triggers and counting conventions live in app/data/deadlines.toml, each
with its citation, its source and a verbatim quote of the controlling text.

  GET /api/deadlines                 the rule table (public read)
  GET /api/deadlines/calendar?year=  holidays and City Hall closed days (public)
  GET /api/deadlines/compute?trigger=&date=&time=
                                     every clock for one event (staff)

Calendars
  court  Maine legal holidays, 4 M.R.S. § 1051. A Sunday holiday is observed
         the Monday after. Used by M.R. Civ. P. 6(a) and M.R. App. P. 1A.
  city   City Hall closed days: Fridays, Saturdays and Sundays (the office is
         open Monday to Thursday since January 3, 2025), plus the twelve
         holidays of City Code § 56-5.1A on the 4 M.R.S. § 1051 dates, with a
         Sunday holiday observed the Monday after (§ 56-5.1C(1)).

Counting conventions (see [conventions] in the TOML for the cited text)
  rule6a / app1a     day of the event excluded; a last day on a Saturday,
                     Sunday or legal holiday rolls to the next court day;
                     under 7 days, intermediate closed days are skipped.
  city_calendar      day of the event excluded, calendar days, no roll; when
                     City Hall is closed on the last day, `plan_by` gives the
                     last open day before it.
  city_working_days  counts City Hall open days only; `alt` gives the Monday
                     to Friday count for comparison.
  clock_hours        hour by hour from the time entered.
  calendar_months    same day number N months on (1 M.R.S. § 72(11-C)),
                     clamped to the last day of a shorter month.
  city_before        N days before the event; a closed day moves earlier.
  annual             the next fixed month and day on or after the date.
"""

from __future__ import annotations

import calendar as _cal
import tomllib
from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from functools import lru_cache
from pathlib import Path
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_staff

router = APIRouter(tags=["deadlines"])

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "deadlines.toml"

# The city calendar (four-day week, § 56-5.1 as amended 12-3-2024) and the
# holiday list (Juneteenth and Indigenous Peoples Day, 2021) hold from here on.
MIN_DATE = date(2025, 1, 1)
MAX_DATE = date(2099, 12, 31)

UNITS = {"days", "working_days", "hours", "months", "annual"}
KINDS = {"deadline", "lapse", "earliest"}
DIRECTIONS = {"after", "before"}
CONVENTIONS_BY_UNIT = {
    "days": {"rule6a", "app1a", "city_calendar", "city_before"},
    "working_days": {"city_working_days"},
    "hours": {"clock_hours"},
    "months": {"calendar_months"},
    "annual": {"annual"},
}
try:
    LOCAL_TZ: ZoneInfo | None = ZoneInfo("America/New_York")
except ZoneInfoNotFoundError:  # no tz database in the image: count naive hours
    LOCAL_TZ = None

WEEKDAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]


# ---------------------------------------------------------------- holidays


def nth_weekday(year: int, month: int, weekday: int, n: int) -> date:
    """The nth `weekday` (Monday = 0) of a month, n from 1."""
    first = date(year, month, 1)
    return first + timedelta(days=(weekday - first.weekday()) % 7 + 7 * (n - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    last = date(year, month, _cal.monthrange(year, month)[1])
    return last - timedelta(days=(last.weekday() - weekday) % 7)


# 4 M.R.S. § 1051 and City Code § 56-5.1A name the same twelve days.
HOLIDAYS: tuple[tuple[str, Callable[[int], date]], ...] = (
    ("New Year's Day", lambda y: date(y, 1, 1)),
    ("Martin Luther King, Jr., Day", lambda y: nth_weekday(y, 1, 0, 3)),
    ("Washington's Birthday (Presidents' Day)", lambda y: nth_weekday(y, 2, 0, 3)),
    ("Patriot's Day", lambda y: nth_weekday(y, 4, 0, 3)),
    ("Memorial Day", lambda y: last_weekday(y, 5, 0)),
    ("Juneteenth", lambda y: date(y, 6, 19)),
    ("Independence Day", lambda y: date(y, 7, 4)),
    ("Labor Day", lambda y: nth_weekday(y, 9, 0, 1)),
    ("Indigenous Peoples Day", lambda y: nth_weekday(y, 10, 0, 2)),
    ("Veterans Day", lambda y: date(y, 11, 11)),
    ("Thanksgiving Day", lambda y: nth_weekday(y, 11, 3, 4)),
    ("Christmas Day", lambda y: date(y, 12, 25)),
)


@lru_cache(maxsize=256)
def legal_holidays(year: int) -> dict[date, str]:
    """Maine legal holidays (4 M.R.S. § 1051) in a year, with Sunday holidays
    also observed the Monday after. The city's § 56-5.1 holidays fall on the
    same days and follow the same Sunday rule, so this serves both calendars."""
    out: dict[date, str] = {}
    for name, fn in HOLIDAYS:
        d = fn(year)
        out[d] = name
        if d.weekday() == 6:
            out[d + timedelta(days=1)] = f"{name} (observed)"
    return out


def holiday(d: date) -> str | None:
    return legal_holidays(d.year).get(d)


def court_closed(d: date) -> str | None:
    """Why a day is not a court day under Rule 6(a), or None."""
    if d.weekday() == 5:
        return "Saturday"
    if d.weekday() == 6:
        return "Sunday"
    return holiday(d)


def city_closed(d: date) -> str | None:
    """Why City Hall is closed that day, or None when it is open."""
    if h := holiday(d):
        return h
    if d.weekday() == 4:
        return "Friday, City Hall closed"
    if d.weekday() == 5:
        return "Saturday"
    if d.weekday() == 6:
        return "Sunday"
    return None


def weekday_closed(d: date) -> str | None:
    """Closed days on a Monday to Friday week (comparison count only)."""
    return court_closed(d)


# ---------------------------------------------------------------- date math


@dataclass
class Count:
    end: date
    steps: list[str]
    raw: date | None = None  # the date before any roll or move


def fmt(d: date) -> str:
    return f"{WEEKDAYS[d.weekday()]}, {d.strftime('%B')} {d.day}, {d.year}"


def add_rule6a(start: date, n: int, short_limit: int = 7) -> Count:
    """M.R. Civ. P. 6(a) (and App. P. 1A, short_limit=7 for "6 days or fewer")."""
    steps = [f"Day of the event ({fmt(start)}) not counted."]
    if n < short_limit:
        d, left = start, n
        skipped = []
        while left:
            d += timedelta(days=1)
            why = court_closed(d)
            if why:
                skipped.append(f"{d.isoformat()} ({why})")
                continue
            left -= 1
        if skipped:
            steps.append(f"Period under {short_limit} days: skipped " + ", ".join(skipped) + ".")
        steps.append(f"Day {n}: {fmt(d)}.")
        return Count(d, steps)
    raw = start + timedelta(days=n)
    steps.append(f"Day {n}: {fmt(raw)}.")
    d = raw
    while why := court_closed(d):
        steps.append(f"{fmt(d)} is a {why}; the period runs to the next court day." if why in ("Saturday", "Sunday") else f"{fmt(d)} is {why}, a legal holiday; the period runs to the next court day.")
        d += timedelta(days=1)
    return Count(d, steps, raw if d != raw else None)


def add_calendar_days(start: date, n: int) -> Count:
    end = start + timedelta(days=n)
    return Count(end, [f"Day of the event ({fmt(start)}) not counted.", f"Day {n}: {fmt(end)}."])


def add_working_days(start: date, n: int, closed: Callable[[date], str | None] = city_closed) -> Count:
    if n < 1:
        raise ValueError("working days must be at least 1")
    d, left, skipped = start, n, 0
    while left:
        d += timedelta(days=1)
        if closed(d):
            skipped += 1
            continue
        left -= 1
    steps = [
        f"Day of the event ({fmt(start)}) not counted.",
        f"Counted {n} open days and passed over {skipped} closed days; working day {n} is {fmt(d)}.",
    ]
    return Count(d, steps)


def add_months(start: date, n: int) -> Count:
    """Calendar months: the same day number n months later, or the last day of
    a shorter month (Jan 31 + 1 month = Feb 28 or 29; Feb 29 + 12 = Feb 28)."""
    m = start.month - 1 + n
    y, m = start.year + m // 12, m % 12 + 1
    last = _cal.monthrange(y, m)[1]
    end = date(y, m, min(start.day, last))
    steps = [f"{n} calendar months from {fmt(start)}: {fmt(end)}."]
    if start.day > last:
        steps.append(f"{_cal.month_name[m]} {y} has no day {start.day}; the clock ends on its last day.")
    return Count(end, steps)


def add_hours(base: datetime, hours: int) -> datetime:
    """Elapsed hours from a Maine wall-clock time, across daylight saving
    changes, returned as Maine wall-clock time (naive)."""
    if LOCAL_TZ is None:
        return base + timedelta(hours=hours)
    aware = base.replace(tzinfo=LOCAL_TZ)
    out = (aware.astimezone(timezone.utc) + timedelta(hours=hours)).astimezone(LOCAL_TZ)
    return out.replace(tzinfo=None)


def before_days(event: date, n: int) -> Count:
    raw = event - timedelta(days=n)
    steps = [f"Event day ({fmt(event)}) not counted.", f"{n} days before: {fmt(raw)}."]
    d = raw
    while why := city_closed(d):
        steps.append(f"{fmt(d)}: {why}; moved one day earlier.")
        d -= timedelta(days=1)
    return Count(d, steps, raw if d != raw else None)


def next_annual(start: date, month: int, day: int) -> Count:
    d = date(start.year, month, day)
    if d < start:
        d = date(start.year + 1, month, day)
    return Count(d, [f"Next {_cal.month_name[month]} {day} on or after {fmt(start)}: {fmt(d)}."])


def last_open_on_or_before(d: date, floor: date) -> date | None:
    while d > floor:
        if not city_closed(d):
            return d
        d -= timedelta(days=1)
    return None


# ---------------------------------------------------------------- data


class RuleTableError(ValueError):
    pass


@lru_cache(maxsize=1)
def load_table(path: Path = DATA_PATH) -> dict:
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    validate_table(data)
    return data


def validate_table(data: dict) -> None:
    conventions = data.get("conventions", {})
    triggers = {t["id"]: t for t in data.get("trigger", [])}
    if len(triggers) != len(data.get("trigger", [])):
        raise RuleTableError("duplicate trigger id")
    ids: set[str] = set()
    used: set[str] = set()
    for r in data.get("rule", []):
        rid = r.get("id", "?")
        if rid in ids:
            raise RuleTableError(f"duplicate rule id {rid}")
        ids.add(rid)
        for key in ("label", "actor", "citation", "quote", "url", "convention", "unit", "direction", "kind"):
            if not r.get(key):
                raise RuleTableError(f"{rid}: missing {key}")
        if not isinstance(r.get("verified"), bool):
            raise RuleTableError(f"{rid}: verified must be true or false")
        if r["unit"] not in UNITS or r["direction"] not in DIRECTIONS or r["kind"] not in KINDS:
            raise RuleTableError(f"{rid}: bad unit, direction or kind")
        if r["convention"] not in conventions:
            raise RuleTableError(f"{rid}: unknown convention {r['convention']}")
        if r["convention"] not in CONVENTIONS_BY_UNIT[r["unit"]]:
            raise RuleTableError(f"{rid}: convention {r['convention']} does not fit unit {r['unit']}")
        if r["unit"] == "annual":
            date(2024, r["month"], r["day"])
        elif not (isinstance(r.get("amount"), int) and r["amount"] > 0):
            raise RuleTableError(f"{rid}: amount must be a positive integer")
        if r["direction"] == "before" and r["convention"] not in ("city_before", "clock_hours"):
            raise RuleTableError(f"{rid}: 'before' needs city_before or clock_hours")
        if r["convention"] == "city_before" and r["direction"] != "before":
            raise RuleTableError(f"{rid}: city_before counts back")
        if r.get("applies", "waterville") not in ("waterville", "check"):
            raise RuleTableError(f"{rid}: applies must be waterville or check")
        for t in r.get("triggers", []):
            if t not in triggers:
                raise RuleTableError(f"{rid}: unknown trigger {t}")
            used.add(t)
        if not r.get("triggers"):
            raise RuleTableError(f"{rid}: no triggers")
    unused = set(triggers) - used
    if unused:
        raise RuleTableError(f"triggers with no rules: {sorted(unused)}")


def offset_text(r: dict) -> str:
    if r["unit"] == "annual":
        return f"Each {_cal.month_name[r['month']]} {r['day']}"
    n, unit = r["amount"], r["unit"]
    word = {"days": "day", "working_days": "working day", "hours": "hour", "months": "month"}[unit]
    return f"{n} {word}{'' if n == 1 else 's'} {r['direction']}"


def public_rule(r: dict) -> dict:
    out = {k: v for k, v in r.items() if k != "triggers"}
    out["triggers"] = list(r["triggers"])
    out["applies"] = r.get("applies", "waterville")
    out["checked"] = r.get("checked") or load_table().get("checked_default")
    out["offset"] = offset_text(r)
    out.setdefault("also", [])
    return out


# ---------------------------------------------------------------- compute


def compute_rule(r: dict, start: date, at: time | None, conventions: dict) -> dict:
    conv = r["convention"]
    unit = r["unit"]
    when: datetime | None = None
    if unit == "hours":
        base = datetime.combine(start, at or time(0, 0))
        when = add_hours(base, r["amount"] if r["direction"] == "after" else -r["amount"])
        count = Count(when.date(), [
            f"Counted from {fmt(start)} at {base.strftime('%H:%M')}" + ("" if at else " (no time entered, so from 12:00 am, the earliest reading)") + ".",
            f"{r['amount']} hours {r['direction']}: {fmt(when.date())} at {when.strftime('%H:%M')} Maine time.",
        ])
    elif conv in ("rule6a", "app1a"):
        count = add_rule6a(start, r["amount"])
    elif conv == "city_calendar":
        count = add_calendar_days(start, r["amount"])
    elif conv == "city_working_days":
        count = add_working_days(start, r["amount"])
    elif conv == "calendar_months":
        count = add_months(start, r["amount"])
    elif conv == "city_before":
        count = before_days(start, r["amount"])
    elif conv == "annual":
        count = next_annual(start, r["month"], r["day"])
    else:  # validate_table rules this out
        raise RuleTableError(conv)

    end = count.end
    closed = city_closed(end)
    plan_by = None
    if closed and conv in ("city_calendar", "calendar_months", "annual"):
        plan_by = last_open_on_or_before(end, start)
        if plan_by:
            count.steps.append(f"City Hall is closed that day ({closed}). Last open day before it: {fmt(plan_by)}.")
    alt = None
    if conv == "city_working_days":
        a = add_working_days(start, r["amount"], weekday_closed)
        if a.end != end:
            alt = {"date": a.end.isoformat(), "basis": "Monday to Friday, less Maine legal holidays"}

    c = conventions[conv]
    return {
        **public_rule(r),
        "convention": {"id": conv, "label": c["label"], "summary": c["summary"], "citation": c.get("citation", ""), "caution": c.get("caution", "")},
        "date": end.isoformat(),
        "time": when.strftime("%H:%M") if when else None,
        "weekday": WEEKDAYS[end.weekday()],
        "raw_date": count.raw.isoformat() if count.raw else None,
        "closed": closed,
        "plan_by": plan_by.isoformat() if plan_by else None,
        "alt": alt,
        "steps": count.steps,
    }


def compute(trigger: str, start: date, at: time | None = None) -> dict:
    data = load_table()
    triggers = {t["id"]: t for t in data["trigger"]}
    if trigger not in triggers:
        raise KeyError(trigger)
    rules = [r for r in data["rule"] if trigger in r["triggers"]]
    results = [compute_rule(r, start, at, data["conventions"]) for r in rules]
    results.sort(key=lambda x: (x["date"], x["time"] or "", x["label"]))
    t = triggers[trigger]
    return {
        "trigger": {"id": t["id"], "label": t["label"], "group": t["group"], "help": t.get("help", ""), "needs_time": bool(t.get("needs_time"))},
        "date": start.isoformat(),
        "time": at.strftime("%H:%M") if at else None,
        "weekday": WEEKDAYS[start.weekday()],
        "event_closed": city_closed(start),
        "results": results,
        "unverified": sum(1 for r in results if not r["verified"]),
    }


def _parse_date(s: str) -> date:
    try:
        d = date.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, "Date must be YYYY-MM-DD.") from None
    if not (MIN_DATE <= d <= MAX_DATE):
        raise HTTPException(400, f"Dates from {MIN_DATE.isoformat()} to {MAX_DATE.isoformat()} only; the City calendar before 2025 differs.")
    return d


def _parse_time(s: str) -> time | None:
    if not s:
        return None
    try:
        return time.fromisoformat(s)
    except ValueError:
        raise HTTPException(400, "Time must be HH:MM.") from None


# ---------------------------------------------------------------- routes


@router.get("/api/deadlines")
async def rule_table():
    """The whole rule table: public, since it is the City's own text with citations."""
    data = load_table()
    return {
        "checked": data.get("checked_default"),
        "conventions": data["conventions"],
        "calendars": data["calendar"],
        "triggers": data["trigger"],
        "rules": [public_rule(r) for r in data["rule"]],
        "range": {"min": MIN_DATE.isoformat(), "max": MAX_DATE.isoformat()},
    }


@router.get("/api/deadlines/calendar")
async def closed_days(year: int = Query(ge=MIN_DATE.year, le=MAX_DATE.year)):
    """Holidays in a year for both calendars. Weekends and Fridays are implied."""
    days = sorted(legal_holidays(year).items())
    return {
        "year": year,
        "city_open_weekdays": ["Monday", "Tuesday", "Wednesday", "Thursday"],
        "holidays": [
            {"date": d.isoformat(), "name": n, "weekday": WEEKDAYS[d.weekday()], "court_closed": True, "city_closed": True}
            for d, n in days
        ],
    }


@router.get("/api/deadlines/compute")
async def compute_route(
    trigger: str = Query(min_length=1, max_length=64),
    date: str = Query(min_length=10, max_length=10),
    time: str = Query(default="", max_length=8),
    user: str = Depends(require_staff),
):
    start = _parse_date(date)
    at = _parse_time(time)
    try:
        return compute(trigger, start, at)
    except KeyError:
        raise HTTPException(404, "Unknown trigger event.") from None

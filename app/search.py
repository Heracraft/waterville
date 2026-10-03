"""Retrieval over the Azure AI Search index, plus source formatting for prompts.

City sources and state sources are searched separately and merged, so the
much larger state manuals can't crowd the city's own code out of the results.

With config.FAKE_AZURE, search(), lookup() and facets() answer from
tests/fixtures/search_docs.json (real chunk rows) instead of Azure.
"""

from __future__ import annotations

import asyncio
import json
import logging
import re
import time
import unicodedata
from dataclasses import dataclass
from functools import lru_cache
from typing import Iterable

from fastapi import HTTPException

from . import config
from .azure_auth import http, search_auth

log = logging.getLogger("app.search")

# ---------------------------------------------------------------- source types

# The city ("local") bucket. city_form: Waterville permit applications and forms.
LOCAL_TYPES = ("code", "attachment", "new_law", "city_form")
# Curated currency and conflict notes. Staff mode only; public searches never see them.
STAFF_ONLY_TYPES = ("staff_note",)
# What public searches leave out (the corpus agent's name for STAFF_ONLY_TYPES).
PUBLIC_EXCLUDE_TYPES = STAFF_ONLY_TYPES
STATE_TYPES = ("state_statute", "state_rule", "state_guidance", "model_code_ref")
SOURCE_TYPES = LOCAL_TYPES + STATE_TYPES + STAFF_ONLY_TYPES

SELECT = "id,title,citation,breadcrumb,url,source_type,content,page_start,page_end"
# Staff answers also see each chunk's edition date, so the model can name a stale edition.
STAFF_SELECT = SELECT + ",chapter_number,chunk_index,chunk_count,legislation_through"

SOURCE_LABELS = {
    "new_law": "New Law, not yet codified",
    "state_statute": "Maine statute",
    "state_rule": "Maine rule",
    "state_guidance": "State guidance manual, may be dated",
    "model_code_ref": "reference only; full text not available",
    "staff_note": "staff note",
    "city_form": "City form",
}

CORPUS_LABELS = ("City of Waterville", "Maine ", "Code of Maine Rules", "Model code adopted")

MAX_FILTER_VALUES = 50
CHAPTER_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9.\- ]{0,19}$")


# ---------------------------------------------------------------- filters


def odata_str(value: str) -> str:
    """An OData string literal: single quotes doubled, wrapped in quotes."""
    return "'" + str(value).replace("'", "''") + "'"


def validate_filters(filters: dict | None, mode: str = "public") -> dict:
    """Normalize {chapters?, source_types?}; raise ValueError on anything off the allowlist."""
    if not filters:
        return {}
    out: dict = {}
    chapters = filters.get("chapters") or []
    types = filters.get("source_types") or []
    if not isinstance(chapters, list) or not isinstance(types, list):
        raise ValueError("Filters must be lists.")
    if len(chapters) > MAX_FILTER_VALUES or len(types) > MAX_FILTER_VALUES:
        raise ValueError("Too many filter values.")
    if chapters:
        clean = []
        for c in chapters:
            if not isinstance(c, str) or not CHAPTER_RE.match(c.strip()):
                raise ValueError(f"Unknown chapter: {str(c)[:40]}")
            clean.append(c.strip())
        out["chapters"] = list(dict.fromkeys(clean))
    if types:
        for t in types:
            if t not in SOURCE_TYPES:
                raise ValueError(f"Unknown source type: {str(t)[:40]}")
            if t in STAFF_ONLY_TYPES and mode != "staff":
                raise ValueError(f"Unknown source type: {t}")
        out["source_types"] = list(dict.fromkeys(types))
    return out


@dataclass(frozen=True)
class Bucket:
    """One search call: source types in (or not in) a set, optionally limited to chapters."""

    types: tuple[str, ...]
    exclude: bool = False
    chapters: tuple[str, ...] = ()

    def odata(self) -> str:
        expr = f"search.in(source_type, '{','.join(self.types)}')"
        if self.exclude:
            expr = "not " + expr
        if self.chapters:
            ors = " or ".join(f"chapter_number eq {odata_str(c)}" for c in self.chapters)
            expr += f" and ({ors})"
        return expr

    def matches(self, doc: dict) -> bool:
        """The same predicate in Python, for FAKE_AZURE."""
        in_types = doc.get("source_type") in self.types
        if in_types == self.exclude:
            return False
        return not self.chapters or doc.get("chapter_number") in self.chapters


def buckets(mode: str = "public", filters: dict | None = None) -> tuple[Bucket | None, Bucket | None]:
    """(local, state) buckets for a search. None means skip that bucket.

    A chapters filter limits the city bucket only: state chunks have no
    chapter_number. A source_types filter limits both buckets.
    """
    filters = validate_filters(filters, mode)
    local_types = LOCAL_TYPES + (STAFF_ONLY_TYPES if mode == "staff" else ())
    chapters = tuple(filters.get("chapters") or ())
    wanted = filters.get("source_types")
    if wanted:
        lt = tuple(t for t in local_types if t in wanted)
        st = tuple(t for t in STATE_TYPES if t in wanted)
        local = Bucket(lt, chapters=chapters) if lt else None
        state = Bucket(st) if st else None
    else:
        local = Bucket(local_types, chapters=chapters)
        state = Bucket(LOCAL_TYPES + STAFF_ONLY_TYPES, exclude=True)
    return local, state


# ---------------------------------------------------------------- Azure calls


async def _post_search(body: dict) -> dict:
    url = f"{config.SEARCH_ENDPOINT}/indexes/{config.SEARCH_INDEX}/docs/search?api-version={config.SEARCH_API}"
    r = await http.post(url, headers=await search_auth.headers(), json=body)
    if r.status_code >= 300:
        log.error("search failed %s %s", r.status_code, r.text[:500])
        raise HTTPException(502, "Search is unavailable right now.")
    return r.json()


async def _search(query: str, filter_: str, top: int, select: str = SELECT) -> list[dict]:
    body = {
        "search": query,
        "filter": filter_,
        "queryType": "semantic",
        "semanticConfiguration": "default",
        "semanticErrorHandling": "partial",
        "vectorQueries": [{"kind": "text", "text": query, "fields": "content_vector", "k": 50}],
        "top": top,
        "select": select,
    }
    return (await _post_search(body))["value"]


def _rank(d: dict) -> float:
    return d.get("@search.rerankerScore") or 0.0


async def search(
    query: str,
    mode: str = "public",
    k_local: int | None = None,
    k_state: int | None = None,
    filters: dict | None = None,
) -> list[dict]:
    staff = mode == "staff"
    if k_local is None:
        k_local = config.STAFF_K_LOCAL if staff else config.LOCAL_K
    if k_state is None:
        k_state = config.STAFF_K_STATE if staff else config.STATE_K
    local, state = buckets(mode, filters)
    select = STAFF_SELECT if staff else SELECT
    calls = []
    for bucket, k in ((local, k_local), (state, k_state)):
        if bucket is None or k <= 0:
            continue
        if config.FAKE_AZURE:
            calls.append(_fake_search(query, bucket, k, select))
        else:
            calls.append(_search(query, bucket.odata(), k, select))
    results = await asyncio.gather(*calls)
    docs = sorted([d for r in results for d in r], key=_rank, reverse=True)
    # Drop weak matches, but always keep a few so the model can say what it found.
    strong = [d for d in docs if _rank(d) >= config.MIN_RERANKER_SCORE]
    docs = strong if len(strong) >= 3 else docs[:3]
    if staff and state is not None and state.matches({"source_type": "state_statute"}) and ENFORCEMENT_RE.search(query):
        docs += await penalty_sources(docs)
    return docs


async def lookup(filter_: str, top: int = 50, order_by: str | None = None, select: str | None = None) -> list[dict]:
    """Plain filtered fetch (no ranking), for exact citation lookup.

    `filter_` is OData; build values with odata_str(). Under FAKE_AZURE only
    `field eq 'v'` terms joined with `and` / `or` (and parentheses) work.
    """
    if config.FAKE_AZURE:
        docs = [d for d in fake_docs() if _fake_filter(filter_)(d)]
        if order_by:
            field = order_by.split()[0]
            docs.sort(key=lambda d: (d.get(field) is None, d.get(field)), reverse=order_by.endswith(" desc"))
        return [dict(d) for d in docs[:top]]
    body = {"search": "*", "filter": filter_, "top": top, "select": select or SELECT}
    if order_by:
        body["orderby"] = order_by
    return (await _post_search(body))["value"]


async def facets(fields: Iterable[str], filter_: str | None = None, count: int = 500) -> dict[str, list[dict]]:
    """{field: [{"value": v, "count": n}, ...]} over the whole index (or the filter)."""
    fields = list(fields)
    if config.FAKE_AZURE:
        out = {}
        keep = _fake_filter(filter_) if filter_ else (lambda d: True)
        for f in fields:
            counts: dict = {}
            for d in fake_docs():
                if keep(d) and d.get(f) is not None:
                    counts[d[f]] = counts.get(d[f], 0) + 1
            out[f] = [{"value": v, "count": n} for v, n in sorted(counts.items(), key=lambda x: -x[1])][:count]
        return out
    body = {"search": "*", "top": 0, "facets": [f"{f},count:{count}" for f in fields]}
    if filter_:
        body["filter"] = filter_
    return (await _post_search(body)).get("@search.facets", {})


# ---------------------------------------------------------------- fake search


@lru_cache(maxsize=1)
def _fixture_docs() -> tuple[dict, ...]:
    path = config.FIXTURES_DIR / "search_docs.json"
    return tuple(json.loads(path.read_text()))


def fake_docs() -> list[dict]:
    """The fixture rows FAKE_AZURE serves (copies)."""
    return [dict(d) for d in _fixture_docs()]


_STOP = set(
    "a an and are can do does for from have how i in is it my of on or the to what when where which who "
    "why with you your me we our need any about be this that there their they if".split()
)


def _terms(text: str) -> set[str]:
    # Crude stemming ("fences" -> "fence") is enough to rank fixtures sensibly.
    return {w[:-1] if len(w) > 4 and w.endswith("s") else w
            for w in re.findall(r"[a-z0-9]+", text.lower()) if len(w) > 2 and w not in _STOP}


async def _fake_search(query: str, bucket: Bucket, top: int, select: str = SELECT) -> list[dict]:
    terms = _terms(query)
    scored = []
    for d in _fixture_docs():
        if not bucket.matches(d):
            continue
        head = _terms(f"{d.get('title') or ''} {d.get('breadcrumb') or ''}")
        body = _terms(d.get("content") or "")
        hits = 2 * len(terms & head) + len(terms & body)
        doc = {k: d.get(k) for k in select.split(",")}
        doc["@search.rerankerScore"] = round(min(3.9, 0.5 + 0.35 * hits), 3)
        scored.append(doc)
    scored.sort(key=_rank, reverse=True)
    return scored[:top]


_EQ = re.compile(r"^\(?\s*(\w+)\s+eq\s+('(?:[^']|'')*'|\d+)\s*\)?$")


def _fake_filter(filter_: str):
    """Evaluate simple OData (`a eq 'x' and (b eq 'y' or b eq 'z')`) for FAKE_AZURE."""

    def atom(expr: str):
        m = _EQ.match(expr.strip())
        if not m:
            raise ValueError(f"FAKE_AZURE cannot evaluate filter: {expr}")
        field, raw = m.groups()
        value = raw[1:-1].replace("''", "'") if raw.startswith("'") else int(raw)
        return lambda d: d.get(field) == value

    def parse(expr: str):
        expr = expr.strip()
        while expr.startswith("(") and expr.endswith(")") and _balanced(expr[1:-1]):
            expr = expr[1:-1].strip()
        for op in (" or ", " and "):
            parts = _split_top(expr, op)
            if len(parts) > 1:
                preds = [parse(p) for p in parts]
                return (lambda d: any(p(d) for p in preds)) if op == " or " else (lambda d: all(p(d) for p in preds))
        return atom(expr)

    return parse(filter_)


def _balanced(s: str) -> bool:
    depth, quoted = 0, False
    for ch in s:
        if ch == "'":
            quoted = not quoted
        elif not quoted:
            depth += ch == "("
            depth -= ch == ")"
            if depth < 0:
                return False
    return depth == 0


def _split_top(s: str, op: str) -> list[str]:
    parts, depth, quoted, i, start = [], 0, False, 0, 0
    while i < len(s):
        ch = s[i]
        if ch == "'":
            quoted = not quoted
        elif not quoted:
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
            elif depth == 0 and s.startswith(op, i):
                parts.append(s[start:i])
                i += len(op)
                start = i
                continue
        i += 1
    parts.append(s[start:])
    return parts


# ---------------------------------------------------------------- prompt helpers


def retrieval_query(messages: list[dict]) -> str:
    users = [m["content"] for m in messages if m["role"] == "user"]
    q = users[-1]
    # Short follow-ups ("what about in R-B?") lean on the previous question.
    if len(users) > 1 and len(q.split()) < 12:
        q = users[-2] + " " + q
    return q[: config.MAX_QUESTION_CHARS * 2]


def source_text(d: dict) -> str:
    """The chunk body without its two-line context header (corpus label, breadcrumb)."""
    content = d.get("content") or ""
    lines = content.split("\n")
    if len(lines) >= 3 and not lines[2].strip() and lines[0].strip() and lines[1].strip():
        crumb = d.get("breadcrumb") or ""
        if (crumb and lines[1].startswith(crumb)) or lines[0].startswith(CORPUS_LABELS):
            return "\n".join(lines[3:]).strip("\n")
    return content.strip("\n")


def open_url(d: dict) -> str | None:
    url = d.get("url")
    if url and d.get("page_start") and url.split("#")[0].split("?")[0].lower().endswith(".pdf"):
        return f"{url.split('#')[0]}#page={d['page_start']}"
    return url


def format_sources(docs: list[dict], mode: str = "public") -> tuple[str, list[dict]]:
    """Prompt text and the `sources` event list.

    Staff mode ends each block with the chunk's edition date, so the model can
    name a stale edition, and adds `legislation_through` to each source. The
    label line stays a bare citation, so the model does not copy the date into
    its citations. Public output is unchanged.
    """
    blocks, meta = [], []
    staff = mode == "staff"
    for n, d in enumerate(docs, 1):
        label = d.get("citation") or d.get("title")
        if suffix := SOURCE_LABELS.get(d.get("source_type")):
            label += f" ({suffix})"
        edition = f"\n(Edition: legislation through {d['legislation_through']})" if staff and d.get("legislation_through") else ""
        blocks.append(f"[{n}] {label}\n{d['content']}{edition}")
        meta.append(
            {
                "n": n,
                "citation": d.get("citation"),
                "title": d.get("title"),
                "breadcrumb": d.get("breadcrumb"),
                "url": d.get("url"),
                "source_type": d.get("source_type"),
                "page_start": d.get("page_start"),
                "page_end": d.get("page_end"),
                "label": SOURCE_LABELS.get(d.get("source_type")),
                "open_url": open_url(d),
                "text": source_text(d),
            }
        )
        if staff:
            meta[-1]["legislation_through"] = d.get("legislation_through")
    return "\n\n---\n\n".join(blocks), meta


# ---------------------------------------------------------------- staff: enforcement chain

# Questions about violations, penalties or court work. A staff answer to one of
# these traces the penalty tier under 30-A M.R.S. § 4452(3), so that section's
# penalty text is added to the sources when the index has it and the search
# missed it. The model still quotes the tier from the source text.
ENFORCEMENT_RE = re.compile(
    r"\b(violat\w*|penalt\w*|fines?|fined|enforc\w*|NOVs?|80K|summons|abat\w*|court|stop[- ]work|"
    r"civil action|consent agreement|land use citation)\b",
    re.I,
)
PENALTY_STATUTE = "30-A M.R.S. § 4452"
PENALTY_TEXT_RE = re.compile(r"penalt", re.I)
MAX_PINNED = 2


async def penalty_sources(docs: list[dict]) -> list[dict]:
    """Chunks of 30-A M.R.S. § 4452 that set out penalties, not already in `docs`."""
    have = {d.get("id") for d in docs}
    try:
        rows = await lookup(f"citation eq {odata_str(PENALTY_STATUTE)}", top=50, order_by="chunk_index", select=STAFF_SELECT)
    except HTTPException:
        log.warning("could not add %s to staff sources", PENALTY_STATUTE)
        return []
    rows.sort(key=lambda r: (r.get("chunk_index") or 0, r.get("id") or ""))
    picked = [r for r in rows if r.get("id") not in have and PENALTY_TEXT_RE.search(r.get("content") or "")]
    return [{k: r.get(k) for k in STAFF_SELECT.split(",")} for r in picked[:MAX_PINNED]]


# ---------------------------------------------------------------- citation lookup

# Index citation forms, as the exporters write them:
#   city code     "§ 205-7", "§ 275-4.27", "§ 275-4.9.1", "§ DL-1"
#   charter       "Charter Art. IV, § 9"
#   chapters      "Chapter 205. Property Maintenance" (node_type chapter)
#   new laws      "Ord. No. 167-2026"
#   statutes      "30-A M.R.S. § 4452", "38 M.R.S. § 436-A"
#   rules         "16-642 CMR ch. 3", "08-003 CMR ch. 1"

LOOKUP_TOP = 300
LOOKUP_SELECT = STAFF_SELECT + ",node_type,chapter_title,section_number,section_title"

_SEC = r"(?:§+|sec(?:tion)?s?\.?|s\.)"
_CMR_RE = re.compile(
    r"^(\d{2})\s*-\s*(\d{3})\s*C\.?\s*M\.?\s*R\.?\s*,?\s*(?:ch(?:apter|\.)?|c\.)?\s*(\d{1,4})\b(.*)$", re.I
)
_TITLE = r"(\d{1,2}(?:\s*-\s*[a-z]{1,2})?)"
_STAT_SEC = r"(\d{1,5}(?:\s*-\s*[a-z]{1,2}\b)?)"
_MRS_RE = re.compile(
    r"^(?:title\s+)?" + _TITLE + r"\s*,?\s*M\.?\s*R\.?\s*S\.?\s*(?:A\.?)?\s*,?\s*(?:" + _SEC + r"\s*)?" + _STAT_SEC + r"(.*)$",
    re.I,
)
_TITLE_SEC_RE = re.compile(r"^(?:title\s+)?" + _TITLE + r"\s*,?\s*" + _SEC + r"\s*" + _STAT_SEC + r"(.*)$", re.I)
_CHARTER_RE = re.compile(
    r"^(?:city\s+)?charter\b\s*,?\s*(?:art(?:icle)?\.?\s*)?([ivxlc]+|\d{1,2})\s*,?\s*(?:" + _SEC + r"\s*)?(\d{1,2})\b(.*)$",
    re.I,
)
_ARTICLE_RE = re.compile(r"^art(?:icle)?\.?\s*([ivxlc]+|\d{1,2})\s*,?\s*" + _SEC + r"\s*(\d{1,2})\b(.*)$", re.I)
_CHARTER_ONLY_RE = re.compile(r"^(?:city\s+)?charter\b", re.I)
_ORD_RE = re.compile(r"^ord(?:inance)?s?\.?\s*(?:no\.?|number|#)?\s*(\d{1,4})\s*-\s*(\d{4})\b(.*)$", re.I)
_CHAPTER_RE = re.compile(r"^(?:chapter|ch\.?|c\.)\s*(\d{1,3}|c)\b\.?(?:\s.*)?$", re.I)
_CITY_PREFIX_RE = re.compile(
    r"^(?:(?:the\s+)?city\s+of\s+)?(?:waterville\b,?\s*(?:me\b\.?|maine\b)?,?\s*)?(?:city\s+)?"
    r"(?:code\b(?:\s+of\s+ordinances)?,?\s*)?",
    re.I,
)
_SEC_PREFIX_RE = re.compile(r"^" + _SEC + r"\s*", re.I)
_CITY_RE = re.compile(r"^(\d{1,3}|[a-z]{1,3})\s*-\s*(\d{1,3}(?:\.\d{1,3})*)(.*)$", re.I)
# What may follow a city section number: a subsection letter and numbered parts, "A", "K(3)", "(2)(a)".
_CITY_REST_RE = re.compile(r"^\s*\.?\s*([a-z]{1,2})?\s*((?:\(\s*[0-9a-z]{1,4}\s*\)\s*)*)\.?\s*$", re.I)
_REST_RE = re.compile(r"^[\s.,;§()\w-]{0,40}$")
# Maine Rules of Civil Procedure: "M.R. Civ. P. 80K", "MRCivP 80K(c)", "Civ. R. 80B", "Rule 80E".
_COURT_RULE_RE = re.compile(
    r"^(?:(?:maine\s+)?m\.?\s*r\.?\s*civ\.?\s*p\.?|me\.?\s*r\.?\s*civ\.?\s*p\.?|(?:maine\s+)?rules?\s+of\s+civil\s+procedure,?(?:\s+rule)?|civ\.?\s*r\.?|(?:civil\s+)?rule)\s*(\d{1,3}[a-z]{0,2}(?:-[a-z0-9]{1,2})?)\b(.*)$",
    re.I,
)
# Renumbered rules (PL 2025, c. 388): 16-642 CMR ch. N is now 08-003 CMR ch. N+1,
# and 16-219 CMR ch. 52 is now 08-003 CMR ch. 1. A lookup of an old number
# falls back to the current one when the old one is not indexed.
_RENUMBERED = {("16-642", n): f"08-003 CMR ch. {n + 1}" for n in range(1, 8)} | {("16-219", 52): "08-003 CMR ch. 1"}

_ROMAN = [(10, "X"), (9, "IX"), (5, "V"), (4, "IV"), (1, "I")]
_ROMAN_VALUES = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}


def _to_roman(n: int) -> str:
    out = ""
    for v, r in [(100, "C"), (90, "XC"), (50, "L"), (40, "XL")] + _ROMAN:
        while n >= v:
            out += r
            n -= v
    return out


def _article(raw: str) -> str:
    """'IV', 'iv' or '4' -> 'IV'. Raises ValueError for a malformed numeral."""
    if raw.isdigit():
        n = int(raw)
    else:
        r = raw.upper()
        vals = [_ROMAN_VALUES[c] for c in r]
        n = sum(-v if i + 1 < len(vals) and v < vals[i + 1] else v for i, v in enumerate(vals))
        if _to_roman(n) != r:
            raise ValueError(f"Could not read the article number {raw!r}.")
    if not 1 <= n <= 30:
        raise ValueError(f"Could not read the article number {raw!r}.")
    return _to_roman(n)


def _part(text: str) -> str:
    """'-a' style suffixes upper-cased with spaces removed: '436 - a' -> '436-A'."""
    return re.sub(r"\s+", "", text).upper()


def _rest(text: str) -> str:
    rest = text.strip().strip(".,;").strip()
    if not _REST_RE.match(rest):
        raise ValueError("Could not read that citation. Try one like § 205-7 or 30-A M.R.S. § 4452.")
    return rest


@dataclass(frozen=True)
class Citation:
    """A citation normalized to the form the index stores in its `citation` field."""

    kind: str  # section, charter, chapter, ordinance, statute, rule
    citation: str  # e.g. "§ 205-7"; for a chapter, "Chapter 205"
    subsection: str = ""  # what followed the section number, e.g. "K(3)"
    chapter: str = ""  # chapter lookups only

    def odata(self) -> str:
        if self.kind == "chapter":
            return f"chapter_number eq {odata_str(self.chapter)} and node_type eq 'chapter'"
        return f"citation eq {odata_str(self.citation)}"

    def parents(self) -> list[Citation]:
        """Broader city sections to try when this one is not indexed: § 275-4.9.1.2 -> § 275-4.9.1 -> § 275-4.9.
        For a renumbered rule, the current number: 16-642 CMR ch. 3 -> 08-003 CMR ch. 4."""
        if self.kind == "rule":
            m = re.match(r"^(\d{2}-\d{3}) CMR ch\. (\d+)$", self.citation)
            new = _RENUMBERED.get((m.group(1), int(m.group(2)))) if m else None
            return [Citation("rule", new, self.subsection)] if new else []
        if self.kind != "section":
            return []
        out, num = [], self.citation
        while num.count(".") >= 2:
            num = num.rsplit(".", 1)[0]
            out.append(Citation("section", num, self.subsection))
        return out


def normalize_citation(raw: str) -> Citation:
    """Read a typed citation ('205-7', 'sec. 205-7', '§ 205-7A', '275-4.27K(3)',
    'Charter Art. IV, § 9', '30-A M.R.S. § 4452', '30-A §4452') into the indexed form.

    A subsection is kept apart in `subsection`; the lookup returns the whole
    section. Raises ValueError with a message for the user.
    """
    s = unicodedata.normalize("NFKC", raw or "")
    s = s.replace("§", "§").replace("–", "-").replace("—", "-").replace("‑", "-")
    s = re.sub(r"\s+", " ", s).strip().strip(",;:").strip()
    if not s:
        raise ValueError("Enter a citation, like § 205-7.")
    if len(s) > 80:
        raise ValueError("That citation is too long. Enter one section, like § 205-7.")

    if m := _CMR_RE.match(s):
        a, b, ch, rest = m.groups()
        return Citation("rule", f"{a}-{b} CMR ch. {int(ch)}", _rest(rest))
    if m := _COURT_RULE_RE.match(s):
        num, rest = m.groups()
        return Citation("rule", f"M.R. Civ. P. {num.upper()}", _rest(rest))
    if m := (_MRS_RE.match(s) or _TITLE_SEC_RE.match(s)):
        title, sec, rest = m.groups()
        return Citation("statute", f"{_part(title)} M.R.S. § {_part(sec)}", _rest(rest))
    if m := (_CHARTER_RE.match(s) or _ARTICLE_RE.match(s)):
        art, sec, rest = m.groups()
        return Citation("charter", f"Charter Art. {_article(art)}, § {int(sec)}", _rest(rest))
    if _CHARTER_ONLY_RE.match(s):
        raise ValueError("Name a Charter article and section, like Charter Art. IV, § 9.")
    if m := _ORD_RE.match(s):
        a, b, rest = m.groups()
        return Citation("ordinance", f"Ord. No. {int(a)}-{b}", _rest(rest))
    if m := _CHAPTER_RE.match(s):
        ch = m.group(1).upper()
        ch = ch if ch == "C" else str(int(ch))
        return Citation("chapter", f"Chapter {ch}", chapter=ch)

    city = _SEC_PREFIX_RE.sub("", _CITY_PREFIX_RE.sub("", s, count=1), count=1)
    if m := _CITY_RE.match(city):
        ch, num, rest = m.groups()
        r = _CITY_REST_RE.match(rest)
        if not r:
            raise ValueError("Could not read that citation. Enter one section, like § 205-7 or § 275-4.27K(3).")
        ch = ch.upper() if not ch.isdigit() else str(int(ch))
        num = ".".join(str(int(p)) for p in num.split("."))
        letter, parens = r.groups()
        parens = re.sub(r"\s+", "", parens or "")
        if not letter and (pm := re.match(r"^\(([a-z])\)", parens, re.I)):
            # "(A)(1)" names subsection A, written "A(1)" in the code.
            letter, parens = pm.group(1), parens[pm.end():]
        sub =((letter or "").upper() + re.sub(r"\s+", "", parens or "")).strip()
        return Citation("section", f"§ {ch}-{num}", sub)
    raise ValueError("Could not read that citation. Try one like § 205-7, Charter Art. IV, § 9 or 30-A M.R.S. § 4452.")


def _natural(text: str | None) -> list:
    return [(0, int(p), "") if p.isdigit() else (1, 0, p) for p in re.split(r"(\d+)", text or "") if p]


def _chunk_view(d: dict) -> dict:
    return {
        "id": d.get("id"),
        "chunk_index": d.get("chunk_index"),
        "page_start": d.get("page_start"),
        "page_end": d.get("page_end"),
        "text": source_text(d),
    }


async def chapter_sections(chapter: str, staff: bool = False) -> list[dict]:
    """The chapter's sections in code order: [{citation, title}]."""
    rows = await lookup(
        f"chapter_number eq {odata_str(chapter)} and node_type eq 'section' and chunk_index eq 0",
        top=1000,
        select="citation,title,section_number,section_title,source_type",
    )
    rows = [r for r in rows if staff or r.get("source_type") not in STAFF_ONLY_TYPES]
    rows.sort(key=lambda r: _natural(r.get("section_number") or r.get("citation")))
    return [{"citation": r.get("citation"), "title": r.get("section_title") or r.get("title")} for r in rows]


async def lookup_citation(raw: str, staff: bool = False) -> tuple[Citation, dict | None]:
    """Every chunk of the cited section, in order, by a filter-only query.

    Returns (normalized citation, result or None when the index has no such
    section). A city section that is not indexed falls back to its parent
    section (§ 275-4.9.1.2 to § 275-4.9.1 to § 275-4.9).
    """
    cite = normalize_citation(raw)
    found, rows = cite, []
    for c in [cite, *cite.parents()]:
        rows = await lookup(c.odata(), top=LOOKUP_TOP, order_by="chunk_index", select=LOOKUP_SELECT)
        rows = [r for r in rows if staff or r.get("source_type") not in STAFF_ONLY_TYPES]
        if rows:
            found = c
            break
    if not rows:
        return cite, None
    rows.sort(key=lambda r: (r.get("chunk_index") or 0, r.get("id") or ""))
    first = rows[0]
    chunks = [_chunk_view(r) for r in rows]
    pages = [p for r in rows for p in (r.get("page_start"), r.get("page_end")) if p]
    result = {
        "query": raw,
        "kind": found.kind,
        "requested": cite.citation,
        "citation": first.get("citation") or found.citation,
        "subsection": cite.subsection,
        "parent": found is not cite,
        "title": first.get("title"),
        "breadcrumb": first.get("breadcrumb"),
        "url": first.get("url"),
        "open_url": open_url(first),
        "source_type": first.get("source_type"),
        "label": SOURCE_LABELS.get(first.get("source_type")),
        "chapter_number": first.get("chapter_number"),
        "chapter_title": first.get("chapter_title"),
        "legislation_through": first.get("legislation_through"),
        "page_start": min(pages) if pages else None,
        "page_end": max(pages) if pages else None,
        "chunk_count": len(chunks),
        "chunks": chunks,
        "text": "\n\n".join(c["text"] for c in chunks if c["text"]),
    }
    if found.kind == "chapter":
        result["sections"] = await chapter_sections(found.chapter, staff)
    return cite, result


# ---------------------------------------------------------------- facets for the desk filters

# Short names for the filter chips.
SOURCE_TYPE_NAMES = {
    "code": "City Code",
    "attachment": "Code attachments",
    "new_law": "New laws",
    "city_form": "City forms",
    "state_statute": "Maine statutes",
    "state_rule": "Maine rules",
    "state_guidance": "State manuals",
    "model_code_ref": "Model codes",
    "staff_note": "Staff notes",
}
FACETS_TTL = 600.0
_facet_cache: dict[bool, tuple[float, dict]] = {}


def _chapter_key(value: str) -> tuple:
    if value == "C":
        return (0, 0, value)
    return (1, int(value), value) if value.isdigit() else (2, 0, value)


async def code_edition() -> str | None:
    """The eCode360 'legislation through' date of the indexed City Code."""
    rows = await lookup("source_type eq 'code'", top=1, select="legislation_through")
    return rows[0].get("legislation_through") if rows else None


async def facet_summary(staff: bool = False) -> dict:
    """Chapters (number, title, chunk count), source types and the code edition, cached for 10 minutes."""
    hit = _facet_cache.get(staff)
    if hit and time.monotonic() - hit[0] < FACETS_TTL:
        return hit[1]
    f = await facets(["chapter_number", "source_type"])
    heads = await lookup("node_type eq 'chapter'", top=500, select="chapter_number,chapter_title")
    titles = {h["chapter_number"]: h.get("chapter_title") for h in heads if h.get("chapter_number")}
    values = [str(x["value"]) for x in f.get("chapter_number", []) if x.get("value") not in (None, "")]
    missing = [v for v in values if not titles.get(v)][:60]
    if missing:
        found = await asyncio.gather(
            *(lookup(f"chapter_number eq {odata_str(v)}", top=1, select="chapter_number,chapter_title") for v in missing)
        )
        for v, rows in zip(missing, found):
            if rows and rows[0].get("chapter_title"):
                titles[v] = rows[0]["chapter_title"]
    counts = {str(x["value"]): x.get("count") for x in f.get("chapter_number", [])}
    chapters = [
        {"value": v, "title": titles.get(v) or "", "count": counts.get(v)} for v in sorted(values, key=_chapter_key)
    ]
    type_counts = {x["value"]: x.get("count") for x in f.get("source_type", [])}
    types = [
        {"value": t, "name": SOURCE_TYPE_NAMES[t], "label": SOURCE_LABELS.get(t), "count": type_counts[t]}
        for t in SOURCE_TYPES
        if t in type_counts and (staff or t not in STAFF_ONLY_TYPES)
    ]
    out = {"chapters": chapters, "source_types": types, "legislation_through": await code_edition()}
    _facet_cache[staff] = (time.monotonic(), out)
    return out


def clear_facet_cache() -> None:
    _facet_cache.clear()

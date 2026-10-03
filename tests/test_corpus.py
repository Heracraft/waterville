"""Corpus: new source kinds (city_form, court_rule, staff_note), heading breadcrumbs,
content hashes and change alerts. No network: fetches go to an in-memory fake."""

from __future__ import annotations

import asyncio
import io
import json
import zipfile

import pymupdf
import pytest

from app import search, store
from ecode import azure, changes, state
from ecode.export import Exporter, content_hash
from ecode.headings import Trail, docx_trail_blocks, pdf_page_blocks, title_case


class FakeFetcher:
    def __init__(self, pages: dict[str, bytes | str]):
        self.pages = pages
        self.calls: list[str] = []

    def get(self, url: str, binary: bool = False) -> bytes:
        self.calls.append(url)
        if url not in self.pages:
            raise RuntimeError(f"no fixture for {url}")
        v = self.pages[url]
        return v.encode() if isinstance(v, str) else v

    def text(self, url: str) -> str:
        return self.get(url).decode()


def make_pdf(*pages: str) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        page.insert_textbox(pymupdf.Rect(72, 72, 540, 760), text, fontsize=10)
    return doc.tobytes()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def para(text: str, style: str = "", bold: bool = False, numbered: bool = False) -> str:
    ppr = ""
    if style or numbered:
        num = '<w:numPr><w:ilvl w:val="0"/><w:numId w:val="14"/></w:numPr>' if numbered else ""
        st = f'<w:pStyle w:val="{style}"/>' if style else ""
        ppr = f"<w:pPr>{st}{num}</w:pPr>"
    rpr = "<w:rPr><w:b/></w:rPr>" if bold else ""
    return f"<w:p>{ppr}<w:r>{rpr}<w:t>{text}</w:t></w:r></w:p>"


def make_docx(*paras: str) -> bytes:
    xml = f"<?xml version='1.0' encoding='UTF-8'?><w:document {W}><w:body>{''.join(paras)}</w:body></w:document>"
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", xml)
    return buf.getvalue()


STATUTE_HTML = """<html><body>
<div class="heading_structure"><div class="toc">Title 17: CRIMES</div><div class="toc">Chapter 91: NUISANCES</div>
<div class="toc">Subchapter 4: DANGEROUS BUILDINGS</div></div>
<div class="MRSSection"><h3 class="heading_section">&#167;2852. Appeal; hearing</h3>
<div class="mrs-text">Any person aggrieved by an order may appeal to the Superior Court.<span class="bhistory">[PL 1987, c. 1 (NEW).]</span></div>
</div><div class="qhistory_list">SECTION HISTORY PL 1987, c. 1 (NEW).</div></body></html>"""

LISTING_URL = "https://waterville-me.gov/225/Building-Permit-Applications"
LISTING_HTML = """<html><body><nav><a href="/DocumentCenter/View/1/Nav">nav</a></nav>
<div id="moduleContent"><h1>Building Permit Applications</h1>
<a href="/DocumentCenter/View/1336/Building-Permit-Application-PDF">Building Permit Application (PDF)</a>
<a href="/DocumentCenter/View/9999/Fence-Permit-Application-PDF">Fence Permit Application (PDF)</a>
<a href="/225/Other">not a document</a></div></body></html>"""
FORM_URL = "https://www.waterville-me.gov/DocumentCenter/View/1336/Building-Permit-Application-PDF"
NEW_FORM_URL = "https://waterville-me.gov/DocumentCenter/View/9999/Fence-Permit-Application-PDF"
GONE_FORM_URL = "https://www.waterville-me.gov/DocumentCenter/View/248/Sign-Permit-Application-PDF"


@pytest.fixture
def exporter(tmp_path):
    def build(pages):
        ex = Exporter("WA3904", tmp_path / "out", FakeFetcher(pages))
        ex.customer = {"name": state.CITY, "legislation_through": None}
        return ex

    return build


# ------------------------------------------------------------------ inventory


def test_inventory_has_new_sources():
    sources = state.load_sources()
    ids = [s["id"] for s in sources]
    assert len(ids) == len(set(ids))
    for want in [
        "mrs-30a-2691", "mrs-30a-4103", "mrs-30a-4353", "mrs-30a-4453",
        "mrs-17-2851", "mrs-17-2852", "mrs-17-2853", "mrs-17-2856", "mrs-17-2857", "mrs-17-2858", "mrs-17-2859",
        "cmr-08-003-ch1", "cmr-08-003-ch8", "mr-civ-p-80b", "mr-civ-p-80e", "mr-civ-p-80k",
        "waterville-form-building-permit", "waterville-form-life-safety-review", "waterville-permit-applications-page",
    ]:
        assert want in ids, want
    # Renumbered rules stay in the file for the record but are not ingested.
    assert not any(i.startswith("cmr-16-642") for i in ids)
    # Repealed dangerous-building sections are not listed.
    assert "mrs-17-2854" not in ids and "mrs-17-2855" not in ids
    by = {s["id"]: s for s in sources}
    assert by["mrs-17-2857"]["url"] == "https://legislature.maine.gov/statutes/17/title17sec2857.html"
    assert by["mrs-17-2857"]["citation"] == "17 M.R.S. § 2857"
    for s in sources:
        assert s["kind"] in state.SOURCE_TYPES and s["kind"] in state.HEADER, s["id"]
        assert s["url"].startswith("https://"), s["id"]
    assert state.SOURCE_TYPES["city_form"] == "city_form"
    assert state.SOURCE_TYPES["court_rule"] == "state_rule"
    assert state.HEADER["city_form"] == "City of Waterville, ME forms"
    # Every source_type the exporter writes is one the app knows how to search.
    assert set(state.SOURCE_TYPES.values()) <= set(search.SOURCE_TYPES)
    assert "city_form" in search.LOCAL_TYPES


def test_model_code_stubs_use_current_rule_numbers():
    stubs = [s for s in state.load_sources() if s["tier"] == "reference"]
    text = " ".join(s["summary"] for s in stubs)
    assert "08-003 CMR ch. 6" in text
    # Old numbers appear only next to the new ones, as "(formerly ...)".
    assert text.count("16-642") == text.count("formerly 16-642")


def test_staff_notes_are_well_formed():
    notes = state.load_staff_notes()
    assert {n["id"] for n in notes} >= {
        "rule-renumbering-08-003", "city-page-code-editions", "penalty-tiers-4452-3", "nov-appealability-2691-4",
    }
    for n in notes:
        assert n["sources"] and all(u.startswith("https://") for u in n["sources"])
        assert n["body"].strip() and n["title"].strip()
        assert "—" not in n["body"] + n["title"], n["id"]  # no em dashes
        assert n.get("status", "draft") in ("draft", "reviewed")


def test_staff_note_validation(tmp_path):
    p = tmp_path / "notes.toml"
    p.write_text('[[note]]\nid = "x"\ntitle = "T"\nbody = "B"\nchecked = "2026-10-03"\nsources = ["http://insecure"]\n')
    with pytest.raises(ValueError, match="https"):
        state.load_staff_notes(p)
    p.write_text('[[note]]\nid = "x"\ntitle = "T"\nbody = "B"\nsources = ["https://a"]\n')
    with pytest.raises(ValueError, match="checked"):
        state.load_staff_notes(p)
    p.write_text('[[note]]\nid = "x"\ntitle = "T"\nbody = "B"\nchecked = "d"\nsources = ["https://a"]\nfoo = 1\n')
    with pytest.raises(ValueError, match="unknown"):
        state.load_staff_notes(p)
    assert state.load_staff_notes(tmp_path / "missing.toml") == []


# ------------------------------------------------------------------ parsing new sources


def test_city_form_listing_and_pdf(exporter, caplog):
    ex = exporter(
        {
            LISTING_URL: LISTING_HTML,
            FORM_URL: make_pdf("APPLICATION FOR BUILDING PERMIT\n\nMinimum of three inspections required."),
            NEW_FORM_URL: make_pdf("FENCE PERMIT APPLICATION\n\nHeight of fence."),
        }
    )
    sources = [
        {"id": "listing", "title": "page", "url": LISTING_URL, "kind": "city_form", "tier": "listing"},
        {"id": "waterville-form-building-permit", "title": "City of Waterville Application for Building Permit",
         "citation": "Waterville form: Building Permit Application", "url": FORM_URL, "listing": LISTING_URL,
         "kind": "city_form", "tier": "ingest"},
        {"id": "waterville-form-sign-permit", "title": "Sign", "citation": "Waterville form: Sign", "url": GONE_FORM_URL,
         "listing": LISTING_URL, "kind": "city_form", "tier": "ingest", "optional": True},
    ]
    with caplog.at_level("WARNING"):
        docs = state.StateExporter(ex).export(sources, notes=[])
    # The known form is not ingested twice; the new one is added; the missing one is skipped with a warning.
    assert [d.doc_id for d in docs] == ["ext-waterville-form-building-permit", "ext-waterville-form-9999"]
    assert "new form on" in caplog.text and "no longer linked" in caplog.text and "skipped" in caplog.text
    form, new = docs
    c = form.chunks[0]
    assert c["source_type"] == "city_form" and c["node_type"] == "city_form"
    assert c["municipality"] == "City of Waterville, ME"
    assert c["citation"] == "Waterville form: Building Permit Application"
    assert c["content"].startswith("City of Waterville, ME forms\nCity of Waterville Application for Building Permit, page 1")
    assert "three inspections" in c["content"]
    assert new.chunks[0]["citation"] == "Waterville form: Fence Permit Application"
    assert (ex.out / "pdf/city-forms/waterville-form-building-permit.pdf").exists()
    assert form.markdown_path.startswith("markdown/city-forms/")


def test_city_form_links_reads_main_content_only():
    links = state.city_form_links(LISTING_HTML, LISTING_URL)
    assert links == [
        ("https://waterville-me.gov/DocumentCenter/View/1336/Building-Permit-Application-PDF", "Building Permit Application (PDF)"),
        ("https://waterville-me.gov/DocumentCenter/View/9999/Fence-Permit-Application-PDF", "Fence Permit Application (PDF)"),
    ]


def test_statute_range_section(exporter):
    url = "https://legislature.maine.gov/statutes/17/title17sec2852.html"
    ex = exporter({url: STATUTE_HTML})
    src = next(s for s in state.load_sources() if s["id"] == "mrs-17-2852")
    (doc,) = state.StateExporter(ex).export([src], notes=[])
    c = doc.chunks[0]
    assert doc.title == "17 M.R.S. § 2852. Appeal; hearing"
    assert c["breadcrumb"] == "Title 17 > Chapter 91: Nuisances > Subchapter 4: Dangerous Buildings > 17 M.R.S. § 2852. Appeal; hearing"
    assert c["source_type"] == "state_statute" and c["citation"] == "17 M.R.S. § 2852"
    assert "appeal to the Superior Court" in c["content"] and "[PL 1987" not in c["content"]


def test_court_rule_pdf_has_rule_header(exporter):
    url = "https://www.courts.maine.gov/rules/text/MRCivPPlus/mr_civ_p_80K_plus_2023-11-15.pdf"
    ex = exporter({url: make_pdf("RULE 80K. LAND USE VIOLATIONS\n\n(a) Applicability. These rules apply.")})
    src = next(s for s in state.load_sources() if s["id"] == "mr-civ-p-80k")
    (doc,) = state.StateExporter(ex).export([src], notes=[])
    c = doc.chunks[0]
    assert c["source_type"] == "state_rule" and c["node_type"] == "court_rule"
    assert c["citation"] == "M.R. Civ. P. 80K"
    assert c["content"].startswith("Maine Rules of Civil Procedure\nM.R. Civ. P. 80K. Land Use Violations (with advisory notes), page 1")


def test_staff_note_chunk(exporter):
    ex = exporter({})
    note = {
        "id": "demo", "title": "Demo note", "body": "Quote the statute.", "checked": "2026-10-03",
        "sources": ["https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html", "https://ecode360.com/1"],
    }
    (doc,) = state.StateExporter(ex).export([], notes=[note])
    c = doc.chunks[0]
    assert c["id"] == "ext-staff-note-demo-0" and c["source_type"] == "staff_note"
    assert c["citation"] == "Staff note: Demo note" and c["url"] == note["sources"][0]
    assert c["breadcrumb"] == "Staff notes > Demo note"
    assert c["content"].startswith(state.HEADER["staff_note"] + "\nStaff notes > Demo note\n\nQuote the statute.")
    assert "- https://ecode360.com/1" in c["content"]
    assert "Not yet reviewed by the Code Enforcement Officer." in c["content"]


def test_cli_notes_only_writes_valid_chunks(tmp_path, capsys):
    out = tmp_path / "out"
    state.main(["--out", str(out), "--cache", str(tmp_path / "cache"), "--notes-only"])
    rows = [json.loads(line) for line in (out / "chunks.jsonl").read_text().splitlines()]
    assert rows and {r["source_type"] for r in rows} == {"staff_note"}
    assert all(r["content_hash"] == content_hash(r) for r in rows)
    index = azure.index_definition("test", 3072, "text-embedding-3-large", None, None)
    assert azure.validate(rows, index) == []


# ------------------------------------------------------------------ headings (open item 1)


def test_title_case_keeps_acronyms_and_numbers():
    assert title_case("WHAT IS AN 80K ACTION?") == "What Is an 80K Action?"
    assert title_case("C. THE PURPOSES OF ZONING") == "C. The Purposes of Zoning"
    assert title_case("APPENDIX A: MUBEC AND THE CEO") == "Appendix A: MUBEC and the CEO"
    assert title_case("Mixed Case Stays") == "Mixed Case Stays"


def test_pdf_heading_trail():
    pages = [
        "# **COURT RULE 80K MANUAL**\n\n### **<u>CHAPTER TWO</u>**\n\n### **CERTIFICATION PROGRAM**\n\n"
        "### **_A. Required Certification._**\n\nA municipality may not employ an uncertified officer.",
        "### **2. Whom to Name**\n\nName the owner.\n\n### **CHAPTER THREE WHEN TO PROCEED**\n\nFollow the ordinance.",
    ]
    out = pdf_page_blocks(pages, doc_title="Court Rule 80K Manual")
    paths = [p for page in out for p, _ in page]
    assert ("Chapter Two: Certification Program", "A. Required Certification") in paths
    assert ("Chapter Two: Certification Program", "A. Required Certification", "2. Whom to Name") in paths
    assert paths[-1] == ("Chapter Three: When to Proceed",)
    # The manual's own title is not a heading level.
    assert all("Court Rule 80K Manual" not in " ".join(p) for p in paths)


def test_roman_numerals_versus_letter_i():
    t = Trail()
    t.pdf_heading("I. Understanding Zoning")
    t.pdf_heading("A. WHAT ZONING IS")
    assert t.path() == ("I. Understanding Zoning", "A. What Zoning Is")
    t.pdf_heading("II. Planning")
    assert t.path() == ("II. Planning",)
    for letter in "ABCDEFGH":
        t.pdf_heading(f"{letter}. Item {letter}")
    t.pdf_heading("I. Item I")  # follows H., so a letter
    assert t.path() == ("II. Planning", "I. Item I")


def test_chapter_then_all_caps_subheads():
    t = Trail()
    t.pdf_heading("CHAPTER 1 - PURPOSE")
    t.pdf_heading("GENERAL")
    assert t.path() == ("Chapter 1: Purpose", "General")
    t.pdf_heading("CHAPTER 2 - SOIL PROFILE TERMINOLOGY")
    assert t.path() == ("Chapter 2: Soil Profile Terminology",)


def test_path_keeps_outer_levels_and_innermost():
    t = Trail()
    t.set(1, "Ch")
    t.set(2, "A")
    t.set(3, "1")
    t.set(4, "(a)")
    assert t.path() == ("Ch", "A", "(a)")


def test_docx_rules_styles_give_breadcrumbs():
    data = make_docx(
        para("Chapter 1000: GUIDELINES FOR MUNICIPAL SHORELAND ZONING ORDINANCES", "RulesChapterTitle", bold=True),
        para("1. Purposes 1", "RulesTableofContents"),
        para("1. Purposes. The purposes of this Ordinance are listed.", bold=True),
        para("Authority. This Ordinance has been prepared under Title 38.", "RulesSection", bold=True, numbered=True),
        para("12. Non-conformance", "RulesSection", bold=True),
        para("C. Non-conforming Structures", "RulesSub-section", bold=True),
        para("(1) Expansions. All new principal structures must meet the setback.", bold=True),
        para("(a) Expansion of any portion of a structure is limited.", "RulesParagraph"),
        '<w:tbl><w:tr><w:tc>' + para("1. Non-intensive recreational uses", bold=True) + "</w:tc></w:tr></w:tbl>",
    )
    items = docx_trail_blocks(data)
    texts = [b.text for _, b in items]
    assert "1. Purposes 1" not in texts  # table of contents dropped
    assert texts[0].startswith("## Chapter 1000")
    by = {b.text[:12]: p for p, b in items}
    assert by["1. Purposes."] == ("1. Purposes",)
    assert by["Authority. T"] == ("Authority",)
    assert by["(a) Expansio"] == ("12. Non-conformance", "C. Non-conforming Structures", "(1) Expansions")
    # A bold numbered table cell is not a section heading.
    assert by["1. Non-inten"] == ("12. Non-conformance", "C. Non-conforming Structures", "(1) Expansions")


def test_docx_mubec_sections_and_revisions():
    data = make_docx(
        para("Chapter 4: COMMERCIAL BUILDING CODE OF MAINE", bold=True),
        para("SECTION 3. DEFINITIONS", bold=True),
        para("1. IBC. “IBC” means the 2021 International Building Code.", bold=True),
        para("SECTION 5. REVISIONS TO THE IBC", bold=True),
        para("1. Section 101.1"),
        para("Insert “State of Maine” in its place.", bold=True),
    )
    items = docx_trail_blocks(data)

    def path_of(start):
        return next(p for p, b in items if b.text.startswith(start))

    assert path_of("1. IBC.") == ("Section 3. Definitions",)
    assert path_of("Insert") == ("Section 5. Revisions to the IBC", "Section 101.1")


def test_docx_export_uses_heading_breadcrumbs(exporter):
    url = "https://www.maine.gov/sos/sites/maine.gov.sos/files/content/assets/096c1000.docx"
    data = make_docx(
        para("Chapter 1000: GUIDELINES", "RulesChapterTitle", bold=True),
        para("12. Non-conformance", "RulesSection", bold=True),
        *[para(f"Paragraph {i}. " + "Setback text applies here. " * 30, "RulesParagraph") for i in range(6)],
        para("13. Establishment of Districts", "RulesSection", bold=True),
        *[para(f"District {i}. " + "District text applies here. " * 30, "RulesParagraph") for i in range(6)],
    )
    ex = exporter({url: data})
    src = {"id": "cmr-06-096-ch1000", "title": "06-096 CMR ch. 1000. Guidelines", "url": url, "kind": "rule", "tier": "ingest"}
    (doc,) = state.StateExporter(ex).export([src], notes=[])
    crumbs = [c["breadcrumb"] for c in doc.chunks]
    assert "06-096 CMR ch. 1000. Guidelines > 12. Non-conformance" in crumbs
    assert "06-096 CMR ch. 1000. Guidelines > 13. Establishment of Districts" in crumbs
    for c in doc.chunks:
        assert c["content"].split("\n")[1].startswith(c["breadcrumb"])
        if c["breadcrumb"].endswith("13. Establishment of Districts"):
            assert "Paragraph" not in c["content"]  # chunks do not straddle sections


def test_merge_pieces_rules():
    small = "Short heading."
    big = "Body text that goes on. " * 40
    pieces = [
        (small, 1, ("Chapter Two",)),
        (big, 1, ("Chapter Two: Certification", "A. Required")),
        (big, 2, ("Chapter Two: Certification", "B. Who")),
        (big, 3, ("Chapter Three",)),
    ]
    merged = state.merge_pieces(pieces)
    # The lone heading joins the next piece and takes its headings; A and B share the chapter.
    assert merged[0][3] == ("Chapter Two: Certification",)
    assert merged[0][1:3] == (1, 2)
    assert merged[-1][3] == ("Chapter Three",)


# ------------------------------------------------------------------ change detection


def _chunk(cid, citation, content, **kw):
    c = {"id": cid, "citation": citation, "content": content, "source_type": "code", "title": citation,
         "url": f"https://ecode360.com/{cid}", "legislation_through": "09-01-2026", **kw}
    c["content_hash"] = content_hash(c)
    return c


def _old(chunks, **override):
    return [{**{k: c.get(k) for k in changes.INDEX_FIELDS}, "legislation_through": "08-05-2026", **override} for c in chunks]


def test_content_hash_is_stable_and_content_only():
    a = _chunk("code-1-0", "§ 1-1", "text")
    b = {**a, "crawled_at": "2030-01-01T00:00:00Z", "legislation_through": "01-01-2030"}
    assert content_hash(a) == content_hash(b) and len(content_hash(a)) == 32
    assert content_hash({**a, "content": "text!"}) != content_hash(a)


def test_diff_changed_added_removed():
    old_chunks = [
        _chunk("code-1-0", "§ 1-1", "same"),
        _chunk("code-2-0", "§ 2-1", "old text"),
        _chunk("code-3-0", "§ 3-1", "gone"),
        _chunk("code-4-0", "§ 4-1", "part one"),
        _chunk("ext-mrs-1-0", "30-A M.R.S. § 1", "state", source_type="state_statute"),
    ]
    new_chunks = [
        _chunk("code-1-0", "§ 1-1", "same"),
        _chunk("code-2-0", "§ 2-1", "new text"),
        _chunk("code-4-0", "§ 4-1", "part one"),
        _chunk("code-4-1", "§ 4-1", "part two"),  # a section that grew a chunk
        _chunk("code-5-0", "§ 5-1", "brand new"),
        _chunk("ext-mrs-1-0", "30-A M.R.S. § 1", "state changed", source_type="state_statute"),
    ]
    result = changes.diff(_old(old_chunks), new_chunks)
    assert not result["baseline"]
    got = {(c["kind"], c["citation"]) for c in result["changes"]}
    assert got == {("changed", "§ 2-1"), ("removed", "§ 3-1"), ("changed", "§ 4-1"), ("added", "§ 5-1")}
    assert result["counts"] == {"changed": 2, "added": 1, "removed": 1}
    c2 = next(c for c in result["changes"] if c["citation"] == "§ 2-1")
    assert c2["legislation_through"] == "09-01-2026" and c2["previous_legislation_through"] == "08-05-2026"


def test_diff_baseline_without_hashes():
    chunks = [_chunk("code-1-0", "§ 1-1", "a")]
    assert changes.diff([], chunks)["baseline"]
    assert changes.diff(_old(chunks, content_hash=None), [_chunk("code-1-0", "§ 1-1", "b")])["baseline"]
    # A row with an unknown hash next to known ones is not reported as changed.
    old = _old([_chunk("code-1-0", "§ 1-1", "a")], content_hash=None) + _old([_chunk("code-2-0", "§ 2-1", "b")])
    new = [_chunk("code-1-0", "§ 1-1", "a2"), _chunk("code-2-0", "§ 2-1", "b")]
    assert changes.diff(old, new)["changes"] == []


def test_record_print_and_store(staff_client, client):
    import datetime as dt

    old = _old([_chunk("code-2-0", "§ 2-1", "old"), _chunk("code-3-0", "§ 3-1", "gone")])
    new = [_chunk("code-2-0", "§ 2-1", "new", chapter_number="2", section_title="Two")]
    result = changes.diff(old, new)
    buf = io.StringIO()
    assert changes.record(result, "waterville-code-preview", 1, "print", out=buf) == "print"
    lines = [json.loads(x) for x in buf.getvalue().splitlines()]
    assert lines[0]["rk"] == "run" and lines[0]["counts"]["changed"] == 1 and lines[0]["table"] == "changes"
    assert changes.record(result, "x", 1, "none") == "none"

    when = dt.datetime(2026, 10, 3, 7, 0, tzinfo=dt.timezone.utc)
    assert changes.record(result, "waterville-code-preview", 1, "store", now=when) == "store"
    earlier = changes.diff(old, [_chunk("code-2-0", "§ 2-1", "old"), _chunk("code-3-0", "§ 3-1", "gone"),
                                 _chunk("code-9-0", "§ 9-1", "new")])
    changes.record(earlier, "waterville-code-preview", 3, "store", now=when - dt.timedelta(days=7))
    rows = asyncio.run(store.get_store().query("changes"))
    assert len(rows) == 5  # two runs plus three changes

    r = staff_client.get("/api/staff/changes")
    assert r.status_code == 200, r.text
    body = r.json()
    assert [run["run_id"] for run in body["runs"]] == ["20261003T070000Z", "20260926T070000Z"]
    assert body["last_run"]["counts"] == {"changed": 1, "added": 0, "removed": 1}
    assert [(c["kind"], c["citation"]) for c in body["changes"]] == [
        ("changed", "§ 2-1"), ("removed", "§ 3-1"), ("added", "§ 9-1")]
    first = body["changes"][0]
    assert first["section_title"] == "Two" and first["run_at"] == "2026-10-03T07:00:00Z"
    assert not any(k.startswith("_") for k in first)
    assert first["detected_at"] == "2026-10-03T07:00:00Z"
    assert first["summary"] == "Text changed between the editions of 08-05-2026 and 09-01-2026."
    assert body["changes"][1]["summary"] == "Not found in the latest crawl."

    assert [c["kind"] for c in staff_client.get("/api/staff/changes?kind=added").json()["changes"]] == ["added"]
    assert staff_client.get("/api/staff/changes?since=2026-10-01").json()["total"] == 2
    assert staff_client.get("/api/staff/changes?kind=bogus").status_code == 422
    assert staff_client.get("/api/staff/changes?since=nope").status_code == 400


def test_changes_requires_staff(client):
    assert client.get("/api/staff/changes").status_code == 401


def test_changes_cli_compares_files(tmp_path, capsys):
    old = tmp_path / "old.jsonl"
    new = tmp_path / "new.jsonl"
    old.write_text(json.dumps({k: v for k, v in _chunk("code-1-0", "§ 1-1", "a").items() if k != "content_hash"}) + "\n")
    new.write_text(json.dumps(_chunk("code-1-0", "§ 1-1", "b")) + "\n")
    changes.main(["--old", str(old), "--new", str(new), "--to", "print"])
    out = capsys.readouterr()
    assert '"kind": "changed"' in out.out and "1 changed" in out.err


class FakeResponse:
    def __init__(self, status, payload):
        self.status_code = status
        self._payload = payload
        self.text = json.dumps(payload)
        self.headers = {}

    def json(self):
        return self._payload


def test_azure_changes_command_reads_index(monkeypatch, tmp_path, capsys):
    chunks = [_chunk("code-1-0", "§ 1-1", "new text")]
    path = tmp_path / "chunks.jsonl"
    path.write_text("".join(json.dumps(c) + "\n" for c in chunks))
    old = _old([_chunk("code-1-0", "§ 1-1", "old text"), _chunk("code-2-0", "§ 2-1", "gone")])
    seen = {}

    def fake_get(url, headers=None, timeout=None):
        seen["get"] = url
        return FakeResponse(200, {"fields": [{"name": f} for f in changes.INDEX_FIELDS]})

    def fake_post(url, headers=None, json=None, timeout=None):
        seen["body"] = json
        return FakeResponse(200, {"value": [{"@search.score": 1, **r} for r in old]})

    monkeypatch.setattr(azure.requests, "get", fake_get)
    monkeypatch.setattr(azure.requests, "post", fake_post)
    monkeypatch.setenv("AZURE_SEARCH_ENDPOINT", "https://search.example")
    monkeypatch.setenv("AZURE_SEARCH_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", "test-key")
    monkeypatch.setenv("AZURE_SEARCH_INDEX", "waterville-code-preview")
    azure.main(["changes", "--chunks", str(path), "--changes-to", "print"])
    out = capsys.readouterr()
    assert seen["get"].startswith("https://search.example/indexes/waterville-code-preview?")
    assert "search.in(source_type, 'code,attachment,new_law,city_form')" == seen["body"]["filter"]
    assert "content_hash" in seen["body"]["select"]
    rows = [json.loads(x) for x in out.out.splitlines()]
    assert {(r["kind"], r.get("citation")) for r in rows[1:]} == {("changed", "§ 1-1"), ("removed", "§ 2-1")}


def test_index_rows_missing_index_and_old_schema(monkeypatch):
    monkeypatch.setattr(azure.requests, "get", lambda *a, **k: FakeResponse(404, {}))
    auth = azure.Auth.__new__(azure.Auth)
    auth.key, auth.scope, auth.cred = "k", "s", None
    assert azure.index_rows("https://s", "idx", auth) is None
    # An index built before content_hash existed: the field is not selected, and the diff is a baseline.
    monkeypatch.setattr(azure.requests, "get", lambda *a, **k: FakeResponse(200, {"fields": [{"name": "id"}, {"name": "citation"}, {"name": "source_type"}]}))
    bodies = []

    def post(url, headers=None, json=None, timeout=None):
        bodies.append(json)
        return FakeResponse(200, {"value": [{"id": "code-1-0", "citation": "§ 1-1", "source_type": "code"}]})

    monkeypatch.setattr(azure.requests, "post", post)
    rows = azure.index_rows("https://s", "idx", auth)
    assert bodies[0]["select"] == "id,citation,source_type"
    assert changes.diff(rows, [_chunk("code-1-0", "§ 1-1", "x")])["baseline"]


def test_schema_has_content_hash():
    index = azure.index_definition("t", 3072, "text-embedding-3-large", None, None)
    f = next(f for f in index["fields"] if f["name"] == "content_hash")
    assert f["type"] == "Edm.String" and f["filterable"] and not f["searchable"]
    committed = json.loads(open("azure/index.json").read())
    assert "content_hash" in {f["name"] for f in committed["fields"]}


# ------------------------------------------------------------------ search: staff notes stay staff-only


@pytest.fixture
def corpus_docs(monkeypatch):
    docs = (
        {"id": "ext-staff-note-x-0", "source_type": "staff_note", "title": "Penalty tiers note",
         "citation": "Staff note: Penalty tiers", "breadcrumb": "Staff notes > Penalty tiers",
         "content": "Waterville code office staff note\nStaff notes > Penalty tiers\n\npenalty tiers resource protection",
         "url": "https://legislature.maine.gov/statutes/30-A/title30-Asec4452.html"},
        {"id": "ext-waterville-form-x-0", "source_type": "city_form", "title": "Building permit application",
         "citation": "Waterville form: Building Permit Application", "breadcrumb": "Building permit application",
         "content": "City of Waterville, ME forms\nBuilding permit application, page 1\n\npenalty tiers permit form",
         "url": "https://www.waterville-me.gov/DocumentCenter/View/1336"},
    )
    monkeypatch.setattr(search, "_fixture_docs", lambda: docs)
    return docs


def test_public_search_never_returns_staff_notes(corpus_docs):
    assert search.PUBLIC_EXCLUDE_TYPES == ("staff_note",)
    public = asyncio.run(search.search("penalty tiers", mode="public"))
    staff = asyncio.run(search.search("penalty tiers", mode="staff"))
    assert "staff_note" not in {d["source_type"] for d in public}
    assert "city_form" in {d["source_type"] for d in public}
    assert {"staff_note", "city_form"} <= {d["source_type"] for d in staff}
    with pytest.raises(ValueError):
        search.validate_filters({"source_types": ["staff_note"]}, "public")
    text, meta = search.format_sources([d for d in staff if d["source_type"] == "city_form"])
    assert "(City form)" in text and meta[0]["text"].startswith("penalty tiers permit form")

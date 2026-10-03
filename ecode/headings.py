"""Heading trails for state manuals and rules (open item 1 in docs/open-items.md).

A chunk from a 200-page manual used to carry only "Manual (2017), page 24" in
its header and breadcrumb, so the semantic ranker could not tell what it was
about. These helpers track the most recent heading at each level while the
exporter walks a document, so every chunk can say where it sits:

    Court Rule 80K Manual (2017) > Chapter Four: How to Prepare the Land Use
    Citation and Complaint > B. Required Attachments, page 24

pymupdf4llm gives almost every heading in the MOCA manuals the same Markdown
level, so PDF levels come from the heading text (chapter words, lettered and
numbered headings), not from the number of '#'. Word rules give paragraph
styles instead (RulesChapterTitle, RulesSection, RulesSub-section, Heading1, H1).
"""

from __future__ import annotations

import io
import re
import zipfile
from dataclasses import dataclass, field

from bs4 import BeautifulSoup

from .parse import Block

MAX_LEVELS = 3
MAX_HEADING_CHARS = 90

# Words kept upper case when an ALL CAPS heading is put in title case.
ACRONYMS = {
    "ADA", "ASHRAE", "ASTM", "BOA", "CEO", "CEOS", "CMR", "CMP", "DEP", "DECD", "DHHS", "FAQ", "FEMA",
    "HHE", "IBC", "ICC", "IEBC", "IECC", "IMC", "IRC", "LPI", "LUPC", "MDOT", "MOCA", "MRS", "MRSA",
    "MUBEC", "NEC", "NFPA", "NRPA", "SPO", "TPI", "TRO", "US", "USA", "ZBA", "II", "III", "IV", "VI",
    "VII", "VIII", "IX", "XI", "XII", "BMP", "BMPS", "LURC", "NPDES", "EPA", "HUD", "DOT", "MSZA", "PL", "LD",
}
SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to", "with", "from"}

LABEL_ONLY = re.compile(r"^(chapter|part|article|appendix|unit|module)\s+[\w.-]+$", re.I)
NUMBER_WORDS = (
    "one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
    "seventeen|eighteen|nineteen|twenty"
)
# "Chapter 3", "PART IV", "Article B", "CHAPTER FOURTEEN", "Appendices"; not "Part of the problem".
LEVEL1 = re.compile(
    rf"^(?:(?:chapter|part|article|appendix|unit|module)\s+(?:\d|[ivxlc]+\b|[a-z]\b|(?:{NUMBER_WORDS})\b)|appendix\b|appendices\b)",
    re.I,
)
# "CHAPTER 3: TITLE", "Chapter V. Title", "CHAPTER 13-APPROVED PRODUCTS" (label 13), "Chapter 3-A Title" (label 3-A).
LABEL_TITLE = re.compile(
    r"^((?:chapter|part|article|appendix|unit|module)\s+[A-Za-z0-9]+(?:\.\d+)*(?:-[A-Z0-9]{1,2}\b)?)\.?\s*[:\-–—]?\s*(\S.*)$",
    re.I,
)
ROMAN = re.compile(r"^(?:section\s+)?([IVX]{1,5})\.\s+\S", re.I)
LETTERED = re.compile(r"^([A-Z])\.\s+\S")
NUMBERED = re.compile(r"^\d{1,3}(?:\.\d{1,3})*\.?\s+\S")
PARENS = re.compile(r"^\(\w{1,4}\)\s+\S")
PAGE_ONLY = re.compile(r"^(page\s+)?\d+(\s+of\s+\d+)?$", re.I)


def clean_heading(text: str) -> str:
    """Strip Markdown emphasis and HTML underline tags from a heading line."""
    t = re.sub(r"</?u>", "", text)
    t = re.sub(r"[*_`]+", "", t)
    t = t.replace(" ", " ")
    t = re.sub(r"\s+", " ", t).strip()
    t = t.strip(" :;-").strip()
    if t.endswith(".") and not re.search(r"\b(?:No|Inc|Co|al|ch|v|U\.S)\.$", t):
        t = t[:-1].rstrip()
    return t


def title_case(text: str) -> str:
    """Title case for an ALL CAPS heading, keeping acronyms and words with digits."""
    if any(c.islower() for c in text):
        return text
    out: list[str] = []
    for w in text.split():
        core = re.sub(r"[^A-Za-z]", "", w)
        start = not out or out[-1].endswith((".", ":", "-", "\u2013", "\u2014"))
        if not core or len(core) == 1 or any(c.isdigit() for c in w) or core.upper() in ACRONYMS:
            out.append(w)
        elif not start and core.lower() in SMALL:
            out.append(w.lower())
        else:
            out.append(w[:1] + w[1:].lower())
    return " ".join(out)


def usable(text: str, doc_title: str = "") -> bool:
    if len(text) < 2 or len(text) > MAX_HEADING_CHARS * 2:
        return False
    if not re.search(r"[A-Za-z]{2}", text) or PAGE_ONLY.match(text):
        return False
    if doc_title and _words(text) - FILLER <= _words(doc_title):
        return False  # "RULE 80K. LAND USE VIOLATIONS" in "M.R. Civ. P. 80K. Land Use Violations"
    return True


FILLER = {"rule", "chapter", "the", "of", "and", "a", "an", "to", "for", "in"}


def _words(text: str) -> set[str]:
    return set(re.findall(r"[a-z0-9]+", text.lower()))


def _all_caps(text: str) -> bool:
    letters = [c for c in text if c.isalpha()]
    return len(letters) >= 4 and all(c.isupper() for c in letters)


@dataclass
class Trail:
    """The most recent heading at each level; a new heading clears the deeper ones.

    PDF levels: 1 = a chapter (or part, article, appendix) or a Roman-numbered
    section, or an ALL CAPS title in a manual with no chapters; 2 = a lettered
    heading ("A. Overview"), or ALL CAPS once chapters exist; 3 = a numbered
    heading ("2. Whom to Name") or any other heading; 4 = "(a) ...".
    """

    levels: dict[int, str] = field(default_factory=dict)
    pending_label: str = ""  # "CHAPTER TWO" waiting for its title on the next heading line
    seen_chapter: bool = False
    last_letter: str = ""

    def set(self, level: int, text: str) -> None:
        for k in [k for k in self.levels if k >= level]:
            del self.levels[k]
        self.levels[level] = text[:MAX_HEADING_CHARS].rstrip()

    def path(self, max_levels: int = MAX_LEVELS, min_level: int = 1) -> tuple[str, ...]:
        """Outermost levels plus the innermost one, at most `max_levels` names."""
        p = [self.levels[k] for k in sorted(self.levels) if k >= min_level]
        if len(p) > max_levels:
            p = p[: max_levels - 1] + p[-1:]
        return tuple(p)

    def pdf_level(self, text: str) -> int:
        if LEVEL1.match(text):
            return 1
        if m := ROMAN.match(text):
            numeral = m.group(1).upper()
            # A lone "I." is a Roman numeral only before any lettered heading in
            # the current part; "V." or "X." is a letter right after "U." or "W.".
            if text[:7].lower() == "section" or len(numeral) > 1:
                return 1
            if numeral == "I" and not self.last_letter:
                return 1
            if numeral in "VX" and not (self.last_letter and ord(numeral) == ord(self.last_letter) + 1):
                return 1
        if m := LETTERED.match(text):
            return 2
        if NUMBERED.match(text):
            return 3
        if PARENS.match(text):
            return 4
        if _all_caps(text):
            return 2 if self.seen_chapter else 1
        return 3

    def pdf_heading(self, raw: str, doc_title: str = "") -> None:
        text = clean_heading(raw)
        if not usable(text, doc_title):
            return
        if self.pending_label and not LEVEL1.match(text) and _all_caps(text):
            # "CHAPTER TWO" then "CERTIFICATION PROGRAM" on the next heading line.
            self.set(1, f"{title_case(self.pending_label)}: {title_case(text)}")
            self.pending_label = ""
            return
        level = self.pdf_level(text)
        if m := LETTERED.match(text):
            if level == 2:
                self.last_letter = m.group(1)
        if level == 1:
            self.last_letter = ""
        if LEVEL1.match(text):
            self.seen_chapter = True
        self.pending_label = text if LABEL_ONLY.match(text) else ""
        if level == 1 and not self.pending_label and (m := LABEL_TITLE.match(text)):
            text = f"{title_case(m.group(1))}: {title_case(m.group(2).lstrip('-: '))}"
        self.set(level, title_case(text))


HEADING_LINE = re.compile(r"^#{1,6}\s+(.*)$")
# A table-of-contents line: dot leaders (or ellipses) then a page number.
LEADER = re.compile(r"(?:\.{4,}|…{2,}|(?:\.\s){3,})[\s.…]*\d+(?:-[A-Z])?\s*\|?\s*$", re.M)
TOC = ("Table of Contents",)


def is_toc_page(page: str) -> bool:
    return len(LEADER.findall(page)) >= 4


def pdf_page_blocks(pages: list[str], doc_title: str = "") -> list[list[tuple[tuple[str, ...], Block]]]:
    """Per page, the page's blocks with the heading trail in effect at each block.

    A heading block carries the trail that includes itself, so a chunk that
    starts with a heading is labeled with it. A table-of-contents page (lines
    ending in dot leaders and page numbers) is labeled "Table of Contents",
    and its chapter lines do not move the trail.
    """
    trail = Trail()
    out = []
    for page in pages:
        if is_toc_page(page):
            trail = Trail()
            out.append([(TOC, Block(b.strip())) for b in re.split(r"\n\s*\n", page) if b.strip()])
            continue
        items = []
        for raw in re.split(r"\n\s*\n", page):
            b = raw.strip()
            if not b:
                continue
            first = b.splitlines()[0]
            if m := HEADING_LINE.match(first):
                trail.pdf_heading(m.group(1), doc_title)
            items.append((trail.path(), Block(b)))
        out.append(items)
    return out


# ------------------------------------------------------------------ Word rules

SECTION_CAPS = re.compile(r"^SECTION\s+\d+[A-Z-]*[.:]", re.I)
NUM_TITLE = re.compile(r"^(\d{1,2})\.\s+([A-Z][^.]{0,80}?)(?:\.\s|\.?$)")
LETTER_TITLE = re.compile(r"^([A-Z])\.\s+([A-Z][^.]{0,80}?)(?:\.\s|\.?$)")
AUTO_TITLE = re.compile(r"^([A-Z][A-Za-z,'’/\- ]{1,60}?)\.(?:\s|$)")
PARA_TITLE = re.compile(r"^\((\d{1,2})\)\s+([A-Z][^.:]{1,60}?)[.:](?:\s|$)")
REVISION = re.compile(
    r"^\d{1,3}\.\s+((?:Sections?|Tables?|Chapters?|Appendix|Figure)\s+\S.{0,50}|Generally all sections)$", re.I
)


def _style(p) -> str:
    st = p.find("pStyle")
    return (st.get("w:val", st.get("val", "")) if st else "") or ""


def _text(p) -> str:
    return re.sub(r"\s+", " ", "".join(x.text if x.name == "t" else " " for x in p.find_all(["t", "tab", "br"]))).strip()


def docx_heading(style: str, text: str, bold: bool, numbered: bool, caps_sections: bool) -> tuple[int, str] | None:
    """(level, label) when a Word paragraph starts a part of the rule, else None.

    Level 1 is the chapter title, 2 a section, 3 a subsection or the model-code
    section a MUBEC chapter revises, 4 a numbered paragraph with its own title.
    """
    if "ChapterTitle" in style:
        return 1, text
    if style in ("Heading1", "H1", "Heading 1") or SECTION_CAPS.match(text):
        return 2, title_case(text)
    if style == "RulesSection" or (style == "" and bold and not caps_sections):
        if m := NUM_TITLE.match(text):
            return 2, f"{m.group(1)}. {m.group(2).strip()}"
        if style == "RulesSection" and numbered and (m := AUTO_TITLE.match(text)):
            return 2, m.group(1).strip()
    if style in ("Heading2", "H2", "Heading 2"):
        return 3, title_case(text)
    if style == "RulesSub-section":
        if m := LETTER_TITLE.match(text):
            return 3, f"{m.group(1)}. {m.group(2).strip()}"
        if numbered and (m := AUTO_TITLE.match(text)):
            return 3, m.group(1).strip()
    if style == "" and caps_sections and not bold and (m := REVISION.match(text)):
        return 3, m.group(1).strip()
    if style in ("RulesParagraph", "") and bold and (m := PARA_TITLE.match(text)):
        return 4, f"({m.group(1)}) {m.group(2).strip()}"
    return None


def docx_trail_blocks(data: bytes) -> list[tuple[tuple[str, ...], Block]]:
    """Paragraphs of a .docx rule with the heading trail (levels 2-4) in effect at each.

    Heading paragraphs are marked "## " in the text as before. The table of
    contents is dropped. Paragraphs inside tables never start a heading.
    """
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    soup = BeautifulSoup(xml, "xml")
    paras = []
    for p in soup.find_all("p"):
        style = _style(p)
        if "TableofContents" in style or "TOC" in style:
            continue
        t = _text(p)
        if t:
            paras.append((p, style, t))
    caps_sections = any(SECTION_CAPS.match(t) for _, _, t in paras)
    trail = Trail()
    out = []
    for p, style, t in paras:
        in_table = p.find_parent("tbl") is not None
        bold = p.find("b") is not None
        numbered = p.find("numPr") is not None
        head = None if in_table else docx_heading(style, t, bold, numbered, caps_sections)
        if head:
            trail.set(*head)
        if "ChapterTitle" in style or style.startswith("Heading") or style in ("H1", "H2") or "Header" in style:
            t = f"## {t}"
        out.append((trail.path(min_level=2), Block(t)))
    return out


def crumb(title: str, path: tuple[str, ...]) -> str:
    return " > ".join([title, *path])

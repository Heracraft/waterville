"""Parse eCode360 table-of-contents and print pages into a section tree.

A chapter's print page (/print/<CUST>?guid=<chapter>&children=true) holds the
full text of the chapter as a flat run of headings (h2 chapter/part/article,
h4 section) each followed by a `<div class="*_content">` body. This module turns
that into Node objects whose bodies are lists of Markdown blocks.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field

from bs4 import BeautifulSoup, NavigableString, Tag

log = logging.getLogger(__name__)

WS = re.compile(r"\s+")


def clean(text: str) -> str:
    return WS.sub(" ", text.replace("\xa0", " ")).strip()


@dataclass
class Block:
    """One Markdown paragraph, list item, definition or table.

    Tables keep their header and rows separate so a chunker can split a long
    table by rows and repeat the header in every piece.
    """

    text: str
    kind: str = "para"
    table_header: str | None = None
    table_rows: list[str] | None = None


@dataclass
class Attachment:
    title: str
    href: str
    chapter_guid: str


@dataclass
class Node:
    guid: str
    kind: str  # chapter | part | article | section
    heading: str  # "§ 275-1.1. Authority."
    number: str  # "275-1.1"
    title: str  # "Authority."
    parent: Node | None = None
    blocks: list[Block] = field(default_factory=list)
    history: list[str] = field(default_factory=list)
    ordinances: list[str] = field(default_factory=list)
    children: list[Node] = field(default_factory=list)

    def ancestors(self) -> list[Node]:
        out, n = [], self.parent
        while n:
            out.append(n)
            n = n.parent
        return out[::-1]


# ---------------------------------------------------------------- TOC


@dataclass
class TocEntry:
    guid: str
    kind: str  # division | chapter
    full_title: str
    division: str | None  # enclosing Part/division title


def parse_toc(html: str) -> list[TocEntry]:
    """Return chapters (and their enclosing division) from the code root page."""
    soup = BeautifulSoup(html, "lxml")
    toc = soup.find("nav", id="toc")
    entries: list[TocEntry] = []
    division = None
    for el in toc.find_all("div", attrs={"data-guid": True}, recursive=True):
        if "contentTitle" not in el.get("class", []):
            continue
        kind = el.get("data-code-content-type")
        full = el.get("data-full-title")
        if full is None:
            # Top-level banner such as "The Charter" / "The Code".
            division = clean(el.get_text(" "))
            continue
        if kind == "division":
            division = full
            continue
        entries.append(TocEntry(el["data-guid"], kind, full, division))
    return entries


def parse_customer(html: str) -> dict:
    soup = BeautifulSoup(html, "lxml")
    title = clean(soup.find("h1", id="pageTitle").get_text(" "))
    dd = soup.find(id="displayDate")
    m = re.search(r"through (\d{2}-\d{2}-\d{4})", dd.get_text() if dd else "")
    return {"name": title, "legislation_through": m.group(1) if m else None}


# ---------------------------------------------------------------- inline text


def inline(el: Tag | NavigableString) -> str:
    """Flatten inline markup to Markdown-ish text."""
    if isinstance(el, NavigableString):
        return str(el)
    name = el.name
    classes = el.get("class", [])
    if name in ("img", "script", "style"):
        return ""
    if name == "br":
        return " "
    inner = "".join(inline(c) for c in el.children)
    if name == "a" and "footnoteref" in classes:
        return f"[^{clean(inner).strip('[]')}]"
    if name == "dfn":
        return f"**{clean(inner)}**: " if clean(inner) else ""
    if name == "b" or name == "strong":
        return f"**{clean(inner)}**" if clean(inner) else ""
    if name in ("i", "em"):
        return f"*{clean(inner)}*" if clean(inner) else ""
    if name == "sup":
        t = clean(inner)
        return t if t in ("®", "™", "©") else f"^{t}"
    if name == "sub":
        return f"_{clean(inner)}"
    if name == "div":
        # Paragraph-level div nested inside inline context (table cells).
        return " " + inner + " "
    return inner


def para_text(el: Tag) -> str:
    return clean(inline(el))


# ---------------------------------------------------------------- tables


def _cell_text(cell: Tag) -> str:
    parts = []
    for c in cell.children:
        if isinstance(c, Tag) and c.name == "div" and "para" in c.get("class", []):
            parts.append(para_text(c))
        elif isinstance(c, Tag) and c.name == "div" and "line" in c.get("class", []):
            parts.append("____________________")
        else:
            t = clean(inline(c))
            if t:
                parts.append(t)
    text = "<br>".join(p for p in parts if p)
    return text.replace("|", "\\|")


def _grid(rows: list[Tag]) -> list[list[str]]:
    """Expand colspan/rowspan into a rectangular grid, repeating spanned text."""
    grid: list[list[str]] = []
    pending: dict[tuple[int, int], str] = {}
    for r, tr in enumerate(rows):
        row: list[str] = []
        c = 0
        cells = tr.find_all(["td", "th"], recursive=False)
        ci = 0
        while ci < len(cells) or (r, c) in pending:
            if (r, c) in pending:
                row.append(pending.pop((r, c)))
                c += 1
                continue
            cell = cells[ci]
            ci += 1
            text = _cell_text(cell)
            cs = int(cell.get("colspan", 1) or 1)
            rs = int(cell.get("rowspan", 1) or 1)
            for k in range(cs):
                row.append(text)
                for dr in range(1, rs):
                    pending[(r + dr, c + k)] = text
            c += cs
        grid.append(row)
    width = max((len(r) for r in grid), default=0)
    return [r + [""] * (width - len(r)) for r in grid]


def _md_row(cells: list[str]) -> str:
    return "| " + " | ".join(cells) + " |"


def table_block(div: Tag) -> Block | None:
    table = div.find("table")
    if table is None:
        return None
    head_rows = table.select(":scope > thead > tr")
    body_rows = table.select(":scope > tbody > tr") or [
        tr for tr in table.find_all("tr") if tr not in head_rows
    ]
    grid = _grid(head_rows + body_rows)
    if not grid:
        return None
    nhead = len(head_rows)
    width = len(grid[0])
    # Header rows whose one cell spans the full width are table captions.
    captions = []
    while nhead and width > 1 and len(set(grid[0])) == 1:
        if grid[0][0]:
            captions.append(f"**{grid[0][0]}**")
        grid.pop(0)
        nhead -= 1
    if not grid:
        return None
    if width == 1 and nhead == 0:
        # Single-column layout tables are boxed text (forms, quotes), not data.
        lines = [cell[0] for cell in grid if cell[0]]
        text = "\n".join("> " + ln.replace("<br>", "\n> ") for ln in lines)
        return Block(text, "quote")
    if nhead == 0:
        header = [""] * width
        body = grid
    else:
        # Multi-row headers collapse into one header row.
        header = []
        for col in range(width):
            vals = []
            for row in grid[:nhead]:
                v = row[col]
                if v and v not in vals:
                    vals.append(v)
            header.append(" / ".join(vals))
        body = grid[nhead:]
    header_md = _md_row(header) + "\n" + _md_row(["---"] * width)
    # Body rows spanning the full width are group labels; keep one copy.
    body = [[r[0]] + [""] * (width - 1) if width > 1 and len(set(r)) == 1 else r for r in body]
    rows_md = [_md_row(r) for r in body if any(x.strip() for x in r)]
    if captions:
        header_md = "\n".join(captions) + "\n\n" + header_md
    return Block(
        header_md + "\n" + "\n".join(rows_md),
        "table",
        table_header=header_md,
        table_rows=rows_md,
    )


# ---------------------------------------------------------------- bodies


class BodyParser:
    """Convert one `*_content` div into Markdown blocks."""

    def __init__(self, node: Node, attachments: list[Attachment], chapter_guid: str):
        self.node = node
        self.attachments = attachments
        self.chapter_guid = chapter_guid
        self.footnotes: list[Block] = []

    def parse(self, content: Tag) -> list[Block]:
        out = self.walk(content, 0)
        return out + self.footnotes

    def walk(self, el: Tag, depth: int) -> list[Block]:
        out: list[Block] = []
        for child in el.children:
            if isinstance(child, NavigableString):
                t = clean(child)
                if t:
                    out.append(Block(self.indent(depth) + t))
                continue
            out.extend(self.element(child, depth))
        return out

    @staticmethod
    def indent(depth: int) -> str:
        return "  " * depth

    def element(self, el: Tag, depth: int) -> list[Block]:
        cls = el.get("class", [])
        ind = self.indent(depth)
        if el.name == "div" and "para" in cls:
            t = para_text(el)
            return [Block(ind + t)] if t else []
        if el.name == "div" and "history" in cls:
            t = para_text(el)
            if not t:
                return []
            self.node.history.append(t)
            for law in el.select("span.loclaw"):
                o = clean(law.get_text())
                if o not in self.node.ordinances:
                    self.node.ordinances.append(o)
            return [Block(ind + f"*{t}*", "history")]
        if el.name == "div" and ("level" in cls or "deflevel" in cls):
            return self.walk(el, depth)
        if el.name == "div" and "litem" in cls or el.name == "section" and "defitem" in cls:
            return self.list_item(el, depth)
        if el.name == "section" and "definition" in cls:
            return self.definition(el, depth)
        if el.name == "div" and "codeTable" in cls:
            b = table_block(el)
            return [b] if b else []
        if el.name == "div" and "footnotes" in cls:
            for fn in el.find_all("div", class_="footnote", recursive=False):
                num = clean(fn.find("a", class_="footnoterefnum").get_text()).strip("[]")
                body = " ".join(para_text(p) for p in fn.find_all("div", class_="ftpara"))
                self.footnotes.append(Block(f"[^{num}]: {body}", "footnote"))
                for law in fn.select("span.loclaw"):
                    o = clean(law.get_text())
                    if o not in self.node.ordinances:
                        self.node.ordinances.append(o)
            return []
        if el.name == "div" and "attachmentsContainer" in cls:
            lines = []
            for a in el.find_all("a", class_="nonxml"):
                title = a.get("data-title") or clean(a.get_text())
                self.attachments.append(Attachment(title, a["href"], self.chapter_guid))
                lines.append(f"- {title} (PDF, indexed as a separate document)")
            return [Block("**Attachments:**\n" + "\n".join(lines), "attachments")] if lines else []
        if el.name == "div" and ("nonxml" in cls or "numberoverride" in cls):
            t = para_text(el)
            return [Block(ind + t)] if t else []
        if el.name == "div" and "line" in cls:
            return [Block(ind + "____________________")]
        # Unknown wrapper: recurse so no text is lost.
        t = clean(el.get_text(" "))
        if t:
            log.warning("unhandled element <%s class=%s> in %s", el.name, cls, self.node.guid)
            return self.walk(el, depth)
        return []

    def list_item(self, el: Tag, depth: int) -> list[Block]:
        num_a = el.find("a", class_=["litem_number", "defitem_number"], recursive=False)
        num = clean(num_a.get_text()) if num_a else ""
        content = el.find("div", class_=["litem_content", "defitem_content"], recursive=False)
        ind = self.indent(depth)
        if content is None:
            return [Block(f"{ind}- {num}")]
        kids = [
            c for c in content.children if not (isinstance(c, NavigableString) and not c.strip())
        ]
        out: list[Block] = []
        first = kids[0] if kids else None
        if isinstance(first, Tag) and first.name == "div" and "para" in first.get("class", []):
            out.append(Block(f"{ind}- {num} {para_text(first)}".rstrip(), "item"))
            rest = kids[1:]
        else:
            out.append(Block(f"{ind}- {num}".rstrip(), "item"))
            rest = kids
        for c in rest:
            if isinstance(c, NavigableString):
                t = clean(c)
                if t:
                    out.append(Block(self.indent(depth + 1) + t))
            else:
                out.extend(self.element(c, depth + 1))
        return out

    def definition(self, el: Tag, depth: int) -> list[Block]:
        ind = self.indent(depth)
        term = clean(el.find("dfn").get_text(" ")) if el.find("dfn") else ""
        out: list[Block] = []
        texts = el.find_all("div", class_="deftext", recursive=False)
        first = para_text(texts[0]) if texts else ""
        out.append(Block(f"{ind}**{term}**: {first}".rstrip(), "definition"))
        for c in el.children:
            if not isinstance(c, Tag) or c.name == "dfn" or (texts and c is texts[0]):
                continue
            if "deftext" in c.get("class", []):
                out.append(Block(ind + para_text(c)))
            else:
                out.extend(self.element(c, depth + 1))
        return out


# ---------------------------------------------------------------- chapter page

HEADING_RE = {
    "chapter": re.compile(r"^Chapter\s+(\S+)\.(?:\s+(.*))?$"),
    "part": re.compile(r"^Part\s+(\S+)\.(?:\s+(.*))?$"),
    "article": re.compile(r"^Article\s+(\S+)\.(?:\s+(.*))?$"),
    "section": re.compile(r"^(?:§|Section)\s*(\S+)\.(?:\s+(.*))?$"),
}
KIND_BY_CLASS = {
    "chapterTitle": "chapter",
    "partTitle": "part",
    "articleTitle": "article",
    "sectionTitle": "section",
}
RANK = {"chapter": 0, "part": 1, "article": 2, "section": 3}


def parse_chapter(html: str) -> tuple[Node, list[Attachment]]:
    """Parse a chapter print page into a Node tree plus its PDF attachments."""
    soup = BeautifulSoup(html, "lxml")
    content = soup.find("div", id="content")
    attachments: list[Attachment] = []
    root: Node | None = None
    stack: list[Node] = []
    current: Node | None = None

    for el in content.children:
        if not isinstance(el, Tag):
            continue
        cls = el.get("class", [])
        if el.name in ("h2", "h4") and "title" in cls:
            kind = next((KIND_BY_CLASS[c] for c in cls if c in KIND_BY_CLASS), None)
            if kind is None:
                log.warning("unknown heading %s", cls)
                continue
            heading = clean(el.get_text(" "))
            m = HEADING_RE[kind].match(heading)
            number, title = (m.group(1), m.group(2) or "") if m else ("", heading)
            node = Node(el["id"], kind, heading, number, title)
            if kind == "chapter":
                root = node
                stack = [node]
            else:
                while stack and RANK[stack[-1].kind] >= RANK[kind]:
                    stack.pop()
                node.parent = stack[-1]
                node.parent.children.append(node)
                stack.append(node)
            current = node
            continue
        if el.name == "div" and "content" in cls:
            if current is None:
                log.warning("content before heading")
                continue
            parser = BodyParser(current, attachments, root.guid if root else "")
            current.blocks.extend(parser.parse(el))
            continue
        if el.name == "h1":
            continue
        t = clean(el.get_text(" "))
        if t:
            log.warning("unhandled top-level <%s class=%s>: %s", el.name, cls, t[:80])
    if root is None:
        raise ValueError("no chapter heading found")
    return root, attachments


def iter_nodes(node: Node):
    yield node
    for c in node.children:
        yield from iter_nodes(c)

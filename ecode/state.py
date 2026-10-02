"""Maine state law, rules and guidance listed in state_sources.toml.

These documents sit beside the eCode360 crawl in the same chunks.jsonl, so
the weekly refresh re-fetches them and the index push treats them like any
other source. Every id starts with "ext-", one of the prefixes the push's
stale-document cleanup owns.
"""

from __future__ import annotations

import io
import re
import tomllib
import zipfile
from copy import copy
from pathlib import Path
from urllib.parse import unquote

from bs4 import BeautifulSoup, Tag

from .chunk import MAX_TOKENS, ntokens, pack
from .export import Exporter, SourceDoc, key, slug
from .parse import Block
from .pdf import pdf_pages_markdown

SOURCES = Path(__file__).with_name("state_sources.toml")

SOURCE_TYPES = {
    "statute": "state_statute",
    "rule": "state_rule",
    "guidance": "state_guidance",
    "model_code": "model_code_ref",
}
HEADER = {
    "statute": "Maine Revised Statutes",
    "rule": "Code of Maine Rules",
    "guidance": "Maine state guidance",
    "model_code": "Model code adopted in Maine (reference only)",
}
MUNICIPALITY = "State of Maine"

def load_sources(path: Path = SOURCES) -> list[dict]:
    """Expand the inventory into one entry per document to ingest."""
    out = []
    for s in tomllib.loads(path.read_text())["source"]:
        if s["tier"] == "skip":
            continue
        if "sections" in s:
            # A section range: one document per statute section.
            prefix = s["title"].split(" §§", 1)[0]
            for sec in s["sections"]:
                out.append({**s, "id": f"{s['id'].rsplit('-', 1)[0]}-{sec.lower()}", "section": sec,
                            "url": s["url_pattern"].format(section=sec), "title": None, "citation": f"{prefix} § {sec}"})
        else:
            out.append(s)
    return out


def citation_of(title: str) -> str:
    """"30-A M.R.S. § 4452. Enforcement ..." -> "30-A M.R.S. § 4452"; other titles stay whole."""
    m = re.match(r"^(.*?(?:§|ch\.)\s*[\w-]+)\.\s", title) or re.match(r"^(.+?\w{2,}[\w-]*)\.\s+[A-Z]", title)
    return m.group(1) if m else title


SMALL = {"a", "an", "and", "as", "at", "by", "for", "in", "of", "on", "or", "the", "to"}


def _smart_title(text: str) -> str:
    words = text.lower().split()
    return " ".join(w if i and w in SMALL else w.capitalize() for i, w in enumerate(words))


def _text(el: Tag) -> str:
    return re.sub(r"\s+", " ", el.get_text(" ")).replace(" ,", ",").replace(" ;", ";").replace(" .", ".").strip()


# ------------------------------------------------------------------ parsers


def statute_blocks(html: str) -> tuple[str, list[str], list[Block], str]:
    """Parse a legislature.maine.gov section page: heading, title path, blocks, history."""
    soup = BeautifulSoup(html, "lxml")
    sec = soup.select_one("div.MRSSection")
    if sec is None:
        raise ValueError("no MRSSection on statute page")
    heading = _text(sec.select_one(".heading_section"))
    path = [_text(d) for d in soup.select(".heading_structure .toc")]
    blocks = []
    for div in sec.select("div.mrs-text"):
        div = copy(div)
        for x in div.select("div.mrs-text, span.bhistory"):
            x.decompose()
        t = _text(div)
        if re.fullmatch(r"[\w()-]+\.", t):
            t += " (Repealed)"  # only the repeal citation was left, in the history span
        if t:
            nested = len(div.find_parents("div", class_="mrs-text"))
            blocks.append(Block(t, "para" if not nested else "item"))
    hist = soup.select_one("div.qhistory_list")
    return heading, path, blocks, _text(hist) if hist else ""


def docx_blocks(data: bytes) -> list[Block]:
    """Paragraphs of a .docx, headings marked in Markdown; the table of contents is dropped."""
    xml = zipfile.ZipFile(io.BytesIO(data)).read("word/document.xml")
    soup = BeautifulSoup(xml, "xml")
    blocks = []
    for p in soup.find_all("p"):
        style = p.find("pStyle")
        style = style.get("w:val", style.get("val", "")) if style else ""
        if "TableofContents" in style or "TOC" in style:
            continue
        t = re.sub(r"\s+", " ", "".join(x.text if x.name == "t" else " " for x in p.find_all(["t", "tab", "br"]))).strip()
        if not t:
            continue
        if "ChapterTitle" in style or style.startswith("Heading") or "Header" in style:
            t = f"## {t}"
        blocks.append(Block(t))
    return blocks


def html_page_blocks(html: str) -> tuple[str, list[Block]]:
    """Main content of a maine.gov web page."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("main") or soup.body
    for x in main.select("nav, script, style, form, [role=navigation], .visually-hidden, .sidebar, aside"):
        x.decompose()
    h1 = main.find("h1")
    title = _text(h1) if h1 else ""
    blocks = []
    for el in main.find_all(["h2", "h3", "h4", "p", "li"]):
        if el.find(["p", "li"]):
            continue
        t = _text(el)
        if len(t) < 3 or re.fullmatch(r"Home|Skip to .*", t) or el.find_parent("header"):
            continue
        blocks.append(Block(f"## {t}" if el.name.startswith("h") else (f"- {t}" if el.name == "li" else t)))
    return title, blocks


# ------------------------------------------------------------------ exporter


class StateExporter:
    def __init__(self, ex: Exporter):
        self.ex = ex
        self.f = ex.f
        self.crawled_at = ex.crawled_at.isoformat().replace("+00:00", "Z")

    def export(self, sources: list[dict] | None = None) -> list[SourceDoc]:
        docs = []
        for s in sources if sources is not None else load_sources():
            if s["tier"] == "reference":
                docs.append(self._stub(s))
            elif s.get("file", "").endswith(".md"):
                md = (SOURCES.parent / s["file"]).read_text()
                docs.append(self._blocks_doc(s, [Block(b.strip()) for b in re.split(r"\n\s*\n|\n(?=- )", md) if b.strip()], s["title"]))
            elif (s.get("file") or s["url"]).lower().endswith(".pdf"):
                docs.append(self._pdf(s))
            elif s["url"].lower().endswith(".docx"):
                docs.append(self._blocks_doc(s, docx_blocks(self.f.get(s["url"], binary=True)), s["title"]))
            elif s["kind"] == "statute":
                docs.append(self._statute(s))
            else:
                title, blocks = html_page_blocks(self.f.text(s["url"]))
                docs.append(self._blocks_doc(s, blocks, s["title"]))
        for d in docs:
            if not d.chunks:
                raise ValueError(f"{d.doc_id}: no text extracted from {d.url}")
        return docs

    # -------------------------------------------------------------- helpers

    def _doc(self, s: dict, title: str, md: str, extra_meta: dict | None = None) -> SourceDoc:
        doc_id = key(f"ext-{s['id']}")
        meta = {
            "title": title,
            "source_type": SOURCE_TYPES[s["kind"]],
            "url": s["url"],
            "citation": s.get("citation") or citation_of(title),
            "municipality": MUNICIPALITY,
            "crawled_at": self.crawled_at,
            **({"note": s["note"]} if s.get("note") else {}),
            **(extra_meta or {}),
        }
        rel = self.ex._write(f"markdown/state/{slug(s['id'])}.md", self.ex._front_matter(meta) + f"# {title}\n\n{md}\n")
        return SourceDoc(doc_id, meta["source_type"], title, s["url"], rel, meta)

    def _add_chunks(self, doc: SourceDoc, s: dict, bodies: list[tuple[str, int | None, int | None]], breadcrumb: str, **fields) -> None:
        n = len(bodies)
        for i, (body, ps, pe) in enumerate(bodies):
            where = ""
            if ps is not None:
                where = f", page {ps}" if ps == pe else f", pages {ps}-{pe}"
            part = f" (part {i + 1} of {n})" if n > 1 else ""
            content = f"{HEADER[s['kind']]}\n{breadcrumb}{where}{part}\n\n{body}"
            doc.chunks.append(
                {
                    "id": key(f"{doc.doc_id}-{i}"),
                    "doc_id": doc.doc_id,
                    "source_type": doc.source_type,
                    "node_type": s["kind"],
                    "title": doc.title,
                    "citation": doc.meta["citation"],
                    "breadcrumb": breadcrumb,
                    "content": content,
                    "url": s["url"],
                    "page_start": ps,
                    "page_end": pe,
                    "chunk_index": i,
                    "chunk_count": n,
                    "token_count": ntokens(content),
                    "ordinances": [],
                    "municipality": MUNICIPALITY,
                    "crawled_at": self.crawled_at,
                    **fields,
                }
            )

    # -------------------------------------------------------------- kinds

    def _statute(self, s: dict) -> SourceDoc:
        heading, path, blocks, history = statute_blocks(self.f.text(s["url"]))
        name = heading.partition(". ")[2]
        cite = s.get("citation") or citation_of(s["title"])
        title = s.get("title") or f"{cite}. {name}".strip()
        # Title 30-A > Chapter 187: Planning and Land Use Regulation > ... > 30-A M.R.S. § 4452. Enforcement of ...
        # Keep the title number and the chapter levels; parts and subparts add length, not meaning.
        crumbs = [
            a.strip() if a.startswith("Title") else f"{a.strip()}: {_smart_title(b)}"
            for a, _, b in (p.partition(":") for p in path)
            if a.startswith(("Title", "Chapter", "Subchapter"))
        ]
        breadcrumb = " > ".join(crumbs + [f"{cite}. {name}".strip()])
        md = "\n\n".join(b.text for b in blocks) + (f"\n\nSection history: {history}" if history else "")
        doc = self._doc(s, title, md, {"title_path": path})
        self._add_chunks(doc, s, [(b, None, None) for b in pack(blocks)], breadcrumb, history=history or None)
        return doc

    def _pdf(self, s: dict) -> SourceDoc:
        data = (SOURCES.parent / s["file"]).read_bytes() if s.get("file") else self.f.get(s["url"], binary=True)
        if not data.startswith(b"%PDF"):
            raise ValueError(f"{s['id']}: {s['url']} did not return a PDF")
        fname = unquote((s.get("file") or s["url"]).rsplit("/", 1)[-1])
        (self.ex.out / "pdf/state").mkdir(parents=True, exist_ok=True)
        (self.ex.out / "pdf/state" / fname).write_bytes(data)
        pages = pdf_pages_markdown(data)
        md = "\n".join(f"<!-- page {i} -->\n\n{p}\n" for i, p in enumerate(pages, 1))
        doc = self._doc(s, s["title"], md, {"pages": len(pages)})
        # Page-by-page chunks merged up to the token limit, as for code attachments.
        merged: list[tuple[str, int, int]] = []
        for i, p in enumerate(pages, 1):
            for body in pack([Block(b.strip()) for b in re.split(r"\n\s*\n", p) if b.strip()]):
                if merged and ntokens(merged[-1][0]) + ntokens(body) <= MAX_TOKENS:
                    merged[-1] = (merged[-1][0] + "\n\n" + body, merged[-1][1], i)
                else:
                    merged.append((body, i, i))
        self._add_chunks(doc, s, merged, s["title"])
        return doc

    def _blocks_doc(self, s: dict, blocks: list[Block], title: str) -> SourceDoc:
        doc = self._doc(s, title, "\n\n".join(b.text for b in blocks))
        self._add_chunks(doc, s, [(b, None, None) for b in pack(blocks)], title)
        return doc

    def _stub(self, s: dict) -> SourceDoc:
        body = (
            f"{s['summary']}\n\n"
            f"The full text of {s['title'].split('. ', 1)[0]} is copyrighted and is not included in this assistant's sources. "
            f"Read it at {s['url']}"
        )
        doc = self._doc(s, s["title"], body)
        self._add_chunks(doc, s, [(body, None, None)], s["title"])
        return doc

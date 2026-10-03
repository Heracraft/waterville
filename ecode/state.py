"""Non-eCode sources: Maine law, rules and guidance, City forms and staff notes.

state_sources.toml lists the state statutes, rules, court rules, manuals and
model-code stubs, plus the City of Waterville permit forms (kind "city_form").
staff_notes.toml holds curated currency and conflict notes (source_type
"staff_note", staff searches only).

These documents sit beside the eCode360 crawl in the same chunks.jsonl, so
the weekly refresh re-fetches them and the index push treats them like any
other source. Every id starts with "ext-", one of the prefixes the push's
stale-document cleanup owns.

Run only these sources, without the eCode crawl:

    python -m ecode.state --out DIR [--only id,id] [--kind city_form] [--cache DIR]
"""

from __future__ import annotations

import logging
import re
import tomllib
from copy import copy
from pathlib import Path
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup, Tag

from .chunk import MAX_TOKENS, MIN_TOKENS, ntokens, pack
from .export import Exporter, SourceDoc, key, slug
from .headings import crumb, docx_trail_blocks, pdf_page_blocks
from .parse import Block
from .pdf import pdf_pages_markdown

log = logging.getLogger(__name__)

SOURCES = Path(__file__).with_name("state_sources.toml")
STAFF_NOTES = Path(__file__).with_name("staff_notes.toml")

SOURCE_TYPES = {
    "statute": "state_statute",
    "rule": "state_rule",
    "court_rule": "state_rule",
    "guidance": "state_guidance",
    "model_code": "model_code_ref",
    "city_form": "city_form",
    "staff_note": "staff_note",
}
HEADER = {
    "statute": "Maine Revised Statutes",
    "rule": "Code of Maine Rules",
    "court_rule": "Maine Rules of Civil Procedure",
    "guidance": "Maine state guidance",
    "model_code": "Model code adopted in Maine (reference only)",
    "city_form": "City of Waterville, ME forms",
    "staff_note": "Waterville code office staff note (research aid, not law)",
}
MUNICIPALITY = "State of Maine"
CITY = "City of Waterville, ME"
MUNICIPALITIES = {"city_form": CITY, "staff_note": CITY}
# Kinds whose chunks carry a heading trail in their breadcrumb (open item 1).
TRAIL_KINDS = ("guidance", "rule", "court_rule")
DOC_VIEW = re.compile(r"/DocumentCenter/View/(\d+)", re.I)

def load_sources(path: Path = SOURCES) -> list[dict]:
    """Expand the inventory into one entry per document to ingest."""
    out = []
    for s in tomllib.loads(path.read_text())["source"]:
        if s["tier"] in ("skip", "superseded"):
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


NOTE_FIELDS = {"id", "title", "body", "sources", "checked", "status", "topics"}


def load_staff_notes(path: Path = STAFF_NOTES) -> list[dict]:
    """Curated staff notes, checked for the fields the exporter needs."""
    if not path.exists():
        return []
    notes = tomllib.loads(path.read_text()).get("note", [])
    seen = set()
    for n in notes:
        missing = {"id", "title", "body", "sources", "checked"} - n.keys()
        if missing:
            raise ValueError(f"staff note {n.get('id')!r} lacks {sorted(missing)}")
        if extra := set(n) - NOTE_FIELDS:
            raise ValueError(f"staff note {n['id']}: unknown fields {sorted(extra)}")
        if n["id"] in seen:
            raise ValueError(f"duplicate staff note id {n['id']}")
        seen.add(n["id"])
        if not n["sources"] or not all(isinstance(u, str) and u.startswith("https://") for u in n["sources"]):
            raise ValueError(f"staff note {n['id']}: every note cites at least one https:// source")
    return notes


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
    return [b for _, b in docx_trail_blocks(data)]


def city_form_links(html: str, base: str) -> list[tuple[str, str]]:
    """(absolute url, link text) for every DocumentCenter file linked from a City web page's content."""
    soup = BeautifulSoup(html, "lxml")
    main = soup.select_one("#moduleContent") or soup.select_one("main") or soup.body or soup
    out, seen = [], set()
    for a in main.find_all("a", href=True):
        m = DOC_VIEW.search(a["href"])
        if not m or m.group(1) in seen:
            continue
        seen.add(m.group(1))
        out.append((urljoin(base, a["href"]), _text(a)))
    return out


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


def _common_prefix(a: tuple[str, ...], b: tuple[str, ...]) -> tuple[str, ...]:
    out = []
    for x, y in zip(a, b):
        if x != y:
            break
        out.append(x)
    return tuple(out)


def merge_pieces(pieces: list[tuple[str, int | None, tuple[str, ...]]]) -> list[tuple[str, int | None, int | None, tuple[str, ...]]]:
    """Merge (body, page, heading path) pieces into chunks of up to MAX_TOKENS.

    Neighbors merge while they fit and share their outermost heading; the
    merged chunk keeps the headings both share. A chunk under MIN_TOKENS (a
    lone heading line, a short section, a page tail) merges into the next
    piece; when the two share no heading, the larger part's headings label
    the chunk. A breadcrumb never names a part the chunk does not contain.
    """
    merged: list[list] = []
    for body, page, path in pieces:
        if merged:
            last = merged[-1]
            have, add = ntokens(last[0]), ntokens(body)
            small = have < MIN_TOKENS
            if have + add <= MAX_TOKENS and (small or last[3][:1] == path[:1]):
                shared = _common_prefix(last[3], path)
                if small and not shared:
                    # A lone heading or a short tail: label with the larger part's headings.
                    shared = path if add >= have else last[3]
                last[0] += "\n\n" + body
                last[2] = page
                last[3] = shared
                continue
        merged.append([body, page, page, path])
    return [tuple(m) for m in merged]


def _pieces(items: list[tuple[tuple[str, ...], Block]], page: int | None) -> list[tuple[str, int | None, tuple[str, ...]]]:
    """Pack each run of blocks that share a heading path."""
    out = []
    run: list[Block] = []
    path: tuple[str, ...] | None = None
    for p, b in [*items, (None, None)]:
        if p != path and run:
            out += [(body, page, path) for body in pack(run)]
            run = []
        path = p
        if b is not None:
            run.append(b)
    return out


class StateExporter:
    def __init__(self, ex: Exporter):
        self.ex = ex
        self.f = ex.f
        self.crawled_at = ex.crawled_at.isoformat().replace("+00:00", "Z")

    def export(self, sources: list[dict] | None = None, notes: list[dict] | None = None) -> list[SourceDoc]:
        sources = self.expand_listings(load_sources() if sources is None else sources)
        docs = []
        for s in sources:
            try:
                doc = self._export_one(s)
            except Exception as e:  # noqa: BLE001
                if not s.get("optional"):
                    raise
                log.warning("skipped %s (%s): %s", s["id"], s["url"], e)
                continue
            docs.append(doc)
        for n in load_staff_notes() if notes is None else notes:
            docs.append(self._note(n))
        for d in docs:
            if not d.chunks:
                raise ValueError(f"{d.doc_id}: no text extracted from {d.url}")
        return docs

    def _export_one(self, s: dict) -> SourceDoc:
        if s["tier"] == "reference":
            return self._stub(s)
        if s.get("file", "").endswith(".md"):
            md = (SOURCES.parent / s["file"]).read_text()
            blocks = [((), Block(b.strip())) for b in re.split(r"\n\s*\n|\n(?=- )", md) if b.strip()]
            return self._blocks_doc(s, blocks, s["title"])
        if s["kind"] == "city_form" or (s.get("file") or s["url"]).lower().endswith(".pdf"):
            return self._pdf(s)
        if s["url"].lower().endswith(".docx"):
            return self._blocks_doc(s, docx_trail_blocks(self.f.get(s["url"], binary=True)), s["title"])
        if s["kind"] == "statute":
            return self._statute(s)
        _, blocks = html_page_blocks(self.f.text(s["url"]))
        return self._blocks_doc(s, [((), b) for b in blocks], s["title"])

    def expand_listings(self, sources: list[dict]) -> list[dict]:
        """Replace each tier = "listing" page with the forms it links that the inventory lacks.

        A City page can gain a form before anyone adds it to state_sources.toml.
        Such a form is ingested with its link text as title and a warning in
        the log; a listed form that is gone from its page is logged too.
        """
        known = {
            m.group(1)
            for s in sources
            if s["kind"] == "city_form" and s["tier"] != "listing" and (m := DOC_VIEW.search(s["url"]))
        }
        out, found = [], []
        for s in sources:
            if s["tier"] != "listing":
                out.append(s)
                continue
            try:
                links = city_form_links(self.f.text(s["url"]), s["url"])
            except Exception as e:  # noqa: BLE001
                log.warning("could not read form listing %s: %s", s["url"], e)
                continue
            on_page = set()
            for url, text in links:
                vid = DOC_VIEW.search(url).group(1)
                on_page.add(vid)
                if vid in known:
                    continue
                name = re.sub(r"\s*\(?PDF\)?\s*$", "", text, flags=re.I).strip() or f"Form {vid}"
                log.warning("new form on %s: %s (%s); add it to state_sources.toml", s["url"], name, url)
                found.append(
                    {
                        "id": f"waterville-form-{vid}",
                        "title": f"City of Waterville {name}",
                        "citation": f"Waterville form: {name}",
                        "url": url,
                        "kind": "city_form",
                        "tier": "ingest",
                        "optional": True,
                        "note": f"found on {s['url']}; not yet reviewed in state_sources.toml",
                    }
                )
            for other in sources:
                m = DOC_VIEW.search(other["url"])
                if other.get("listing") == s["url"] and m and m.group(1) not in on_page:
                    log.warning("%s is no longer linked from %s", other["url"], s["url"])
        return out + found

    # -------------------------------------------------------------- helpers

    def _doc(self, s: dict, title: str, md: str, extra_meta: dict | None = None) -> SourceDoc:
        doc_id = key(f"ext-{s['id']}")
        meta = {
            "title": title,
            "source_type": SOURCE_TYPES[s["kind"]],
            "url": s["url"],
            "citation": s.get("citation") or citation_of(title),
            "municipality": MUNICIPALITIES.get(s["kind"], MUNICIPALITY),
            "crawled_at": self.crawled_at,
            **({"note": s["note"]} if s.get("note") else {}),
            **(extra_meta or {}),
        }
        folder = {"city_form": "city-forms", "staff_note": "staff-notes"}.get(s["kind"], "state")
        rel = self.ex._write(f"markdown/{folder}/{slug(s['id'])}.md", self.ex._front_matter(meta) + f"# {title}\n\n{md}\n")
        return SourceDoc(doc_id, meta["source_type"], title, s["url"], rel, meta)

    def _add_chunks(self, doc: SourceDoc, s: dict, bodies: list[tuple], breadcrumb: str, **fields) -> None:
        """bodies: (body, page_start, page_end), optionally with a fourth item, the heading path."""
        n = len(bodies)
        for i, (body, ps, pe, *rest) in enumerate(bodies):
            crumb_i = crumb(breadcrumb, rest[0]) if rest and rest[0] else breadcrumb
            where = ""
            if ps is not None:
                where = f", page {ps}" if ps == pe else f", pages {ps}-{pe}"
            part = f" (part {i + 1} of {n})" if n > 1 else ""
            content = f"{HEADER[s['kind']]}\n{crumb_i}{where}{part}\n\n{body}"
            doc.chunks.append(
                {
                    "id": key(f"{doc.doc_id}-{i}"),
                    "doc_id": doc.doc_id,
                    "source_type": doc.source_type,
                    "node_type": s["kind"],
                    "title": doc.title,
                    "citation": doc.meta["citation"],
                    "breadcrumb": crumb_i,
                    "content": content,
                    "url": s["url"],
                    "page_start": ps,
                    "page_end": pe,
                    "chunk_index": i,
                    "chunk_count": n,
                    "token_count": ntokens(content),
                    "ordinances": [],
                    "municipality": doc.meta["municipality"],
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
        if not fname.lower().endswith(".pdf"):
            fname = f"{slug(s['id'])}.pdf"
        folder = "pdf/city-forms" if s["kind"] == "city_form" else "pdf/state"
        (self.ex.out / folder).mkdir(parents=True, exist_ok=True)
        (self.ex.out / folder / fname).write_bytes(data)
        pages = pdf_pages_markdown(data)
        md = "\n".join(f"<!-- page {i} -->\n\n{p}\n" for i, p in enumerate(pages, 1))
        doc = self._doc(s, s["title"], md, {"pages": len(pages)})
        # Page-by-page chunks merged up to the token limit, as for code attachments.
        # Manuals and rules also carry the heading trail in effect (open item 1).
        if s["kind"] in TRAIL_KINDS:
            page_items = pdf_page_blocks(pages, doc_title=s["title"])
        else:
            page_items = [[((), Block(b.strip())) for b in re.split(r"\n\s*\n", p) if b.strip()] for p in pages]
        pieces = [pc for i, items in enumerate(page_items, 1) for pc in _pieces(items, i)]
        self._add_chunks(doc, s, merge_pieces(pieces), s["title"])
        return doc

    def _blocks_doc(self, s: dict, items: list[tuple[tuple[str, ...], Block]], title: str) -> SourceDoc:
        doc = self._doc(s, title, "\n\n".join(b.text for _, b in items))
        self._add_chunks(doc, s, merge_pieces(_pieces(items, None)), title)
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

    def _note(self, n: dict) -> SourceDoc:
        """A curated staff note: staff searches only, and every note names its sources."""
        reviewed = n.get("status") == "reviewed"
        s = {
            "id": f"staff-note-{n['id']}",
            "kind": "staff_note",
            "url": n["sources"][0],
            "citation": f"Staff note: {n['title']}",
        }
        body = (
            n["body"].strip()
            + "\n\nSources:\n"
            + "\n".join(f"- {u}" for u in n["sources"])
            + f"\n\nChecked against these sources on {n['checked']}. "
            + ("Reviewed by the Code Enforcement Office." if reviewed else "Not yet reviewed by the Code Enforcement Officer.")
        )
        meta = {"sources": n["sources"], "checked": n["checked"], "status": n.get("status", "draft")}
        doc = self._doc(s, n["title"], body, meta)
        blocks = [Block(b.strip()) for b in re.split(r"\n\s*\n", body) if b.strip()]
        self._add_chunks(doc, s, [(b, None, None) for b in pack(blocks)], f"Staff notes > {n['title']}")
        return doc


# ------------------------------------------------------------------ CLI


def main(argv=None) -> None:
    """Export only the non-eCode sources (state law, City forms, staff notes) to a directory."""
    import argparse
    import json

    from .fetch import Fetcher

    ap = argparse.ArgumentParser(description=main.__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--cache", type=Path, default=Path("data/raw"), help="raw HTTP response cache")
    ap.add_argument("--only", default="", help="comma-separated source ids; a range id (mrs-17-2851) selects its sections")
    ap.add_argument("--kind", action="append", default=[], help="only sources of this kind (repeatable)")
    ap.add_argument("--no-notes", action="store_true", help="leave out staff_notes.toml")
    ap.add_argument("--notes-only", action="store_true", help="only staff_notes.toml")
    ap.add_argument("--delay", type=float, default=1.5)
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    ranges = {s["id"]: s["id"].rsplit("-", 1)[0] for s in tomllib.loads(SOURCES.read_text())["source"] if "sections" in s}
    only = {x.strip() for x in args.only.split(",") if x.strip()}
    prefixes = tuple(ranges[x] + "-" for x in only if x in ranges)
    sources = []
    for s in load_sources():
        if only and s["id"] not in only and not ("section" in s and s["id"].startswith(prefixes or ("\0",))):
            continue
        if args.kind and s["kind"] not in args.kind:
            continue
        sources.append(s)
    if args.notes_only:
        sources = []
    notes = [] if args.no_notes else load_staff_notes()

    args.out.mkdir(parents=True, exist_ok=True)
    ex = Exporter("WA3904", args.out, Fetcher(args.cache, delay=args.delay))
    ex.customer = {"name": CITY, "legislation_through": None}
    ex.docs = StateExporter(ex).export(sources, notes)
    manifest = ex.write_outputs(None)
    print(json.dumps({k: manifest[k] for k in ("documents", "chunks", "chunk_tokens")}, indent=2))


if __name__ == "__main__":
    main()

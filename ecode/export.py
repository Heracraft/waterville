"""Crawl an eCode360 code and write Azure-ready RAG output."""

from __future__ import annotations

import datetime as dt
import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote

from bs4 import BeautifulSoup

from .chunk import MAX_TOKENS, ntokens, pack
from .fetch import BASE, Fetcher
from .parse import Attachment, Block, Node, TocEntry, iter_nodes, parse_chapter, parse_customer, parse_toc
from .pdf import pdf_pages_markdown

log = logging.getLogger(__name__)


def slug(text: str, maxlen: int = 80) -> str:
    s = re.sub(r"[^A-Za-z0-9]+", "-", text).strip("-").lower()
    return s[:maxlen].rstrip("-")


def key(text: str) -> str:
    """Azure AI Search keys allow letters, digits, '_', '-' and '='."""
    return re.sub(r"[^A-Za-z0-9_\-=]", "_", text)


@dataclass
class SourceDoc:
    """One ingestible document: a code chapter, a PDF attachment or a new law."""

    doc_id: str
    source_type: str  # code_chapter | attachment | new_law | state_* | model_code_ref (see state.py)
    title: str
    url: str
    markdown_path: str
    meta: dict = field(default_factory=dict)
    chunks: list[dict] = field(default_factory=list)


class Exporter:
    def __init__(self, cust: str, out: Path, fetcher: Fetcher):
        self.cust = cust
        self.out = out
        self.f = fetcher
        self.crawled_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        self.docs: list[SourceDoc] = []
        self.chapters: list[tuple[TocEntry, Node]] = []
        self.attachments: list[Attachment] = []

    # ------------------------------------------------------------ crawl

    def crawl(self) -> None:
        root_html = self.f.text(f"/{self.cust}")
        self.customer = parse_customer(root_html)
        self.toc = parse_toc(root_html)
        log.info("%s: %d chapters", self.customer["name"], len(self.toc))
        for entry in self.toc:
            html = self.f.text(f"/print/{self.cust}?guid={entry.guid}&children=true")
            node, atts = parse_chapter(html)
            if node.guid != entry.guid:
                raise ValueError(f"print page for {entry.guid} returned chapter {node.guid}")
            self.chapters.append((entry, node))
            self.attachments.extend(atts)

    def verify(self) -> dict:
        """Cross-check parsed sections against the site's own navigation TOCs.

        Chapter pages list their articles/parts/sections; container pages list
        their children. Every section guid found this way must appear in the
        print output, and vice versa.
        """
        report = {"chapters": [], "missing": [], "extra": []}
        for entry, node in self.chapters:
            parsed = {n.guid for n in iter_nodes(node) if n.kind == "section"}
            found: set[str] = set()
            queue = [entry.guid]
            seen = set()
            while queue:
                g = queue.pop()
                if g in seen:
                    continue
                seen.add(g)
                soup = BeautifulSoup(self.f.text(f"/{g}"), "lxml")
                nav = soup.find("nav", id="toc")
                if nav is None:
                    continue
                for el in nav.find_all(attrs={"data-code-content-type": True}):
                    t = el["data-code-content-type"]
                    if t == "section":
                        found.add(el["data-guid"])
                    elif el["data-guid"] not in seen:
                        queue.append(el["data-guid"])
            missing = sorted(found - parsed)
            extra = sorted(parsed - found)
            report["chapters"].append(
                {"chapter": entry.full_title, "toc_sections": len(found), "parsed_sections": len(parsed)}
            )
            report["missing"] += [{"chapter": entry.full_title, "guid": g} for g in missing]
            report["extra"] += [{"chapter": entry.full_title, "guid": g} for g in extra]
        return report

    # ------------------------------------------------------------ helpers

    def _base_meta(self) -> dict:
        return {
            "municipality": self.customer["name"],
            "code_id": self.cust,
            "legislation_through": self.customer["legislation_through"],
            "crawled_at": self.crawled_at.isoformat().replace("+00:00", "Z"),
        }

    @staticmethod
    def _front_matter(meta: dict) -> str:
        lines = ["---"]
        for k, v in meta.items():
            if v is None or v == [] or v == "":
                continue
            lines.append(f"{k}: {json.dumps(v, ensure_ascii=False)}")
        lines.append("---")
        return "\n".join(lines) + "\n\n"

    def _write(self, rel: str, text: str) -> str:
        p = self.out / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
        return rel

    # ------------------------------------------------------------ code

    def _citation(self, chapter: Node, n: Node) -> str:
        arts = [a for a in n.ancestors() if a.kind == "article"]
        if n.kind != "section":
            return n.heading.rstrip(".")
        if chapter.number == "C":
            art = f" Art. {arts[0].number}," if arts else ""
            return f"Charter{art} § {n.number}"
        return f"§ {n.number}"

    def export_code(self) -> None:
        for entry, chapter in self.chapters:
            doc_id = key(f"code-{chapter.number}")
            url = f"{BASE}/{chapter.guid}"
            meta = {
                "title": chapter.heading,
                "source_type": "code_chapter",
                "division": entry.division,
                "chapter_number": chapter.number,
                "chapter_title": chapter.title,
                "url": url,
                **self._base_meta(),
            }
            md = [self._front_matter(meta), f"# {chapter.heading}\n"]
            doc = SourceDoc(doc_id, "code_chapter", chapter.heading, url, "", meta)

            for n in iter_nodes(chapter):
                level = {"chapter": 1, "part": 2, "article": 2, "section": 3}[n.kind]
                if n.kind == "article" and any(a.kind == "part" for a in n.ancestors()):
                    level = 3
                if n.kind == "section" and any(a.kind == "part" for a in n.ancestors()):
                    level = 4
                if n.kind != "chapter":
                    md.append(f"{'#' * level} {n.heading}\n")
                if n.blocks:
                    md.append("\n\n".join(b.text for b in n.blocks) + "\n")
                self._chunk_node(doc, entry, chapter, n)

            doc.markdown_path = self._write(
                f"markdown/code/{slug(chapter.number.zfill(3))}-{slug(chapter.title)}.md", "\n".join(md)
            )
            self.docs.append(doc)

    def _chunk_node(self, doc: SourceDoc, entry: TocEntry, chapter: Node, n: Node) -> None:
        if not n.blocks:
            return
        anc = n.ancestors()
        part = next((a for a in anc if a.kind == "part"), None)
        article = next((a for a in anc if a.kind == "article"), None)
        path = [a.heading for a in anc] + [n.heading]
        title = n.heading if n.kind == "section" else f"{n.heading} (history and notes)"
        citation = self._citation(chapter, n)
        bodies = pack(n.blocks)
        for i, body in enumerate(bodies):
            cont = f" (part {i + 1} of {len(bodies)})" if len(bodies) > 1 else ""
            header = f"{self.customer['name']} Code\n{' > '.join(path)}{cont}\n\n"
            content = header + body
            doc.chunks.append(
                {
                    "id": key(f"code-{n.guid}-{i}"),
                    "doc_id": doc.doc_id,
                    "source_type": "code",
                    "node_type": n.kind,
                    "title": title,
                    "citation": citation,
                    "content": content,
                    "division": entry.division,
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                    "part": part.heading if part else None,
                    "article": article.heading if article else None,
                    "section_number": n.number if n.kind == "section" else None,
                    "section_title": n.title if n.kind == "section" else None,
                    "breadcrumb": " > ".join(path),
                    "url": f"{BASE}/{n.guid}",
                    "ecode_guid": n.guid,
                    "history": " ".join(n.history) or None,
                    "ordinances": n.ordinances,
                    "adopted_date": None,
                    "page_start": None,
                    "page_end": None,
                    "chunk_index": i,
                    "chunk_count": len(bodies),
                    "token_count": ntokens(content),
                    **self._common_fields(),
                }
            )

    def _common_fields(self) -> dict:
        return {
            "municipality": self.customer["name"],
            "legislation_through": self.customer["legislation_through"],
            "crawled_at": self.crawled_at.isoformat().replace("+00:00", "Z"),
        }

    # ------------------------------------------------------------ PDFs

    def _pdf_doc(
        self,
        doc_id: str,
        source_type: str,
        title: str,
        url: str,
        pdf_rel: str,
        md_rel: str,
        meta: dict,
        chunk_fields: dict,
        header_title: str,
    ) -> SourceDoc:
        data = self.f.get(url, binary=True)
        (self.out / pdf_rel).parent.mkdir(parents=True, exist_ok=True)
        (self.out / pdf_rel).write_bytes(data)
        pages = pdf_pages_markdown(data)
        full_meta = {"title": title, "source_type": source_type, "url": url, "pages": len(pages), **meta, **self._base_meta()}
        md = [self._front_matter(full_meta), f"# {title}\n"]
        for i, p in enumerate(pages, 1):
            md.append(f"<!-- page {i} -->\n\n{p}\n")
        doc = SourceDoc(doc_id, source_type, title, url, self._write(md_rel, "\n".join(md)), full_meta)

        # Chunk page by page so every chunk carries an accurate page range,
        # then merge neighbouring small chunks.
        per_page: list[tuple[int, int, str]] = []
        for i, p in enumerate(pages, 1):
            blocks = [Block(b.strip()) for b in re.split(r"\n\s*\n", p) if b.strip()]
            for body in pack(blocks):
                per_page.append((i, i, body))
        merged: list[tuple[int, int, str]] = []
        for s, e, body in per_page:
            if merged and ntokens(merged[-1][2]) + ntokens(body) <= MAX_TOKENS:
                ps, _, pb = merged[-1]
                merged[-1] = (ps, e, pb + "\n\n" + body)
            else:
                merged.append((s, e, body))
        for i, (s, e, body) in enumerate(merged):
            pages_txt = f"page {s}" if s == e else f"pages {s}-{e}"
            cont = f" (part {i + 1} of {len(merged)})" if len(merged) > 1 else ""
            label = self.customer["name"] + (" Code" if source_type == "attachment" else "")
            content = f"{label}\n{header_title}, {pages_txt}{cont}\n\n{body}"
            doc.chunks.append(
                {
                    "id": key(f"{doc_id}-{i}"),
                    "doc_id": doc_id,
                    "source_type": source_type,
                    "node_type": "pdf",
                    "title": title,
                    "content": content,
                    "url": url,
                    "page_start": s,
                    "page_end": e,
                    "chunk_index": i,
                    "chunk_count": len(merged),
                    "token_count": ntokens(content),
                    **chunk_fields,
                    **self._common_fields(),
                }
            )
        return doc

    def export_attachments(self) -> None:
        chapters = {node.guid: (entry, node) for entry, node in self.chapters}
        seen = set()
        for att in self.attachments:
            if att.href in seen:
                continue
            seen.add(att.href)
            entry, chapter = chapters[att.chapter_guid]
            fname = att.href.rsplit("/", 1)[-1]
            stem = fname.rsplit(".", 1)[0]
            doc_id = key(f"attachment-{slug(stem)}")
            url = BASE + quote(att.href)
            title = f"{chapter.heading}, {att.title}"
            doc = self._pdf_doc(
                doc_id,
                "attachment",
                title,
                url,
                f"pdf/attachments/{fname}",
                f"markdown/attachments/{slug(stem)}.md",
                {"chapter_number": chapter.number, "chapter_title": chapter.title, "division": entry.division},
                {
                    "citation": f"Ch. {chapter.number}, {att.title}",
                    "division": entry.division,
                    "chapter_number": chapter.number,
                    "chapter_title": chapter.title,
                    "breadcrumb": f"{chapter.heading} > {att.title}",
                    "ordinances": [],
                },
                header_title=f"{chapter.heading} > {att.title}",
            )
            self.docs.append(doc)

    def export_new_laws(self) -> None:
        soup = BeautifulSoup(self.f.text(f"/{self.cust}/laws"), "lxml")
        for tr in soup.select("table#newLawsTable tbody tr[data-document-id]"):
            a = tr.find("a", class_="law")
            if a is None:
                continue
            law_id = tr["data-document-id"]
            law_title = tr.get("data-title") or a.get_text(strip=True)
            subject = tr.get("data-subject") or ""
            adopted = tr.get("data-adopted") or None
            title = f"{law_title}: {subject}" if subject else law_title
            url = BASE + a["href"]
            doc = self._pdf_doc(
                key(f"newlaw-{law_id}"),
                "new_law",
                title,
                url,
                f"pdf/new-laws/{law_id}.pdf",
                f"markdown/new-laws/{law_id}-{slug(law_title)}.md",
                {
                    "law_id": law_id,
                    "law_title": law_title,
                    "subject": subject,
                    "adopted_date": adopted,
                    "legislation_type": tr.get("data-legislation-type"),
                    "status": "Adopted, not yet codified into the Code",
                },
                {
                    "citation": law_title,
                    "breadcrumb": f"New Laws (adopted, not yet codified) > {title}",
                    "ordinances": [law_title],
                    "adopted_date": f"{adopted}T00:00:00Z" if adopted else None,
                    "history": f"Adopted {adopted}; pending codification." if adopted else None,
                },
                header_title=f"New Laws (adopted {adopted}, not yet codified) > {title}",
            )
            self.docs.append(doc)

    # ------------------------------------------------------------ output

    def write_outputs(self, verify_report: dict | None) -> dict:
        chunks = [c for d in self.docs for c in d.chunks]
        ids = [c["id"] for c in chunks]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate chunk ids")
        fields = sorted({k for c in chunks for k in c})
        with open(self.out / "chunks.jsonl", "w", encoding="utf-8") as fh:
            for c in chunks:
                row = {k: c.get(k) for k in fields}
                if row.get("ordinances") is None:
                    row["ordinances"] = []
                fh.write(json.dumps(row, ensure_ascii=False) + "\n")
        with open(self.out / "documents.jsonl", "w", encoding="utf-8") as fh:
            for d in self.docs:
                fh.write(
                    json.dumps(
                        {
                            "doc_id": d.doc_id,
                            "source_type": d.source_type,
                            "title": d.title,
                            "url": d.url,
                            "markdown_path": d.markdown_path,
                            "chunk_count": len(d.chunks),
                            "token_count": sum(c["token_count"] for c in d.chunks),
                            **{k: v for k, v in d.meta.items() if k not in ("title", "url", "source_type")},
                        },
                        ensure_ascii=False,
                    )
                    + "\n"
                )
        tokens = [c["token_count"] for c in chunks]
        manifest = {
            "source": f"{BASE}/{self.cust}",
            **self._base_meta(),
            "documents": {t: sum(1 for d in self.docs if d.source_type == t) for t in dict.fromkeys(d.source_type for d in self.docs)},
            "sections": sum(1 for _, n in self.chapters for x in iter_nodes(n) if x.kind == "section"),
            "chunks": len(chunks),
            "chunk_tokens": {
                "min": min(tokens),
                "max": max(tokens),
                "mean": round(sum(tokens) / len(tokens)),
                "total": sum(tokens),
            },
            "tokenizer": "cl100k_base",
            "verification": None
            if verify_report is None
            else {
                "toc_sections": sum(c["toc_sections"] for c in verify_report["chapters"]),
                "parsed_sections": sum(c["parsed_sections"] for c in verify_report["chapters"]),
                "missing": verify_report["missing"],
                "extra": verify_report["extra"],
            },
        }
        (self.out / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n")
        return manifest

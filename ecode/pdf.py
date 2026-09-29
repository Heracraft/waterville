"""PDF to Markdown conversion for code attachments and new laws."""

from __future__ import annotations

import re
from collections import Counter

import pymupdf
import pymupdf4llm

# Running footers General Code prints on attachment pages, e.g. "173 Attachment 1:2".
FOOTER_RE = re.compile(r"^\s*[\w-]+ Attachment \d+(?::\d+)?\s*$", re.I)


def _norm(line: str) -> str:
    return re.sub(r"[#*_\s]+", " ", line).strip().lower()


PICTURE_MARK = re.compile(r"<!--\s*(?:Start|End) of picture text\s*-->|\**-+\s*(?:Start|End) of picture text\s*-+\**", re.I)


def _clean_picture_text(line: str) -> str:
    """Drop pymupdf4llm's picture-text markers; text OCR'd from images stays."""
    if not PICTURE_MARK.search(line):
        return line
    line = PICTURE_MARK.sub("", line)
    return re.sub(r"\s+", " ", line.replace("<br>", " ")).strip()


def pdf_pages_markdown(data: bytes) -> list[str]:
    """Return one Markdown string per page, with running headers/footers removed."""
    doc = pymupdf.open(stream=data, filetype="pdf")
    pages = [p["text"] for p in pymupdf4llm.to_markdown(doc, page_chunks=True, show_progress=False)]
    if len(pages) >= 2:
        seen = Counter()
        for p in pages:
            seen.update({_norm(ln) for ln in p.splitlines() if _norm(ln) and not ln.lstrip().startswith("|")})
        repeated = {k for k, v in seen.items() if v > len(pages) / 2 and len(k) < 60}
    else:
        repeated = set()
    out = []
    for p in pages:
        keep = [
            ln
            for ln in p.splitlines()
            if not FOOTER_RE.match(ln.replace("*", "").replace("_", "").replace("#", "").strip())
            and _norm(ln) not in repeated
        ]
        keep = [_clean_picture_text(ln) for ln in keep]
        text = re.sub(r"\n{3,}", "\n\n", "\n".join(keep)).strip()
        out.append(text)
    return out

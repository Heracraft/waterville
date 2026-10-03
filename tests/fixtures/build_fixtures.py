"""Rebuild tests/fixtures/search_docs.json from real rows of output/chunks.jsonl.

FAKE_AZURE=1 serves these rows in place of Azure AI Search, so the UI, the
e2e tests and screenshots run with real code text and no Azure access.

    uv run python tests/fixtures/build_fixtures.py
"""

from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CHUNKS = ROOT / "output" / "chunks.jsonl"
OUT = Path(__file__).with_name("search_docs.json")
# Rows that output/chunks.jsonl does not hold (it is the eCode export only):
# 30-A M.R.S. § 4452, two chunks of M.R. Civ. P. 80K, one city form and one
# staff note, taken from `python -m ecode.state` output. Appended as they are.
EXTRA = Path(__file__).with_name("extra_docs.json")

# Whole chapters an inspector touches every week.
CHAPTERS = {"1", "115", "127", "205", "215"}
# Zoning and licensing sections behind the top public questions and the
# enforcement chain (fences, sheds, chickens, home occupations, permits,
# nonconformity, violations and penalties).
CITATIONS = {
    "Chapter 275. Zoning",
    "§ 275-1.1", "§ 275-1.6", "§ 275-2.1", "§ 275-3.2", "§ 275-4.5", "§ 275-4.6",
    "§ 275-4.7", "§ 275-4.14", "§ 275-4.33", "§ 275-5.1", "§ 275-5.2", "§ 275-5.3",
    "§ 275-6.1", "§ 275-6.2", "§ 275-6.3", "§ 275-6.4", "§ 275-7.1",
    "§ 173-1.1", "§ 173-1.2", "§ 173-10.1",
    "§ 210-10", "§ 232-1",
}
KEEP = (
    "id", "doc_id", "source_type", "node_type", "title", "citation", "breadcrumb", "url",
    "content", "chapter_number", "chapter_title", "article", "section_number", "section_title",
    "page_start", "page_end", "chunk_index", "chunk_count", "legislation_through",
)


def main() -> None:
    docs = []
    attachments = 0
    for line in CHUNKS.read_text().splitlines():
        row = json.loads(line)
        st = row.get("source_type")
        take = (
            st == "new_law"
            or (st == "code" and (row.get("chapter_number") in CHAPTERS or row.get("citation") in CITATIONS))
        )
        if st == "attachment" and attachments < 4 and "Zoning" in (row.get("citation") or ""):
            take = True
            attachments += 1
        if take:
            docs.append({k: row.get(k) for k in KEEP})
    if EXTRA.exists():
        seen = {d["id"] for d in docs}
        docs += [d for d in json.loads(EXTRA.read_text()) if d["id"] not in seen]
    OUT.write_text(json.dumps(docs, indent=1, ensure_ascii=False) + "\n")
    print(f"wrote {len(docs)} docs to {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()

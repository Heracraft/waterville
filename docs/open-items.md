# Open items: corpus expansion

Status on 2026-10-02. The state sources from the September 29 kickoff email are in the live index (commit `fa563cf`, refresh job run on 2026-10-02). These items remain.

| # | Item | Owner | Priority |
| --- | --- | --- | --- |
| 1 | Better labels on state manual chunks | Developer | Low |
| 2 | Ask the city about an ICC license | Project team | Medium |
| 3 | Find the 2000 energy manual | Project team | Low |
| 4 | Delete the `state-sources` branch and worktree | Developer | Low |

## 1. Better labels on state manual chunks

**Status: done (2026-10-03).** `ecode/headings.py` works out a heading trail for each manual page, and `ecode/state.py` adds it to the chunk header and `breadcrumb`, for example `Court Rule 80K Manual (2017) > Chapter Four: How to Prepare the Land Use Citation and Complaint > B. Required Attachments, page 24`. It reaches the index on the next refresh. See "Changes" in `docs/staff-preview-spec.md`.

**Problem.** Chunks from the state manuals show up in answers to unrelated city questions. For example, a question about backyard chickens returns two chunks from the Shoreland Zoning Manual (2008). The model ignores them, so the answers are correct. But these chunks use search slots that better sources could use.

**Cause.** Each manual chunk has only the manual name and a page number in its header and `breadcrumb`. For example: `Shoreland Zoning Manual (2008), page 24`. The semantic ranker cannot tell what the chunk is about from this header.

**Fix.**
1. In `ecode/state.py`, in `StateExporter._pdf`, read the Markdown headings (`#`, `##`, `###`) that `pdf_pages_markdown` returns.
2. Keep the most recent heading at each level as you go through the pages.
3. Add these headings to the chunk header and `breadcrumb`. For example: `Shoreland Zoning Manual (2008) > Chapter 3: Nonconforming Structures, page 24`.
4. Do the same for the `.docx` rule (06-096 CMR ch. 1000). Its headings use the `RulesHeader` and `RulesChapterTitle` styles.
5. Run `uv run python -m ecode --out <dir>` and look at the breadcrumbs of 10 chunks from different manuals.
6. Run `uv run python -m ecode.azure validate --chunks <dir>/chunks.jsonl`.
7. Commit to master. Ask the person who deploys to rebuild the image and start the refresh job.

**Test.** After the refresh, ask the live site about backyard chickens. No state manual chunks should appear in the sources. Then ask about shoreland zoning penalties. The answer must still cite § 275-6.1 and 30-A M.R.S. § 4452.

**Note.** The app now searches city sources and state sources separately (commit `b3915b4`). This change stops state chunks from pushing out city chunks. It does not stop weak state chunks from filling the state slots.

## 2. Ask the city about an ICC license

**Problem.** The assistant cannot quote the building codes that Maine adopts: the 2021 IRC, IBC, IEBC, IECC and IMC. The International Code Council (ICC) owns the text. The ICC site gives a free read-only view, but its terms do not let us copy the text. The corpus has a short reference entry for each code. Each entry names the state rule that adopts the code and links to the ICC viewer.

**Action.** Ask Nathan Bernard (City of Waterville) these questions:
1. Does the city have an ICC Digital Codes Premium subscription?
2. If yes, do its terms let us put code text in a search index for a public assistant?

**If the answer is yes to both,** add each licensed code as a new source in `ecode/state_sources.toml` with `tier = "ingest"`. We will also need a way to get the text, because the ICC viewer does not offer downloads.

**If the answer is no,** keep the reference entries. No change is necessary.

The same limit applies to the 2021 Uniform Plumbing Code (IAPMO), ASHRAE 62.1, 62.2 and 90.1, and ASTM E1465-08.

## 3. Find the 2000 energy manual

**Problem.** The email linked "Building Standards: Energy Conservation" (`energy_man.pdf`) on the old DECD site. This file is not on maine.gov, not on the MOCA publications page, and not in the Wayback Machine.

**Impact.** Low. The 2021 IECC and 16-642 CMR ch. 6 replace it, and both are in the corpus (the IECC as a reference entry).

**Action.** If the team needs this manual, ask the city or MOCA for a copy. If you get the file:
1. Put it in `ecode/archived/`.
2. In `ecode/state_sources.toml`, change the `decd-energy-manual` entry: set `tier = "ingest"` and add `file = "archived/<name>.pdf"`.
3. Rebuild and refresh as in item 1, steps 5 to 7.

## 4. Delete the `state-sources` branch and worktree

The work on branch `state-sources` is in master. The worktree at `~/waterville-state` holds a copy of the HTTP cache and nothing else of value. To delete both:

```bash
git -C ~/waterville worktree remove --force ~/waterville-state
git -C ~/waterville branch -d state-sources
```

## Watch item: refresh job time

The refresh job ran in 22 minutes with the state sources. Its time limit is now 2 hours (commit `443bb01`). If the job time goes above 1 hour, look first at the PDF conversion step. The state PDFs have about 1,200 pages and take about 9 minutes on one CPU.

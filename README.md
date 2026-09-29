# Waterville, ME Code for Azure RAG

This repo scrapes the City of Waterville, ME municipal code from eCode360 (https://ecode360.com/WA3904) and turns it into files you can load straight into Azure AI Search for retrieval-augmented generation.

The `output/` folder holds the finished export. You only need to re-run the scraper when the city adopts new legislation.

## What gets collected

| Source | Where it comes from | Output |
| --- | --- | --- |
| The Charter, 38 code chapters and the Disposition List | `/print/WA3904?guid=<chapter>&children=true`, which returns a chapter's full text | `output/markdown/code/*.md` |
| 39 PDF attachments (fee schedules, committee charges, personnel policies, the sex offender address exclusion list, subdivision appendix, and more) | `/attachment/...pdf` links inside chapters | `output/pdf/attachments/`, `output/markdown/attachments/*.md` |
| New Laws (adopted but not yet codified) | `/WA3904/laws` | `output/pdf/new-laws/`, `output/markdown/new-laws/*.md` |

The site's Law Ledger for this code is empty, and Waterville has no Public Documents section, so neither produces files.

## Output files

- `output/chunks.jsonl`: the retrieval units, one JSON object per line. Each object already matches the Azure AI Search index schema in `azure/index.json` (minus the vector, which the push script adds). This is the file to index.
- `output/markdown/**.md`: one Markdown file per source document with YAML front matter. Use these if you prefer Azure's blob indexer or the portal's "Import and vectorize data" wizard, or to read the code as plain text.
- `output/pdf/**`: original PDFs, kept so you can reprocess them with Azure AI Document Intelligence if you want its layout model instead of the text extraction done here.
- `output/documents.jsonl`: one line per source document with its metadata and chunk count.
- `output/manifest.json`: crawl date, "legislation through" date, counts, token stats and the completeness check result.

### How chunks are built

A code section is the natural retrieval unit, so each section becomes one chunk. Sections longer than 800 tokens (cl100k, the tokenizer of the `text-embedding-3` models) are split at subsection boundaries. When a split lands inside a list, the previous short item repeats at the top of the next chunk so a lead-in sentence travels with its items. Long tables split by rows and repeat the header row in each piece. PDFs are chunked page by page and every chunk records `page_start` and `page_end`.

Every chunk's `content` starts with a two-line context header, for example:

```
City of Waterville, ME Code
Chapter 275. Zoning > Article III. Definitions > § 275-3.2. Additional definitions. (part 4 of 15)
```

That header goes into the embedding, so a chunk holding one definition still matches queries about zoning. It also lets the LLM cite the section without looking up metadata.

Useful metadata fields for filters, facets and citations: `citation` (such as `§ 275-3.2` or `Charter Art. IV, § 9`), `chapter_number`, `chapter_title`, `article`, `section_number`, `url` (deep link to the section on eCode360), `ordinances` (ordinance numbers from the section history), `source_type` (`code`, `attachment`, `new_law`), `page_start`/`page_end` for PDFs, and `legislation_through`.

## Loading into Azure AI Search

Option 1 pushes documents with vectors you generate through Azure OpenAI. You need an Azure AI Search service (Basic tier or higher for semantic ranker) and an Azure OpenAI embedding deployment.

```bash
export AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
export AZURE_SEARCH_API_KEY=<admin key>
export AZURE_SEARCH_INDEX=waterville-code
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_KEY=<key>
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<deployment name>
export AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large   # or text-embedding-3-small
# export EMBEDDING_DIMENSIONS=1536                            # optional, shrinks 3-large vectors

uv run python -m ecode.azure validate   # checks every document against the schema, no network
uv run python -m ecode.azure push       # creates the index, embeds, uploads
```

`push` creates the index with hybrid search in mind: BM25 on `content`, `title` and `breadcrumb` (English Microsoft analyzer), an HNSW cosine vector field, a semantic ranker configuration, and an Azure OpenAI vectorizer so queries can be vectorized server side. Embeddings are cached in `output/embeddings-cache-*.jsonl`, so a re-run after a code update only pays for changed chunks. Pass `--recreate` to drop and rebuild the index, which you need after changing the embedding model or dimensions.

For the best answers, query with hybrid search plus the semantic ranker (`queryType=semantic`, `semanticConfiguration=default`, a text query and a `vectorQueries` entry of kind `text` against `content_vector`). Azure AI Foundry "On your data" and Azure OpenAI "Add your data" can point at the same index; map `content` as the content field, `title` as title, `url` as URL and `content_vector` as the vector field.

Option 2 skips the script. Upload `output/chunks.jsonl` to a blob container and create an indexer with `"parsingMode": "jsonLines"` targeting the same index definition, plus a skillset with the `AzureOpenAIEmbedding` skill writing to `content_vector`. Or upload `output/markdown/` and run the portal's "Import and vectorize data" wizard, which chunks for you but drops the per-section metadata.

`azure/index.json` is the index definition with placeholder vectorizer settings; regenerate it with `uv run python -m ecode.azure schema --out azure/index.json`.

## Re-running the scraper

```bash
uv sync
uv run python -m ecode --refresh      # re-download everything and rebuild output/
```

Without `--refresh` the scraper reuses the HTTP cache in `data/raw/` (not committed). It waits 1.5 seconds between requests and backs off on HTTP 429.

The run also checks completeness. It walks the site's own navigation (chapter pages, then article and part pages) to collect every section ID eCode360 lists, and compares that set with the sections parsed from the print pages. `manifest.json` records both counts, and the command exits non-zero if any section is missing or unexpected. Pass `--no-verify` to skip this and save about 200 requests.

## Code layout

- `ecode/fetch.py`: HTTP with a disk cache, rate limit and retries.
- `ecode/parse.py`: table of contents parsing and the HTML to Markdown converter for chapter print pages (nested subsections, definitions, tables with row and column spans, footnotes, history notes, attachments).
- `ecode/pdf.py`: PDF to Markdown via `pymupdf4llm`, with running headers and footers removed.
- `ecode/chunk.py`: token-aware chunk packing.
- `ecode/export.py`: the pipeline and the writers for all output files.
- `ecode/azure.py`: Azure AI Search index schema, validation and push.

Other eCode360 codes should work with `--customer <ID>`, though only WA3904 has been tested. The index name, "Waterville" in the defaults and the chunk header text come from the site, so change `AZURE_SEARCH_INDEX` for another code.

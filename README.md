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

## Deploying the public assistant to Azure

`infra/` deploys a public question-answering site on top of the index. Everything runs in one resource group:

- **Azure AI Search** (Basic, semantic ranker on the standard plan) holds the index.
- **Azure OpenAI** runs two deployments: `embedding` (text-embedding-3-large) and `chat`. Key auth is disabled on the account.
- **Container Apps** runs `waterville-app`, the FastAPI chat API that also serves the web UI from `app/web/`. It scales from 0 to 2 replicas.
- **A Container Apps job** (`waterville-refresh`) re-crawls eCode360 every Monday at 07:00 UTC, checks completeness and updates the index. It also deletes sections that disappeared from the code. If the crawl comes back incomplete, the job fails before touching the index.
- **Azure Container Registry** (Basic) stores the image, and **Log Analytics** stores the logs.

The app and the job each get their own user-assigned managed identity. The app can only read the index and call the chat model. The job can write the index and call the embedding model. The search service calls Azure OpenAI with its own identity to vectorize queries, so no keys exist anywhere.

### One-time setup (your laptop, Azure CLI signed in)

```bash
SUB=$(az account show --query id -o tsv)
az group create -n rg-waterville-rag -l eastus2
az ad sp create-for-rbac --name sp-waterville-rag --role Contributor \
  --scopes /subscriptions/$SUB/resourceGroups/rg-waterville-rag
az role assignment create --assignee <appId> --role "Role Based Access Control Administrator" \
  --scope /subscriptions/$SUB/resourceGroups/rg-waterville-rag
for ns in Microsoft.Search Microsoft.CognitiveServices Microsoft.App Microsoft.ContainerRegistry \
          Microsoft.OperationalInsights Microsoft.ManagedIdentity; do az provider register --namespace $ns; done
```

Check Azure OpenAI quota for the region in the Foundry portal (ai.azure.com, Quotas).

### Deploy

```bash
export AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=... AZURE_TENANT_ID=... AZURE_SUBSCRIPTION_ID=...
infra/deploy.sh
```

The script needs `az`, `docker` and `jq`. It:
1. picks a chat model with free quota in the region (gpt-5-mini, then gpt-4.1-mini, then gpt-4o-mini; override with `CHAT_MODEL`)
2. deploys the infrastructure, builds the image and pushes it to the registry
3. deploys the app and job
4. on the first deploy, runs the refresh job to load the index (about 10 minutes)
5. asks the live site a test question

Re-running it updates everything in place. `REFRESH=1 infra/deploy.sh` forces a re-crawl. To refresh the index without redeploying, run `az containerapp job start -g rg-waterville-rag -n waterville-refresh`.

### Abuse and cost controls

The site has no login, so the API limits itself:
- 6 questions per minute and 60 per day per IP address
- 3,000 questions per day in total
- questions capped at 1,000 characters

Change these with the `RATE_LIMIT_PER_MINUTE`, `RATE_LIMIT_PER_DAY`, `GLOBAL_LIMIT_PER_DAY` and `MAX_QUESTION_CHARS` environment variables on the container app. The chat deployment's capacity (`CHAT_CAPACITY`, default 50K tokens per minute) sets a hard ceiling on spend, because Azure rejects requests above it. Azure OpenAI's default content filter stays on.

Expected fixed cost is about $85 to $100 a month, mostly AI Search Basic. Model usage comes on top and depends on traffic.

### Running the app locally

```bash
export AZURE_SEARCH_ENDPOINT=... AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_CHAT_DEPLOYMENT=chat
# Uses your az login (DefaultAzureCredential); or set AZURE_SEARCH_API_KEY / AZURE_OPENAI_API_KEY
uv run uvicorn app.main:app --reload
```

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
- `ecode/azure.py`: Azure AI Search index schema, validation and push (API keys or Entra ID).
- `app/main.py`: the public chat API (hybrid search, semantic ranker, streamed answers with citations, rate limits).
- `app/web/`: the web UI, plain HTML, CSS and JS.
- `infra/main.bicep`, `infra/deploy.sh`, `infra/refresh.sh`, `Dockerfile`: the Azure deployment.

Other eCode360 codes should work with `--customer <ID>`, though only WA3904 has been tested. The index name, "Waterville" in the defaults and the chunk header text come from the site, so change `AZURE_SEARCH_INDEX` for another code.

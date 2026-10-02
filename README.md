# Waterville, ME Code for Azure RAG

Live site: https://waterville-app.greensky-a20028bf.eastus2.azurecontainerapps.io

This repository has three parts:

1. A scraper. It gets the municipal code of the City of Waterville, ME from eCode360 (https://ecode360.com/WA3904). It also gets the related Maine state law, rules and guidance.
2. An export. The scraper writes files that you can load into Azure AI Search for retrieval-augmented generation (RAG).
3. A public question-and-answer site. It uses the search index to answer questions about the code.

The `output/` folder contains the completed export. Run the scraper again only when the city adopts new legislation.

## Collected sources

| Source | Location on eCode360 | Output |
| --- | --- | --- |
| The Charter, 38 code chapters and the Disposition List | `/print/WA3904?guid=<chapter>&children=true`. This page gives the full text of a chapter. | `output/markdown/code/*.md` |
| 39 PDF attachments. Examples: fee schedules, committee charges, personnel policies, the sex offender address exclusion list, the subdivision appendix. | `/attachment/...pdf` links in the chapters | `output/pdf/attachments/`, `output/markdown/attachments/*.md` |
| New Laws (adopted, but not yet in the code) | `/WA3904/laws` | `output/pdf/new-laws/`, `output/markdown/new-laws/*.md` |

The Law Ledger for this code is empty. Waterville has no Public Documents section. Thus these two parts of the site give no files.

### Maine state sources

The file `ecode/state_sources.toml` lists the state sources. The list comes from the project kickoff materials. It contains:

- 26 statute sections from Titles 17, 25, 30-A and 38, as HTML from legislature.maine.gov
- the seven chapters of the Maine Uniform Building and Energy Code (16-642 CMR)
- the subsurface wastewater rule (10-144 CMR ch. 241)
- the shoreland zoning guidelines (06-096 CMR ch. 1000)
- nine manuals for code enforcement officers

Some model codes have a copyright (ICC, UPC, ASHRAE, ASTM). For each of these codes, the scraper writes one short stub chunk. The stub tells which state rule adopts the code. It also gives a link to the free viewer of the publisher. The stub does not contain the text of the code.

To add a source:

1. Add a `[[source]]` entry to `ecode/state_sources.toml`.
2. Set `kind` to `statute`, `rule`, `guidance` or `model_code`.
3. Set `tier` to `ingest`, `reference` or `skip`.
4. If the state no longer hosts the file, put the file in `ecode/archived/`. Then refer to it with `file`.

State chunks have IDs that start with `ext-`. The scraper writes them to `output/markdown/state/` and `output/pdf/state/`. The scraper gets the state sources again on each run. To skip them, use `--no-state`.

## Output files

- `output/chunks.jsonl`: the retrieval units, one JSON object per line. Each object agrees with the Azure AI Search index schema in `azure/index.json`. Only the vector is missing; the push script adds it. Index this file.
- `output/markdown/**.md`: one Markdown file for each source document, with YAML front matter. Use these files with the Azure blob indexer or the "Import and vectorize data" wizard in the portal. You can also read the code as plain text in these files.
- `output/pdf/**`: the original PDFs. You can process them again with Azure AI Document Intelligence if you prefer its layout model.
- `output/documents.jsonl`: one line for each source document, with its metadata and its number of chunks.
- `output/manifest.json`: the crawl date, the "legislation through" date, counts, token statistics and the result of the completeness check.

### Chunk structure

Each code section becomes one chunk. The rules for long content are:

- If a section has more than 800 tokens, the scraper divides it at subsection boundaries. (The token count uses cl100k, the tokenizer of the `text-embedding-3` models.)
- If a division occurs in a list, the next chunk starts with the previous short item. Thus the lead-in sentence stays with its items.
- Long tables are divided by rows. Each part repeats the header row.
- PDFs are divided by page. Each chunk records `page_start` and `page_end`.

The `content` of each chunk starts with a header of two lines. Example:

```
City of Waterville, ME Code
Chapter 275. Zoning > Article III. Definitions > § 275-3.2. Additional definitions. (part 4 of 15)
```

The embedding includes this header. Thus a chunk with only one definition still matches queries about zoning. The LLM can also cite the section without the metadata.

Use these metadata fields for filters, facets and citations:

- `citation`, for example `§ 275-3.2` or `Charter Art. IV, § 9`
- `chapter_number`, `chapter_title`, `article`, `section_number`
- `url`: a direct link to the section on eCode360
- `ordinances`: the ordinance numbers from the section history
- `source_type`: `code`, `attachment`, `new_law`, `state_statute`, `state_rule`, `state_guidance` or `model_code_ref`
- `page_start` and `page_end` for PDFs
- `legislation_through`

## Load the export into Azure AI Search

### Option 1: Use the push script

The push script makes the vectors with Azure OpenAI and uploads the documents. You must have:

- an Azure AI Search service. Use the Basic tier or higher for the semantic ranker.
- an Azure OpenAI embedding deployment.

```bash
export AZURE_SEARCH_ENDPOINT=https://<service>.search.windows.net
export AZURE_SEARCH_API_KEY=<admin key>
export AZURE_SEARCH_INDEX=waterville-code
export AZURE_OPENAI_ENDPOINT=https://<resource>.openai.azure.com
export AZURE_OPENAI_API_KEY=<key>
export AZURE_OPENAI_EMBEDDING_DEPLOYMENT=<deployment name>
export AZURE_OPENAI_EMBEDDING_MODEL=text-embedding-3-large   # or text-embedding-3-small
# export EMBEDDING_DIMENSIONS=1536                            # optional, makes 3-large vectors smaller

uv run python -m ecode.azure validate   # checks each document against the schema, no network
uv run python -m ecode.azure push       # creates the index, embeds, uploads
```

`push` makes an index for hybrid search. The index has:

- BM25 on `content`, `title` and `breadcrumb`, with the English Microsoft analyzer
- an HNSW vector field with cosine distance
- a semantic ranker configuration
- an Azure OpenAI vectorizer. The search service uses it to make query vectors.

The script keeps the embeddings in `output/embeddings-cache-*.jsonl`. After a code update, the script embeds only the changed chunks. If you change the embedding model or the dimensions, you must delete and make the index again. To do this, use `--recreate`.

For the best answers, use hybrid search with the semantic ranker:

- `queryType=semantic`
- `semanticConfiguration=default`
- a text query
- a `vectorQueries` entry of kind `text` against `content_vector`

You can also connect Azure AI Foundry "On your data" or Azure OpenAI "Add your data" to the same index. Set these field mappings:

| Setting | Field |
| --- | --- |
| Content | `content` |
| Title | `title` |
| URL | `url` |
| Vector | `content_vector` |

### Option 2: Use an indexer

This option does not use the script. Do one of these procedures:

- Upload `output/chunks.jsonl` to a blob container. Make an indexer with `"parsingMode": "jsonLines"` and the same index definition. Add a skillset with the `AzureOpenAIEmbedding` skill. Set the skill to write to `content_vector`.
- Upload `output/markdown/`. Run the "Import and vectorize data" wizard in the portal. The wizard makes its own chunks, but it does not keep the metadata of each section.

`azure/index.json` is the index definition. Its vectorizer settings are placeholders. To make it again, run `uv run python -m ecode.azure schema --out azure/index.json`.

## Deploy the public site to Azure

The `infra/` folder deploys a public question-and-answer site that uses the index. All resources are in one resource group:

- **Azure AI Search** (Basic, semantic ranker on the standard plan) contains the index.
- **Azure OpenAI** has two deployments: `embedding` (text-embedding-3-large) and `chat`. Key authentication is off for the account.
- **Container Apps** runs `waterville-app`. This is the FastAPI chat API. It also serves the web UI from `app/web/`. It scales from 0 to 2 replicas.
- **A Container Apps job** (`waterville-refresh`) runs each Monday at 07:00 UTC. The job crawls eCode360 again, does the completeness check and updates the index. It also deletes sections that the code no longer contains. If the crawl is not complete, the job stops before it changes the index.
- **Azure Container Registry** (Basic) keeps the image. **Log Analytics** keeps the logs.

The app and the job each have a user-assigned managed identity:

| Identity | Index access | Model access |
| --- | --- | --- |
| App | Read | Chat model |
| Job | Write | Embedding model |

The search service uses its own identity to call Azure OpenAI for query vectors. Thus the deployment uses no keys.

### One-time setup

Do these steps on your computer, with the Azure CLI signed in.

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

Make sure that the region has Azure OpenAI quota. To see the quota, go to the Foundry portal (ai.azure.com) and open Quotas.

### Deploy

```bash
export AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=... AZURE_TENANT_ID=... AZURE_SUBSCRIPTION_ID=...
infra/deploy.sh
```

The script must have `az`, `docker` and `jq`. The script does these steps:

1. It finds a chat model with free quota in the region. It tries gpt-5-mini, then gpt-4.1-mini, then gpt-4o-mini. To select a different model, set `CHAT_MODEL`.
2. It deploys the infrastructure.
3. It builds the image and pushes it to the registry.
4. It deploys the app and the job.
5. On the first deploy, it starts the refresh job to load the index. This takes approximately 10 minutes.
6. It sends a test question to the live site.

You can run the script again. It updates all resources in place.

- To crawl again during the deploy, run `REFRESH=1 infra/deploy.sh`.
- To update the index without a deploy, run `az containerapp job start -g rg-waterville-rag -n waterville-refresh`.

### Abuse and cost controls

The site has no login. Thus the API applies these limits:

| Limit | Default | Environment variable |
| --- | --- | --- |
| Questions per minute, for each IP address | 6 | `RATE_LIMIT_PER_MINUTE` |
| Questions per day, for each IP address | 60 | `RATE_LIMIT_PER_DAY` |
| Questions per day, total | 3,000 | `GLOBAL_LIMIT_PER_DAY` |
| Characters per question | 1,000 | `MAX_QUESTION_CHARS` |

To change a limit, set its environment variable on the container app.

The capacity of the chat deployment (`CHAT_CAPACITY`, default 50K tokens per minute) sets a maximum on cost. Azure refuses requests above this capacity. The default content filter of Azure OpenAI stays on.

The fixed cost is approximately $85 to $100 each month. Most of this cost is AI Search Basic. The cost of model usage is in addition to this amount. It changes with traffic.

### Run the app on your computer

```bash
export AZURE_SEARCH_ENDPOINT=... AZURE_OPENAI_ENDPOINT=... AZURE_OPENAI_CHAT_DEPLOYMENT=chat
# Uses your az login (DefaultAzureCredential); or set AZURE_SEARCH_API_KEY / AZURE_OPENAI_API_KEY
uv run uvicorn app.main:app --reload
```

## Run the scraper again

```bash
uv sync
uv run python -m ecode --refresh      # downloads all pages again and makes output/ again
```

If you do not use `--refresh`, the scraper uses the HTTP cache in `data/raw/`. Git does not track this folder. The scraper waits 1.5 seconds between requests. If it gets HTTP 429, it waits longer before the next request.

Each run also does a completeness check:

1. The scraper follows the navigation of the site: first the chapter pages, then the article and part pages.
2. It collects each section ID that eCode360 lists.
3. It compares these IDs with the sections that it got from the print pages.

`manifest.json` records the two counts. If a section is missing or unexpected, the command exits with a non-zero code. To skip the check, use `--no-verify`. This saves approximately 200 requests.

## Code layout

- `ecode/fetch.py`: HTTP with a disk cache, a rate limit and retries.
- `ecode/parse.py`: parses the table of contents. Converts the HTML of the chapter print pages to Markdown. Supports nested subsections, definitions, tables with row and column spans, footnotes, history notes and attachments.
- `ecode/pdf.py`: converts PDF to Markdown with `pymupdf4llm`. Removes the headers and footers that repeat on each page.
- `ecode/chunk.py`: puts text into chunks by token count.
- `ecode/export.py`: the pipeline, and the writers for all output files.
- `ecode/azure.py`: the Azure AI Search index schema, validation and push. Supports API keys or Entra ID.
- `app/main.py`: the public chat API. It does hybrid search with the semantic ranker, streams answers with citations and applies rate limits.
- `app/web/`: the web UI, in plain HTML, CSS and JS.
- `infra/main.bicep`, `infra/deploy.sh`, `infra/refresh.sh`, `Dockerfile`: the Azure deployment.

Other eCode360 codes possibly work with `--customer <ID>`. We tested only WA3904. The index name, the name "Waterville" in the defaults and the text of the chunk header come from the site. For a different code, change `AZURE_SEARCH_INDEX`.

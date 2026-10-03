# Preview deployment

The preview runs the staff desk and the new public tools next to production, so the city can try them before production changes. Azure Container Apps has no preview button like Coolify's. The preview is a second container app in the same Container Apps environment, with its own identities, storage, search index and secrets.

| | Production | Preview |
|---|---|---|
| Container app | `waterville-app` | `waterville-preview` (0 to 1 replica) |
| Refresh job | `waterville-refresh`, Mondays 07:00 UTC | `waterville-preview-refresh`, manual only |
| Search index | `waterville-code` | `waterville-code-preview` |
| Identities | `waterville-app-id`, `waterville-refresh-id` | `waterville-preview-id`, `waterville-preview-refresh-id` |
| Store | none | storage account `wvpreview<suffix>` (tables) |
| `APP_ENV` | unset (production) | `preview` |
| Template | `infra/main.bicep` | `infra/preview.bicep` |
| Script | `infra/deploy.sh` | `infra/deploy-preview.sh` |

Shared and left unchanged: the environment `waterville-env`, the registry, the AI Search service, the Azure OpenAI account with its `chat` and `embedding` deployments, and the Log Analytics workspace. `preview.bicep` declares each of them `existing`. It adds role assignments on them for the preview identities and changes nothing else.

## Deploy

```bash
export AZURE_CLIENT_ID=... AZURE_CLIENT_SECRET=... AZURE_TENANT_ID=... AZURE_SUBSCRIPTION_ID=...
infra/deploy-preview.sh --what-if   # read only: what would change
infra/deploy-preview.sh             # build, push, deploy, load the index, smoke test
```

Use the same service principal as `infra/deploy.sh` (Contributor and Role Based Access Control Administrator on `rg-waterville-rag`). You need `az`, `docker`, `jq`, `curl` and `uv`.

The script runs these steps:

1. It signs in and finds the existing environment, registry, search service, OpenAI account and workspace in the resource group. It reads the chat model from the `chat` deployment and sets reasoning effort `low` for gpt-5 and o-series models, as `deploy.sh` does.
2. It records production's revision and image (`waterville-app`, `waterville-refresh`).
3. It prepares the secrets (see "Staff accounts").
4. It builds the image from the working tree, tags it `preview-<commit>` (plus `-dirty-<time>` with uncommitted changes) and pushes it to the existing registry. Production keeps its own tag.
5. It runs `az deployment group what-if` on `preview.bicep`. It stops if any change is not a new resource or a preview resource, and it stops on any delete.
6. It deploys `preview.bicep` as deployment `waterville-preview` in incremental mode.
6a. It creates or updates the definition of `waterville-code-preview` itself (`python -m ecode.azure ensure-index`, with the search admin key passed in the environment of that one command, or the service principal's token when keys are off). It then grants the refresh job's identity Search Index Data Contributor on that index only (scope `.../searchServices/NAME/indexes/waterville-code-preview`) and removes any service-wide search role an earlier version gave the job.
7. It starts the preview refresh job when that job has never succeeded (`REFRESH=auto`), and waits 20 to 40 minutes while it crawls eCode360 and the state and City sources into `waterville-code-preview`. `REFRESH=1` always runs it and `REFRESH=0` never does.
8. Smoke test: `/healthz` (the first request wakes a scaled-to-zero app in about 20 seconds), `X-Robots-Tag: noindex` on `/`, `/staff/login`, one public question, then a staff sign-in, `/api/staff/me` reporting `env: preview`, a staff-mode answer and sign-out.
9. It checks that production still has the revision and image recorded in step 2, and fails loudly if not.

The script never deploys `main.bicep` and never updates `waterville-app` or `waterville-refresh`. Run it again to update the preview in place.

| Variable | Default | Meaning |
|---|---|---|
| `RESOURCE_GROUP` | `rg-waterville-rag` | |
| `IMAGE` | build one | deploy this image instead |
| `STAFF_USERS` | saved, else a demo account | see "Staff accounts" |
| `SESSION_SECRET` | saved, else generated | cookie signing key |
| `PREVIEW_CREDENTIALS` | `~/waterville-preview-credentials.txt` | where the demo password goes |
| `PREVIEW_STATE_DIR` | `~/.config/waterville-preview` | generated secrets kept between runs |
| `MIN_REPLICAS` | `0` | `1` keeps the preview warm (costs a replica around the clock) |
| `REFRESH` | `auto` | `1` always runs the refresh job, `0` never |
| `SMOKE` | `1` | `0` skips the smoke test |
| `STAFF_LOGIN_USER`, `STAFF_LOGIN_PASSWORD` | demo account | staff account for the smoke test |

### What-if on 2026-10-03

Against the live resource group, before any preview existed: 24 resources to create, 9 existing resources ignored, nothing modified or deleted.

```
Create  Microsoft.App/containerApps/waterville-preview
Create  Microsoft.App/jobs/waterville-preview-refresh
Create  Microsoft.ManagedIdentity/userAssignedIdentities/waterville-preview-id
Create  Microsoft.ManagedIdentity/userAssignedIdentities/waterville-preview-refresh-id
Create  Microsoft.Storage/storageAccounts/wvpreviewkhyesf4lvm3yo (+ tableServices/default, 7 tables, 1 diagnostic setting)
Create  10 role assignments (2 on the registry, 4 on AI Search, 2 on Azure OpenAI, 2 on the storage account)

Since then the job's three service-wide AI Search roles left the template (see "Security and data"), so the
template now creates 7 role assignments and the script adds one on the preview index.
Ignore  waterville-app, waterville-refresh, waterville-env, waterville-openai-..., watervilleacr..., waterville-app-id,
        waterville-refresh-id, waterville-logs-..., waterville-search-...
```

## Staff accounts

`STAFF_USERS` is a JSON object of username to scrypt hash. Make an entry per person:

```bash
uv run python -m app.auth hash dbradstreet          # asks for the password, prints {"dbradstreet": "scrypt$..."}
```

Merge the entries into one object and deploy with it:

```bash
STAFF_USERS='{"dbradstreet": "scrypt$...", "abradstreet": "scrypt$..."}' infra/deploy-preview.sh
```

With no `STAFF_USERS` and nothing saved, the first deploy creates one demo account, `inspector`, with a random password. It writes the URL, username and password to `~/waterville-preview-credentials.txt` (mode 600, outside the repository) and keeps the hash in `~/.config/waterville-preview/staff-users.json`, so later deploys keep the same password. `SESSION_SECRET` is generated once and kept in the same folder; changing it signs everyone out. Both reach the app as Container App secrets (`staff-users`, `session-secret`). The script passes them to Azure through a temporary parameters file with mode 600, never on a command line.

To remove the demo account, deploy with your own `STAFF_USERS` and delete the two saved files and the credentials file.

## Security and data

- The preview is public on its `*.azurecontainerapps.io` address, like production, and answers every request with `X-Robots-Tag: noindex`. Staff pages need a sign-in. Pages refuse framing except `/embed`.
- The session cookie is `Secure`, so the preview works only over HTTPS. Container Apps ingress gives HTTPS and refuses plain HTTP (`allowInsecure: false`).
- The app identity can read the search service, call the model and read and write its own tables. It cannot write any index.
- The refresh job crawls the internet, so its identity is kept narrow. Its one search role is Search Index Data Contributor on `waterville-code-preview` (an index-scoped assignment the deploy script makes); it has no role on the service or on `waterville-code`, so it cannot change or delete the production index. It runs with `SEARCH_INDEX_UPDATE=never` and never sends the index definition; the deploy script does that. Its table role (Storage Table Data Contributor) covers the `changes` table only, so it cannot read or change cases, drafts, saved answers, feedback or the question log. The template also refuses `waterville-code` as the preview index, and `infra/refresh-preview.sh` checks the job's `AZURE_SEARCH_INDEX` before starting it.
- The storage account accepts Microsoft Entra tokens only (`allowSharedKeyAccess: false`), TLS 1.2 or later, HTTPS only, no public blob access. Write and delete operations on the tables are logged to the existing workspace (diagnostic setting `preview-table-audit`).
- Both scripts sign in with the service principal secret on standard input (`az login ... -p @-`), so it never appears in a process list.
- Requests are logged by path only. Uvicorn's own access log is off (`--no-access-log`), because staff case and draft searches send names and addresses in `?q=`. A failed staff sign-in logs the length and a short hash of the username, never the text, which is sometimes a password typed in the wrong field.
- Every `/api/staff/*` response and every staff answer carries `Cache-Control: no-store`, for shared office computers. Pages send a Content Security Policy that allows scripts from the site itself plus the two inline scripts of the built page, by hash.
- The public question log is scrubbed by `app.pii.scrub` and kept for `questionLogRetentionDays` days (default 365, env `QUESTION_LOG_RETENTION_DAYS`); the app deletes older days after it logs a new question. Set the parameter to the city's retention period once it is decided, or `questionLog=false` to log nothing.
- Cases, drafts, saved answers, the scrubbed public question log (`QUESTION_LOG=1`) and change alerts live in that storage account. These are city records once real cases go in. Agree custody, retention and FOAA handling with the city before the pilot uses real case data.
- Rate limits and login throttling are kept in memory per replica. The preview runs at most one replica, so they hold.

## Refresh the preview index

```bash
infra/refresh-preview.sh             # start and wait, 20 to 40 minutes
infra/refresh-preview.sh --no-wait   # start and print the log command
```

The first run is a baseline for change alerts and reports none. Later runs write changed, added and removed citations to the `changes` table, which `/staff/insights` shows. Production's index and schedule are unaffected.

## Evaluate the preview

```bash
uv run python eval/run.py --url https://<preview fqdn>     # 30 staff questions, writes eval/results-<date>.md
node eval/e2e.mjs --url https://<preview fqdn>             # browser walk through every feature
```

Both read the staff password from `~/waterville-preview-credentials.txt`, or from `EVAL_STAFF_PASSWORD` and `E2E_STAFF_PASSWORD`; the user is `inspector` unless `EVAL_STAFF_USER` or `E2E_STAFF_USER` says otherwise.

`eval/run.py` asks each question in `eval/questions.yaml` in staff mode and scores it. An expected citation is a hit when the answer cites it with `[n]`, or names it in the text and the search returned it. The run also counts expected figures and phrases. It writes a Markdown report with a blank right/partial/wrong column per answer for the Code Enforcement Officer to mark, which is the pilot's accuracy measure (target 90% right), and the raw results as JSON next to it. `--only id,id` runs a subset; `--min-pass 0.8` makes the exit status fail below 80%.

`eval/e2e.mjs` drives Chromium through the public chat, the source panel, the permit router, the fee estimator, the complaint sheet and its print view, then signs in and runs a citation lookup, creates a case, saves a staff answer to it, creates a notice of violation draft and downloads its .docx, computes deadlines, opens insights and signs out. It deletes the case and draft it created (`E2E_KEEP=1` keeps them). `--phone` and `--dark` switch the viewport and color scheme, `--shots DIR` saves a screenshot per step, and `--public-only` skips the staff part, which makes it safe against production. Each run signs in once; staff sign-in allows 10 attempts per 15 minutes per IP address.

## Cost

With `MIN_REPLICAS=0` the app costs nothing while idle beyond the shared environment. The storage account holds a few megabytes. A refresh run uses about 40 minutes of 1 vCPU and 2 GiB and embeds the whole corpus once (well under a dollar with text-embedding-3-large). The second index fits the Basic search tier: on 2026-10-03 the service used 1 of 15 indexes and 38 MB of 15 GB. Staff answers read more sources and allow up to 4,000 output tokens, so each costs more than a public answer, and all of them share the 50K tokens per minute of the `chat` deployment with production.

## Remove the preview

Delete the preview resources by name. Nothing else depends on them.

```bash
RG=rg-waterville-rag
az containerapp delete -g $RG -n waterville-preview --yes
az containerapp job delete -g $RG -n waterville-preview-refresh --yes
az storage account delete -g $RG -n "$(az storage account list -g $RG --query "[?starts_with(name,'wvpreview')].name | [0]" -o tsv)" --yes
az identity delete -g $RG -n waterville-preview-id
az identity delete -g $RG -n waterville-preview-refresh-id
```

Deleting the identities leaves their role assignments orphaned; `az role assignment list -g $RG --query "[?principalName=='']"` lists them for removal. The index `waterville-code-preview` stays in the search service until you delete it in the portal or with the REST API.

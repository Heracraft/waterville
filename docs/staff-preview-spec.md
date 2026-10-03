# Build spec: inspector workspace and preview deployment

Source of the feature list: `docs/inspector-workflow.md` (sections 4 and 6). This spec fixes the architecture so several agents can build in parallel without colliding. If a choice here proves wrong, change it in this file and say why at the bottom under "Changes".

## Decisions

- **Frontend: SvelteKit** (Svelte 5, TypeScript, `@sveltejs/adapter-static` with `fallback: 'index.html'`, SPA mode, `ssr = false`). Source in `web/`. Built output in `web/build/`, which FastAPI serves. pnpm.
- **Backend: FastAPI stays.** The Python retrieval, the scraper and the Azure push code stay. `app/main.py` is split into a package.
- **One image.** Multi-stage `Dockerfile`: a node stage builds `web/`, the python stage copies `web/build` to `/srv/web`.
- **The public UI is ported, not redesigned.** Production users see the same page. Port `app/web/style.css` verbatim into `web/src/lib/styles/app.css` and port the behavior of `app.js`, `source.js`, `scroll.js`, `theme.js` (source panel, highlighted claim, cited-passage highlight, auto-scroll, theme toggle, New chat, SSE streaming, `[n]` and `[n.sub]` citation chips). The old `app/web/` folder is deleted once the port matches.
- **Design.** All new UI follows the ledger look (memory: paper #eaeaea, ink #032c3c, rust #ba351a, blush #e6c5b8, stone #e1dcd8; 1px ink rules; square corners; no shadows; Source Serif 4 light plus Inter; strong separation between page, header, surfaces and inputs). Reuse the CSS tokens. Light and dark themes both work. Phone width works with no horizontal scroll. No emojis anywhere.
- **Prose in the UI and docs** follows the user's writing rules: no em dashes, no filler adverbs, no "not X but Y".

## Backend layout (`app/`)

```
app/
  main.py          FastAPI app factory, middleware, router registration, static/SPA serving
  config.py        all env vars in one place
  azure_auth.py    Auth class (managed identity or key)
  search.py        _search, search(query, mode, k_local, k_state, filters), citation lookup
  llm.py           chat completion streaming + non-streaming helper
  prompts.py       PUBLIC_SYSTEM_PROMPT (current prompt, plus A1/A2 rules), STAFF_SYSTEM_PROMPT
  ratelimit.py     RateLimiter, client_ip
  auth.py          staff login, sessions, require_staff dependency
  store.py         Store interface: Azure Table storage in prod, SQLite file for local/tests
  pii.py           scrub() for question logs
  routers/
    chat.py        POST /api/chat  (public and staff modes)
    staff.py       /api/staff/me, login, logout
    lookup.py      GET /api/lookup?cite=   GET /api/facets
    notebooks.py   /api/staff/cases ...
    drafts.py      /api/staff/drafts ...  (NOV, letters, 80K packet; .docx export)
    deadlines.py   /api/deadlines ...      (staff; public read of rule table is fine)
    checklists.py  /api/checklists, /api/permit-router, /api/fees/estimate, /api/staff/gates
    insights.py    /api/staff/insights, /api/staff/reports, /api/staff/changes
  data/
    checklists.toml   permit-type checklists, permit router, fee formulas
    deadlines.toml    legal clocks with citations and verification status
    gates.toml        project gate rules
    templates/        letter templates (Markdown with {placeholders})
tests/             pytest, no network; Azure calls are faked
```

Every router is registered in `main.py`. The foundation agent creates every module above with working stubs so feature agents only edit their own files.

### Config (env)

Existing vars keep their names. New:

| Var | Meaning | Default |
|---|---|---|
| `APP_ENV` | `production` or `preview` or `local` | `local` |
| `STAFF_USERS` | JSON `{"username": "scrypt$N$r$p$salt_b64$hash_b64"}` | empty: staff login disabled |
| `SESSION_SECRET` | HMAC key for session cookies | random per process if unset (local only) |
| `STORAGE_TABLE_ENDPOINT` | `https://<acct>.table.core.windows.net` | unset: SQLite at `STORE_SQLITE_PATH` |
| `STORE_SQLITE_PATH` | local store file | `./.data/store.sqlite` |
| `QUESTION_LOG` | `1` to log scrubbed public questions to the store | `0` |
| `EMBED_ORIGINS` | space-separated origins allowed to iframe `/embed` | `https://waterville-me.gov https://www.waterville-me.gov` |
| `STAFF_K_LOCAL`, `STAFF_K_STATE` | staff retrieval depth | 8, 6 |
| `STAFF_MAX_ANSWER_TOKENS` | | 4000 |

`python -m app.auth hash` reads a password on stdin and prints the `STAFF_USERS` value form.

### Auth

- Staff log in at `/staff/login` with username and password checked against `STAFF_USERS` (hashlib.scrypt, constant-time compare).
- Session: cookie `wv_session`, value `username.expiry.hmac`, HttpOnly, Secure (except local), SameSite=Strict, 12 h.
- `require_staff` FastAPI dependency returns the username or raises 401.
- Staff requests skip the per-IP rate limits but have their own generous limit (60/min per user).
- CSRF: SameSite=Strict plus requiring header `X-Requested-With: wv` on every staff POST/PUT/DELETE.
- Login attempts are rate limited per IP (10 per 15 min).

### Store

`Store` has `put(table, pk, rk, entity)`, `get`, `query(table, pk=None, filter=None)`, `delete`. Tables: `cases`, `caseitems`, `drafts`, `questions`, `changes`, `feedback`. Values are JSON-serializable dicts; the Table backend stores large fields as JSON strings, splitting above 32K chars. Use `azure-data-tables` with `DefaultAzureCredential` (role: Storage Table Data Contributor).

### Chat contract

`POST /api/chat` body: `{messages, mode?: "public"|"staff", filters?: {chapters?: string[], source_types?: string[]}, case_id?: string}`. `mode: "staff"` requires a staff session; otherwise 401. SSE events unchanged (`sources`, `delta`, `error`, `done`), plus `event: meta data: {mode, answer_id}` first. Staff answers end with the research-aid stamp, which the UI renders, not the model.

Staff prompt (cite-it): section numbers first, verbatim quotes of controlling text in blockquotes with citations, the enforcement chain when relevant (city section, penalty tier under 30-A §4452(3) as written in the sources, Rule 80K), conflicts and stale editions named, no City Clerk fallback, say "not in the sources" plainly.

### Corpus and index

- Preview uses its own index `waterville-code-preview` on the existing search service. Production index `waterville-code` is never written by preview code.
- New `source_type` values: `city_form` (Waterville permit application PDFs and forms; searched in the local bucket), `staff_note` (curated currency and conflict notes; staff mode only; public searches filter it out).
- New state sources: 30-A M.R.S. §§2691, 4103, 4353, 4453; 17 M.R.S. §§2851-2859 (dangerous buildings) if not present; 08-003 CMR chapters available from maine.gov; M.R. Civ. P. 80K and 80E text if a public official copy exists.
- Open item 1 (manual heading breadcrumbs) is implemented in `ecode/state.py`.
- Change alerts: the refresh job, before pushing, compares new code chunk hashes with the index (`id`, `content_hash` field, add it to the schema) and writes changed citations to the store table `changes`.

### Frontend routes (`web/src/routes/`)

| Route | Who | What |
|---|---|---|
| `/` | public | ported chat, plus A1 checklists rendered under answers, A2 triage, links to tools |
| `/permits` | public | A3 permit-type router and "what to bring" |
| `/fees` | public | A4 fee estimator (published formulas only, every figure labeled estimate) |
| `/complaint` | public | A5 printable complaint sheet, nothing stored |
| `/embed` | public | compact chat for iframing on the city site |
| `/staff/login` | public | |
| `/staff` | staff | research desk: cite-it chat, filters (chapter, source type), citation lookup box, copy citation, copy answer with citations, save to case |
| `/staff/cases`, `/staff/cases/[id]` | staff | case notebooks: parcel/address, type tags, timeline of saved answers, notes, deadlines, drafts |
| `/staff/drafts/[id]` | staff | NOV 1/2/3, stop-work, abutter letter, ZBA notice, decision letter, 80K packet; edit, .docx and print |
| `/staff/deadlines` | staff | deadline calculator |
| `/staff/gates` | staff | project gate checklist (B8) |
| `/staff/insights` | staff | public question digest, unanswered rate, top sections, code change alerts, reports (DEP biennial shoreland, LPI annual) from case data |

Shared: `web/src/lib/api.ts` (fetch wrappers, SSE reader), `web/src/lib/components/` (Chat, Answer, CitationChip, SourcePanel, Header, StaffNav, Stamp), `web/src/lib/styles/app.css`. A service worker (`web/src/service-worker.ts`) caches the app shell and viewed source texts for offline re-reading (B11).

## Local dev

- Backend: `uv run uvicorn app.main:app --port <your port>` with `APP_ENV=local`. Without Azure keys, `/api/chat` and lookup fail; tests fake them via `app.search` and `app.llm` monkeypatching.
- Frontend: `cd web && pnpm dev --port <port>` proxies `/api` to the backend (vite proxy target from `API_PORT`).
- Each parallel agent uses the ports it is assigned to avoid collisions. Do not run `pnpm build` into `web/build` concurrently; use `pnpm check` and `pnpm test`. The integration stage does the build.
- Do not add dependencies outside the foundation stage. Do not commit; the orchestrator commits.

## Preview deployment (Azure)

Azure Container Apps has no Coolify-style preview button. The preview is a second container app in the same environment, with its own identity, index, storage and secrets, deployed by `infra/deploy-preview.sh` from `infra/preview.bicep`. It reads the existing Search service and OpenAI account (role assignments for its own identity) and never modifies production resources.

- App `waterville-preview`, min replicas 0, max 1.
- Job `waterville-preview-refresh`, manual trigger only, writes `waterville-code-preview`.
- Storage account for tables, identity gets Storage Table Data Contributor.
- Secrets `staff-users`, `session-secret` as Container App secrets.

## Changes

(append here)
- 2026-10-03: added `FAKE_AZURE=1`. With it, `app.search` and `app.llm` return deterministic fixtures from `tests/fixtures/` (real chunk texts taken from `output/chunks.jsonl`), so the UI, e2e tests and screenshots run with no Azure access.

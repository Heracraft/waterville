"""Create the Azure AI Search index and push chunks with Azure OpenAI embeddings.

Uses the REST APIs directly (no Azure SDK) so the only dependency is requests.

Environment:
  AZURE_SEARCH_ENDPOINT            https://<service>.search.windows.net
  AZURE_SEARCH_API_KEY             admin key
  AZURE_SEARCH_INDEX               index name (default: waterville-code)
  AZURE_OPENAI_ENDPOINT            https://<resource>.openai.azure.com
  AZURE_OPENAI_API_KEY             key for the Azure OpenAI resource
  AZURE_OPENAI_EMBEDDING_DEPLOYMENT  deployment name of the embedding model
  AZURE_OPENAI_EMBEDDING_MODEL     text-embedding-3-large (default) | text-embedding-3-small | text-embedding-ada-002
  EMBEDDING_DIMENSIONS             vector size (default 3072 for 3-large, 1536 otherwise)

Usage:
  python -m ecode.azure schema  [--out azure/index.json]   # print/write index JSON
  python -m ecode.azure validate [--chunks output/chunks.jsonl]
  python -m ecode.azure push    [--chunks output/chunks.jsonl] [--recreate]
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import sys
import time
from pathlib import Path

import requests

SEARCH_API = "2024-07-01"
AOAI_API = "2024-10-21"
VECTOR_FIELD = "content_vector"


def _f(name, type_="Edm.String", *, key=False, search=False, filt=False, facet=False, sort=False, analyzer=None):
    f = {
        "name": name,
        "type": type_,
        "key": key,
        "searchable": search,
        "filterable": filt,
        "facetable": facet,
        "sortable": sort,
        "retrievable": True,
    }
    if analyzer:
        f["analyzer"] = analyzer
    if type_.startswith("Collection("):
        f.pop("sortable")
    return f


def index_definition(name: str, dims: int, model: str, aoai_endpoint: str | None, deployment: str | None) -> dict:
    fields = [
        _f("id", key=True, filt=True),
        _f("doc_id", filt=True, facet=True),
        _f("source_type", filt=True, facet=True),
        _f("node_type", filt=True, facet=True),
        _f("title", search=True, analyzer="en.microsoft"),
        _f("citation", search=True, filt=True, sort=True),
        _f("content", search=True, analyzer="en.microsoft"),
        _f("division", filt=True, facet=True),
        _f("chapter_number", filt=True, facet=True, sort=True),
        _f("chapter_title", search=True, filt=True, facet=True),
        _f("part", search=True, filt=True),
        _f("article", search=True, filt=True, facet=True),
        _f("section_number", filt=True, sort=True),
        _f("section_title", search=True),
        _f("breadcrumb", search=True, analyzer="en.microsoft"),
        _f("url"),
        _f("ecode_guid", filt=True),
        _f("history", search=True),
        _f("ordinances", "Collection(Edm.String)", search=True, filt=True, facet=True),
        _f("adopted_date", "Edm.DateTimeOffset", filt=True, sort=True),
        _f("page_start", "Edm.Int32", filt=True),
        _f("page_end", "Edm.Int32", filt=True),
        _f("chunk_index", "Edm.Int32", filt=True, sort=True),
        _f("chunk_count", "Edm.Int32"),
        _f("token_count", "Edm.Int32"),
        _f("municipality", filt=True, facet=True),
        _f("legislation_through"),
        _f("crawled_at", "Edm.DateTimeOffset", filt=True, sort=True),
        {
            "name": VECTOR_FIELD,
            "type": "Collection(Edm.Single)",
            "searchable": True,
            "retrievable": False,
            "stored": False,
            "dimensions": dims,
            "vectorSearchProfile": "vector-profile",
        },
    ]
    vector_search = {
        "algorithms": [
            {
                "name": "hnsw",
                "kind": "hnsw",
                "hnswParameters": {"metric": "cosine", "m": 4, "efConstruction": 400, "efSearch": 500},
            }
        ],
        "profiles": [{"name": "vector-profile", "algorithm": "hnsw", "vectorizer": "aoai-vectorizer"}],
        "vectorizers": [
            {
                "name": "aoai-vectorizer",
                "kind": "azureOpenAI",
                "azureOpenAIParameters": {
                    "resourceUri": aoai_endpoint or "https://<your-resource>.openai.azure.com",
                    "deploymentId": deployment or "<embedding-deployment>",
                    "modelName": model,
                },
            }
        ],
    }
    semantic = {
        "defaultConfiguration": "default",
        "configurations": [
            {
                "name": "default",
                "prioritizedFields": {
                    "titleField": {"fieldName": "title"},
                    "prioritizedContentFields": [{"fieldName": "content"}],
                    "prioritizedKeywordsFields": [
                        {"fieldName": "citation"},
                        {"fieldName": "chapter_title"},
                        {"fieldName": "breadcrumb"},
                    ],
                },
            }
        ],
    }
    return {"name": name, "fields": fields, "vectorSearch": vector_search, "semantic": semantic}


# ------------------------------------------------------------------ validation

EDM_CHECK = {
    "Edm.String": lambda v: isinstance(v, str),
    "Edm.Int32": lambda v: isinstance(v, int) and -(2**31) <= v < 2**31,
    "Edm.DateTimeOffset": lambda v: isinstance(v, str) and dt.datetime.fromisoformat(v.replace("Z", "+00:00")),
    "Collection(Edm.String)": lambda v: isinstance(v, list) and all(isinstance(x, str) for x in v),
}


def validate(chunks: list[dict], index: dict) -> list[str]:
    errors = []
    fields = {f["name"]: f for f in index["fields"]}
    keyname = next(f["name"] for f in index["fields"] if f.get("key"))
    ids = set()
    for c in chunks:
        k = c.get(keyname)
        if not k or not all(ch.isalnum() or ch in "_-=" for ch in k) or len(k) > 1024:
            errors.append(f"bad key {k!r}")
        if k in ids:
            errors.append(f"duplicate key {k}")
        ids.add(k)
        for name, v in c.items():
            if name not in fields:
                errors.append(f"{k}: field {name} not in index")
                continue
            if v is None:
                continue
            t = fields[name]["type"]
            if t in EDM_CHECK:
                try:
                    ok = EDM_CHECK[t](v)
                except ValueError:
                    ok = False
                if not ok:
                    errors.append(f"{k}: {name}={v!r} is not {t}")
        if len(c.get("content", "").encode()) > 32766 and fields["content"].get("filterable"):
            errors.append(f"{k}: content too long for a filterable field")
        if len(json.dumps(c).encode()) > 16 * 1024 * 1024:
            errors.append(f"{k}: document exceeds 16 MB")
    return errors


# ------------------------------------------------------------------ push


def _retry(fn, what: str):
    for attempt in range(8):
        r = fn()
        if r.status_code < 300:
            return r
        if r.status_code in (429, 500, 502, 503, 504):
            wait = float(r.headers.get("retry-after", 2 ** attempt))
            print(f"{what}: {r.status_code}, retrying in {wait:.0f}s", file=sys.stderr)
            time.sleep(wait)
            continue
        raise RuntimeError(f"{what} failed: {r.status_code} {r.text[:2000]}")
    raise RuntimeError(f"{what}: gave up after retries")


class Embedder:
    def __init__(self, endpoint: str, api_key: str, deployment: str, model: str, dims: int, cache: Path):
        self.url = f"{endpoint.rstrip('/')}/openai/deployments/{deployment}/embeddings?api-version={AOAI_API}"
        self.headers = {"api-key": api_key, "Content-Type": "application/json"}
        self.model = model
        self.dims = dims
        self.cache_path = cache
        self.cache: dict[str, list[float]] = {}
        if cache.exists():
            for line in cache.open():
                row = json.loads(line)
                self.cache[row["h"]] = row["v"]

    def _hash(self, text: str) -> str:
        return hashlib.sha256(f"{self.model}|{self.dims}|{text}".encode()).hexdigest()

    def embed(self, texts: list[str], batch: int = 16) -> list[list[float]]:
        todo = [t for t in dict.fromkeys(texts) if self._hash(t) not in self.cache]
        with self.cache_path.open("a") as fh:
            for i in range(0, len(todo), batch):
                part = todo[i : i + batch]
                body = {"input": part}
                if self.model != "text-embedding-ada-002":
                    body["dimensions"] = self.dims
                r = _retry(lambda: requests.post(self.url, headers=self.headers, json=body, timeout=120), "embed")
                for t, item in zip(part, sorted(r.json()["data"], key=lambda d: d["index"])):
                    h = self._hash(t)
                    self.cache[h] = item["embedding"]
                    fh.write(json.dumps({"h": h, "v": item["embedding"]}) + "\n")
                print(f"embedded {min(i + batch, len(todo))}/{len(todo)}", file=sys.stderr)
        return [self.cache[self._hash(t)] for t in texts]


def _env(name: str, default: str | None = None) -> str:
    v = os.environ.get(name, default)
    if not v:
        sys.exit(f"missing environment variable {name}")
    return v


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["schema", "validate", "push"])
    ap.add_argument("--chunks", default="output/chunks.jsonl")
    ap.add_argument("--out", help="write schema JSON here (schema command)")
    ap.add_argument("--recreate", action="store_true", help="delete and recreate the index before pushing")
    ap.add_argument("--batch", type=int, default=100, help="documents per upload request")
    args = ap.parse_args(argv)

    model = os.environ.get("AZURE_OPENAI_EMBEDDING_MODEL", "text-embedding-3-large")
    dims = int(os.environ.get("EMBEDDING_DIMENSIONS", 3072 if model == "text-embedding-3-large" else 1536))
    name = os.environ.get("AZURE_SEARCH_INDEX", "waterville-code")
    index = index_definition(
        name,
        dims,
        model,
        os.environ.get("AZURE_OPENAI_ENDPOINT"),
        os.environ.get("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
    )

    if args.command == "schema":
        text = json.dumps(index, indent=2) + "\n"
        if args.out:
            Path(args.out).write_text(text)
        else:
            print(text, end="")
        return

    chunks = [json.loads(line) for line in open(args.chunks, encoding="utf-8")]
    errors = validate(chunks, index)
    if errors:
        print("\n".join(errors[:50]), file=sys.stderr)
        sys.exit(f"{len(errors)} validation errors")
    print(f"{len(chunks)} documents valid against index '{name}'", file=sys.stderr)
    if args.command == "validate":
        return

    endpoint = _env("AZURE_SEARCH_ENDPOINT").rstrip("/")
    sheaders = {"api-key": _env("AZURE_SEARCH_API_KEY"), "Content-Type": "application/json"}
    aoai_key = _env("AZURE_OPENAI_API_KEY")
    # Query-time vectorizer needs a credential too; fill it in on the live index only.
    index["vectorSearch"]["vectorizers"][0]["azureOpenAIParameters"]["apiKey"] = aoai_key

    idx_url = f"{endpoint}/indexes/{name}?api-version={SEARCH_API}"
    if args.recreate:
        r = requests.delete(idx_url, headers=sheaders, timeout=60)
        if r.status_code not in (204, 404):
            sys.exit(f"delete index failed: {r.status_code} {r.text}")
    _retry(lambda: requests.put(idx_url, headers=sheaders, json=index, timeout=60), "create index")
    print(f"index '{name}' ready", file=sys.stderr)

    embedder = Embedder(
        _env("AZURE_OPENAI_ENDPOINT"),
        aoai_key,
        _env("AZURE_OPENAI_EMBEDDING_DEPLOYMENT"),
        model,
        dims,
        Path(args.chunks).with_name(f"embeddings-cache-{model}-{dims}.jsonl"),
    )
    vectors = embedder.embed([c["content"] for c in chunks])

    docs_url = f"{endpoint}/indexes/{name}/docs/index?api-version={SEARCH_API}"
    for i in range(0, len(chunks), args.batch):
        batch = []
        for c, v in zip(chunks[i : i + args.batch], vectors[i : i + args.batch]):
            batch.append({"@search.action": "mergeOrUpload", **c, VECTOR_FIELD: v})
        r = _retry(lambda: requests.post(docs_url, headers=sheaders, json={"value": batch}, timeout=300), "upload")
        failed = [x for x in r.json()["value"] if not x["status"]]
        if failed:
            sys.exit(f"upload failures: {failed[:5]}")
        print(f"uploaded {min(i + args.batch, len(chunks))}/{len(chunks)}", file=sys.stderr)


if __name__ == "__main__":
    main()

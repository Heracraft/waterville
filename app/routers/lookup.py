"""Exact citation lookup and index facets (research desk, B3 and B4).

GET /api/lookup?cite=§ 205-7A
  Normalizes the typed citation to the indexed form (app.search.normalize_citation)
  and returns every chunk of that section in chunk order, from a filter-only
  query (no ranking). 400 when the citation cannot be read, 404 when the index
  has no such section.

  {"query", "kind", "requested", "citation", "subsection", "parent", "title",
   "breadcrumb", "url", "open_url", "source_type", "label", "chapter_number",
   "chapter_title", "legislation_through", "page_start", "page_end",
   "chunk_count", "chunks": [{"id", "chunk_index", "page_start", "page_end", "text"}],
   "text", "sections"?: [{"citation", "title"}]}       (sections: chapter lookups)

GET /api/facets
  {"chapters": [{"value", "title", "count"}],
   "source_types": [{"value", "name", "label", "count"}],
   "legislation_through": "MM-DD-YYYY" | null}

Both are open to the public, since the text is the same the public chat
shows. Staff notes appear only for a staff session. Public callers share a
per-IP limit (LOOKUP_RATE_LIMIT_PER_MINUTE, default 30); staff use the staff
per-user limit.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request

from .. import auth, ratelimit, search

router = APIRouter(tags=["lookup"])

public_limiter = ratelimit.WindowLimiter(
    int(os.environ.get("LOOKUP_RATE_LIMIT_PER_MINUTE", "30")),
    60,
    "Too many lookups in a short time. Please wait a minute and try again.",
)


def _limit(request: Request) -> str | None:
    user = auth.current_staff(request)
    msg = ratelimit.staff_limiter.check(user) if user else public_limiter.check(ratelimit.client_ip(request))
    if msg:
        raise HTTPException(429, msg)
    return user


@router.get("/api/lookup")
async def lookup(request: Request, cite: str = Query("", max_length=200)):
    user = _limit(request)
    try:
        normalized, result = await search.lookup_citation(cite, staff=bool(user))
    except ValueError as e:
        raise HTTPException(400, str(e))
    if result is None:
        raise HTTPException(404, f"{normalized.citation} is not in the sources.")
    return result


@router.get("/api/facets")
async def facets(request: Request):
    user = _limit(request)
    return await search.facet_summary(staff=bool(user))

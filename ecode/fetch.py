"""Polite HTTP fetching with an on-disk cache of raw responses."""

from __future__ import annotations

import hashlib
import logging
import time
from pathlib import Path

import requests

BASE = "https://ecode360.com"
UA = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0 Safari/537.36"
)
log = logging.getLogger(__name__)


class Fetcher:
    def __init__(self, cache_dir: Path, delay: float = 1.0, refresh: bool = False):
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.delay = delay
        self.refresh = refresh
        self.session = requests.Session()
        self.session.headers["User-Agent"] = UA
        self._last = 0.0

    def _cache_path(self, url: str, suffix: str) -> Path:
        key = hashlib.sha1(url.encode()).hexdigest()[:16]
        return self.cache_dir / f"{key}{suffix}"

    def get(self, path_or_url: str, binary: bool = False) -> bytes:
        url = path_or_url if path_or_url.startswith("http") else BASE + path_or_url
        cp = self._cache_path(url, ".bin" if binary else ".html")
        if cp.exists() and not self.refresh:
            return cp.read_bytes()
        for attempt in range(5):
            wait = self.delay - (time.monotonic() - self._last)
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
            try:
                r = self.session.get(url, timeout=120)
            except requests.RequestException as e:
                log.warning("GET %s failed (%s), retry %d", url, e, attempt + 1)
                time.sleep(2 ** attempt * 2)
                continue
            if r.status_code == 200:
                cp.write_bytes(r.content)
                (cp.with_suffix(cp.suffix + ".url")).write_text(url)
                log.info("GET %s -> %d bytes", url, len(r.content))
                return r.content
            if r.status_code in (429, 500, 502, 503, 504):
                log.warning("GET %s -> %d, retry %d", url, r.status_code, attempt + 1)
                time.sleep(2 ** attempt * 5)
                continue
            r.raise_for_status()
        raise RuntimeError(f"giving up on {url}")

    def text(self, path_or_url: str) -> str:
        return self.get(path_or_url).decode("utf-8", errors="replace")

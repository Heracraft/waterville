"""Command line entry point: python -m ecode [--customer WA3904] [--out output]."""

from __future__ import annotations

import argparse
import json
import logging
import shutil
from pathlib import Path

from .export import Exporter
from .fetch import Fetcher


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(description="Scrape an eCode360 code into Azure-ready RAG files.")
    ap.add_argument("--customer", default="WA3904", help="eCode360 customer id")
    ap.add_argument("--out", default="output", type=Path)
    ap.add_argument("--cache", default="data/raw", type=Path, help="raw HTTP response cache")
    ap.add_argument("--refresh", action="store_true", help="ignore the cache and re-download everything")
    ap.add_argument("--delay", type=float, default=1.5, help="seconds between requests")
    ap.add_argument("--no-verify", action="store_true", help="skip the TOC cross-check (saves ~200 requests)")
    ap.add_argument("-v", "--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING, format="%(levelname)s %(name)s: %(message)s"
    )

    if args.out.exists():
        for sub in ("markdown", "pdf"):
            shutil.rmtree(args.out / sub, ignore_errors=True)
    args.out.mkdir(parents=True, exist_ok=True)

    ex = Exporter(args.customer, args.out, Fetcher(args.cache, delay=args.delay, refresh=args.refresh))
    ex.crawl()
    report = None if args.no_verify else ex.verify()
    ex.export_code()
    ex.export_attachments()
    ex.export_new_laws()
    manifest = ex.write_outputs(report)
    print(json.dumps(manifest, indent=2))
    v = manifest["verification"]
    if v and (v["missing"] or v["extra"]):
        raise SystemExit("verification found missing or extra sections; see manifest.json")


if __name__ == "__main__":
    main()

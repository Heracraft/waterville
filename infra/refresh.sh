#!/bin/sh
# Weekly refresh: re-crawl eCode360, verify completeness, update the index.
# The scraper exits non-zero when sections are missing, which stops the
# push so a bad crawl never replaces good data.
set -eu
python -m ecode --out /tmp/out --cache /tmp/raw --delay "${CRAWL_DELAY:-1.5}"
python -m ecode.azure push --chunks /tmp/out/chunks.jsonl

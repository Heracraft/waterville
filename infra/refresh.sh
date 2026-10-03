#!/bin/sh
# Weekly refresh: re-crawl eCode360, verify completeness, update the index.
# The scraper exits non-zero when sections are missing, which stops the
# push so a bad crawl never replaces good data.
#
# The crawl also re-fetches the non-eCode sources: state law and rules, the
# City permit forms (and any new form on the City's permit page) and the
# staff notes in ecode/staff_notes.toml.
#
# Change alerts: before uploading, the push reads id and content_hash of the
# city chunks already in the target index (AZURE_SEARCH_INDEX). After a
# successful upload it writes each changed, added or removed citation to the
# store table `changes` when STORAGE_TABLE_ENDPOINT is set, and prints them to
# the job log otherwise. GET /api/staff/changes lists them. The first push to
# an index without content hashes is a baseline and reports nothing.
# CHANGES_TO overrides the target: auto, store, print or none.
set -eu
python -m ecode --out /tmp/out --cache /tmp/raw --delay "${CRAWL_DELAY:-1.5}"
python -m ecode.azure push --chunks /tmp/out/chunks.jsonl --changes-to "${CHANGES_TO:-auto}"

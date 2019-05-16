#!/bin/bash
set -eu

MERGED="$1"
CHUNK="$2"

# sanity check that the table is indeed a chunk in case we consume the order of args
sqlite3 "$CHUNK" "
SELECT * FROM keyword_search_terms;
" >/dev/null


if [[ ! -f "$MERGED" ]]; then
    echo "$MERGED doesn't exist, initialising"
    sqlite3 "$MERGED" "
CREATE TABLE main.urls(
  id INTEGER PRIMARY KEY,
  url LONGVARCHAR,
  title LONGVARCHAR
);
CREATE TABLE main.visits(
  id INTEGER PRIMARY KEY,
  url INTEGER NOT NULL,
  visit_time INTEGER NOT NULL,
  visit_duration INTEGER DEFAULT 0 NOT NULL
);
"
fi
# TODO shit, perhaps setting visi_duration to NOT NULL wasn't wisest.. but whatever


# TODO how to ensure it all happens withing a single commit??
sqlite3 "$MERGED" "
attach '$CHUNK' as chunk;
insert or ignore into main.urls select id, url, title from chunk.urls;
insert or ignore into main.visits select id, url, visit_time, visit_duration from chunk.visits;
detach chunk;
"

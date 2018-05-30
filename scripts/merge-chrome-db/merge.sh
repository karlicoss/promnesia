#!/bin/bash -eu

MERGED="$1"
CHUNK="$2"

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


sqlite3 "$MERGED" "
attach '$CHUNK' as chunk;
insert or ignore into main.urls select id, url, title from chunk.urls;
insert or ignore into main.visits select id, url, visit_time, visit_duration from chunk.visits;
detach chunk;
"

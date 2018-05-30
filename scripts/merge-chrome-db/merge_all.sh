#!/bin/bash -eu
backups="/L/backups/chrome-history"
merge_one="$(dirname "$0")/merge.sh"
merged="$backups/merged/chrome-history.sql"

rm -f "$merged"

for db in "$backups"/*/History; do
    echo "merging $db"
    "$merge_one" "$merged" "$db"
done

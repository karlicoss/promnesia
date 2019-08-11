#!/bin/sh
set -eu
BACKUP_DIR="$1"

backup_file () {
    file="$1"
    to="$2"
    fname="$(basename "$file")"
    timestamp=$(date -d "@$(stat -c %Y "$file")" +'%Y%m%d%H%M%S')
    tdir="$to/$timestamp"
    mkdir -p "$tdir"
    cp "$file" "$tdir/$fname"
}


backup_chrome () {
    backup_file '/data/data/com.android.chrome/app_chrome/Default/History'            "$BACKUP_DIR/chrome"
}

backup_firefox () {
    backup_file '/data/data/org.mozilla.firefox/files/mozilla/'*.default/'browser.db' "$BACKUP_DIR/firefox"
}


backup_firefox
backup_chrome

#!/bin/sh
set -eu
BACKUP_DIR="$1"

backup_file () {
    fdir="$1"
    fname="$2"
    to="$3"
    file="$fdir/$fname"
    timestamp="$(stat -c %Y "$file")"
    cp "$file" "$to/$timestamp.$fname"
}


backup_chrome () {
    backup_file '/data/data/com.android.chrome/app_chrome/Default/'       'History'    "$BACKUP_DIR/chrome"
}

backup_firefox () {
    backup_file '/data/data/org.mozilla.firefox/files/mozilla/'*.default/ 'browser.db' "$BACKUP_DIR/firefox"
}


backup_firefox
backup_chrome

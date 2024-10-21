#!/bin/bash
set -eux

# Seems wrong to keep the whole repository in docker build context.
# So instead, we mount the repository inside the container (into /promnesia_source)
# (as read only to avoid messing up host files and crapping with caches etc.)
# However to actually run tests we do need a writable directory..
# So we copy the repo to the actual working dir here

# ugh, kinda annoying -- not sure how to update source files when we change them on the host system...
cp -R -T /promnesia_source /promnesia
extension/.ci/build

git init  # todo ??? otherwise setuptools-scm fails to detect the version...

# eh. kinda annoying to jump over so many venv layer here...
# but docker runs as root and it doesn't like pip install uv now
# even if you pass --break-system-packages, then subsequent uv invocation also fails
pipx run uv tool run --with=tox-uv tox -e end2end -- "$@"

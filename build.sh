#!/bin/bash
set -eu
cd "$(dirname "$0")"

# TODO err... have I lost this script? what was there?
# extension/prepare-extension.sh

cd extension
npm run-script build

#!/bin/bash
set -eu
cd "$(dirname "$0")/extension"

npm run-script jslint

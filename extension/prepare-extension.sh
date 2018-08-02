#!/bin/bash
set -eu

SDIR="$(dirname "$0")"

cd "$SDIR/../wereyouhere/"
jiphy js_shared.py -od "$SDIR"

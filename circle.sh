#!/bin/bash
set -eu
# https://circleci.com/docs/2.0/local-cli/
circleci config validate

# TODO ugh doesn't work :(
# circleci local execute
# circleci local execute --job build 

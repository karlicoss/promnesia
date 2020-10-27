#!/usr/bin/env bash

cd "$(dirname "$0")"
mkdir user_data
cp docker_files/indexer-config.py.example user_data/indexer-config.py
./get-some-data.sh

# the config file will be periodically reloaded by the indexer process, and data sources will be periodically re-indexed.


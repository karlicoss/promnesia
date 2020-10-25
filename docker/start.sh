#!/usr/bin/env bash

cd "$(dirname "$0")"
cp indexer-config.py.example data/indexer-config.py
./get-some-data.sh
docker-compose build; and docker-compose up

# the config file will be periodically reloaded by the indexer process, and data will be periodically re-indexed.


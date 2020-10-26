#!/usr/bin/env bash

cd "$(dirname "$0")"
docker-compose -f docker_files/docker-compose.yaml build && docker-compose -f docker_files/docker-compose.yaml up



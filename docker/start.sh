#!/usr/bin/env bash

cd "$(dirname "$0")"
docker-compose -f docker_files/docker-compose.yaml build --build-arg VERSION="$(git describe | cut -f1 -d"-")" && docker-compose -f docker_files/docker-compose.yaml up



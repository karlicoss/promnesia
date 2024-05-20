#!/bin/bash
set -eux

# TODO assert we're running under github ci?
# since this setup is kinda elaborate and can be somewhat unsafe to run blindly

# supposed to be called from promnesia repository root
[ -e src/promnesia ]
[ -e extension/src ]

PROMNESIA_SRC="$(pwd)"

cd .ci/end2end

IMAGE='promnesia_end2end_tests'

docker build -t "$IMAGE" .

# NOTE: dev/shm mount to prevent crashes during headless chrome
docker run -v /dev/shm:/dev/shm --mount "type=bind,src=$PROMNESIA_SRC,dst=/promnesia_source,readonly=true" -e CI "$IMAGE" "$@"

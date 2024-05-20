#!/bin/bash
set -eux -o pipefail

apt update --yes
apt install --yes curl
curl -fsSL https://deb.nodesource.com/setup_20.x | bash -
apt install --yes nodejs

#!/bin/bash
set -eux -o pipefail

apt update --yes

apt install --yes wget

# NOTE: these days ubuntu provisions firefox via snap, and it's a nightmare to make it work with webdriver
# so we force it to use a regular package (following these instructions https://askubuntu.com/a/1510872/427470)
install -d -m 0755 /etc/apt/keyrings
wget -q https://packages.mozilla.org/apt/repo-signing-key.gpg -O- | tee /etc/apt/keyrings/packages.mozilla.org.asc > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/packages.mozilla.org.asc] https://packages.mozilla.org/apt mozilla main" | tee -a /etc/apt/sources.list.d/mozilla.list > /dev/null

# prevent snap version from overriding:
echo '
Package: *
Pin: origin packages.mozilla.org
Pin-Priority: 1000
' | tee /etc/apt/preferences.d/mozilla
# to check: -- should not show anything mentioning snap
# apt install --verbose-versions --dry-run firefox

apt update

apt install --yes firefox
# NOTE: selenium should download the corresponding geckodriver itself via selenium_manager

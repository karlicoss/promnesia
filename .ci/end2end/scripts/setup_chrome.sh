#!/bin/bash
set -eux -o pipefail

apt update --yes

apt install --yes wget

install -d -m 0755 /etc/apt/keyrings
wget -q https://dl.google.com/linux/linux_signing_key.pub -O- | tee /etc/apt/keyrings/linux_signing_key.pub.asc > /dev/null
echo "deb [signed-by=/etc/apt/keyrings/linux_signing_key.pub.asc] https://dl.google.com/linux/chrome/deb/ stable main" | tee -a /etc/apt/sources.list.d/google-chrome.list > /dev/null

apt update

apt install --yes google-chrome-stable

# sadly latest version of chrome/chromedriver isn't working due to some bugs with iframes (see install_custom_chrome)

# remove the actual chrome to get it out of the way (we do want dependencies though)
apt remove --yes google-chrome-stable
! which google-chrome  # check there is no binary (in case of virtual packages or whatever)

function install_custom_chrome() {
    ## this installs last revision that was actually working (1110897) or 113.0.5623.0
    ## see https://bugs.chromium.org/p/chromedriver/issues/detail?id=4440
    apt install --yes unzip

    mkdir /tmp/chrome

    wget -q 'https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F1110897%2Fchrome-linux.zip?generation=1677589092014487&alt=media'         \
       -O /tmp/chrome/chrome-linux.zip
    unzip /tmp/chrome/chrome-linux.zip         -d /tmp/chrome
    ln -sf /tmp/chrome/chrome-linux/chrome /usr/bin/google-chrome

    wget -q 'https://www.googleapis.com/download/storage/v1/b/chromium-browser-snapshots/o/Linux_x64%2F1110897%2Fchromedriver_linux64.zip?generation=1677589097630198&alt=media' \
       -O /tmp/chrome/chromedriver_linux64.zip
    unzip /tmp/chrome/chromedriver_linux64.zip -d /tmp/chrome
    ln -sf /tmp/chrome/chromedriver_linux64/chromedriver /usr/bin/chromedriver
}

install_custom_chrome

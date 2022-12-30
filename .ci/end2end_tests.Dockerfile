FROM ubuntu:jammy

ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update        \
 # install add-apt-repository
 && apt-get install --yes software-properties-common \
 && add-apt-repository ppa:mozillateam/ppa \
 # force to use firefox from ppa instead of snap
 && printf 'Package: *\nPin: release o=LP-PPA-mozillateam\nPin-Priority: 1001\n' > /etc/apt/preferences.d/mozilla-firefox \
 && apt-get install --yes firefox \
 # install extra dependencies
 && apt-get install --yes \
    # gcc needed for psutil?
    python3 python3-dev gcc python3-pip tox \
    # used to pack the extension
    atool \
    curl git \
 # using python docs as a source of some html test data
 # also prevent dpkg from excluding doc files...
 && sed -i '/usr.share.doc/d' /etc/dpkg/dpkg.cfg.d/excludes \
 && apt-get install --yes python3-doc \
 # https://github.com/nodesource/distributions/blob/master/README.md#installation-instructions
 && (curl -sL https://deb.nodesource.com/setup_16.x | bash - ) \
 && apt-get install --yes nodejs \
 && apt-get clean \
 # geckodriver isn't available in ubuntu repos anymore because of snap
 && curl -L https://github.com/mozilla/geckodriver/releases/download/v0.32.0/geckodriver-v0.32.0-linux64.tar.gz | tar xz -C /usr/local/bin


# ugh. so
# - chromium (as well as the chromedriver???) is packaged as snap in ubuntu 20.04 and basically it doesn't work under docker
# - debian image lacks many convenient binaries..
# - it's apparently easier to usea actual Google fucking Chrome instead
#   https://stackoverflow.com/questions/58997430/how-to-install-chromium-in-docker-based-on-ubuntu-19-10-and-20-04/60908332#60908332
#   (+ driver from here https://chromedriver.chromium.org/downloads)
#   but either way exentesions don't work under headless chrome??? (see end2end tests source code)

# TODO would be nice to only copy git tracked files?...
COPY    . /repo
WORKDIR   /repo


# FIXME fuck. otherwise setuptools-scm fails to detect the version...
RUN git init

# builds both firefox and chrome targets
CMD bash -c 'extension/.ci/build && tox -e end2end'

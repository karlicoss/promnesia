FROM ubuntu:latest

ENV DEBIAN_FRONTEND=noninteractive

COPY scripts /scripts

RUN /scripts/setup_firefox.sh \
 && /scripts/setup_chrome.sh  \
 && /scripts/setup_node.sh    \
 && apt install --yes pipx git \
# using python docs as a source of some html test data
# need to prevent dpkg from excluding doc files...
 && sed -i '/usr.share.doc/d' /etc/dpkg/dpkg.cfg.d/excludes && apt install --yes python3-doc \
 && apt clean                     \
 && mkdir /promnesia

WORKDIR /promnesia

ENTRYPOINT ["/scripts/build_and_run_tests.sh"]

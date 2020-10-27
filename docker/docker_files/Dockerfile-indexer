FROM promnesia:latest

RUN apt-get update && apt-get install -y cron
COPY docker/docker_files/indexer-entrypoint.sh /
ENTRYPOINT ["/indexer-entrypoint.sh"]

#!/bin/bash

# note: https://lostindetails.com/articles/How-to-run-cron-inside-Docker
# note: CRONTAB is set in docker-compose.yaml.

echo "${CRONTAB} > /proc/1/fd/1 2>/proc/1/fd/2" | crontab -
cron -f

#!/bin/bash

echo "${CRONTAB} > /proc/1/fd/1 2>/proc/1/fd/2" | crontab -
cron -f

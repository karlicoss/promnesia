#!/bin/bash

. ~/bash_ci

cd "$(this_dir)" || exit

ci_run python3 -mmypy wereyouhere
ci_run python3 -mpylint -E wereyouhere

ci_report_errors

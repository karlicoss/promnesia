import argparse
import os.path
import logging
import json
import inspect
from sys import exit
from typing import List, Tuple
from pathlib import Path

def import_config(config_file: str):
    import os, sys, importlib
    mpath = Path(config_file)
    sys.path.append(mpath.parent.as_posix())
    try:
        res = importlib.import_module(mpath.stem)
        return res
    finally:
        sys.path.pop()


from .common import Entry, Visit, History, Filter, make_filter, get_logger, get_tmpdir, merge_histories
from .render import render

# TODO smart is misleading... perhaps, get rid of it?
from wereyouhere.generator.smart import previsits_to_history

def run(config_file: str):
    logger = get_logger()

    config = import_config(config_file)

    fallback_tz = config.FALLBACK_TIMEZONE
    extractors = config.EXTRACTORS

    output_dir = Path(config.OUTPUT_DIR)
    if not output_dir.exists():
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    filters = [make_filter(f) for f in config.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..


    all_histories = []
    had_errors = False

    for extractor in extractors:
        hist, errors = previsits_to_history(extractor)
        if len(errors) > 0:
            had_errors = True
        all_histories.append(hist)

    urls_json = output_dir.joinpath('linksdb.json')

    history = merge_histories(all_histories)
    j = render(history, fallback_timezone=fallback_tz)
    with urls_json.open('w') as fo:
        json.dump(j, fo, indent=1, ensure_ascii=False)

    if had_errors:
        exit(1)


def main():
    from kython.klogging import setup_logzero
    setup_logzero(get_logger(), level=logging.DEBUG)

    p = argparse.ArgumentParser()
    p.add_argument('--config', default='config.py')
    args = p.parse_args()

    try:
        run(config_file=args.config)
    except:
        tdir = get_tmpdir()
        tdir.cleanup()
        raise

main()

# TODO move to kython?
def cwd_import(name: str):
    import os, sys, importlib
    sys.path.append(os.getcwd())
    res = importlib.import_module(name)
    sys.path.pop()
    return res

import logging

import inspect
import os.path
from sys import exit
from typing import List, Tuple

from .common import Entry, Visit, History, Filter, make_filter, get_logger, get_tmpdir
from .render import render

# TODO smart is misleading... perhaps, get rid of it?
from wereyouhere.generator.smart import previsits_to_history

def run():
    logger = get_logger()

    config = cwd_import('config')

    fallback_tz = config.FALLBACK_TIMEZONE

    extractors = config.EXTRACTORS
    output_dir = config.OUTPUT_DIR
    filters = [make_filter(f) for f in config.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..

    if output_dir is None or not os.path.lexists(output_dir):
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    all_histories = []
    had_errors = False

    for extractor in extractors:
        hist, errors = previsits_to_history(extractor)
        if len(errors) > 0:
            had_errors = True
        all_histories.append(hist)

    urls_json = os.path.join(output_dir, 'linksdb.json')
    render(all_histories, urls_json, fallback_timezone=fallback_tz)

    if had_errors:
        exit(1)


def main():
    from kython.klogging import setup_logzero
    setup_logzero(get_logger(), level=logging.DEBUG)
    try:
        run()
    except:
        tdir = get_tmpdir()
        tdir.cleanup()
        raise

main()

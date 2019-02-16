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

from .common import Entry, Visit, History, simple_history, Filter, make_filter, get_logger, get_tmpdir
from .render import render


def run():
    logger = get_logger()
    from kython.klogging import setup_logzero
    setup_logzero(logger, level=logging.DEBUG)

    config = cwd_import('config')

    fallback_tz = config.FALLBACK_TIMEZONE

    errors = False
    takeout_path = config.GOOGLE_TAKEOUT_PATH
    custom_extractors = config.CUSTOM_EXTRACTORS
    extractors = config.EXTRACTORS
    output_dir = config.OUTPUT_DIR
    filters = [make_filter(f) for f in config.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..

    if output_dir is None or not os.path.lexists(output_dir):
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    all_histories = []

    def log_hists(histories: List[History], from_: str):
        lengths = [len(h) for h in histories]
        logger.info(f"Got {len(histories)} Histories from {from_}: {lengths}")

    if takeout_path is not None:
        import wereyouhere.generator.takeout as takeout_gen
        try:
            takeout_histories = list(takeout_gen.get_takeout_histories(takeout_path))
        except Exception as e:
            logger.exception(e)
            logger.error("Error while processing google takeout")
            errors = True
        else:
            all_histories.extend(takeout_histories)
            log_hists(takeout_histories, 'Google Takeout')
    else:
        logger.warning("GOOGLE_TAKEOUT_PATH is not set, not using Google Takeout for populating extension DB!")

    for tag, extractor in custom_extractors:
        import wereyouhere.generator.custom as custom_gen
        logger.info(f"Running extractor {extractor} (tag {tag})")
        try:
            custom_histories: List[History]
            if isinstance(extractor, str): # must be shell command
                custom_histories = [custom_gen.get_custom_history(extractor, tag)]
            elif inspect.isfunction(extractor):
                urls = extractor()
                custom_histories = [simple_history(urls, tag)]
            else:
                raise RuntimeError(f'{type(extractor)}')
        except Exception as e:
            logger.exception(e)
            logger.error(f'Error while curring exctractor {extractor}')
        else:
            log_hists(custom_histories, str(extractor))
            all_histories.extend(custom_histories)

    for extractor in extractors:
        hist = extractor()
        all_histories.append(hist)

    urls_json = os.path.join(output_dir, 'linksdb.json')
    render(all_histories, urls_json, fallback_timezone=fallback_tz)

    if errors:
        exit(1)


def main():

    logging.basicConfig(level=logging.INFO)
    try:
        run()
    except:
        tdir = get_tmpdir()
        tdir.cleanup()
        raise

main()

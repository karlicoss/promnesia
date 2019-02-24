import argparse
import os.path
import logging
import json
import inspect
from sys import exit
from typing import List, Tuple, Optional
from pathlib import Path
from datetime import datetime

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
from wereyouhere.generator.smart import previsits_to_history, Wrapper

def run(config_file: str, intermediate: Optional[str]):
    logger = get_logger()

    config = import_config(config_file)

    fallback_tz = config.FALLBACK_TIMEZONE
    extractors = config.EXTRACTORS

    output_dir = Path(config.OUTPUT_DIR)
    if not output_dir.exists():
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    intm = output_dir.joinpath('intermediate') if intermediate is None else Path(intermediate)
    intm.mkdir(exist_ok=True)

    filters = [make_filter(f) for f in config.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..


    all_histories = []
    had_errors = False

    for extractor in extractors:
        ex = extractor
        # TODO isinstance wrapper?
        # TODO make more defensive?
        einfo: str
        if isinstance(ex, Wrapper):
            einfo = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs}'
        else:
            einfo = f'{ex.__module__}:{ex.__name__}'

        hist, errors = previsits_to_history(extractor)
        if len(errors) > 0:
            had_errors = True
        all_histories.append((einfo, hist))

    # this is intermediate, to make future raw data comparisons easier...
    intermediates = []
    for e, h in all_histories:
        cur = []
        # TODO what do we do in case of parity?
        for entry in sorted(h.urls.values(), key=lambda e: e.url):
            url = entry.url
            visits = list(sorted(entry.visits, key=lambda v: (v.dt.isoformat(), v.context or ''))) # isoformat just to get away with comparing aware/unaware...
            cur.append({
                'url': url,
                'visits': [{
                    'dt': v.dt.isoformat(), # hopefully that's ok; python 3.7 is capable of deserializing it, but I might have to backport it
                    'tag': v.tag,
                    'context': v.context,
                } for v in visits],
            })
        intermediates.append((e, cur))
    with intm.joinpath(datetime.utcnow().strftime('%Y%m%d%H%M%S.json')).open('w') as fo:
        json.dump(intermediates, fo, ensure_ascii=False, sort_keys=True, indent=1)

    history = merge_histories([h for _, h in all_histories])
    j = render(history, fallback_timezone=fallback_tz)

    urls_json = output_dir.joinpath('linksdb.json')
    with urls_json.open('w') as fo:
        json.dump(j, fo, indent=1, ensure_ascii=False)

    if had_errors:
        exit(1)


def main():
    from kython.klogging import setup_logzero
    setup_logzero(get_logger(), level=logging.DEBUG)

    p = argparse.ArgumentParser()
    p.add_argument('--config', default='config.py')
    p.add_argument('--intermediate', required=False)
    # TODO maybe, it's better for server to compute intermediate represetnation?
    # the only downside is storage. dunno.
    # worst case -- could use database?
    args = p.parse_args()

    try:
        run(config_file=args.config, intermediate=args.intermediate)
    except:
        tdir = get_tmpdir()
        tdir.cleanup()
        raise

main()

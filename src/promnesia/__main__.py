import argparse
import os.path
import logging
import inspect
import sys
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from datetime import datetime


from kython.ktyping import PathIsh


from .common import History, Filter, make_filter, get_logger, get_tmpdir
from . import config
from .dump import dump_histories

from .common import previsits_to_history, Indexer



def _do_index():
    cfg = config.get()

    logger = get_logger()

    fallback_tz = cfg.FALLBACK_TIMEZONE
    indexers = cfg.INDEXERS

    output_dir = Path(cfg.OUTPUT_DIR)
    if not output_dir.exists():
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    filters = [make_filter(f) for f in cfg.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..


    all_histories = []
    all_errors = []

    for extractor in indexers:
        ex = extractor
        # TODO isinstance indexer?
        # TODO make more defensive?
        einfo: str
        if isinstance(ex, Indexer):
            einfo = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs}'
        else:
            einfo = f'{ex.__module__}:{ex.__name__}'

        assert isinstance(ex, Indexer)

        hist, errors = previsits_to_history(extractor, src=ex.src)
        all_errors.extend(errors)
        all_histories.append((einfo, hist))

    # TODO perhaps it's better to open connection and dump as we collect so it consumes less memory?
    dump_histories(all_histories, config=cfg)

    if len(all_errors) > 0:
        sys.exit(1)


def do_index(config_file: Path):
    try:
        config.load_from(config_file)
        _do_index()
    finally:
        config.reset()


def adhoc_indexers():
    from .indexers import custom, browser, takeout
    return {
        # TODO rename to plaintext?
        'simple': custom.simple,
        # TODO org mode

        # TODO ugh, this runs against merged db
        # 'chrome' : browser.chrome,
        # 'firefox': browser.firefox,
        'takeout': takeout.extract,
    }


def do_adhoc(indexer: str, *args):
    # TODO logging?
    idx = adhoc_indexers()[indexer]
    for visit in idx(*args):
        print(visit)
    print("Finished extracting {} {}".format(indexer, *args))
    # TODO color?


from .promnesia_server import setup_parser, run as do_serve

def main():
    from kython.klogging import setup_logzero
    setup_logzero(get_logger(), level=logging.DEBUG)

    p = argparse.ArgumentParser()
    subp = p.add_subparsers(dest='mode')
    ep = subp.add_parser('index')
    ep.add_argument('--config', type=Path, default=Path('config.py'))
    # TODO use some way to override or provide config only via cmdline?
    ep.add_argument('--intermediate', required=False)

    sp = subp.add_parser('serve')
    setup_parser(sp)

 # TODO not sure what would be a good name?
    ap = subp.add_parser('adhoc')
    # TODO use docstring or something?
    ap.add_argument(
        'indexer',
        choices=list(sorted(adhoc_indexers().keys())),
        help='Indexer name',
    )
    ap.add_argument('params', nargs='*')

    args = p.parse_args()

    # TODO maybe, it's better for server to compute intermediate represetnation?
    # the only downside is storage. dunno.
    # worst case -- could use database?

    with get_tmpdir() as tdir: # TODO??
        if args.mode == 'index':
            do_index(config_file=args.config)
        elif args.mode == 'serve':
            do_serve(port=args.port, config=args.config, quiet=args.quiet)
        elif args.mode == 'adhoc':
            do_adhoc(args.indexer, *args.params)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')

if __name__ == '__main__':
    main()

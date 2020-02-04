import argparse
import os.path
import logging
import inspect
import sys
from typing import List, Tuple, Optional, Dict
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory


from .common import PathIsh, History, Filter, make_filter, get_logger, get_tmpdir
from . import config
from .dump import dump_histories

from .common import previsits_to_history, Indexer



def _do_index():
    cfg = config.get()

    logger = get_logger()

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
        if callable(ex):
            # lazy indexers
            ex = ex()
        assert isinstance(ex, Indexer)

        einfo = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs}'

        hist, errors = previsits_to_history(ex, src=ex.src)
        all_errors.extend(errors)
        all_histories.append((einfo, hist))

    # TODO perhaps it's better to open connection and dump as we collect so it consumes less memory?
    dump_histories(all_histories)

    if len(all_errors) > 0:
        sys.exit(1)


def do_index(config_file: Path):
    try:
        config.load_from(config_file)
        _do_index()
    finally:
        config.reset()




def adhoc_indexers():
    def lazy(name: str):
        # helper to avoid failed imports etc, since people might be lacking necessary dependencies
        def inner(*args, **kwargs):
            from . import indexers
            import importlib
            module = importlib.import_module('promnesia.indexers' + '.' + name)
            return getattr(module, 'index')
        return inner

    return {

        # TODO ugh, this runs against merged db
        # 'chrome' : browser.chrome,
        # 'firefox': browser.firefox,
        'auto'    : lazy('auto'),
        # TODO org mode

        'takeout' : lazy('takeout'),
        'telegram': lazy('telegram'),
    }


from .promnesia_server import setup_parser, run as do_serve


def do_adhoc(indexer: str, *args, port: Optional[str]):
    logger = get_logger()
    from pprint import pprint
    # TODO logging?
    idx = adhoc_indexers()[indexer]()

    idxr = Indexer(idx, *args, src='adhoc')
    hist, errors = previsits_to_history(idxr, src=idxr.src)

    for e in errors:
        logger.error(e)
    logger.info("Finished indexing {} {}, {} total".format(indexer, args, len(hist)))
    # TODO color?
    from . import config
    with TemporaryDirectory() as tdir:
        outdir = Path(tdir)
        cfg = config.Config(
            OUTPUT_DIR=outdir,
            INDEXERS=[],
        )
        config.instance = cfg
        dump_histories([('adhoc', hist)])

        if port is None:
            logger.warning("Port isn't specified, not serving!")
        else:
            do_serve(port=port, db=outdir / 'promnesia.sqlite', timezone='Europe/London', quiet=False) # TODO FIXME TZ

        if sys.stdin.isatty():
            input("Press any key when ready")



def main():
    from .common import setup_logger
    setup_logger(get_logger(), level=logging.DEBUG)

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
    ap.add_argument('--port', type=str, help='Port to serve (omit in order to index only)', required=False)
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
            do_serve(port=args.port, db=args.db, timezone=args.timezone, quiet=args.quiet)
        elif args.mode == 'adhoc':
            do_adhoc(args.indexer, *args.params, port=args.port)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')

if __name__ == '__main__':
    main()

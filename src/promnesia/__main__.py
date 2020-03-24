import argparse
import os
import logging
import inspect
import sys
from typing import List, Tuple, Optional, Dict, Sequence
from pathlib import Path
from datetime import datetime
from tempfile import TemporaryDirectory


from . import config
from . import server
from .misc import install_server
from .common import PathIsh, History, make_filter, get_logger, get_tmpdir
from .common import previsits_to_history, Indexer
from .dump import dump_histories


def _do_index():
    cfg = config.get()

    logger = get_logger()

    indexers = cfg.INDEXERS

    output_dir = Path(cfg.OUTPUT_DIR)
    if not output_dir.exists():
        raise ValueError(f"Expected OUTPUT_DIR({output_dir}) to exist")

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


def demo_indexers():
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
        'guess'   : lazy('guess')
    }



def do_demo(index_as: str, params: Sequence[str], port: Optional[str]):
    logger = get_logger()
    from pprint import pprint
    # TODO logging?
    idx = demo_indexers()[index_as]()

    idxr = Indexer(idx, *params, src='demo')
    hist, errors = previsits_to_history(idxr, src=idxr.src)

    for e in errors:
        logger.error(e)
    logger.info("Finished indexing {} {}, {} total".format(index_as, params, len(hist)))
    # TODO color?
    with TemporaryDirectory() as tdir:
        outdir = Path(tdir)
        cfg = config.Config(
            OUTPUT_DIR=outdir,
            INDEXERS=[],
        )
        config.instance = cfg
        dump_histories([('demo', hist)])

        if port is None:
            logger.warning("Port isn't specified, not serving!")
        else:
            server._run(port=port, db=outdir / 'promnesia.sqlite', timezone='Europe/London', quiet=False) # TODO FIXME TZ

        if sys.stdin.isatty():
            input("Press any key when ready")


def main():
    # TODO longer, literate description?
    from .common import setup_logger
    setup_logger(get_logger(), level=logging.DEBUG)

    F = argparse.ArgumentDefaultsHelpFormatter
    p = argparse.ArgumentParser(formatter_class=F)
    # p.add_argument('--hello', required=False, default='YES', help='alala')
    subp = p.add_subparsers(dest='mode', )
    ep = subp.add_parser('index', help='Create/update the link database', formatter_class=F)
    ep.add_argument('--config', type=Path, default=Path('config.py'))
    # TODO use some way to override or provide config only via cmdline?
    ep.add_argument('--intermediate', required=False)

    sp = subp.add_parser('serve', help='Serve a link database', formatter_class=F)
    server.setup_parser(sp)

    # TODO not sure what would be a good name? rename to 'demo'?
    ap = subp.add_parser('demo', help='Demo mode: index and serve a directory in single command', formatter_class=F)
    # TODO use docstring or something?
    ap.add_argument('--port', type=str, help='Port to serve. If omitted, will only create the index without serving.', required=False)
    ap.add_argument(
        '--as',
        choices=list(sorted(demo_indexers().keys())),
        default='guess',
        help='Index the path as',
    )
    ap.add_argument('params', nargs='*', help='Optional extra params for the indexer')

    isp = subp.add_parser('install-server', help='Install server as a systemd service (for autostart)', formatter_class=F)
    install_server.setup_parser(isp)

    args = p.parse_args()

    # TODO is there a way to print full help? i.e. for all subparsers
    if args.mode is None:
        print('ERROR: Please specify a mode', file=sys.stderr)
        p.print_help(sys.stderr)
        sys.exit(1)

    # TODO maybe, it's better for server to compute intermediate represetnation?
    # the only downside is storage. dunno.
    # worst case -- could use database?

    with get_tmpdir() as tdir: # TODO??
        if args.mode == 'index':
             do_index(config_file=args.config)
        elif args.mode == 'serve':
            server.run(args)
        elif args.mode == 'demo':
            do_demo(index_as=getattr(args, 'as'), params=args.params, port=args.port)
        elif args.mode == 'install-server':
            install_server.install(args)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')

if __name__ == '__main__':
    main()

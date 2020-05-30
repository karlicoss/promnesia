import argparse
import os
import logging
import inspect
import sys
from typing import List, Tuple, Optional, Dict, Sequence, Iterable
from pathlib import Path
from datetime import datetime
from subprocess import check_call
from tempfile import TemporaryDirectory


from . import config
from . import server
from .misc import install_server
from .common import PathIsh, History, make_filter, get_logger, get_tmpdir
from .common import previsits_to_history, Source, appdirs
from .dump import dump_histories


def _do_index() -> Iterable[Exception]:
    cfg = config.get()

    logger = get_logger()

    indexers = cfg.sources

    output_dir = cfg.output_dir
    if not output_dir.exists():
        logger.warning("OUTPUT_DIR '%s' didn't exist, creating", output_dir)
        output_dir.mkdir(exist_ok=True)

    filters = [make_filter(f) for f in cfg.FILTERS]
    for f in filters:
        History.add_filter(f) # meh..


    all_histories = []
    errors = []

    for idx in indexers:
        if isinstance(idx, Exception):
            errors.append(idx)
            continue
        # TODO more defensive! e.g. might not have __module__
        einfo = f'{idx.ff.__module__}:{idx.ff.__name__} {idx.args} {idx.kwargs}'

        hist, err = previsits_to_history(idx, src=idx.name)
        errors.extend(err)
        all_histories.append((einfo, hist))

    # TODO perhaps it's better to open connection and dump as we collect so it consumes less memory?
    dump_histories(all_histories)

    return errors


def do_index(config_file: Path):
    config.load_from(config_file)
    try:
        errors = _do_index()
    finally:
        config.reset()
    if len(list(errors)) > 0:
        sys.exit(1)


def demo_sources():
    def lazy(name: str):
        # helper to avoid failed imports etc, since people might be lacking necessary dependencies
        def inner(*args, **kwargs):
            from . import sources
            import importlib
            module = importlib.import_module('promnesia.sources' + '.' + name)
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



def do_demo(*, index_as: str, params: Sequence[str], port: Optional[str], config_file: Optional[Path]):
    logger = get_logger()
    from pprint import pprint
    with TemporaryDirectory() as tdir:
        outdir = Path(tdir)

        if config_file is not None:
            config.load_from(config_file)
        else:
            idx = demo_sources()[index_as]()
            src = Source(idx, *params)
            cfg = config.Config(
                OUTPUT_DIR=outdir,
                SOURCES=[src],
            )
            config.instance = cfg

        errors = _do_index()
        for e in errors:
            logger.error(e)

        if port is None:
            logger.warning("Port isn't specified, not serving!")
        else:
            server._run(port=port, db=config.get().output_dir / 'promnesia.sqlite', timezone=server.get_system_tz(), quiet=False)

        if sys.stdin.isatty():
            input("Press any key when ready")


def user_config_file() -> Path:
    return Path(appdirs().user_config_dir) / 'config.py'


def default_config_path() -> Path:
    cfg = Path('config.py')
    if cfg.exists():
        # eh. not sure if it's a good idea, but whatever, it was the old behaviour
        return cfg.absolute()
    else:
        return user_config_file()
    # TODO need to test this..


def config_create(args):
    logger = get_logger()
    cfg = user_config_file()
    cfgdir = cfg.parent
    if cfgdir.exists():
        logger.error('Config directory %s already exists. Aborting', cfgdir)
        sys.exit(1)
    else:
        # TODO ugh. example config might not be in the repository
        stub = """
from promnesia import Source
from promnesia.sources import auto

'''
List of sources to use
You can specify your own, add more sources, etc.
See https://github.com/karlicoss/promnesia#setup for more information
'''
SOURCES = [
    Source(
        auto.index,
        # just some arbitrary directory with html files
        '/usr/share/doc/python3/html/faq',
    )
]
"""
        cfgdir.mkdir(parents=True)
        cfg.write_text(stub)
        logger.info("Created a stub config in %s. Edit it to tune to your linking.", cfg)


def config_check(args):
    cfg = args.config
    logger = get_logger()

    # TODO add this to HPI
    logger.info('Checking syntax...')
    check_call(['python3', '-m', 'compileall', cfg])

    # todo not sure if should be more defensive than check_call here
    logger.info('Checking type safety...')
    try:
        import mypy
    except ImportError:
        logger.warning("mypy not found, can't use it to check config!")
    else:
        check_call([
            'python3', '-m', 'mypy',
            '--namespace-packages',
            '--color-output', # not sure if works??
            '--pretty',
            '--show-error-codes',
            '--show-error-context',
            '--check-untyped-defs',
            cfg,
        ])

    logger.info('Checking runtime errors...')
    check_call(['python3', cfg])



def main():
    # TODO longer, literate description?
    from .common import setup_logger
    setup_logger(get_logger(), level=logging.DEBUG)

    F = lambda prog: argparse.ArgumentDefaultsHelpFormatter(prog, width=120)
    p = argparse.ArgumentParser(formatter_class=F) # type: ignore
    subp = p.add_subparsers(dest='mode', )
    ep = subp.add_parser('index', help='Create/update the link database', formatter_class=F)
    ep.add_argument('--config', type=Path, default=default_config_path(), help='Config path')
    # TODO use some way to override or provide config only via cmdline?
    ep.add_argument('--intermediate', required=False, help="Used for development, you don't need it")

    sp = subp.add_parser('serve', help='Serve a link database', formatter_class=F) # type: ignore
    server.setup_parser(sp)

    ap = subp.add_parser('demo', help='Demo mode: index and serve a directory in single command', formatter_class=F)
    # TODO use docstring or something?
    #

    ap.add_argument('--port', type=str, default='13131'              , help='Port to serve on')
    ap.add_argument('--no-serve', action='store_false', dest='server', help='Pass to only index without running server')
    ap.add_argument('--config', type=Path, required=False            , help='Config to run against. If omitted, will use empty base config')
    ap.add_argument(
        '--as',
        choices=list(sorted(demo_sources().keys())),
        default='guess',
        help='Index the path as',
    )
    ap.add_argument('params', nargs='*', help='Optional extra params for the indexer')

    isp = subp.add_parser('install-server', help='Install server as a systemd service (for autostart)', formatter_class=F)
    install_server.setup_parser(isp)

    cp = subp.add_parser('config', help='Config management')
    scp = cp.add_subparsers()
    ccp = scp.add_parser('check', help='Check config')
    ccp.set_defaults(func=config_check)
    ccp.add_argument('--config', type=Path, default=default_config_path(), help='Config path')

    icp = scp.add_parser('create', help='Create user config')
    icp.set_defaults(func=config_create)

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
            do_demo(index_as=getattr(args, 'as'), params=args.params, port=args.port, config_file=args.config)
        elif args.mode == 'install-server': # todo rename to 'autostart' or something?
            install_server.install(args)
        elif args.mode == 'config':
            args.func(args)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')

if __name__ == '__main__':
    main()

import argparse
import logging
import inspect
import sys
from typing import List, Tuple, Optional, Dict, Sequence, Iterable, Iterator, Union
from pathlib import Path
from datetime import datetime
from .compat import check_call, register_argparse_extend_action_in_pre_py38
from tempfile import TemporaryDirectory


from . import config
from . import server
from .misc import install_server
from .common import PathIsh, logger, get_tmpdir, DbVisit, Res
from .common import Source, get_system_tz, user_config_file, default_config_path
from .dump import visits_to_sqlite
from .extract import extract_visits, make_filter


def iter_all_visits(sources_subset: Iterable[Union[str, int]]=()) -> Iterator[Res[DbVisit]]:
    cfg = config.get()
    output_dir = cfg.output_dir
    # not sure if belongs here??
    if not output_dir.exists():
        logger.warning("OUTPUT_DIR '%s' didn't exist, creating", output_dir)
        output_dir.mkdir(exist_ok=True, parents=True)

    hook = cfg.hook

    sources = list(cfg.sources)

    is_subset_sources = bool(sources_subset)
    if is_subset_sources:
        sources_subset = set(sources_subset)

    for i, source in enumerate(sources):
        # TODO why would it not be present??
        name = getattr(source, "name", None)
        if name and is_subset_sources:
            matched = name in sources_subset or i in sources_subset
            if matched:
                sources_subset -= {i, name}  # type: ignore
            else:
                logger.debug("skipping '%s' not in --sources.", name)
                continue

        if isinstance(source, Exception):
            yield source
            continue

        if not isinstance(source, Source):
            # just in case cause previously it was technically possible to be something else
            # but I think that was a dead codepath
            yield RuntimeError(f"Shouldn't have gotten this as a source: {source}")
            continue

        # todo hmm it's not even used??
        einfo = source.description
        for v in extract_visits(source, src=source.name):
            if hook is None:
                yield v
            else:
                try:
                    yield from hook(v)
                except Exception as e:
                    yield e

    if sources_subset:
        logger.warning("unknown --sources: %s", ", ".join(repr(i) for i in sources_subset))


def _do_index(dry: bool=False, sources_subset: Iterable[Union[str, int]]=(), overwrite_db: bool=False) -> Iterable[Exception]:
    # also keep & return errors for further display
    errors: List[Exception] = []
    def it() -> Iterable[Res[DbVisit]]:
        for v in iter_all_visits(sources_subset):
            if isinstance(v, Exception):
                errors.append(v)
            yield v

    if dry:
        res = list(it())
        logger.warning("DRY MODE: won't modify the database. Printing the results out")
        for v in res:
            print(v)
    else:
        dump_errors = visits_to_sqlite(it(), overwrite_db=overwrite_db)
        for e in dump_errors:
            logger.exception(e)
            errors.append(e)
    return errors


def do_index(
        config_file: Path,
        dry: bool=False,
        sources_subset: Iterable[Union[str, int]]=(),
        overwrite_db: bool=False,
    ) -> None:
    config.load_from(config_file) # meh.. should be cleaner
    try:
        errors = list(_do_index(dry=dry, sources_subset=sources_subset, overwrite_db=overwrite_db))
    finally:
        config.reset()
    if len(errors) > 0:
        logger.error('%d errors, printing them out:', len(errors))
        for e in errors:
            logger.exception(e)
        logger.error('%d errors, exit code 1', len(errors))
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

    res = {}
    import ast
    import promnesia.sources
    for p in promnesia.sources.__path__: # type: ignore[attr-defined] # should be present
        for x in sorted(Path(p).glob('*.py')):
            a = ast.parse(x.read_text())
            candidates = [c for c in a.body if getattr(c, 'name', None) == 'index']
            if len(candidates) > 0:
                res[x.stem] = lazy(x.stem)
    return res


def do_demo(
        *,
        index_as: str,
        params: Sequence[str],
        port: Optional[str],
        config_file: Optional[Path],
        dry: bool=False,
        name: str='demo',
        sources_subset: Iterable[Union[str, int]]=(),
        overwrite_db: bool=False,
    ) -> None:
    from pprint import pprint
    with TemporaryDirectory() as tdir:
        outdir = Path(tdir)

        if config_file is not None:
            config.load_from(config_file)
        else:
            idx = demo_sources()[index_as]()
            src = Source(idx, *params, name=name)
            cfg = config.Config(
                OUTPUT_DIR=outdir,
                SOURCES=[src],
            )
            config.instance = cfg

        errors = list(_do_index(dry=dry, sources_subset=sources_subset, overwrite_db=overwrite_db))
        if len(errors) > 0:
            logger.error('%d errors during indexing (see logs above for backtraces)', len(errors))
        for e in errors:
            logger.error(e)

        dbp = config.get().db
        if port is None:
            logger.warning(f"Port isn't specified, not serving!\nYou can inspect the database in the meantime, e.g. 'sqlitebrowser {dbp}'")
        else:
            from .server import ServerConfig
            server._run(
                host='127.0.0.1',
                port=port,
                quiet=False,
                config=ServerConfig(
                    db=dbp,
                    timezone=get_system_tz()
                ),
            )

        if sys.stdin.isatty():
            input("Press any key when ready")


def read_example_config() -> str:
    import inspect
    from .misc import config_example
    return inspect.getsource(config_example)


def config_create(args: argparse.Namespace) -> None:
    cfg = user_config_file()
    cfgdir = cfg.parent
    if cfgdir.exists():
        logger.error('Config directory %s already exists. Aborting', cfgdir)
        sys.exit(1)
    else:
        stub = read_example_config()
        cfgdir.mkdir(parents=True)
        cfg.write_text(stub)
        logger.info("Created a stub config in '%s'. Edit it to tune to your liking. (see https://github.com/karlicoss/promnesia#setup for more info)", cfg)


def config_check(args: argparse.Namespace) -> None:
    cfg: Path = args.config
    errors = list(_config_check(cfg))
    if len(errors) == 0:
        logger.info('OK')
    else:
        logger.error('CHECK FAILED')
        sys.exit(1)


def _config_check(cfg: Path) -> Iterable[Exception]:
    from .compat import run

    logger.info('config: %s', cfg)

    def check(cmd) -> Iterable[Exception]:
        logger.debug(' '.join(map(str, cmd)))
        res = run(cmd)
        if res.returncode > 0:
            yield Exception()

    logger.info('Checking syntax...')
    cmd = [sys.executable, '-m', 'compileall', cfg]
    yield from check(cmd)

    # todo not sure if should be more defensive than check_call here
    logger.info('Checking type safety...')
    try:
        import mypy
    except ImportError:
        logger.warning("mypy not found, can't use it to check config!")
    else:
        yield from check([
            sys.executable, '-m', 'mypy',
            '--namespace-packages',
            '--color-output', # not sure if works??
            '--pretty',
            '--show-error-codes',
            '--show-error-context',
            '--check-untyped-defs',
            cfg,
        ])

    logger.info('Checking runtime errors...')
    yield from check([sys.executable, cfg])


def cli_doctor_db(args: argparse.Namespace) -> None:
    # todo could fallback to 'sqlite3 <db> .dump'?
    config.load_from(args.config) # TODO meh
    db = config.get().db
    if not db.exists():
        logger.error("Database {db} doesn't exist!")
        sys.exit(1)
    else:
        logger.info(f'OK, database exists: {db}')

    cmd = ['sqlite3', str(db), 'select src, COUNT(*) from visits GROUP BY src']
    logger.info(f'Querying database summary: {cmd}')
    check_call(cmd)

    bro = 'sqlitebrowser'
    import shutil
    if not shutil.which(bro):
        logger.error(f'Install {bro} to inspect the database!')
        sys.exit(1)
    cmd = [bro, str(db)]
    logger.debug(f'Running {cmd}')
    from .compat import Popen
    Popen(cmd)


def cli_doctor_server(args: argparse.Namespace) -> None:
    port = args.port
    endpoint = f'http://localhost:{port}/status'
    cmd = ['curl', endpoint]
    logger.info(f'Running {cmd}')
    check_call(cmd)
    print() # curl doesn't add newline
    logger.info('You should see the database path and version above!')


def _ordinal_or_name(s: str) -> Union[str, int]:
    try:
        s = int(s)  # type: ignore
    except ValueError:
        pass
    return s


def main() -> None:
    # TODO longer, literate description?

    def add_index_args(parser: argparse.ArgumentParser, default_config_path: Optional[PathIsh]=None) -> None:
        """
        :param default_config_path:
            if not given, all :func:`demo_sources()` are run
        """
        register_argparse_extend_action_in_pre_py38(parser)
        parser.add_argument('--config', type=Path, default=default_config_path, help='Config path')
        parser.add_argument('--dry', action='store_true', help="Dry run, won't touch the database, only print the results out")
        parser.add_argument(
            '--sources',
            required=False,
            action="extend",
            nargs="+",
            type=_ordinal_or_name,
            metavar="SOURCE",
            help="Source names (or their 0-indexed position) to index.",
        )
        parser.add_argument(
            '--overwrite',
            required=False,
            action="store_true",
            help="Empty db before populating it with newly indexed visits."
            "  If interrupted, db is left untouched."
        )

    F = lambda prog: argparse.ArgumentDefaultsHelpFormatter(prog, width=120)
    p = argparse.ArgumentParser(formatter_class=F) # type: ignore
    subp = p.add_subparsers(dest='mode', )
    ep = subp.add_parser('index', help='Create/update the link database', formatter_class=F)
    add_index_args(ep, default_config_path())
    # TODO use some way to override or provide config only via cmdline?
    ep.add_argument('--intermediate', required=False, help="Used for development, you don't need it")

    sp = subp.add_parser('serve', help='Serve a link database', formatter_class=F) # type: ignore
    server.setup_parser(sp)

    ap = subp.add_parser('demo', help='Demo mode: index and serve a directory in single command', formatter_class=F)
    # TODO use docstring or something?
    #

    add_port_arg = lambda p: p.add_argument('--port', type=str, default='13131'              , help='Port to serve on')

    ap.add_argument('--name', type=str, default='demo'               , help='Set custom source name')
    add_port_arg(ap)
    ap.add_argument('--no-serve', action='store_const', const=None, dest='port', help='Pass to only index without running server')
    ap.add_argument(
        '--as',
        choices=list(sorted(demo_sources().keys())),
        default='guess',
        help='Promnesia source to index as (see https://github.com/karlicoss/promnesia/tree/master/src/promnesia/sources for the full list)',
    )
    add_index_args(ap)
    ap.add_argument('params', nargs='*', help='Optional extra params for the indexer')

    isp = subp.add_parser('install-server', help='Install server as a systemd service (for autostart)', formatter_class=F)
    install_server.setup_parser(isp)

    cp = subp.add_parser('config', help='Config management')
    cp.set_defaults(func=lambda *args: cp.print_help())
    scp = cp.add_subparsers()
    ccp = scp.add_parser('check', help='Check config')
    ccp.set_defaults(func=config_check)
    ccp.add_argument('--config', type=Path, default=default_config_path(), help='Config path')

    icp = scp.add_parser('create', help='Create user config')
    icp.add_argument(
        "--config", type=Path, default=default_config_path(), help="Config path"
    )
    icp.set_defaults(func=config_create)

    dp = subp.add_parser('doctor', help='Troubleshooting assistant')
    dp.add_argument('--config', type=Path, default=default_config_path(), help='Config path')
    dp.set_defaults(func=lambda *args: dp.print_help())
    sdp = dp.add_subparsers()
    sdp.add_parser('config'  , help='Check config'    ).set_defaults(func=config_check )
    sdp.add_parser('database', help='Inspect database').set_defaults(func=cli_doctor_db)
    sdps = sdp.add_parser('server'  , help='Check server'    )
    sdps.set_defaults(func=cli_doctor_server)
    add_port_arg(sdps)

    args = p.parse_args()

    # TODO is there a way to print full help? i.e. for all subparsers
    if args.mode is None:
        print('ERROR: Please specify a mode', file=sys.stderr)
        p.print_help(sys.stderr)
        sys.exit(1)

    logger.info("CLI args: %s", args)

    # TODO maybe, it's better for server to compute intermediate representations?
    # the only downside is storage. dunno.
    # worst case -- could use database?

    with get_tmpdir() as tdir: # TODO??
        if args.mode == 'index':
            do_index(
                config_file=args.config,
                dry=args.dry,
                sources_subset=args.sources,
                overwrite_db=args.overwrite,
            )
        elif args.mode == 'serve':
            server.run(args)
        elif args.mode == 'demo':
            # TODO not sure if 'as' is that useful
            # something like Telegram/Takeout is too hard to setup to justify adhoc mode like this?
            do_demo(
                index_as=getattr(args, 'as'),
                params=args.params,
                port=args.port,
                config_file=args.config,
                dry=args.dry,
                name=args.name,
                sources_subset=args.sources,
                overwrite_db=args.overwrite,
                )
        elif args.mode == 'install-server': # todo rename to 'autostart' or something?
            install_server.install(args)
        elif args.mode == 'config':
            args.func(args)
        elif args.mode == 'doctor':
            args.func(args)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')

if __name__ == '__main__':
    main()

import argparse
import os.path
import logging
import json
import inspect
import sys
from typing import List, Tuple, Optional
from pathlib import Path
from datetime import datetime


from kython.ktyping import PathIsh


from .common import Config, import_config

from .common import Entry, Visit, History, Filter, make_filter, get_logger, get_tmpdir, merge_histories
from .render import render

# TODO smart is misleading... perhaps, get rid of it?
from wereyouhere.generator.smart import previsits_to_history, Wrapper

# jeez...
class hdict(dict):
    def __hash__(self):
        return hash(tuple(sorted(self.items())))

# shit, it's gonna be really hard to hack namedtuples int JSONEncoder...
# https://github.com/python/cpython/blob/dc078947a5033a048d804e244e847b5844734439/Lib/json/encoder.py#L263
# also guarantees consistent ordering...
def dictify(obj):
    if isinstance(obj, tuple) and hasattr(obj, '_asdict'):
        return dictify(obj._asdict())
    elif isinstance(obj, dict):
        return hdict({k: dictify(v) for k, v in obj.items()})
    elif isinstance(obj, (list, tuple)):
        cls = type(obj)
        return cls(dictify(x) for x in obj)
    else:
        return obj

def encoder(o):
    if isinstance(o, datetime):
        return o.isoformat() # hopefully that's ok; python 3.7 is capable of deserializing it, but I might have to backport it
    else:
        raise RuntimeError(f"can't encode {o}")


def do_extract(config: Config):
    logger = get_logger()

    fallback_tz = config.FALLBACK_TIMEZONE
    extractors = config.EXTRACTORS

    output_dir = Path(config.OUTPUT_DIR)
    if not output_dir.exists():
        raise ValueError("Expecting OUTPUT_DIR to be set to a correct path!")

    intm = output_dir / 'intermediate'
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

    logger.info('preparing intermediate state...')

    intermediates = []
    for e, h in all_histories:
        cur = []
        for entry in sorted(h.urls.values(), key=lambda e: e.url):
            # TODO ugh what do we do in case of parity?
            entry = entry._replace( # type: ignore
                visits=list(sorted(entry.visits, key=lambda v: (v.dt.isoformat(), v.context or '')))
                # isoformat just to get away with comparing aware/unaware...
            )
            cur.append(dictify(entry))
        intermediates.append((e, cur))
    intp = intm.joinpath(datetime.utcnow().strftime('%Y%m%d%H%M%S.json'))
    with intp.open('w') as fo:
        json.dump(intermediates, fo, ensure_ascii=False, sort_keys=True, indent=1, default=encoder)
    logger.info('saved intermediate state to %s', intp)

    if had_errors:
        sys.exit(1)


from .wereyouhere_server import setup_parser, run as do_serve

def main():
    from kython.klogging import setup_logzero
    setup_logzero(get_logger(), level=logging.DEBUG)

    p = argparse.ArgumentParser()
    p.add_argument('--config', type=Path, default=Path('config.py'))
    sp = p.add_subparsers(dest='mode')
    ep = sp.add_parser('extract')
    ep.add_argument('--intermediate', required=False)
    sp = sp.add_parser('serve')
    setup_parser(sp)

    args = p.parse_args()

    # TODO maybe, it's better for server to compute intermediate represetnation?
    # the only downside is storage. dunno.
    # worst case -- could use database?

    config = import_config(args.config)
    with get_tmpdir() as tdir:
        if args.mode == 'extract':
            run(config=config, intermediate=args.intermediate)
        elif args.mode == 'serve':
            do_serve(port=args.port, config=config)
        else:
            raise AssertionError(f'unexpected mode {args.mode}')


main()

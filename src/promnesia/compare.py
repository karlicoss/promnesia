#!/usr/bin/env python3
# TODO perhaps make it external script?
import argparse
from pathlib import Path
import logging
import sys
from typing import Dict, List, Any, NamedTuple, Optional, Iterator, Set, Tuple


from .common import DbVisit, Url, PathWithMtime # TODO ugh. figure out pythonpath

# TODO include latest too?
# from cconfig import ignore, filtered

def get_logger():
    return logging.getLogger('promnesia-db-changes')

# TODO return error depending on severity?


from typing import TypeVar, Sequence


T = TypeVar('T')

def eliminate_by(sa: Sequence[T], sb: Sequence[T], key):
    def make_dict(s: Sequence[T]) -> Dict[str, List[T]]:
        res: Dict[str, List[T]] = {}
        for a in s:
            k = key(a)
            ll = res.get(k, None)
            if ll is None:
                ll = []
                res[k] = ll
            ll.append(a)
        return res
    da = make_dict(sa)
    db = make_dict(sb)
    ka = set(da.keys())
    kb = set(db.keys())
    onlya: Set[T] = set()
    common: Set[T] = set()
    onlyb: Set[T] = set()
    for k in ka.union(kb):
        la = da.get(k, [])
        lb = db.get(k, [])
        common.update(la[:min(len(la), len(lb))])
        if len(la) > len(lb):
            onlya.update(la[len(lb):])
        if len(lb) > len(la):
            onlyb.update(lb[len(la):])

    return onlya, common, onlyb


def compare(before: List[DbVisit], after: List[DbVisit], between: str, *, log=True) -> List[DbVisit]:
    logger = get_logger()
    logger.info('comparing between: %s', between)

    errors: List[DbVisit] = []

    umap: Dict[Url, List[DbVisit]] = {}
    for a in after:
        url = a.norm_url
        xx = umap.get(url, []) # TODO canonify here?
        xx.append(a)
        umap[url] = xx

    def reg_error(b):
        errors.append(b)
        if log:
            logger.error('between %s missing %s', between, b)
            print('ignoreline "%s", # %s %s' % ('exid', b.norm_url, b.src), file=sys.stderr)


    # the idea is that we eliminate items simultaneously from both sets
    eliminations = [
        ('identity'               , lambda x: x),
        ('without dt'             , lambda x: x._replace(src='', dt='')),
        ('without context'        , lambda x: x._replace(src='',        context='', locator='')),
        ('without dt and context' , lambda x: x._replace(src='', dt='', context='', locator='')),
    ]
    for ename, ekey in eliminations:
        logger.info('eliminating by %s', ename)
        logger.info('before: %d, after: %d', len(before), len(after))
        before, common, after = eliminate_by(before, after, key=ekey)
        logger.info('common: %d, before: %d, after: %d', len(common), len(before), len(after))

    logger.info('removing explicitly ignored items')
    # before = filtered(before, between=between, umap=umap)
    logger.info('before: %d', len(before))

    for b in before:
        reg_error(b)

    return errors

def setup_parser(p):
    # TODO better name?
    p.add_argument('--intermediate-dir', type=Path)
    p.add_argument('--last', type=int, default=2)
    p.add_argument('--all', action='store_const', const=0, dest='last')
    p.add_argument('paths', nargs='*')


def get_files(args):
    if len(args.paths) == 0:
        int_dir = args.intermediate_dir
        assert int_dir.exists()
        files = list(sorted(int_dir.glob('*.sqlite*')))
        files = files[-args.last:]
    else:
        files = [Path(p) for p in args.paths]
    return files


def main():
    p = argparse.ArgumentParser()
    setup_parser(p)
    args = p.parse_args()
    files = get_files(args)

    errors = list(compare_files(*files))
    if len(errors) > 0:
        sys.exit(1)


def compare_files(*files: Path, log=True) -> Iterator[Tuple[str, DbVisit]]:
    assert len(files) > 0

    logger = get_logger()
    logger.info('comparing %s', files)

    last = None
    last_dts = None
    for f in files:
        logger.info('processing %r', f)
        name = f.name
        this_dts = name[0: name.index('.')] # can't use stem due to multiple extensions..

        from promnesia.server import _get_stuff # TODO ugh
        engine, binder, table = _get_stuff(PathWithMtime.make(f))

        with engine.connect() as conn:
            vis = [binder.from_row(row) for row in conn.execute(table.select())]  # type: ignore[var-annotated]

        if last is not None:
            between = f'{last_dts}:{this_dts}'
            errs = compare(last, vis, between=between, log=log)
            for e in errs:
                yield between, e
        last = vis
        last_dts = this_dts

if __name__ == '__main__':
    main()


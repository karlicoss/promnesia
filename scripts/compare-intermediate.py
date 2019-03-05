#!/usr/bin/env python3
from datetime import datetime
import argparse
from pathlib import Path
import json
import logging
from typing import Dict, List, Any, NamedTuple, Optional, Set

from kython.klogging import setup_logzero

# TODO include latest too?
from cconfig import ignore

def get_logger():
    return logging.getLogger('wereyouhere-db-changes')

int_dir = Path('intermediate')


# TODO return error depending on severity?

Url = str
Dt = str
Source = str
Context = str
Tag = str


class Visit(NamedTuple):
    url: Url
    dt: Dt
    source: Source
    context: Context
    tag: Tag


def ddiff(a, b):
    return list(sorted(a.difference(b))), list(sorted(a.intersection(b))), list(sorted(b.difference(a)))


def eliminate_by(sa, sb, key):
    def make_dict(s):
        res = {}
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
    onlya = set()
    common = set()
    onlyb = set()
    for k in ka.union(kb):
        la = da.get(k, [])
        lb = db.get(k, [])
        common.update(la[:min(len(la), len(lb))])
        if len(la) > len(lb):
            onlya.update(la[len(lb):])
        if len(lb) > len(la):
            onlyb.update(lb[len(la):])

    return onlya, common, onlyb


def compare(before: Set[Visit], after: Set[Visit], before_fdt=None):
    logger = get_logger()
    # optimisation: elimiante common

    eliminations = [
        ('identity'               , lambda x: x),
        ('without dt'             , lambda x: x._replace(source='', dt='')),
        ('without context'        , lambda x: x._replace(source='', context='')), # TODO FIXME only allow for certain tags?
        ('without dt and context' , lambda x: x._replace(source='', dt='', context='')), # ugh..
    ]
    for ename, ekey in eliminations:
        logger.info('eliminating by %s', ename)
        logger.info('before: %d, after: %d', len(before), len(after))
        before, common, after = eliminate_by(before, after, key=ekey)
        logger.info('common: %d, before: %d, after: %d', len(common), len(before), len(after))

    logger.info('removing explicitly ignored items')
    before = {b for b in before if not ignore(b, fdt=before_fdt)}
    logger.info('before: %d', len(before))


    for b in before:
        logger.warning('%s', b)

def collect(jj):
    # TODO FIXME multiset??
    visits = set()
    for src, data in sorted(jj):
        for x in data:
            for v in x['visits']:
                vs = Visit(
                    source=src,
                    url=x['url'],
                    tag=v['tag'],
                    dt=v['dt'],
                    context=v['context'] or '<no context>', # to simplify comparisons...
                )
                assert vs not in visits
                visits.add(vs)
    return visits

def main():
    setup_logzero(get_logger(), level=logging.DEBUG)
    logger = get_logger()

    last = None
    last_dt = None
    for f in sorted(int_dir.glob('*.json')):
        logger.info('processing %r', f)
        vis = collect(json.loads(f.read_text()))
        if last is not None:
            compare(last, vis, before_fdt=last_dt)
        last = vis
        last_dt = datetime.strptime(f.stem, '%Y%m%d%H%M%S')

if __name__ == '__main__':
    main()

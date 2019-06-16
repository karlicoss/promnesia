#!/usr/bin/env python3
from datetime import datetime
import argparse
from pathlib import Path
import sys
import json
import logging
from itertools import chain
from typing import Dict, List, Any, NamedTuple, Optional, Set

from hashlib import sha1

from kython.klogging import setup_logzero
from kython import kompress
from kython.canonify import canonify

# TODO include latest too?
from cconfig import ignore, filtered

def get_logger():
    return logging.getLogger('wereyouhere-db-changes')

# TODO return error depending on severity?

Url = str
Dt = str
Source = str
Context = str
Tag = str
Locator = str


# TODO reuse DbVisit? or use db?
class Visit(NamedTuple):
    url: Url
    dt: Dt
    source: Source
    context: Context
    tag: Tag
    locator: Locator


    # special id for easier excluding..
    @property
    def exid(self):
        return sha1('!'.join([self.url, self.dt, self.source, self.context, self.tag]).encode('utf8')).hexdigest()


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


def compare(before: Set[Visit], after: Set[Visit], between: str) -> List[Visit]:
    errors: List[Visit] = []

    umap: Dict[str, List[Visit]] = {
    }
    for a in after:
        xx = umap.get(a.url, [])
        xx.append(a)
        umap[a.url] = xx

    def reg_error(b):
        errors.append(b)
        logger.error('between %s missing %s', between, b)
        print('ignoreline "%s", # %s %s' % (b.exid, b.url, b.tag), file=sys.stderr)


    logger = get_logger()
    # optimisation: eliminate common

    eliminations = [
        ('identity'               , lambda x: x),
        ('without dt'             , lambda x: x._replace(source='', dt='')),
        ('without context'        , lambda x: x._replace(source='', context='', locator='')), # TODO FIXME only allow for certain tags?
        ('without dt and context' , lambda x: x._replace(source='', dt='', context='', locator='')), # ugh..
    ]
    for ename, ekey in eliminations:
        logger.info('eliminating by %s', ename)
        logger.info('before: %d, after: %d', len(before), len(after))
        before, common, after = eliminate_by(before, after, key=ekey)
        logger.info('common: %d, before: %d, after: %d', len(common), len(before), len(after))

    logger.info('removing explicitly ignored items')
    before = filtered(before, between=between, umap=umap)
    logger.info('before: %d', len(before))

    for b in before:
        reg_error(b)

    return errors


def collect(fname: str, jj):
    logger = get_logger()
    visits = set()
    for src, data in sorted(jj):
        for v in data:
            loc = v['locator']
            # TODO hmm, comparison tends to be same if we just ignore the locator..
            locs = '' # TODO FIXME '{}:{}'.format(loc['href'], loc['title'])

            tag = v['tag']
            # # TODO shit, only need to do that first time...
            # if '20190525074221' in fname:
            #     # split databases
            #     if tag.endswith('-old'):
            #         tag = tag[:-4]

            vs = Visit(
                source=src,
                # canonify once again to compare against changes in normalising as well
                url=canonify(v['norm_url']),
                tag=tag,
                dt=v['dt'],
                context=v['context'] or '<no context>', # to simplify comparisons...
                locator=locs,
            )
            # assert vs not in visits
            if vs in visits:
                # TODO FIXME multiset??
                # TODO debug level? not sure if should show them at all
                # TODO FIXME shit. ok, duplicates are coming from different takeouts apparently. enable back once I merge properly...
                # logger.warning('duplicate visit %s', vs)
                pass
            #     import ipdb; ipdb.set_trace() 
            visits.add(vs)
    return visits

def main():
    setup_logzero(get_logger(), level=logging.DEBUG)
    logger = get_logger()

    p = argparse.ArgumentParser()
    # TODO better name?
    p.add_argument('--intermediate-dir', type=Path, required=True)
    p.add_argument('--last', type=int, default=2)
    p.add_argument('--all', action='store_const', const=0, dest='last')
    p.add_argument('paths', nargs='*')
    args = p.parse_args()
    # TODO perhaps get rid of linksdb completely? The server could merge them by itself
    int_dir = args.intermediate_dir
    assert int_dir.exists()

    jsons = list(sorted(int_dir.glob('*.json*')))
    if len(args.paths) == 0:
        jsons = jsons[-args.last:]
    else:
        jsons = [Path(p) for p in args.paths]

    assert len(jsons) > 0

    all_errors = []

    last = None
    last_dts = None
    for f in jsons:
        logger.info('processing %r', f)
        name = f.name
        this_dts = name[0: name.index('.')] # can't use stem due to multiple extensions..
        with kompress.open(f) as fo:
            vis = collect(name, json.load(fo))
        if last is not None:
            between = f'{last_dts}:{this_dts}'
            errs = compare(last, vis, between=between)
            all_errors.extend(errs)
        last = vis
        last_dts = this_dts

    if len(all_errors) > 0:
        sys.exit(1)
import sys; exec("global info\ndef info(type, value, tb):\n    import ipdb, traceback; traceback.print_exception(type, value, tb); ipdb.pm()"); sys.excepthook = info # type: ignore

if __name__ == '__main__':
    main()


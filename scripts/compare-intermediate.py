#!/usr/bin/env python3
import argparse
from pathlib import Path
import json
import logging
from typing import Dict, List, Any

from kython.klogging import setup_logzero

def get_logger():
    return logging.getLogger('wereyouhere-db-changes')

int_dir = Path('intermediate')

# TODO return error depending on severity?
# TODO needs private config or something?
# TODO need to indicate timezone in serialized data?
# ah, looks like it does

Url = str
Visit = Any
Umap = Dict[Url, List[Visit]]

def ddiff(a, b):
    return list(sorted(a.difference(b))), list(sorted(a.intersection(b))), list(sorted(b.difference(a)))


# TODO ok some data providers can respect timestamps. some cant...
# TODO include latest too?
# TODO configure so some urls can be ignored. by regex?
def compare(before: Umap, after: Umap):
    logger = get_logger()
    # TODO FIXME error if duplicate provider names
    # TODO items might move between sources?
    # providers = list(sorted(x[0] for x in before))
    urls = sorted(set().union(before.keys(), after.keys())) # type: ignore

    def by_ts(xxx):
        res = {}
        for x in sorted(xxx, key=str):
            ts = x['dt']
            ll = res.get(ts, [])
            ll.append(x)
            res[ts] = ll
        return res

    errors = 0
    for u in urls:
        bb = by_ts(before.get(u, []))
        aa = by_ts(after.get(u, []))
        mb = []
        ma = []
        for ts in sorted(set().union(bb.keys(), aa.keys())): # type: ignore
            tb = bb.get(ts, [])
            ta = aa.get(ts, [])
            if tb == ta:
                # TODO FIXME actually, remove all common items
                continue 
                # so, dt is same, the only changes that are possible are tags?
                # TODO only append the differences?
            mb.extend(tb)
            ma.extend(ta)
        if len(mb) == 0:
            continue # all ok?

        errors += 1
        # import ipdb; ipdb.set_trace() 
        logger.warning('%s: before %s after %s', u, mb, ma)
        if errors > 10:
            raise RuntimeError


                # import ipdb; ipdb.set_trace()
        # TODO compute diff between these?

    # ob, common, oa = ddiff(set(before.keys()), set(after.keys()))
    # for u in ob:
    #     logger.warning('%s is only in old', u)
    # for u in oa:
    #     pass
    #     # logger.info('%s is only in new', u)
    # for u in common:
    #     bb = before[u]
    #     aa = after[u]
    #     # TODO if aa dominates bb, then just carry on?
    #     # if bb != aa:
    #     #     logger.info('%s vs %s', bb, aa)
    import ipdb; ipdb.set_trace() 

def collect(jj):
    all_visits = {}
    for _, data in sorted(jj):
        for v in data:
            u = v['url']
            vs = all_visits.get(u, None)
            if vs is None:
                vs = []
                all_visits[u] = vs
            vs.extend(v['visits'])
    return all_visits

def main():
    setup_logzero(get_logger(), level=logging.DEBUG)
    logger = get_logger()

    last = None
    for f in sorted(int_dir.glob('*.json')):
        logger.info('processing %r', f)
        vis = collect(json.loads(f.read_text()))
        if last is not None:
            compare(last, vis)
        last = vis

if __name__ == '__main__':
    main()

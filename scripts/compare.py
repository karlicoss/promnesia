#!/usr/bin/env python3

from typing import NamedTuple, List, Set, Tuple, Optional

class Visit(NamedTuple):
    when: str
    tag: str

def vdiff(a: Set, b: Set):
    if a is None:
        a = set()
    if b is None:
        b = set()
    return a.difference(b), b.difference(a)

from private import ignore_url, compatible_visits

def compare(old, new, ignore_new=False, only=Optional[Set[str]]):
    o = old
    n = new
    all_keys = set(o.keys()).union(n.keys())

    incr = []
    decr = []

    def getv(x, u):
        r = x.get(u, None)
        if r is None:
            return None
        vis = r[0]
        res = set()
        for v in vis:
            tags = set(v[1])
            tags = {t for t in tags if only is None or t in only}
            tags = {t for t in tags if not ignore_url(url=u, tag=t)}
            for t in tags:
                res.add(Visit(when=v[0], tag=t))
        return res

    import urllib
    # urllib.quote

    total = 0
    for k in all_keys:
        vo = getv(o, k)
        vn = getv(n, k)

        if vn is None:
            qk = urllib.parse.quote(k)
            # TODO encoding??
            # TODO uncomment some of old suppressions
            # print(f'attempt to fallback on {qk}')
            vn = getv(n, qk)


        onotn, nnoto = vdiff(vo, vn)
        if len(onotn) == 0 and len(nnoto) == 0:
            continue
        if len(nnoto) > 0 and len(onotn) == 0 and ignore_new:
            # print(f'ignoring new {k}') # TODO FIXME
            continue

        [tag] = list(only)
        # TODO ok, makes more sense to only use in --only mode?

        # TODO shit. ok, no surprise timestamps are different since it depends on multiple sources simultaneously..
        # TODO lesson I guess -- dump data as raw as possible so it's easy to compare it. only then use postprocessing
        # TODO yaml for python objects??
        if compatible_visits(onotn, nnoto, tag=tag, url=k):
            continue

        errs = []
        errs.append(f"ERROR: {k}")
        if len(onotn) > 0:
            errs.append(f'    old only {onotn}')
            # TODO WIP
            # supers = [u for u in n.keys() if u.startswith(k)]
            # if len(supers) > 0:
            #     errs.append(f'    BUT present in {supers}')
        if len(nnoto) > 0:
            errs.append(f'    new only {nnoto}')
        print('\n'.join(errs))
        if len(errs) > 0:
            total += 1
        # if vo != vn:
        #     print(f'ERROR: difference at {k}: {vo} vs {vn}')
            # ll = f"{v1:3d} {v2:3d} {k}"
            # if v1 < v2:
            #     incr.append(ll)
            # else:
            #     decr.append(ll)
    print(f"Total mismatches: {total}")
    # print("---------INCREASED")
    # for ll in incr:
    #     print(ll)


    # print("---------DECREASED")
    # for ll in decr:
    #     print(ll)

def load_visits(p):
    import json
    from pathlib import Path
    return json.loads(Path(p).read_text())

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('--old', required=True)
    p.add_argument('--new', required=True)
    p.add_argument('--only', action='append', help='only compare certain tags')
    p.add_argument('--ignore-new', action='store_true', help="do not report items that weren't present in old links database")
    args = p.parse_args()
    vold = load_visits(args.old)
    vnew = load_visits(args.new)
    compare(old=vold, new=vnew, ignore_new=args.ignore_new, only=None if args.only is None else set(args.only))



if __name__ == '__main__':
    main()

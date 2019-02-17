#!/usr/bin/env python3

from typing import NamedTuple, List

class Visit(NamedTuple):
    when: str
    tags: List[str]

def compare(o, n):
    all_keys = set(o.keys()).union(n.keys())

    incr = []
    decr = []

    def getv(x, u):
        r = x.get(u, None)
        if r is None:
            return None
        vis = r[0]
        res = []
        for v in vis:
            res.append(Visit(v[0], v[1]))
        return res


    for k in all_keys:
        v1 = getv(o, k)
        v2 = getv(n, k)
        if v1 != v2:
            print(f'difference at {k}: {v1} vs {v2}')
            # ll = f"{v1:3d} {v2:3d} {k}"
            # if v1 < v2:
            #     incr.append(ll)
            # else:
            #     decr.append(ll)

    print("---------INCREASED")
    for ll in incr:
        print(ll)


    print("---------DECREASED")
    for ll in decr:
        print(ll)

def load_visits(p):
    import json
    from pathlib import Path
    return json.loads(Path(p).read_text())

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument('old')
    p.add_argument('new')
    args = p.parse_args()
    vold = load_visits(args.old)
    vnew = load_visits(args.new)
    compare(vold, vnew)



if __name__ == '__main__':
    main()

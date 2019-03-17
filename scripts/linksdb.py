#!/usr/bin/env python3
from collections import OrderedDict
import json
from pathlib import Path
import sys
from typing import NamedTuple, Dict, List

Url = str
Dt = str
Source = str
Tag = str
Context = str


class Visit(NamedTuple):
    url: Url
    dt: Dt
    tag: Tag


def load(fname: Path) -> Dict[Url, List[Visit]]:
    jj = json.loads(fname.read_text())
    res: Dict[Url, List[Visit]] = OrderedDict()
    for url, vv in sorted(jj.items()):
        ures = []
        for vis in vv[0]:
            [dt, tags] = vis
            for t in tags:
                ures.append(Visit(
                    url=url,
                    dt=dt,
                    tag=t,
                ))
            res[url] = ures
    return res



def main():
    fname = sys.argv[1]
    from pprint import pprint
    pprint(load(Path(fname)))


if __name__ == '__main__':
    main()

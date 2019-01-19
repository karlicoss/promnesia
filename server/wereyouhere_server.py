#!/usr/bin/python3
import argparse
import json
import re
import os
from pathlib import Path

import hug # type: ignore
import hug.types as T # type: ignore


def log(*things):
    # TODO proper logging
    print(*things)


# TODO how to have a worker in parallel??

LINKS = Path('/L/data/wereyouhere/linksdb.json')

def get_visits_map():
    # TODO could even store in some decent format now instead of lists...
    with VISITS.open('r') as fo:
        vmap = json.load(fo)
    return vmap # TODO keep it in memory so don't have to reload every time
    # res = {}
    # for u, (vis, cont) in vmap.items():
    #     res[u] = {
    #         'visits': vis,
    #         'contexts': cont,
    #     }
    # return res


@hug.local()
@hug.post('/visits')
def visits(
        url: T.text,
):
    # TODO could also normalise here!! wohoo
    log(f"getting visits for {url}")
    vmap = get_visits_map()
    res = vmap.get(url, None)
    log(res)
    return res


def run(port: str): # , capture_path: str):
    # env = os.environ.copy()
    # # not sure if there is a simpler way to communicate with the server...
    # env[CAPTURE_PATH_VAR] = capture_path
    os.execvp(
        'hug',
        [
            'wereyouhere-server',
            '-p', port,
            '-f', __file__,
        ],
        # env,
    )

def setup_parser(p):
    p.add_argument('--port', type=str, default='13131', help='Port for communicating with extension')
    # p.add_argument('--path', type=str, default='~/capture.org', help='File to capture into')

def main():
    p = argparse.ArgumentParser('wereyouhere server', formatter_class=argparse.ArgumentDefaultsHelpFormatter)
    setup_parser(p)
    args = p.parse_args()
    run(args.port) # , args.path)

if __name__ == '__main__':
    main()

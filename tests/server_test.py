import json
from pathlib import Path
import sys
from subprocess import check_output, check_call
from textwrap import dedent
from typing import NamedTuple

import pytz

from integration_test import index_urls
from common import promnesia_bin

from promnesia.tests.server_helper import run_server as wserver


class Helper(NamedTuple):
    port: str


def post(*args):
    cmd = [
        sys.executable, '-m', 'httpie',
        # '--timeout', '10000', # useful for debugging
        '--ignore-stdin',
        'post',
        *args,
    ]
    return json.loads(check_output(cmd).decode('utf8'))


import pytest
@pytest.mark.parametrize('count',
    [1, 5, 10, 12, 25, 50, 100, 200, 400, 800, 1600]
)
def test_visited_benchmark(count: int, tmp_path) -> None:
    pytest.skip("Only works on @karlicoss computer for now")
    # TODO skip on ci
    import promnesia.server as S
    # TODO reset after?
    S.EnvConfig.set(S.ServerConfig(
        # TODO populate with test db and benchmark properly...
        db=Path('/todo'),
        timezone=pytz.utc,
    ))
    links = [f'https://reddit.com/whatever{i}.html' for i in range(count)]
    res = S.visited(links)
    assert len(res) == len(links)


# TODO right.. I guess that triggered because of reddit indexer specifically
# TODO could probably reuse parts of tests to be both integration/server and end2end when necessary?
def test_visits_hier(tmp_path: Path) -> None:
    test_url = 'https://www.reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/'
    urls = {
        test_url: 'parent url',
        'https://reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/f0vem56': 'Some context',
        'https://reddit.com/r/QuantifiedSelf/comments/d6m7bd/android_app_to_track_and_export_application_use/whatever': None, # no context so should be ignored..
    }
    indexer = index_urls(urls)
    indexer(tmp_path)
    with wserver(db=tmp_path / 'promnesia.sqlite') as helper:
        response = post(f'http://localhost:{helper.port}/visits', f'url={test_url}')
        assert {v['context'] for v in response['visits']} == {'parent url', 'Some context'}


def test_query_while_indexing(tmp_path: Path) -> None:
    cfg = tmp_path / 'config.py'
    indexing_cmd = promnesia_bin('index', '--config', cfg)

    # just trigger the database
    cfg.write_text(dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'
    SOURCES = ['promnesia.sources.demo']
    '''))
    check_call(indexing_cmd)

    cfg.write_text(dedent(f'''
    OUTPUT_DIR = r'{tmp_path}'

    from promnesia.common import Source
    from promnesia.sources import demo
    # index stupid amount of visits to increase time spent in database serialization
    SOURCES = [Source(demo.index, count=100000)]
    '''))
    with wserver(db=tmp_path / 'promnesia.sqlite') as helper:
        status = lambda: post(f'http://localhost:{helper.port}/status')
        # precondition -- db should be healthy
        r = status()
        assert 0 < r['stats']['total_visits'] < 100000, r

        # now run the indexing (asynchronously)
        #
        from subprocess import Popen
        with Popen(indexing_cmd):
            # and hammer the backend to increase likelihood of race condition
            # not ideal -- doesn't really 'guarantee' to catch races, but good enough
            for _ in range(100):
                r = status()
                assert r['stats'].get('total_visits', 0) > 0, r
        # after indexing finished, new visits should be in the db
        r = status()
        assert r['stats']['total_visits'] >= 100000, r

from datetime import datetime
from pathlib import Path
from subprocess import Popen

import pytest

from ..__main__ import do_index
from .common import promnesia_bin, write_config
from .server_helper import run_server


def test_status_error() -> None:
    """
    If DB doesn't exist, server should handle it gracefully and respond with error
    """
    with run_server(db='/does/not/exist') as server:
        response = server.post('/status')

        # TODO ugh currently returns 200? maybe should return proper error, but need to handle in extension
        # assert response.status_code == 404

        body = response.json()

        version = body['version']
        assert version is not None
        assert len(version.split('.')) >= 2  # random check..

        assert 'ERROR' in body['db']  # defensive, it doesn't exist


def test_status_ok(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, count=10)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    db_path = tmp_path / 'promnesia.sqlite'
    with run_server(db=db_path, timezone='America/New_York') as server:
        r = server.post('/status').json()
        version = r['version']
        assert version is not None
        assert len(version.split('.')) >= 2  # random check..

        assert r['db'] == str(db_path)

        assert r['stats'] == {'total_visits': 10}


def test_visits(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, base_dt='2000-01-01', delta=30 * 60)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    # force timezone here, otherwise dependeing on the test env response varies
    with run_server(db=tmp_path / 'promnesia.sqlite', timezone='America/New_York') as server:
        r = server.post('/visits', json={'url': 'whatever'}).json()
        assert r['visits'] == []

        r = server.post('/visits', json={'url': 'https://demo.com/page0.html'})
        rj = r.json()
        assert rj['normalised_url'] == 'demo.com/page0.html'
        [v] = rj['visits']
        assert v['src'] == 'demo'
        assert v['locator']['title'] == 'demo'

        assert v['dt'] == '01 Jan 2000 00:00:00 -0500'


def test_visits_hierarchy(tmp_path: Path) -> None:
    def cfg() -> None:
        from datetime import datetime

        from promnesia.common import Loc, Source, Visit
        from promnesia.sources import demo

        def indexer():
            visits = list(demo.index(count=6))
            yield Visit(
                url='https://reddit.com/post1',
                dt=datetime.fromisoformat('2023-12-04'),
                locator=Loc.make('reddit'),
            )
            yield Visit(
                url='https://reddit.com/post1/comment2',
                dt=datetime.fromisoformat('2023-12-02'),
                locator=Loc.make('reddit'),
                context='I am comment 2',
            )
            yield from visits[:3]
            yield Visit(
                url='https://reddit.com/post2',
                dt=datetime.fromisoformat('2023-12-05'),
                locator=Loc.make('reddit'),
            )
            yield from visits[3:]
            yield Visit(
                url='https://reddit.com/post1/ihavenocontext',
                dt=datetime.fromisoformat('2023-12-06'),
                locator=Loc.make('reddit'),
            )
            yield Visit(
                url='https://reddit.com/post1/comment1',
                dt=datetime.fromisoformat('2023-12-06'),
                locator=Loc.make('reddit'),
                context='I am comment 1',
            )

        SOURCES = [Source(indexer)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    # force timezone here, otherwise dependeing on the test env response varies
    with run_server(db=tmp_path / 'promnesia.sqlite', timezone='America/New_York') as server:
        r = server.post('/visits', json={'url': 'https://reddit.com/post1'}).json()
        # retuns exact match + 'child' visits that are interesting (e.g. have context)
        assert {v['original_url'] for v in r['visits']} == {
            'https://reddit.com/post1',
            'https://reddit.com/post1/comment1',
            'https://reddit.com/post1/comment2',
        }


def test_visited(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, base_dt='2000-01-01', delta=30 * 60)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    test_url = 'https://demo.com/page5.html'

    # force timezone here, otherwise dependeing on the test env response varies
    with run_server(db=tmp_path / 'promnesia.sqlite', timezone='America/New_York') as server:
        r = server.post('/visited', json={'urls': []}).json()
        assert r == []

        r = server.post('/visited', json={'urls': [test_url, 'http://badurl.org']}).json()
        [r1, r2] = r
        assert r1['original_url'] == test_url
        assert r2 is None


def test_search(tmp_path: Path) -> None:
    # TODO not sure if should index at all here or just insert DbVisits directly?
    def cfg() -> None:
        from datetime import datetime

        from promnesia.common import Loc, Source, Visit
        from promnesia.sources import demo

        def indexer():
            visits = list(demo.index(count=6))
            yield Visit(
                url='https://someone.org/something',
                dt=datetime.fromisoformat('2023-12-04T11:12:13+03:00'),
                locator=Loc.make('whatever'),
            )
            yield from visits[:3]
            yield Visit(
                url='https://wiki.termux.com/wiki/Termux-setup-storage',
                locator=Loc.make(
                    title='Reddit comment',
                    href='https://reddit.com/r/termux/comments/m4qrxt/cant_open_storageshared_in_termux/gso0kak/',
                ),
                dt=datetime.fromisoformat('2023-12-02'),
                context='perhaps it will help someone else https://wiki.termux.com/wiki/Termux-setup-storage',
            )
            yield from visits[3:]

        SOURCES = [Source(indexer)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    with run_server(db=tmp_path / 'promnesia.sqlite', timezone='America/New_York') as server:
        # FIXME 'url' is actually kinda misleading -- it can be any text
        rj = server.post('/search', json={'url': 'someone'}).json()
        # TODO maybe return in chronological order or something? not sure
        [v1, v2] = sorted(rj['visits'], key=lambda j: j['dt'])

        assert v1['context'] == 'perhaps it will help someone else https://wiki.termux.com/wiki/Termux-setup-storage'
        assert v1['dt'] == '02 Dec 2023 00:00:00 -0500'  # uses server timezone (original visit didn't have it)

        assert v2['normalised_url'] == 'someone.org/something'
        assert v2['dt'] == '04 Dec 2023 11:12:13 +0300'  # uses original visit timezone

        rj = server.post('/search', json={'url': 'comment'}).json()
        [v] = rj['visits']
        assert v['context'] == 'perhaps it will help someone else https://wiki.termux.com/wiki/Termux-setup-storage'


def test_search_around(tmp_path: Path) -> None:
    # this should return visits up to 3 hours in the past
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        # generates 60 visits within 10 mins of each other -- so spanning over 10 hours
        SOURCES = [Source(demo.index, count=60, base_dt='2000-01-01T00:00:00+03:00', delta=10 * 60)]  # noqa: F841

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    # TODO hmm. perhaps it makes more sense to run query in different process and server in main process for testing??
    with run_server(db=tmp_path / 'promnesia.sqlite') as server:
        rj = server.post(
            '/search_around',
            json={'timestamp': datetime.fromisoformat('2005-01-01T00:00:00+06:00').timestamp()},
        ).json()
        assert rj['visits'] == []

        rj = server.post(
            '/search_around',
            json={'timestamp': datetime.fromisoformat('2000-01-01T07:55:00+06:00').timestamp()},
        ).json()
        visits = rj['visits']
        assert len(visits) == 18  # 6 per hour * 3
        assert visits[0 ]['dt'] == '01 Jan 2000 02:00:00 +0300'
        assert visits[-1]['dt'] == '01 Jan 2000 04:50:00 +0300'


@pytest.mark.parametrize('mode', ['update', 'overwrite'])
def test_query_while_indexing(tmp_path: Path, mode: str) -> None:
    overwrite = mode == 'overwrite'
    moverwrite = ['--overwrite'] if overwrite else []

    def _index(run_id: str) -> Popen:
        def cfg(run_id: str) -> None:
            from promnesia.common import Source
            from promnesia.sources import demo

            SOURCES = [Source(demo.index, count=1_000, name=run_id)]  # noqa: F841

        cfg_path = tmp_path / f'config{run_id}.py'
        write_config(cfg_path, cfg, run_id=run_id)

        return Popen(promnesia_bin('index', '--config', cfg_path, *moverwrite))

    # trigger initial indexing
    with _index(run_id='0'):
        pass

    with run_server(db=tmp_path / 'promnesia.sqlite') as server:
        rj = server.post(
            '/search_around',
            json={'timestamp': datetime.fromisoformat('2005-01-01T00:00:00+06:00').timestamp()},
        ).json()
        assert rj['visits'] == []

        for run_id in range(1, 5):
            with _index(run_id=str(run_id)) as indexer:
                # hammer the backend to increase likelihood of race condition
                while indexer.poll() is None:
                    stats = server.post('/status').json()['stats']
                    total_visits = stats['total_visits']
                    if overwrite:
                        assert total_visits >= 1_000
                    else:
                        assert total_visits >= 1_000 * run_id


# TODO also could check server methods directly?
# via something like this... but not sure if really makes much difference
# import promnesia.server as S
# S.EnvConfig.set(S.ServerConfig(
#     # TODO populate with test db and benchmark properly...
#     db=Path('/todo'),
#     timezone=timezone.utc,
# ))
# links = [f'https://reddit.com/whatever{i}.html' for i in range(count)]
# res = S.visited(links)
# assert len(res) == len(links)

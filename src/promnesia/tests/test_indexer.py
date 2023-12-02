from collections import Counter
import inspect
from pathlib import Path
from subprocess import check_call, Popen
from textwrap import dedent

import pytest

from .common import promnesia_bin
from ..__main__ import do_index
from ..database.load import get_all_db_visits


def get_stats(tmp_path: Path) -> Counter:
    visits = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    return Counter(v.src for v in visits)


def write_config(path: Path, gen) -> None:
    output_dir = path.parent
    cfg_src = dedent('\n'.join(inspect.getsource(gen).splitlines()[1:])) + f"\nOUTPUT_DIR = r'{output_dir}'"
    path.write_text(cfg_src)


@pytest.mark.parametrize('mode', ['update', 'overwrite'])
def test_indexing_mode(tmp_path: Path, mode: str) -> None:
    # ugh. we modify the config very fast during tests
    # and pycache distinguishes identical filenames based on int mtime in seconds
    # so best to use different names to prevent undesired caching
    # https://github.com/python/cpython/blob/fb202af4470d6051a69bb9d2f44d7e8a1c99eb4f/Lib/importlib/_bootstrap_external.py#L714-L739
    # TODO could probably relax that if we switch from importlib config loading to exec()?

    def cfg1() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [
            Source(demo.index, count=10, base_dt='2000-01-01', delta=30, name='demo1'),
            Source(demo.index, count=20, base_dt='2001-01-01', delta=30, name='demo2'),
        ]

    cfg_path = tmp_path / 'config1.py'
    write_config(cfg_path, cfg1)
    do_index(cfg_path)

    stats = get_stats(tmp_path)
    assert stats == {'demo1': 10, 'demo2': 20}

    def cfg2() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [
            Source(demo.index, count=30, base_dt='2005-01-01', delta=30, name='demo2'),
            Source(demo.index, count=40, base_dt='2010-01-01', delta=30, name='demo3'),
        ]

    cfg_path = tmp_path / 'config2.py'
    write_config(cfg_path, cfg2)
    do_index(cfg_path, overwrite_db={'overwrite': True, 'update': False}[mode])
    # TODO use some sort of test helper?
    stats = get_stats(tmp_path)

    if mode == 'update':
        # should keep the original visits too!
        assert stats == {'demo1': 10, 'demo2': 30, 'demo3': 40}
    else:
        # should overwrite with newly indexed visits
        assert stats == {'demo2': 30, 'demo3': 40}


# TODO check both modes?
def test_concurrent_indexing(tmp_path: Path) -> None:
    def cfg_fast() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, count=10)]

    cfg_fast_path = tmp_path / 'cfg_fast.py'
    write_config(cfg_fast_path, cfg_fast)

    def cfg_slow() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, count=100_000)]

    cfg_slow_path = tmp_path / 'cfg_slow.py'
    write_config(cfg_slow_path, cfg_slow)

    # init it first, to create the database
    # TODO ideally this shouldn't be necessary but it's reasonable that people would already have the index
    # otherwise it would fail at db creation point.. which is kinda annoying to work around
    # todo in principle can work around same way as in cachew, by having a loop around PRAGMA WAL command?
    check_call(promnesia_bin('index', '--config', cfg_fast_path, '--overwrite'))

    total_runs = 0
    # run in the background
    with Popen(promnesia_bin('index', '--config', cfg_slow_path, '--overwrite')) as slow_indexer:
        while slow_indexer.poll() is None:
            # create a bunch of 'smaller' indexers running in parallel
            fasts = [
                Popen(promnesia_bin('index', '--config', cfg_fast_path, '--overwrite'))
                for _ in range(10)
            ]
            for fast in fasts:
                assert fast.wait() == 0, fast  # should succeed
                total_runs += 1
        assert slow_indexer.poll() == 0, slow_indexer

    # FIXME ok, need to uncomment this once proper concurrent indexing is supported
    # if not, slow indexer is too fast, so crank up the count in it
    # assert total_runs > 20

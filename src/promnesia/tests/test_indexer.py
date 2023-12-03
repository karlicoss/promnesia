from collections import Counter
import inspect
from pathlib import Path
from subprocess import check_call, Popen
from textwrap import dedent

from ..__main__ import do_index
from ..common import DbVisit
from ..database.load import get_all_db_visits

import pytest

from .common import get_testdata, promnesia_bin, reset_filters


def get_stats(tmp_path: Path) -> Counter:
    visits = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    return Counter(v.src for v in visits)


def write_config(path: Path, gen, **kwargs) -> None:
    output_dir = path.parent
    cfg_src = dedent('\n'.join(inspect.getsource(gen).splitlines()[1:])) + f"\nOUTPUT_DIR = r'{output_dir}'"
    for k, v in kwargs.items():
        assert k in cfg_src, k
        cfg_src = cfg_src.replace(k, repr(str(v)))  # meh
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


def test_filter(tmp_path: Path, reset_filters) -> None:
    domain_to_filter = 'some-weird-domain.xyz'
    testdata = get_testdata('custom')
    assert any(domain_to_filter in p.read_text() for p in testdata.glob('*.txt'))  # precondition

    def cfg(testdata, domain_to_filter) -> None:
        from promnesia.common import Source
        from promnesia.sources import shellcmd
        from promnesia.sources.plaintext import extract_from_path

        FILTERS = [
            domain_to_filter,
        ]

        SOURCES = [Source(shellcmd.index, extract_from_path(testdata))]

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg, testdata=testdata, domain_to_filter=domain_to_filter)
    do_index(cfg_path)

    visits = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    urls = {v.orig_url for v in visits}
    assert not any(domain_to_filter in u for u in urls), urls
    assert len(visits) == 4  # just in case


def test_weird_urls(tmp_path: Path) -> None:
    # specifically test this here (rather than in cannon)
    # to make sure it's not messed up when we insert/extract from sqlite

    def cfg(testdata: str) -> None:
        from promnesia.common import Source
        from promnesia.sources import shellcmd
        from promnesia.sources.plaintext import extract_from_path

        SOURCES = [Source(shellcmd.index, extract_from_path(testdata))]

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg, testdata=get_testdata('weird.txt'))
    do_index(cfg_path)

    [v1, v2] = get_all_db_visits(tmp_path / 'promnesia.sqlite')

    assert v1.norm_url == "urbandictionary.com/define.php?term=Belgian%20Whistle"

    assert v2.norm_url == "en.wikipedia.org/wiki/Dinic%27s_algorithm"
    assert v2.locator.title.endswith('weird.txt:2')
    assert v2.context == 'right, so https://en.wikipedia.org/wiki/Dinic%27s_algorithm can be used for max flow'


def test_errors_during_indexing(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        def indexer1():
            visits = list(demo.index(count=10))
            yield from visits[:5]
            yield RuntimeError("some error during visits extraction")
            yield from visits[5:]

        def indexer2():
            raise RuntimeError("in this case indexer itself crashed")

        SOURCES = [Source(indexer1), Source(indexer2)]

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    stats = get_stats(tmp_path)
    assert stats == {
        'error': 2,
        'config': 10,
    }


def test_hook(tmp_path: Path) -> None:
    def cfg() -> None:
        from promnesia.common import Source
        from promnesia.sources import demo

        SOURCES = [Source(demo.index, count=7, name='somename')]

        from typing import cast, Iterator
        from promnesia.common import DbVisit, Loc, Res
        from promnesia.sources import demo

        def HOOK(visit: Res[DbVisit]) -> Iterator[Res[DbVisit]]:
            visit = cast(DbVisit, visit)

            # NOTE: might be a good idea to check that the visit is an exception first and yield it intact?
            nurl = visit.norm_url
            if 'page1' in nurl:
                yield visit._replace(norm_url='patched.com')
            elif 'page2' in nurl:
                raise Exception('boom')  # deliberately crash
            elif 'page3' in nurl:
                # just don't yield anything! it will be omitted
                pass
            elif 'page4' in nurl:
                # can emit multiple!
                yield visit
                yield visit
            elif 'page6' in nurl:
                # patch locator
                yield visit._replace(locator=Loc.make(title='some custom timte', href='/can/replace/original/path'))
            else:
                yield visit

    cfg_path = tmp_path / 'config.py'
    write_config(cfg_path, cfg)
    do_index(cfg_path)

    [p0, p1, e2, p41, p42, p5, p6] = get_all_db_visits(tmp_path / 'promnesia.sqlite')
    assert p0.norm_url == 'demo.com/page0.html'
    assert p1.norm_url == 'patched.com'
    assert e2.norm_url == '<error>'
    assert p41 == p42
    assert isinstance(p6, DbVisit)
    assert p6.locator is not None

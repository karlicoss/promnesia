#!/usr/bin/env python3
from contextlib import contextmanager
from datetime import datetime, date
from os.path import join, getsize
from pathlib import Path
from tempfile import TemporaryDirectory
import pytz
from shutil import copytree
import os
from os import mkdir
from os.path import lexists
from typing import Union, List

import pytest # type: ignore
from pytest import mark # type: ignore


from common import tdata, reset_hpi_modules
from config_tests import with_config

from promnesia.common import Visit, Indexer, Loc, Res, DbVisit, _is_windows

# TODO need to expire dbcache in tests..

skip = mark.skip


def W(*args, **kwargs):
    if 'src' not in kwargs:
        kwargs['src'] = 'whatever'
    return Indexer(*args, **kwargs)


def as_visits(*args, **kwargs) -> List[Res[DbVisit]]:
    from promnesia.extract import extract_visits
    kwargs['src'] = 'whatever'
    return list(extract_visits(*args, **kwargs))


def as_ok_visits(*args, **kwargs) -> List[DbVisit]:
    r: List[DbVisit] = []
    for v in as_visits(*args, **kwargs):
        if isinstance(v, Exception):
            raise v
        r.append(v)
    return r


from contextlib import contextmanager
@contextmanager
def extra_path(p: Path):
    import sys
    try:
        sys.path.append(str(p))
        yield
    finally:
        sys.path.pop()

def import_file(p: Union[str, Path], name=None):
    p = Path(p)
    if name is None:
        name = p.stem
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, p); assert spec is not None
    foo = importlib.util.module_from_spec(spec)
    with extra_path(p.parent):
        spec.loader.exec_module(foo) # type: ignore
    return foo


# TODO eh. need to separate stuff for history backups out...
backup_db = import_file('scripts/browser_history.py')

def assert_got_tzinfo(visits):
    for v in visits:
        assert v.dt.tzinfo is not None


# TODO I guess global get_config methods is ok? command line can populate it, also easy to hack in code?
# TODO cache should be in the configuration I suppose?

@pytest.fixture
def adhoc_config(tmp_path: Path):
    cdir = tmp_path / 'cache'
    cdir.mkdir()

    from promnesia import config

    try:
        config.instance = config.Config(
            OUTPUT_DIR=tmp_path,
            CACHE_DIR=cdir,
        )
        yield
    finally:
        config.reset()


def test_with_error() -> None:
    class ExtractionError(Exception):
        pass
    def err_ex():
        for i in range(3):
            if i == 1:
                yield ExtractionError()
            else:
                yield Visit(
                    url=f'http://test{i}',
                    dt=datetime.utcfromtimestamp(0),
                    locator=Loc.make('whatever'),
                )
    [v1, e, v2] = as_visits(lambda: err_ex())
    assert isinstance(v1, DbVisit)
    assert isinstance(e, Exception)
    assert isinstance(v2, DbVisit)


# todo testing this logic probably belongs to hpi or google_takeout_export, but whatever
def test_takeout_directory(adhoc_config, tmp_path: Path) -> None:
    reset_hpi_modules()
    from my.cfg import config
    class user_config:
        takeout_path = tdata('takeout')
    config.google = user_config # type: ignore

    # TODO ugh, the disabled_cachew thing isn't very nice
    from my.core.cachew import disabled_cachew
    with disabled_cachew():
        import promnesia.sources.takeout as tex
        visits = as_ok_visits(W(tex.index))
    assert len(visits) == 3

    assert_got_tzinfo(visits)


def test_takeout_zip(adhoc_config) -> None:
    reset_hpi_modules()
    from my.cfg import config
    class user_config:
        takeout_path = tdata('takeout-20150518T000000Z.zip')
    config.google = user_config # type: ignore

    from my.core.cachew import disabled_cachew
    with disabled_cachew():
        import promnesia.sources.takeout as tex
        visits = as_ok_visits(tex.index)
    assert len(visits) == 3
    [vis] = [v for v in visits if v.norm_url == 'takeout.google.com/settings/takeout']

    edt = datetime(
        year=2018,
        month=9,
        day=18,
        hour=5,
        minute=48,
        second=23,
        tzinfo=pytz.utc,
    )
    assert vis.dt == edt

    assert_got_tzinfo(visits)


@skip("TODO not sure how to trigger firefox on CI...")
def test_backup_firefox(tmp_path):
    tdir = Path(tmp_path)
    path = backup_db.backup_history('firefox', to=tdir, profile='*release*')
    # shouldn't fail at least

        # [hist] = list(chrome_gen.iter_chrome_histories(path, 'sqlite'))
        # assert len(hist) > 10 # kinda random sanity check

        # render([hist], join(tdir, 'res.json'))

        # assert_got_tzinfo(hist)


def test_plaintext_path_extractor() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = as_ok_visits(W(custom_gen.index,
        extract_from_path(tdata('custom')),
    ))
    assert {
        v.orig_url for v in visits
    } == {
        'http://google.com',
        'http://google.com/',
        'http://some-weird-domain.xyz/whatever',
        'https://google.com',
        'http://what.about.this.link',
    }

    [wa] = [v for v in visits if v.orig_url == 'http://what.about.this.link']
    f2 = Path(tdata('custom')) / 'file2.txt'
    assert wa.locator.href == f'editor://{f2}:3' # occurs line 3

# TODO perhaps it belongs to canonify?
def test_normalise() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = as_ok_visits(W(custom_gen.index,
        extract_from_path(tdata('normalise')),
    ))
    assert len(visits) == 7
    assert {
        v.norm_url for v in visits
    } == {
        'hi.com',
        'reddit.com/post',
        'argos.co.uk/webapp/wcs/stores/servlet/OrderItemDisplay',
        'youtube.com/watch?v=XXlZfc1TrD0',
        'youtube.com/watch?v=XXlZfc1Tr11',
    }


def test_normalise_weird() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = as_ok_visits(W(
        custom_gen.index,
        extract_from_path(tdata('weird.txt')),
    ))
    [v1, v2] = visits

    # TODO assert there are no spaces in the database?
    assert "urbandictionary.com/define.php?term=Belgian%20Whistle" == v1.norm_url

    assert "en.wikipedia.org/wiki/Dinic%27s_algorithm"             == v2.norm_url
    assert v2.locator.title.endswith('weird.txt:2')
    assert v2.context == 'right, so https://en.wikipedia.org/wiki/Dinic%27s_algorithm can be used for max flow'


def test_filter() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    # ugh... such a mess
    @contextmanager
    def reset_filters():
        try:
            E.filters.cache_clear()
            yield
        finally:
            E.filters.cache_clear()

    import promnesia.extract as E
    with reset_filters(), with_config('''
FILTERS = [
    "some-weird-domain.xyz"
]
'''):
        visits = as_visits(W(
            custom_gen.index,
            extract_from_path(tdata('custom')),
        ))
        assert len(visits) == 4


@pytest.mark.skipif(_is_windows, reason="no grep on windows")
def test_custom() -> None:
    import promnesia.sources.shellcmd as custom_gen

    visits = as_visits(W(
        custom_gen.index,
        # meh. maybe should deprecate plain string here...
        """grep -Eo -r --no-filename (http|https)://\S+ """ + tdata('custom'),
    ))
    # TODO I guess filtering of equivalent urls should rather be tested on something having context (e.g. org mode)
    assert len(visits) == 5


def test_hook() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.__main__ import iter_all_visits
    with with_config('''
from promnesia.common import Source
from promnesia.sources import demo

SOURCES = [
    Source(demo.index, count=7, name='somename'),
]

from typing import Iterable
from promnesia.common import DbVisit, Loc, Res

def HOOK(visit: Res[DbVisit]) -> Iterable[Res[DbVisit]]:
    # NOTE: might be a good idea to check that the visit is an exception first and yield it intact?
    nurl = visit.norm_url
    if 'page1' in nurl:
        yield visit._replace(norm_url='patched.com')
    elif 'page2' in nurl:
        None.boom # deliberately crash
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
'''):
        # TODO hmm might be nice to allow in-pace modifications...
        [p0, p1, e2, p41, p42, p5, p6] = list(iter_all_visits())
        assert isinstance(p0, DbVisit)
        assert p0.norm_url == 'demo.com/page0.html'
        assert isinstance(p1, DbVisit)
        assert p1.norm_url == 'patched.com'
        assert isinstance(e2, Exception)
        assert p41 == p42
        assert isinstance(p6, DbVisit)
        assert p6.locator is not None


TESTDATA_CHROME_HISTORY = "/L/data/promnesia/testdata/chrome-history"

def get_chrome_history_backup(td: str):
    copytree(TESTDATA_CHROME_HISTORY, join(td, 'backup'))

@skip("TODO move this to populate script instead")
def test_merge():
    merge = backup_db.merge

    # TODO third is implicit... use merging function
    with TemporaryDirectory() as tdir:
        get_chrome_history_backup(tdir)
        first  = join(tdir, "backup/20180415/History")
        second = join(tdir, "backup/20180417/History")

        mdir = join(tdir, 'merged')
        mkdir(mdir)
        merged_path = join(mdir, 'merged.sql')


        def merged_size() -> int:
            return getsize(merged_path)

        merge(merged_path, first)
        fsize = merged_size()

        merge(merged_path, first)
        fsize_2 = merged_size()

        assert fsize == fsize_2

        merge(merged_path, second)
        ssize = merged_size()

        assert ssize > fsize

        merge(merged_path, second)
        ssize_2 = merged_size()

        assert ssize_2 == ssize


def _test_merge_all_from(tdir):
    merge_all_from = backup_db.merge_all_from # type: ignore
    mdir = join(tdir, 'merged')
    mkdir(mdir)
    mfile = join(mdir, 'merged.sql')

    get_chrome_history_backup(tdir)

    merge_all_from(mfile, join(tdir, 'backup'), None)

    first  = join(tdir, "backup/20180415/History")
    second = join(tdir, "backup/20180417/History")

    # should be removed
    assert not lexists(first)
    assert not lexists(second)

    import promnesia.sources.chrome as chrome_ex # type: ignore

    hist = history(W(chrome_ex.extract, mfile)) # type: ignore
    assert len(hist) > 0

    older = hist['github.com/orgzly/orgzly-android/issues']
    assert any(v.dt.date() < date(year=2018, month=1, day=17) for v in older)
    # in particular, "2018-01-16 19:56:56"

    newer = hist['en.wikipedia.org/wiki/Notice_and_take_down']
    assert any(v.dt.date() >= date(year=2018, month=4, day=16) for v in newer)

    # from implicit db
    newest = hist['feedly.com/i/discover']
    assert any(v.dt.date() >= date(year=2018, month=9, day=27) for v in newest)

@skip("TODO move this to populate script")
def test_merge_all_from(tmp_path):
    tdir = Path(tmp_path)
    _test_merge_all_from(tdir)
    # TODO and also some other unique thing..

if __name__ == '__main__':
    pytest.main([__file__])

# TODO once I integrate test for db population, test chrome/firefox extractors

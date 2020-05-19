#!/usr/bin/env python3
from datetime import datetime, date
from os.path import join, getsize
from pathlib import Path
from tempfile import TemporaryDirectory
import pytz
from shutil import copytree
import os
from os import mkdir
from os.path import lexists
from typing import Union

import pytest # type: ignore
from pytest import mark # type: ignore


from common import skip_if_ci, tdata

from promnesia.common import History, Visit
from promnesia.common import Indexer

# TODO need to expire dbcache in tests..

skip = mark.skip


def W(*args, **kwargs):
    if 'src' not in kwargs:
        kwargs['src'] = 'whatever'
    return Indexer(*args, **kwargs)

def history(*args, **kwargs):
    from promnesia.common import previsits_to_history
    return previsits_to_history(*args, **kwargs, src='whatever')[0] # TODO meh


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
    spec = importlib.util.spec_from_file_location(name, p) # type: ignore
    foo = importlib.util.module_from_spec(spec)
    with extra_path(p.parent):
        spec.loader.exec_module(foo) # type: ignore
    return foo


# TODO eh. need to separate stuff for history backups out...
backup_db = import_file('scripts/browser_history.py')
populate_db = import_file('scripts/populate-browser-history.py')

def assert_got_tzinfo(visits):
    for v in visits:
        assert v.dt.tzinfo is not None


# TODO I guess global get_config methods is ok? command line can populate it, also easy to hack in code?
# TODO cache should be in the configuration I suppose?

@pytest.fixture
def adhoc_config(tmp_path):
    tdir = Path(tmp_path)
    cdir = tdir / 'cache'
    cdir.mkdir()

    from promnesia import config

    try:
        config.instance = config.Config(
            INDEXERS=[],
            OUTPUT_DIR=tdir,
            CACHE_DIR=cdir,
        )
        yield
    finally:
        config.reset()


@pytest.mark.skip(reason='TODO support unpacked directories in HPI')
def test_takeout_directory(adhoc_config, tmp_path):
    from my.cfg import config
    class user_config:
        takeout_path = tdata('takeout')
    config.google = user_config
    import promnesia.sources.takeout as tex

    visits = history(W(tex.index))
    assert len(visits) > 0 # kinda arbitrary?

    assert_got_tzinfo(visits)



def test_with_error():
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
                    locator=None,
                )
    hist = history(lambda: err_ex())
    assert len(hist) == 2


def test_takeout_new_zip(adhoc_config):
    from my.cfg import config
    class user_config:
        takeout_path = tdata('takeout-20150518T000000Z.zip')
    config.google = user_config

    import promnesia.sources.takeout as tex
    visits = history(tex.index)
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


# TODO run condition?? and flag to force all
@skip_if_ci("TODO try triggering firefox on CI? not sure if that's possible...")
def test_chrome(tmp_path):
    from promnesia.sources.browser import chrome
    tdir = Path(tmp_path)

    path = tdir / 'history'
    populate_db.merge_from('chrome', from_=None, to=path)
    # TODO hmm, it actually should be from merged db....

    hist = history(W(chrome, path))
    assert len(hist) > 10 # kinda random sanity check

    assert_got_tzinfo(hist)


@skip_if_ci("TODO try triggering firefox on CI? not sure if that's possible...")
def test_firefox(tmp_path):
    tdir = Path(tmp_path)
    path = backup_db.backup_history('firefox', to=tdir, profile='*release*')
    # shouldn't fail at least

        # [hist] = list(chrome_gen.iter_chrome_histories(path, 'sqlite'))
        # assert len(hist) > 10 # kinda random sanity check

        # render([hist], join(tdir, 'res.json'))

        # assert_got_tzinfo(hist)


def test_plaintext_path_extractor():
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = history(W(custom_gen.index,
        extract_from_path(tdata('custom')),
    ))
    assert {
        v.orig_url for v in visits
    } == {
        'http://google.com',
        'http://google.com/',
        'http://some-weird-domain/whatever',
        'https://google.com',
        'http://what.about.this.link',
    }

# TODO perhaps it belongs to canonify?
def test_normalise():
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = history(W(custom_gen.index,
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


def test_normalise_weird():
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = history(W(
        custom_gen.index,
        extract_from_path(tdata('weird.txt')),
    ))
    norms = {v.norm_url for v in visits}

    # TODO assert there are no spaces in the database?
    assert "urbandictionary.com/define.php?term=Belgian%20Whistle" in norms
    assert "en.wikipedia.org/wiki/Dinic%27s_algorithm" in norms


@skip("use a different way to specify filter other than class variable..")
def test_filter():
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    History.add_filter(r'some-weird-domain')
    hist = custom_gen.get_custom_history(
        extract_from_path(tdata('custom')),
    )
    assert len(hist) == 4 # chrome-error got filtered out

def test_custom():
    import promnesia.sources.shellcmd as custom_gen

    hist = history(W(
        custom_gen.index,
        """grep -Eo -r --no-filename '(http|https)://\S+' """ + tdata('custom'),
    ))
    # TODO I guess filtering of equivalent urls should rather be tested on something having context (e.g. org mode)
    assert len(hist) == 5



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

    import promnesia.sources.chrome as chrome_ex

    hist = history(W(chrome_ex.extract, mfile))
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

# TODO mark tests with @skip_if_ci

# TODO once I integrate test for db population, test chrome/firefox extractors

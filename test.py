#!/usr/bin/env python3
from datetime import datetime, date
from os.path import join, getsize
from pathlib import Path
from tempfile import TemporaryDirectory
import pytz
from shutil import copytree
from os import mkdir
from os.path import lexists

import pytest # type: ignore
from pytest import mark # type: ignore
skip = mark.skip

from wereyouhere.dump import dump_histories
from wereyouhere.common import History, PreVisit
from wereyouhere.generator.smart import Wrapper

def W(*args, **kwargs):
    if 'tag' not in kwargs:
        kwargs['tag'] = 'whatever'
    return Wrapper(*args, **kwargs)

def history(*args, **kwargs):
    from wereyouhere.generator.smart import previsits_to_history
    return previsits_to_history(*args, **kwargs)[0] # TODO meh

import imp
backup_db = imp.load_source('hdb', 'scripts/backup-history-db.py')

def assert_got_tzinfo(h: History):
    for v in h.visits:
        assert v.dt.tzinfo is not None


def dump(hist: History):
    # TODO cfg??
    with TemporaryDirectory() as tdir:
        class Cfg:
            OUTPUT_DIR = tdir
        dump_histories([('test', hist)], config=Cfg()) # type: ignore


def test_takeout():
    test_takeout_path = "testdata/takeout"
    import wereyouhere.extractors.takeout as tex
    hist = history(W(tex.extract, test_takeout_path))
    assert len(hist) > 0 # kinda arbitrary?

    assert_got_tzinfo(hist)

    dump(hist)

def test_with_error():
    class ExtractionError(Exception):
        pass
    def err_ex():
        for i in range(3):
            if i == 1:
                yield ExtractionError()
            else:
                yield PreVisit(
                    url=f'http://test{i}',
                    dt=datetime.utcfromtimestamp(0),
                    locator=None,
                )
    hist = history(lambda: err_ex())
    assert len(hist) == 2

def test_takeout_new_zip():
    test_takeout_path = "testdata/takeout-20150518T000000Z.zip"
    import wereyouhere.extractors.takeout as tex
    hist = history(lambda: tex.extract(test_takeout_path, tag='whatevs'))
    assert len(hist) == 3
    [vis] = hist['takeout.google.com/settings/takeout']

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

    assert_got_tzinfo(hist)


# TODO run condition?? and flag to force all

def test_chrome(tmp_path):
    import wereyouhere.extractors.chrome as chrome_ex
    tdir = Path(tmp_path)

    path = backup_db.backup_to(tdir, 'chrome')

    hist = history(W(chrome_ex.extract, path))
    assert len(hist) > 10 # kinda random sanity check

    dump(hist)

    assert_got_tzinfo(hist)

def test_firefox(tmp_path):
    tdir = Path(tmp_path)
    path = backup_db.backup_to(tdir, 'firefox')
    # shouldn't fail at least

        # [hist] = list(chrome_gen.iter_chrome_histories(path, 'sqlite'))
        # assert len(hist) > 10 # kinda random sanity check

        # render([hist], join(tdir, 'res.json'))

        # assert_got_tzinfo(hist)


def test_plaintext_path_extractor():
    import wereyouhere.extractors.custom as custom_gen
    from wereyouhere.generator.plaintext import extract_from_path

    hist = history(W(custom_gen.extract,
        extract_from_path('testdata/custom'),
    ))
    assert len(hist) == 3

def test_normalise():
    import wereyouhere.extractors.custom as custom_gen
    from wereyouhere.generator.plaintext import extract_from_path

    hist = history(W(custom_gen.extract,
        extract_from_path('testdata/normalise'),
    ))
    assert len(hist) == 5


def test_normalise_weird():
    import wereyouhere.extractors.custom as custom_gen
    from wereyouhere.generator.plaintext import extract_from_path

    hist = history(W(custom_gen.extract,
        extract_from_path('testdata/weird.txt'),
    ))
    assert "urbandictionary.com/define.php?term=Belgian Whistle" in hist
    assert "en.wikipedia.org/wiki/Dinic's_algorithm" in hist


@skip("use a different way to specify filter other than class variable..")
def test_filter():
    import wereyouhere.generator.custom as custom_gen
    from wereyouhere.generator.plaintext import extract_from_path

    History.add_filter(r'some-weird-domain')
    hist = custom_gen.get_custom_history(
        extract_from_path('testdata/custom'),
    )
    assert len(hist) == 4 # chrome-error got filtered out

def test_custom():
    import wereyouhere.extractors.custom as custom_gen

    hist = history(W(custom_gen.extract,
        """grep -Eo -r --no-filename '(http|https)://\S+' testdata/custom""",
    ))
    assert len(hist) == 3 # https and http are same; also trailing slash and no trailing slash
    dump(hist)



TESTDATA_CHROME_HISTORY = "/L/data/wereyouhere/testdata/chrome-history"

def get_chrome_history_backup(td: str):
    copytree(TESTDATA_CHROME_HISTORY, join(td, 'backup'))

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

merge_all_from = backup_db.merge_all_from # type: ignore


def _test_merge_all_from(tdir):
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

    import wereyouhere.extractors.chrome as chrome_ex

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

def test_merge_all_from(tmp_path):
    tdir = Path(tmp_path)
    _test_merge_all_from(tdir)
    # TODO and also some other unique thing..

if __name__ == '__main__':
    pytest.main([__file__])

# TODO mark tests with @skip_if_ci

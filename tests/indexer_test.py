from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
import pytz
from typing import Union, List

import pytest

from promnesia.common import Visit, Source, Loc, Res, DbVisit, _is_windows
from promnesia.extract import extract_visits

from common import tdata, reset_hpi_modules
from config_tests import with_config


# TODO need to expire dbcache in tests..

skip = pytest.mark.skip


def W(*args, **kwargs) -> Source:
    if 'src' not in kwargs:
        kwargs['src'] = 'whatever'
    return Source(*args, **kwargs)


def as_visits(source: Source) -> List[Res[DbVisit]]:
    return list(extract_visits(source=source, src='whatever'))


def as_ok_visits(source: Source) -> List[DbVisit]:
    r: List[DbVisit] = []
    for v in as_visits(source=source):
        if isinstance(v, Exception):
            raise v
        r.append(v)
    return r


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


def assert_got_tzinfo(visits) -> None:
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
    [v1, e, v2] = as_visits(W(lambda: err_ex()))
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
        visits = as_ok_visits(W(tex.index))
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


def test_plaintext_path_extractor() -> None:
    import promnesia.sources.shellcmd as custom_gen
    from promnesia.sources.plaintext import extract_from_path

    visits = as_ok_visits(W(
        custom_gen.index,
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

    visits = as_ok_visits(W(
        custom_gen.index,
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
        r"""grep -Eo -r --no-filename (http|https)://\S+ """ + tdata('custom'),
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

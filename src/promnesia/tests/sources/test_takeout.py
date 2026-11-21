import sys
from datetime import UTC, datetime
from traceback import format_exception

import pytest
from my.core.cfg import tmp_config

from ...common import Source
from ...extract import extract_visits
from ...sources import takeout
from ..common import get_testdata, unwrap


@pytest.fixture(autouse=True)
def no_legacy_takeout(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ('my.core.kompress', 'my.google.takeout.paths', 'my.google.takeout.html'):
        monkeypatch.setitem(sys.modules, name, None)


# TODO apply in conftest so it's used in all tests?
@pytest.fixture
def no_cachew():
    from my.core.cachew import disabled_cachew

    with disabled_cachew():
        yield


# todo testing this logic probably belongs to hpi or google_takeout_export, but whatever
def test_takeout_directory(no_cachew) -> None:
    class config:
        class google:
            takeout_path = get_testdata('takeout')

    with tmp_config(modules=r'my\.google\.takeout\.parser', config=config):
        visits = list(extract_visits(Source(takeout.index), src='takeout'))

    assert len(visits) == 3
    assert all(unwrap(v).dt.tzinfo is not None for v in visits)


def test_takeout_zip(no_cachew) -> None:
    class config:
        class google:
            takeout_path = get_testdata('takeout-20150518T000000Z.zip')

    with tmp_config(modules=r'my\.google\.takeout\.parser', config=config):
        visits = list(extract_visits(Source(takeout.index), src='takeout'))

    assert len(visits) == 3
    assert all(unwrap(v).dt.tzinfo is not None for v in visits)

    [vis] = [v for v in visits if unwrap(v).norm_url == 'takeout.google.com/settings/takeout']

    edt = datetime(
        year=2018,
        month=9,
        day=18,
        hour=5,
        minute=48,
        second=23,
        tzinfo=UTC,
    )
    assert unwrap(vis).dt == edt


@pytest.mark.parametrize('missing_module', ['google_takeout_parser.models', 'my.google.takeout.parser'])
def test_takeout_missing_parser(monkeypatch: pytest.MonkeyPatch, missing_module: str) -> None:
    monkeypatch.setitem(sys.modules, missing_module, None)

    [error] = extract_visits(Source(takeout.index), src='takeout')

    assert isinstance(error, ModuleNotFoundError), error
    assert error.name == missing_module
    rendered = ''.join(format_exception(error))
    assert 'ModuleNotFoundError' in rendered
    assert 'hpi module install my.google.takeout.parser' in rendered
    assert 'google.takeout_path' in rendered

from datetime import datetime, timezone

import pytest
from my.core.cfg import tmp_config

from ...common import Source
from ...extract import extract_visits
from ...sources import takeout
from ..common import get_testdata, unwrap


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

    with tmp_config(modules='my.google.takeout.*', config=config):
        visits = list(extract_visits(Source(takeout.index), src='takeout'))

    assert len(visits) == 3
    assert all(unwrap(v).dt.tzinfo is not None for v in visits)


def test_takeout_zip(no_cachew) -> None:
    class config:
        class google:
            takeout_path = get_testdata('takeout-20150518T000000Z.zip')

    with tmp_config(modules='my.google.takeout.*', config=config):
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
        tzinfo=timezone.utc,
    )
    assert unwrap(vis).dt == edt

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Iterable


from hypothesis import settings, given
from hypothesis.strategies import from_type
# NOTE: pytest ... -s --hypothesis-verbosity=debug is useful for seeing what hypothesis is doing
import pytest
import pytz


from ..common import DbVisit, Loc, Res
from ..dump import visits_to_sqlite
from ..sqlite import sqlite_connection

from .common import gc_control, running_on_ci


HSETTINGS: dict[str, Any] = dict(
    derandomize=True,
)


def make_visits(count: int) -> Iterable[Res[DbVisit]]:
    assert count == 0
    yield from []


def test_no_visits(tmp_path: Path) -> None:
    visits: list[DbVisit] = []

    db = tmp_path / 'db.sqlite'
    errors = visits_to_sqlite(
        vit=visits,
        overwrite_db=True,
        _db_path=db,
    )
    assert db.exists()
    [err] = [errors]
    assert 'No visits were indexed' in str(err)


def test_one_visit(tmp_path: Path) -> None:
    dt = datetime.fromisoformat('2023-11-14T23:11:01')
    dt = pytz.timezone('Europe/Warsaw').localize(dt)
    visit = DbVisit(
        norm_url='google.com',
        orig_url='https://google.com',
        dt=dt,
        locator=Loc.make(title='title', href='https://whatever.com'),
        duration=123,
        src='whatever',
    )

    visits = [visit]

    db = tmp_path / 'db.sqlite'
    errors = visits_to_sqlite(
        vit=visits,
        overwrite_db=True,
        _db_path=db,
    )
    assert len(errors) == 0
    assert db.exists()

    with sqlite_connection(db, row_factory='dict') as conn:
        [sqlite_visit] = conn.execute('SELECT * FROM visits')

    assert sqlite_visit == {
        'context': None,
        # NOTE: at the moment date is dumped like this because of cachew NTBinder
        # however it's not really necessary for promnesia (and possibly results in a bit of performance hit)
        # I think we could just convert to a format sqlite supports, just need to make it backwards compatible
        'dt': '2023-11-14T23:11:01+01:00 Europe/Warsaw',
        'duration': 123,
        'locator_href': 'https://whatever.com',
        'locator_title': 'title',
        'norm_url': 'google.com',
        'orig_url': 'https://google.com',
        'src': 'whatever',
    }


def _test_random_visit_aux(visit: DbVisit, tmp_path: Path) -> None:
    db = tmp_path / 'db.sqlite'
    errors = visits_to_sqlite(
        vit=[visit],
        overwrite_db=True,
        _db_path=db,
    )
    assert db.exists()
    assert len(errors) == 0, errors
    # TODO query the db?


@given(
    visit=from_type(DbVisit).filter(
        # if duration is too big it fails to insert in sqlite
        lambda v: (v.duration is None or 0 <= v.duration <= 10**5)
    )
)
@settings(**HSETTINGS, max_examples=100)
def test_random_visit(visit: DbVisit) -> None:
    with TemporaryDirectory() as tdir:
        tmp_path = Path(tdir)
        _test_random_visit_aux(visit=visit, tmp_path=tmp_path)


@pytest.mark.parametrize('count', [99, 100_000])
@pytest.mark.parametrize('gc_on', [True, False], ids=['gc_on', 'gc_off'])
def test_benchmark_visits_dumping(count: int, gc_control, tmp_path: Path) -> None:
    if count > 99 and running_on_ci:
        pytest.skip("test would be too slow on CI, only meant to run manually")

    dt_naive = datetime.fromisoformat('2023-11-14T23:11:01')
    dt_aware = pytz.timezone('America/New_York').localize(dt_naive)
    visits = (
        DbVisit(
            norm_url=f'google.com/{i}',
            orig_url=f'https://google.com/{i}',
            dt=(dt_naive if i % 2 == 0 else dt_aware) + timedelta(seconds=i),
            locator=Loc.make(title=f'title{i}', href=f'https://whatever.com/{i}'),
            duration=i,
            src='whatever',
        )
        for i in range(count)
    )

    db = tmp_path / 'db.sqlite'
    errors = visits_to_sqlite(  # TODO maybe this method should return db stats? would make testing easier
        vit=visits,
        overwrite_db=True,
        _db_path=db,
    )
    assert db.exists()
    assert len(errors) == 0, errors

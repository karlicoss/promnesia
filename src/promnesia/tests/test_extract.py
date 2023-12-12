from datetime import datetime

from ..common import Visit, DbVisit, Loc, Source
from ..extract import extract_visits

from .common import get_testdata, unwrap, running_on_ci, gc_control

from more_itertools import ilen
import pytest


def test_with_error() -> None:
    class ExtractionError(Exception):
        pass

    def indexer():
        yield Visit(url='http://test1', dt=datetime.utcfromtimestamp(0), locator=Loc.make('whatever'))
        yield ExtractionError()
        yield Visit(url='http://test2', dt=datetime.utcfromtimestamp(0), locator=Loc.make('whatever'))

    [v1, e, v2] = extract_visits(source=Source(indexer), src='whatever')
    assert isinstance(v1, DbVisit)
    assert isinstance(e, Exception)
    assert isinstance(v2, DbVisit)


def test_urls_are_normalised() -> None:
    # generally this stuff is covered by cannon tests, but good to check it's actually inserted in the db
    # TODO maybe this should be a separate test which takes DbVisit.make separately?
    # especially to decouple from shellcmd source
    from ..sources import shellcmd
    from ..sources.plaintext import extract_from_path

    visits = list(extract_visits(
        source=Source(shellcmd.index, extract_from_path(get_testdata('normalise'))),
        src='whatever',
    ))
    assert len(visits) == 7

    assert {unwrap(v).norm_url for v in visits} == {
        'hi.com',
        'reddit.com/post',
        'argos.co.uk/webapp/wcs/stores/servlet/OrderItemDisplay',
        'youtube.com/watch?v=XXlZfc1TrD0',
        'youtube.com/watch?v=XXlZfc1Tr11',
    }


@pytest.mark.parametrize('count', [99, 100_000, 1_000_000])
@pytest.mark.parametrize('gc_on', [True, False], ids=['gc_on', 'gc_off'])
def test_benchmark(count: int, gc_control) -> None:
    # NOTE: at the moment most time is spent canonifying urls, so not much point optimizing this in isolation
    # TODO maybe could specify custom cannonifying strategy that doesn't do anything to isolate benchmark
    if count > 99 and running_on_ci:
        pytest.skip("test would be too slow on CI, only meant to run manually")

    from ..sources import demo
    source = Source(demo.index, count=count)

    total = ilen(extract_visits(source=source, src='whatever'))
    assert total == count  # sanity check

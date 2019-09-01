import pytz
from pathlib import Path

# TODO FIXME need to update it
DB_PATH = '/L/data/promnesia/visits.sqlite'

FALLBACK_TIMEZONE = pytz.timezone('Europe/London')

FILTERS = [] # type: ignore


from promnesia.common import Indexer as I
from promnesia.indexers.plaintext import extract_from_path
import promnesia.indexers.custom as custom # type: ignore
import promnesia.indexers.takeout as takeout # type: ignore

class Indexers:
    TAKEOUT = I(
        takeout.extract,
        # TODO relative paths are not great..
        'testdata/takeout-20150518T000000Z.zip',
        src='takeout',
    )

    PLAIN = I(
        custom.extract,
        extract_from_path('testdata/custom'),
        src='test',
    )


INDEXERS = [
    Indexers.PLAIN,
    Indexers.TAKEOUT,
]

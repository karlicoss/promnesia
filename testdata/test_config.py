import pytz
from pathlib import Path

# TODO FIXME need to update it
DB_PATH = '/L/data/wereyouhere/visits.sqlite'

FALLBACK_TIMEZONE = pytz.timezone('Europe/London')

FILTERS = [] # type: ignore


from wereyouhere.generator.smart import Indexer as I
from wereyouhere.generator.plaintext import extract_from_path
import wereyouhere.extractors.custom as custom # type: ignore
import wereyouhere.extractors.takeout as takeout # type: ignore

class Extractors:
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


EXTRACTORS = [
    Extractors.PLAIN,
    Extractors.TAKEOUT,
]

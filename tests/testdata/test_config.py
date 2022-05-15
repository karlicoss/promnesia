from pathlib import Path

from promnesia.common import Source
from promnesia.sources.plaintext import extract_from_path
import promnesia.sources.shellcmd as shellcmd # type: ignore
import promnesia.sources.takeout as takeout # type: ignore


def index_takeout():
    class user_config:
        takeout_path = 'tests/testdata/takeout-20150518T000000Z.zip'

    import my.config
    my.config.google = user_config # type: ignore

    yield from takeout.index()


class Sources:

    TAKEOUT = Source(index_takeout, name='takeout')

    PLAIN = Source(
        shellcmd.index,
        extract_from_path('tests/testdata/custom'),
        name='test',
    )


SOURCES = [
    Sources.PLAIN,
    Sources.TAKEOUT,
]

# todo ugh, this shouldn't really be collected by pytest...

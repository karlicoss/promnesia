from pathlib import Path

from promnesia.common import Source
from promnesia.sources.plaintext import extract_from_path
import promnesia.sources.shellcmd as shellcmd # type: ignore
import promnesia.sources.takeout as takeout # type: ignore


class Sources:
    TAKEOUT = Source(
        takeout.index,
        # TODO relative paths are not great..
        'testdata/takeout-20150518T000000Z.zip',
        name='takeout',
    )

    PLAIN = Source(
        shellcmd.index,
        extract_from_path('testdata/custom'),
        name='test',
    )


SOURCES = [
    Sources.PLAIN,
    Sources.TAKEOUT,
]

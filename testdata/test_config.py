from pathlib import Path

from promnesia.common import Source
from promnesia.sources.plaintext import extract_from_path
import promnesia.sources.shellcmd as shellcmd # type: ignore
import promnesia.sources.takeout as takeout # type: ignore


class Sources:
    @staticmethod
    def TAKEOUT():
        # TODO would be good to share this with readme..
        from my.cfg import config
        from types import SimpleNamespace
        config.google = SimpleNamespace(
            takeout_path='testdata/takeout-20150518T000000Z.zip',
        )
        return Source(
            takeout.index,
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

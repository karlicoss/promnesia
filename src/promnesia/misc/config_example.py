from promnesia.common import Source
from promnesia.sources import auto

'''
List of sources to use.

You can specify your own, add more sources, etc.
See https://github.com/karlicoss/promnesia#setup for more information
'''
SOURCES = [
    Source(
        auto.index,
        # just some arbitrary directory with plaintext files
        '/usr/share/vim/',
    )
]

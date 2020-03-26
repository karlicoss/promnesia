from contextlib import contextmanager
from pathlib import Path
from subprocess import Popen
from typing import Optional

# TODO decorator that records a video if a certain env var/flag is set (pass a custom name too)

@contextmanager
def hotkeys(geometry: Optional[str]=None):
    # TODO kill in advance??
    ctx = Popen([
        'screenkey',
        '--no-detach',
        '--timeout', '2',
        '--key-mode', 'composed',
        *([] if geometry is None else ['-g', geometry]),
    ])
    with ctx as p:
        try:
            yield p
        finally:
            p.kill()


@contextmanager
def record(output: Optional[Path]=None, wid: Optional[str]=None, quality: Optional[str]=None):
    assert output is not None, "TODO use tmp file or current dir??"

    ctx = Popen([
        'recordmydesktop',
        *([] if wid     is None else ['--windowid' , wid]),
        *([] if quality is None else ['--v_quality', quality]),

        '--no-sound',
        '--on-the-fly-encoding',
        '--workdir=/tmp', # TODO not sure..

        '--overwrite', # TODO make optional?
        '--output', output,
    ])
    with ctx as p:
        try:
            yield p
        finally:
            # TODO check if it terminated gracefully?
            p.terminate()
            p.wait(timeout=10)

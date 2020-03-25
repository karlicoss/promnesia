from contextlib import contextmanager
from pathlib import Path
from subprocess import Popen
from typing import Optional

# TODO decorator that records a video if a certain env var/flag is set (pass a custom name too)

@contextmanager
def hotkeys():
    # TODO kill in advance??
    ctx = Popen([
        'screenkey',
        '--no-detach',
        '--timeout', '2',
        '--key-mode', 'composed',
    ])
    with ctx as p:
        try:
            yield p
        finally:
            p.kill()


@contextmanager
def record(output: Optional[Path]=None):
    assert output is not None, "TODO use tmp file or current dir??"

    # TODO window-id
    ctx = Popen([
        'recordmydesktop',
        '--no-sound',
        '--v_quality=1', # TODO fix quality later
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

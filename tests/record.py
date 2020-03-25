from contextlib import contextmanager
from pathlib import Path
from typing import Optional

# TODO decorator that records a video if a certain env var/flag is set (pass a custom name too)


@contextmanager
def record(output: Optional[Path]=None):
    assert output is not None, "TODO use tmp file or current dir??"

    from subprocess import Popen
    # TODO window-id
    ctx = Popen([
        'recordmydesktop',
        '--no-sound',
        '--v_quality=1', # TODO fix quality later
        '--on-the-fly-encoding',
        '--workdir=/tmp', # TODO not sure..
        '--output', output,
    ])
    with ctx as p:
        try:
            yield p
        finally:
            # TODO check if it terminated gracefully?
            p.terminate()

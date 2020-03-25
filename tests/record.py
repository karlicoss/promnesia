from contextlib import contextmanager

# TODO decorator that records a video if a certain env var/flag is set (pass a custom name too)


# recordmydesktop --no-sound --v_quality=1 --on-the-fly-encoding --workdir=/tmp --output /tmp/res.ogv
@contextmanager
def record():
    from subprocess import Popen
    # TODO window-id
    ctx = Popen([
        'recordmydesktop',
        '--no-sound',
        '--v_quality=1',
        '--on-the-fly-encoding',
        '--workdir=/tmp',
        '--output', '/tmp/res.ogv'
    ])
    with ctx as p:
        try:
            yield p
        finally:
            p.terminate()

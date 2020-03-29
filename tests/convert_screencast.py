#!/usr/bin/env python3
import sys
from pathlib import Path
from subprocess import check_call


if __name__ == '__main__':
    path = Path(sys.argv[1])
    ogv  = path.with_suffix('.ogv')
    assert ogv.exists(), ogv
    subs = path.with_suffix('.ssa')
    webm = path.with_suffix('.webm')


    # jeez... https://video.stackexchange.com/a/28276/29090
    # otherwise quiality sucks, e.g. letters are grainy
    for stage in [
            f'-pass 1 -an -f webm /dev/null',
            f'-pass 2 {webm}',
    ]:
        check_call([
            'ffmpeg',
            # TODO display banner if running interactively??
            '-hide_banner', '-loglevel', 'panic', # less spam
            '-y', # allow overwrite
            '-i', ogv,
            '-vf', f"ass={subs}",
            *stage.split(),
        ])

#!/usr/bin/env python3
import sys
from pathlib import Path
from subprocess import check_call


def convert(path: Path):
    if path.suffix == '.ogv':
        # makes it easier for shell globbing...
        path = path.with_suffix('')

    ogv  = path.with_suffix('.ogv')
    assert ogv.exists(), ogv
    subs = path.with_suffix('.ssa')
    webm = path.with_suffix('.webm')


    # jeez... https://video.stackexchange.com/a/28276/29090
    # otherwise quiality sucks, e.g. letters are grainy
    for stage in [
            f'-b:v 0  -crf 30  -pass 1 -passlogfile {path.with_suffix(".pass0")} -an -f webm /dev/null',
            f'-b:v 0  -crf 30  -pass 2 {webm}' if all(
                x not in str(ogv) for x in (
                    # fucking hell, it segfaults...
                    'child-visits-2',
                    'highlights',
                )) else str(webm),
    ]:
        check_call([
            'ffmpeg',
            # TODO display banner if running interactively??
            '-hide_banner', '-loglevel', 'panic', # less spam
            '-y', # allow overwrite
            '-i', ogv,
            '-vf', f"ass={subs}",
            *stage.split(),
        ]) # TODO cwd??


if __name__ == '__main__':
    paths = list(map(Path, sys.argv[1:]))
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor() as pool:
        for _ in pool.map(convert, paths):
            # need to force the iterator
            pass

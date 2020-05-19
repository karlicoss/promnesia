#!/usr/bin/env python3
import sys
from pathlib import Path
from subprocess import check_call


def convert(path: Path):
    suf = '.mp4'
    if path.suffix == suf:
        # makes it easier for shell globbing...
        path = path.with_suffix('')

    inp  = path.with_suffix(suf)
    assert inp.exists(), inp
    subs = path.with_suffix('.ssa')
    webm = path.with_suffix('.webm')


    # jeez... https://video.stackexchange.com/a/28276/29090
    # otherwise quiality sucks, e.g. letters are grainy
    #
    # ok, nice guide.. https://gist.github.com/Vestride/278e13915894821e1d6f#convert-to-webm
    #
    passfile = path.with_suffix(".pass0")
    for stage in [
            f'-b:v 0  -crf 30  -pass 1 -passlogfile {passfile} -an -f webm /dev/null',
            f'-b:v 0  -crf 30  -pass 2 -passlogfile {passfile} {webm}' if all(
                x not in str(inp) for x in (
                    # fucking hell, it segfaults...
                    'child-visits-2',
                    'highlights',
                )) else str(webm),
    ]:
        check_call([
            'ffmpeg',
            # TODO display banner if running interactively??
            # '-hide_banner', '-loglevel', 'panic', # less spam
            '-y', # allow overwrite
            '-i', inp,
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

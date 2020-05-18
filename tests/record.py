from contextlib import contextmanager
from pathlib import Path
import re
from time import sleep
from subprocess import Popen, check_output
from typing import Optional, List, Union

# TODO decorator that records a video if a certain env var/flag is set (pass a custom name too)

@contextmanager
def hotkeys(geometry: Optional[str]=None):
    # TODO kill in advance??
    ctx = Popen([
        'screenkey',
        '--no-detach',
        '--key-mode', 'composed',
        '--scr', '0',
        '--timeout', '2',
        '--bg-color', '#000000',
        '--font-color', '#ffffff',
        '--font-size', 'large',
        '--opacity', '0.6',
        # TODO hmm. it has --persist arg, but no --no-persist??
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
    # TODO to fullscreen if None?
    assert wid is not None


    # ugh. no idea wtf is happening here... why is position 2,90??
    # wmctrl -i -r 230686723 -e '0,0,0,400,400'
    # xdotool getwindowgeometry 230686723
    # Window 230686723
    #   Position: 2,90 (screen: 0)
    #   Geometry: 400x400
    # Position + Geometry don't add up to the screen size. fuck.
    #
    # ok, xwininfo seems more reliable
    #
    # xwininfo -id $(xdotool getactivewindow)'
    out = check_output(['xwininfo', '-id', wid]).decode('utf8').replace('\n', ' ')
    m = re.search(r'geometry (\d+)x(\d+)[+-](\d+)[+-](\d+)', out)
    assert m is not None, out
    w, h, x, y = m.groups()

    # fuck.
    titlebar = 32

    # fuck x 2
    margin   = 28

    cmd: List[Union[Path, str]] = [
        'ffmpeg',
        '-hide_banner', '-loglevel', 'panic', # less spam in the terminal
        '-f', 'x11grab',
        '-y',
        '-r', '30',
        '-s', f'{w}x{titlebar + int(h)}',
        '-i', f':0.0+{x},{margin + int(y)}',
        output,
    ]
    # TODO not sure if need converter script
    # TODO double check there are no ffmpeg processes remaining?
    # maybe, set timeout?

    with Popen(cmd) as p:
        # early check
        sleep(0.5)
        assert p.poll() is None, f'{cmd} died!'

        try:
            yield p
        finally:
            assert p.poll() is None, f'{cmd} died!'

            p.terminate()
            p.wait(timeout=10)


# https://stackoverflow.com/a/52669454/706389
CURSOR_SCRIPT = '''
function enableCursor() {
  var seleniumFollowerImg = document.createElement("img");
  seleniumFollowerImg.setAttribute('src', 'data:image/png;base64,'
    + 'iVBORw0KGgoAAAANSUhEUgAAABQAAAAeCAQAAACGG/bgAAAAAmJLR0QA/4ePzL8AAAAJcEhZcwAA'
    + 'HsYAAB7GAZEt8iwAAAAHdElNRQfgAwgMIwdxU/i7AAABZklEQVQ4y43TsU4UURSH8W+XmYwkS2I0'
    + '9CRKpKGhsvIJjG9giQmliHFZlkUIGnEF7KTiCagpsYHWhoTQaiUUxLixYZb5KAAZZhbunu7O/PKf'
    + 'e+fcA+/pqwb4DuximEqXhT4iI8dMpBWEsWsuGYdpZFttiLSSgTvhZ1W/SvfO1CvYdV1kPghV68a3'
    + '0zzUWZH5pBqEui7dnqlFmLoq0gxC1XfGZdoLal2kea8ahLoqKXNAJQBT2yJzwUTVt0bS6ANqy1ga'
    + 'VCEq/oVTtjji4hQVhhnlYBH4WIJV9vlkXLm+10R8oJb79Jl1j9UdazJRGpkrmNkSF9SOz2T71s7M'
    + 'SIfD2lmmfjGSRz3hK8l4w1P+bah/HJLN0sys2JSMZQB+jKo6KSc8vLlLn5ikzF4268Wg2+pPOWW6'
    + 'ONcpr3PrXy9VfS473M/D7H+TLmrqsXtOGctvxvMv2oVNP+Av0uHbzbxyJaywyUjx8TlnPY2YxqkD'
    + 'dAAAAABJRU5ErkJggg==');
  seleniumFollowerImg.setAttribute('id', 'selenium_mouse_follower');
  seleniumFollowerImg.setAttribute('style', 'position: absolute; z-index: 99999999999; pointer-events: none; left:0; top:0');
  document.body.appendChild(seleniumFollowerImg);
  document.onmousemove = function (e) {
    document.getElementById("selenium_mouse_follower").style.left = e.pageX + 'px';
    document.getElementById("selenium_mouse_follower").style.top  = e.pageY + 'px';
  };
};

enableCursor();
'''


# https://stackoverflow.com/a/987376/706389
SELECT_SCRIPT = '''
function selectText(node) {
    if (document.body.createTextRange) {
        const range = document.body.createTextRange();
        range.moveToElementText(node);
        range.select();
    } else if (window.getSelection) {
        const selection = window.getSelection();
        const range = document.createRange();
        range.selectNodeContents(node);
        selection.removeAllRanges();
        selection.addRange(range);
    } else {
        console.warn("Could not select text in node: Unsupported browser.");
    }
}
'''

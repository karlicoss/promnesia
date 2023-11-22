from pathlib import Path

from ...common import PathIsh, _is_windows as windows
from ...sources.auto import by_path


def handled(p: PathIsh) -> bool:
    idx, m = by_path(Path(p))
    return idx is not None
    # ideally these won't hit libmagic path (would try to open the file and cause FileNotFoundError)


def test_filetypes() -> None:
    # test media
    for ext in 'avi mp4 mp3 webm'.split() + ([] if windows else 'mkv'.split()):
        assert handled('file.' + ext)

    # images
    for ext in 'gif jpg png jpeg'.split():
        assert handled('file.' + ext)

    # TODO more granual checks that these are ignored?
    # binaries
    for ext in 'o sqlite'.split() + ([] if windows else 'class jar'.split()):
        assert handled('file.' + ext)

    # these might have potentially some links
    for ext in [
        'svg',
        'pdf', 'epub', 'ps',
        'doc', 'ppt', 'xsl',
        # seriously, windows doesn't know about docx???
        *([] if windows else 'docx pptx xlsx'.split()),
        *([] if windows else 'ods odt rtf'.split()),
    ] + ([] if windows else 'djvu'.split()):
        assert handled('file.' + ext)

    # source code
    for ext in 'rs tex el js sh hs pl h py hpp c go css'.split() + ([] if windows else 'java cpp'.split()):
        assert handled('file.' + ext)

    assert handled('x.html')

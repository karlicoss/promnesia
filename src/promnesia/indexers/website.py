from pathlib import Path
from subprocess import check_call, run
from typing import Iterable

from ..common import Extraction, PathIsh, get_tmpdir, slugify, get_logger


def index(path: PathIsh, *args, **kwargs) -> Iterable[Extraction]:
    logger = get_logger()
    url = str(path)

    # TODO better context name
    tp = Path(get_tmpdir().name) / slugify(url)

    # TODO careful, set some hard limit on data size? use --quota?
    # https://www.linuxjournal.com/content/downloading-entire-web-site-wget

    cmd = [
        'wget', '--directory-prefix', str(tp),
        '--no-verbose',
        '--recursive',
        '-A', 'html,html,txt', # TODO eh, ideally would use mime type I guess...
        '--no-parent',
        url,
    ]
    # TODO follow sitemap? e.g. gwern
    logger.info(' '.join(cmd))
    res = run(cmd)

    if res.returncode == 8:
        # man wget: 8 means server error (e.g. broken link)
        yield RuntimeError('Encountered server error(s) during downloading')
    else:
        # rest of the errors are a bit more critical..
        res.check_returncode()

    # TODO smarter html handling
    from . import auto
    yield from auto.index(tp, *args, **kwargs)

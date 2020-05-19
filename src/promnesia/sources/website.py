'''
Clones a website with wget and indexes via sources.auto
'''

from pathlib import Path
import re
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

    def replacer(p: PathIsh, prefix=str(tp), url=url) -> str:
        ps = str(p)
        pos = ps.find(prefix)
        if pos == -1:
            return ps
        rest = ps[pos + len(prefix):]
        # now this should look kinda like /domain.tld/rest (due to the way wget downloads stuff)
        rest = re.sub(r'/.*?/', '/', rest)
        return url + rest

    # TODO create a file that maps prefix?
    # TODO ugh. it creates a directory with a domain... how to map it to http/https properly?

    # TODO smarter html handling
    from . import auto
    yield from auto.index(tp, *args, replacer=replacer, **kwargs)

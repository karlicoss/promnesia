'''
Extracts links from HTML files
'''

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from bs4 import BeautifulSoup, Tag

from promnesia.common import Loc, PathIsh, Results, Visit, file_mtime

# TODO present error summary in the very end; import errors -- makes sense to show
# TODO on some exceptions, request a fallback to text?


Url = tuple[str, str]


def extract_urls_from_html(s: str) -> Iterator[Url]:
    """
    Helper method to extract URLs from any HTML, so this could
    potentially be used by other modules
    """
    soup = BeautifulSoup(s, 'lxml')
    for a in soup.find_all('a'):
        assert isinstance(a, Tag), a  # make mypy happy
        href = a.attrs.get('href')
        if href is None or ('://' not in href):
            # second condition means relative link
            continue
        assert isinstance(href, str), href  # make mypy happy
        text: str = a.text
        yield (href, text)


def extract_from_file(fname: PathIsh) -> Results:
    ts = file_mtime(fname)

    for href, text in extract_urls_from_html(Path(fname).read_text(errors='replace')):
        yield Visit(
            url=href,
            dt=ts,
            locator=Loc.file(fname),
            context=text,
        )

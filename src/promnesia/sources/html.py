'''
Extracts links from HTML files
'''

from pathlib import Path
from typing import Iterator, Tuple

from ..common import PathIsh, Visit, Loc, Results, file_mtime

from bs4 import BeautifulSoup


# TODO present error summary in the very end; import errors -- makes sense to show 
# TODO on some exceptions, request a fallback to text?


Url = Tuple[str, str]

def extract_urls_from_html(s: str) -> Iterator[Url]:
    """
    Helper method to extract URLs from any HTML, so this could
    potentially be used by other modules
    """
    soup = BeautifulSoup(s, 'lxml')
    for a in soup.find_all('a'):
        href = a.attrs.get('href')
        if href is None or ('://' not in href):
            # second condition means relative link
            continue
        text = a.text
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

'''
Extracts links from HTML files
'''

from pathlib import Path
from typing import Iterator, Tuple
from ..common import PathIsh, Visit, Loc, Results, file_mtime

# TODO present error summary in the very end; import errors -- makes sense to show 
# TODO on some exceptions, request a fallback to text?

from bs4 import BeautifulSoup # type: ignore[import]

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


# from html.parser import HTMLParser
# eh. it's not really going to work well because of nesting inside <a> tags..
# class Parser(HTMLParser):
#     results: List[Tuple[str, str]] = []
#
#     link = None
#     title = None
#
#     def handle_starttag(self, tag, attrs):
#         if tag != 'a':
#             return
#         href = dict(attrs).get('href')
#         if href is None:
#             return
#         self.link = href
#
#     def handle_data(self, data):
#         # TODO only if url is set??
#         # also, only set once?
#         if self.link is not None:
#             breakpoint()
#         # TODO what if it's bold?
#         title = 'sup'
#
#     def handle_endtag(self, tag):
#         if tag != 'a':
#             return
#         # TODO if old isn't none, emit
#         if self.link is not None:
#             self.links.append((self.link, self.title))
#         self.link = None


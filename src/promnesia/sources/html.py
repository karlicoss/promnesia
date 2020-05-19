'''
Extracts links from HTML files
'''

from datetime import datetime
from pathlib import Path
from typing import List, Tuple

from ..common import PathIsh, Visit, Loc, Results

# TODO present error summary in the very end; import errors -- makes sense to show 
# TODO on some exceptions, request a fallback to text?

from bs4 import BeautifulSoup # type: ignore[import]

def extract_from_file(fname: PathIsh) -> Results:

    ts = datetime.fromtimestamp(Path(fname).stat().st_mtime)
    # TODO just allow passing file as timestamp?

    soup = BeautifulSoup(Path(fname).read_text(errors='replace'), 'lxml')
    for a in soup.find_all('a'):
        href = a.attrs.get('href')
        if href is None:
            # TODO ignore #?
            continue
        text = a.text

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


from pathlib import Path
from typing import Iterator, NamedTuple, Optional

from ..common import get_logger, Extraction, Url, PathIsh, Res, Visit, Loc, file_mtime, logger


import mistletoe # type: ignore
from mistletoe.span_token import AutoLink, Link # type: ignore
import mistletoe.block_token as BT # type: ignore
from mistletoe.html_renderer import HTMLRenderer # type: ignore


renderer = HTMLRenderer()


block_tokens = tuple(getattr(BT, name) for name in BT.__all__)


class Parsed(NamedTuple):
    url: Url
    context: Optional[str]


Result = Res[Parsed]


# the fuck...
#
# from mistletoe import Document
# d = Document('''
# # heading
# ## sub
# ## sub2
# ''')
# d.children[0].content
# Out[13]: 'sub2'

# meh, but for now fine I guess
HTML_MARKER = '!html '


def _ashtml(block) -> str:
    res = renderer.render(block)
    if res.startswith('<p>') and res.endswith('</p>'):
        res = res[3: -4] # meh, but for now fine
    return res


class Parser:
    def __init__(self, path: Path):
        self.doc = mistletoe.Document(path.read_text())

    def _extract(self, cur, last_block) -> Iterator[Parsed]:
        if not isinstance(cur, (AutoLink, Link)):
            # hopefully that's all??
            return

        url = cur.target
        # TODO fuck. it doesn't preserve line numbers/positions in text???

        # ugh. It can't output markdown.. https://github.com/miyuchina/mistletoe/issues/4
        context = None if last_block is None else HTML_MARKER + _ashtml(last_block)
        yield Parsed(url=url, context=context)


    def _walk(self, cur, last_block) -> Iterator[Result]:
        if isinstance(cur, block_tokens):
            last_block = cur

        try:
            yield from self._extract(cur, last_block)
        except Exception as e:
            logger.exception(e)
            yield e

        children = getattr(cur, 'children', [])
        for c in children:
            yield from self._walk(c, last_block=last_block)


    def walk(self):
        yield from self._walk(self.doc, last_block=None)


def extract_from_file(fname: PathIsh) -> Iterator[Extraction]:
    path = Path(fname)
    fallback_dt = file_mtime(path)

    p = Parser(path)
    for r in p.walk():
        if isinstance(r, Exception):
            yield r
        else:
            yield Visit(
                url=r.url,
                dt=fallback_dt,
                locator=Loc.file(fname), # TODO line number
                context=r.context,
            )


class TextParser(Parser):
    '''
    Used to extract links/render markdown from text, e.g. reddit/github comments
    Instead of chunking blocks like for files, this returns the entire
    message rendered as the context
    '''
    def __init__(self, text: str):
        self.doc = mistletoe.Document(text)


    def _doc_ashtml(self):
        '''
        cached html representation of the entire html message/document
        '''
        if not hasattr(self, '_html'):
            self._html = HTML_MARKER + _ashtml(self.doc)
        return self._html


    def _extract(self, cur, last_block = None) -> Iterator[Parsed]:
        if not isinstance(cur, (AutoLink, Link)):
            return

        yield Parsed(url=cur.target, context=self._doc_ashtml())


def extract_from_text(text: str) -> Iterator[Result]:
    '''
    assume this is rendering something like a github/reddit markdown message
    use the entire contents of the comment/body as the context
    '''
    # note: returns Result (link/context), not Visit
    # the callee function has to insert dt/duration etc.
    yield from TextParser(text).walk()

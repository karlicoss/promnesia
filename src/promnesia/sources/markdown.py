from datetime import datetime
from pathlib import Path
from typing import Iterator, NamedTuple, Optional

from ..common import get_logger, Extraction, Url, PathIsh, Res, Visit, echain, Loc


import mistletoe # type: ignore
from mistletoe import Document # type: ignore
from mistletoe.span_token import AutoLink, Link # type: ignore


class Parsed(NamedTuple):
    url: Url
    context: Optional[str]


Result = Res[Parsed]


def _extract(cur) -> Iterator[Parsed]:
    # TODO take in surrounding context??
    if not isinstance(cur, (AutoLink, Link)):
        # hopefully that's all??
        return

    url = cur.target
    if type(url) != str:
        print(url, type(url))
    context = None
    yield Parsed(url=url, context=context)


def _walk(cur: mistletoe.Document) -> Iterator[Result]:
    try:
        yield from _extract(cur)
    except Exception as e:
        # TODO log context??
        yield e

    children = getattr(cur, 'children', [])
    for c in children:
        yield from _walk(c)


def extract_from_file(fname: PathIsh) -> Iterator[Extraction]:
    path = Path(fname)
    fallback_dt = datetime.fromtimestamp(path.stat().st_mtime)

    ex = RuntimeError(f'while extracting from {path}')

    doc = mistletoe.Document(path.read_text())
    for r in _walk(doc):
        if isinstance(r, Exception):
            yield echain(ex, r)
        else:
            yield Visit(
                url=r.url,
                dt=fallback_dt,
                locator=Loc.file(fname), # TODO line number
                context=r.context,
            )

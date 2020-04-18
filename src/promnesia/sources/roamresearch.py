from typing import Iterable, Iterator

from ..common import Extraction, get_logger, Visit, Loc, PathIsh, extract_urls

import my.roamresearch as RR


def _collect(node: RR.Node) -> Iterable[Extraction]:
    title = node.title
    body  = node.body or ''
    if title is None:
        # most notes don't have title, so we just take the first line instead..
        lines = body.splitlines(keepends=True)
        if len(lines) > 0:
            title = lines[0]
            body = ''.join(lines)
    title = title or ''

    full = title + '\n' + body

    urls = extract_urls(full)
    if len(urls) != 0:
        loc = Loc.make(
            title=node.path,
            href=node.permalink,
        )
        for u in urls:
            yield Visit(
                url=u,
                dt=node.created,
                context=body,
                locator=loc,
            )
    for c in node.children:
        yield from _collect(c)


def index() -> Iterator[Extraction]:
    roam = RR.roam()
    for n in roam.notes:
        yield from _collect(n)

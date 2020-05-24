'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Roam Research data
'''

from ..common import Results, Visit, Loc, extract_urls


def index() -> Results:
    import my.roamresearch as RR
    roam = RR.roam()
    for node in roam.traverse():
        yield from _collect(node)


def _collect(node: 'RoamNode') -> Results:
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
    if len(urls) == 0:
        return

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


import typing
if typing.TYPE_CHECKING:
    import my.roamresearch as RR
    RoamNode = RR.Node

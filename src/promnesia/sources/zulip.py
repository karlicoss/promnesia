'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Zulip data.
'''

from ..common import Results, Visit, Loc, iter_urls


def index() -> Results:
    from . import hpi
    import my.zulip.organization as Z
    for m in Z.messages():
        if isinstance(m, Exception):
            yield m
            continue
        loc = Loc.make(title=f'{m.sender.full_name} mentioned', href=m.permalink)
        # todo if syntax is markdown, could extract title as well?
        content = m.content
        for u in iter_urls(content, syntax='markdown'):
            yield Visit(
                url=u,
                dt=m.sent,
                # TODO render as markdown?
                context=content,
                locator=loc,
            )

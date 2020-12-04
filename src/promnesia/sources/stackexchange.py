'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Stackexchange data.
'''

from ..common import Results, Visit, Loc, extract_urls


def index() -> Results:
    from . import hpi
    import my.stackexchange.gdpr as G # type: ignore[import] # TODO eh, not sure if should run against pypi or not...
    for v in G.votes():
        if isinstance(v, Exception):
            yield v
        else:
            yield Visit(
                url=v.link,
                dt=v.when,
                context='voted', # todo use the votetype? although maybe worth ignoring downvotes
                # or, downvotes could have 'negative' ranking or something
                locator=Loc.make(title='voted', href=v.link)
            )

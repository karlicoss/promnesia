'''
Uses [[https://github.com/karlicoss/HPI][HPI]] for Stackexchange data.
'''

from promnesia.common import Loc, Results, Visit


def index() -> Results:
    from . import hpi  # noqa: F401,I001
    import my.stackexchange.gdpr as G

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

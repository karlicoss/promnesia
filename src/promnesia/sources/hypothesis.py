'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myhypothesis][hypothesis]] module
'''
from ..common import Visit, Results, logger, Loc


def index() -> Results:
    from . import hpi
    import my.hypothesis as hyp
    for h in hyp.get_highlights():
        if isinstance(h, Exception):
            yield h
            continue
        hl = h.highlight
        ann = h.annotation
        cparts = []
        if hl is not None:
            cparts.append(hl)
        if ann is not None:
            cparts.extend(['comment: ' + ann])
        yield Visit(
            url=h.url,
            dt=h.created,
            context='\n\n'.join(cparts),
            locator=Loc.make(
                title='hypothesis',
                href=h.hyp_link,
            )
        )

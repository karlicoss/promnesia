'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myhypothesis][hypothesis]] module
'''
from ..common import Visit, Results, get_logger, Loc

import my.hypothesis as hyp


def index() -> Results:
    logger = get_logger()

    for h in hyp.get_highlights():
        if isinstance(h, Exception):
            yield h
            continue
        # TODO FIXME need to make sure it's typechecked on CI... and also do coverage checks
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

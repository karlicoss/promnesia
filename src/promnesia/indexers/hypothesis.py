# extracts stuff from hypothes.is json backup
from typing import Iterable

from ..common import Visit, Extraction, get_logger, Loc

import my.hypothesis as hyp


def index() -> Iterable[Extraction]:
    logger = get_logger()

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

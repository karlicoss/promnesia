# extracts stuff from hypothes.is json backup
from pathlib import Path
import logging
from typing import NamedTuple, List, Optional, Union, Iterable

from ..common import PathIsh, Visit, Extraction, get_logger, Loc

import my.hypothesis as hyp


# TODO perhaps configuring should be external? e.g. in config, although it'd probably not propagate?
def index(**kwargs) -> Iterable[Extraction]:
    hyp.configure(**kwargs)

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

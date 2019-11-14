# extracts stuff from hypothes.is json backup
from pathlib import Path
import logging
from typing import NamedTuple, List, Optional, Union, Iterable

from ..common import PathIsh, Visit, get_logger, Loc

# pylint: disable=import-error
import my.hypothesis as hyp # type: ignore


# TODO perhaps configuring should be external? e.g. in config, although it'd probably not propagate?
def index(**kwargs) -> Iterable[Visit]:
    hyp.configure(**kwargs)

    logger = get_logger()

    # TODO FIXME careful, need defensive error handling?
    for h in hyp.get_highlights():
        hl = h.highlight
        ann = h.annotation
        cparts = []
        if hl is not None:
            cparts.append(hl)
        if ann is not None:
            cparts.extend(['comment: ' + ann])
        yield Visit(
            url=h.page_link,
            dt=h.dt,
            context='\n\n'.join(cparts),
            locator=Loc.make(
                title='hypothesis',
                href=h.hyp_link,
            )
        )

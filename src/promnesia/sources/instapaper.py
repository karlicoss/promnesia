from typing import Iterator, Optional

from ..common import Extraction, get_logger, Visit, Loc, PathIsh

import my.instapaper as ip


def index() -> Iterator[Extraction]:
    logger = get_logger()

    for p in ip.pages():
        bm = p.bookmark
        hls = p.highlights

        def visit(**kwargs):
            return Visit(
                url=bm.url,
                **kwargs,
            )

        if len(hls) == 0:
            yield visit(
                dt=bm.dt,
                context=None,
                locator=Loc.make(title='instapaper', href=bm.instapaper_link),
            )
        else:
            for hl in p.highlights:
                cparts = [hl.text]
                if hl.note is not None:
                    cparts.append('comment: ' + hl.note)
                yield visit(
                    dt=hl.dt,
                    context='\n'.join(cparts),
                    locator=Loc.make(title='instapaper', href=hl.instapaper_link),
                )


'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myinstapaper][instapaper]] module
'''
from ..common import Results, get_logger, Visit, Loc

import my.instapaper as ip


def index() -> Results:
    logger = get_logger()

    for p in ip.pages():
        bm = p.bookmark # type: ignore[attr-defined]
        hls = p.highlights # type: ignore[attr-defined]

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
            for hl in p.highlights: # type: ignore[attr-defined]
                cparts = [hl.text]
                if hl.note is not None:
                    cparts.append('comment: ' + hl.note)
                yield visit(
                    dt=hl.dt,
                    context='\n'.join(cparts),
                    locator=Loc.make(title='instapaper', href=hl.instapaper_link),
                )


# TODO mypy: properly clone repos and typecheck on CI, get rid of attr-defined ignores

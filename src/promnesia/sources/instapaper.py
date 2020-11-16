'''
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myinstapaper][instapaper]] module
'''
from ..common import Results, logger, Visit, Loc


def index() -> Results:
    from . import hpi
    import my.instapaper as ip

    for p in ip.pages():
        bm = p.bookmark
        hls = p.highlights

        def visit(**kwargs) -> Visit:
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

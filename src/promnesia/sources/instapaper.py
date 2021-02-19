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

        if len(hls) == 0:
            yield Visit(
                url=bm.url,
                dt=bm.dt,
                context=None,
                locator=Loc.make(title='instapaper', href=bm.instapaper_link),
            )
        else:
            for hl in p.highlights:
                cparts = [hl.text]
                if hl.note is not None:
                    cparts.append('comment: ' + hl.note)
                yield Visit(
                    url=bm.url,
                    dt=hl.dt,
                    context='\n'.join(cparts),
                    locator=Loc.make(title='instapaper', href=hl.instapaper_link),
                )

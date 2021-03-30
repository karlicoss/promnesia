"""
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myhypothesis][hypothesis]] module
"""
from ..common import Loc, Results, Visit, extract_urls


def _harvest_text(text, visit_base) -> Results:
    if text and text.strip():
        urls = extract_urls(text)
        for url in urls:
            yield visit_base._replace(url=url)


def index() -> Results:
    from . import hpi
    import my.hypothesis as hyp
    for h in hyp.get_highlights():
        if isinstance(h, Exception):
            yield h
            continue
        hl = h.highlight
        ann = h.annotation
        tags = h.tags
        cparts = []
        if hl is not None:
            cparts.append(hl)
        if ann is not None:
            cparts.append(f"comment: {ann}")
        if tags:
            cparts.append(" ".join(f"#{t}" for t in tags))
        visit = Visit(
            url=h.url,
            dt=h.created,
            context="\n\n".join(cparts),
            locator=Loc.make(
                title="hypothesis",
                href=h.hyp_link,
            ),
        )

        yield visit

        for text in (hl, ann):
            yield from _harvest_text(text, visit)

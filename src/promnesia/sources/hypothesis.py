"""
Uses HPI [[https://github.com/karlicoss/HPI/blob/master/doc/MODULES.org#myhypothesis][hypothesis]] module
"""
from ..common import Loc, Results, Visit, extract_urls, join_tags


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
            cparts.append(join_tags(tags))
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

        in_text_visits = (
            (hl, "highlighted"),
            (ann, "comment"),
        )
        for text, part_name in in_text_visits:
            if text and text.strip():
                urls = extract_urls(text)
                for url in urls:
                    yield visit._replace(
                        url=url,
                        locator=visit.locator._replace(title=f"hypothesis-{part_name}"),
                    )

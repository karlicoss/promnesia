from typing import Optional

from promnesia.common import Results, Visit, Loc, Second


def index() -> Results:
    from . import hpi
    from my.browser.all import history

    for v in history():
        desc: Optional[str] = None
        duration: Optional[Second] = None
        metadata = v.metadata
        if metadata is not None:
            desc = metadata.title
            duration = metadata.duration
        yield Visit(
            url=v.url,
            dt=v.dt,
            locator=Loc(title=desc or v.url, href=v.url),
            duration=duration,
        )

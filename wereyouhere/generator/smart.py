# TODO: give a better name...
from typing import Iterable

from wereyouhere.common import History, Visit, PreVisit

import dateparser # type: ignore

def extract(extr: Iterable[PreVisit]) -> History:
    # TODO make more defensive?
    h = History()
    previsits = list(extr)
    for p in previsits:
        if isinstance(p.dt, str):
            dt = dateparser.parse(p.dt)
        else:
            dt = p.dt

        visit = Visit(
            dt=dt,
            tag=p.tag,
            context=p.context,
        )
        h.register(p.url, visit)
    return h

# TODO: give a better name...
from typing import Iterable

from wereyouhere.common import History, Visit, PreVisit, get_logger

import dateparser # type: ignore

def extract(ff, *args, **kwargs) -> History:
    # TODO make more defensive?
    logger = get_logger()
    logger.info(f'extracting via {ff.__module__}:{ff.__name__} {args} {kwargs} ...')

    extr: Iterable[PreVisit] = ff(*args, **kwargs)
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

    logger.info(f'extracting via {ff.__module__}:{ff.__name__} {args} {kwargs}: got {len(h)} visits')
    return h

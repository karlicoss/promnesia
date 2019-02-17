# TODO: give a better name...
from datetime import datetime, date
from typing import Iterable, List, Tuple

from wereyouhere.common import History, Visit, PreVisit, get_logger

import dateparser # type: ignore

class Wrapper:
    def __init__(self, ff, *args, **kwargs):
        self.ff = ff
        self.args = args
        self.kwargs = kwargs

def previsits_to_history(extractor) -> Tuple[History, List[Exception]]:
    ex = extractor
    # TODO isinstance wrapper?
    # TODO make more defensive?
    logger = get_logger()

    log_info: str
    if isinstance(ex, Wrapper):
        log_info = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs} ...'
        extr = lambda: ex.ff(*ex.args, **ex.kwargs)
    else:
        # TODO if it's a lambda?
        log_info = f'{ex.__module__}:{ex.__name__}'
        extr = ex


    logger.info('extracting via %s ...', log_info)

    h = History()
    errors = []
    previsits = list(extr()) # TODO DEFENSIVE HERE!!!
    for p in previsits:
        if isinstance(p, Exception):
            errors.append(p)
            logger.error('extractor emitted exception!')
            logger.exception(p)
            continue

        # TODO might want to append errors here too?
        if isinstance(p.dt, str):
            dt = dateparser.parse(p.dt)
        elif isinstance(p.dt, datetime):
            dt = p.dt
        elif isinstance(p.dt, date):
            dt = datetime.combine(p.dt, datetime.min.time()) # meh..
        else:
            raise AssertionError(f'unexpected date: {p.dt}, {type(p.dt)}')

        visit = Visit(
            dt=dt,
            tag=p.tag,
            context=p.context,
        )
        h.register(p.url, visit)

    logger.info('extracting via %s: got %d visits', log_info, len(h))
    return h, errors

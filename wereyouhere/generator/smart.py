# TODO: give a better name...
from kython.kerror import unwrap

from typing import Iterable, List, Tuple

from wereyouhere.common import History, PreVisit, get_logger, Loc

class Wrapper:
    def __init__(self, ff, *args, **kwargs):
        self.ff = ff
        self.args = args
        self.kwargs = kwargs

# TODO do we really need it?
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

        # TODO check whether it's filtered before construction? probably doesn't really impact
        try:
            unwrap(h.register(p))
        except Exception as e:
            logger.exception(e)
            errors.append(e)

    # TODO should handle filtering properly?
    logger.info('extracting via %s: got %d visits', log_info, len(h))
    return h, errors

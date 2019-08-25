# TODO: give a better name...
from typing import Iterable, List, Optional, Tuple

from kython.kerror import unwrap

from ..common import History, Loc, PreVisit, get_logger, Source, DbVisit


class Indexer:
    def __init__(self, ff, *args, src: str, **kwargs):
        self.ff = ff
        self.args = args
        self.kwargs = kwargs
        self.src = src

# TODO do we really need it?
def previsits_to_history(extractor, *, src: Source) -> Tuple[List[DbVisit], List[Exception]]:
    ex = extractor
    # TODO isinstance wrapper?
    # TODO make more defensive?
    logger = get_logger()

    log_info: str
    if isinstance(ex, Indexer):
        log_info = f'{ex.ff.__module__}:{ex.ff.__name__} {ex.args} {ex.kwargs} ...'
        extr = lambda: ex.ff(*ex.args, **ex.kwargs)
    else:
        # TODO if it's a lambda?
        log_info = f'{ex.__module__}:{ex.__name__}'
        extr = ex


    logger.info('extracting via %s ...', log_info)

    h = History(src=src)
    errors = []
    previsits = list(extr()) # TODO DEFENSIVE HERE!!!
    for p in previsits:
        if isinstance(p, Exception):
            errors.append(p)

            # Ok, I guess we can't rely on normal exception logger here because it expects proper traceback
            # so we can unroll the cause chain manually at least...
            # TODO at least preserving location would be nice.
            parts = ['indexer emitted exception']
            cur: Optional[BaseException] = p
            while cur is not None:
                ss = str(cur)
                if len(parts) >= 2:
                    ss = 'caused by ' + ss # TODO use some lib for that
                parts.append(ss)
                cur = cur.__cause__
            logger.error('\n'.join(parts))
            continue

        # TODO check whether it's filtered before construction? probably doesn't really impact
        try:
            unwrap(h.register(p))
        except Exception as e:
            logger.exception(e)
            errors.append(e)

    # TODO should handle filtering properly?
    logger.info('extracting via %s: got %d visits', log_info, len(h))
    return h.visits, errors

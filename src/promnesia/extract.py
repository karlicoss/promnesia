from functools import lru_cache
import re
import traceback
from typing import Set, Iterable, Sequence, Union

from .cannon import CanonifyException
from .common import (
    logger,
    DbVisit, Visit,
    Res,
    SourceName, Source,
    Filter,
    Url,
    Results, Extractor,
)


DEFAULT_FILTERS = (
    r'^chrome-\w+://',
    r'chrome://newtab',
    r'chrome://apps',
    r'chrome://history',
    r'^about:',
    r'^blob:',
    r'^view-source:',

    r'^content:',
)


@lru_cache(1) #meh, not sure what would happen under tests?
def filters() -> Sequence[Filter]:
    from . import config

    flt = list(DEFAULT_FILTERS)
    if config.has(): # meeeh...
        cfg = config.get()
        flt.extend(cfg.FILTERS)
    return tuple(make_filter(f) for f in flt)


def extract_visits(source: Source, *, src: SourceName) -> Iterable[Res[DbVisit]]:
    extractor = source.extractor
    logger.info('extracting via %s ...', source.description)

    try:
        vit: Results = extractor()
    except Exception as e:
        # todo critical error?
        # cause that means error during binding extractor args
        logger.exception(e)
        yield e
        return

    handled: Set[Visit] = set()
    try:
        for p in vit:
            if isinstance(p, Exception):
                # todo not sure if need it at all?
                # parts = ['indexer emitted exception\n']
                # eh, exception type is ignored by format_exception completely, apparently??
                # parts.extend(traceback.format_exception(Exception, p, p.__traceback__))
                # logger.error(''.join(parts))
                yield p
                continue

            if p in handled: # no need to emit duplicates
                continue
            handled.add(p)

            yield from as_db_visit(p, src=src)
    except Exception as e:
        # todo critical error?
        logger.exception(e)
        yield e


    logger.info('extracting via %s: got %d visits', source.description, len(handled))


def as_db_visit(v: Visit, *, src: SourceName) -> Iterable[Res[DbVisit]]:
    if filtered(v.url):
        return
    res = DbVisit.make(v, src=src)
    if isinstance(res, CanonifyException):
        # todo not sure if need this log? either way maybe get rid of canonify exception and just yield up
        logger.error('error while canonnifying %s... ignoring', v)
        logger.exception(res)
    yield res


def filtered(url: Url) -> bool:
    return any(f(url) for f in filters())


def make_filter(thing: Union[str, Filter]) -> Filter:
    if isinstance(thing, str):
        rc = re.compile(thing)
        def filter_(u: str) -> bool:
            return rc.search(u) is not None
        return filter_
    else: # must be predicate
        return thing

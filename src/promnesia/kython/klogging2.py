#!/usr/bin/env python3
import logging
from typing import Union, Optional

Level = int
LevelIsh = Optional[Union[Level, str]]


def mklevel(level: LevelIsh) -> Level:
    if level is None:
        return logging.NOTSET
    if isinstance(level, int):
        return level
    return getattr(logging, level.upper())


_FMT = '{start}[%(levelname)-7s %(asctime)s %(name)s %(filename)s:%(lineno)d]{end} %(message)s'
_FMT_COLOR   = _FMT.format(start='%(color)s', end='%(end_color)s')
_FMT_NOCOLOR = _FMT.format(start='', end='')


def setup_logger(logger: logging.Logger, level: Level) -> None:
    try:
        import logzero # type: ignore
    except ModuleNotFoundError:
        import warnings
        warnings.warn("You might want to install 'logzero' for nice colored logs!")
        logger.setLevel(level)
        h = logging.StreamHandler()
        h.setLevel(level)
        h.setFormatter(logging.Formatter(fmt=_FMT_NOCOLOR))
        logger.addHandler(h)
    else:
        formatter = logzero.LogFormatter(
            fmt=_FMT_COLOR,
            datefmt=None, # pass None to prevent logzero from messing with date format
        )
        logzero.setup_logger(logger.name, level=level, formatter=formatter)


class LazyLogger(logging.Logger):
    # TODO perhaps should use __new__?

    def __new__(cls, name, level: LevelIsh = 'DEBUG'):
        logger = logging.getLogger(name)
        lvl = mklevel(level)

        # this is called prior to all _log calls so makes sense to do it here?
        def isEnabledFor_lazyinit(*args, logger=logger, orig=logger.isEnabledFor, **kwargs):
            att = 'lazylogger_init_done'
            if not getattr(logger, att, False): # init once, if necessary
                setup_logger(logger, level=lvl)
                setattr(logger, att, True)
            return orig(*args, **kwargs)

        logger.isEnabledFor = isEnabledFor_lazyinit  # type: ignore[assignment]
        return logger


def test():
    ll = LazyLogger('test')
    ll.debug('THIS IS DEBUG')
    ll.warning('THIS IS WARNING')
    ll.exception(RuntimeError("oops"))


if __name__ == '__main__':
    test()

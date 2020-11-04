#!/usr/bin/env python3
'''
Default logger is a bit, see 'test'/run this file for a demo
'''

def test() -> None:
    import logging
    import sys
    M = lambda s: print(s, file=sys.stderr)

    M("   Logging module's deafults are not great...'")
    l = logging.getLogger('test_logger')
    l.error("For example, this should be logged as error. But it's not even formatted properly, doesn't have logger name or level")

    M("   The reason is that you need to remember to call basicConfig() first")
    logging.basicConfig()
    l.error("OK, this is better. But the default format kinda sucks, I prefer having timestamps and the file/line number")

    M("")
    M("    With LazyLogger you get a reasonable logging format, colours and other neat things")

    ll = LazyLogger('test') # No need for basicConfig!
    ll.info("default level is INFO")
    ll.debug(".. so this shouldn't be displayed")
    ll.warning("warnings are easy to spot!")
    ll.exception(RuntimeError("exceptions as well"))


import logging
from typing import Union, Optional
import os
import warnings

Level = int
LevelIsh = Optional[Union[Level, str]]


def mklevel(level: LevelIsh) -> Level:
    # todo do the same for Promnesia?
    # glevel = os.environ.get('HPI_LOGS', None)
    # if glevel is not None:
    #     level = glevel
    if level is None:
        return logging.NOTSET
    if isinstance(level, int):
        return level
    return getattr(logging, level.upper())


FORMAT = '{start}[%(levelname)-7s %(asctime)s %(name)s %(filename)s:%(lineno)d]{end} %(message)s'
FORMAT_COLOR   = FORMAT.format(start='%(color)s', end='%(end_color)s')
FORMAT_NOCOLOR = FORMAT.format(start='', end='')
DATEFMT = '%Y-%m-%d %H:%M:%S'

# NOTE: this is a bit experimental and temporary..
COLLAPSE_DEBUG_LOGS = os.environ.get('COLLAPSE_DEBUG_LOGS', False)

_init_done = 'lazylogger_init_done'

def setup_logger(logger: logging.Logger, level: LevelIsh) -> None:
    lvl = mklevel(level)
    try:
        import logzero # type: ignore[import]
        formatter = logzero.LogFormatter(
            fmt=FORMAT_COLOR,
            datefmt=DATEFMT,
        )
        use_logzero = True
    except ModuleNotFoundError:
        warnings.warn("You might want to install 'logzero' for nice colored logs!")
        formatter = logging.Formatter(fmt=FORMAT_NOCOLOR, datefmt=DATEFMT)
        use_logzero = False

    if use_logzero and not COLLAPSE_DEBUG_LOGS: # all set, nothing to do
        # 'simple' setup
        logzero.setup_logger(logger.name, level=lvl, formatter=formatter)
        return

    h = CollapseDebugHandler() if COLLAPSE_DEBUG_LOGS else logging.StreamHandler()
    logger.setLevel(lvl)
    h.setLevel(lvl)
    h.setFormatter(formatter)
    logger.addHandler(h)
    logger.propagate = False # ugh. otherwise it duplicates log messages


class LazyLogger(logging.Logger):
    def __new__(cls, name, level: LevelIsh = 'INFO'):
        logger = logging.getLogger(name)

        # this is called prior to all _log calls so makes sense to do it here?
        def isEnabledFor_lazyinit(*args, logger=logger, orig=logger.isEnabledFor, **kwargs):
            if not getattr(logger, _init_done, False):
                setup_logger(logger, level=level)
                setattr(logger, _init_done, True)
                logger.isEnabledFor = orig # restore the callback
            return orig(*args, **kwargs)

        # oh god.. otherwise might go into an inf loop
        if not hasattr(logger, _init_done):
            setattr(logger, _init_done, False) # will setup on the first call
            logger.isEnabledFor = isEnabledFor_lazyinit  # type: ignore[assignment]
        return logger


# todo also save full log in a file?
class CollapseDebugHandler(logging.StreamHandler):
    '''
    Collapses subsequent debug log lines and redraws on the same line.
    Hopefully this gives both a sense of progress and doesn't clutter the terminal as much?
    '''
    last = False

    def emit(self, record):
        try:
            msg = self.format(record)
            cur = record.levelno == logging.DEBUG and '\n' not in msg
            if cur:
                if self.last:
                    self.stream.write('\033[K' + '\r') # clear line + return carriage
            else:
                if self.last:
                    self.stream.write('\n') # clean up after the last debug line
            self.last = cur
            import os
            columns, _ = os.get_terminal_size(0)
            # ugh. the columns thing is meh. dunno I guess ultimately need curses for that
            # TODO also would be cool to have a terminal post-processor? kinda like tail but aware of logging keyworkds (INFO/DEBUG/etc)
            self.stream.write(msg + ' ' * max(0, columns - len(msg)) + ('' if cur else '\n'))
            self.flush()
        except:
            self.handleError(record)


if __name__ == '__main__':
    test()

'''
Just a helper for a more humane error message when importing my.* dependencies
'''

from ..common import logger

try:
    import my
except ImportError as e:
    logger.exception(e)
    logger.critical("Failed during 'import my'. You probably need to install & configure HPI package first (see 'https://github.com/karlicoss/HPI/blob/master/doc/SETUP.org')")

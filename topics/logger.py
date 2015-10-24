
import logging
import os
import re
import threading


_level = -1  # pylint: disable=C0103
_ldata = threading.local()  # pylint: disable=C0103


class Logger(object):
    """Provides the logging methods"""

    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET

    LEVEL_MAP = {
        0: CRITICAL,
        1: ERROR,
        2: WARNING,
        3: INFO,
        4: DEBUG,
        5: NOTSET
    }

    @staticmethod
    def set(verbose=None, level=None, name=None, newformat=None):
        global _level  # pylint: disable=C0103,W0603
        if verbose is None and _level < 0:
            krep_verbose = os.environ.get('KREP_VERBOSE', '')
            if re.match(r'-?\d+', krep_verbose):
                verbose = int(krep_verbose)

        if verbose is not None and verbose > -1:
            level = Logger.LEVEL_MAP.get(verbose, Logger.DEBUG)

        if newformat:
            logging.basicConfig(format=newformat, level=level)
        else:
            logging.basicConfig(format='%(name)s: %(message)s', level=level)

        if _level < 0 or (verbose > 0 and level < _level):
            _level = level or logging.ERROR

        if level is None:
            level = _level

        logger = Logger.get_logger(name or 'root')
        if level is not None:
            logger.setLevel(level)

        return logger

    @staticmethod
    def get_logger(name=None):
        if name:
            curr = threading.currentThread()
            # update the local data if the name is null or current thread is
            # the main thread, which is because the running job is 1.
            if not hasattr(_ldata, 'name') or curr.getName() == 'MainThread':
                _ldata.name = name
        else:
            if hasattr(_ldata, 'name'):
                name = _ldata.name

        if _level < 0:
            Logger.set()

        logger = logging.getLogger(name or 'root')
        if logger.getEffectiveLevel() > _level:
            logger.setLevel(_level)

        return logger


TOPIC_ENTRY = 'Logger'

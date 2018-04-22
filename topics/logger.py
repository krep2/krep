
import logging
import os
import re
import threading


_level = logging.ERROR  # pylint: disable=C0103
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
        0: ERROR,
        1: WARNING,
        2: INFO,
        3: DEBUG,
        4: NOTSET,
    }

    @staticmethod
    def set(verbose=0, level=0, name=None, newformat=None):
        global _level  # pylint: disable=C0103,W0603
        if level == 0:
            level = _level

        if verbose == 0:
            krep_verbose = os.environ.get('KREP_VERBOSE', '')
            if re.match(r'-?\d+', krep_verbose):
                verbose = int(krep_verbose)

        newlevel = Logger.LEVEL_MAP.get(verbose, Logger.DEBUG)
        if 0 <= newlevel <= level:
            level = newlevel
            if newlevel == 0:
                _level = newlevel

        if 0 < level < _level:
            _level = level

        if newformat:
            logging.basicConfig(format=newformat, level=_level)
        else:
            logging.basicConfig(format='%(name)s: %(message)s', level=_level)

        return Logger.get_logger(name, level=_level)

    @staticmethod
    def get_logger(name=None, level=0, verbose=0):
        if level == 0 and verbose > 0:
            level = Logger.LEVEL_MAP.get(verbose, Logger.NOTSET)

        if name is None and hasattr(_ldata, 'name'):
            name = _ldata.name

        if hasattr(_ldata, 'level'):
            oldlevel = _ldata.level
        else:
            oldlevel = _level

        if name and not hasattr(_ldata, 'name'):
            _ldata.name = name

        if level == 0:
            level = oldlevel

        if 0 <= level <= oldlevel:
            _ldata.level = level

        logger = logging.getLogger(name)
        if logger.getEffectiveLevel() > level > 0 or name is None:
            logger.setLevel(level)

        return logger


TOPIC_ENTRY = 'Logger'

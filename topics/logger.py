
import logging
import os
import re
import threading


_level = 0  # pylint: disable=C0103
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
        0: NOTSET,
        1: ERROR,
        2: WARNING,
        3: INFO,
        4: DEBUG
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
        if 0 < newlevel < level:
            level = newlevel

        if _level <= 0:
            if level > _level:
                _level = level
            else:
                _level = Logger.ERROR
        elif 0 < level < _level:
            _level = level

        if newformat:
            logging.basicConfig(format=newformat, level=level)
        else:
            logging.basicConfig(format='%(name)s: %(message)s', level=level)

        if _level < 0 or ((verbose or -1) > 0 and (level or -1) < _level):
            _level = level or logging.ERROR

        if level is None:
            level = _level

        logger = Logger.get_logger(name or 'root')
        logger.setLevel(level)

        return logger

    @staticmethod
    def get_logger(name=None, level=0, verbose=0):
        if _level < 0:
            Logger.set()

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

        if 0 <= level <= oldlevel:
            _ldata.level = level

        if level == 0:
            level = oldlevel

        logger = logging.getLogger(name or 'root')
        if logger.getEffectiveLevel() > level:
            logger.setLevel(level)

        return logger


TOPIC_ENTRY = 'Logger'


import logging
import threading


_ldata = threading.local()  # pylint: disable=C0103


class Logger(object):
    """Provides the logging methods"""
    @staticmethod
    def set(level=None, newformat=None):
        if newformat:
            logging.basicConfig(format=newformat, level=level)
        else:
            logging.basicConfig(format='%(name)s: %(message)s', level=level)

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

        return logging.getLogger(name or 'root')


TOPIC_ENTRY = 'Logger'

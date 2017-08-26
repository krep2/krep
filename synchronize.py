
import threading

def synchronized(func):
    func.__lock__ = threading.Lock()

    def synced_f(*args, **kws):
        with func.__lock__:
            return func(*args, **kws)

    return synced_f



class KrepError(Exception):
    """Root exception for krep"""


class OptionMissedError(KrepError):
    """Indicate the missed option."""


class RaiseExceptionIfOptionMissed(object):
    """Raise OptionMissedError if the option or options are missed."""
    def __init__(self, option, prompt):
        if not option:
            raise OptionMissedError(prompt)


TOPIC_ENTRY = 'KrepError, OptionMissedError, RaiseExceptionIfOptionMissed'

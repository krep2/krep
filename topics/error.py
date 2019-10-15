
class KrepError(Exception):
    """Root exception for krep"""


class HookError(KrepError):
    """Indicate a failed execution of hook."""


class OptionMissedError(KrepError):
    """Indicate the missed option."""


class ProcessingError(KrepError):
    """Indicate the unsuccessful processing."""


class AttributeNotFoundError(KrepError):
    """Indicate that the XML attribute isn't existed."""


class RaiseExceptionIfOptionMissed(object):
    """Raise OptionMissedError if the option or options are missed."""
    def __init__(self, option, prompt):
        if not option:
            raise OptionMissedError(prompt)


class RaiseExceptionIfAttributeNotFound(object):
    def __init__(self, flag, prompt):
        if flag:
            raise AttributeNotFoundError(prompt)


TOPIC_ENTRY = 'KrepError, AttributeNotFoundError HookError, ' \
              'OptionMissedError, ProcessingError, ' \
              'RaiseExceptionIfAttributeNotFound, RaiseExceptionIfOptionMissed'


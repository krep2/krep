
class KrepError(Exception):
    """Root exception for krep"""


class DownloadError(KrepError):
    """Indicate the unsuccessful download."""

class HookError(KrepError):
    """Indicate a failed execution of hook."""


class OptionMissedError(KrepError):
    """Indicate the missed option."""


class ProcessingError(KrepError):
    """Indicate the unsuccessful processing."""


class RepositoryNotFound(KrepError):
    """Indicate that the repository isn't existed."""


class RaiseExceptionIfOptionMissed(object):
    """Raise OptionMissedError if the option or options are missed."""
    def __init__(self, option, prompt):
        if not option:
            raise OptionMissedError(prompt)


TOPIC_ENTRY = 'KrepError, DownloadError, HookError, OptionMissedError, ' \
              'ProcessingError, RepositoryNotFound, ' \
              'RaiseExceptionIfOptionMissed'

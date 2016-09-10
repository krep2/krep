
import os


class ExecutableNotFoundError(Exception):
    """Indicate the executable not found."""


class FileUtils(object):
    """Utility to handle file operations."""
    @staticmethod
    def find_execute(program, exception=True):
        dirs = os.environ.get('PATH', '~/bin:/usr/bin:/bin/')
        for dname in dirs.split(':'):
            name = os.path.expanduser(os.path.join(dname, program))
            if os.path.exists(name):
                return name

        if exception:
            raise ExecutableNotFoundError('"%s" not found in PATH' % program)

        return None


TOPIC_ENTRY = 'ExecutableNotFoundError, FileUtils'

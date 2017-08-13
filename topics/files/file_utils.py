
import os
import shutil


class ExecutableNotFoundError(Exception):
    """Indicate the executable not found."""


class FileUtils(object):
    """Utility to handle file operations."""
    @staticmethod
    def find_execute(program, exception=True):
        dirs = os.environ.get(
            'PATH', os.pathsep.join(('~/bin', '/usr/bin', '/bin/')))
        for dname in dirs.split(os.pathsep):
            name = os.path.expanduser(os.path.join(dname, program))
            if os.path.exists(name):
                return name

        if exception:
            raise ExecutableNotFoundError('"%s" not found in PATH' % program)

        return None

    @staticmethod
    def ensure_path(dirname, subdir=None, prefix=None, exists=True):
        name = dirname
        if prefix and not name.startswith(prefix):
            name = prefix + name
        if subdir and os.path.basename(dirname) != subdir:
            name = os.path.join(name, subdir)

        if exists:
            return name if os.path.exists(name) else None
        else:
            return name

    @staticmethod
    def copy_file(src, dest):
        if os.path.islink(src):
            linkto = os.readlink(src)
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            elif os.path.lexists(dest):
                os.unlink(dest)

            os.symlink(linkto, dest)
        else:
            if os.path.isdir(dest):
                shutil.rmtree(dest)
            elif os.path.lexists(dest):
                os.unlink(dest)

            shutil.copy2(src, dest)


TOPIC_ENTRY = 'ExecutableNotFoundError, FileUtils'

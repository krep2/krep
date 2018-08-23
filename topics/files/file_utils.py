
import os
import re
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
    def secure_path(dirname):
        if dirname:
            dirname = re.sub(r"([^:]\/)\/+", "\\1", dirname.replace('\\', '/'))

        return dirname

    @staticmethod
    def ensure_path(dirname, subdir=None, prefix=None, exists=True):
        name = FileUtils.secure_path(dirname)
        if prefix and not name.startswith(prefix):
            name = prefix + name
        if subdir and os.path.basename(dirname) != subdir:
            name = os.path.join(name, subdir)

        if exists:
            return name if os.path.exists(name) else None
        else:
            return name

    @staticmethod
    def last_modified(path, recursive=True):
        def _modified_time(filename):
            if os.path.exists(filename):
                while os.path.islink(filename):
                    name = os.readlink(filename)
                    if not os.path.isabs(name):
                        name = os.path.join(os.path.dirname(filename), name)

                    if os.path.exists(name):
                        filename = name
                    else:
                        continue

                stat = os.lstat(filename)
                return stat.st_mtime
            else:
                return 0

        timestamp = _modified_time(path)
        if os.path.isdir(path) and recursive:
            timestamp = 0
            for root, _, files in os.walk(path):
                for name in files:
                    mtime = _modified_time(os.path.join(root, name))
                    if mtime > timestamp:
                        timestamp = mtime

        return timestamp

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

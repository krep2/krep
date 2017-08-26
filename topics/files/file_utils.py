
import os
import tempfile
import shutil

from dir_utils import AutoChangedDir
from topics.command import Command
from topics.error import KrepError


class ExecutableNotFoundError(KrepError):
    """Indicate the executable not found."""


class FileDecompressor(Command):
    COMMAND_FOR_EXTENSION = {
        '.tar.gz': {'p': ('tar', 'xzf')},
        '.tar.bz2': {'p': ('tar', 'xjf')},
        '.tgz': {'p': ('tar', 'xzf')},
        '.gz': {'p': ('gunzip', '--keep')},
        '.gzip': {'p': ('gunzip', '--keep')},
        '.bz2': {'p': ('bzip',)},
        '.zip': {'p': ('unzip',)},
        '.7z': {'p': ('p7zip', '-d'), 'duplicated': True},
    }

    def execute(self, filename):
        args = list()
        for ext, vals in FileDecompressor.COMMAND_FOR_EXTENSION.items():
            if filename.endswith(ext):
                args.extend(vals['p'])
                if 'duplicated' in vals:
                    tempname = tempfile.mktemp()
                    os.symlink(filename, tempname)
                    args.append(tempname)
                else:
                    args.append(filename)
                break
        else:
            raise ExecutableNotFoundError(
                '%s: Unknown extension "%s"' % (
                    filename, (os.path.split(filename))[1]))

        self.new_args(args)  # pylint: disable=E1101
        return self.wait()

    @staticmethod
    def extract(filename, output):
        decompressor = FileDecompressor()

        with AutoChangedDir(output, cleanup=False):
            decompressor.execute(filename)


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


    @staticmethod
    def extract_file(src, dest):
        FileDecompressor.extract(src, dest)


TOPIC_ENTRY = 'ExecutableNotFoundError, FileUtils'

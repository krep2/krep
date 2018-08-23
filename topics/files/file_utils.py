
import os
import re
import tempfile
import shutil

from dir_utils import AutoChangedDir
from topics.command import Command
from topics.error import KrepError


class ExecutableNotFoundError(KrepError):
    """Indicate the executable not found."""


class FileDecompressor(Command):

    COMMAND_FOR_EXTENSION = (
        ('.tar', ('tar', 'xf')),
        ('.tar.gz', ('tar', 'xzf')),
        ('.tar.bz2', ('tar', 'xjf')),
        ('.tar.xz', ('tar', 'xJf')),
        ('.tgz', ('tar', 'xzf')),
        ('.gz', ('gunzip', '--keep')),
        ('.gzip', ('gunzip', '--keep')),
        ('.bz2', ('bzip',)),
        ('.zip', ('unzip',)),
        ('.7z', ('p7zip', '-d'), ('keep',)),
        ('.xz', ('xz', '--keep')),
    )

    def execute(self, filename):
        args = list()
        for items in FileDecompressor.COMMAND_FOR_EXTENSION:
            if len(items) == 2:
                extends = list()
                ext, vals = items
            else:
                ext, vals, extends = items

            if filename.endswith(ext):
                args.extend(vals)
                if 'keep' in extends:
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
    def last_modifed(path):
        timestamp = 0
        for root, _, files in os.walk(path):
            for name in files:
                timest = os.lstat(os.path.join(root, name))
                if timest.st_mtime > timestamp:
                    timestamp = timest.st_mtime

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

    @staticmethod
    def rmtree(dest, ignore_list=None):
        for name in os.listdir(dest):
            matched = False
            if os.path.isdir(os.path.join(dest, name)):
                name += '/'

            for pattern in ignore_list or list():
                if re.match(pattern, name) is not None:
                    matched = True
                    break

            if matched:
                continue

            filename = os.path.join(dest, name)
            if os.path.isdir(filename):
                shutil.rmtree(filename)
            else:
                os.unlink(filename)

    @staticmethod
    def copy_files(src, dest, ignore_list=None):
        for name in os.listdir(src):
            matched = False
            for pattern in ignore_list or list():
                if re.match(pattern, name) is not None:
                    matched = True
                    break

            if matched:
                continue

            filename = os.path.join(src, name)
            if os.path.isdir(filename):
                shutil.copytree(
                    filename, os.path.join(dest, name), symlinks=True)
            else:
                FileUtils.copy_file(filename, os.path.join(dest, name))

    @staticmethod
    def extract_file(src, dest):
        FileDecompressor.extract(src, dest)


TOPIC_ENTRY = 'ExecutableNotFoundError, FileUtils'

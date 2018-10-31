
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
        (('.tgz', '.tar.gz'), ('tar', 'xzf')),
        ('.tar.bz2', ('tar', 'xjf')),
        ('.tar.xz', ('tar', 'xJf')),
        (('.gz', '.gzip'), ('gunzip', '--keep')),
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


class FileVersion(object):
    @staticmethod
    def cmp(va, vb):
        def _split(ver):
            return re.split('[-_\.]',  ver)

        def _cmp(vva, vvb):
            return (vva > vvb) - (vva < vvb)

        vsa = _split(va)
        vsb = _split(vb)

        for k in range(min(len(vsa), len(vsb))):
            maa = re.match(r'(?P<digit>\d+)(?P<patch>.*)', vsa[k])
            mab = re.match(r'(?P<digit>\d+)(?P<patch>.*)', vsb[k])
            if maa and mab:
                if maa.group('digit') != mab.group('digit'):
                    return _cmp(
                        int(maa.group('digit')), int(mab.group('digit')))

                paa, pab = maa.group('patch'), mab.group('patch')
                if paa != pab:
                    if not paa:
                        return 1
                    elif not pab:
                        return -1
                    else:
                        return _cmp(paa, pab)

            res = _cmp(vsa[k], vsb[k])
            if res != 0:
                return res

        return _cmp(len(vsa), len(vsb))


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
    def copy_file(src, dest, symlinks=False):
        destdir = os.path.dirname(dest)
        if not os.path.exists(destdir):
            os.makedirs(destdir)

        if symlinks and os.path.islink(src):
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
                # OS doesn't complain the trailing backslash, but patterns use
                # it to treat the name with trailing backslash as directories
                name += '/'

            for pattern in ignore_list or list():
                if re.match(pattern, name) is not None:
                    matched = True
                    break

            if matched:
                continue

            filename = os.path.join(dest, name)
            if os.path.isdir(filename):
                FileUtils.rmtree(filename, ignore_list=ignore_list)
            else:
                os.unlink(filename)

        if len(os.listdir(dest)) == 0:
            shutil.rmtree(dest)

    @staticmethod
    def copy_files(src, dest, ignore_list=None, symlinks=False):
        for name in os.listdir(src):
            matched = False
            for pattern in ignore_list or list():
                if re.match(pattern, name) is not None:
                    matched = True
                    break

            if matched:
                continue

            sname = os.path.join(src, name)
            dname = os.path.join(dest, name)
            if os.path.isdir(sname):
                dname = os.path.join(dest, name)
                if not os.path.exists(dname):
                    os.makedirs(dname)

                FileUtils.copy_files(
                    sname, dname, ignore_list=ignore_list, symlinks=symlinks)
            else:
                FileUtils.copy_file(sname, dname, symlinks=symlinks)

    @staticmethod
    def extract_file(src, dest):
        FileDecompressor.extract(src, dest)


TOPIC_ENTRY = 'ExecutableNotFoundError, FileUtils, FileVersion'

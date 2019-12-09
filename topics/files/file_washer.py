
import fnmatch
import os
import stat
import subprocess

try:
    import cStringIO as StringIO
except ImportError:
    import io as StringIO

try:
    import magic  # pylint: disable=F0401

    def _get_magic(filename):
        msc = magic.open(magic.NONE)
        msc.load()
        try:
            result = msc.file(filename)
        except UnicodeDecodeError:
            result = None
        finally:
            msc.close()

        return result
except ImportError:
    from file_utils import FileUtils

    filebin = FileUtils.find_execute('file')
    def _get_magic(filename):
        return subprocess.check_output([filebin, filename])


class FileMagic(object):
    EOL_NONE = 0
    EOL_UNIX = 1
    EOL_DOS = 2
    EOL_MAC = 3

    MAGIC_TEXT = 'ASCII text'

    @staticmethod
    def get_file_magic(filename):
        return _get_magic(filename)

    @staticmethod
    def contain_text_flag(magic_str):
        return magic_str and (
            magic_str.find(' text') > -1 or
            magic_str.find('line terminators') > 0)

    @staticmethod
    def is_text_file(filename):
        magic_str = FileMagic.get_file_magic(filename)
        return FileMagic.contain_text_flag(magic_str)

    @staticmethod
    def get_eof_of_text_file(filename):
        magic_str = FileMagic.get_file_magic(filename)
        if FileMagic.contain_text_flag(magic_str):
            if magic_str.find('CRLF'):
                return FileMagic.EOL_DOS
            elif magic_str.find('LF'):
                return FileMagic.EOL_MAC
            else:
                return FileMagic.EOL_UNIX

        return FileMagic.EOL_NONE


class FileWasher(object):  # pylint: disable=R0902
    """\
Supports to wash out the a text file or text files inside a directory.
    """

    LF = '\x0d'
    CR = '\x0a'
    CRLF = '\x0d\x0a'

    def __init__(self, default_pattern=None, patterns=None,
                 excluded=None, dryrun=False):
        self.dryrun = dryrun
        self.patterns = patterns or dict()
        self.excluded = excluded or list()
        self.defaultp = default_pattern

    @staticmethod
    def options(optparse, option_enabler=False, option_file=True):
        # Washer file options
        if option_file:
            options = optparse.add_option_group('Washer file options')
            if option_enabler:
                options.add_option(
                    '--washed',
                    dest='washed', action='store_true', default=False,
                    help='wash out files with activated washing options')
            options.add_option(
                '--keep-time',
                dest='keep_time', action='store_true', default=True,
                help='keep the washed file timestamp')
            options.add_option(
                '--keep-owner',
                dest='keep_owner', action='store_true', default=True,
                help='keep the washed file onwer')
            options.add_option(
                '--keep-file-mode',
                dest='keep_file_mode', action='store_true', default=True,
                help='keep the washed file mode')
            options.add_option(
                '--read-only',
                dest='read_only', action='store_true', default=False,
                help='wash even the file attribute is read-only')
            options.add_option(
                '--exclude-files',
                dest='excluded_files', action='append',
                help='set the files excluded to wash')

        # Washer line options
        options = optparse.add_option_group('Washer line options')
        options.add_option(
            '-E', '--eol',
            dest='eol', action='store',
            help='set to set EOL to DOS/MAC/UNIX format')
        options.add_option(
            '-L', '--skip-leading-tabs',
            dest='skip_leading_tabs', action='store_true', default=False,
            help='skip to convert the leading tabs')
        options.add_option(
            '-B', '--tab-to-space',
            dest='tab_to_space', action='store_true', default=False,
            help='convert tab to spaces')
        options.add_option(
            '-S', '--space-to-tab',
            dest='space_to_tab', action='store_true', default=False,
            help='convert spaces to tab')
        options.add_option(
            '-Z', '--tab-size',
            dest='tab_size', action='store', type='int', default=4,
            help='set the tab size to expand tab as space')
        options.add_option(
            '-M', '--trim-trailing-space',
            dest='trim_trailing_space', action='store_true', default=False,
            help='set to trim the trailing spaces')

    @staticmethod
    def default_pattern(optparse):
        FileWasher.options(optparse)

        return ['*', optparse.parse_args(list())]

    def wash(self, file_or_dir):
        updated = False
        if os.path.isdir(file_or_dir):
            for root, _, files in os.walk(file_or_dir):
                for name in files:
                    updated |= self._wash_file(os.path.join(root, name))
        elif os.path.isfile(file_or_dir):
            updated = self._wash_file(file_or_dir)
        else:
            raise IOError('cannot open %s' % file_or_dir)

        return updated

    def _wash_file(self, filename):  # pylint: disable=R0915
        def _eol(value):
            lvalue = (value or '').lower()
            if lvalue == 'unix':
                return FileMagic.EOL_UNIX
            elif lvalue == 'dos':
                return FileMagic.EOL_DOS
            elif lvalue == 'mac':
                return FileMagic.EOL_MAC
            else:
                return FileMagic.EOL_NONE

        if filename in self.excluded:
            return False
        else:
            for excluded in self.excluded:
                if fnmatch.fnmatch(filename, excluded):
                    return False

        opt = None
        for pattern, configs in self.patterns.items():
            if fnmatch.fnmatch(filename, pattern):
                opt = configs
                break
        else:
            opt = self.defaultp

        if opt is None:
            return False

        changed = False
        tabs = opt.tab_size > 0 and ' ' * opt.tab_size
        ret = FileMagic.get_eof_of_text_file(filename)
        if ret == FileMagic.EOL_NONE:
            return False

        sta = os.stat(filename)
        if not opt.read_only and \
                (sta.st_mode & stat.S_IWUSR) == 0:
            return False

        text = StringIO.StringIO()
        with open(filename, 'r') as fp:
            for origin in fp:
                line = origin
                has_eol = origin.endswith(FileWasher.LF) or \
                    origin.endswith(FileWasher.CR)

                if has_eol:
                    line = line.rstrip(FileWasher.CRLF)
                if opt.trim_trailing_space:
                    line = line.rstrip()

                if tabs:
                    alt = ''
                    if opt.skip_leading_tabs:
                        lln = len(line) - len(line.lstrip())
                        alt, line = line[:lln], line[lln:]

                    if opt.tab_to_space:
                        line = alt + line.replace('\t', tabs)
                    elif opt.space_to_tab:
                        line = alt + line.replace(tabs, '\t')

                if has_eol:
                    if opt.eol:
                        ret = _eol(opt.eol)

                    if ret == FileMagic.EOL_DOS:
                        line += FileWasher.CRLF
                    elif ret == FileMagic.EOL_MAC:
                        line += FileWasher.LF
                    else:  # ret == FileMagic.EOL_UNIX:
                        line += FileWasher.CR

                changed = changed or (origin != line)
                text.write(line)

        if not self.dryrun and changed:
            if (sta.st_mode & stat.S_IWUSR) == 0:
                os.chmod(filename, stat.S_IWUSR)

            with open(filename, 'wb') as fp:
                fp.write(text.getvalue())

            if opt.keep_file_mode:
                os.chmod(filename, sta.st_mode)

            if opt.keep_keep_owner:
                os.chown(filename, sta.st_uid, sta.st_gid)

            if opt.keep_time:
                os.utime(filename, (sta.st_atime, sta.st_mtime))

        text.close()
        return changed

TOPIC_ENTRY = 'FileWasher'

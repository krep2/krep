
import os
import re


class OppositeFail(Exception):
    pass


class FilePattern(object):
    def __init__(self, patterns=None):
        self.patterns = list(patterns or [])
        self.filep, self.dirp, self.others, self.fileop, \
            self.dirop, self.otheros = FilePattern._filter(patterns)

    def __iadd__(self, obj):
        if isinstance(obj, FilePattern):
            self.patterns.extend(obj.patterns)

            self.filep.extend(obj.filep)
            self.dirp.extend(obj.dirp)
            self.others.extend(obj.others)

            self.fileop.extend(obj.fileop)
            self.dirop.extend(obj.dirop)
            self.otheros.extend(obj.otheros)

        return self

    @staticmethod
    def _filter(patterns):
        files, dirs, others = list(), list(), list()
        fileos, diros, otheros = list(), list(), list()

        def _secure_name(pattern):
            segs = pattern.replace('//', '/').split('$/')
            name = segs.pop(0)
            for seg in segs:
                if name.endswith('\\'):
                    name += '\\$'

                if not name.endswith('/'):
                  name += '/'

                name += seg

            return name.replace('/^', '/')

        for pattern in patterns or list():
            opposite = False
            if pattern.startswith('!'):
                opposite = True
                pattern = pattern[1:]

            pattern = _secure_name(pattern)
            if pattern.endswith(('/', '/$')):
                if opposite:
                    diros.append(pattern)
                    otheros.append(_secure_name('%s/.?' % pattern))
                else:
                    dirs.append(pattern)
                    others.append(_secure_name('%s/.?' % pattern))
            elif pattern.find('/') > -1:
                if opposite:
                    otheros.append(pattern)
                else:
                    others.append(pattern)
            else:
                if opposite:
                    fileos.append(pattern)
                    otheros.append(pattern)
                else:
                    files.append(pattern)
                    others.append(pattern)

        return files, dirs, others, fileos, diros, otheros

    def get_patterns(self):
        return self.patterns

    def _match_file(self, filename):
        for pattern in self.fileop:
            if re.search(pattern, filename):
                raise OppositeFail("matched")

        for pattern in self.filep:
            if re.search(pattern, filename):
                return True

        return len(self.filep) == 0

    def _match_dir(self, dirname):
        dirname = dirname.rstrip('/') + '/'

        for pattern in self.dirop:
            if re.search(pattern, dirname):
                raise OppositeFail("matched")

        for pattern in self.dirp:
            if re.search(pattern, dirname):
                return True

        return len(self.dirp) == 0

    def _match_full(self, fullname):
        for pattern in self.otheros:
            if re.search(pattern, fullname):
                raise OppositeFail("matched")

        for pattern in self.others:
            if re.search(pattern, fullname):
                return True

        return len(self.others) == 0

    def has_file_rule(self):
        return len(self.filep) + len(self.fileop) > 0

    def has_dir_rule(self):
        return len(self.dirp) + len(self.dirop) > 0

    def match_file(self, filename):
        try:
            return self._match_file(filename)
        except OppositeFail:
            return False

    def match_dir(self, dirname):
        try:
            return self._match_dir(dirname)
        except OppositeFail:
            return False

    def match(self, fullname):
        try:
            if fullname.endswith('/'):
                return self._match_dir(fullname)
            else:
                return self._match_full(fullname)
        except OppositeFail:
            return False


class RepoFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'^\.repo/',                          # repo
    )

    def __init__(self):
        FilePattern.__init__(self, RepoFilePattern.FILTER_OUT_PATTERN)


class GitFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'^\.git/', r'\.gitignore',             # git
        r'^\.gitattributes',
    )

    def __init__(self):
        FilePattern.__init__(self, GitFilePattern.FILTER_OUT_PATTERN)


class SccsFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'CVS/', r'RCS/', r'\.cvsignore',       # CVS
        r'\.svn/',                              # subversion
        r'^\.hg/', r'\.hgignore', r'\.hgtags',  # mercurial
        r'^\.git/', r'\.gitignore',             # git
    )

    def __init__(self):
        FilePattern.__init__(self, SccsFilePattern.FILTER_OUT_PATTERN)

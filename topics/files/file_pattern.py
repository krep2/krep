
import os
import re


class FilePattern(object):
    def __init__(self, patterns=None):
        self.patterns = list(patterns or [])
        self.filep, self.dirp, self.others = FilePattern._filter(patterns)

    def __iadd__(self, obj):
        if isinstance(obj, FilePattern):
            self.patterns.extend(obj.patterns)

            self.filep.extend(obj.filep or list())
            self.dirp.extend(obj.dirp or list())
            self.others.extend(obj.others or list())

        return self

    @staticmethod
    def _filter(patterns):
        files, dirs, others = list(), list(), list()
        for pattern in patterns or list():
            if pattern.startswith('/') or pattern.endswith('/'):
                dirs.append(pattern.lstrip('/'))
                others.append('%s/.?' % pattern.rstrip('/'))
            elif pattern.find('/') > 0:
                others.append(pattern)
            else:
                files.append(pattern)

        return files, dirs, others

    def get_patterns(self):
        return self.patterns

    def match(self, fullname):
        if fullname.endswith('/'):
            return self.match_dir(fullname)
        else:
            dirname = os.path.dirname(fullname)
            filename = os.path.basename(fullname)
            return self.match_full(fullname) or \
                (self.match_file(filename) and self.match_dir(dirname))

    def match_file(self, filename):
        for pattern in self.filep:
            if re.search(pattern, filename):
                return True

        return False

    def match_dir(self, dirname):
        dirname = dirname.rstrip('/')
        for pattern in self.dirp:
            if re.search(pattern, dirname):
                return True

        return False

    def match_full(self, fullname):
        for pattern in self.others:
            if re.search(pattern, fullname):
                return True

        return False


class RepoFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'^\.repo/',                          # repo
    )

    def __init__(self):
        FilePattern.__init__(self, RepoFilePattern.FILTER_OUT_PATTERN)


class GitFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'^\.git/', r'\.gitignore',           # git
    )

    def __init__(self):
        FilePattern.__init__(self, GitFilePattern.FILTER_OUT_PATTERN)


class SccsFilePattern(FilePattern):
    FILTER_OUT_PATTERN = (
        r'^CVS/', r'^RCS/', r'^\.cvsignore',  # CVS
        r'\.svn/',                            # subversion
        r'^\.hg/', r'\.hgignore',             # mercurial
        r'^\.git/', r'\.gitignore',           # git
    )

    def __init__(self):
        FilePattern.__init__(self, SccsFilePattern.FILTER_OUT_PATTERN)

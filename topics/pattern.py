
import re

from logger import Logger


class PatternItem(object):
    """Contains the positive or opposite pattern items."""

    CATEGORY_DELIMITER = ':'
    PATTERN_DELIMITER = ','
    OPPOSITE_DELIMITER = '!'
    REPLACEMENT_DELIMITER = '~'

    def __init__(self, category, patterns=None, exclude=False):
        self.include = list()
        self.exclude = list()
        self.replacement = list()

        self.category = category
        if patterns:
            self.add(patterns, exclude)

    def __len__(self):
        return len(self.include) + len(self.exclude) + len(self.replacement)

    def __str__(self):
        patterns = self.include[:]
        patterns.extend(['%s%s' % (PatternItem.OPPOSITE_DELIMITER, e)
                         for e in self.exclude])
        if self.replacement:
            patterns.append(
                '%s%s%s%s%s' % (
                    PatternItem.REPLACEMENT_DELIMITER,
                    self.replacement[0],
                    PatternItem.REPLACEMENT_DELIMITER,
                    self.replacement[1],
                    PatternItem.REPLACEMENT_DELIMITER))

        return '%s%s%s' % (
            self.category, PatternItem.CATEGORY_DELIMITER,
            PatternItem.PATTERN_DELIMITER.join(patterns))

    @staticmethod
    def split(patterns):
        inc, exc, rep = list(), list(), list()

        for pattern in patterns.split(PatternItem.PATTERN_DELIMITER):
            pattern = pattern.strip()
            if pattern.startswith(PatternItem.REPLACEMENT_DELIMITER):
                items = re.split(PatternItem.REPLACEMENT_DELIMITER, pattern)
                if len(items) == 4:
                    rep = items[1:-1]
            elif pattern.startswith(PatternItem.OPPOSITE_DELIMITER):
                exc.append(pattern[1:])
            else:
                inc.append(pattern)

        return inc, exc, rep

    def add(self, patterns, exclude=False):
        inc, exc, rep = PatternItem.split(patterns)
        if exclude:
            inc, exc = exc, inc

        if inc:
            self.include.extend(inc)
        if exc:
            self.exclude.extend(exc)
        if rep:
            self.replacement = rep

    def match(self, patterns):
        for pattern in patterns.split(PatternItem.PATTERN_DELIMITER):
            opposite = pattern.startswith(PatternItem.OPPOSITE_DELIMITER)
            if opposite:
                pattern = pattern[1:]

            for i in self.include:
                if re.search(i, pattern) is not None:
                    return not opposite

            for e in self.exclude:
                if re.search(e, pattern) is not None:
                    return opposite

        return True

    def replace(self, value):
        if self.replacement:
            return re.sub(self.replacement[0], self.replacement[1], value)
        else:
            return value


class Pattern(object):
    """\
Contains pattern categories with the format CATEGORY:PATTERN,PATTERN.

A valid pattern could have the format in text like:

  CATEGORY:PATTERN[,PATTERN[,!PATTERN]]

Each category supports several patterns split with a comma. The exclamation
mark shows an opposite pattern which means to return the opposite result if
matching.
"""
    REPLACEMENT = ('rp', 'replace', 'replacement')

    def __init__(self, pattern=None):
        self.categories = dict()
        self.add(pattern)

    def __nozero__(self):
        return len(self.categories) > 0

    def __len__(self):
        return len(self.categories)

    @staticmethod
    def options(optparse):
        options = optparse.get_option_group('--job') or \
            optparse.add_option_group('Other options')
        options.add_option(
            '-p', '--pattern',
            dest='pattern', action='append',
            help='Set the patterns for the command')

    def add(self, patterns, exclude=False):
        if isinstance(patterns, (str, unicode)):
            patterns = [patterns]

        logger = Logger.get_logger('PATTERN')
        if isinstance(patterns, (list, tuple)):
            for pattern in patterns:
                if pattern.find(PatternItem.CATEGORY_DELIMITER) > 0:
                    name, value = pattern.split(
                        PatternItem.CATEGORY_DELIMITER, 1)
                    if name in self.categories:
                        self.categories[name].add(value, exclude)
                    else:
                        self.categories[name] = PatternItem(
                            name, value, exclude)
                else:
                    logger.error('unknown pattern string "%s"', pattern)
        elif patterns is not None:
            logger.error('unknown option "%s"', str(patterns))

    def get(self):
        return self.categories

    def match(self, categories, value):
        ret = False
        existed = False

        for category in categories.split(','):
            item = self.categories.get(category)
            if item:
                existed = True
                ret |= item.match(value)

        return ret if existed else True

    def replace(self, categories, value):
        item = None
        for category in categories.split(','):
            for replace in Pattern.REPLACEMENT:
                if category.endswith(replace):
                    item = self.categories.get(category)
                    break
            else:
                for replace in Pattern.REPLACEMENT:
                    item = self.categories.get('%s-%s' % (category, replace))
                    if item:
                        break

            if item:
                return item.replace(value)

        return value


TOPIC_ENTRY = 'Pattern'

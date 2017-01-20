
import re

from collections import namedtuple
from logger import Logger


PatternReplaceItem = namedtuple('PatternReplaceItem', 'pattern,subst')


class PatternItem(object):
    """Contains the positive or opposite pattern items."""

    CATEGORY_DELIMITER = ':'
    PATTERN_DELIMITER = ','
    OPPOSITE_DELIMITER = '!'
    ITEM_NAME_DELIMITER = '@'
    REPLACEMENT_DELIMITER = '~'

    def __init__(self, category, patterns=None, exclude=False, name=None):
        self.name = name
        self.include = list()
        self.exclude = list()
        self.subst = list()

        self.category = category
        if patterns:
            self.add(patterns, exclude)

    def __len__(self):
        return len(self.include) + len(self.exclude) + len(self.subst)

    def __str__(self):
        patterns = self.include[:]
        patterns.extend(['%s%s' % (PatternItem.OPPOSITE_DELIMITER, e)
                         for e in self.exclude])
        patterns.extend(
            ['%(d)s%(p)s%(d)s%(r)s%(d)s' % {
                'd': PatternItem.REPLACEMENT_DELIMITER,
                'p': rp.pattern,
                'r': rp.subst} for rp in self.subst])

        return '%s%s%s%s' % (
            '%s%s' % (self.name, PatternItem.ITEM_NAME_DELIMITER)
            if self.name else '',
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
                    rep.append(PatternReplaceItem(items[1], items[2]))
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
            self.subst.extend(rep)

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

            if len(self.include) > 0:
                return opposite
            elif len(self.exclude) > 0:
                return not opposite

        return True

    def replace(self, value):
        if self.subst:
            for rep in self.subst:
                value = re.sub(rep.pattern, rep.subst, value)

        return value



class Pattern(object):
    """\
Contains pattern categories with the format CATEGORY:PATTERN,PATTERN.

A valid pattern could have the format in text like:

  CATEGORY:PATTERN[,NAME@PATTERN[,!PATTERN,[!NAME@PATTERN[,~PATTERN~REPLACE~]]]]

Each category supports several patterns split with a comma. The exclamation
mark shows an opposite pattern which means to return the opposite result if
matching.
"""
    REPLACEMENT = ('rp', 'replace', 'replacement')

    def __init__(self, pattern=None):
        self.orders = dict()
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

    def _ensure_item(self, category, name):
        if category in self.categories:
            items = self.categories[category]
            if name in items:
                return items[name]

            for pattern in self.orders[category]:
                if pattern is not None and name:
                    if re.search(pattern, name) is not None:
                        return items[pattern]

            return items.get(None)

        return None

    def add(self, patterns, exclude=False):  # pylint: disable=R0912
        if isinstance(patterns, (str, unicode)):
            patterns = [patterns]

        logger = Logger.get_logger('PATTERN')
        if isinstance(patterns, (list, tuple)):
            for pattern in patterns:
                if pattern.find(PatternItem.CATEGORY_DELIMITER) > 0:
                    category, value = pattern.split(
                        PatternItem.CATEGORY_DELIMITER, 1)

                    if value.find(PatternItem.ITEM_NAME_DELIMITER) > 0:
                        name, value = value.split(
                            PatternItem.ITEM_NAME_DELIMITER, 1)
                    else:
                        name = None

                    if category not in self.categories:
                        self.orders[category] = list()
                        self.categories[category] = dict()

                    item = self._ensure_item(category, name)
                    if item:
                        item.add(value, exclude)
                    else:
                        self.orders[category].append(name)
                        self.categories[category][name] = PatternItem(
                            category, value, exclude, name=name)
                else:
                    logger.error('unknown pattern string "%s"', pattern)
        elif isinstance(patterns, dict):
            for category, pattern in patterns:
                if category not in self.categories:
                    self.orders[category] = list()
                    self.categories[category] = dict()

                for item in pattern:
                    self.orders[category].append(item.name)
                    self.categories[category][item.name] = item
        elif patterns is not None:
            logger.error('unknown option "%s"', str(patterns))

    def get(self):
        return self.categories

    def match(self, categories, value, name=None):
        ret = False
        existed = False

        for category in categories.split(','):
            item = self._ensure_item(category, name)
            if item:
                existed = True
                ret |= item.match(value)

        return ret if existed else True

    def replace(self, categories, value, name=None):
        for category in categories.split(','):
            item = None
            for replace in Pattern.REPLACEMENT:
                if category.endswith(replace):
                    item = self._ensure_item(category, name)
                    if item:
                        break
            else:
                for replace in Pattern.REPLACEMENT:
                    item = self._ensure_item(
                        '%s-%s' % (category, replace), name)
                    if item:
                        break

            if item:
                return item.replace(value)

        return value


TOPIC_ENTRY = 'Pattern'

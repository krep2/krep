
import re
import xml.dom.minidom

from collections import namedtuple
from error import KrepError
from logger import Logger


PatternReplaceItem = namedtuple('PatternReplaceItem', 'pattern,subst,cont')


class XmlError(KrepError):
    pass


def _normalize_regex(val):
    if val:
        if val.startswith('^'):
            val = val[1:]
        if val.endswith('$'):
            val = val[:-1]

    return val


def _secure_split(val, delimiter, num=0):
    ret = val.split(delimiter)

    k = 0
    while k < len(ret) - 1:
        # support \\\@ as \@ when @ is a delimiter
        if ret[k].endswith('\\\\\\'):
            ret[k] = ret[k][:-1]
        elif ret[k].endswith('\\\\'):
            ret[k] = ret[k][:-1]
            k += 1

            continue

        if ret[k].endswith('\\'):
            ret[k] = ret[k][:-1] + delimiter + ret[k + 1]
            del ret[k + 1]
        else:
            k += 1

    if num and len(ret) > num + 1:
        ret[num] = delimiter.join(ret[num:])
        del ret[num + 1:]

    return ret


class PatternItem(object):
    """Contains the positive or opposite pattern items."""

    REPLACEMENT = ('-rp', '-replace', '-replacement')

    CATEGORY_DELIMITER = ':'
    PATTERN_DELIMITER = ','
    OPPOSITE_DELIMITER = '!'
    ITEM_NAME_DELIMITER = '@'
    REPLACEMENT_DELIMITER = '~'
    CONN_REPLACE_DELIMITER = '='

    def __init__(self, category, patterns=None,  # pylint: disable=R0913
                 exclude=False, name=None, cont=False):
        self.name = name
        self.cont = cont
        self.repcont = False
        self.include = list()
        self.exclude = list()
        self.subst = list()

        self.category = category
        if patterns:
            self.add(patterns, exclude=exclude)

    def __len__(self):
        return len(self.include) + len(self.exclude) + len(self.subst)

    def __str__(self):
        patterns = self.include[:]
        patterns.extend(['%s%s' % (PatternItem.OPPOSITE_DELIMITER, e)
                         for e in self.exclude])
        patterns.extend(
            ['%(d)s%(p)s%(d)s%(r)s%(d)s' % {
                'd': PatternItem.CONN_REPLACE_DELIMITER if rp.cont else \
                     PatternItem.REPLACEMENT_DELIMITER,
                'p': rp.pattern or '',
                'r': rp.subst or ''} for rp in self.subst])

        return '%s%s%s' % (
            ('%s%s' % (self.category, PatternItem.CATEGORY_DELIMITER)
             if self.category else ''),
            ('%s%s' % (self.name, PatternItem.ITEM_NAME_DELIMITER)
             if self.name else ''),
            PatternItem.PATTERN_DELIMITER.join(patterns))

    @staticmethod
    def ensure_category(name):
        for replace in PatternItem.REPLACEMENT:
            if name and name.endswith(replace):
                return name[:-len(replace)]

        return name

    @staticmethod
    def is_replace_str(value):
        if value and (
                value.startswith(PatternItem.CONN_REPLACE_DELIMITER) or
                value.startswith(PatternItem.REPLACEMENT_DELIMITER)):
            pattern1 = '%(p)s[^%(p)s]*%(p)s[^%(p)s]*%(p)s' % {
                'p': PatternItem.CONN_REPLACE_DELIMITER}
            pattern2 = '%(p)s[^%(p)s]*%(p)s[^%(p)s]*%(p)s' % {
                'p': PatternItem.REPLACEMENT_DELIMITER}

            if re.match(pattern1, value):
                return True
            elif re.match(pattern2, value):
                return True

        return False

    def replacable(self):
        return len(self.subst) > 0

    def replacable_only(self):
        return len(self.subst) > 0 and len(self.include) == 0 \
            and len(self.exclude) == 0

    def continuable(self):
        if len(self.subst) > 1:
            return self.cont
        else:
            return self.cont or self.repcont

    def split(self, patterns, cont=None):
        inc, exc, rep = list(), list(), list()
        patterns = patterns.strip()

        for pattern in _secure_split(patterns, PatternItem.PATTERN_DELIMITER):
            pattern = pattern.strip()
            if PatternItem.is_replace_str(pattern):
                items = re.split(pattern[0], pattern)
                if len(items) == 4:
                    rep.append(  # pylint: disable=E1103
                        PatternReplaceItem(
                            items[1] or self.name, items[2],
                            cont if cont is not None else (
                                self.cont or
                                pattern.startswith(
                                    PatternItem.CONN_REPLACE_DELIMITER))))
            elif pattern.startswith(PatternItem.OPPOSITE_DELIMITER):
                exc.append(pattern[1:])
            elif pattern:
                inc.append(pattern)

        return inc, exc, rep

    def add(self, patterns='', exclude=False,  # pylint: disable=R0913
            subst=None, pattern=None, cont=None):
        inc, exc, rep = self.split(patterns, cont)
        if exclude:
            inc, exc = exc, inc

        if inc:
            self.include.extend(inc)
        if exc:
            self.exclude.extend(exc)
        if rep:
            self.subst.extend(rep)
        if isinstance(subst, PatternReplaceItem):
            self.subst.append(subst)

        if pattern:
            self.include.extend(pattern.include)
            self.exclude.extend(pattern.exclude)
            self.subst.extend(pattern.subst)

    def match(self, patterns, strict=False):  # pylint: disable=R0911
        for pattern in _secure_split(patterns, PatternItem.PATTERN_DELIMITER):
            opposite = pattern.startswith(PatternItem.OPPOSITE_DELIMITER)
            if opposite:
                pattern = pattern[1:]

            npattern = _normalize_regex(pattern)
            for i in self.include:
                if strict:
                    if _normalize_regex(i) == npattern:
                        return not opposite
                elif re.search(i, pattern) is not None:
                    return not opposite

            for e in self.exclude:
                if strict:
                    if _normalize_regex(e) == npattern:
                        return opposite
                elif re.search(e, pattern) is not None:
                    return opposite

            if len(self.include) > 0:
                return opposite
            elif len(self.exclude) > 0:
                return not opposite

        return True

    def replace(self, value, strict=False):
        if self.subst:
            for rep in self.subst:
                ovalue = value
                if strict:
                    value = _normalize_regex(value).replace(
                        rep.pattern, rep.subst)
                else:
                    value = re.sub(rep.pattern, rep.subst, value)

                if ovalue != value:
                    self.repcont = rep.cont

                if ovalue != value and not rep.cont:
                    break

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

    def __init__(self, pattern=None, pattern_file=None, aliases=None):
        self.orders = dict()
        self.categories = dict()
        self.aliases = dict()

        self.add_alias(aliases)
        self.add(pattern)

    def __nozero__(self):
        return len(self.categories) > 0

    def __len__(self):
        return len(self.categories)

    def __add__(self, val):
        self.add(val)

        return self

    def __str__(self):
        val = '<Pattern - %r' % self
        for pattern in sorted(self.categories.keys()):
            items = self.categories[pattern]
            val += '\n %s = {\n' % pattern
            for name in self.orders[pattern]:
                val += '   %s : %s\n' % (name, items[name])
            val += ' },'

        if len(self.categories):
            val = val[:-1] + '\n'

        val += '>\n'

        return val

    @staticmethod
    def options(optparse):
        options = optparse.get_option_group('--working-dir') or \
            optparse.add_option_group('Global file options')
        options.add_option(
            '--pattern-file',
            dest='pattern_file', action='store',
            help='Set the pattern file in XML format for patterns')

        options = optparse.get_option_group('--force') or \
            optparse.add_option_group('Global other options')
        options.add_option(
            '-p', '--pattern',
            dest='pattern', action='append',
            help='Set the patterns for the command')

    def add_alias(self, aliases):
        for alias in aliases or list():
            vals = _secure_split(alias, PatternItem.PATTERN_DELIMITER)
            for val in vals[:]:
                category = self._detect_category(val)
                if category != val:
                    vals.remove(val)

            if len(vals):
                name, categories = vals[0], vals[1:]
                if name not in self.aliases:
                    self.aliases[name] = list()

                self.aliases[name] = list(set(self.aliases[name] + categories))

        categories = self.categories.keys()
        for category in categories:
            newc = self._detect_category(category)
            if newc != category:
                pattern = self.remove(cacetegory)
                if pattern:
                    self.add({newc: pattern})

    def _detect_category(self, category):
        for name, aliases in self.aliases.items():
            if name == category or category in aliases:
                return name

        return category

    def _ensure_item(self, category, name, strict=False):
        category = PatternItem.ensure_category(category)
        if category in self.categories:
            items = self.categories[category]
            if name in items:
                return items[name]

            if not strict:
                for pattern in self.orders[category]:
                    if pattern is not None and name:
                        if re.search(pattern, name) is not None:
                            return items[pattern]

                return items.get(None)

        return None

    def add(self, patterns, exclude=False):  # pylint: disable=R0912
        if isinstance(patterns, str):
            patterns = [patterns]

        logger = Logger.get_logger('PATTERN')
        if isinstance(patterns, (list, tuple)):
            for pattern in patterns:
                sli = _secure_split(pattern, PatternItem.CATEGORY_DELIMITER, 1)
                if len(sli) == 2:
                    category, value = sli
                    sli = _secure_split(
                        value, PatternItem.ITEM_NAME_DELIMITER, 1)
                    if len(sli) == 2:
                        name, value = sli
                    else:
                        name = None
                        value = sli[0]

                    category = self._detect_category(
                        PatternItem.ensure_category(category))
                    if category not in self.categories:
                        self.orders[category] = list()
                        self.categories[category] = dict()

                    item = self._ensure_item(category, name, strict=True)
                    if item:
                        item.add(value, exclude)
                    else:
                        self.orders[category].append(name)
                        self.categories[category][name] = PatternItem(
                            category, value, exclude, name=name)
                else:
                    logger.error('unknown pattern string "%s"', pattern)
        elif isinstance(patterns, dict):
            for category, pattern in patterns.items():  # pylint: disable=E1103
                category = self._detect_category(
                    PatternItem.ensure_category(category))
                if category not in self.categories:
                    self.orders[category] = list()
                    self.categories[category] = dict()

                for item in pattern:
                    self.orders[category].append(item.name)
                    self.categories[category][item.name] = item
        elif isinstance(patterns, Pattern):
            for key, orders in patterns.orders.items():  # pylint: disable=E1103
                if key in self.orders:
                    self.orders[key].extend(orders)
                else:
                    self.orders[key] = orders

            for key, categories in patterns.categories.items():  # pylint: disable=E1103
                if key in self.categories:
                    for category, item in categories.items():
                        category = self._detect_category(
                            PatternItem.ensure_category(category))
                        if category in self.categories[key]:
                            self.categories[key][category].add(pattern=item)
                        else:
                            self.categories[key][category] = item
                else:
                    self.categories[key] = categories
        elif patterns is not None:
            logger.error('unknown option "%s"', str(patterns))

    def remove(self, category):
        if category in self.categories:
            pattern = self.categories[category]
            del self.orders[category]
            del self.categories[category]

            return pattern
        else:
            return None

    def get(self):
        return self.categories

    def has_category(self, categories):
        for category in _secure_split(
                categories, PatternItem.PATTERN_DELIMITER):
            if category in self.categories:
                return True

        return False

    def match(self, categories, value, name=None, strict=False):
        ret = False
        existed = False

        for category in _secure_split(
                categories, PatternItem.PATTERN_DELIMITER):
            item = self._ensure_item(category, name)
            if item and not item.replacable_only():
                existed = True
                ret |= item.match(value, strict=strict)

        if not existed and name is None:
            for category in _secure_split(
                    categories, PatternItem.PATTERN_DELIMITER):
                item = self._ensure_item(category, value)
                if item and not item.replacable_only():
                    existed = True
                    ret |= item.match(value, strict=strict)

        return ret if existed else True

    def replace(self, categories, value, name=None, strict=False):
        replaced = False

        for category in _secure_split(
                categories, PatternItem.PATTERN_DELIMITER):
            category = PatternItem.ensure_category(category)
            if category in self.categories:
                items = self.categories[category]
                for pattern in self.orders[category]:
                    if pattern and name and (
                            (strict and name == pattern) or
                            (not strict and re.search(pattern, name)) or (
                                replaced and re.search(pattern, value))):
                        item = items[pattern]
                        if not item.replacable():
                            continue

                        value, ovalue = item.replace(value, strict), value
                        if value != ovalue:
                            replaced = True
                        if replaced and not item.continuable():
                            return value


            if not replaced:
                item = self._ensure_item(category, name)
                if item and item.replacable():
                    return item.replace(value)

        return value

    def can_replace(self, categories, values, name=None):
        for value in values or list():
            newvalue = self.replace(categories, value, name)
            if newvalue != value:
                return True

        return False


TOPIC_ENTRY = 'Pattern'

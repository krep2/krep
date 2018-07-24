
import re
import xml.dom.minidom

from collections import namedtuple
from error import KrepError
from logger import Logger


PatternReplaceItem = namedtuple('PatternReplaceItem', 'pattern,subst,cont')


class XmlError(KrepError):
    pass


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

    def __init__(self, category, patterns=None, exclude=False,
                 name=None, cont=False):
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
                    rep.append(
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

    def match(self, patterns):
        for pattern in _secure_split(patterns, PatternItem.PATTERN_DELIMITER):
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
                ovalue, value = value, re.sub(rep.pattern, rep.subst, value)
                if ovalue != value:
                    self.repcont = rep.cont

                if ovalue != value and not rep.cont:
                    break

        return value


def _attr(node, attribute, default=None):
    return node.getAttribute(attribute) or default


class PatternFile(object):  # pylint: disable=R0903
    _XmlPattern = namedtuple(
        '_XmlPattern', 'category,name,value,replacement,cont')

    @staticmethod
    def parse_pattern(node, patterns=None, exclude=False, replacement=False):
        if node.nodeName not in (
                'pattern', 'exclude-pattern', 'rp-pattern', 'replace-pattern'):
            return None

        def _ensure_bool(value):
            if value is None:
                return None
            else:
                value = value.lower()
                if value in ('true', 'yes'):
                    return True
                elif value in ('false', 'no'):
                    return False

            return None

        is_exc = exclude or node.nodeName == 'exclude-pattern'
        is_rep = replacement or \
            node.nodeName in ('rp-pattern', 'replace-pattern')
        p = PatternFile._XmlPattern(
            name=_attr(node, 'name') if not is_exc else \
                (None if not _attr(node, 'value') else _attr(node, 'name')),
            category=_attr(node, 'category', patterns and patterns.category),
            value=_attr(node, 'name') or _attr(node, 'value') \
                if is_rep else _attr(node, 'value') or _attr(node, 'name'),
            replacement=_attr(node, 'replace') or _attr(node, 'value') \
                if is_rep else None,
            cont=_ensure_bool(
                _attr(node, 'continue', patterns and patterns.cont)))

        if p.replacement is not None:
            if PatternItem.is_replace_str(p.replacement):
                pi = PatternItem(
                    category=p.category, patterns=p.replacement, name=p.name,
                    cont=p.cont)
            else:
                pi = PatternItem(category=p.category, name=p.name)
                pi.add(
                    subst=PatternReplaceItem(
                        p.value, p.replacement, p.cont == True))
        elif not PatternItem.is_replace_str(p.value):
            pi = PatternItem(category=p.category, name=p.name)
            pi.add(
                p.value, exclude=(
                    exclude or node.nodeName == 'exclude-pattern'))
        else:
            pi = PatternItem(
                category=p.category, patterns=p.value,
                name=p.name,
                exclude=exclude or node.nodeName == 'exclude-pattern',
                cont=p.cont)

        return pi

    @staticmethod
    def parse_pattern_str(node, patterns=None):
        p = PatternFile.parse_pattern(node, patterns)
        return str(p) if p else ''

    @staticmethod
    def parse_patterns(node):
        patterns = list()

        if node.nodeName in (
                'patterns', 'exclude-patterns', 'rp-patterns',
                'replace-patterns'):
            parent = PatternFile._XmlPattern(
                name=_attr(node, 'name'),
                category=_attr(node, 'category'),
                value=None,
                replacement=node.nodeName in (
                    'rp-patterns', 'replace-patterns'),
                cont=_attr(node, 'continue', 'false'))

            for child in node.childNodes:
                pi = PatternFile.parse_pattern(
                    child, parent,
                    exclude=node.nodeName == 'exclude-patterns',
                    replacement=parent.replacement)
                if pi:
                    patterns.append(pi)

        return patterns

    @staticmethod
    def parse_patterns_str(node):
        lists = list()
        patterns = PatternFile.parse_patterns(node)

        for pi in patterns:
            lists.append(str(pi))

        return lists

    @staticmethod
    def load(filename):
        patterns = dict()

        logger = Logger.get_logger('PATTERN')

        try:
            root = xml.dom.minidom.parse(filename)
        except (OSError, xml.parsers.expat.ExpatError):
            logger.error('error to parse pattern file %s', filename)
            return

        if not root or not root.childNodes:
            logger.error('manifest has no root')
            return

        if root.nodeName != 'patterns':
            logger.error('root name should be patterns')
            return

        for node in root.childNodes:
            if node.nodeName in (
                    'patterns', 'exclude-patterns', 'replace-patterns'):
                for pi in PatternFile.parse_patterns(node):
                    if pi.category not in patterns:
                        patterns[pi.category] = list()

                    patterns[pi.category].append(pi)

        return patterns


class Pattern(object):
    """\
Contains pattern categories with the format CATEGORY:PATTERN,PATTERN.

A valid pattern could have the format in text like:

  CATEGORY:PATTERN[,NAME@PATTERN[,!PATTERN,[!NAME@PATTERN[,~PATTERN~REPLACE~]]]]

Each category supports several patterns split with a comma. The exclamation
mark shows an opposite pattern which means to return the opposite result if
matching.
"""

    def __init__(self, pattern=None, pattern_file=None):
        self.orders = dict()
        self.categories = dict()
        self.add(pattern)
        self.load(pattern_file)

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
        options = optparse.get_option_group('--job') or \
            optparse.add_option_group('Other options')
        options.add_option(
            '-p', '--pattern',
            dest='pattern', action='append',
            help='Set the patterns for the command')
        options.add_option(
            '--pattern-file',
            dest='pattern_file', action='store',
            help='Set the pattern file in XML format for patterns')

    def _ensure_item(self, category, name, strict=False):
        category = PatternItem.ensure_category(category)
        if category in self.categories:
            items = self.categories[category]
            if name in items:
                return items[name]

            for pattern in self.orders[category]:
                if pattern is not None and name:
                    if not strict and re.search(pattern, name) is not None:
                        return items[pattern]

            if not strict:
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

                    category = PatternItem.ensure_category(category)
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
                        if category in self.categories[key]:
                            self.categories[key][category].add(pattern=item)
                        else:
                            self.categories[key][category] = item
                else:
                    self.categories[key] = categories
        elif patterns is not None:
            logger.error('unknown option "%s"', str(patterns))

    def load(self, pattern_file):
        if pattern_file:
            self.add(PatternFile.load(pattern_file))

    def get(self):
        return self.categories

    def match(self, categories, value, name=None):
        ret = False
        existed = False

        for category in _secure_split(
                categories, PatternItem.PATTERN_DELIMITER):
            item = self._ensure_item(category, name)
            if item and not item.replacable_only():
                existed = True
                ret |= item.match(value)

        if not existed and name is None:
            for category in _secure_split(
                    categories, PatternItem.PATTERN_DELIMITER):
                item = self._ensure_item(category, value)
                if item and not item.replacable_only():
                    existed = True
                    ret |= item.match(value)

        return ret if existed else True

    def replace(self, categories, value, name=None):
        replaced = False

        for category in _secure_split(
                categories, PatternItem.PATTERN_DELIMITER):
            category = PatternItem.ensure_category(category)
            if category in self.categories:
                items = self.categories[category]
                for pattern in self.orders[category]:
                    if pattern and name and (
                            re.search(pattern, name) or (
                                replaced and re.search(pattern, value))):
                        item = items[pattern]
                        if not item.replacable():
                            continue

                        value, ovalue = item.replace(value), value
                        if value != ovalue:
                            replaced = True
                        if replaced and not item.continuable():
                            return value


            if not replaced:
                item = self._ensure_item(category, name)
                if item and item.replacable():
                    return item.replace(value)

        return value


TOPIC_ENTRY = 'Pattern'

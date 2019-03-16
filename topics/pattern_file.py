
from collections import namedtuple

from config_file import XmlConfigFile
from options import Values
from pattern import PatternItem, PatternReplaceItem


class PatternFile(XmlConfigFile):  # pylint: disable=R0903
    KNOWN_PATTERN = (
        'pattern', 'exclude-pattern', 'rp-pattern', 'replace-pattern')
    KNOWN_PATTERNS = (
        'patterns', 'exclude-patterns', 'rp-patterns', 'replace-patterns')

    _XmlPattern = namedtuple(
        '_XmlPattern', 'category,name,value,replacement,cont')

    def parse_pattern_node(
            self, node, patterns=None, exclude=False, replacement=False):
        if node.nodeName not in PatternFile.KNOWN_PATTERN:
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
            name=self.get_var_attr(node, 'name') if not is_exc else \
                (None if not self.get_var_attr(node, 'value') else
                 self.get_var_attr(node, 'name')),
            category=self.get_var_attr(
                node, 'category', patterns and patterns.category),
            value=self.get_var_attr(node, 'name') or \
                self.get_var_attr(node, 'value') \
                if is_rep else self.get_var_attr(node, 'value') or \
                self.get_var_attr(node, 'name'),
            replacement=self.get_var_attr(node, 'replace') or \
                self.get_var_attr(node, 'value') if is_rep else None,
            cont=_ensure_bool(
                self.get_var_attr(
                    node, 'continue', patterns and patterns.cont)))

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

    def parse_patterns_node(self, node):
        patterns = list()

        if node.nodeName in PatternFile.KNOWN_PATTERNS:
            parent = PatternFile._XmlPattern(
                name=self.get_var_attr(node, 'name'),
                category=self.get_var_attr(node, 'category'),
                value=None,
                replacement=node.nodeName in (
                    'rp-patterns', 'replace-patterns'),
                cont=self.get_var_attr(node, 'continue', 'false'))

            for child in node.childNodes:
                if child.nodeName in PatternFile.KNOWN_PATTERNS:
                    patterns.extend(self.parse_patterns_node(child))
                elif child.nodeName in PatternFile.KNOWN_PATTERN:
                    pi = self.parse_pattern_node(
                        child, parent,
                        exclude=node.nodeName == 'exclude-patterns',
                        replacement=parent.replacement)
                    if pi:
                        patterns.append(pi)

        return patterns

    def parse_patterns(self, node, config=None):
        if config is None:
            config = Values()

        if node.nodeName in PatternFile.KNOWN_PATTERNS:
            self.set_attr(config, 'pattern', [])
            patterns = self.parse_patterns_node(node)
            for pattern in patterns:
                self.set_attr(config, 'pattern', str(pattern))
        elif node.nodeName in PatternFile.KNOWN_PATTERN:
            self.set_attr(config, 'pattern', [])
            pattern = self.parse_pattern_node(node)
            self.set_attr(config, 'pattern', str(pattern or ''))

        return config

    def parse(self, node, pi=None):  # pylint: disable=R0914
        if node.nodeName in PatternFile.KNOWN_PATTERNS or \
                node.nodeName in PatternFile.KNOWN_PATTERN:
            cfg = self._new_value(XmlConfigFile.FILE_PREFIX)
            self.parse_patterns(node, cfg)
        else:
            XmlConfigFile.parse(self, node, pi)

    @staticmethod
    def load(filename):
        cfg = PatternFile(filename)
        val = cfg.get_value(XmlConfigFile.FILE_PREFIX)

        if val:
            return val.pattern  # pylint: disable=E1103
        else:
            return None

TOPIC_ENTRY = 'PatternFile'

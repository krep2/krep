
import json
import os
import re
import xml.dom.minidom

from error import ProcessingError
from options import Values
from pattern import PatternFile


def _setattr(obj, name, value):
    values = None

    name = name.replace('-', '_')
    if hasattr(obj, name):
        values = getattr(obj, name)
        if values and not isinstance(values, list):
            values = [values]

    if values is not None:
        if isinstance(value, (list, tuple)):
            values.extend(value)
        else:
            values.append(value)
    else:
        values = value

    setattr(obj, name, values)


class _ConfigFile(object):
    DEFAULT_CONFIG = '#%^(DEFAULT%%_'
    PATTERN_PREFIX = 'pattern'
    PROJECT_PREFIX = 'project'
    LOCATION_PREFIX = 'location'
    FILE_PREFIX = 'file'
    HOOK_PREFIX = "hook"

    def __init__(self, filename=None):
        self.vals = dict()
        self.filename = os.path.realpath(filename)

    def _new_value(self, name, vals=None):
        val = vals or Values()
        if name not in self.vals:
            self.vals[name] = val
        else:
            if not isinstance(self.vals[name], list):
                self.vals[name] = [self.vals[name]]

            self.vals[name].append(val)

        return val

    @staticmethod
    def _build_name(section=None, subsection=None):
        name = ''
        if section:
            name = '%s.' % str(section)
        if subsection:
            name += '%s.' % str(subsection)

        return name.rstrip('.')

    @staticmethod
    def get_section_name(name):
        names = name.split('.')
        if len(names) > 0:
            return names[0]
        else:
            return None

    @staticmethod
    def get_subsection_name(name):
        names = name.split('.')
        if len(names) > 1:
            return names[1]
        else:
            return None

    def join(self, vals):
        for key, val in vals.items():
            if key not in self.vals:
                self.vals[key] = val

    def read(self):
        content = ''
        with open(self.filename, 'r') as fp:
            content = '\n'.join(fp.readlines())

        return content

    def get_default(self):
        default = self.get_values(_ConfigFile.DEFAULT_CONFIG)
        if default:
            return default[0]
        else:
            return Values()

    def get_names(self, section=None, subsection=None):
        vals = list()
        sname = self._build_name(section, subsection)
        if sname:
            for key, value in self.vals.items():
                if section != _ConfigFile.FILE_PREFIX and \
                        isinstance(value, _ConfigFile):
                    vals.extend(value.get_names(section, subsection))
                elif key.startswith(sname):
                    vals.append(key)
        else:
            vals.extend(self.vals.keys())

        return vals

    def get_value(self, section, subsection=None, name=None):
        vals = self.get_values(section, subsection)
        if vals:
            if isinstance(vals, list):
                if name:
                    return getattr(vals[0], name)
                else:
                    return vals[0]

        return vals

    def get_values(self, section=None, subsection=None):
        sname = self._build_name(section, subsection)

        if section and subsection:
            proposed = self.vals.get(sname)
        elif section:
            proposed = list()
            for key, value in self.vals.items():
                if section != _ConfigFile.FILE_PREFIX and \
                        isinstance(value, _ConfigFile):
                    proposed.extend(value.get_values(section, subsection))
                if key.startswith(sname):
                    proposed.append(value)
        else:
            proposed = self.vals.values()

        if isinstance(proposed, Values):
            return proposed

        vals = list()
        for value in proposed or list():
            if isinstance(value, list):
                vals.extend(value)
            elif section != _ConfigFile.FILE_PREFIX and \
                    isinstance(value, _ConfigFile):
                vals.extend(value.get_values())
            else:
                vals.append(value)

        return vals


class _IniConfigFile(_ConfigFile):
    def __init__(self, filename, content=None):
        _ConfigFile.__init__(self, filename)

        self._parse_ini(content or self.read())

    def _parse_ini(self, content):
        cfg = self._new_value(_ConfigFile.DEFAULT_CONFIG)
        for k, line in enumerate(content.split('\n')):
            strip = line.strip()
            if len(strip) == 0:
                continue

            # comment
            if strip.startswith('#') or strip.startswith(';'):
                continue

            # [section]
            m = re.match(r'^\s*\[(?P<section>[A-Za-z0-9\-]+)\]$', strip)
            if m:
                cfg = self._new_value(m.group('section'))
                continue

            # [section "subsection"]
            m = re.match(r'^\s*\[(?P<section>[A-Za-z0-9\-]+)\s+'
                         r'"(?P<subsection>[A-Za-z0-9\-]+)"\]', strip)
            if m:
                cfg = self._new_value(
                    '%s.%s' % (m.group('section'), m.group('subsection')))

            # option = value
            m = re.match(r'^\s*(?P<name>[A-Za-z0-9\-_]+)\s*=\s*'
                         r'(?P<value>.*)$', strip)
            if m:
                name = m.group('name')
                value = m.group('value')

                _setattr(cfg, name, value)
                continue

            if len(strip) > 0:
                raise ProcessingError('Unmatched Line %d: %s' % (k + 1, strip))


class _JsonConfigFile(_ConfigFile):
    def __init__(self, filename, content=None):
        _ConfigFile.__init__(self, filename)

        self._parse_json(content or self.read())

    def _parse_json(self, content):
        jresults = json.loads(content)

        for section, values in jresults.items():
            cfg = self._new_value(section)

            for name, value in values.items():
                _setattr(cfg, name, value)


class _XmlConfigFile(_ConfigFile):
    def __init__(self, filename, pi=None):
        _ConfigFile.__init__(self, filename)

        self._parse_xml(filename, pi)

    def _parse_xml(self, filename, pi=None):  # pylint: disable=R0914
        def _getattr(node, name, default=None):
            if node.hasAttribute(name):
                return node.getAttribute(name)
            else:
                return default

        def _handle_patterns(cfg, node):
            if node.nodeName in (
                    'patterns', 'exclude-patterns', 'replace-patterns'):
                patterns = PatternFile.parse_patterns_str(node)
                for pattern in patterns:
                    _setattr(cfg, 'pattern', pattern)

        root = xml.dom.minidom.parse(filename)

        default = self._new_value(_ConfigFile.DEFAULT_CONFIG)

        proj = root.childNodes[0]

        if proj.nodeName == 'projects':
            def _parse_global(node):
                _setattr(default, _getattr(node, 'name'),
                         _getattr(node, 'value', 'true'))

            def _parse_include(node):
                name = _getattr(node, 'name')
                if name and not os.path.isabs(name):
                    name = os.path.join(os.path.dirname(self.filename), name)

                xvals = _XmlConfigFile(name, self.get_default())
                return name, xvals

            def _parse_hook(cfg, node):
                name = _getattr(node, 'name')
                filen = _getattr(node, 'file')
                if filen and not os.path.isabs(filen):
                    filen = os.path.join(
                        os.path.dirname(self.filename), filen)

                _setattr(cfg, 'hook-%s' % name, filen)
                for child in node.childNodes:
                    if child.nodeName == 'args':
                        _setattr(cfg, 'hook-%s-%s' % (name, child.nodeName),
                                 _getattr(child, 'value'))

            def _parse_project(node):
                name = _getattr(node, 'name')
                cfg = self._new_value(
                    '%s.%s' % (_ConfigFile.PROJECT_PREFIX, name))
                group = _getattr(node, 'group')
                if group:
                    _setattr(cfg, 'group', group)

                for child in node.childNodes:
                    if child.nodeName == 'args':
                        _setattr(cfg, child.nodeName, _getattr(child, 'value'))
                    elif child.nodeName == 'option':
                        name = _getattr(child, 'name')
                        value = _getattr(child, 'value')
                        _setattr(cfg, name, value)
                    elif child.nodeName == 'hook':
                        _parse_hook(cfg, child)
                    elif child.nodeName == 'include':
                        name, xvals = _parse_include(child)
                        # only pattern supported and need to export explicitly
                        val = xvals.get_value(ConfigFile.FILE_PREFIX)
                        if val and val.pattern:  # pylint: disable=E1103
                            _setattr(cfg, 'pattern', val.pattern)  # pylint: disable=E1103
                    elif child.nodeName in (
                            'pattern', 'exclude-pattern', 'rp-pattern',
                            'replace-pattern'):
                        pattern = PatternFile.parse_pattern_str(child)
                        _setattr(cfg, 'pattern', [])
                        _setattr(cfg, 'pattern', pattern)
                    else:
                        _handle_patterns(cfg, child)

                cfg.join(self.get_default(), override=False)
                if pi is not None:
                    cfg.join(pi, override=False)

            for node in proj.childNodes:
                if node.nodeName in ('global_option', 'global-option'):
                    _parse_global(node)
                elif node.nodeName == 'project':
                    _parse_project(node)
                elif node.nodeName == 'hook':
                    _parse_hook(default, node)
                elif node.nodeName == 'include':
                    name, xvals = _parse_include(node)
                    self._new_value(
                        '%s.%s' % (_ConfigFile.FILE_PREFIX, name), xvals)

                    val = xvals.get_value(ConfigFile.FILE_PREFIX)
                    if val and val.pattern:  # pylint: disable=E1103
                        self._new_value(
                            '%s.%s' % (_ConfigFile.FILE_PREFIX, 'pattern'),
                            val.pattern)  # pylint: disable=E1103
        elif proj.nodeName == 'patterns':
            cfg = self._new_value(_ConfigFile.FILE_PREFIX)
            for child in proj.childNodes:
                _handle_patterns(cfg, child)
        elif proj.nodeName == 'locations':
            def _handle_locations(name, path, nodes):
                cfg = self._new_value(
                    '%s.%s' % (ConfigFile.LOCATION_PREFIX, name))
                _setattr(cfg, 'exclude', [])
                _setattr(cfg, 'include', [])
                _setattr(cfg, 'location', path)

                for node in nodes:
                    if node.nodeName == 'include-dir':
                        item = _getattr(node, 'name')
                        _setattr(cfg, 'include', '%s/' % item)

                        excd = _getattr(node, 'exclude-dirs')
                        excf = _getattr(node, 'exclude-files')

                        if excd:
                            for exc in excd.split(','):
                                _setattr(
                                    cfg, 'exclude',
                                    '%s/' % os.path.join(item, exc))
                        if excf:
                            for exc in excf.split(','):
                                _setattr(
                                    cfg, 'exclude', os.path.join(item, exc))
                    elif node.nodeName == 'include-file':
                        _setattr(cfg, 'include', _getattr(node, 'name'))
                    elif node.nodeName == 'exclude-dir':
                        _setattr(
                            cfg, 'exclude', '%s/' % _getattr(node, 'name'))
                    elif node.nodeName == 'exclude-file':
                        _setattr(cfg, 'exclude', _getattr(node, 'name'))

            for child in proj.childNodes:
                if child.nodeName == 'project':
                    _handle_locations(
                        _getattr(child, 'name'),
                        _getattr(child, 'location'),
                        child.childNodes)


class ConfigFile(_ConfigFile):
    def __init__(self, filename):
        _ConfigFile.__init__(self, filename)

        content = self.read().lstrip()
        if content[:6].lower().startswith('<?xml'):
            self.inst = _XmlConfigFile(filename)
        elif content.startswith('{'):
            self.inst = _JsonConfigFile(filename, content)
        else:
            self.inst = _IniConfigFile(filename, content)

    def get_default(self):
        return self.inst.get_default()

    def get_value(self, section, subsection=None, name=None):
        return self.inst.get_value(section, subsection, name)

    def get_names(self, section=None, subsection=None):
        return self.inst.get_names(section, subsection)

    def get_values(self, section=None, subsection=None):
        return self.inst.get_values(section, subsection)


TOPIC_ENTRY = 'ConfigFile'


import json
import os
import re
import xml.dom.minidom

from error import ProcessingError
from options import Values


def _setattr(obj, name, value):
    values = None

    name = name.replace('-', '_')
    if hasattr(obj, name):
        values = getattr(obj, name)
        if values is not None and not isinstance(values, list):
            values = [values]

    if values is not None:
        if isinstance(value, list):
            values.extend(value)
        else:
            values.append(value)
    else:
        values = value

    setattr(obj, name, values)


class _ConfigFile(object):
    DEFAULT_CONFIG = '#%^(DEFAULT%%_'
    FILE_PREFIX = 'file'

    def __init__(self, filename=None):
        self.vals = dict()
        self.filename = os.path.realpath(filename)

    def _add_value(self, name, val, override=False):
        if override or name not in self.vals:
            self.vals[name] = val
        else:
            if not isinstance(self.vals[name], list):
                self.vals[name] = [self.vals[name]]

            self.vals[name].append(val)

        return val

    def _new_value(self, name, vals=None, override=False):
        return self._add_value(
            name, Values() if vals is None else vals, override)

    def _get_value(self, name):
        vals = self.vals.get(name)
        if vals is None:
            return self._new_value(name)
        elif isinstance(vals, list):
            return vals[-1]
        else:
            return vals

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
                if key == sname or key.startswith('%s.' % sname):
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


class XmlConfigFile(_ConfigFile):
    """It delegates to handle element "global-options" only.
       Other depends on inherited implementation."""
    def __init__(self, filename, pi=None):
        _ConfigFile.__init__(self, filename)

        root = xml.dom.minidom.parse(filename)
        for node in root.childNodes:
            self.parse(node, pi)

    def parse_global(self, node, config=None):
        name = self.get_attr(node, 'name')
        value = self.get_attr(node, 'value', 'true')

        if config is None:
            config = Values()

        if name and value:
            self.set_attr(config, name, value)

        return config

    def parse(self, node, pi=None):  # pylint: disable=R0914,W0613
        # it delegates only to handle global options
        config = self._get_value(_ConfigFile.DEFAULT_CONFIG)
        for child in node.childNodes:
            if child.nodeName == 'global-option':
                self.parse_global(child, config)
            elif child.nodeName == 'global-options':
                for child2 in child.childNodes:
                    if child2.nodeName == 'option':
                        self.parse_global(child2, config)

    @staticmethod
    def get_attr(node, name, default=None):
        if node.hasAttribute(name):
            return node.getAttribute(name)
        else:
            return default

    @staticmethod
    def set_attr(obj, name, value):
        _setattr(obj, name, value)


class ConfigFile(_ConfigFile):
    def __init__(self, filename):
        _ConfigFile.__init__(self, filename)

        content = self.read().lstrip()
        if content.startswith('<?xml'):
            self.inst = XmlConfigFile(filename)
        elif content.startswith('{'):
            self.inst = _JsonConfigFile(filename, content)
        else:
            self.inst = _IniConfigFile(filename, content)

    @staticmethod
    def options(optparse):
        options = optparse.get_option_group('--working-dir') or \
            optparse.add_option_group('Global file options')
        options.add_option(
            '--config-file',
            dest='config_file', action='store',
            help='Set the config file in XML format for configurations')

    def get_default(self):
        return self.inst.get_default()

    def get_value(self, section, subsection=None, name=None):
        return self.inst.get_value(section, subsection, name)

    def get_names(self, section=None, subsection=None):
        return self.inst.get_names(section, subsection)

    def get_values(self, section=None, subsection=None):
        return self.inst.get_values(section, subsection)


TOPIC_ENTRY = 'ConfigFile, XmlConfigFile'

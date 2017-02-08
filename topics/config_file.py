
"""
File formats for the config file.

Two configurable formats could be supported by the program to provide the
function to the main program and its sub-commands.

One is the XML format to define the elements mapping to the options. It's
defined by the following DTD:

  <!DOCTYPE projects [
    <!ELEMENT global_option (EMPTY)>
    <!ATTLIST global_option name   ID    #REQUIRED>
    <!ATTLIST global_option value  CDATA #IMPLIED>

    <!ELEMENT project (name?, args*)>
    <!ATTLIST project name         ID    #REQUIRED>
    <!ATTLIST project group        CDATA #IMPLIED>
      <!ELEMENT args (EMPTY)>
      <!ATTLIST args value         CDATA #REQUIRED>

      <!ELEMENT option (name?, value?)>
      <!ATTLIST option name        ID    #REQUIRED>
      <!ATTLIST option value       CDATA #REQUIRED>

      <!ELEMENT pattern (name?, value?)>
      <!ATTLIST pattern name       ID    #REQUIRED>
      <!ATTLIST pattern value      CDATA #REQUIRED>

      <!ELEMENT exclude-pattern (name?, value?)>
      <!ATTLIST exclude-pattern    ID    #REQUIRED>
      <!ATTLIST exclude-pattern    CDATA #REQUIRED>
  ]>

The other is similar like the ini file with an extension to support global
variables without the section, which is the equilivalent with global_option.

A sample for the function is:

bar = blabla
[section]
bar = blabla2
[section "subsection"]
bar = blabla3
"""


import re
import xml.dom.minidom

from error import ProcessingError
from logger import Logger
from options import Values
from pattern import PatternFile


def _setattr(obj, name, value):
    values = list()

    name = name.replace('-', '_')
    if hasattr(obj, name):
        values = getattr(obj, name)
        if values and not isinstance(values, list):
            values = [values]

    if values is not None:
        values.append(value)
    else:
        values = value

    setattr(obj, name, values)


class _ConfigFile(object):
    DEFAULT_CONFIG = '#%^(DEFAULT%%_'

    def __init__(self, content):  # pylint: disable=W0613
        self.vals = dict()

    def _new_value(self, name):
        val = Values()
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
            for key in self.vals.keys():
                if key.startswith(sname):
                    vals.append(key)
        else:
            vals.extend(self.vals.keys())

        return vals

    def get_values(self, section=None, subsection=None):
        vals = list()
        sname = self._build_name(section, subsection)

        if section and subsection:
            proposed = self.vals.get(sname)
        elif section:
            proposed = list()
            for key, value in self.vals.items():
                if key.startswith(sname):
                    proposed.append(value)
        else:
            proposed = self.vals.values()

        for value in proposed or list():
            if isinstance(value, list):
                vals.extend(value)
            else:
                vals.append(value)

        return vals


class _IniConfigFile(_ConfigFile):
    def __init__(self, content):
        _ConfigFile.__init__(self, content)

        self._parse_ini(content)

    def _parse_ini(self, content):
        logger = Logger.get_logger()
        k, cfg = 0, self._new_value(_ConfigFile.DEFAULT_CONFIG)
        for line in content.split('\n'):
            k += 1
            logger.debug('%d: [%s]', k, line.rstrip())

            strip = line.strip()
            if len(strip) == 0:
                continue

            # comment
            if strip.startswith('#') or strip.startswith(';'):
                continue

            # [section]
            m = re.match(r'^\[(?P<section>[A-Za-z0-9\-]+)\]$', strip)
            if m:
                cfg = self._new_value(m.group('section'))
                continue

            # [section "subsection"]
            m = re.match(r'^\[(?P<section>[A-Za-z0-9\-]+)\s+'
                         r'"(?P<subsection>[A-Za-z0-9\-]+)"\]', strip)
            if m:
                cfg = self._new_value(
                    '%s.%s' % (m.group('section'), m.group('subsection')))

            # option = value
            m = re.match(r'^(?P<name>[A-Za-z0-9\-_]+)\s*=\s*'
                         r'(?P<value>.*)$', strip)
            if m:
                name = m.group('name')
                value = m.group('value')

                _setattr(cfg, name, value)
                continue

            if len(strip) > 0:
                raise ProcessingError('Unmatched Line %d: %s' % (k, strip))


class _XmlConfigFile(_ConfigFile):
    def __init__(self, content):
        _ConfigFile.__init__(self, content)

        self._parse_xml(content)

    def _parse_xml(self, content):
        root = xml.dom.minidom.parseString(content)

        default = self._new_value(_ConfigFile.DEFAULT_CONFIG)

        proj = root.childNodes[0]
        if proj and proj.nodeName == 'projects':
            def _getattr(node, name):
                if node.hasAttribute(name):
                    return node.getAttribute(name)
                else:
                    return None

            def _parse_global(node):
                _setattr(default, _getattr(node, 'name'),
                         _getattr(node, 'value'))

            def _parse_project(node):
                name = _getattr(node, 'name')
                cfg = self._new_value('project.%s' % name)
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
                    elif child.nodeName in (
                            'patterns', 'exclude-patterns', 'replace-patterns'):
                        patterns = PatternFile.parse_patterns_str(child)
                        for pattern in patterns:
                            _setattr(cfg, 'pattern', pattern)
                    elif child.nodeName in (
                            'pattern', 'exclude-pattern', 'rp-pattern',
                            'replace-pattern'):
                        pattern = PatternFile.parse_pattern_str(child)
                        _setattr(cfg, 'pattern', pattern)

            for node in proj.childNodes:
                if node.nodeName == 'global_option':
                    _parse_global(node)
                elif node.nodeName == 'project':
                    _parse_project(node)


class ConfigFile(_ConfigFile):
    def __init__(self, filename):
        _ConfigFile.__init__(self, None)

        with open(filename, 'r') as fp:
            content = '\n'.join(fp.readlines())

        if content[:6].lower().startswith('<?xml'):
            self.inst = _XmlConfigFile(content)
        else:
            self.inst = _IniConfigFile(content)

    def get_default(self):
        return self.inst.get_default()

    def get_value(self, section, subsection=None, name=None):
        vals = self.get_values(section, subsection)
        if vals:
            if isinstance(vals, list):
                if name:
                    return getattr(vals[0], name)
                else:
                    return vals[0]

        return vals

    def get_names(self, section=None, subsection=None):
        return self.inst.get_names(section, subsection)

    def get_values(self, section=None, subsection=None):
        return self.inst.get_values(section, subsection)


TOPIC_ENTRY = 'ConfigFile'

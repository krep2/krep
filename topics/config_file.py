
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

    INCLUDED_FILE_NAME = "krep.included.name"
    INCLUDED_FILE_NAMES = "krep.included.names"
    INCLUDED_FILE_DEPTH = "krep.included.depth"

    SUPPORTED_ELEMENTS = (
        'include',
        'global-option', 'global-options', 'option',
        'var', 'variable', 'value-sets',
    )

    class _WithVariable(object):
        def __init__(self, config, kws):
            self.obj = config
            self.kws = kws

        def __enter__(self):
            for var, key in self.kws.items():
                self.obj.set_var(var, key)

        def __exit__(self, exc_type, exc_value, traceback):
            for var, _ in self.kws.items():
                self.obj.unset_var(var)

    """It delegates to handle element "global-options" only.
       Other depends on inherited implementation."""
    def __init__(self, filename, pi=None, config=None):
        _ConfigFile.__init__(self, filename)

        self.fvar = dict()
        self.vars = dict()
        self.sets = dict()

        if config:
            for var, value in config.vars.items():
                self.vars[var] = value

            for key, value in config.sets.items():
                self.sets[key] = value

        if os.path.exists(filename):
            root = xml.dom.minidom.parse(filename)
            for node in root.childNodes:
                self.parse(node, pi)

    def set_var(self, var, value=None):
        if var in (XmlConfigFile.INCLUDED_FILE_NAMES,
                   XmlConfigFile.INCLUDED_FILE_DEPTH):
            return
        elif var == XmlConfigFile.INCLUDED_FILE_NAME:
            if var not in self.vars:
                self.vars[var] = list()

            if value is None:
                self.vars[var].pop()
            else:
                self.vars[var].append(value)
        else:
            if value is None:
                del self.vars[var]
            else:
                self.vars[var] = value

    def unset_var(self, var):
        self.set_var(var, None)

    def with_var(self, vals):
        return XmlConfigFile._WithVariable(self, vals)

    def value_sets(self):
        return self.sets.copy()

    def foreach(self, group, node=None):
        skip = Values.boolean(self.get_attr(node, 'skip-if-inexistence'))
        for yset in self.sets.get(group, []):
            if skip and not self.secure_vars(node, yset):
                continue

            self.fvar = yset
            yield yset

        self.fvar = dict()

    def secure_vars(self, node, var=None):
        ret = True

        if var is None and self.var is None:
            return False

        for attr in (node._attrs or dict()).keys():
            value = self.get_attr(node, attr)
            if value:
                _, nonexisted = self.escape_attr(value, var=var)
                if nonexisted:
                    ret = False
                    break

        return ret

    def parse_variable(self, node):
        if not self.evaluate_if_node(node):
            return

        name = self.get_attr(node, 'name')
        value = self.get_attr(node, 'value')

        if name and value:
            self.vars[name] = value

    def parse_global(self, node, config=None):
        name = self.get_attr(node, 'name')
        value = self.get_attr(node, 'value', 'true')

        if config is None:
            config = Values()

        if self.evaluate_if_node(node):
            if name and value:
                self.set_attr(config, name, value)

        return config

    def parse_set(self, node, name=None):
        attrs = dict()

        if not self.evaluate_if_node(node):
            return

        for attr in (node._attrs or dict()).keys():
            attrs[attr] = self.get_var_attr(node, attr)

        if name not in self.sets:
            self.sets[name] = list()

        self.sets[name].append(attrs)

    def parse_include(self, node, clazz=None):
        if not self.evaluate_if_node(node):
            return None, XmlConfigFile('')

        name = self.get_attr(node, 'name')
        if name and not os.path.isabs(name):
            name = os.path.join(os.path.dirname(self.filename), name)

        with self.with_var(
                {XmlConfigFile.INCLUDED_FILE_NAME: name}):
            if issubclass(clazz, XmlConfigFile):
                xvals = clazz(name, self.get_default(), self)
            else:
                xvals = XmlConfigFile(name, self.get_default(), self)

        # duplicate the 'value-sets'
        for key, value in xvals.sets.items():
            if key not in self.sets:
                self.sets[key] = list()

            self.sets[key].extend(value)

        return name, xvals

    def parse(self, node, pi=None):  # pylint: disable=R0914,W0613
        # it delegates only to handle global options
        config = self._get_value(_ConfigFile.DEFAULT_CONFIG)
        if node.nodeName == 'global-option':
            self.parse_global(node, config)
        elif node.nodeName == 'global-options':
            for child2 in node.childNodes:
                if child2.nodeName == 'option':
                    self.parse_global(child2, config)
        elif node.nodeName in ('var', 'variable'):
            self.parse_variable(node)
        elif node.nodeName == 'value-sets':
            name = self.get_attr(node, 'name')
            for child2 in node.childNodes:
                if child2.nodeName in ('pair', 'set'):
                    self.parse_set(child2, name)
        elif node.nodeName == 'include':
            name, xvals = self.parse_include(node)
            # record included file name
            self._new_value(
                '%s.%s' % (XmlConfigFile.FILE_PREFIX, name), xvals)

    def get_var_attr(self, node, name, default=None):
        value = self.get_attr(node, name, default)
        if value:
            return self.escape_attr(value)[0]
        else:
            return value

    def escape_attr(self, value, var=None):
        def _escape_var(varname):
            if varname in (XmlConfigFile.INCLUDED_FILE_NAME,
                       XmlConfigFile.INCLUDED_FILE_NAMES,
                       XmlConfigFile.INCLUDED_FILE_DEPTH):
                vx = XmlConfigFile.INCLUDED_FILE_NAME
                if vx not in var:
                    var[vx] = list()

                if varname == XmlConfigFile.INCLUDED_FILE_NAME:
                    if len(var[vx]) > 0:
                        return var[vx][-1]
                    else:
                        return ''
                elif varname == XmlConfigFile.INCLUDED_FILE_NAMES:
                    return var[vx]
                elif varname == XmlConfigFile.INCLUDED_FILE_DEPTH:
                    return str(len(var[vx]))
            else:
                return var.get(varname)

        i, nonexisted = 0, False
        varprog = re.compile(r'\$(\w+|\{[^}]*\}|\([^)]*\))')
        if var is None:
            var = {}
            var.update(self.vars)
            var.update(self.fvar)

        while True:
            m = varprog.search(value, i)
            if not m:
                break

            i, j = m.span(0)
            name = m.group(1)
            if (name.startswith('{') and name.endswith('}')) or \
                  (name.startswith('(') and name.endswith(')')):
                name = name[1:-1]

            val = _escape_var(name)
            if val is not None:
                value = value[:i] + val + value[j:]
                i += len(val)
            else:
                nonexisted = True
                i = j

        return value, nonexisted

    def _supported_node(self, node):
        if hasattr(node, 'nodeName'):
            return node.nodeName in self.SUPPORTED_ELEMENTS or \
                node.nodeName in XmlConfigFile.SUPPORTED_ELEMENTS
        else:
            return False

    def evaluate_if(self, exp):
        escape, _ = self.escape_attr(exp)
        return eval(escape)

    def evaluate_if_node(self, node):
        if self._supported_node(node):
            expif = self.get_attr(node, 'if')
            if expif:
                return self.evaluate_if(expif)

        return True

    @staticmethod
    def get_attr(node, name, default=None):
        if node and node.hasAttribute(name):
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

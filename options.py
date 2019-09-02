
import re
import sys
import textwrap
import optparse


make_option = optparse.make_option  # pylint: disable=C0103
OptionValueError = optparse.OptionValueError


def _ensure_attr(attr, reverse=False):
    if reverse:
        return attr.replace('_', '-')
    else:
        return attr.replace('-', '_')


class _Origins(object):
    def __init__(self, defaults=None, origin=None):
        self.origin = origin or 'undef'
        self.origins = dict()
        self.details = dict()
        if isinstance(defaults, Values):
            if hasattr(defaults, '_origins'):
                defaults = defaults._origins
            else:
                for attr in defaults.__dict__.keys():
                    self.origins[attr] = origin or 'default'
                raise

        if isinstance(defaults, _Origins):
            if origin is None:
                self.origin = defaults.origin

            for ori, value in defaults.origins.items():
                self.origins[ori] = value
            for det, value in defaults.details.items():
                self.details[det] = value

    def set(self, key, origin):
        if origin:
            if key in self.origins and self.origins[key]:
                if self.origins[key] != 'mixed' and key not in self.details:
                    self.details[key] = list()
                    self.details[key].append(self.origins[key])
                if origin != 'mixed' and origin not in self.details[key]:
                    self.details[key].append(origin)

                self.origins[key] = 'mixed' \
                    if len(self.details[key]) > 0 else origin
            else:
                self.origins[key] = origin

    def unset(self, key):
        self.origins.pop(key, None)

    def get(self, key):
        return self.origins.get(key, self.origin)

    def detail(self, key):
        return self.details.get(key, '')


class Values(optparse.Values):
    def __init__(self, defaults=None, option=None, origin=None):
        if isinstance(defaults, Values):
            optparse.Values.__init__(self, defaults.__dict__)
            self._origins = _Origins(defaults, origin=origin)
        elif isinstance(defaults, dict):
            defs = dict()
            for key, value in defaults.items():
                defs[key] = Values._secure_value(option, key, value)

            optparse.Values.__init__(self, defs)
            self._origins = _Origins(defs, origin=origin)
        else:
            optparse.Values.__init__(self)
            self._origins = _Origins(origin=origin)

    def origin(self, attr, detail=False, default=None):
        ret = self._origins.get(attr)
        if ret is None:
            return default

        if detail:
            details = self._origins.detail(attr)
            if details:
                ret += ' ' + str(details)

        return ret

    @staticmethod
    def _handle_value(val, boolean=False):
        if val is None:
            return val

        sval = str(val).lower()
        if boolean:
            if sval in ('true', 't', 'yes', 'y', '1'):
                val = True
            elif boolean and sval in ('false', 'f', 'no', 'n', '0'):
                val = False
            else:
                val = None
        elif re.match(r'^0x[a-f0-9]+$', sval):
            val = int(sval, 16)
        elif re.match(r'^0[0-7]+$', sval):
            val = int(sval, 8)
        elif re.match(r'^[0-9]+$', sval):
            val = int(sval)
        elif re.match(r'0b[01]+$', sval):
            val = int(sval, 2)

        return val

    @staticmethod
    def _getopt(option, attr):
        nattr = _ensure_attr(attr, reverse=True).strip('-')
        sattr = '-%s' % nattr
        lattr = '--%s' % nattr
        if lattr in option._long_opt:  # pylint: disable=W0212
            opt = option._long_opt[lattr]  # pylint: disable=W0212
        elif sattr in option._short_opt:  # pylint: disable=W0212
            opt = option._short_opt[sattr]  # pylint: disable=W0212
        else:
            opt = None

        return opt

    @staticmethod
    def _is_boolean_opt(option):
      return option and option.action in ('store_true', 'store_false')

    @staticmethod
    def _secure_value(option, attr, value):
        opt = option and Values._getopt(option, attr)
        if opt:
            if opt.action == 'append':
                if not (value is None or isinstance(value, (list, tuple))):
                    return [value]
            elif Values._is_boolean_opt(opt):
                return Values.boolean(value)

        return Values._handle_value(value)

    def join(self, values, option=None, override=True, origin=None):
        if values is not None:
            for attr in values.__dict__:
                if attr and attr.startswith('_'):
                    continue

                nattr, value = None, getattr(values, attr)
                if option and (
                        attr.startswith('no_') or attr.startswith('not_')):
                    nattr = attr[attr.index('_') + 1:]
                    nopt= Values._getopt(option, nattr)
                    if Values._is_boolean_opt(nopt) and str(value).lower() == 'true':
                        attr = nattr
                        value = False

                opt = option and Values._getopt(option, attr)
                if opt and opt.action == 'append' and value is not None:
                    vals = self.__dict__.get(attr)
                    if vals is None:
                        vals = list()
                    if isinstance(vals, tuple):
                        vals = list(vals)
                    elif not isinstance(vals, list):
                        vals = list([vals])

                    if isinstance(value, (tuple, list)):
                        vals.extend(value)
                    else:
                        vals.append(value)

                    self._origins.set(attr, self.origin(attr, origin))
                    self.ensure_value(attr, vals)
                elif override:
                    if nattr is None and getattr(values, attr) is None:
                        if attr in self.__dict__:
                            del self.__dict__[attr]
                        continue

                    self._origins.set(attr, self.origin(attr, origin))
                    setattr(
                        self, attr, Values._secure_value(option, attr, value))
                else:
                    if value is None:
                        continue

                    self._origins.set(attr, self.origin(attr, origin))
                    self.ensure_value(
                        attr, Values._secure_value(option, attr, value))

    def __nonzero__(self):
        return self.__bool__()

    def __bool__(self):
        # ignore '_origins'
        return len(self.__dict__) > 1

    def __getattr__(self, attr):
        return self.__dict__.get(_ensure_attr(attr))

    def diff(self, values, option=None, args=None):
        diffs = Values()
        if isinstance(values, optparse.Values):
            dests = list()
            if args is not None:
                for arg in args:
                    opt = Values._getopt(
                        option, OptionParser.split_argument(arg)[0])
                    if opt:
                        dests.append(opt.dest)

            for attr in self.__dict__:
                if attr in values.__dict__ and (
                        self.__dict__[attr] != values.__dict__[attr] or
                        attr in dests):
                    diffs.ensure_value(attr, values.__dict__[attr])

            for attr in values.__dict__:
                if attr not in self.__dict__:
                    diffs.ensure_value(attr, values.__dict__[attr])

        return diffs

    def pop(self, attr, default=None):
        return self.__dict__.pop(_ensure_attr(attr), default)

    def ensure_value(self, attr, value):
        return optparse.Values.ensure_value(
            self, _ensure_attr(attr), Values._handle_value(value))

    def _normalize(self, val):
        newval = None
        while newval != val:
            match = re.search(r'\$\{([0-9A-Za-z_\-]+)\}', str(val))
            if match:
                name = match.group(1)
                newval = val.replace(
                    '${%s}' % name, self.__dict__.get(_ensure_attr(name), ''))
            else:
                match = re.search(r'\$\(([0-9A-Za-z_\-]+)\)', str(val))
                if match:
                    name = match.group(1)
                    newval = val.replace(
                        '$(%s)' % name,
                        self.__dict__.get(_ensure_attr(name), ''))
                else:
                    break

            val, newval = newval, val

        return val

    def normalize(self, values, attr=False):
        if isinstance(values, (list, tuple)):
            ret = list()
            for val in values:
                ret.append(self.normalize(val, attr=attr))

            return ret
        else:
            if attr:
                values = self.__dict__.get(_ensure_attr(values))
                if isinstance(values, (list, tuple)):
                    return self.normalize(values, attr=False)
                elif not isinstance(values, str):
                    return values

            return self._normalize(values)

    @staticmethod
    def boolean(value):
        ret = Values._handle_value(value, True)
        if ret in (True, False):
            return ret
        else:
            return False

    @staticmethod
    def int(value):
        ret = Values._handle_value(value)
        try:
            tmp = ret  # pylint: disable=W0612
            # try inc
            tmp += 1
            return ret
        except TypeError:
            return None

    @staticmethod
    def extra(option, prefix=None):
        ret = list()

        if option and not isinstance(option, (list, tuple)):
            option = [option]

        for value in option or list():
            if ':' in value and prefix:
                name, extra = value.split(':', 1)
                if name == prefix:
                    ret.append(extra)
            else:
                ret.append(value)

        return ret

    @staticmethod
    def extra_values(option, prefix=None):
        rets = dict()

        for value in Values.extra(option, prefix):
            value = value.lstrip('-')
            if '=' in value:
                opt, arg = value.split('=', 1)
                rets[_ensure_attr(opt)] = arg
            elif ' ' in value:
                opt, arg = value.split(' ', 1)
                rets[_ensure_attr(opt)] = arg
            else:
                rets[_ensure_attr(value)] = 'true'

        return Values(rets)

    @staticmethod
    def build(**kws):
        ret = Values()

        if 'values' in kws:
            values = kws['values']
            if isinstance(values, dict):
                ret.join(values)

            del kws['values']

        ret.join(Values(kws))
        return ret


class IndentedHelpFormatterWithLf(optparse.IndentedHelpFormatter):
    def format_option(self, option):
        if option.help:
            help_text = self.expand_default(option)
            if '\n' not in help_text:
                return optparse.IndentedHelpFormatter.format_option(
                    self, option)

        result = list()
        opts = self.option_strings[option]
        opt_width = self.help_position - self.current_indent - 2
        if len(opts) > opt_width:
            opts = "%*s%s\n" % (self.current_indent, "", opts)
            indent_first = self.help_position
        else:                       # start help on same line as opts
            opts = "%*s%-*s  " % (self.current_indent, "", opt_width, opts)
            indent_first = 0
        result.append(opts)

        help_texts = self.expand_default(option).split('\n')
        help_lines = textwrap.wrap(help_texts[0], self.help_width) + \
                     help_texts[1:]
        result.append("%*s%s\n" % (indent_first, "", help_lines[0]))
        result.extend(["%*s%s\n" % (self.help_position, "", line)
                       for line in help_lines[1:]])

        return "".join(result)


class OptionParser(optparse.OptionParser):
    SUPPRESS_HELP = optparse.SUPPRESS_HELP

    def __init__(self,  # pylint: disable=R0913
                 usage=None,
                 option_list=None,
                 option_class=None,
                 version=None,
                 conflict_handler="error",
                 description=None,
                 add_help_option=True,
                 prog=None,
                 epilog=None):
        optparse.OptionParser.__init__(
            self, usage=usage,
            option_list=option_list,
            option_class=option_class or optparse.Option,
            version=version,
            conflict_handler=conflict_handler,
            description=description,
            formatter=IndentedHelpFormatterWithLf(),
            add_help_option=add_help_option,
            prog=prog,
            epilog=epilog)

        self.sup_values = Values()
        self.defer_options = dict()

    @staticmethod
    def split_argument(arg):
        for k, c in enumerate(arg):
            if c == ' ' or c == '=':
                return [arg[:k], arg[k + 1:]]

        return [arg]

    def _handle_options(self, args):
        """Extends to handle the oppsite options."""
        group = None

        is_help = False
        for arg in args:
            if arg in ('-h', '--help'):
                is_help = True
                break

        if is_help:
            return ['-h']

        for arg in args or sys.argv[1:]:
            for opt, action in self.defer_options.items():
                if re.match(opt, args):
                    if not group:
                        group = self.add_option_group('Pseduo options')

                    group.add_option(
                        arg, dest=re.subst('[\.\*]', '_'),
                        action=action,
                        help=optparse.SUPPRESS_HELP)

            if arg.startswith('--no-') or arg.startswith('--not-'):
                if arg in self._long_opt:
                    continue

                opt = '--%s' % arg[arg.find('-', 4) + 1:]
                if opt in self._long_opt:
                    if not group:
                        group = self.add_option_group('Pseduo options')

                    option = self._long_opt[opt]
                    # don't check the option default but use the rule here
                    group.add_option(
                        arg, dest=option.dest,
                        action='store_false',
                        help=optparse.SUPPRESS_HELP)
                else:
                    raise OptionValueError("no such option %r" % arg)

        return args

    def defer_opt(self, opt, action):
        self.defer_options[opt] = action

    def suppress_opt(self, opt, default=None):
        option = self.get_option_group(opt)
        if option:
            option.remove_option(opt)
        if default:
            setattr(self.sup_values, opt.lstrip('-'), default)

    def join(self, opt):
        opt.join(self.sup_values, override=True, origin='parser')

    def parse_args(self, args=None, inject=False):
        """ Creates a pseduo group to hold the --no- options. """
        try:
            args = self._handle_options(args)
        except AttributeError:
            pass

        opts, argv = optparse.OptionParser.parse_args(self, args)
        if inject:
            opti, _ = optparse.OptionParser.parse_args(self, [])
            optd = Values(opti.__dict__).diff(opts, self, args)
            return optd, _

        optv = Values(opts.__dict__)
        optv.join(self.sup_values)

        return optv, argv

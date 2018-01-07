
import re
import sys
import optparse


make_option = optparse.make_option  # pylint: disable=C0103
OptionValueError = optparse.OptionValueError


def _ensure_attr(attr, reverse=False):
    if reverse:
        return attr.replace('_', '-')
    else:
        return attr.replace('-', '_')


class Values(optparse.Values):
    def __init__(self, defaults=None):
        if isinstance(defaults, Values):
            optparse.Values.__init__(self, defaults.__dict__)
        elif isinstance(defaults, dict):
            optparse.Values.__init__(self, defaults)
        else:
            optparse.Values.__init__(self)

    @staticmethod
    def _handle_value(val, boolean=False):
        sval = str(val).lower()
        if boolean and sval in ('true', 't', 'yes', 'y', '1'):
            return True
        elif boolean and sval in ('false', 'f', 'no', 'n', '0'):
            return False
        elif re.match(r'^0x[a-f0-9]+$', sval):
            return int(sval, 16)
        elif re.match(r'^0[0-7]+$', sval):
            return int(sval, 8)
        elif re.match(r'^[0-9]+$', sval):
            return int(sval)
        else:
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

    def join(self, values, option=None, override=True):
        if values is not None:
            for attr in values.__dict__:
                opt = option and Values._getopt(option, attr)
                st_b = opt and opt.action in ('store_true', 'store_false')

                if override:
                    if getattr(values, attr) is None:
                        if attr in self.__dict__:
                            del self.__dict__[attr]
                        continue

                    setattr(
                        self, attr,
                        Values._handle_value(
                            getattr(values, attr), boolean=st_b))
                else:
                    if getattr(values, attr) is None:
                        continue

                    self.ensure_value(
                        attr, Values._handle_value(
                            getattr(values, attr), boolean=st_b))

    def __getattr__(self, attr):
        nattr = _ensure_attr(attr)
        if nattr in self.__dict__:
            return self.__dict__[nattr]
        else:
            return None

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
            match = re.search(r'\$\{([0-9A-Za-z_\-]+)\}', val)
            if match:
                name = match.group(1)
                newval = val.replace(
                    '${%s}' % name, self.__dict__.get(_ensure_attr(name), ''))
            else:
                match = re.search(r'\$\(([0-9A-Za-z_\-]+)\)', val)
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
                elif not isinstance(values, (str, unicode)):
                    return values

            return self._normalize(values)


class OptionParser(optparse.OptionParser):
    def __init__(self,  # pylint: disable=R0913
                 usage=None,
                 option_list=None,
                 option_class=None,
                 version=None,
                 conflict_handler="error",
                 description=None,
                 formatter=None,
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
            formatter=formatter,
            add_help_option=add_help_option,
            prog=prog,
            epilog=epilog)

        self.sup_values = Values()

    @staticmethod
    def split_argument(arg):
        for k, c in enumerate(arg):
            if c == ' ' or c == '=':
                return [arg[:k], arg[k:]]

        return [arg]

    def _handle_opposite(self, args):
        """Extends to handle the oppsite options."""
        group = None

        for arg in args or sys.argv[1:]:
            if arg.startswith('--no-'):
                opt = '--%s' % arg[5:]
                if opt in self._long_opt:
                    if not group:
                        group = self.add_option_group('Pseduo options')

                    option = self._long_opt[opt]
                    # don't check the option default but use the rule here
                    group.add_option(
                        arg, dest=option.dest,
                        action='store_false',
                        help='Pseduo non-option for %s' % opt)
                else:
                    raise OptionValueError("no such option %r" % arg)

    def suppress_opt(self, opt, default=None):
        option = self.get_option_group(opt)
        if option:
            option.remove_option(opt)
        if default:
            setattr(self.sup_values, opt.lstrip('-'), default)

    def join(self, opt):
        opt.join(self.sup_values, override=True)

    def parse_args(self, args=None, inject=False):
        """ Creates a pseduo group to hold the --no- options. """
        try:
            self._handle_opposite(args)
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

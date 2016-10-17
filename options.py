
import re
import sys
import optparse


make_option = optparse.make_option  # pylint: disable=C0103
OptionValueError = optparse.OptionValueError


class Values(optparse.Values):
    """Extends to enable the values like numbers, boolean values, etc."""
    def join(self, values, option=None, override=True):
        def _getopt(option_, attr):
            nattr = attr.replace('_', '-')
            sattr = '-%s' % nattr
            lattr = '--%s' % nattr
            if lattr in option_._long_opt:  # pylint: disable=W0212
                opt = option_._long_opt[lattr]  # pylint: disable=W0212
            elif sattr in option_._short_opt:  # pylint: disable=W0212
                opt = option_._short_opt[sattr]  # pylint: disable=W0212
            else:
                opt = None

            return opt

        if values is not None:
            for attr in values.__dict__:
                if override:
                    opt = option and _getopt(option, attr)
                    if opt and opt.default == getattr(values, attr):
                        continue

                    setattr(self, attr, getattr(values, attr))
                else:
                    self.ensure_value(attr, getattr(values, attr))

    def __getattr__(self, attr):
        try:
            return self.__dict__[attr]
        except KeyError:
            return None

    def exude(self, attr, default=None):
        ret = default
        if attr in self.__dict__:
            ret = self.__dict__[attr]
            del self.__dict__[attr]

        return ret

    def ensure_value(self, attr, value):
        def _handle_value(val):
            sval = str(val).lower()
            if sval in ('true', 't', 'yes', 'y', '1'):
                return True
            elif sval in ('false', 'f', 'no', 'n', '0'):
                return False
            elif re.match(r'^(0x|0X)?[A-Fa-f\d+]$', sval):
                if sval.startswith('0x'):
                    return int(sval, 16)
                elif sval.startswith('0'):
                    return int(sval, 8)
                else:
                    return int(sval)
            else:
                return val

        return optparse.Values.ensure_value(self, attr, _handle_value(value))


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
        opt.join(self.sup_values)

    def parse_args(self, args=None, values=None):
        """ Creates a pseduo group to hold the --no- options. """
        try:
            self._handle_opposite(args)
        except AttributeError:
            pass

        opts, args = optparse.OptionParser.parse_args(self, args, values)
        optv = Values(opts.__dict__)
        optv.join(self.sup_values)

        return optv, args

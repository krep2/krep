
from logger import Logger


class SubCommand(object):
    """Supports to run as the tool running command."""
    _name = None
    _optparse = None

    def get_option_parser(self, opt):
        """Returns the option parser for the subcommand."""
        if self._optparse is None:
            try:
                usage = self.help_usage.replace(  # pylint: disable=E1101
                    '%prog', 'krep %s' % getattr(
                        self, 'COMMAND', self.NAME))  # pylint: disable=E1101
            except AttributeError:
                # it shouldn't be run here
                raise SyntaxError('Failed to read command attribute')

            self._optparse = opt
            self._optparse.set_usage(usage)
            self.options(self._optparse)

        return self._optparse

    def options(self, optparse, *args, **kws):  # pylint: disable=W0613
        """Handles the options for the subcommand."""
        pass

    @staticmethod
    def get_logger():
        """Returns the encapusulated logger for subcommands."""
        return Logger.get_logger()

    def get_name(self, options):  # pylint: disable=W0613
        """Gets the subcommand name."""
        return self._name or \
            getattr(self, 'COMMAND', self.NAME)  # pylint: disable=E1101

    def set_name(self, name):
        """Sets the subcommand name."""
        self._name = name

    @staticmethod
    def override_value(va, vb=False):
        """Overrides the late values if it's a boolean one."""
        def _is_bool(value):
            return isinstance(value, bool)

        return ((_is_bool(va) and va) and not (_is_bool(vb) and not vb)) or va

    def execute(self, options, *args, **kws):  # pylint: disable=W0613
        return True


TOPIC_ENTRY = 'SubCommand'

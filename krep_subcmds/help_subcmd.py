
from topics import key_compare, SubCommand


class HelpSubcmd(SubCommand):
    COMMAND = 'help'
    help_summary = 'Print the command summaries'
    help_usage = '''\
%prog <subcmd> ...

Display the detailed usage of the sub-command or the list of all supported
sub-commands.

Environment variables KREP_EXTRA_PATH and KREP_SUBCMD_PATH could define new
external sub-commands. Try to define the variables if required.

The argument "all" indicats to list all sub-commands implicitly.'''

    def _print_all_commands(self):
        print('Usage: krep subcmd [args] ...')
        print('The commands of krep are:')
        print('')

        lines = list()
        for name, cmd in self.commands.items():  # pylint: disable=E1101
            try:
                summary = cmd.help_summary.strip()
            except AttributeError:
                summary = 'No Summary'

            if name in getattr(cmd, 'ALIASES', list()):
                summary = 'Alias of "%s"' % getattr(cmd, 'COMMAND', cmd.NAME)

            lines.append('  %-15s%s' % (name, summary))

        def sort_help(linea, lineb):
            def _is_help_command(line):
                return line.lstrip().startswith('help')

            if _is_help_command(linea):
                return -1
            elif _is_help_command(lineb):
                return 1

            return (linea > lineb) - (linea < lineb)  # cmp(linea, lineb)

        # put help command on the top
        lines.sort(key=key_compare(sort_help))
        print('\n'.join(lines))
        print('\nSee more info with "krep help <command>"')

    def _print_command(self, command):
        if command not in self.commands:  # pylint: disable=E1101
            print('krep: "%s" is not a known command' % command)
        else:
            try:
                cmd = self.commands[command]  # pylint: disable=E1101
                help_usage = cmd.help_usage
            except AttributeError:
                help_usage = 'Failed to read the command help.'

            print(help_usage.replace('%prog', 'krep %s' % command))

    def execute(self, options, *args):  # pylint: disable=W0613
        if len(args) == 0 or 'all' in args:
            self._print_all_commands()
        else:
            for arg in args:
                self._print_command(arg)

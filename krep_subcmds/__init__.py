
import os


all_commands = {}  # pylint: disable=C0103


def _register_subcmd(command, instance):
    if command in all_commands:
        raise ImportError(
            "%s is duplicated with %s" % (command, all_commands[command].NAME))

    all_commands[command] = instance


for py in os.listdir(os.path.dirname(__file__)):
    if py == '__init__.py':
        continue

    if py.endswith('.py'):
        name = py[:-3]

        clsn = name.capitalize()
        while clsn.find('_') > 0:
            h = clsn.index('_')
            clsn = clsn[0:h] + clsn[h + 1:].capitalize()

        mod = __import__(__name__,
                         globals(),
                         locals(),
                         ['%s' % name])
        mod = getattr(mod, name)
        try:
            cmd = getattr(mod, clsn)()
        except AttributeError:
            raise SyntaxError(
                '%s/%s does not define class %s' % (__name__, py, clsn))

        name = name.replace('_', '-')
        cmd.NAME = name
        _register_subcmd(getattr(cmd, 'COMMAND', name), cmd)

        if hasattr(cmd, 'ALIASES'):
            aliases = cmd.ALIASES
            if isinstance(aliases, (list, tuple)):
                for alias in aliases:
                    _register_subcmd(alias, cmd)
            else:
                _register_subcmd(aliases, cmd)


if 'help' in all_commands:
    all_commands['help'].commands = all_commands

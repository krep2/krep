
import os
import sys


all_commands = {}  # pylint: disable=C0103


def _register_subcmd(command, instance):
    if command in all_commands:
        raise ImportError(
            "%s is duplicated with %s" % (command, all_commands[command].NAME))

    all_commands[command] = instance


def _load_python_file(pyname):
    if pyname.endswith('.py'):
        name = os.path.basename(os.path.splitext(pyname)[0])

        clsn = name.capitalize()
        while clsn.find('_') > 0:
            und = clsn.index('_')
            clsn = clsn[0:und] + clsn[und + 1:].capitalize()

        sys.path.append(os.path.dirname(pyname))
        mod = __import__(name, globals())
        sys.path.pop(-1)

        try:
            cmd = getattr(mod, clsn)()
        except AttributeError:
            raise SyntaxError(
                '%s/%s does not define class %s' % (__name__, pyname, clsn))

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


def _load_python_in_dir(dirname):
    if os.path.isdir(dirname):
        for name in os.listdir(dirname):
            if name == '__init__.py':
                continue

            filename = os.path.join(dirname, name)
            if os.path.isfile(filename):
                _load_python_file(filename)


# load default sub-commands
_load_python_in_dir(os.path.dirname(__file__))

# load the ones specified in KREP_EXTRA_PATH
for dname in os.environ.get('KREP_EXTRA_PATH', '').split(os.pathsep):
    if os.path.isdir(dname):
        _load_python_in_dir(os.path.join(dname, 'subcmds'))

# load the ones in KREP_SUBCMD_PATH
for dname in os.environ.get('KREP_SUBCMD_PATH', '').split(os.pathsep):
    if os.path.isdir(dname):
        _load_python_in_dir(dname)

if 'help' in all_commands:
    all_commands['help'].commands = all_commands

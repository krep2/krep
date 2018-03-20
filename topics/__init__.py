
import inspect
import os
import sys


__all__ = list()
all_topics = dict()  # pylint: disable=C0103


def _register_topic(topic, doc):
    if topic in all_topics:
        raise SyntaxError("%s is duplicated" % topic)

    __all__.append(topic)
    all_topics[topic] = doc


def _load_python_file(pyname):
    if pyname.endswith('.py'):
        dirname = os.path.dirname(pyname)
        topicdir = os.path.dirname(__file__)

        if pyname.startswith(topicdir + os.sep):
            mname = os.path.join(os.path.basename(topicdir),
                                 pyname[len(topicdir) + 1:])
        else:
            mname = os.path.basename(pyname)

        name = os.path.splitext(mname)[0].replace(os.sep, '.')

        sys.path.append(dirname)
        mod = __import__(os.path.basename(pyname)[:-3], globals())
        sys.path.pop(-1)

        topics = getattr(mod, 'TOPIC_ENTRY', '')
        for clazz in topics.split(','):
            clazz = clazz.strip()
            if clazz:
                if name not in sys.modules and name.find('.') > -1:
                    name = name.split('.')[-1]

                members = inspect.getmembers(
                    sys.modules[name],
                    lambda member: inspect.isclass(member))  # pylint: disable=W0108

                for m in members or list():
                    if m[0] == clazz:
                        globals().update({m[0]: m[1]})

                        _register_topic(
                            clazz,
                            getattr(m[1], '__doc__') or
                            getattr(mod, '__doc__'))
                        break
                else:
                    members = inspect.getmembers(
                        sys.modules[name],
                        lambda member: inspect.isfunction(member))  # pylint: disable=W0108

                    for m in members or list():
                        if m[0] == clazz:
                            globals().update({m[0]: m[1]})
                            _register_topic(clazz, getattr(m[1], '__doc__'))

                            break
                    else:
                        raise SyntaxError(
                            '%s/%s does not define %s' % (
                                __name__, pyname, clazz))


def _load_python_recursive(dirname, level=1):
    if os.path.isdir(dirname):
        dirsname = list()
        for name in os.listdir(dirname):
            if name == '__init__.py':
                continue

            filename = os.path.join(dirname, name)
            if os.path.isfile(filename):
                _load_python_file(filename)
            elif os.path.isdir(filename) and level > 0:
                dirsname.append(filename)

        for name in dirsname:
            _load_python_recursive(name, level - 1)

# load the default topics
_load_python_recursive(os.path.dirname(__file__))

# load the ones specified in KREP_EXTRA_PATH
for dname in os.environ.get('KREP_EXTRA_PATH', '').split(os.pathsep):
    if os.path.isdir(dname):
        _load_python_recursive(os.path.join(dname, 'topics'))

# load the ones specified in KREP_TOPIC_PATH
for dname in os.environ.get('KREP_TOPIC_PATH', '').split(os.pathsep):
    if os.path.isdir(dname):
        _load_python_recursive(dname, 0)

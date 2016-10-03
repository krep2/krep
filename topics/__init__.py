
import inspect
import os
import sys


__all__ = list()
all_topics = dict()  # pylint: disable=C0103


def _register_topic(topic, doc):
    if topic in all_topics:
        raise SyntaxError("%s is duplicated" % topic)

    all_topics[topic] = doc


def _load_python_files(pyname):
    if os.path.basename(pyname) == '__init__.py':
        return

    blen = len(os.path.dirname(__file__)) + 1
    if pyname.endswith('.py'):
        name = pyname[blen:-3].replace('/', '.')
        import_name = '%s.%s' % (__name__, name)
        mod = __import__(import_name, globals(), locals(), ['*'])

        topics = getattr(mod, 'TOPIC_ENTRY', '')
        for clazz in topics.split(','):
            clazz = clazz.strip()
            if clazz:
                members = inspect.getmembers(
                    sys.modules[import_name],
                    lambda member: inspect.isclass(member) and
                    member.__module__.startswith(__name__))

                for m in members or list():
                    globals().update({m[0]: m[1]})
                    if m[0] == clazz:
                        __all__.append(m[0])

                        _register_topic(
                            clazz,
                            getattr(m[1], '__doc__') or
                            getattr(mod, '__doc__'))
                        break
                else:
                    raise SyntaxError(
                        '%s/%s does not define %s' % (__name__, pyname, clazz))


def _load_python_recursive(dirname, level=0):
    for name in os.listdir(dirname):
        filename = os.path.join(dirname, name)
        if os.path.isfile(filename):
            _load_python_files(filename)
        elif os.path.isdir(filename) and level < 1:
            _load_python_recursive(filename, level + 1)


_load_python_recursive(os.path.dirname(__file__))

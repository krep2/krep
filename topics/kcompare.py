
def key_compare(ncmp):
    """Functions used by sorted as key function."""
    class Kcompare(object):
        def __init__(self, objs, *args):  # pylint: disable=W0613
            self.objs = objs

        # pylint: disable=E0602
        def __lt__(self, other):
            return ncmp(self.objs, other.objs) < 0

        def __gt__(self, other):
            return ncmp(self.objs, other.objs) > 0

        def __eq__(self, other):
            return ncmp(self.objs, other.objs) == 0

        def __le__(self, other):
            return ncmp(self.objs, other.objs) <= 0

        def __ge__(self, other):
            return ncmp(self.objs, other.objs) >= 0

        def __ne__(self, other):
            return ncmp(self, objs, other.objs) != 0
        # pylint: enable=E0602

    return Kcompare


TOPIC_ENTRY = 'key_compare'

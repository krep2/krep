
def key_compare(cmp):
    """Functions used by sorted as key function."""
    class Kcompare(object):
        def __init__(self, obj, *args):
            self.obj = obj

        def __lt__(self, other):
            return cmp(self.obj, other.obj) < 0

        def __gt__(self, other):
            return cmp(self.obj, other.obj) > 0

        def __eq__(self, other):
            return cmp(self.obj, other.obj) == 0

        def __le__(self, other):
            return cmp(self.obj, other.obj) <= 0

        def __ge__(self, other):
            return cmp(self.obj, other.obj) >= 0

        def __ne__(self, other):
            return cmp(self, obj, other.obj) != 0

    return Kcompare
            
TOPIC_ENTRY = 'key_compare'

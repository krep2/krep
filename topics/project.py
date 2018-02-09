
from pattern import Pattern


class Project(object):
    def __init__(self, uri, path=None, revision=None, remote=None,  # pylint: disable=W0613
                 pattern=None, *args, **kws):
        self.uri = self._safepath(uri)
        self.path = self._safepath(path)
        self.revision = revision
        self.remote = remote
        self.source = kws.get('source') or remote
        self.pattern = pattern or Pattern()
        self.args = args
        self.kws = kws

    def _safepath(self, path):
        if path:
            ret = path.strip().replace('\\', '/').rstrip('/')
        else:
            ret = path

        return ret

    def __getattr__(self, attr):
        return self.kws.get(attr)

    def __str__(self):
        return '%s' % self.uri

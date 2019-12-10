
from pattern import Pattern


class Project(object):  # pylint: disable=R0902
    def __init__(self, uri, path=None, revision=None, remote=None,  # pylint: disable=W0613
                 pattern=None, *args, **kws):
        self.uri = self._safepath(uri)
        self.path = self._safepath(path)
        self.revision = revision
        self.remote = remote
        self.source = kws.get('source') or uri
        self.pattern = pattern or Pattern()
        self.args = args
        self.kws = kws

    def _safepath(self, path):
        if path:
            ret = path.strip().replace('\\', '/').rstrip('/')
        else:
            ret = path

        return ret

    def update(self, name, remote=None):
        self.uri = name
        if remote:
            self.remote = remote

    def __eq__(self, obj):
        if isinstance(obj, Project):
            return self.uri == obj.uri and \
                   self.path == obj.path and \
                   self.revision == obj.revision and \
                   self.remote == obj.remote and \
                   self.soure == obj.source and \
                   self.args == obj.args and \
                   self.kws == self.kws

        return False

    def __lt__(self, obj):
        if isinstance(obj, Project):
            return self.uri < obj.uri or self.path < obj.path
        else:
            return False

    def __getattr__(self, attr):
        return self.kws.get(attr)

    def __str__(self):
        return '%s' % self.uri

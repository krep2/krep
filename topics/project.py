
class Project(object):
    def __init__(self, uri, path=None, revision=None, remote=None):
        self.uri = self._safepath(uri)
        self.path = self._safepath(path)
        self.revision = revision or 'master'
        self.remote = remote

    def _safepath(self, path):
        if path:
            ret = path.strip().replace('\\', '/').rstrip('/')
        else:
            ret = path

        return ret

    def __str__(self):
        return '%s' % self.uri

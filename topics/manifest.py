
"""
Support git-repo manifest XML file.

It works a a light-weight git-repo manifest implementation not to support all
features from the original one. It can parse a standard git-repo manifest to
fetch the supported attributes.
"""


import os
import xml.dom.minidom

from collections import namedtuple


def _attr(node, attribute, default=None):
    attr = node.getAttribute(attribute)
    if not attr:
        if default is None:
            raise ManifestException(
                '<%s> has no %s' % (node.nodeName, attribute))
        else:
            attr = default

    return attr


def _attr2(node, attribute):
    return _attr(node, attribute, '') or None


def _setattr(elem, name, value):
    if value is not None:
        elem.setAttribute(name, value)


class ManifestException(Exception):
    pass


class _XmlDefault(object):
    revision = None
    remote = None
    sync_j = 1
    sync_c = False
    sync_s = False


class _XmlRemote(object):
    def __init__(self, name, alias, fetch, review, revision):
        self.name = name
        self.alias = alias
        self.fetch = fetch
        self.review = review
        self.revision = revision


class _XmlProject(object):  # pylint: disable=R0902
    File = namedtuple('File', 'src,dest')

    def __init__(self, name, path=None, revision=None, groups=None,
                 remote=None, upstream=None, rebase=None):
        self.name = name
        self.path = path
        self.revision = revision
        self.groups = groups
        self.remote = remote
        self.rebase = rebase
        self.upstream = upstream
        self.removed = False
        self.copyfile = list()
        self.linkfile = list()

    def set_removed(self, removed):
        self.removed = removed

    def add_copy_file(self, src, dest):
        self.copyfile.append(_XmlProject.File(src, dest))

    def add_link_file(self, src, dest):
        self.linkfile.append(_XmlProject.File(src, dest))


class Manifest(object):
    """
Supports git-repo manifest XML file.

It works as a light-weight git-repo manifest implementation not to support all
features from the original one. It can parse a standard git-repo manifest to
fetch the supported attributes. And the loaded manifest or built manifest could
be saved in XML file again with limited attributes.
    """

    DEFAULT_MANIFEST = 'manifest.xml'

    def __init__(self, filename=None, refspath=None, mirror=False):
        self.mirror = mirror
        self.refspath = refspath
        self._default = None
        self._remote = dict()
        self._projects = list()
        self._load(filename)

    def _parse_remote(self, node):
        return _XmlRemote(
            name=_attr(node, 'name'),
            alias=_attr2(node, 'alias'),
            fetch=_attr(node, 'fetch', ''),
            review=_attr2(node, 'review'),
            revision=_attr2(node, 'revision'))

    def _parse_default(self, node):
        default = _XmlDefault()

        default.remote = _attr(node, 'remote')
        if default.remote not in self._remote:
            raise ManifestException(
                'no %s in support remotes' % default.remote)

        default.revision = _attr2(node, 'revision')
        default.sync_j = _attr2(node, 'sync_j')
        default.sync_c = _attr2(node, 'sync_c')
        default.sync_s = _attr2(node, 'sync_s')

        return default

    def _parse_project(self, node):
        # subproject isn't checked
        return _XmlProject(
            name=_attr(node, 'name', _attr2(node, 'in-project')),
            path=_attr2(node, 'path'),
            revision=_attr2(node, 'revision'),
            remote=_attr2(node, 'remote'),
            groups=_attr2(node, 'groups'),
            rebase=_attr2(node, 'rebase'))

    def _parse_manifest_xml(self, filename, path=None):
        try:
            root = xml.dom.minidom.parse(filename)
        except (OSError, xml.parsers.expat.ExpatError):
            raise ManifestException('error to parse manifest %s' % filename)

        if not root or not root.childNodes:
            raise ManifestException('manifest has no root')

        nodes = list()
        for manifest in root.childNodes:
            if manifest.nodeName == 'manifest':
                for node in manifest.childNodes:
                    if node.nodeName == 'include':
                        name = _attr(node, 'name')
                        fname = os.path.join(
                            path or os.path.dirname(
                                os.path.realpath(filename)), name)
                        if not os.path.exists(fname):
                            raise ManifestException(
                                'include %s is not existent' % fname)

                        try:
                            nodes.extend(self._parse_manifest_xml(fname, path))
                        except Exception:
                            raise ManifestException(
                                'failed to parse included manifest %s' % fname)
                    else:
                        nodes.append(node)
                break
        else:
            raise ManifestException('no <manifest> in the file')


        return nodes

    def _parse_manifest(self, nodes):
        for node in nodes:
            if node.nodeName == 'remote':
                remote = self._parse_remote(node)
                if remote.name in self._remote:
                    raise ManifestException('remote %s has been definied')
                else:
                    self._remote[remote.name] = remote

        for node in nodes:
            if node.nodeName == 'default':
                default = self._parse_default(node)
                if self._default is None:
                    self._default = default
                elif self._default != default:
                    raise ManifestException('duplicated default element')

        if self._default is None:
            self._default = _XmlDefault()

        for node in nodes:
            if node.nodeName in ('project', 'repo-hooks'):
                self._projects.append(self._parse_project(node))
                project = self._projects[-1]
                if project.remote and project.remote not in self._remote:
                    raise ManifestException(
                        'Remote %s in project %s not defined' % (
                            project.remote, project.name))

        for node in nodes:
            if node.nodeName == 'remove-project':
                name = _attr(node, 'name')
                if name not in self._projects:
                    raise ManifestException(
                        'remove-project project %s is not existent' % name)
                else:
                    self._projects[name].set_removed(True)

    def _load(self, filename):
        fp = filename or os.path.join('.repo', Manifest.DEFAULT_MANIFEST)
        nodes = self._parse_manifest_xml(fp)
        self._parse_manifest(nodes)

    def _build_projects(self, project_list):
        def _relpath(path, start):
            names = path.replace('\\', '/').split('/')

            for k, name in enumerate(names):
                if name == '.':
                    continue
                elif name == '..':
                    start = os.path.dirname(start)
                else:
                    start = os.path.join(start, names[k])

            return start

        def _build_fetch_url(relative, project):
            if not relative:
                return project.name

            if project.remote:
                remote = project.remote
            else:
                remote = self._default.remote

            remotep = self._remote[remote]
            if remotep.fetch and remotep.fetch.find('://') > 0:
                return os.path.join(remotep.fetch, project.name)
            else:
                return os.path.join(
                    _relpath(remotep.fetch, relative), project.name)

        projects = list()
        for project in project_list or list():
            projects.append(
                _XmlProject(
                    name=project.name,
                    remote=_build_fetch_url(self.refspath, project),
                    path=None if self.mirror else project.path,
                    revision=project.revision))

        return projects

    def get_default(self):
        return self._default

    def get_remote(self, remote):
        return self._remote.get(remote)

    def get_projects(self, raw=False):
        projects = [
            project for project in self._projects if not project.removed]

        if raw:
            return projects
        else:
            return self._build_projects(projects)

    def get_all_projects(self, raw=False):
        if raw:
            return self._projects
        else:
            return self._build_projects(self._projects)


TOPIC_ENTRY = 'Manifest, ManifestException'


"""
Support git-repo manifest XML file.

It works a a light-weight git-repo manifest implementation not to support all
features from the original one. It can parse a standard git-repo manifest to
fetch the supported attributes.
"""


import contextlib
import os
import sys
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
    def __init__(self):
        self.revision = None
        self.remote = None
        self.sync_j = 1
        self.sync_c = False
        self.sync_s = False

    def xml(self, doc):
        e = doc.createElement('default')
        _setattr(e, 'remote', self.remote)
        _setattr(e, 'revision', self.revision)
        _setattr(e, 'sync_j', self.sync_j)
        _setattr(e, 'snyc_c', self.sync_c)
        _setattr(e, 'sync_s', self.sync_s)

        return e

class _XmlRemote(object):
    def __init__(self, name, alias, fetch, review, revision):
        self.name = name
        self.alias = alias
        self.fetch = fetch
        self.review = review
        self.revision = revision

    def xml(self, doc):
        e = doc.createElement('remote')
        _setattr(e, 'name', self.name)
        _setattr(e, 'fetch', self.fetch)
        _setattr(e, 'alias', self.alias)
        _setattr(e, 'review', self.review)
        _setattr(e, 'revision', self.revision)

        return e

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
        self.copyfiles = list()
        self.linkfiles = list()

    def xml(self, doc, default, remotes, rootdir, mirror):
        e = doc.createElement('project')
        _setattr(e, 'name', self.name)
        if (rootdir is not None or not mirror) and self.path:
            _setattr(e, 'path', self.path.replace(rootdir or '', ''))

        remote = None
        if self.remote and remotes:
            for item in remotes:
                if self.remote == item.name:
                    remote = item.name
                    revision = item.revision
                    break

        if not remote and self.revision:
            for item in remotes:
                if item.revision == self.revision:
                    remote = item.name
                    revision = self.revision
                    break

        if not remote:
            remote = default.remote
            revision = default.revision

        if revision != self.revision:
            rev = self.revision
            if remote and self.revision.startswith('%s/' % remote):
                rev = self.revision[len(remote) + 1:]
            if rev != revision:
              _setattr(e, 'revision', rev)
        if remote and self.remote and self.remote != remote:
            _setattr(e, 'remote', remote)
        _setattr(e, 'upstream', self.upstream)
        _setattr(e, 'groups', self.groups)
        for item in self.copyfiles:
            xce = doc.createElement('copyfile')
            _setattr(xce, 'src', item.src)
            _setattr(xce, 'dest', item.dest)
            e.appendChild(xce)

        for item in self.linkfiles:
            xle = doc.createElement('linkfile')
            _setattr(xle, 'src', item.src)
            _setattr(xle, 'dest', item.dest)
            e.appendChild(xle)

        return e

    def set_removed(self, removed):
        self.removed = removed

    def add_copy_file(self, src, dest):
        self.copyfiles.append(_XmlProject.File(src, dest))

    def add_copy_files(self, files):
        self.copyfiles.extend(files)

    def add_link_file(self, src, dest):
        self.linkfiles.append(_XmlProject.File(src, dest))

    def add_link_files(self, files):
        self.linkfiles.extend(files)


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
                'no %s in the supported remotes' % default.remote)

        default.revision = _attr2(node, 'revision')
        default.sync_j = _attr2(node, 'sync_j')
        default.sync_c = _attr2(node, 'sync_c')
        default.sync_s = _attr2(node, 'sync_s')

        return default

    def _parse_project(self, node):
        project = _XmlProject(
            name=_attr(node, 'name', _attr2(node, 'in-project')),
            path=_attr2(node, 'path'),
            revision=_attr2(node, 'revision'),
            remote=_attr2(node, 'remote'),
            groups=_attr2(node, 'groups'),
            rebase=_attr2(node, 'rebase'),
            upstream=_attr2(node, 'upstream'))

        # annotation, subproject isn't checked
        for child in node.childNodes:
            if child.nodeName == 'copyfile':
                project.add_copy_file(
                    _attr2(child, 'src'), _attr2(child, 'dest'))
            elif child.nodeName == 'linkfile':
                project.add_link_file(
                    _attr2(child, 'src'), _attr2(child, 'dest'))

        return project

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
                if name in self._projects:
                    self._projects[name].set_removed(True)

    def _load(self, filename):
        fp = filename or os.path.join('.repo', Manifest.DEFAULT_MANIFEST)
        nodes = self._parse_manifest_xml(fp)
        self._parse_manifest(nodes)

    def _build_projects(self, project_list):
        def _get_revision(project):
            revision = project.revision

            if not revision and project.remote:
                remote = self.get_remote(project.remote)
                if remote:
                    revision = remote.revision

            if not revision:
                revision = self._default.revision
                if not revision:
                    remote = self.get_remote(self._default.remote)
                    if remote:
                        revision = remote.revision

            return revision

        projects = list()
        for project in project_list or list():
            if project.groups and project.groups.find('notdefault') > -1:
                continue

            projects.append(
                _XmlProject(
                    name=project.name,
                    remote=project.remote or self._default.remote,
                    path=project.path or project.name,
                    revision=_get_revision(project),
                    groups=project.groups,
                    upstream=project.upstream))
            projects[-1].add_copy_files(project.copyfiles)
            projects[-1].add_link_files(project.linkfiles)

        return projects

    def get_default(self):
        return self._default

    def get_remote(self, remote):
        return self._remote.get(remote)

    def get_remotes(self):
        return self._remote.values()

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


class ManifestBuilder(object):
    """
Supports to build up git-repo manifest and store.

It works oppositely like Manifest to work with git-repo manifest but to
store the live manifest nodes into files.
    """

    def __init__(self, filename, rootdir, mirror=False):
        self.list = list()
        self.mirror = mirror
        self.rootdir = rootdir and '%s/' % rootdir.rstrip('/')
        self.filename = filename

    def append(self, item):
        self.list.append(item)

    def default(self, revision=None, remote=None, sync_j=None):
        default = _XmlDefault()
        default.revision = revision
        default.remote = remote
        default.sync_j = sync_j

        self.append(default)

    def remote(self, name, alias=None, fetch=None, review=None, revision=None):
        remote = _XmlRemote(name, alias, fetch, review, revision)
        self.append(remote)

    def project(self, name, path=None, revision=None, groups=None,
                remote=None, rebase=None, upstream=None,
                copyfiles=None, linkfiles=None):
        project = _XmlProject(
            name=name, path=path, revision=revision, groups=groups,
            remote=remote, rebase=rebase, upstream=upstream)
        if copyfiles:
            project.add_copy_files(copyfiles)
        if linkfiles:
            project.add_link_files(linkfiles)

        self.append(project)

        return project

    def xml(self):
        doc = xml.dom.minidom.Document()
        root = doc.createElement('manifest')
        doc.appendChild(root)

        remotes = list()
        for node in self.list:
            if isinstance(node, _XmlRemote):
                remotes.append(node)
                root.appendChild(node.xml(doc))

        root.appendChild(doc.createTextNode(''))

        default = None
        for node in self.list:
            if isinstance(node, _XmlDefault):
                if default is not None:
                    raise ManifestException(
                        'element "deault" has been defined')
                else:
                    default = node
                    root.appendChild(node.xml(doc))
                    root.appendChild(doc.createTextNode(''))

        for node in self.list:
            if isinstance(node, _XmlProject):
                root.appendChild(
                    node.xml(doc, default, remotes, self.rootdir, self.mirror))

        return doc

    def save(self):
        @contextlib.contextmanager
        def _open(output, mode):
            if output:
                fp = open(output, mode)
            else:
                fp = sys.stdout

            try:
                yield fp
            finally:
                if fp is not sys.stdout:
                    fp.close()

        with _open(self.filename, 'w') as filep:
            doc = self.xml()
            doc.writexml(filep, '', '  ', '\n', 'utf-8')


TOPIC_ENTRY = 'Manifest, ManifestBuilder'

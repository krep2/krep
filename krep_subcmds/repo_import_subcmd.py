
import os

from collections import namedtuple

from options import Values
from pkg_import_subcmd import PkgImporter, PkgImportSubcmd
from repo_subcmd import RepoSubcmd

from options import Values
# pylint: disable=W0611
from topics import ConfigFile, FileVersion, GitProject, key_compare, \
    KrepXmlConfigFile, Logger, Pattern, RaiseExceptionIfOptionMissed, \
    SubCommandWithThread
# pylint: enable=W0611


class VersionMatcher(object):
    def __init__(self, project=None):
        self.project = project

    def _secure(self, version):
        prefixes = ['v', '-']
        if self.project:
            prefixes.insert(0, self.project.lower())

        if version:
            changed, lvalue = True, version.lower()
            while changed:
                changed = False
                for prefix in prefixes:
                    if lvalue.startswith(prefix):
                        length = len(prefix)
                        version = version[length:]
                        lvalue = lvalue[length:]
                        changed = True

        return version

    def match(self, version, at=None, start=None, end=None, till=None):
        if self.project:
            if not version.startswith(self.project):
                return False

        start = self._secure(start)
        end = self._secure(end)
        till = self._secure(till)
        version = self._secure(version)
        at = self._secure(at)

        if start and FileVersion.cmp(version, start) == -1:
            return False
        if end and FileVersion.cmp(version, end) == 1:
            return False
        if till and FileVersion.cmp(version, till) >= 0:
            return False
        if at:
            return FileVersion.cmp(version, at) == 0

        return True


class RepoImportLocation(object):
    Rule = namedtuple('Rule', 'location,start,end,till,project')

    def __init__(self):
        # order will be kept as input
        self.locations = list()

    def __repr__(self):
        def append(items, name, value):
            if name and value:
                items.append("%s=%s," % (name, value))

        ret = list()
        for location in self.locations:
            item = list()
            append(item, "project", location.project)
            append(item, "start", location.start)
            append(item, "end", location.end)
            append(item, "till", location.till)

            if item:
                ret.append(', '.join(item))

        return str(ret)

    def add(self, location, start=None, end=None, till=None, project=None):
        if location:
            self.locations.append(
                RepoImportLocation.Rule(
                    location=location, start=start, end=end,
                    till=till, project=project))

    def get(self, version, rootdir=None):
        for loc, start, end, till, project in self.locations:
            if project:
                if not version.startswith(project):
                    continue

            matcher = VersionMatcher(project)
            if not matcher.match(version, start=start, end=end, till=till):
                continue

            if rootdir:
                path = os.path.join(rootdir, loc)
                if os.path.exists(path):
                    return path
            else:
                return path

        return None


class RepoImportMeta(object):
    Rule = namedtuple('Rule', 'author,date,committer,cdate')

    def __init__(self):
        self.meta = dict()

    def __len__(self):
        return len(self.meta)

    def __repr__(self):
        def append(items, name, value):
            if name and value:
                items.append("%s=%s," % (name, value))

        ret = list()
        for version, meta in self.meta.items():
            item = list()
            append(item, "author", meta.author)
            append(item, "date", meta.date)
            append(item, "committer", meta.committer)
            append(item, "committer_date", meta.cdate)

            if item:
                ret.append('%s: %s' % (version, ', '.join(item)))

        return str(ret)

    def __iadd__(self, obj):
        if isinstance(obj, RepoImportMeta):
            for meta, val in obj.meta.items():
                self.meta[meta] = val

        return self

    def add(self, version, author=None, date=None, committer=None, cdate=None):
        self.meta[version]= RepoImportMeta.Rule(
            author=author, date=date, committer=committer, cdate=cdate)

    def match(self, version):
        matcher = VersionMatcher()
        for candidate, meta in self.meta.items():
            if matcher.match(version, at=candidate):
                return meta

        return None


# pylint: disable=E1101
class RepoImportXmlConfigFile(KrepXmlConfigFile):
    LOCATION_PREFIX = "locations"

    SUPPORTED_ELEMENTS = (
        'locations', 'location', 'project', 'meta', 'meta-info',
        'subdir', 'include-dir', 'exclude-dir',
        'include-file', 'exclude-file', 'copy-file', 'link-file'
    )

    def parse(self, node, pi=None):  # pylint: disable=R0914
        if node.nodeName != 'locations' and node.nodeName != 'meta-info':
            return

        if not self.evaluate_if_node(node):
            return

        self.meta = RepoImportMeta()
        if node.nodeName == 'meta-info':
            for child in node.childNodes:
                if child.nodeName == 'meta':
                    self._parse_meta(child, self.meta, recursive=False)
        else:
            for child in node.childNodes:
                if child.nodeName == 'project':
                    self._parse_project(child)
                elif child.nodeName == 'remove-project':
                    self._parse_remove_project(child)
                elif child.nodeName == 'include':
                    self._parse_include(child)
                elif child.nodeName == 'meta-info':
                    self._parse_meta(child, self.meta)

    def _parse_include(self, node):
        if not self.evaluate_if_node(node):
            return

        _, conf = KrepXmlConfigFile.parse_include(
            self, node, RepoImportXmlConfigFile)
        names = conf.get_names(RepoImportXmlConfigFile.LOCATION_PREFIX)
        for cname in names:
            self._new_value(cname, conf.get_values(cname))

        # duplicate meta-info
        if conf.meta:
            self.meta += conf.meta

    def _parse_location(self, node, locations, name=None):
        if not self.evaluate_if_node(node):
            return

        if node.nodeName == 'locations':
            name = self.get_attr(node, 'name')
            for child in node.childNodes:
                self._parse_location(child, locations, name)
        elif node.nodeName == 'location':
            location = self.get_attr(node, 'name', name)
            start = self.get_attr(node, 'start')
            end = self.get_attr(node, 'end')
            till = self.get_attr(node, 'till')
            project = self.get_attr(node, 'project')
            locations.add(
                location, start=start, end=end, till=till, project=project)

    def _parse_meta(self, node, meta, recursive=True):
        if not self.evaluate_if_node(node):
            return

        if node.nodeName == 'meta':
            meta.add(
                version=self.get_attr(node, 'version'),
                author=self.get_attr(node, 'author'),
                date=self.get_attr(node, 'date'),
                committer=self.get_attr(node, 'committer'),
                cdate=self.get_attr(node, 'committer-date'))
        elif recursive and node.nodeName == 'meta-info':
            for child in node.childNodes:
                self._parse_meta(child, meta)

    def _parse_project(self, node, name=None, subdir=False):
        if not self.evaluate_if_node(node):
            return

        self._new_value(
            '%s.%s' % (RepoImportXmlConfigFile.LOCATION_PREFIX,
                       name or self.get_attr(node, 'name')),
            [], override=self.get_attr(node, 'override'))

        active = False

        cfg = Values()
        self.set_attr(cfg, 'exclude', [])
        self.set_attr(cfg, 'include', [])
        self.set_attr(cfg, 'copyfile', [])
        self.set_attr(cfg, 'linkfile', [])
        if subdir:
            self.set_attr(cfg, 'subdir', self.get_attr(node, 'name'))
        else:
            self.set_attr(cfg, 'subdir', self.get_attr(node, 'subdir'))

        self.set_attr(cfg, 'path', self.get_attr(node, 'path'))

        locs = RepoImportLocation()
        self.set_attr(cfg, 'location', locs)
        meta = RepoImportMeta()
        self.set_attr(cfg, 'meta', meta or self.meta)

        self.set_attr(
            cfg, 'symlinks', Values.boolean(self.get_attr(node, 'symlinks')))
        self.set_attr(cfg, 'cleanup', self.get_attr(node, 'cleanup'))
        self.set_attr(cfg, 'strict', self.get_attr(node, 'strict'))
        self.set_attr(cfg, 'override', self.get_attr(node, 'override'))

        for child in node.childNodes:
            if child.nodeName == 'subdir':
                active = True

                self._parse_project(
                    child, name=self.get_attr(node, 'name'), subdir=True)
            elif child.nodeName in ('location', 'locations'):
                self._parse_location(child, locs)
            elif child.nodeName == 'meta-info':
                self._parse_meta(child, meta)
            elif child.nodeName == 'include-dir':
                item = self.get_attr(child, 'name')
                cpfs = self.get_attr(child, 'copy')
                lkfs = self.get_attr(child, 'link')
                incd = self.get_attr(child, 'dirs')
                incf = self.get_attr(child, 'files')
                excd = self.get_attr(child, 'exclude-dirs')
                excf = self.get_attr(child, 'exclude-files')

                if cpfs:
                    for cps in cpfs.split(','):
                        src, dest = cps.split(':')
                        self.set_attr(
                            cfg, 'copyfile',
                            (os.path.join(item, src),
                             os.path.join(item, dest)))
                if lkfs:
                    for lkf in lkfs.split(','):
                        src, dest = lkf.split(':')
                        self.set_attr(
                            cfg, 'copyfile',
                            (os.path.join(item, src),
                             os.path.join(item, dest)))

                if incd:
                    for inc in incd.split(','):
                        self.set_attr(
                            cfg, 'include', '%s/' % os.path.join(item, inc))
                if incf:
                    for inc in incf.split(','):
                        self.set_attr(cfg, 'include', os.path.join(item, inc))

                if not (incd or incf):
                    self.set_attr(cfg, 'include', '%s/' % item)

                if excd:
                    for exc in excd.split(','):
                        self.set_attr(
                            cfg, 'exclude', '%s/' % os.path.join(item, exc))
                if excf:
                    for exc in excf.split(','):
                        self.set_attr(cfg, 'exclude', os.path.join(item, exc))
            elif child.nodeName == 'include-file':
                self.set_attr(cfg, 'include', self.get_attr(child, 'name'))
            elif child.nodeName == 'exclude-dir':
                self.set_attr(
                    cfg, 'exclude', '%s/' % self.get_attr(child, 'name'))
            elif child.nodeName == 'exclude-file':
                self.set_attr(cfg, 'exclude', self.get_attr(child, 'name'))
            elif child.nodeName == 'copy-file':
                self.set_attr(
                    cfg, 'copyfile',
                    (self.get_attr(child, 'src'),
                     self.get_attr(child, 'dest')))
            elif child.nodeName == 'link-file':
                self.set_attr(
                    cfg, 'linkfile',
                    (self.get_attr(child, 'src'),
                     self.get_attr(child, 'dest')))

        location = self.get_attr(node, 'location')
        if location:
            for loc in location.split('|'):
                locs.add(loc.strip())

        if not active:
            self._new_value(
                '%s.%s' % (RepoImportXmlConfigFile.LOCATION_PREFIX,
                           name or self.get_attr(node, 'name')), cfg)
        elif cfg and (
                cfg.include or cfg.exclude or cfg.copyfile or cfg.linkfile):
            print('Warning: "%s" defined, all other values ignored' %
                  self.get_attr(node, 'name'))

    def _parse_remove_project(self, node):
        name = self.get_attr(node, 'name')
        if name:
            self._remove_value(
              '%s.%s' % (RepoImportXmlConfigFile.LOCATION_PREFIX, name))
# pylint: enable=E1101


class RepoImportSubcmd(RepoSubcmd, PkgImportSubcmd):
    COMMAND = 'repo-import'
    ALIASES = ()

    help_summary = '''\
Import directories to remote with git-repo projects'''

    help_usage = """\
%prog [options] ...

Unpack the local packages and import into the git-repo repositories

It works with git-repo manifest and local packages, tries to re-deploy
the local changes to the repositories and upload. A config file could
be used to define the wash-out and generate the final commit.
"""

    def options(self, optparse):  # pylint: disable=W0221
        RepoSubcmd.options(self, optparse, inherited=True, modules=globals())
        options = optparse.get_option_group('--all') or \
            optparse.add_option_group('Import options')
        options.add_option(
            '--label', '--tag', '--revision',
            dest='tag', action='store',
            help='Import version for the import')

        options = optparse.get_option_group('-a') or \
            optparse.add_option_group('Import options')
        options.add_option(
            '--keep-order', '--keep-file-order', '--skip-file-sort',
            dest='keep_order', action='store_true',
            help='Keep the order of input files or directories without sort')

        options = optparse.add_option_group('Version options')
        options.add_option(
            '--project',
            dest='project', action='store',
            help='Set the project to match import directories')
        options.add_option(
            '--start', '--vstart',
            dest='start', action='store',
            help='Limit the start version from the import directories')
        options.add_option(
            '--end', '--vend',
            dest='end', action='store',
            help='Limit the end version from the import directories')
        options.add_option(
            '--till', '--vtill',
            dest='till', action='store',
            help='Limit the start version from the import directories')

    def get_name(self, options):
        return options.name or '[-]'

    @staticmethod
    def do_import_with_config(project, options, pvalues, logger, rootdir,
                              force=False):

        project_name = "%s" % str(project)
        if options.tag:
            label = options.tag
        else:
            label = os.path.basename(rootdir)

        # don't pass project_name, which will be showed in commit
        # message and confuse the user to see different projects
        with PkgImporter(project, options, '', label, logger) as imp:
            for pvalue in pvalues:
                if not pvalue:
                    logger.warning(
                        '"%s%s" is undefined' % (
                            project_name,
                            '/%s' % pvalue.subdir if pvalue.subdir else ''))
                    continue
                elif pvalue.path and project.path != \
                        os.path.join(options.working_dir, pvalue.path):
                    continue

                path, location = rootdir, None
                if pvalue.location:
                    location = pvalue.location.get(label, rootdir)
                    if location:
                        path = os.path.join(rootdir, location)

                if location is None or \
                        not os.path.exists(os.path.join(rootdir, location)):
                    if location:
                        logger.warning(
                            '"%s" is not existed',
                            os.path.join(rootdir, location))
                    else:
                        logger.warning('path is not existed')

                    continue

                filters = list()
                filters.extend(pvalue.include or list())
                filters.extend([
                    '!%s' % p for p in pvalue.exclude or list()])

                if len(filters) == 0:
                    logger.warning(
                        'No provided filters for "%s" during importing',
                        project_name)

                optc = options.extra_values(options.extra_option, 'git-commit')
                if pvalue.meta:
                    meta = pvalue.meta.match(label)
                    if meta:
                        if meta.author:
                            optc.author = meta.author
                        if meta.date:
                            optc.date = meta.date
                        if meta.committer:
                            optc.committer = meta.committer
                        if meta.cdate:
                            optc.committer_date = meta.cdate

                opti = Values.build(
                    copyfiles=pvalue.copyfile,
                    cleanup=pvalue.cleanup,
                    filter_sccs=True,
                    filters=filters,
                    force=force,
                    imports=False if location else None,
                    linkfiles=pvalue.linkfile,
                    refs=options.refs,
                    strict=pvalue.strict,
                    subdir=pvalue.subdir,
                    symlinks=pvalue.symlinks,
                    tag_refs=options.tag_refs,
                    extra=optc)

                imp.do_import(path, options=opti)

        return True

    @staticmethod
    def push(project, options, config, logger, rootdirs):  # pylint: disable=W0221
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        logger.info('Start processing ...')

        pvalues = config.get_values(
            RepoImportXmlConfigFile.LOCATION_PREFIX, project_name)
        if pvalues:
            pvals = [pvalue for pvalue in pvalues if pvalue.path is not None]
            if len(pvals) not in (0, len(pvalues)):
                logger.error(
                    'not all items of "%s" has defined "path"',
                    project_name)

                return 1
        else:
            logger.warning('"%s" is undefined', project_name)
            return 0

        changed = False
        matcher = VersionMatcher(options.project)
        for rootdir in rootdirs:
            res = 0

            if options.project and not matcher.match(
                    os.path.basename(rootdir), start=options.start,
                    end=options.end, till=options.till):
                logger.warning('Ignore %s not to match version rules' % rootdir)
                continue

            if RepoImportSubcmd.do_import_with_config(
                    project, options, pvalues, logger, rootdir.rstrip('/'),
                    changed or options.force):
                res += 1

            # all subdirs return without results, ignore finally
            if res > 0:
                changed = True

        RepoImportSubcmd.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        optgp = options.extra_values(options.extra_option, 'git-push')
        optp = Values.build(extra=optgp, fullname=True)
        # push the branches
        if changed and RepoImportSubcmd.override_value(  # pylint: disable=E1101
                options.branches, options.all):
            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                options=optp,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push heads')

        # push the tags
        if changed and RepoImportSubcmd.override_value(  # pylint: disable=E1101
                options.tags, options.all):
            res = project.push_tags(
                tags, RepoImportSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                options=optp,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push tags')

        RepoImportSubcmd.do_hook(  # pylint: disable=E1101
            'post-push', options, dryrun=options.dryrun)

    def execute(self, options, *args, **kws):  # pylint: disable=R0915
        SubCommandWithThread.execute(self, options, *args, **kws)

        RaiseExceptionIfOptionMissed(
            len(args), "No directories specified to import")

        RaiseExceptionIfOptionMissed(
            options.config_file, "No config file specified for the import")

        if not options.offsite:
            self.init_and_sync(options, update=False)

        options.filter_out_sccs = True

        if not options.keep_order:
            args = sorted(args, key=key_compare(FileVersion.cmp))

        cfg = RepoImportXmlConfigFile(
            SubCommandWithThread.get_absolute_running_file_name(
                options, options.config_file))

        self.run_with_thread(  # pylint: disable=E1101
            options.job,
            RepoSubcmd.fetch_projects_in_manifest(options),
            RepoImportSubcmd.push, options, cfg,
            Logger.get_logger(),  # pylint: disable=E1101
            args)

        return 0

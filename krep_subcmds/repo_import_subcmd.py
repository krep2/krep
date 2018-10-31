
import os

from options import Values
from pkg_import_subcmd import PkgImportSubcmd
from repo_subcmd import RepoSubcmd

# pylint: disable=W0611
from topics import ConfigFile, FileVersion, GitProject, key_compare, \
    KrepXmlConfigFile, Logger, Pattern, RaiseExceptionIfOptionMissed, \
    SubCommandWithThread
# pylint: enable=W0611


# pylint: disable=E1101
class RepoImportXmlConfigFile(KrepXmlConfigFile):
    LOCATION_PREFIX = "locations"

    def __init__(self, filename, pi=None):
        KrepXmlConfigFile.__init__(self, filename, pi)

    def parse(self, node, pi=None):  # pylint: disable=R0914
        if node.nodeName != 'locations':
            return

        for child in node.childNodes:
            self._parse_project(child)

    def _parse_project(self, node):
        if node.nodeName != 'project':
            return

        cfg = self._new_value(
            '%s.%s' % (RepoImportXmlConfigFile.LOCATION_PREFIX,
                       self.get_attr(node, 'name')))

        self.set_attr(cfg, 'exclude', [])
        self.set_attr(cfg, 'include', [])
        self.set_attr(cfg, 'copyfile', [])
        self.set_attr(cfg, 'linkfile', [])
        self.set_attr(cfg, 'subdir', self.get_attr(node, 'subdir'))
        self.set_attr(cfg, 'location', self.get_attr(node, 'location'))
        self.set_attr(
            cfg, 'symlinks', Values.boolean(self.get_attr(node, 'symlinks')))

        for child in node.childNodes:
            if child.nodeName == 'include-dir':
                item = self.get_attr(child, 'name')
                self.set_attr(cfg, 'include', '%s/' % item)

                excd = self.get_attr(child, 'exclude-dirs')
                excf = self.get_attr(child, 'exclude-files')

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
# pylint: enable=E1101


class RepoImportSubcmd(RepoSubcmd, PkgImportSubcmd):
    COMMAND = 'repo-import'
    ALIASES = ()

    help_summary = '''\
Import package file or directories to the remote with git-repo projects'''

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

    def get_name(self, options):
        return options.name or '[-]'

    @staticmethod
    def push(project, options, config, logger, rootdir):  # pylint: disable=W0221
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        filters = list()
        logger.info('Start processing ...')

        path, subdir, location = rootdir, '', None
        symlinks, copyfile, linkfile = True, None, None

        pvalues = config.get_value(
            RepoImportXmlConfigFile.LOCATION_PREFIX, project_name)
        if pvalues:
            filters.extend(getattr(pvalues, 'include') or list())
            filters.extend([
                '!%s' % p for p in getattr(pvalues, 'exclude') or list()])

            subdir = getattr(pvalues, 'subdir')
            locations = getattr(pvalues, 'location')
            symlinks = getattr(pvalues, 'symlinks')
            copyfile = getattr(pvalues, 'copyfile')
            linkfile = getattr(pvalues, 'linkfile')

            if locations:
                for location in sorted(locations.split('|'), reverse=True):
                    path = os.path.join(rootdir, location)
                    if os.path.exists(path):
                        break
        else:
            logger.warning('"%s" is undefined', project_name)
            return 0

        if len(filters) == 0:
            logger.warning(
                'No provided filters for "%s" during importing', project_name)

        if options.tag:
            label = options.tag
        else:
            label = os.path.basename(rootdir)

        if not (copyfile or linkfile) and not (
                location and os.path.exists(os.path.join(rootdir, location))):
            logger.warning('Ignored as nothing to import')
            return 0

        # don't pass project_name, which will be showed in commit
        # message and confuse the user to see different projects
        _, tags = PkgImportSubcmd.do_import(
            project, options, '', path, label, subdir=subdir,
            filters=filters, logger=logger, imports=False if location else None,
            symlinks=symlinks, copyfiles=copyfile, linkfiles=linkfile)

        RepoImportSubcmd.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        optgp = options.extra_values(options.extra_option, 'git-push')

        # push the branches
        if RepoImportSubcmd.override_value(  # pylint: disable=E1101
                options.branches, options.all):
            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                options=optgp,
                fullname=True,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push heads')

        # push the tags
        if RepoImportSubcmd.override_value(  # pylint: disable=E1101
                options.tags, options.all):
            res = project.push_tags(
                tags, RepoImportSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                options=optgp,
                fullname=True,
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

        for arg in args:
            self.run_with_thread(  # pylint: disable=E1101
                options.job,
                RepoSubcmd.fetch_projects_in_manifest(options),
                RepoImportSubcmd.push, options, cfg,
                Logger.get_logger(),  # pylint: disable=E1101
                arg.rstrip('/'))

        return 0

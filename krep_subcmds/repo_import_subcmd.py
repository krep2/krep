
import hashlib
import os
import re
import stat
import shutil
import tempfile
import time

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from pkg_import_subcmd import PkgImportSubcmd
from repo_subcmd import RepoSubcmd

from topics import ConfigFile, Logger, RaiseExceptionIfOptionMissed, \
    SubCommandWithThread


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

    def options(self, optparse):
        RepoSubcmd.options(self, optparse, inherited=True, modules=globals())
        options = optparse.get_option_group('--all') or \
            optparse.add_option_group('Import options')
        options.add_option(
            '--label', '--tag', '--revision',
            dest='tag', action='store',
            help='Import version for the import')

    def get_name(self, options):
        return options.name or '[-]'

    @staticmethod
    def push(project, options, config, logger, rootdir):
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        filters = list()
        logger.info('Start processing ...')

        path = rootdir
        pvalues = config.get_value(ConfigFile.LOCATION_PREFIX, project_name)
        if pvalues:
            filters.extend(getattr(pvalues, 'include') or list())
            filters.extend([
                '!%s' % p for p in getattr(pvalues, 'exclude') or list()])

            location = getattr(pvalues, 'location')
            if location:
                path = os.path.join(rootdir, location)

        if os.path.exists(path):
            if len(filters) > 0:
                # don't pass project_name, which will be showed in commit
                # message and confuse the user to see different projects
                _, tags = PkgImportSubcmd.do_import(
                    project, options, '', path, options.tag, filters, logger)
            else:
                logger.warning(
                    'No provided location for "%s" to import', project_name)
                return -1
        else:
            logger.warning('"%s" is not existed', path)
            return -1

        RepoImportSubcmd.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        # push the branches
        if RepoImportSubcmd.override_value(  # pylint: disable=E1101
                options.branches, options.all):
            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
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
            options.tag, "No label specified for the import")

        if not options.offsite:
            self.init_and_sync(options, update=False)

        cfg = ConfigFile(
            SubCommandWithThread.get_absolute_running_file_name(
                options, options.config_file))

        options.filter_out_sccs = True

        for arg in args:
            self.run_with_thread(  # pylint: disable=E1101
                options.job,
                RepoSubcmd.fetch_projects_in_manifest(options),
                RepoImportSubcmd.push, options, cfg,
                Logger.get_logger(),  # pylint: disable=E1101
                arg)

        return 0

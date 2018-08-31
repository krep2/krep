
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

from topics import Gerrit, Logger, RepoSubcmd, PkgImportSubcmd, \
    RaiseExceptionIfOptionMissed


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
        RepoSubcmd.options(self, optparse, inherited=True)
        PkgImportSubcmd.options(self, optparse, external=True)

    def get_name(self, options):
        return options.name or '[-]'

    @staticmethod
    def push(project, pattern, gerrit, options, remote, name, root, revision):
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        logger.info('Start processing ...')
        path = os.path.join(
            root, pattern.replace('loc,location', project.name))

        if path:
            if os.path.exists(path):
                _, tags = PkgImportSubcmd.do_import(
                    project, options, name, path, revision, None, logger)
            else:
                logger.error('Location "%s" is not existed')
                return
        else:
            logger.warning('No matched location for update')
            return

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
        SubCommand.execute(self, options, option_import=True, *args, **kws)

        logger = Logger.get_logger()  # pylint: disable=E1101

        RaiseExceptionIfOptionMissed(
            options.remote, 'remote (--remote) is not set')

        if options.prefix and not options.endswith('/'):
            options.prefix += '/'

        if not options.offsite:
            self.init_and_sync(options)

        ulp = urlparse(options.remote)
        if not ulp.scheme:
            remote = options.remote
            options.remote = 'git://%s' % options.remote
        else:
            remote = ulp.netloc.strip('/')

        gerrit = Gerrit(remote)
        projects = self.fetch_projects_in_manifest(options)

        return self.run_with_thread(  # pylint: disable=E1101
            options.job, projects, RepoImportSubcmd.push, gerrit, options, remote)

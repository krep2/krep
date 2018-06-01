
try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from topics import FileUtils, GitProject, SubCommand, DownloadError, \
    Gerrit, Pattern, ProcessingError, RaiseExceptionIfOptionMissed


class GitCloneSubcmd(SubCommand):
    COMMAND = 'git-p'
    help_summary = 'Download and import git repository'
    help_usage = """\
%prog [options] ...

Download git project and import to the remote server.

It supports to clone the full git repository outside and import the specified
branches and tags into the remote gerrit server.

If the remote server hasn't registered the named repository, a new gerrit
repository will be requested to create with the description.

The default description has the format "Mirror of GIT_URL". If option
"--no-description" is used, no description will be added. The description
could has a customized format like "Mirror of %url", which %url would be
replaced by GIT_URL."""

    def options(self, optparse):
        SubCommand.options(self, optparse, option_remote=True,
                           option_import=True, modules=globals())

        options = optparse.get_option_group('--refs') or \
            optparse.add_option_group('Remote options')
        options.add_option(
            '--git', '--git-url',
            dest='git', action='store', metavar='GIT_URL',
            help='Set the git repository url to download and import')
        options.add_option(
            '--rev', '--reversion', '--branch',
            dest='branch', action='store',
            help='Set the initial revisions to download')
        options = optparse.get_option_group('--all') or \
            optparse.add_option_group('Git options')
        options.add_option(
            '-n', '--name', '--project-name',
            dest='name', action='store', metavar='NAME',
            help='Set the project name or local url. If it\'s not set, the '
                 'name will be generated from the git name.')
        options.add_option(
            '--bare',
            dest='bare', action='store_true',
            help='Clone the bare repository')
        options.add_option(
            '-m', '--mirror',
            dest='mirror', action='store', metavar='LOCATION',
            help='Set the git repository mirror location')

    def get_name(self, options):
        # use options.name with a higher priority if it's set
        if options.name:
            self.set_name(options.name)  # pylint: disable=E1101
        else:
            ulp = urlparse(options.git or '')
            self.set_name(ulp.path.strip('/'))  # pylint: disable=E1101

        return SubCommand.get_name(self, options)

    def execute(self, options, *args, **kws):
        SubCommand.execute(self, options, *args, **kws)

        RaiseExceptionIfOptionMissed(
            options.git or options.offsite, 'git url (--git-url) is not set')

        ulp = urlparse(options.name or '')
        RaiseExceptionIfOptionMissed(
            ulp.scheme or options.remote,
            'Neither git name (--name) nor remote (--remote) is set')

        logger = self.get_logger()  # pylint: disable=E1101
        if ulp.scheme:
            remote = ulp.hostname
            projectname = ulp.path.strip('/')
        else:
            remote = options.remote
            projectname = self.get_name(options)  # pylint: disable=E1101

        remote = FileUtils.ensure_path(
            remote, prefix='git://', subdir=projectname, exists=False)

        working_dir = self.get_absolute_working_dir(options)  # pylint: disable=E1101
        project = GitProject(
            options.git,
            worktree=working_dir,
            gitdir=FileUtils.ensure_path(
                working_dir, subdir=None if options.bare else '.git'),
            revision=options.branch,
            remote=remote,
            bare=options.bare,
            pattern=Pattern(options.pattern))

        ret = 0
        if not options.offsite:
            ret = project.download(
                options.git, options.mirror, options.bare)
            if ret != 0:
                raise DownloadError('%s: failed to fetch project' % project)

        ulp = urlparse(remote)
        # creat the project in the remote
        if ulp.scheme in ('ssh', 'git'):
            if not options.dryrun and options.remote and options.repo_create:
                gerrit = Gerrit(options.remote)
                gerrit.create_project(
                    ulp.path.strip('/'),
                    description=options.description,
                    source=options.git,
                    options=options)
        else:
            raise ProcessingError(
                '%s: unknown scheme for remote "%s"' % (project, remote))

        self.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        # push the branches
        if self.override_value(  # pylint: disable=E1101
                options.all, options.branches):
            res = project.push_heads(
                options.branch,
                self.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                push_all=options.all,
                fullname=options.keep_name,
                skip_validation=options.skip_validation,
                force=options.force,
                dryrun=options.dryrun)

            ret |= res
            if res:
                logger.error('Failed to push heads')

        # push the tags
        if self.override_value(  # pylint: disable=E1101
                options.all, options.tags):
            res = project.push_tags(
                None if options.all else options.tag,
                self.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                skip_validation=options.skip_validation,
                fullname=options.keep_name,
                force=options.force,
                dryrun=options.dryrun)

            ret |= res
            if res:
                logger.error('Failed to push tags')

        self.do_hook(  # pylint: disable=E1101
            'post-push', options, dryrun=options.dryrun)

        return ret

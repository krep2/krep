
import os

from options import Values
from topics import FileUtils, GitProject, SubCommandWithThread, Gerrit, \
    RaiseExceptionIfOptionMissed


def secure_remote(remote):
    if remote and remote.endswith('.git'):
        return remote[:-4]
    else:
        return remote


class GitListImportSubcmd(SubCommandWithThread):
    COMMAND = 'git-list'
    ALIASES = ('gli',)

    help_summary = 'Import git bare repositories with list'
    help_usage = """\
%prog [options] ...

Import git mirror projects with a list to the remote server.

It supports to import the listed projects with the specified branches and
tags into the remote gerrit server.

If the remote server hasn't registered the named repository, a new gerrit
repository will be requested to create with the description."""

    def options(self, optparse):
        SubCommandWithThread.options(self, optparse, option_remote=True,
                                     option_import=True, modules=globals())

        options = optparse.add_option_group('File options')
        options.add_option(
            '--file', '--import-file',
            dest='file', action='store',
            help='Set the file list to import')

        options = optparse.add_option_group('Debug options')
        options.add_option(
            '--dump',
            dest='dump', action='store_true',
            help='Dump the provided project list')

    def push(self, name, remotes, gerrit, options):
        remote = remotes.get(name, name)

        working_dir = self.get_absolute_working_dir(options)  # pylint: disable=E1101
        project = GitProject(
            secure_remote(name),
            worktree=os.path.join(working_dir, name),
            gitdir=os.path.join(working_dir, name),
            revision=options.revision,
            remote='%s/%s' % (options.remote, remote),
            bare=name.endswith('.git'),
            pattern=SubCommandWithThread.get_patterns(options)  # pylint: disable=E1101
        )

        self.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        if options.repo_create:
            gerrit.create_project(
                remote, description=False, initial_commit=False,
                options=options)

        optgp = options.extra_values(options.extra_option, 'git-push')

        ret = 0
        logger = self.get_logger()  # pylint: disable=E1101

        # push the branches
        if self.override_value(  # pylint: disable=E1101
                options.all, options.heads):
            optp = Values.build(
                extra=optgp,
                push_all=options.all or options.revision is None,
                fullname=options.keep_name)

            res = project.push_heads(
                options.revision,
                self.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                options.head_pattern,
                options=optp,
                push_all=options.all or options.revision is None,
                fullname=options.keep_name,
                force=options.force,
                dryrun=options.dryrun)

            ret |= res
            if res:
                logger.error('Failed to push heads')

        # push the tags
        if self.override_value(  # pylint: disable=E1101
                options.all, options.tags):
            optp = Values.build(
                extra=optgp,
                fullname=options.keep_name)

            res = project.push_tags(
                None if options.all else options.tag,
                self.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                options.tag_pattern,
                options=optp,
                force=options.force,
                dryrun=options.dryrun)

            ret |= res
            if res:
                logger.error('Failed to push tags')

        self.do_hook(  # pylint: disable=E1101
            'post-push', options, dryrun=options.dryrun)

        return ret

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        RaiseExceptionIfOptionMissed(
            options.remote, 'remote (--remote) is not set')
        RaiseExceptionIfOptionMissed(
            options.file or len(args), 'file list (--file) is not set')

        projects = dict()
        if options.file:
            with open(options.file, 'r') as fp:
                for li in fp:
                    fields = li.strip().split(' -> ')
                    if len(fields) > 1:
                        projects[fields[0]] = secure_remote(fields[1])
                    else:
                        projects[fields[0]] = secure_remote(fields[0])

        if len(args):
            for arg in args:
                projects[arg] = secure_remote(arg)

        if options.dump:
            names = list(projects.keys())
            for name in sorted(names):
                remote = projects.get(name)
                if secure_remote(name) == remote:
                    print name
                else:
                    print '%s -> %s' % (name, remote)

            return 0

        return self.run_with_thread(  # pylint: disable=E1101
            options.job, list(projects.keys()), self.push, projects,
            Gerrit(options.remote, options), options)
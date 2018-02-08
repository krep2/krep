
import os
import urlparse

from topics import Command, FileUtils, GitProject, Gerrit, Manifest, \
    ManifestBuilder, Pattern, SubCommandWithThread, DownloadError, \
    RaiseExceptionIfOptionMissed


class RepoCommand(Command):
    """Executes a repo sub-command with specified parameters"""
    def __init__(self, *args, **kws):
        Command.__init__(self, *args, **kws)
        self.repo = FileUtils.find_execute('repo')

    def _execute(self, *args, **kws):
        cli = list()
        cli.append(self.repo)

        if len(args):
            cli.extend(args)

        self.new_args(cli, self.get_args())  # pylint: disable=E1101
        return self.wait(**kws)  # pylint: disable=E1101

    def init(self, *args, **kws):
        return self._execute('init', *args, **kws)

    def sync(self, *args, **kws):
        return self._execute('sync', *args, **kws)


class RepoSubcmd(SubCommandWithThread):
    COMMAND = 'repo'

    help_summary = 'Download and import git-repo manifest project'
    help_usage = """\
%prog [options] ...

Download the project managed with git-repo and import to the remote server.

The project need be controlled by git-repo (created with the command
"repo init" with the "--mirror" option, whose architecture guarantees the
managed sub-projects importing to the local server.

Not like the sub-command "repo-mirror", the manifest git would be handled with
this command.
"""

    def options(self, optparse, inherited=False):
        SubCommandWithThread.options(self, optparse, option_remote=True,
                                     option_import=True, modules=globals())

        options = optparse.add_option_group('Repo tool options')
        options.add_option(
            '-u', '--manifest-url',
            dest='manifest', metavar='URL',
            help='Set the git-repo manifest url')
        options.add_option(
            '-b', '--branch', '--manifest-branch',
            dest='manifest_branch', metavar='REVISION',
            help='Set the project branch or revision')
        options.add_option(
            '-m', '--manifest-name',
            dest='manifest_name', metavar='NAME.xml',
            help='initialize the manifest name')
        options.add_option(
            '--mirror',
            dest='mirror', action='store_true', default=False,
            help='Create a replica of the remote repositories')
        options.add_option(
            '--reference',
            dest='reference', metavar='REFERENCE',
            help='Set the local project mirror')
        options.add_option(
            '--repo-options',
            dest='repo_options', action='append', metavar='OPTIONS',
            help='Provides options to repo command. sub-command prefix with '
                 'colon can be used to provide the option to the command only')

        if not inherited:
            options = optparse.get_option_group('--remote') or \
                optparse.add_option_group('Remote options')
            options.add_option(
                '--prefix',
                dest='prefix', metavar='PREFIX',
                help='prefix on the remote location')

            options = optparse.add_option_group('Debug options')
            options.add_option(
                '--dump-projects',
                dest='dump_projects', action='store_true',
                help='Print the info of imported project')
            options.add_option(
                '--print-new-projects',
                dest='print_new_projects', action='store_true',
                help='Print the new projects which isn\'t managed by Gerrit')

            options = optparse.get_option_group('--force') or \
                optparse.add_option_group('Other options')
            options.add_option(
                '--output-xml-file',
                dest='output_xml_file', action='store', metavar='FILE',
                help='Set the output XML filename')

    @staticmethod
    def get_manifest(options, manifest=None, mirror=False):
        refsp = manifest
        if not refsp and options is not None:
            refsp = options.manifest

        working_dir = RepoSubcmd.get_absolute_working_dir(options)  # pylint: disable=E1101
        if not refsp:
            repo = GitProject(
                'repo-manifest',
                worktree=os.path.join(working_dir, '.repo/manifests'))
            _, refsp = repo.ls_remote('--get-url')

        if not manifest:
            manifest = os.path.realpath(
                os.path.join(working_dir, '.repo/manifest.xml'))

        return Manifest(
            filename=manifest,
            refspath=os.path.dirname(refsp),
            mirror=mirror or (options is not None and options.mirror))

    def fetch_projects_in_manifest(self, options):
        manifest = self.get_manifest(options)

        projects = list()
        logger = self.get_logger()  # pylint: disable=E1101
        pattern = Pattern(options.pattern)

        for node in manifest.get_projects():
            if not os.path.exists(node.path):
                logger.warning('%s not existed, ignored', node.path)
                continue
            elif not pattern.match('p,project', node.name):
                logger.debug('%s ignored by the pattern', node.name)
                continue

            name = '%s%s' % (
                options.prefix or '',
                pattern.replace('p,project', node.name, name=node.name))
            projects.append(
                GitProject(
                    name,
                    worktree=os.path.join(
                        self.get_absolute_working_dir(options), node.path),  # pylint: disable=E1101
                    revision='%s/%s' % (node.remote, node.revision),
                    remote='%s/%s' % (options.remote, name),
                    pattern=pattern,
                    source=node.name))

        return projects

    def init_and_sync(self, options):
        def _repo_options(cli, subcmd):
            if options.repo_options is not None and \
                    not isinstance(options.repo_options, list):
                options.repo_options = [options.repo_options]

            for opts in options.repo_options or list():
                for opt in opts.split(' '):
                    prefix = opt.split(':', 1)
                    if prefix[0] == subcmd and len(prefix) > 1:
                        cli.add_args(prefix[1])
                    elif prefix[0] == opt:
                        cli.add_args(opt)
        # pylint: disable=E1101
        self.run_hook(
            options.pop('hook-pre-init'),
            options.normalize('hook-pre-init-args', attr=True),
            cwd=self.get_absolute_working_dir(options),
            tryrun=options.tryrun)
        # pylint: enable=E1101
        res = 0
        if not os.path.exists('.repo'):
            RaiseExceptionIfOptionMissed(
                options.manifest, 'manifest (--manifest) is not set')
            repo = RepoCommand()
            # pylint: disable=E1101
            repo.add_args(options.manifest, before='-u')
            repo.add_args(options.manifest_branch, before='-b')
            repo.add_args(options.manifest_name, before='-m')
            repo.add_args('--mirror', condition=options.mirror)
            repo.add_args(options.reference, before='--reference')
            # pylint: enable=E1101
            _repo_options(repo, 'init')
            res = repo.init()

        if res:
            raise DownloadError(
                'Failed to init "%s"' % options.manifest)

        # pylint: disable=E1101
        self.run_hook(
            options.pop('hook-post-init'),
            options.normalize('hook-post-init-args', attr=True),
            cwd=self.get_absolute_working_dir(options),
            tryrun=options.tryrun)
        self.run_hook(
            options.pop('hook-pre-sync'),
            options.normalize('hook-pre-sync-args', attr=True),
            cwd=self.get_absolute_working_dir(options),
            tryrun=options.tryrun)
        # pylint: enable=E1101

        repo = RepoCommand()
        repo.add_args(options.job, before='-j')   # pylint: disable=E1101
        _repo_options(repo, 'sync')
        res = repo.sync()
        if res:
            if options.force:
                print 'Failed to sync "%s"' % options.manifest
            else:
                raise DownloadError(
                    'Failed to sync "%s"' % options.manifest)

        # pylint: disable=E1101
        self.run_hook(
            options.pop('hook-post-sync'),
            options.normalize('hook-post-sync-args', attr=True),
            cwd=self.get_absolute_working_dir(options),
            tryrun=options.tryrun)
        # pylint: enable=E1101

    @staticmethod
    def push(project, options, remote):
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        logger.info('Start processing ...')
        if not options.tryrun and remote:
            gerrit = Gerrit(remote)
            gerrit.create_project(project.uri)

        # pylint: disable=E1101
        RepoSubcmd.run_hook(
            options.pop('hook-pre-push'),
            options.normalize('hook-pre-push-args', attr=True),
            cwd=project.path,
            tryrun=options.tryrun)
        # pylint: enable=E1101

        # push the branches
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.branches, options.all):
            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                push_all=options.all,
                fullname=options.keep_name,
                force=options.force,
                tryrun=options.tryrun)
            if res != 0:
                logger.error('failed to push heads')

        # push the tags
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.tags, options.all):
            res = project.push_tags(
                None, RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                fullname=options.keep_name,
                force=options.force,
                tryrun=options.tryrun)
            if res != 0:
                logger.error('failed to push tags')

        # pylint: disable=E1101
        RepoSubcmd.run_hook(
            options.pop('hook-post-push'),
            options.normalize('hook-post-push-args', attr=True),
            cwd=project.path,
            tryrun=options.tryrun)
        # pylint: enable=E1101

    @staticmethod
    def build_xml_file(options, projects, sort=False):
        _project_key = lambda name, rev: '%s"%s' % (name, rev)

        projv = dict()
        manifest = RepoSubcmd.get_manifest(options)
        for project in manifest.get_projects():
            projv[_project_key(project.name, project.revision)] = (
                project.path, project.groups)

        builder = ManifestBuilder(
            options.output_xml_file,
            RepoSubcmd.get_absolute_working_dir(options),  # pylint: disable=E1101
            options.mirror)

        default = manifest.get_default()
        default.remote = options.remote
        builder.append(default)

        for remote in manifest.get_remotes():
            builder.append(remote)

        if sort:
            projects.sort(lambda prja, prjb: cmp(prja.path, prjb.path))

        for project in projects:
            path, groups = project.path, None

            key = _project_key(project.source, project.revision)
            if key in projv:
                path, groups = projv[key]

            builder.project(project.uri, path, project.revision, groups)

        builder.save()

    @staticmethod
    def dump_projects(options, projects, nprojects):
        def _cmp(prja, prjb):
            return cmp(prja.source, prjb.source)

        lsrc, luri = 0, 0
        if options.dump_projects:
            print 'IMPORTED PROJECTS'
            print '====================='
            for p in projects:
                if len(p.source) > lsrc:
                    lsrc = len(p.source)
                if len(p.uri) > luri:
                    luri = len(p.uri)

            sfmt = ' %%-%ds -> %%-%ds %%s' % (lsrc, luri)
            for project in sorted(projects, _cmp):
                print (
                    sfmt % (
                        project.source, project.uri,
                        ' [NEW]' if options.print_new_projects and
                        project in nprojects else '')).rstrip()
        elif options.print_new_projects:
            print 'NEW PROJECTS'
            print '================'
            for p in nprojects:
                if len(p.source) > lsrc:
                    lsrc = len(p.source)
                if len(p.uri) > luri:
                    luri = len(p.uri)

            sfmt = ' %%-%ds -> %%-%ds' % (lsrc, luri)
            for project in sorted(nprojects, _cmp):
                print (sfmt % (project.source, project.uri)).rstrip()
        elif not options.repo_create and len(nprojects) > 0:
            print 'Exit with following new projects:'
            for project in sorted(nprojects, _cmp):
                print ' %s' % project.source

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        if options.prefix and not options.endswith('/'):
            options.prefix += '/'

        if not options.offsite:
            self.init_and_sync(options)

        # handle the schema of the remote
        ulp = urlparse.urlparse(options.remote)
        if not ulp.scheme:
            remote = options.remote
            options.remote = 'git://%s' % options.remote
        else:
            remote = ulp.netloc.strip('/')

        projects = self.fetch_projects_in_manifest(options)

        if options.print_new_projects or options.dump_projects or \
                not options.repo_create:
            gerrit = Gerrit(remote)

            new_projects = list()
            existed_projects = gerrit.ls_projects()
            for p in projects:
                if p.uri not in existed_projects:
                    new_projects.append(p)

            if options.dump_projects or options.print_new_projects or \
                    not options.repo_create and len(new_projects) > 0:
                RepoSubcmd.dump_projects(options, projects, new_projects)
                return

        if options.output_xml_file:
            RepoSubcmd.build_xml_file(options, projects, True)
            return

        return self.run_with_thread(  # pylint: disable=E1101
            options.job, projects, RepoSubcmd.push, options, remote)

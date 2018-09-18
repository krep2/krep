
import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from topics import Command, FileUtils, GitProject, Gerrit, Manifest, \
    ManifestBuilder, Pattern, SubCommandWithThread, DownloadError, \
    RaiseExceptionIfOptionMissed


def sort_project(project):
    return project.source


def sort_project_path(project):
    return project.path


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

    extra_items = (
        ('Repo options for repo init:', (
            ('repo-init:platform',
             'restrict manifest projects to one platform'),
            ('repo-init:reference', 'location of mirror directory'),
            ('repo-init:no-clone-bundle',
             'disable use of /clone.bundle on HTTP/HTTPS'),
            ('repo-init:repo-url', 'repo repository location'),
            ('repo-init:repo-branch', 'repo branch or revision'),
            ('repo-init:no-repo-verify', 'do not verify repo source code'),
        )),
        ('Repo options for repo sync:', (
            ('repo-sync:force-broken',
             'continue sync even if a project fails'),
            ('repo-sync:current-branch', 'fetch only current branch'),
            ('repo-sync:jobs', 'projects to fetch simultaneously'),
            ('repo-sync:no-clone-bundle',
             'disable use of /clone.bundle on HTTP/HTTPS'),
            ('repo-sync:no-repo-verify', 'do not verify repo source code'),
            ('repo-sync:fetch-submodules', 'fetch submodules from server'),
            ('repo-sync:optimized-fetch', 'only fetch project fixed to sha1'),
            ('repo-sync:prune', 'delete refs that no longer exist on remote'),
            ('repo-sync:no-repo-verify', 'do not verify repo source code'),
        ))
    )

    def options(self, optparse, inherited=False, modules=None):
        SubCommandWithThread.options(
            self, optparse, option_remote=True,
            option_import=True, modules=modules or globals())

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
            help=optparse.SUPPRESS_HELP)

        if not inherited:
            options = optparse.get_option_group('--refs') or \
                optparse.add_option_group('Remote options')
            options.add_option(
                '--prefix',
                dest='prefix', action='store', metavar='PREFIX',
                help='prefix on the remote location')
            options.add_option(
                '--sha1-tag',
                dest='sha1_tag', action='store', metavar='TAG',
                help='Push named tag for the SHA-1 to the remote. It works '
                     'without the option "--all"')

            options = optparse.add_option_group('Debug options')
            options.add_option(
                '--dump-projects',
                dest='dump_projects', action='store_true',
                help='Print the info of imported project')
            options.add_option(
                '--print-new-projects',
                dest='print_new_projects', action='store_true',
                help='Print the new projects which isn\'t managed by Gerrit')

            options = optparse.add_option_group('Extra action options')
            options.add_option(
                '--convert-manifest-file',
                dest='convert_manifest_file', action='store_true',
                help='Do convert the manifest file with the manifest map file')

            options = optparse.get_option_group('--hook-dir') or \
                optparse.add_option_group('File options')
            options.add_option(
                '--manifest-xml-file',
                dest='manifest_xml_file', action='store', metavar='MANIFEST',
                default='.repo/manifest.xml',
                help='Set the manifest XML file to parse')
            options.add_option(
                '--output-xml-file',
                dest='output_xml_file', action='store', metavar='FILE',
                help='Set the output XML filename')
            options.add_option(
                '--map-file',
                dest='map_file', action='store', metavar='MAP_FILE',
                help='Set the manifest map file with patterns')

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
            if not options.manifest_xml_file:
                options.manifest_xml_file = '.repo/manifest.xml'

            manifest = RepoSubcmd.get_absolute_running_file_name(  # pylint: disable=E1101
                options, options.manifest_xml_file)

        return Manifest(
            filename=manifest,
            refspath=os.path.dirname(refsp),
            mirror=mirror or (options is not None and options.mirror))

    @staticmethod
    def fetch_projects_in_manifest(options, filename=None):
        manifest = RepoSubcmd.get_manifest(options, filename)

        projects = list()
        logger = RepoSubcmd.get_logger()  # pylint: disable=E1101
        pattern = RepoSubcmd.get_patterns(options)  # pylint: disable=E1101

        for node in manifest.get_projects():
            if not os.path.exists(node.path) and \
                    not options.convert_manifest_file:
                logger.warning('%s not existed, ignored', node.path)
                continue
            elif not pattern.match('p,project', node.name):
                logger.warning('%s ignored by the pattern', node.name)
                continue

            name = '%s%s' % (
                options.prefix or '',
                pattern.replace('p,project', node.name, name=node.name))

            project = GitProject(
                name,
                worktree=os.path.join(
                    RepoSubcmd.get_absolute_working_dir(options), node.path),  # pylint: disable=E1101
                remote='%s/%s' % (options.remote, name),
                pattern=pattern,
                source=node.name,
                copyfiles=node.copyfiles,
                linkfiles=node.linkfiles)

            if project.is_sha1(node.revision) and \
                    project.rev_existed(node.revision):
                project.revision = '%s' % node.revision
            else:
                project.revision = '%s/%s' % (node.remote, node.revision)

            projects.append(project)

        return projects

    def init_and_sync(self, options, offsite=False, update=True):
        self.do_hook(  # pylint: disable=E1101
            'pre-init', options, dryrun=options.dryrun)

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
            # pylint: enable=E1101

            opti = options.extra_values(options.extra_option, 'repo-init')
            if opti:
                # pylint: disable=E1101
                repo.add_args(opti.reference, before='--reference')
                repo.add_args(opti.platform, before='--platform')
                repo.add_args(
                    '--no-clone-bundle', condition=opti.no_clone_bundle)

                repo.add_args(opti.repo_url, before='--repo-url')
                repo.add_args(opti.repo_branch, before='--repo-branch')
                repo.add_args(
                    '--no-repo-verify', condition=opti.no_repo_verify)
                # pylint: enable=E1101

            res = repo.init()
        elif not update:
            return

        if res:
            raise DownloadError(
                'Failed to init "%s"' % options.manifest)

        # pylint: disable=E1101
        self.do_hook('post-init', options, dryrun=options.dryrun)
        self.do_hook('pre-sync', options, dryrun=options.dryrun)
        # pylint: enable=E1101

        repo = RepoCommand()
        opts = options.extra_values(options.extra_option, 'repo-sync')
        # pylint: disable=E1101
        if opts:
            repo.add_args(
                '--current-branch', condition=opts.current_branch)
            repo.add_args(
                '--force-broken', condition=opts.force_broken)
            repo.add_args(
                '--fetch-submodules', condition=opts.fetch_submodules)
            repo.add_args(
                '--optimized-fetch', condition=opts.optimized_fetch)
            repo.add_args('--prune', condition=opts.prune)
            repo.add_args(
                '--no-clone-bundle', condition=opts.no_clone_bundle)

        if opts.jobs:
            repo.add_args(opts.jobs, before='-j')
        else:
            repo.add_args(options.job, before='-j')
        # pylint: enable=E1101

        res = repo.sync()
        if res:
            if options.force:
                self.get_logger().error(  # pylint: disable=E1101
                    'Failed to sync "%s"' % options.manifest)
            else:
                raise DownloadError(
                    'Failed to sync "%s"' % options.manifest)

        self.do_hook(  # pylint: disable=E1101
            'post-sync', options, dryrun=options.dryrun)

    @staticmethod
    def push(project, gerrit, options, remote):
        project_name = str(project)
        logger = RepoSubcmd.get_logger(  # pylint: disable=E1101
            name=project_name)

        logger.info('Start processing ...')
        if not options.dryrun and remote:
            gerrit.create_project(project.uri, options=options)

        RepoSubcmd.do_hook(  # pylint: disable=E1101
            'pre-push', options, dryrun=options.dryrun)

        optgp = options.extra_values(options.extra_option, 'git-push')
        no_thin = optgp and optgp.boolean(optgp.no_thin)
        skip_validation = options.skip_validation or (
            optgp and optgp.boolean(optgp.skip_validation))

        # push the heads
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.heads, options.all):
            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                options.head_pattern,
                push_all=options.all or (
                    options.head_pattern and options.heads),
                fullname=options.keep_name,
                skip_validation=skip_validation,
                no_thin=no_thin,
                force=options.force,
                sha1tag=options.sha1_tag,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push heads')

        # push the tags
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.tags, options.all):
            res = project.push_tags(
                None, RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                options.tag_pattern,
                fullname=options.keep_name,
                skip_validation=skip_validation,
                no_thin=no_thin,
                force=options.force,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push tags')

        RepoSubcmd.do_hook(  # pylint: disable=E1101
            'post-push', options, dryrun=options.dryrun)

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
            projects.sort(key=sort_project_path)

        for project in projects:
            path, groups = project.path, None

            key = _project_key(project.source, project.revision)
            if key in projv:
                path, groups = projv[key]

            builder.project(
                project.uri, path, project.revision, groups,
                copyfiles=project.copyfiles, linkfiles=project.linkfiles)

        builder.save()

    @staticmethod
    def build_map_file(options, projects):
        with open(options.map_file, 'w') as fp:
            for project in projects:
                if project.uri != project.source:
                    fp.write('%s -> %s' % (project.uri, project.source))

    @staticmethod
    def do_convert_manifest(options):
        maps = dict()
        origins = dict()

        manifest = RepoSubcmd.get_manifest(options)
        for project in manifest.get_projects():
            origins[project.name] = project

        default = manifest.get_default()
        default.remote = options.remote

        builder = ManifestBuilder(
            options.output_xml_file,
            RepoSubcmd.get_absolute_working_dir(options))  # pylint: disable=E1101

        builder.append(default)

        for remote in manifest.get_remotes():
            builder.append(remote)

        projects = RepoSubcmd.fetch_projects_in_manifest(options)
        projects.sort(key=sort_project_path)

        if options.map_file:
            if not os.path.exists(options.map_file):
                RepoSubcmd.build_map_file(options, projects)

            if os.path.exists(options.map_file):
                with open(options.map_file, 'r') as fp:
                    for line in fp.readlines():
                        nname, _, origin = line.split(' ', 2)
                        maps[origin] = nname

        for project in projects:
            name = project.uri
            if name in maps:
                name = maps[name]

            builder.project(
                name, project.path, project.revision,
                origins[project.source].groups,
                copyfiles=project.copyfiles, linkfiles=project.linkfiles)

        builder.save()

    @staticmethod
    def dump_projects(options, projects, nprojects):
        lsrc, luri = 0, 0
        if options.dump_projects:
            print('IMPORTED PROJECTS (%d)' % len(projects))
            print('=========================')
            for p in projects:
                if len(p.source) > lsrc:
                    lsrc = len(p.source)
                if len(p.uri) > luri:
                    luri = len(p.uri)

            sfmt = ' %%-%ds %%s> %%-%ds%%s' % (lsrc, luri)
            for project in sorted(projects, key=sort_project):
                print((
                    sfmt % (
                        project.source,
                        '=' if project.source == project.uri else '-',
                        project.uri,
                        ' [NEW]' if options.print_new_projects and
                        project in nprojects else '')).rstrip())
        elif options.print_new_projects:
            if nprojects:
                print('NEW PROJECTS (%d)' % len(nprojects))
                print('====================')
                for p in nprojects:
                    if len(p.source) > lsrc:
                        lsrc = len(p.source)
                    if len(p.uri) > luri:
                        luri = len(p.uri)

                sfmt = ' %%-%ds %%s> %%-%ds' % (lsrc, luri)
                for project in sorted(nprojects, key=sort_project):
                    print((
                        sfmt % (
                            project.source,
                            '=' if project.source == project.uri else '-',
                            project.uri)).rstrip())
            else:
                print('No new project found')
        elif not options.repo_create and len(nprojects) > 0:
            print('Exit with following new projects (%d):'  % len(nprojects))
            for project in sorted(nprojects, key=sort_project):
                line = ' %s' % project.source
                if project.source != project.uri:
                    line += ' (%s)' % project.uri

                print(line)

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        if options.convert_manifest_file:
            return RepoSubcmd.do_convert_manifest(options)

        RaiseExceptionIfOptionMissed(
            options.remote, 'remote (--remote) is not set')

        if options.prefix and not options.endswith('/'):
            options.prefix += '/'

        self.init_and_sync(options, options.offsite)

        ulp = urlparse(options.remote)
        if not ulp.scheme:
            remote = options.remote
            options.remote = 'git://%s' % options.remote
        else:
            remote = ulp.netloc.strip('/')

        gerrit = Gerrit(remote)
        projects = self.fetch_projects_in_manifest(options)

        if options.print_new_projects or options.dump_projects or \
                not options.repo_create:

            new_projects = list()
            existed_projects = gerrit.ls_projects()
            for p in projects:
                if p.uri not in existed_projects:
                    new_projects.append(p)

            if options.dump_projects or options.print_new_projects or \
                    not options.repo_create and len(new_projects) > 0:
                RepoSubcmd.dump_projects(options, projects, new_projects)
                return

        if options.output_xml_file or options.map_file:
            if options.map_file:
                RepoSubcmd.build_map_file(options, projects)

            if options.output_xml_file:
                RepoSubcmd.build_xml_file(options, projects, True)

            return

        return self.run_with_thread(  # pylint: disable=E1101
            options.job, projects, RepoSubcmd.push, gerrit, options, remote)


import os

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from options import Values
from topics import DownloadError, FileUtils, Gerrit, GitProject, Manifest,  \
    ManifestBuilder, Pattern, RaiseExceptionIfOptionMissed, RepoProject, \
    SubCommandWithThread


def sort_project(project):
    return project.source


def sort_project_path(project):
    return project.path


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

            options = optparse.add_option_group('Other options')
            options.add_option(
                '--include-init-manifest',
                dest='include_init_manifest', action='store_true',
                help='Include .repo/manifests if mirror didn\'t contain it')

            options = optparse.add_option_group('Extra action options')
            options.add_option(
                '--convert-manifest-file',
                dest='convert_manifest_file', action='store_true',
                help='Do convert the manifest file with the manifest map file')
            options.add_option(
                '--ignore-new-project',
                dest='ignore_new_project', action='store_true',
                help='Ignore new projects and do import the git-repo project')

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
    def include_project_manifest(options, projects, pattern):
        if options.include_init_manifest:
            projects.append(
                GitProject(
                    None,
                    gitdir=os.path.join(
                        RepoSubcmd.get_absolute_working_dir(options),  # pylint: disable=E1101
                        '.repo/manifests.git'),
                    worktree=os.path.join(
                        RepoSubcmd.get_absolute_working_dir(options),  # pylint: disable=E1101
                        '.repo/manifests'),
                    pattern=pattern))

            # substitute project name after initialization
            projects[-1].update_(
                pattern.replace(
                    'project', projects[-1].uri, name=projects[-1].uri),
                options.remote)

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
            elif not pattern.match('project', node.name):
                logger.warning('%s ignored by the pattern', node.name)
                continue

            name = '%s%s' % (
                options.prefix or '',
                pattern.replace('project', node.name, name=node.name))

            project = GitProject(
                name,
                worktree=os.path.join(
                    RepoSubcmd.get_absolute_working_dir(options), node.path),  # pylint: disable=E1101
                remote='%s/%s' % (options.remote, name),
                pattern=pattern,
                source=node.name,
                copyfiles=node.copyfiles,
                linkfiles=node.linkfiles)

            if project.is_sha1(node.revision) or \
                    node.revision.startswith('refs/'):
                project.revision = '%s' % node.revision
            else:
                project.revision = '%s/%s' % (node.remote, node.revision)

            projects.append(project)

        RepoSubcmd.include_project_manifest(options, projects, pattern)

        return projects

    def init_and_sync(self, options, offsite=False, update=True):
        self.do_hook(  # pylint: disable=E1101
            'pre-init', options, dryrun=options.dryrun)

        res = 0
        repo = RepoProject(
            options.manifest,
            RepoSubcmd.get_absolute_working_dir(options),
            options.manifest_branch, options=options)

        if offsite:
            return repo
        if not repo.exists():
            RaiseExceptionIfOptionMissed(
                options.manifest, 'manifest (--manifest) is not set')

            res = repo.init()
        elif not update:
            return repo

        if res:
            raise DownloadError('Failed to init "%s"' % options.manifest)

        # pylint: disable=E1101
        self.do_hook('post-init', options, dryrun=options.dryrun)
        self.do_hook('pre-sync', options, dryrun=options.dryrun)
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

        return repo

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

        # push the heads
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.heads, options.all):
            optp = Values.build(
                extra=optgp,
                push_all=options.all or (
                    options.head_pattern and options.heads),
                fullname=options.keep_name,
                sha1tag=options.sha1_tag,
                git_repo=True,
                mirror=options.mirror)

            res = project.push_heads(
                project.revision,
                RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.head_refs),
                options.head_pattern,
                options=optp,
                force=options.force,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push heads')

        # push the tags
        if RepoSubcmd.override_value(  # pylint: disable=E1101
                options.tags, options.all):
            optp = Values.build(
                extra=optgp,
                fullname=options.keep_name)

            res = project.push_tags(
                None, RepoSubcmd.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs),
                options.tag_pattern,
                options=optp,
                force=options.force,
                dryrun=options.dryrun,
                logger=logger)
            if res != 0:
                logger.error('failed to push tags')

        RepoSubcmd.do_hook(  # pylint: disable=E1101
            'post-push', options, dryrun=options.dryrun)

    @staticmethod
    def build_xml_file(options, projects, sort=False):
        origins = dict()
        manifest = RepoSubcmd.get_manifest(options)
        for project in manifest.get_projects():
            origins[project.path] = project

        builder = ManifestBuilder(
            options.output_xml_file,
            RepoSubcmd.get_absolute_working_dir(options),  # pylint: disable=E1101
            options.mirror)

        default = manifest.get_default()
        builder.append(default)

        for remote in manifest.get_remotes():
            builder.append(remote)

        if sort:
            projects.sort(key=sort_project_path)

        for project in projects:
            revision = project.revision
            if revision.startswith(default.remote + '/'):
                 revision = revision[len(default.remote) + 1]

            path = project.path.replace(
                RepoSubcmd.get_absolute_working_dir(options) + '/', '')

            builder.project(
                name=project.uri, path=path, revision=revision,
                remote=origins[path].remote,
                groups=origins[path].groups,
                upstream=origins[path].upstream,
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
            origins[project.path] = project

        builder = ManifestBuilder(
            options.output_xml_file,
            RepoSubcmd.get_absolute_working_dir(options))  # pylint: disable=E1101

        default = manifest.get_default()
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

            path = project.path.replace(
                RepoSubcmd.get_absolute_working_dir(options) + '/', '')

            builder.project(
                name=name, path=path, revision=project.revision,
                remote=origins[path].remote,
                groups=origins[path].groups,
                upstream=origins[path].upstream,
                copyfiles=project.copyfiles, linkfiles=project.linkfiles)

        builder.save()

    @staticmethod
    def dump_projects(options, projects, nprojects, ignore_new=False):
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
            print('%s with following new projects (%d):'  % (
                  'Ignore' if ignore_new else 'Exit', len(nprojects)))

            for project in sorted(nprojects, key=sort_project):
                line = ' %s' % project.source
                if project.source != project.uri:
                    line += ' (%s)' % project.uri

                print(line)

            if ignore_new:
                return False

        return True

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        if options.convert_manifest_file:
            return RepoSubcmd.do_convert_manifest(options)

        RaiseExceptionIfOptionMissed(
            options.remote, 'remote (--remote) is not set')

        if options.prefix and not options.prefix.endswith('/'):
            options.prefix += '/'

        repo = self.init_and_sync(options, options.offsite)

        ulp = urlparse(options.remote)
        if not ulp.scheme:
            remote = options.remote
            options.remote = 'git://%s' % options.remote
        else:
            remote = ulp.netloc.strip('/')

        gerrit = Gerrit(remote, options)
        projects = self.fetch_projects_in_manifest(options)

        if options.print_new_projects or options.dump_projects or \
                not options.repo_create:

            new_projects = list()
            for p in projects:
                if not gerrit.has_project(p.source) and \
                        not gerrit.has_project(p.uri):
                    new_projects.append(p)

            if options.dump_projects or options.print_new_projects or \
                    not options.repo_create and len(new_projects) > 0:
                if RepoSubcmd.dump_projects(
                        options, projects, new_projects,
                        options.ignore_new_project):
                    return

            # remove the new projects if option is set
            if options.ignore_new_project:
                for project in new_projects:
                    projects.remove(project)

        if options.output_xml_file or options.map_file:
            if options.output_xml_file:
                RepoSubcmd.build_xml_file(options, projects, True)
            else:
                RepoSubcmd.build_map_file(options, projects)

            return

        return self.run_with_thread(  # pylint: disable=E1101
            options.job, projects, RepoSubcmd.push, gerrit, options, remote)

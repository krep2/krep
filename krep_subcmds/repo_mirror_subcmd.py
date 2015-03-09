
import os
import urlparse

from repo_subcmd import RepoSubcmd
from topics import GitProject


class RepoMirrorSubcmd(RepoSubcmd):
    REMOTE = ''
    COMMAND = 'repo-mirror'

    help_summary = 'Download and import git-repo mirror project'
    help_usage = """\
%prog [options] ...

Download the mirror project managed with git-repo and import to the local
server.

The project need be controlled by git-repo and should be a mirrored project,
(created with the command line "repo init ... --mirror") whose architecture
guarantees the managed sub-projects importing to the local server.

All projects inside .repo/default.xml will be managed and imported. Exactly,
the manifest git will be detected and converted to the actual location to
import either. (For example, the android manifest git in .repo/manifests is
acutally in platform/manifest.git within a mirror.)
"""

    def options(self, optparse):
        RepoSubcmd.options(self, optparse)
        optparse.remove_option('--mirror')

    def fetch_projects_in_manifest(self, options):
        manifest = self.get_manifest(options)

        projects = list()
        logger = self.get_logger()  # pylint: disable=E1101

        # add the manifest, which isn't inside the xml file
        manp = GitProject(
            '.repo/manifests',
            worktree=os.path.join(options.working_dir, '.repo/manifests'),
            gitdir=os.path.join(options.working_dir, '.repo/manifests.git'))

        ret, url = manp.config('--get', 'remote.origin.url')
        if ret == 0:
            ulp = urlparse.urlparse(url)
            name = ulp.path.strip('/')
            projects.append(
                GitProject(
                    '%s%s' % (options.prefix or '', name),
                    worktree=os.path.join(
                        options.working_dir, '%s.git' % name),
                    gitdir=os.path.join(
                        options.working_dir, '%s.git' % name),
                    revision=options.repo_branch or None,
                    remote='%s/%s' % (options.remote, name)))

        for node in manifest.get_projects():
            path = os.path.join(options.working_dir, '%s.git' % node.name)
            if not os.path.exists(path):
                logger.warning('%s not existed, ignored' % path)
                continue

            projects.append(
                GitProject(
                    '%s%s' % (options.prefix or '', node.name),
                    worktree=path,
                    gitdir=path,
                    revision=node.revision,
                    remote='%s/%s' % (options.remote, node.name),
                    bare=True))

        return projects

    def execute(self, options, *args, **kws):
        options.mirror = True
        RepoSubcmd.execute(self, options, *args, **kws)

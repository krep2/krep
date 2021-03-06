
import os

from repo_cmd import RepoCommand
from project import Project


class RepoProject(Project, RepoCommand):

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
            ('repo-sync:force-sync', 'overwrite an existing git stuffs'),
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

    def __init__(self, uri, path=None, revision=None, remote=None,
                 options=None, *args, **kws):
        Project.__init__(self, uri, path, revision, remote, *args, **kws)
        RepoCommand.__init__(self, *args, **kws)

        self.options = options

    def exists(self):
        return os.path.isdir(os.path.join(self.path, '.repo'))

    def init(self, *args, **kws):
        self.new_args()
        self.add_args(self.options.manifest, before='-u')
        self.add_args(self.options.manifest_branch, before='-b')
        self.add_args(self.options.manifest_name, before='-m')
        self.add_args('--mirror', condition=self.options.mirror)

        opti = self.options.extra_values(
            self.options.extra_option, 'repo-init')
        if opti:
            self.add_args(opti.reference, before='--reference')
            self.add_args(opti.platform, before='--platform')
            self.add_args(
                '--no-clone-bundle', condition=opti.no_clone_bundle)

            self.add_args(opti.repo_url, before='--repo-url')
            self.add_args(opti.repo_branch, before='--repo-branch')
            self.add_args(
                '--no-repo-verify', condition=opti.no_repo_verify)

        return RepoCommand.init(self, *args, **kws)

    def sync(self, *args, **kws):
        self.new_args()

        opts = self.options.extra_values(
            self.options.extra_option, 'repo-sync')

        force_sync = self.options.force
        # pylint: disable=E1101
        if opts:
            if opts.force_sync:
                force_sync = True

            self.add_args(
                '--current-branch', condition=opts.current_branch)
            self.add_args(
                '--force-broken', condition=opts.force_broken)
            self.add_args(
                '--fetch-submodules', condition=opts.fetch_submodules)
            self.add_args(
                '--optimized-fetch', condition=opts.optimized_fetch)
            self.add_args('--prune', condition=opts.prune)
            self.add_args(
                '--no-clone-bundle', condition=opts.no_clone_bundle)

        self.add_args('--force-sync', condition=force_sync)

        if opts.jobs:
            self.add_args(opts.jobs, before='-j')
        else:
            self.add_args(self.options.job, before='-j')

        return RepoCommand.sync(self, *args, **kws)


TOPIC_ENTRY = "RepoProject"

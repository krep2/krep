
import os
import re

from error import DownloadError, ProcessingError
from git_cmd import GitCommand
from logger import Logger
from project import Project


def _sha1_equals(sha, shb):
    if sha and shb:
        return sha.startswith(shb) or shb.startswith(sha)
    else:
        return sha == shb


class GitProject(Project, GitCommand):
    """Manages the git repository as a project"""
    def __init__(self, uri, worktree=None, gitdir=None, revision='master',
                 remote=None, pattern=None, bare=False, *args, **kws):
        self.bare = bare

        if not worktree:
            if bare and gitdir:
                worktree = gitdir
            elif uri:
                worktree = os.path.basename(uri)

        if bare and not gitdir and worktree:
            gitdir = worktree

        # gitdir will be secured before executing the command per time
        GitCommand.__init__(self, gitdir, worktree, *args, **kws)
        Project.__init__(self, uri, worktree, revision, remote, pattern)

    def init(self, bare=False, *args, **kws):
        cli = list()
        if bare:
            cli.append('--bare')

        if len(args):
            cli.extend(args)

        return GitCommand.init(self, *cli, **kws)

    def clone(self, url=None, mirror=None, bare=False, *args, **kws):
        cli = list()
        cli.append(url or self.remote)

        logger = Logger.get_logger()
        if self.revision:
            cli.append('--branch=%s' % self.revision)
        else:
            logger.warning(
                '%s: branch/revision is null, the default branch '
                'will be used by the git (server)', self.uri)

        if bare:
            cli.append('--bare')
        if mirror:
            cli.append('--reference=%s' % mirror)

        # FIXME: check if the snippet below can be removed
        if bare:
            cli.append(self.gitdir)
        else:
            cli.append(self.worktree)

        if len(args):
            cli.extend(args)

        return GitCommand.clone(self, *cli, **kws)

    def download(self, url=None, mirror=False, bare=False, *args, **kws):
        if self.gitdir and os.path.isdir(self.gitdir) \
                and os.listdir(self.gitdir):
            ret, get_url = self.ls_remote('--get-url')
            if ret and url and get_url != url.strip('/'):
                raise ProcessingError(
                    '%s: different url "%s" with existed git "%s"',
                    self.uri, url, get_url)

            ret = self.fetch('--all', *args, **kws)
        else:
            if url is None:
                url = self.remote

            ret = self.clone(url, mirror=mirror, bare=bare, *args, **kws)

        return ret

    def get_remote_tags(self):
        tags = list()
        ret, result = self.ls_remote('--tags', self.remote)
        if ret == 0 and result:
            for e in result.split('\n'):
                tags.append(e.split()[1])

        return ret, tags

    def get_remote_heads(self):
        heads = dict()

        ret, result = self.ls_remote('--heads', self.remote)
        if ret == 0 and result:
            for line in result.split('\n'):
                line = line.strip()
                if not line:
                    continue

                sha1, head = re.split(r'\s+', line, maxsplit=1)
                heads[head] = sha1

        return ret, heads

    def get_local_heads(self, local=False):
        heads = dict()
        ret, lines = self.branch('-lva')
        if ret == 0:
            for line in lines.split('\n'):
                line = line.strip()
                if line.startswith('*'):
                    if self.bare or local:
                        line = line[1:].lstrip()
                    else:
                        continue
                elif not line:
                    continue

                head = re.split(r'[\s]+', line, maxsplit=2)
                if head[1] != '->':
                    heads[head[0]] = head[1]

        return ret, heads

    def get_local_tags(self):
        tags = list()
        ret, lines = self.tag('--list')
        if ret == 0:
            for line in lines.split('\n'):
                tags.append(line.strip())

        return ret, tags

    def rev_existed(self, rev):
        ret, _ = self.rev_parse(rev, capture_stderr=False)

        return ret == 0

    def push_heads(self, branch=None, refs=None, push_all=False,
                   fullname=False, force=False, *args, **kws):
        logger = Logger.get_logger()

        refs = refs and '%s/' % refs.rstrip('/')
        ret, local_heads = self.get_local_heads()
        ret, remote_heads = self.get_remote_heads()

        if not push_all:
            local_heads = {branch or '': local_heads.get(branch)}

        # put 'master' to end of the list
        def rev_sort(rev1, rev2):
            if rev1 == 'master':
                return 1
            elif rev2 == 'master':
                return -1
            else:
                return cmp(rev1, rev2)

        for origin in sorted(local_heads, rev_sort):
            head = origin
            if not fullname:
                head = os.path.basename(head)
            if not head:
                continue

            if not self.pattern.match(
                    'r,rev,revision', origin, name=self.uri):
                logger.debug('"%s" do not match revision pattern', origin)
                continue
            elif not self.pattern.match('r,rev,revision', head, name=self.uri):
                logger.debug('"%s" do not match revision pattern', head)
                continue

            if not self.bare and not origin.startswith('remotes/'):
                local_ref = 'refs/remotes/%s' % origin
            elif origin.startswith('remotes/'):
                local_ref = 'refs/%s' % origin
            else:
                local_ref = 'refs/heads/%s' % origin

            if not self.rev_existed(local_ref):
                local_ref = 'refs/heads/%s' % origin
                if not self.rev_existed(local_ref):
                    logger.error('"%s" has no matched rev', origin)
                    continue

            if not self.pattern.match(
                    'r,rev,revision', local_ref, name=self.uri):
                logger.debug('"%s" do not match revision pattern', local_ref)
                continue

            if fullname:
                heads = head.split('/')
                while len(heads) > 1 and heads[0] in ('remotes', 'origin'):
                    heads = heads[1:]

                head = '/'.join(heads)

            remote_ref = 'refs/heads/%s' % self.pattern.replace(
                'r,rev,revision', '%s%s' % (refs or '', head),
                name=self.uri)

            sha1 = local_heads[origin]
            if not force and _sha1_equals(remote_heads.get(remote_ref), sha1):
                logger.info('%s has been up-to-dated', remote_ref)
                continue

            ret = self.push(
                self.remote,
                '%s%s:%s' % (
                    '+' if force else '', local_ref, remote_ref),
                *args, **kws)

            if ret != 0:
                logger.error('error to execute git push to %s', self.remote)

        return ret

    def push_tags(self, tags=None, refs=None, force=False, fullname=False,
                  *args, **kws):
        logger = Logger.get_logger()

        refs = refs and '%s/' % refs.rstrip('/')
        ret, remote_tags = self.get_remote_tags()

        local_tags = list()
        if not tags:
            ret, local_tags = self.get_local_tags()
        elif isinstance(tags, (list, tuple)):
            local_tags.extend(tags)
        else:
            local_tags.append(tags)

        for origin in local_tags:
            tag = origin
            if not fullname:
                tag = os.path.basename(tag)
            if not tag:
                continue

            if not self.pattern.match('t,tag,revision', origin, name=self.uri):
                logger.debug('%s: "%s" not match tag pattern', origin, origin)
                continue
            elif not self.pattern.match('t,tag,revision', tag, name=self.uri):
                logger.debug('%s: "%s" not match tag pattern', origin, tag)
                continue

            rtags = 'refs/tags/%s' % self.pattern.replace(
                't,tag,revision', '%s%s' % (refs or '', tag), name=self.uri)

            if not force and rtags in remote_tags:
                logger.info('%s is up-to-date', rtags)
                continue

            ret = self.push(
                self.remote,
                '%srefs/tags/%s:%s' % (
                    '+' if force else '', origin, rtags),
                *args, **kws)

            if ret != 0:
                logger.error('%s: cannot push tag "%s"', self.remote, rtags)

        return ret

    def init_or_download(self, revision=None, default='master', offsite=False):
        logger = Logger.get_logger()

        if not revision:
            revision = self.revision

        if offsite:
            ret = self.init()
            ret &= self.commit(
                ['--allow-empty', '--no-edit', '-m',
                 'Init the empty repository'])
        elif self.remote:
            logger.info('Clone %s', self)
            ret = self.download(self.remote)
            if ret != 0 and self.revision != default:
                self.revision = default
                ret = self.download(self.remote)
        else:
            raise DownloadError('Remote is not defined')

        rbranches = list()
        if not offsite:
            ret, branches = self.get_remote_heads()
            if ret:
                rbranches.extend(branches)

        if ret == 0:
            ret, branches = self.get_local_heads(local=True)
            if ret == 0:
                rbranches.extend(branches)

        if ret == 0:
            for branch in rbranches:
                if branch in (revision, 'refs/heads/%s' % revision):
                    self.checkout(revision)
                    self.revision = revision
                    break
            else:
                self.revision = default

        if self.revision != revision:
            ret, parent = self.rev_list('--max-parents=0', 'HEAD')
            ret, _ = self.branch(revision, parent)
            if ret != 0:
                raise DownloadError(
                    '%s: failed to create branch: "%s"', self, revision)

            ret = self.checkout(revision)
            if ret != 0:
                raise DownloadError(
                    '%s: failed to checkout "%s"', self, revision)

        return ret


TOPIC_ENTRY = 'GitProject'

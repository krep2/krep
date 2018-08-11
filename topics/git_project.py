
import os
import re

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from error import DownloadError, ProcessingError
from git_cmd import GitCommand
from logger import Logger
from project import Project


def _sha1_equals(sha, shb):
    if sha and shb:
        return sha.startswith(shb) or shb.startswith(sha)
    else:
        return sha == shb


def _ensure_remote(url):
    if url:
        ulp = urlparse(url)
        if not ulp.scheme:
            url = 'git://' + url
        url = re.sub(r'://[^\/@]+@', '://', url)

    return url


def _secure_head_name(head):
    heads = head.split('/')
    while len(heads) > 1 and heads[0] in ('remotes', 'origin'):
        heads = heads[1:]

    return '/'.join(heads)


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
        Project.__init__(
            self, uri, worktree, revision, _ensure_remote(remote),
            pattern, *args, **kws)

    def init(self, bare=False, *args, **kws):
        cli = list()
        if bare:
            cli.append('--bare')

        if len(args):
            cli.extend(args)

        return GitCommand.init(self, notdir=True, *cli, **kws)

    def clone(self, url=None, mirror=None, bare=False,
              revision=None, single_branch=False, *args, **kws):
        cli = list()
        cli.append(url or self.remote)

        logger = Logger.get_logger()

        if not revision:
            revision = self.revision

        if revision:
            cli.append('--branch=%s' % revision)
        else:
            logger.warning(
                '%s: branch/revision is null, the default branch '
                'will be used by the git (server)', self.uri)

        if mirror:
            cli.append('--reference=%s' % mirror)
        if single_branch:
            cli.append('--single-branch')

        if bare:
            cli.append('--bare')

        if bare and self.gitdir:
            cli.append(self.gitdir)
        else:
            cli.append(self.worktree)

        if len(args) > 0:
            cli.extend(args)

        return GitCommand.clone(self, notdir=True, *cli, **kws)

    def download(self, url=None, mirror=False, bare=False,
                 revision=None, single_branch=False, *args, **kws):
        if self.gitdir and os.path.isdir(self.gitdir) \
                and os.listdir(self.gitdir):
            ret, get_url = self.ls_remote('--get-url')
            if ret and url and get_url != url.strip('/'):
                raise ProcessingError(
                    '%s: different url "%s" with existed git "%s"',
                    self.uri, url, get_url)

            cli = list()
            cli.append('origin')
            cli.append('--progress')
            if self.bare:
                cli.append('--update-head-ok')
            cli.append('--tags')
            cli.append('+refs/heads/*:refs/heads/*')
            cli.extend(args)
            ret = self.fetch(*cli, **kws)
        else:
            if url is None:
                url = self.remote
            ret = self.clone(
                _ensure_remote(url), mirror=mirror, bare=bare,
                revision=revision, single_branch=single_branch, *args, **kws)

        if ret == 0:
            self.revision = revision

        return ret

    def get_remote_tags(self, remote=None):
        tags = dict()
        ret, result = self.ls_remote('--tags', remote or self.remote)
        if ret == 0 and result:
            for line in result.split('\n'):
                sha1, tag = re.split(r'\s+', line, maxsplit=1)
                tags[tag] = sha1

        return ret, tags

    def get_remote_heads(self, remote=None):
        heads = dict()

        ret, result = self.ls_remote('--heads', remote or self.remote)
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
                if re.search('^\s*remotes/.*/HEAD', line):
                    continue
                elif line.startswith('*'):
                    line = line[1:].lstrip()
                    if line.startswith('(HEAD detached at '):
                        continue
                    elif not (self.bare or local):
                        continue
                elif not line:
                    continue

                if line.startswith('(no branch)'):
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

    @staticmethod
    def is_sha1(sha1):
        return re.match('^[0-9a-f]{6,40}$', sha1)

    def rev_existed(self, rev):
        ret, _ = self.rev_parse(rev, capture_stderr=False)

        return ret == 0

    def push_heads(self, branch=None, refs=None, push_all=False,  # pylint: disable=R0915
                   fullname=False, skip_validation=False,
                   force=False, sha1tag=None, *args, **kws):
        logger = Logger.get_logger()

        refs = refs and '%s/' % refs.rstrip('/')
        ret, local_heads = self.get_local_heads(local=True)
        ret, remote_heads = self.get_remote_heads()
        ret, remote_tags = self.get_remote_tags()

        if not push_all:
            local_heads = {
                branch or '': branch if self.is_sha1(branch) \
                    else local_heads.get(branch)}

        for origin in local_heads:
            head = _secure_head_name(origin)

            if head != origin and head in local_heads:
                continue

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

            if self.rev_existed(origin):
                local_ref = '%s' % origin
            else:
                local_ref = 'refs/%s' % origin

            if not self.rev_existed(local_ref):
                local_ref = 'refs/heads/%s' % origin
                if not self.rev_existed(local_ref):
                    logger.error('"%s" has no matched revision', origin)
                    continue

            if not self.pattern.match(
                    'r,rev,revision', local_ref, name=self.uri):
                logger.debug('"%s" do not match revision pattern', local_ref)
                continue

            rhead = self.pattern.replace(
                'r,rev,revision', '%s' % head, name=self.uri)
            if rhead != head:
                rhead = '%s%s' % (refs or '', rhead)
            else:
                rhead = self.pattern.replace(
                    'r,rev,revision', '%s%s' % (refs or '', head),
                    name=self.uri)

            skip = False
            sha1 = local_heads[origin]
            remote_ref = 'refs/heads/%s' % rhead
            if os.path.basename(remote_ref) == sha1:
                logger.warning(
                    "remote branch %s equals to an existed SHA-1, which "
                    "isn't normal. Ignoring ...", remote_ref)
                skip = True
            elif _sha1_equals(remote_heads.get(remote_ref), sha1):
                logger.info('%s has been up-to-dated', remote_ref)
                skip = True

            ret = 0
            if not skip:
                if skip_validation:
                    ret = self.push(
                        self.remote,
                        '-o', 'skip-validation',
                        '%s%s:%s' % (
                            '+' if force else '', local_ref, remote_ref),
                        *args, **kws)
                else:
                    ret = self.push(
                        self.remote,
                        '%s%s:%s' % (
                            '+' if force else '', local_ref, remote_ref),
                        *args, **kws)

            if ret == 0 and not push_all and (
                    sha1tag and self.is_sha1(origin)):
                equals = False
                if sha1tag in remote_tags:
                    sha1 = remote_tags[sha1tag]
                    equals = _sha1_equals(sha1, origin)

                if not equals or force:
                    if skip_validation:
                        ret = self.push(
                            self.remote,
                            '-o', 'skip-validation',
                            '%s%s:refs/tags/%s' % (
                                '+' if force else '', local_ref, sha1tag),
                            *args, **kws)
                    else:
                        ret = self.push(
                            self.remote,
                            '%s%s:refs/tags/%s' % (
                                '+' if force else '', local_ref, sha1tag),
                            *args, **kws)

            if ret != 0:
                logger.error('error to execute git push to %s', self.remote)

        return ret

    def push_tags(self, tags=None, refs=None, force=False, fullname=False,
                  skip_validation=False, *args, **kws):
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

        if not (tags or self.pattern) and fullname:
            if skip_validation:
                ret = self.push(
                    self.remote,
                    '-o', 'skip-validation',
                    '%srefs/tags/*:refs/tags/%s*' % (
                        '+' if force else '', refs),
                    *args, **kws)
            else:
                ret = self.push(
                    self.remote,
                    '%srefs/tags/*:refs/tags/%s*' % (
                        '+' if force else '', refs),
                    *args, **kws)

            return ret

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

            rtag = self.pattern.replace(
                't,tag,revision', '%s' % tag, name=self.uri)
            if rtag != tag:
                rtag = '%s%s' % (refs or '', rtag)
            else:
                rtag = self.pattern.replace(
                    't,tag,revision', '%s%s' % (refs or '', tag),
                    name=self.uri)

            remote_tag = 'refs/tags/%s' % rtag
            if remote_tag in remote_tags:
                equals = True
                if force:
                    sha1 = remote_tags[remote_tag]
                    ret, lsha1 = self.rev_parse(origin)
                    equals = _sha1_equals(sha1, lsha1)

                if equals:
                    logger.info('%s is up-to-date', remote_tag)
                    continue

            if skip_validation:
                ret = self.push(
                    self.remote,
                    '-o', 'skip-validation',
                    '%srefs/tags/%s:%s' % (
                        '+' if force else '', origin, remote_tag),
                    *args, **kws)
            else:
                ret = self.push(
                    self.remote,
                    '%srefs/tags/%s:%s' % (
                        '+' if force else '', origin, remote_tag),
                    *args, **kws)

            if ret != 0:
                logger.error(
                    '%s: cannot push tag "%s"', self.remote, remote_tag)

        return ret

    def init_or_download(self, revision='master', single_branch=True,
                         offsite=False):
        logger = Logger.get_logger()

        if not revision:
            revision = self.revision

        if offsite:
            ret = self.init()
            ret &= self.commit(
                '--allow-empty', '--no-edit', '-m', 'Init the empty repository')
        elif self.remote:
            logger.info('Clone %s', self)

            ret, branches = self.get_remote_heads()
            if ret == 0:
                for branch in branches:
                    if branch in (revision, 'refs/heads/%s' % revision):
                        ret = self.download(
                            self.remote, revision=revision,
                            single_branch=single_branch)
                        break
                else:
                    ret = self.download(
                        self.remote, revision='master',
                        single_branch=single_branch)

        if ret == 0 and self.revision != revision:
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

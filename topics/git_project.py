
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
    CATEGORY_TAGS = 'tag'
    CATEGORY_REVISION = 'revision'
    CATEGORY_PROJECT = 'project'

    extra_items = (
        ('Git options for git-clone:', (
            ('git-clone:reference', 'Set reference repository'),
        )),
        ('Git options for git-commit:', (
            ('git-commit:author', 'Update the commit author'),
            ('git-commit:date', 'Update the commit time'),
        )),
        ('Git options for git-push:', (
            ('git-push:no-thin', 'Don\'t use thin transfer'),
            ('git-push:skip-validation', 'Don\'t validate the commit number'),
        )),
    )

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

        if uri is None:
            ret, url = self.ls_remote('--get-url')
            if ret == 0:
                ulp = urlparse(url)
                uri = ulp.path.lstrip('/')

        Project.__init__(
            self, uri, worktree, revision, _ensure_remote(remote),
            pattern, *args, **kws)

    def update_(self, name, remote=None):
        if remote:
            Project.update(
                self, name, _ensure_remote('%s/%s' % (remote, name)))
        else:
            Project.update(self, name)

    def init(self, bare=False, *args, **kws):
        cli = list()
        if bare:
            cli.append('--bare')

        if len(args):
            cli.extend(args)

        return GitCommand.init(self, notdir=True, *cli, **kws)

    def clone(self, url=None, reference=None, bare=False,
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

        if reference:
            cli.append('--reference=%s' % reference)
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

    def download(self, url=None, reference=False, bare=False,
                 revision=None, single_branch=False, *args, **kws):
        if self.exists_() and os.listdir(self.gitdir):
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
            if bare:
                ret = self.fetch(*cli, **kws)
        else:
            if url is None:
                url = self.remote
            ret = self.clone(
                _ensure_remote(url), reference=reference, bare=bare,
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

    def get_local_heads(self, local=False, git_repo=False):
        heads = dict()
        ret, lines = self.branch('-lva')
        if ret == 0:
            for line in lines.split('\n'):
                line = line.strip()
                if re.search(r'^remotes/.*/HEAD', line):
                    continue
                elif line.startswith('remotes/m/') and git_repo:
                    # created by git-repo, ignore
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
        tags = dict()
        ret, lines = self.show_ref('--tags')
        if ret == 0:
            for line in lines.split('\n'):
                match = re.split(r'\s+', line)
                tags[match[1].replace('refs/tags/', '')] = match[0]

        return ret, tags

    @staticmethod
    def is_sha1(sha1):
        return re.match('^[0-9a-f]{6,40}$', sha1)

    def rev_existed(self, rev):
        ret, _ = self.rev_parse(rev, capture_stderr=False)

        return ret == 0

    @staticmethod
    def has_name_changes(names, keepname=False):
        if keepname:
            return False

        for name in names:
            if os.path.basename(name) != name:
                return True

        return False

    @staticmethod
    def _push_args(parameters, options, *args):
        if options and options.skip_validation:
            parameters.extend(['-o', 'skip-validation'])
        if options and options.no_thin:
            parameters.append('--no-thin')

        if len(args):
            parameters.extend(args)

        return parameters

    def build_heads(  # pylint: disable=R0915
            self, branch=None, refs=None, patterns=None, options=None,
            force=False, logger=None, *args, **kws):
        if not logger:
            logger = Logger.get_logger()

        prefs = list()
        if self.pattern.has_category(GitProject.CATEGORY_PROJECT) and (
                not self.pattern.match(GitProject.CATEGORY_PROJECT,
                                       self.source, name=self.source,
                                       strict=True) or
                not self.pattern.match(GitProject.CATEGORY_PROJECT,
                                       self.uri, name=self.uri, strict=True)):
            logger.info('project is excluded to push heads')
            return prefs

        if patterns and not isinstance(patterns, (list, tuple)):
            patterns = [patterns]

        refs = (refs and '%s/' % refs.rstrip('/')) or ''
        ret, local_heads = self.get_local_heads(
            local=True, git_repo=options.git_repo)
        ret, remote_heads = self.get_remote_heads()
        ret, remote_tags = self.get_remote_tags()

        if not options.push_all:
            local_heads = {
                branch or '': branch if self.is_sha1(branch) \
                    else local_heads.get(branch)}
        elif not (not options.mirror or options.sha1tag or patterns
                  or GitProject.has_name_changes(local_heads, options.fullname)
                  or self.pattern.has_category(GitProject.CATEGORY_REVISION)
                  or self.pattern.can_replace(
                      GitProject.CATEGORY_REVISION, local_heads)):
            prefs.append(
                '%srefs/heads/*:refs/heads/%s*' % ('+' if force else '', refs))

            return prefs

        for origin in local_heads:
            head = _secure_head_name(origin)

            if head != origin and head in local_heads:
                continue

            if patterns:
                for pattern in patterns:
                    if re.match(pattern, head):
                        break
                else:
                    logger.info(
                        '"%s" does not match provied patterns', head)
                    continue

            if not options.fullname:
                head = os.path.basename(head)
            if not head:
                continue

            if not self.pattern.match(
                    GitProject.CATEGORY_REVISION, origin,
                    name=self.source or self.uri):
                logger.info('"%s" does not match revision pattern', origin)
                continue
            elif not self.pattern.match(
                    GitProject.CATEGORY_REVISION, head,
                    name=self.source or self.uri):
                logger.info('"%s" does not match revision pattern', head)
                continue

            local_ref = origin if '/' in origin else 'refs/heads/%s' % origin
            if not self.rev_existed(local_ref):
                local_ref = 'refs/%s' % origin
                if not self.rev_existed(local_ref):
                    local_ref = 'refs/heads/%s' % origin
                    if not self.rev_existed(local_ref):
                        logger.error('"%s" has no matched revision', origin)
                        continue

            rhead = self.pattern.replace(
                GitProject.CATEGORY_REVISION, '%s' % head,
                name=self.source or self.uri)
            if rhead != head:
                rhead = '%s%s' % (refs, rhead)
            else:
                rhead = self.pattern.replace(
                    GitProject.CATEGORY_REVISION, '%s%s' % (refs, head),
                    name=self.source or self.uri)

            skip = False
            sha1 = local_heads[origin]
            remote_ref = 'refs/heads/%s' % rhead
            if os.path.basename(remote_ref) == sha1:
                logger.warning(
                    "remote branch %s equals to an existed SHA-1, which "
                    "isn't normal.%s", remote_ref,
                    "" if force else " Ignoring ...")
                if not force:
                    skip = True
            elif remote_heads.get(remote_ref) and \
                    _sha1_equals(remote_heads.get(remote_ref), sha1):
                logger.info('%s has been up-to-dated', remote_ref)
                skip = True

            ret = 0
            if not skip:
                prefs.append(
                    '%s%s:%s' % ('+' if force else '', local_ref, remote_ref))

            if ret == 0 and not options.push_all and (
                    options.sha1tag and self.is_sha1(origin)):
                equals = False
                if options.sha1tag in remote_tags:
                    sha1 = remote_tags[options.sha1tag]
                    equals = _sha1_equals(sha1, origin)

                if not equals or force:
                    prefs.append(
                        '%s%s:%s' % (
                            '+' if force else '', local_ref, options.sha1tag))

        return prefs

    def push_heads(  # pylint: disable=R0915
            self, branch=None, refs=None, patterns=None, options=None,
            force=False, logger=None, *args, **kws):
        if not logger:
            logger = Logger.get_logger()

        ret = 0
        prefs = self.build_heads(
            branch=branch, refs=refs, patterns=patterns, options=options,
            force=force, logger=logger, *args, **kws)

        if prefs:
            cargs = GitProject._push_args(list(), options.extra, *prefs)
            ret = self.push(self.remote, *cargs, **kws)

        if ret != 0:
            logger.error('error to execute git push to %s', self.remote)

        return ret

    def build_tags(self, tags=None, refs=None, patterns=None,  # pylint: disable=R0915
                  force=False, options=None, logger=None, *args, **kws):
        if not logger:
            logger = Logger.get_logger()

        trefs = list()
        if self.pattern.has_category(GitProject.CATEGORY_PROJECT) and (
                not self.pattern.match(GitProject.CATEGORY_PROJECT,
                                       self.source, name=self.source,
                                       strict=True) or
                not self.pattern.match(GitProject.CATEGORY_PROJECT,
                                       self.uri, name=self.uri, strict=True)):
            logger.info('project is excluded to push tags')
            return trefs

        refs = (refs and '%s/' % refs.rstrip('/')) or ''
        ret, remote_tags = self.get_remote_tags()

        local_tags = dict()
        if not tags:
            ret, local_tags = self.get_local_tags()
            if len(local_tags) == 0:
                ret = 0
        elif isinstance(tags, (list, tuple)):
            for tag in tags:
                local_tags[tag] = None
        else:
            local_tags[tags] = None

        if not (tags or patterns
                or GitProject.has_name_changes(
                    local_tags.keys(), options.fullname)
                or self.pattern.has_category(GitProject.CATEGORY_TAGS)
                or self.pattern.can_replace(
                    GitProject.CATEGORY_TAGS, local_tags.keys())):
            trefs.append(
                '%srefs/tags/*:refs/tags/%s*' % ('+' if force else '', refs))

            return trefs

        for origin, lsha1 in local_tags.items():
            tag = origin

            if patterns:
                for pattern in patterns:
                    if re.match(pattern, tag):
                        break
                else:
                    logger.info(
                        '"%s" does not match provied patterns', tag)
                    continue

            if not options.fullname:
                tag = os.path.basename(tag)
            if not tag:
                continue

            if not self.pattern.match(
                    GitProject.CATEGORY_TAGS, origin,
                    name=self.source or self.uri):
                logger.info(
                    '%s: "%s" does not match tag pattern', origin, origin)
                continue
            elif not self.pattern.match(
                    GitProject.CATEGORY_TAGS, tag,
                    name=self.source or self.uri):
                logger.info(
                    '%s: "%s" does not match tag pattern', origin, tag)
                continue

            rtag = self.pattern.replace(
                GitProject.CATEGORY_TAGS, '%s' % tag,
                name=self.source or self.uri)
            if rtag != tag:
                rtag = '%s%s' % (refs, rtag)
            else:
                rtag = self.pattern.replace(
                    GitProject.CATEGORY_TAGS, '%s%s' % (refs, tag),
                    name=self.source or self.uri)

            remote_tag = 'refs/tags/%s' % rtag
            if remote_tag in remote_tags:
                equals = True
                if force:
                    sha1 = remote_tags[remote_tag]
                    if lsha1 is None:
                        if not origin.startswith('refs'):
                            ret, lsha1 = self.rev_parse('refs/tags/%s' % origin)
                        else:
                            ret, lsha1 = self.rev_parse(origin)

                    equals = _sha1_equals(sha1, lsha1)

                if equals:
                    logger.info('%s is up-to-date', remote_tag)
                    continue

            trefs.append('%srefs/tags/%s:%s' % (
                '+' if force else '', origin, remote_tag))

        return trefs

    def push_tags(self, tags=None, refs=None, patterns=None,  # pylint: disable=R0915
                  force=False, options=None, logger=None, *args, **kws):
        if not logger:
            logger = Logger.get_logger()

        ret = 0
        trefs = self.build_tags(
            tags=tags, refs=refs, patterns=patterns, force=force,
            options=options, logger=logger, *args, **kws)

        if trefs:
            cargs = GitProject._push_args(list(), options.extra, *trefs)
            ret = self.push(self.remote, *cargs, **kws)

        if ret != 0 and trefs:
            logger.error(
                '%s: cannot push tag "%s"', self.remote, ','.join(trefs))

        return ret

    def init_or_download(self, revision='master', single_branch=True,
                         offsite=False, reference=None):
        logger = Logger.get_logger()

        if not revision:
            revision = self.revision

        ret = 0
        if offsite:
            if not self.exists_():
                ret = self.init()
                ret &= self.commit(
                    '--allow-empty', '--no-edit', '-m',
                    'Init the empty repository')
        elif self.remote:
            logger.info('Clone %s', self)

            ret, branches = self.get_remote_heads()
            if ret == 0:
                for branch in branches:
                    if branch in (revision, 'refs/heads/%s' % revision):
                        ret = self.download(
                            self.remote, revision=revision,
                            single_branch=single_branch,
                            reference=reference)
                        break
                else:
                    ret = self.download(
                        self.remote, revision='master',
                        single_branch=single_branch,
                        reference=reference)

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

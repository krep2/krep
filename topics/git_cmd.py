
import os

from command import Command
from files.file_utils import FileUtils


class GitCommand(Command):
    """Executes a git sub-command with specified parameters"""
    def __init__(self, gitdir=None, worktree=None, *args, **kws):
        Command.__init__(self, cwd=worktree, *args, **kws)

        self.gitdir = gitdir
        self.worktree = worktree or os.getcwd()
        self.git = FileUtils.find_execute('git')

    def _execute(self, *args, **kws):
        cli = list()
        cli.append(self.git)

        gitdir = self.gitdir if self.gitdir else None
        if not gitdir:
            gitdir = FileUtils.ensure_path(self.worktree, '.git')

        if not kws.get('notdir', False):
            if self.worktree:
                cli.append('--work-tree=%s' % self.worktree)
            if gitdir:
                cli.append('--git-dir=%s' % gitdir)

        if len(args):
            cli.extend(args)

        self.new_args(cli)
        return self.wait(**kws)

    def raw_command(self, *args, **kws):
        return self._execute(*args, **kws)

    def raw_command_with_output(self, *args, **kws):
        res = self._execute(capture_stdout=True, *args, **kws)

        return res, self.get_output()

    def set_path(self, gitdir=None, worktree=None):
        if gitdir:
            self.gitdir = gitdir

        if worktree:
            self.worktree = worktree

    def init(self, *args, **kws):
        return self.raw_command('init', *args, **kws)

    def add(self, *args, **kws):
        if len(args) == 0:
            args = args[:]
            args.append('.')

        return self.raw_command('add', *args, **kws)

    def branch(self, *args, **kws):
        return self.raw_command_with_output('branch', *args, **kws)

    def checkout(self, *args, **kws):
        return self.raw_command('checkout', *args, **kws)

    def clone(self, *args, **kws):
        return self.raw_command(
            'clone', capture_stdout=False, capture_stderr=False, *args, **kws)

    def commit(self, *args, **kws):
        return self.raw_command('commit', *args, **kws)

    def config(self, *args, **kws):
        return self.raw_command_with_output('config', *args, **kws)

    def fetch(self, *args, **kws):
        return self.raw_command(
            'fetch', capture_stdout=False, capture_stderr=False, *args, **kws)

    def log(self, *args, **kws):
        return self.raw_command_with_output('log', *args, **kws)

    def ls_remote(self, *args, **kws):
        return self.raw_command_with_output('ls-remote', notdir=True, *args, **kws)

    def pull(self, *args, **kws):
        return self.raw_command(
            'pull', capture_stdout=False, capture_stderr=False, *args, **kws)

    def push(self, *args, **kws):
        return self.raw_command(
            'push', capture_stdout=False, capture_stderr=False, *args, **kws)

    def rev_list(self, *args, **kws):
        return self.raw_command_with_output('rev-list', *args, **kws)

    def rev_parse(self, *args, **kws):
        return self.raw_command_with_output('rev-parse', *args, **kws)

    def rm(self, *args, **kws):  # pylint: disable=C0103
        return self.raw_command('rm', *args, **kws)

    def tag(self, *args, **kws):
        return self.raw_command_with_output('tag', *args, **kws)

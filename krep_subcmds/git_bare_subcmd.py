
from git_clone_subcmd import GitCloneSubcmd


class GitBareSubcmd(GitCloneSubcmd):
    COMMAND = 'git-b'
    help_summary = 'Download and import git bare repository'
    help_usage = """\
%prog [options] ...

Download git project with the option "--bare" and import to the local server.

It supports to clone the full git bare repository and import the specified
branches and tags into the local server with the similar implementation like
the command 'git-p'. The difference is that option "--bare" is used when
cloning the git.
"""

    def options(self, optparse):
        GitCloneSubcmd.options(self, optparse)
        optparse.suppress_opt('--bare', True)

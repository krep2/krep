
from git_clone_subcmd import GitCloneSubcmd


class GitBareSubcmd(GitCloneSubcmd):
    COMMAND = 'git-b'
    helpSummary = 'Download and import git bare repository'
    helpUsage = """\
%prog [options] ...

Download git project with the option "--bare" and import to the local server.

It supports to clone the full git bare repository and import the specified
branches and tags into the local server with the similar implementation like
the command 'git-p'. The difference is that option "--bare" is used when
cloning the git.
"""

    def options(self, optparse):
        GitCloneSubcmd.options(self, optparse)
        option = optparse.get_option_group('--bare')
        if option:
            option.remove_option('--bare')

    def execute(self, options, *args, **kws):
        options.bare = True
        GitCloneSubcmd.execute(self, options, args)

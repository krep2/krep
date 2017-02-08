
from command import Command
from files.file_utils import FileUtils
from logger import Logger
from subcmd import SubCommand


class GerritError(Exception):
    """Indicate the unsuccessful gerrit processing."""


class Gerrit(Command):
    """\
Provides Gerrit access.

It encapsulates the ssh command to run Gerrit commands. Not all but
required commands have been implemented with specific handling:

 - create-branch
 - create-project
 - ls-projects

Other unimplemented command can be accessed with __call__ method
implicitly."""

    def __init__(self, server, cwd=None):
        Command.__init__(self, cwd=cwd)

        self.dirty = True
        self.server = server

        self.projects = list()
        self.ssh = FileUtils.find_execute('ssh')

    @staticmethod
    def options(optparse):
        options = optparse.get_option_group('--refs') or \
            optparse.add_option_group('Remote options')
        options.add_option(
            '--remote', '--server', '--gerrit-server',
            dest='remote', action='store',
            help='Set gerrit url for the repository management')
        options.add_option(
            '--repo-create',
            dest='repo_create', action='store_true', default=True,
            help='Create the repository by default: %default')
        # Not to set the default for no-option
        options.add_option(
            '--description', '--repo-description',
            dest='description', action='store',
            help='Set the repository description in gerrit when creating the '
                 'new repository. If not set, the default string will be '
                 'used. "--no-description" could suppress the description')

    def set_dirty(self, dirty):
        self.dirty = dirty

    def get_server(self):
        return self.server

    def _execute(self, cmd, *args, **kws):
        cli = list()
        cli.append(self.ssh)
        cli.append('-p')
        cli.append('29418')
        cli.append(self.server)
        cli.append('gerrit')
        cli.append(cmd)

        if len(args):
            cli.extend(args)

        self.new_args(cli)
        return self.wait(**kws)

    def ls_projects(self, force=False):
        if (self.dirty or force) and self._execute(
                'ls-projects', capture_stdout=True) == 0:
            self.dirty = False
            self.projects = list()

            for line in self.get_out_lines():
                self.projects.append(line.strip())

        return self.projects

    def create_project(self, project, initial_commit=True, description=None,
                       source=None):
        logger = Logger.get_logger('Gerrit')

        project = project.strip()
        if project not in self.ls_projects():
            args = list()
            if initial_commit:
                args.append('--empty-commit')

            # description may be None in the case, description=False means
            # --no-description is set to suppress the function
            if SubCommand.override_value(description):
                if not description:
                    description = "Mirror of %url"

                if source:
                    description = description.replace('%url', source)

                if description.find('%url') > -1:
                    logger.error("gerrit url is being missed")
                else:
                    args.append('--description')
                    args.append("'%s'" % description.strip("'\""))

            args.append(project)
            ret = self._execute('create-project', *args)
            if ret:
                # try fetching the latest project to confirm the result
                # if gerrit reports the mistake to create the repository
                if project not in self.ls_projects(force=True):
                    raise GerritError(
                        'Gerrit: cannot create "%s" on remote "%s"'
                        % (project, self.server))
        else:
            logger.debug('%s existed in the remote', project)

    def create_branch(self, branch):
        return self._execute('create-branch', branch)

TOPIC_ENTRY = "Gerrit, GerritError"

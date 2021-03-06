
from command import Command
from files.file_utils import FileUtils
from logger import Logger
from synchronize import synchronized


class GerritError(Exception):
    """Indicate the unsuccessful gerrit processing."""


class GerritCmd(Command):
    def __init__(self, server, enable):
        Command.__init__(self)

        self.dirty = True
        self.enable = enable
        self.server = server

        self.projects = list()
        self.ssh = FileUtils.find_execute('ssh')

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

    def has_project_(self, project):
        if not self.enable:
            return True

        projects = self.ls_projects()
        return project in projects

    @synchronized
    def ls_projects(self, force=False):
        if not self.enable:
            return list()

        if (self.dirty or force) and self._execute(
                'ls-projects', capture_stdout=True) == 0:
            self.dirty = False
            self.projects = list()

            for line in self.get_out_lines():
                self.projects.append(line.strip())

        return self.projects

    @synchronized
    def create_project(self, project, initial_commit=True, description=None,
                       source=None, options=None):
        if not self.enable:
            return

        logger = Logger.get_logger('Gerrit')

        project = project.strip()
        optcp = options and options.extra_values(
            options.extra_option, 'gerrit-cp')
        if project not in self.ls_projects():
            args = list()
            cp_value = optcp and optcp.boolean(optcp.empty_commit)
            if initial_commit or cp_value:
                if cp_value is not False:
                    args.append('--empty-commit')

            # description=False means --no-description to suppress the function
            if optcp and optcp.description:
                args.append('--description')
                args.append("'%s'" % optcp.description.strip("'\""))
            elif not description == False:
                if not description:
                    description = "Mirror of %url"

                if source:
                    description = description.replace('%url', source)

                if description.find('%url') > -1:
                    logger.warning("gerrit url is being missed")
                else:
                    args.append('--description')
                    args.append("'%s'" % description.strip("'\""))

            if optcp:
                if optcp.branch:
                    args.append('--branch')
                    args.append(optcp.branch)
                if optcp.owner:
                    args.append('--owner')
                    args.append(optcp.owner)
                if optcp.parent:
                    args.append('--parent')
                    args.append(optcp.parent)

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

    @synchronized
    def create_branch(self, branch):
        if self.enable:
            return self._execute('create-branch', branch)
        else:
            return 0

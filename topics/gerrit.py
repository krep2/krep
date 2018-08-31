
from gerrit_cmd import GerritCmd, GerritError


class Gerrit(GerritCmd):
    """\
Provides Gerrit access.

It encapsulates the ssh command to run Gerrit commands. Not all but
required commands have been implemented with specific handling:

 - create-branch
 - create-project
 - ls-projects

Other unimplemented command can be accessed with __call__ method
implicitly."""

    extra_items = (
        ('Gerrit options for create-project:', (
            ('gerrit-cp:branch', 'initial branch name'),
            ('gerrit-cp:empty-commit', 'to create initial empty commit'),
            ('gerrit-cp:description', 'description of project'),
            ('gerrit-cp:owner', 'owner(s) of the project'),
            ('gerrit-cp:parent', 'parent project'),
        )),
    )

    @staticmethod
    def options(optparse):
        options = optparse.get_option_group('--refs') or \
            optparse.add_option_group('Remote options')
        options.add_option(
            '--disable-gerrit',
            dest='enable_gerrit', action='store_false', default=True,
            help='Disable gerrit server, default is to enable gerrit')
        options.add_option(
            '--remote', '--server', '--gerrit-server',
            dest='remote', action='store',
            help='Set gerrit url for the repository management')
        options.add_option(
            '--repo-create',
            dest='repo_create', action='store_true', default=False,
            help='Create the repository by default: %default')
        # Not to set the default for no-option
        options.add_option(
            '--description', '--repo-description',
            dest='description', action='store',
            help='Set the repository description in gerrit when creating the '
                 'new repository. If not set, the default string will be '
                 'used. "--no-description" could suppress the description')

    def __init__(self, server, enable=True):
        GerritCmd.__init__(self, server, enable)

    def has_project(self, project):
        projects = self.ls_projects()

        return project in projects


TOPIC_ENTRY = "Gerrit, GerritError"

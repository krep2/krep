
from gerrit_cmd import GerritCmd


class GerritError(Exception):
    """Indicate the unsuccessful gerrit processing."""


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

    def __init__(self, server, enable=True):
        GerritCmd.__init__(self, server, enable)

    def has_project(self, project):
        projects = self.ls_projects()

        return project in projects


TOPIC_ENTRY = "Gerrit, GerritError"

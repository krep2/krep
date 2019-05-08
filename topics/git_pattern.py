
from pattern import Pattern


class GitPattern(Pattern):
    ALIASES = (
        'project,p,proj',
        'revision,r,rev',
        'tag,t'
    )

    def __init__(self, pattern=None, pattern_file=None):
        Pattern.__init__(
          self, pattern, pattern_file, aliases=GitPattern.ALIASES)


TOPIC_ENTRY = 'GitPattern'

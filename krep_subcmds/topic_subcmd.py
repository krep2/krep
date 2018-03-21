
import re

from topics import all_topics, SubCommand


class TopicSubcmd(SubCommand):
    COMMAND = 'topic'
    help_summary = 'Print the topic summaries'
    help_usage = """\
%prog <topic> ...

Display all registered topics of the program for debugging purpose.

Topic contains the classes that can be imported from "topics", which
is the official way to use by the implemented sub-commands."""

    @staticmethod
    def _print_formatted_topic(topics, print_name=True):
        lines = list()

        topfmt = '%(summary)s'
        if print_name:
            longest = max([len(topic) for topic in topics])
            topfmt = ' %%(name)-%ds%%(summary)s' % (longest + 2)

        for name in topics:
            value = dict()
            if print_name:
                value['name'] = name

            summary = ((all_topics[name] or '').split('\n'))[0].strip('.')
            while len(summary) > 60:
                splits = re.split(r'\s+', summary.strip())
                if len(splits) > 1:
                    summary = ' '.join(splits[:-1]) + '...'
                else:
                    summary = summary[:57] + '...'

            value['summary'] = summary or 'No description'
            lines.append(topfmt % value)

        if len(lines) > 0:
            lines.sort()
            print '\n'.join(lines)

    def _print_all_topics(self):  # pylint: disable=R0201
        print 'The topics of krep are:'
        print

        TopicSubcmd._print_formatted_topic(all_topics.keys())
        print '\nSee more info with "krep topic <topic>"'

    def _print_topic(self, topics):  # pylint: disable=R0201
        aliases = dict()
        for name in all_topics.keys():
            alias = ''
            for i in range(len(name)):
                if 'A' <= name[i] <= 'Z':
                    alias += '_'

                alias += name[i].lower()

            aliases[name] = name
            aliases[alias.lstrip('_')] = name

        topics = list(topics)
        for topic in topics[:]:
            topics.remove(topic)
            if topic not in aliases:
                print 'krep: "%s" is not a known topic' % topic
            else:
                topics.append(aliases[topic])

        if len(topics) > 1:
            TopicSubcmd._print_formatted_topic(topics)
        elif len(topics) == 1:
            print all_topics[topics[0]]

    def execute(self, options, *args):  # pylint: disable=W0613
        if len(args) == 0 or 'all' in args:
            self._print_all_topics()
        else:
            self._print_topic(args)

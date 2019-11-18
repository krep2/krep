
import os
import threading

from command import Command
from config_file import XmlConfigFile
from debug import Debug
from error import HookError
from git_pattern import GitPattern
from logger import Logger
from options import Values
from pattern_file import PatternFile as XmlPatternFile


class KrepXmlConfigFile(XmlPatternFile):
    pass


class SubCommand(object):
    """Supports to run as the tool running command."""
    _name = None
    _optparse = None

    def get_option_parser(self, opt):
        """Returns the option parser for the subcommand."""
        if self._optparse is None:
            try:
                usage = self.help_usage.replace(  # pylint: disable=E1101
                    '%prog', 'krep %s' % getattr(
                        self, 'COMMAND', self.NAME))  # pylint: disable=E1101
            except AttributeError:
                # it shouldn't be run here
                raise SyntaxError('Failed to read command attribute')

            self._optparse = opt
            self._optparse.set_usage(usage)
            self.options(self._optparse)

        return self._optparse

    def options(self, optparse, option_remote=False,  # pylint: disable=W0613
                option_import=False, banned=None, *args, **kws):
        """Handles the options for the subcommand."""
        if option_remote:
            self.options_remote(optparse)
        if option_import:
            self.options_import(optparse)

        self._options_jobs(optparse)
        # load options from the imported classes
        extra_list = self._options_loaded(optparse, banned, kws.get('modules'))
        self._option_extra(optparse, extra_list)

    def options_remote(self, optparse):
        options = optparse.get_option_group('--force') or \
            optparse.add_option_group('Other options')

        options.add_option(
            '--offsite', dest='offsite',
            action='store_true', default=False,
            help='not to fetch from the network and work offline')

        # Remote options
        options = optparse.add_option_group('Remote options')
        options.add_option(
            '-r', '--refs',
            dest='refs', action='store', metavar='REF',
            help='the reference prefix of the remote server')
        options.add_option(
            '--branch-refs', '--head-refs',
            dest='head_refs', action='store', metavar='HEAD_REF',
            help='the reference prefix of the heads. it will override the one '
                 'of "refs"')
        options.add_option(
            '--tag-refs',
            dest='tag_refs', action='store', metavar='TAG_REF',
            help='the reference prefix of the tags. it will override the one '
                 'of "refs"')
        options.add_option(
            '-k', '--keep-name',
            dest='keep_name', action='store_true', default=False,
            help='keep current head or tag name without new refs as the '
                 'last part')

        return options

    def options_import(self, optparse):
        # Import options
        options = optparse.add_option_group('Import options')
        options.add_option(
            '--skip-validation',
            dest='skip_validation', action='store_true',
            help='Skip the validation with lots of commits. More info can '
                 'refer to gerrit document for user upload')
        options.add_option(
            '-a', '--all',
            dest='all', action='store_true', default=None,
            help='Take all operations except to suppress with opposite option '
                 'like "--no-tags". The action is merged by the sub-command')
        # Not to set the default for no-option
        options.add_option(
            '--branches', '--heads',
            dest='heads', action='store_true',
            help='push all branches to the remote. Once option "--all" is '
                 'set, it is enabled except "--no-branches" or "--no-heads" '
                 'is set explicitly')
        # Not to set the default for no-option
        options.add_option(
            '--tags',
            dest='tags', action='store_true',
            help='push all tags to the remote. Once option "--all" is set, it '
                 'is enabled except "--no-tags" is set explicitly')

        options.add_option(
            '--branch-pattern', '--head-pattern',
            dest='head_pattern', action='append',
            help='push the matched heads with regex patterns. The replacement '
                 'rules could be used to update the remote head name')

        options.add_option(
            '--tag-pattern',
            dest='tag_pattern', action='append',
            help='push the matched tags with regex patterns. The replacement '
                 'rule could be used to update the remote tag names')

        return options

    def _options_jobs(self, optparse):
        if self.support_jobs():
            options = optparse.get_option_group('--force') or \
                optparse.add_option_group('Other options')

            options.add_option(
                '-j', '--job',
                dest='job', action='store', type='int',
                help='jobs to run with specified threads in parallel')

    def _option_extra(self, optparse, extra_list=None):
        def _format_list(extra_items):
            item_list = list()

            if extra_items:
                items = dict()
                length = 0
                # re-arrange the extra list with a flat format
                for opt in extra_items:
                    if isinstance(opt, (list, tuple)):
                        items[opt[0]] = opt[1]
                        for extra, _ in opt[1]:
                            length = max(length, len(extra))
                    else:
                        item[opt] = None

                fmt = '  %%-%ds%%s' % (length + 2)
                for opt in sorted(items):
                    item_list.append('')
                    item_list.append(opt)

                    item = items[opt]
                    if isinstance(item, (list, tuple)):
                        for extra, desc in item:
                            item_list.append(fmt % (extra, desc))

            return '\n'.join(item_list)

        if extra_list or self.support_extra():
            item = _format_list(extra_list or [])

            options = optparse.get_option_group('--force') or \
                optparse.add_option_group('Other options')

            options.add_option(
                '--extra-option',
                dest='extra_option', action='append',
                help='extra options in internal group with prefix. '
                     'The format is like "inject-option"%s' % (
                         ':\n%s' % item if item else ''))

    @staticmethod
    def _options_loaded(optparse=None, banned=None, modules=None):
        extra_list = list()

        logger = SubCommand.get_logger()
        # search the imported class to load the options
        for name, clazz in (modules or dict()).items():
            if banned and name in banned:
                continue

            if optparse and hasattr(clazz, 'options'):
                try:
                    logger.debug('Load %s', name)
                    clazz.options(optparse)
                except TypeError:
                    pass

            if hasattr(clazz, 'extra_items'):
                logger.debug('Load extras from %s', name)
                extra_list.extend(clazz.extra_items)

        return extra_list

    @staticmethod
    def get_patterns(options):
        patterns = GitPattern()

        if options.pattern:
            patterns += GitPattern(options.pattern)

        if options.pattern_file:
            patf = XmlPatternFile.load(
                SubCommand.get_absolute_running_file_name(
                    options, options.pattern_file))

            if patf:
                patterns += patf

        Debug.dump_pattern(options, patterns)

        return patterns

    @staticmethod
    def get_logger(name=None, level=0, verbose=0):
        """Returns the encapusulated logger for subcommands."""
        return Logger.get_logger(name, level, verbose)

    @staticmethod
    def get_absolute_working_dir(options):
        if options.relative_dir:
            path = os.path.join(options.working_dir, options.relative_dir)
        else:
            path = options.working_dir

        return os.path.expanduser(path)

    @staticmethod
    def get_absolute_running_file_name(options, filename):
        name = os.path.expanduser(filename)
        if os.path.isabs(name):
            return name
        elif options.current_dir:
            return os.path.join(options.current_dir, name)
        else:
            return os.path.join(
                SubCommand.get_absolute_working_dir(options), name)

    def get_name(self, options):  # pylint: disable=W0613
        """Gets the subcommand name."""
        return self._name or \
            getattr(self, 'COMMAND', self.NAME)  # pylint: disable=E1101

    def set_name(self, name):
        """Sets the subcommand name."""
        self._name = name

    def support_jobs(self):  # pylint: disable=W0613
        """Indicates if the command can run with threading."""
        return False

    def support_inject(self):  # pylint: disable=W0613
        """Indicates if the command supports the injection option."""
        return False

    def support_extra(self):  # pylint: disable=W0613
        """Indicates if the command supports the extra option."""
        return False

    @staticmethod
    def override_value(va, vb=None):
        """Overrides the late values if it's not a boolean value."""
        return vb if vb is not None and va is not False else va

    @staticmethod
    def do_hook(name, option, args=None, dryrun=False):
        # try option.hook-name first to support xml configurations
        hookcmd = option.pop('hook-%s-cmd' % name)
        if hookcmd:
            try:
                return eval(hookcmd)
            except Exception:
                return 1

        hook = option.pop('hook-%s' % name)
        if hook:
            hargs = option.normalize('hook-%s-args' % name, attr=True)
            if args:
                hargs.extend(args)

            return SubCommand.run_hook(
                hook, hargs,
                SubCommand.get_absolute_working_dir(option),
                dryrun=dryrun)

        hook = None
        # try hook-dir with the hook name then
        if option.hook_dir:
            hook = os.path.join(option.hook_dir, name)
        elif 'KREP_HOOK_PATH' in os.environ:
            hook = os.path.join(os.environ['KREP_HOOK_PATH'], name)

        if hook:
            return SubCommand.run_hook(
                hook, args,
                SubCommand.get_absolute_working_dir(option),
                dryrun=dryrun)
        else:
            return 1

    @staticmethod
    def run_hook(hook, hargs, cwd=None, dryrun=False, *args, **kws):
        if hook:
            if os.path.exists(hook):
                cli = list([hook])
                if hargs:
                    cli.extend(hargs)
                if args:
                    cli.extend(args)

                cmd = Command(cwd=cwd, dryrun=dryrun)
                cmd.new_args(*cli)
                ret = cmd.wait(**kws)
                if ret != 0:
                    raise HookError('Failed to run %s' % hook)

                return 0
            else:
                SubCommand.get_logger().debug("Error: %s not existed", hook)

    def execute(self, options, *args, **kws):  # pylint: disable=W0613
        # set the logger name at the beggining
        self.get_logger(self.get_name(options))

        return True


class SubCommandWithThread(SubCommand):
    """Commands with threading method to run with multiple jobs"""
    def support_jobs(self):  # pylint: disable=W0613
        return True

    def run_with_thread(self, jobs, tasks, func, *args):
        def _run(task, sem, event, func, args):
            try:
                if len(args) > 0:
                    func(task, *args)
                else:
                    func(task)
            except KeyboardInterrupt:
                if event:
                    event.set()
            except Exception as e:  # pylint: disable=W0703
                self.get_logger().exception(e)
                event.set()
            finally:
                sem.release()

        ret = True
        if jobs and jobs > 1:
            threads = set()
            sem = threading.Semaphore(jobs)
            event = threading.Event()

            for task in tasks:
                if event.isSet():
                    break

                sem.acquire()
                thread = threading.Thread(
                    target=_run,
                    args=(task, sem, event, func, args))
                threads.add(thread)
                thread.start()

            for thread in threads:
                thread.join()

            if event.isSet():
                self.get_logger().error('Exited due to errors')
                ret = False
        else:
            for task in tasks:
                ret = func(task, *args) and ret

        return ret


TOPIC_ENTRY = 'SubCommand, SubCommandWithThread, KrepXmlConfigFile'

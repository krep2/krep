
import threading
from logger import Logger


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

    def options(self, optparse, *args, **kws):  # pylint: disable=W0613
        """Handles the options for the subcommand."""
        self._options_jobs(optparse)

    def _options_jobs(self, optparse):
        if self.support_jobs():
            options = optparse.get_option_group('--force') or \
                optparse.add_option_group('Other options')

            options.add_option(
                '-j', '--job',
                dest='job', action='store', type='int',
                help='jobs to run with specified threads in parallel')

    @staticmethod
    def get_logger():
        """Returns the encapusulated logger for subcommands."""
        return Logger.get_logger()

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

    @staticmethod
    def override_value(va, vb=None):
        """Overrides the late values if it's not a boolean value."""
        return vb if vb is not None else va

    def execute(self, options, *args, **kws):  # pylint: disable=W0613
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
            except Exception, e:  # pylint: disable=W0703
                self.get_logger().exception(e)
                event.set()
            finally:
                sem.release()

        ret = True
        if jobs > 1:
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
                print '\nerror: Exited due to errors.'
                ret = False
        else:
            for task in tasks:
                ret = func(task, *args) and ret

        return ret


TOPIC_ENTRY = 'SubCommand, SubCommandWithThread'

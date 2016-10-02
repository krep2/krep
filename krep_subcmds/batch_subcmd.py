
import os
import re

from topics import ConfigFile, SubCommandWithThread, \
    RaiseExceptionIfOptionMissed


class BatchSubcmd(SubCommandWithThread):
    COMMAND = 'batch'

    help_summary = 'Load and executes projects from specified files'
    help_usage = """\
%prog [options] ...

Read the project configures from files and executes per project configuration.

The project is implemented to read configs from file and execute. With the
support, "%prog" would extend as the batch method to run as a single
command to accomplish multiple commands.

The plain-text file format can refer to the topic "config_file", which is used
to define the projects in the config file.
"""

    def options(self, optparse):
        SubCommandWithThread.options(self, optparse)

        options = optparse.add_option_group('File options')
        options.add_option(
            '-f', '--file', '--batch-file',
            dest='batch_file', action='append', metavar='FILE',
            help='Set the batch config file')
        options.add_option(
            '-u', '--group',
            dest='group', metavar='GROUP1,GROUP2,...',
            help='Set the handling groups')

        options = optparse.add_option_group('Error handling options')
        options.add_option(
            '--ierror', '--ignore-errors',
            dest='ignore_errors', action='store_true',
            help='Ignore the running error and continue for next command')

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        logger = self.get_logger()  # pylint: disable=E1101

        def _in_group(limits, groups):
            allminus = True

            for limit in limits:
                opposite = False
                if limit.startswith('-'):
                    limit = limit[1:]
                    opposite = True
                else:
                    allminus = False

                if limit in groups:
                    return not opposite

            if (allminus or 'all' in limits) and '-all' not in groups:
                return True

            return False

        def _filter_with_group(project, name, limit):
            limits = re.split(r'\s*,\s*', limit or 'all')

            groups = re.split(r'\s*,\s*', project.exude('group', ''))
            groups.extend([name, os.path.basename(name)])
            if _in_group(limits, groups):
                return True
            else:
                logger.debug('%s: %s not in %s',
                             getattr(project, 'name'), limits, groups)

                return False

        def _run(project):
            largs = options.args or list()
            ignore_error = options.ignore_error or False

            self._run(project.schema,  # pylint: disable=E1101
                      project,
                      largs,
                      ignore_except=ignore_error)

        def _batch(batch):
            conf = ConfigFile(batch)

            projects = list()
            default = conf.get_default()
            for name in conf.get_names('project') or list():
                projs = conf.get_value(name)
                if not isinstance(projs, list):
                    projs = [projs]

                # handle projects with the same name
                for project in projs:
                    # remove the prefix 'project.'
                    proj_name = conf.get_subsection_name(name)
                    setattr(project, 'name', proj_name)
                    if _filter_with_group(project, proj_name, options.group):
                        project.join(default, override=False)
                        projects.append(project)

            projs, nprojs = list(), list()
            for project in projects:
                try:
                    multiple = self._cmd(  # pylint: disable=E1101
                        project.schema).support_jobs()
                except AttributeError:
                    raise SyntaxError(
                        'schema is not recognized or undefined in %s' %
                        project)

                working_dir = project.exude('working_dir')
                if working_dir:
                    setattr(
                        project, 'working_dir', os.path.abspath(working_dir))

                project.join(options, override=False)
                if multiple:
                    projs.append(project)
                else:
                    nprojs.append(project)

            ret = self.run_with_thread(  # pylint: disable=E1101
                options.job, nprojs, _run)
            ret = self.run_with_thread(  # pylint: disable=E1101
                1, projs, _run) and ret

            return ret

        RaiseExceptionIfOptionMissed(
            options.batch_file or args, "batch file (--batch-file) is not set")

        ret = True
        files = (options.batch_file or list())[:]
        files.extend(args[:])

        for batch in files:
            if os.path.exists(batch):
                ret = _batch(batch) and ret
            else:
                logger.error('cannot open batch file %s', batch)
                ret = False

            if not ret and not options.ignore_errors:
                break

        return ret


import os
import re

from options import Values
from topics import KrepXmlConfigFile, PatternFile, \
    RaiseExceptionIfOptionMissed, SubCommandWithThread


# pylint: disable=E1101
class BatchXmlConfigFile(KrepXmlConfigFile):
    PROJECT_PREFIX = "project"

    SUPPORTED_ELEMENTS = (
        'projects', 'project',
        'args', 'option', 'hook'
    )

    def __init__(self, filename, pi=None, config=None):
        KrepXmlConfigFile.__init__(self, filename, pi=pi, config=config)

    def parse_include(self, node):
        if not self.evaluate_if_node(node):
            return Values()

        name, xvals = KrepXmlConfigFile.parse_include(
            self, node, BatchXmlConfigFile)

        return name, xvals

    def parse_hook(self, node, config=None):
        if not self.evaluate_if_node(node):
            return

        name = self.get_attr(node, 'name')
        filen = self.get_attr(node, 'file')
        if filen and not os.path.isabs(filen):
            filen = os.path.join(
                os.path.dirname(self.filename), filen)

        if not config:
            config = Values()

        self.set_attr(config, 'hook-%s' % name, filen)
        for child in node.childNodes:
            if child.nodeName == 'args':
                self.set_attr(
                    config, 'hook-%s-%s' % (name, child.nodeName),
                    self.get_attr(child, 'value'))

    def parse_project(self, node, pi=None, config=None):
        name = self.get_var_attr(node, 'name')
        group = self.get_var_attr(node, 'group')

        if not config:
            config = Values()

        if not self.evaluate_if_node(node):
            return config

        if group:
            self.set_attr(config, 'group', group)

        for child in node.childNodes:
            if not self.evaluate_if_node(child):
                continue

            if child.nodeName == 'args':
                self.set_attr(
                    config, child.nodeName, self.get_var_attr(child, 'value'))
            elif child.nodeName == 'option':
                name = self.get_var_attr(child, 'name')
                value = self.get_var_attr(child, 'value')
                self.set_attr(config, name, value)
            elif child.nodeName == 'hook':
                self.parse_hook(child, config)
            elif child.nodeName == 'include':
                _, xvals = self.parse_include(child)
                # only pattern supported and need to export explicitly
                vals = xvals.get_values(BatchXmlConfigFile.FILE_PREFIX)
                for val in vals:
                  # pylint: disable=E1103
                  if val and val.pattern:
                      self.set_attr(config, 'pattern', val.pattern)
                  # pylint: enable=E1103
            else:
                self.parse_patterns(child, config)

        config.join(self.get_default(), override=False)
        if pi is not None:
            config.join(pi, override=False)

        return config

    def parse(self, node, pi=None):  # pylint: disable=R0914
        if node.nodeName != 'projects':
            KrepXmlConfigFile.parse(self, node, pi)
            return

        if not self.evaluate_if_node(node):
            return

        default = self._get_value(BatchXmlConfigFile.DEFAULT_CONFIG)
        for child in node.childNodes:
            if child.nodeName == 'project':
                source = self.get_attr(child, 'source')
                if source:
                    for _ in self.foreach(source, child):
                        self._add_value(
                            '%s.%s' % (
                                BatchXmlConfigFile.PROJECT_PREFIX,
                                self.get_attr(child, 'name')),
                            self.parse_project(child, pi=pi))
                else:
                    self._add_value(
                        '%s.%s' % (
                            BatchXmlConfigFile.PROJECT_PREFIX,
                            self.get_attr(child, 'name')),
                        self.parse_project(child, pi=pi))
            elif child.nodeName == 'hook':
                self.parse_hook(child, default)
            else:
                KrepXmlConfigFile.parse(self, child, default)

# pylint: enable=E1101


class BatchSubcmd(SubCommandWithThread):
    COMMAND = 'batch'

    help_summary = 'Load and execute projects from specified files'
    help_usage = """\
%prog [options] ...

Read project configurations from files and executes per project configuration.

The project is implemented to read configations from the config file and
execute. With the support, "%prog" would extend as the batch method to run as
a single command to accomplish multiple commands.

The format of the plain-text configuration file can refer to the topic
"config_file", which is used to define the projects in the file.
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
        options.add_option(
            '--list',
            dest='list', action='store_true',
            help='List the selected projects')

        options = optparse.add_option_group('Error handling options')
        options.add_option(
            '--ierror', '--ignore-errors',
            dest='ignore_errors', action='store_true',
            help='Ignore the running error and continue for next command')

    def support_inject(self):  # pylint: disable=W0613
        return True

    def execute(self, options, *args, **kws):
        SubCommandWithThread.execute(self, options, *args, **kws)

        logger = self.get_logger()  # pylint: disable=E1101

        def _in_group(limits, groups):
            allminus = True

            for limit in limits:
                opposite = False
                if limit.startswith('-') or limit.startswith('!'):
                    limit = limit[1:]
                    opposite = True
                else:
                    allminus = False

                if limit in groups:
                    return not opposite

            if (allminus or 'default' in limits) and \
                    'notdefault' not in groups and '-default' not in groups:
                return True

            return False

        def _filter_with_group(project, name, limit):
            limits = re.split(r'\s*,\s*', limit or 'default')

            groups = re.split(r'\s*,\s*', project.pop('group', ''))

            if name not in groups:
                groups.append(name)
            bname = os.path.basename(name)
            if bname not in groups:
                groups.append(bname)

            if _in_group(limits, groups):
                return True
            else:
                logger.debug('%s: %s not in %s',
                             getattr(project, 'name'), limits, groups)

                return False

        def _list(batch, projs, nprojs):
            def _inc(dicta, key):
                if key in dicta:
                    dicta[key] += 1
                else:
                    dicta[key] = 1

            print('\nFile: %s' % batch)
            print('==================================')
            if len(nprojs):
                print('Parallel projects with %s job(s)' % (options.job or 1))
                print('---------------------------------')
                results = dict()
                for project in nprojs:
                    _inc(results, '[%s] %s' % (project.schema, project.name))

                for k, result in enumerate(sorted(results.keys())):
                    print('  %2d. %s' % (k + 1, result))

            if len(projs):
                print('\nNon-parallel projects')
                print('---------------------------------')
                results = dict()
                for project in projs:
                    _inc(results, '[%s] %s' % (project.schema, project.name))

                for k, result in enumerate(sorted(results.keys())):
                    print('  %2d. %s%s' % (
                        k + 1, result, ' (%d)' % results[result]
                        if results[result] > 1 else ''))

            print('')

            return True

        def _run(project):
            largs = options.args or list()
            ignore_error = options.ignore_error or False

            # clean current directory
            project.current_dir = False
            # ensure to construct thread logger
            self.get_logger(project.name)  # pylint: disable=E1101
            self._run(project.schema,  # pylint: disable=E1101
                      project,
                      largs,
                      ignore_except=ignore_error)

        def _batch(batch):
            conf = BatchXmlConfigFile(batch)

            projs, nprojs, tprojs = list(), list(), list()
            projects = conf.get_names(BatchXmlConfigFile.PROJECT_PREFIX)
            for name in projects or list():
                projects = conf.get_values(name)  # pylint: disable=E1101
                if not isinstance(projects, list):
                    projects = [projects]

                # handle projects with the same name
                for project in projects:
                    proj = Values()
                    # remove the prefix 'project.'
                    proj_name = conf.get_subsection_name(name)  # pylint: disable=E1101
                    setattr(proj, 'name', proj_name)
                    if _filter_with_group(project, proj_name, options.group):
                        optparse = self._cmdopt(project.schema)  # pylint: disable=E1101
                        # recalculate the attribute types
                        proj.join(project, option=optparse)
                        proj.join(options, option=optparse, override=False)
                        if len(projects) == 1:
                            tprojs.append(proj)
                        else:
                            projs.append(proj)

            for project in tprojs:
                try:
                    multiple = self._cmd(  # pylint: disable=E1101
                        project.schema).support_jobs()
                except AttributeError:
                    raise SyntaxError(
                        'schema is not recognized or undefined in %s' %
                        project)

                working_dir = project.pop('working_dir')
                if working_dir:
                    setattr(
                        project, 'working_dir', os.path.abspath(working_dir))

                if multiple:
                    projs.append(project)
                else:
                    nprojs.append(project)

            if options.list:
                return _list(batch, projs, nprojs)

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
            if os.path.isfile(batch):
                ret = _batch(batch) and ret
            else:
                logger.error('cannot find batch file %s', batch)
                ret = False

            if not ret and not options.ignore_errors:
                break

        return ret

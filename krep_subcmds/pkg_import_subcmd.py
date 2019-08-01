
import glob
import hashlib
import os
import re
import stat
import shutil
import tempfile
import time

try:
    from urllib.parse import urlparse
except ImportError:
    from urlparse import urlparse

from options import Values
from topics import FileDiff, FileUtils, FileVersion, FileWasher, GitProject, \
    Gerrit, key_compare, Logger, SubCommand, RaiseExceptionIfOptionMissed


def _handle_message_with_escape(pkg, escaped=True, default=None,
                                maps=None, dofile=True):

    def hash_digest(filename, mode):
        with open(filename, 'r') as fp:
            if mode == 'md5':
                return hashlib.md5(fp.read()).hexdigest()
            elif mode == 'sha1':
                return hashlib.sha1(fp.read()).hexdigest()

        return None

    message = default

    if dofile:
        main, _ = os.path.splitext(pkg)
        for ext in ('.txt', '.msg'):
            msgf = '%s%s' % (main, ext)
            if os.path.exists(msgf):
                with open(msgf, 'r') as fp:
                    message = '\n'.join(
                        [line.rstrip() for line in fp.readlines()])

                break
    elif message:
        message = message.replace('\\n', '\n')

    if message and escaped:
        vals = {
            '%file': os.path.basename(pkg),
            '%size': '%s' % os.lstat(pkg)[stat.ST_SIZE],
            '%sha1': hash_digest(pkg, 'sha1'),
            '%md5': hash_digest(pkg, 'md5')
        }

        if maps:
            for key, value in maps.items():
                message = message.replace('%%%s' % key, value or '')

        for key, value in vals.items():
            message = message.replace(key, value or '')

    return message


class PkgImportSubcmd(SubCommand):
    COMMAND = 'pkg-import'
    ALIASES = ('pki',)

    help_summary = 'Import package file or directory to the remote server'
    help_usage = """\
%prog [options] ...

Unpack the local packages in order and import into the git repository

It tires to sort the package files and import into the git repository one by
one with the proposed branch. If specified, the tag will be created with the
package number with patterns.

Both option "message-template" and "tag-template" accept the Python
parenthesisd mapping key with %(N)s or %(NAME)s for capital pakcage name,
%(n)s or %(name)s as original name, and %(V)s or %(VERSION)s for capital
version string, %(v)s or %(version)s for normal version.

If tag_pattern is provided, the tag will be fetched from the file or directory
name. For example, bzip30 could be matched with (\\w+)(\\d)(\\d) as v3.0. And
sqlite-autoconf-3081101 could be (\\d\\d)(\\d\\d)(\\d\\d)(\\d\\d) as v3.8.11.1,
which is combinated with dot. Currently no more than four segments will be
handled. the program will treat the pkgname bzip and the revision v3.0 if the
option version-prefix "v" is omitted. In the case, %(NAME)s would be
"SQLITE-AUTOCONF" and %(name)s be "sqlite-autoconf". Both %(VERSION)s and
%(version)s are 38.11.1 without the default "v" as version-prefix.

The escaped variants are supported for the imported files including:

 %file - the imported file name
 %size - the size of the imported file
 %sha1 - the SHA-1 of the imported file
 %md5  - the MD5 value of the imported file
"""

    def options(self, optparse, inherited=False):
        if not inherited:
            SubCommand.options(self, optparse, option_import=True,
                               option_remote=True, modules=globals())

            options = optparse.get_option_group('--refs') or \
                optparse.add_option_group('Remote options')
            options.add_option(
                '-b', '--branch',
                dest="branch", action='store', metavar='BRANCH',
                help='Set the branch')
            options.add_option(
                '-n', '--name', '--project-name',
                dest="name", action='store', metavar='NAME',
                help='Set the project name. If it\'s not set, the name will '
                     'be generated from the git name')

        options = optparse.get_option_group('-a') or \
            optparse.add_option_group('Import options')
        options.add_option(
            '--init-path', '--init-import-path',
            dest='init_path', action='store',
            help='Set the initialized path with the provided path or '
                 'extracted package')
        options.add_option(
            '-l', '--local',
            dest='local', action='store_true',
            help='Set locally not to push the stuffs')
        options.add_option(
            '--keep-order', '--keep-file-order', '--skip-file-sort',
            dest='keep_order', action='store_true',
            help='Keep the order of input files or directories without sort')

        options = optparse.add_option_group('File options')
        options.add_option(
            '--auto-detect', '--skip-single-directory',
            dest='auto_detect', action='store_true',
            help='Ignore the root directory from the uncompressed package')
        options.add_option(
            '--vpref', '--version-prefix',
            dest='version_prefix', action='store',
            default='v', metavar='PREFIX',
            help='append the tag prefix ahead of the normal tag, it has no '
                 'effort with the option "tag-template", the default '
                 'is "%default"')
        options.add_option(
            '--temp-directory', '--temporary-directory',
            dest='temp_directory', action='store',
            help='Temporary directory for immediate storage')
        options.add_option(
            '--ppattern', '--pkg-pattern',
            dest='pkg_pattern', action='append', metavar='PATTERN',
            help='setup the matching pattern with the file or directory name '
                 'to pick out the pkgname and the version to decide the '
                 'importing order. The first match will be treated as the '
                 'package name {%(n)s in normal and %(N)s in capital} and '
                 'other will be built as the version {%(v)s or ${V}s}. More '
                 'than one pattern can be accepted')
        options.add_option(
            '--message-template',
            dest='message_template', action='store',
            help='Set the message template with the value from option '
                 '"--ppattern"')
        options.add_option(
            '--enable-escape',
            dest='enable_escape', action='store_true',
            help='Escape the messages with the known items like %sha1, '
                 '%md5, %file, %size, etc')
        options.add_option(
            '--version-template',
            dest='version_template', action='store',
            help='Set the tag template with the value from option '
                 '"--ppattern"')
        options.add_option(
            '--use-commit-file',
            dest='use_commit_file', action='store_true',
            help='Use the file like the imported file as the commit message')

        options = optparse.add_option_group('Filter options')
        options.add_option(
            '--filter-out',
            dest='filter_out', action='append', metavar='FILTER1,FILTER2',
            help='filter out not to import the directories or files which '
                 'match the filter pattern. More than one pattern can be '
                 'accepted')
        options.add_option(
            '--characters', '--filter-out-chars',
            dest='filter_out_chars', action='store',
            metavar='CHARS', default='-.',
            help='filter out the characters in the segments returned from '
                 'the option "ppattern", default: %default')
        options.add_option(
            '--filter-out-sccs',
            dest='filter_out_sccs', action='store_true',
            help='filter out the known sccs meta files including cvs, '
                 'subversion, mercurial. git is excluded as they can be '
                 'resued')

        options = optparse.add_option_group('Other options')
        options.add_option(
            '--show-order',
            dest='show_order', action='store_true',
            help='Show the import order for the listed files')

    def get_name(self, options):
        return options.name or '[-]'

    @staticmethod
    def split_name(fullname, patterns, filtered_chars):
        name, _ = os.path.splitext(os.path.basename(fullname))
        if name.endswith('.tar'):
            name = name[:len(name) - 4]

        for pattern in patterns or list():
            m = re.match(pattern, name)
            if m:
                res = [r for r in m.groups() if r is not None]
                if len(res) > 1:
                    return res[0], '.'.join(
                        [r.lstrip(filtered_chars) for r in res[1:]])

        return name, ''

    @staticmethod
    def build_packages(options, args, logger=None):
        name, pkgs, rets = None, dict(), list()
        for pkg in args:
            pkgname, revision = PkgImportSubcmd.split_name(
                pkg, options.pkg_pattern, options.filter_out_chars)

            if name and pkgname != name:
                logger and logger.warn(
                    'Warning: pkgname "%s" mismatched "%s"', pkgname, name)

            if options.pkg_pattern and not revision:
                logger and logger.error(
                    'Error: %s failed to be recognized with revision' % pkg)
            else:
                pkgs[revision] = (os.path.realpath(pkg), pkgname, revision)

                name = pkgname
                rets.append(pkgs[revision])

        if not options.keep_order and pkgs:
            rets = list()
            for rev in sorted(pkgs.keys(), key=key_compare(FileVersion.cmp)):
                rets.append(pkgs[rev])

        return len(rets) == len(args), name, rets

    @staticmethod
    def do_import(project, options, name, path, revision,
                  logger=None, *args, **kws):
        tmpl = dict({
            'n': name,             'name': name,
            'N': name.upper(),     'NAME': name.upper(),
            'v': revision,         'version': revision,
            'V': revision.upper(), 'VERSION': revision.upper()}
        )

        if options.tmpl_message:
            message = options.tmpl_message
        else:
            message = 'Import %s' % (
                '%s%s%s' % (
                    name,
                    (name and revision) and ' %s' % (options.prefix or ''),
                    revision))

        message = _handle_message_with_escape(
            path, options.tmpl_escape, message, dofile=options.tmpl_file)

        workplace = path
        tmpdir = options.directory or tempfile.mkdtemp()
        if os.path.isfile(path):
            FileUtils.extract_file(path, tmpdir)
            workplace = tmpdir

        count = 0
        if options.detect_root:
            dname = os.listdir(workplace)
            while 0 < len(dname) < 2:
                workplace = os.path.join(workplace, dname[0])
                dname = os.listdir(workplace)
                logger.info('Go into %s' % workplace)

        psource = os.path.join(project.path, options.subdir or '')
        timestamp = FileUtils.last_modified(workplace, recursive=False)

        scmtool = project if options.strict else None
        if options.imports is not None and os.path.exists(workplace):
            if options.cleanup or options.imports:
                FileUtils.rmtree(
                    psource, ignore_list=(r'^\.git.*',), scmtool=scmtool)

            if options.imports:
                timestamp = FileUtils.last_modified(workplace)
                FileUtils.copy_files(
                    workplace, psource,
                    symlinks=options.symlinks, scmtool=scmtool)
            else:
                diff = FileDiff(
                    psource, workplace, options.filters,
                    enable_sccs_pattern=options.filter_sccs)
                count = diff.sync(
                    logger, symlinks=options.symlinks, scmtool=scmtool)

                timestamp = diff.timestamp

        if options.washed:
            # wash the directory
            washer = FileWasher()
            washer.wash(workplace)

        for src, dest in options.copyfiles or list():
            names = glob.glob(os.path.join(workplace, src))
            filename = '' if not names else names[0]
            if os.path.exists(filename):
                mtime = FileUtils.last_modified(filename)
                if mtime > timestamp:
                    timestamp = mtime

                logger.debug('copy %s', src)
                FileUtils.copy_file(
                    filename, os.path.join(psource, dest),
                    symlinks=options.symlinks, scmtool=scmtool)
                count += 1

        for src, dest in options.linkfiles or list():
            names = glob.glob(os.path.join(workplace, src))
            filename = '' if not names else names[0]
            if os.path.exists(filename):
                mtime = FileUtils.last_modified(filename)
                if mtime > timestamp:
                    timestamp = mtime

                logger.debug('link %s', src)
                FileUtils.link_file(
                    src, os.path.join(psource, dest), scmtool=scmtool)
                count += 1

        ret, tags = 0, list()
        if count > 0:
            if not options.strict:
                project.add('--all', '-f', project.path)

            args = list()

            optgc = options.extra
            if optgc and optgc.author:
                args.append('--author="%s"' % optgc.author)
            if optgc and optgc.date:
                args.append('--date="%s"' % optgc.date.strip('\'"'))
            else:
                args.append('--date="%s"' % time.ctime(timestamp))

            args.append('-m')
            args.append(message)

            ret = project.commit(*args)

        if count > 0 or options.force:
            if options.tmpl_version:
                tags.append(options.tmpl_version % tmpl)
            elif options.local and revision:
                trefs = SubCommand.override_value(  # pylint: disable=E1101
                    options.refs, options.tag_refs) or ''
                if trefs:
                    trefs += '/'

                tags.append(
                    '%s%s%s' % (trefs, options.prefix or '', revision))
            elif revision:
                tags.append('%s%s' % (options.prefix or '', revision))

            if tags:
                if options.force:
                    ret, _ = project.tag(tags[-1], '--force')
                else:
                    ret, _ = project.tag(tags[-1])

        if os.path.lexists(tmpdir):
            try:
                shutil.rmtree(tmpdir)
            except OSError as e:
                logger.exception(e)

        return count > 0 and ret == 0, tags

    def execute(self, options, *args, **kws):  # pylint: disable=R0915
        SubCommand.execute(self, options, option_import=True, *args, **kws)

        logger = Logger.get_logger()  # pylint: disable=E1101

        ret, _, pkgs = PkgImportSubcmd.build_packages(options, args, logger)
        if not ret:
            return

        if options.show_order or (options.verbose and options.verbose > 0):
            print('Effective packages (%d)' % len(pkgs))
            print('----------------------------')
            for pkg, pkgname, revision in pkgs:
                print('%s %-15s %s' % (pkgname, '[v%s]' % revision, pkg))
            print

            if options.show_order:
                return

        RaiseExceptionIfOptionMissed(
            options.name, "project name (--name) is not set")
        RaiseExceptionIfOptionMissed(
            options.remote or options.offsite, 'remote (--remote) is set')
        RaiseExceptionIfOptionMissed(
            options.pkg_pattern or options.message_template,
            'pkg pattern (--pkg-pattern) is not set')
        RaiseExceptionIfOptionMissed(
            args, "no files or directories are specified to import")

        if not options.dryrun and options.remote:
            gerrit = Gerrit(options.remote, options)
            gerrit.create_project(
                options.name,
                description=options.description or False,
                options=options)

        branch = options.branch or 'master'

        name, _ = os.path.splitext(os.path.basename(options.name))
        path = os.path.join(options.working_dir, name)
        if options.offsite and not os.path.exists(path):
            os.makedirs(path)

        if options.remote:
            ulp = urlparse(options.remote)
            if not ulp.scheme:
                remote = 'git://%s/%s' % (
                    options.remote.strip('/'), options.name)
            else:
                remote = '%s/%s' % (options.remote.strip('/'), options.name)
        else:
            remote = ''

        project = GitProject(
            options.name,
            worktree=path,
            gitdir='%s/.git' % path,
            revision=branch,
            remote=remote)

        optgc = options.extra_values(options.extra_option, 'git-clone')
        ret = project.init_or_download(
            branch, single_branch=True, offsite=options.offsite,
            reference=optgc and optgc.reference)
        if ret != 0:
            logger.error('Failed to init the repo %s' % project)
            return False

        filters = list()
        if options.washed:
            filters = list([r'\.git/'])
            for fout in options.filter_out or list():
                filters.extend(fout.split(','))

        opti = Values.build(
            detect_root=options.auto_detect,
            directory=options.temp_directory,
            filter_sccs=options.filter_out_sccs,
            filters=filters,
            force=options.force,
            local=options.local,
            prefix=options.version_prefix,
            refs=options.refs,
            tag_refs=options.tag_refs,
            tmpl_escape=options.enable_escape,
            tmpl_file=options.use_commit_file,
            tmpl_message=options.message_template,
            tmpl_version=options.version_template,
            washed=options.washed,
            extra=options.extra_values(options.extra_option, 'git-commit'))

        tags = list()
        for pkg, pkgname, revision in pkgs:
            workplace = pkg
            if options.init_path:
                inited = os.path.join(workplace, options.init_path)
                if os.path.exists(inited):
                    workplace = inited

            _, ptags = PkgImportSubcmd.do_import(
                project, opti, pkgname, workplace, revision, logger=logger)

            if ptags:
                tags.extend(ptags)

        if not ret and not options.local:
            # pylint: disable=E1101
            # push the branches
            if self.override_value(
                    options.branches, options.all):
                ret = project.push_heads(
                    branch,
                    self.override_value(
                        options.refs, options.head_refs),
                    force=options.force, dryrun=options.dryrun)
            # push the tags
            if tags and self.override_value(
                    options.tags, options.all):
                optp = Values.build(fullname=True)
                ret = project.push_tags(
                    tags, self.override_value(
                        options.refs, options.tag_refs),
                    options=optp, force=options.force, dryrun=options.dryrun)
            # pylint: enable=E1101

        return ret == 0



import hashlib
import os
import re
import stat
import shutil
import tempfile
import time

from topics import FileDiff, FileUtils, FileWasher, GitProject, Gerrit, \
    Logger, SubCommand, RaiseExceptionIfOptionMissed


def _hash_digest(filename, mode):
    with open(filename, 'r') as fp:
        if mode == 'md5':
            return hashlib.md5(fp.read()).hexdigest()
        elif mode == 'sha1':
            return hashlib.sha1(fp.read()).hexdigest()

    return None


def _read_file_with_escape(pkg, escaped, default):
    message = default

    main, _ = os.path.splitext(pkg)
    for ext in ('.txt', '.msg'):
        msgf = '%s%s' % (main, ext)
        if os.path.exists(msgf):
            with open(msgf, 'r') as fp:
                message = '\n'.join([line.rstrip() for line in fp.readlines()])

            break

    if escaped:
        vals = {
            '%file': os.path.basename(pkg),
            '%size': '%s' % os.lstat(pkg)[stat.ST_SIZE],
            '%sha1': _hash_digest(pkg, 'sha1'),
            '%md5': _hash_digest(pkg, 'md5')
        }

        for key, value in vals.items():
            message = message.replace(key, value)

    return message


def _split_name(fullname, patterns, filtered_chars):
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


def _pkg_sort(a, b):
    va = a[2].split('.')
    vb = b[2].split('.')

    for k in range(min(len(va), len(vb))):
        maa = re.match(r'(?P<digit>\d+)(?P<patch>.*)', va[k])
        mab = re.match(r'(?P<digit>\d+)(?P<patch>.*)', vb[k])
        if maa and mab:
            if maa.group('digit') != mab.group('digit'):
                return cmp(
                    int(maa.group('digit')), int(mab.group('digit')))

            if maa.group('patch') != mab.group('patch'):
                return cmp(maa.group('patch'), mab.group('patch'))

        if cmp(va[k], vb[k]) != 0:
            return cmp(va[k], vb[k])

    return cmp(len(va), len(vb))


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
option tag_prefix "v" is omitted. In the case, %(NAME)s would be
"SQLITE-AUTOCONF" and %(name)s be "sqlite-autoconf". Both %(VERSION)s and
%(version)s are 38.11.1 without the default "v" as tag_prefix.

The escaped variants are supported for the imported files including:

 %file - the imported file name
 %size - the size of the imported file
 %sha1 - the SHA-1 of the imported file
 %md5  - the MD5 value of the imported file
"""

    def options(self, optparse):
        SubCommand.options(self, optparse, option_import=True,
                           option_remote=True)

        options = optparse.get_option_group('--refs') or \
            optparse.add_option_group('Remote options')
        options.add_option(
            '-b', '--branch',
            dest="branch", action='store', metavar='BRANCH',
            help='Set the branch')
        options.add_option(
            '-n', '--name', '--project-name',
            dest="name", action='store', metavar='NAME',
            help='Set the project name. If it\'s not set, the name will be '
                 'generated from the git name')
        options.add_option(
            '--tpref', '--tag-prefix',
            dest='tag_prefix', action='store', default='v', metavar='PREFIX',
            help='append the tag prefix ahead of the normal tag, it has no '
                 'effort with the option "tag-template", the default '
                 'is "%default"')

        options = optparse.get_option_group('-a') or \
            optparse.add_option_group('Import options')
        options.add_option(
            '--author',
            dest='author', action='store',
            help='Set the commit author')
        options.add_option(
            '--init-path', '--init-import-path',
            dest='init_path', action='store',
            help='Set the initialized path with the provided path or '
                 'extracted package')
        options.add_option(
            '--temp-directory', '--temporary-directory',
            dest='temp_directory', action='store',
            help='Temporary directory for immediate storage')
        options.add_option(
            '--auto-detect', '--skip-single-directory',
            dest='auto_detect', action='store_true',
            help='Ignore the root directory from the uncompressed package')
        options.add_option(
            '-l', '--local',
            dest='local', action='store_true',
            help='Set locally not to push the stuffs')
        options.add_option(
            '--keep-file-order', '--skip-file-sort',
            dest='keep_file_order', action='store_true',
            help='Keep the order of input files or directories without sort')

        options = optparse.add_option_group('File options')
        options.add_option(
            '--iversion', '--ignore-version',
            dest='ignore_version', action='store_true',
            help='Ignore the fail to fetch the version from the file or '
                 'directory name')
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
        options.add_option(
            '--enable-escape',
            dest='enable_escape', action='store_true',
            help='Escape the messages with the known items like %sha1, '
                 '%md5, %file, %size, etc')
        options.add_option(
            '--message-template',
            dest='message_template', action='store',
            help='Set the message template with the value from option '
                 '"--ppattern"')
        options.add_option(
            '--tag-template',
            dest='tag_template', action='store',
            help='Set the tag template with the value from option '
                 '"--ppattern"')

    def get_name(self, options):
        return options.name or '[-]'

    def execute(self, options, *args, **kws):  # pylint: disable=R0915
        SubCommand.execute(self, options, option_import=True, *args, **kws)

        logger = Logger.get_logger()  # pylint: disable=E1101

        pkgs, name = list(), None
        for pkg in args:
            pkgname, revision = _split_name(
                pkg, options.pkg_pattern, options.filter_out_chars)

            if name and pkgname != name:
                logger.warn(
                    'Warning: pkgname "%s" mismatched "%s"', pkgname, name)

            if not revision and not options.ignore_version:
                logger.error(
                    'Error: %s failed to be recognized with revision' % pkg)
            else:
                name = pkgname
                pkgs.append((os.path.realpath(pkg), pkgname, revision))

        if len(pkgs) != len(args):
            return

        if not options.keep_order:
            pkgs.sort(_pkg_sort)

        if options.show_order or options.verbose > 0:
            print 'Effective packages'
            print '----------------------------'
            for pkg, pkgname, revision in pkgs:
                print '%s %-15s %s' % (pkgname, '[v%s]' % revision, pkg)
            print

            if options.show_order:
                return

        RaiseExceptionIfOptionMissed(
            options.name, "project name (--name) is not set")
        RaiseExceptionIfOptionMissed(
            options.ignore_version or options.pkg_pattern,
            "pkg pattern (--pkg-pattern) is not set")
        RaiseExceptionIfOptionMissed(
            args, "no files or directories are specified to import")

        if not options.tryrun and options.gerrit:
            gerrit = Gerrit(options.gerrit)
            gerrit.createProject(
                options.name,
                description=options.description or False)

        path, _ = os.path.splitext(os.path.basename(options.name))

        branch, tagp = options.branch, ''
        if options.refs:
            tagp = '%s/' % options.refs
            branch = '%s/%s' % (options.refs, branch or 'master')

        path = os.path.realpath(path)
        if options.offsite and not os.path.exists(path):
            os.makedirs(path)

        remote = '%s/%s' % (options.remote.rstrip(), options.name) \
            if options.remote else None

        project = GitProject(
            options.name,
            worktree=path,
            gitdir='%s/.git' % path,
            revision=branch,
            remote=remote)

        ret = project.init_or_download(
            branch, single_branch=True, offsite=options.offsite)
        if ret != 0:
            logger.error('Failed to init the repo %s' % project)
            return False

        temp = options.temp_directory or tempfile.mkdtemp()
        tags = list()
        filter_out = list([r'\.git/'])
        for fout in options.filter_out or list():
            filter_out.extend(fout.split(','))

        for pkg, pkgname, revision in pkgs:
            workp = pkg

            tmpl = dict({
                'n': pkgname,
                'name': pkgname,
                'N': pkgname.upper(),
                'NAME': pkgname.upper(),
                'v': revision,
                'version': revision,
                'V': revision.upper(),
                'VERSION': revision.upper()})

            if options.message_template:
                message = options.message_template % tmpl
            else:
                message = 'Import %s' % (
                    '%s%s%s' % (
                        pkgname,
                        revision and ' %s' % options.tag_prefix,
                        revision))

            if options.use_commit_file:
                message = _read_file_with_escape(
                    pkg, options.enable_escape, message)

            if os.path.isfile(pkg):
                FileUtils.extract_file(pkg, temp)
                workp = temp

            if options.init_path:
                inited = os.path.join(workp, options.init_path)
                if os.path.exists(inited):
                    workp = inited

            if options.washed:
                if workp != temp:
                    os.makedirs(temp)
                    shutil.copytree(workp, temp, symlinks=True)
                    # wash the directory
                    washer = FileWasher(
                        temp, overrideReadOnly=True,
                        eol=options.washer_eol,
                        tab=options.washer_tabsize > 0,
                        trailing=options.washer_trailing)
                    if washer.wash(temp):
                        workp = temp

            if options.auto_detect:
                dname = os.listdir(workp)
                while 0 < len(dname) < 2:
                    workp += '/%s' % dname[0]
                    dname = os.listdir(workp)
                    logger.info('Go into %s' % workp)

            diff = FileDiff(project.path, workp, filter_out,
                            enable_sccs_pattern=options.filter_out_sccs)
            if diff.sync(project, logger) > 0:
                args = list()
                if options.author:
                    args.append('--author="%s"' % options.author)

                args.append('-m')
                args.append(message)
                args.append('--date="%s"' % time.ctime(diff.timestamp))

                ret = project.commit(*args)
                if ret == 0:
                    if options.tag_template:
                        tags.append(options.tag_template % tmpl)
                    else:
                        tags.append(
                            '%s%s%s' % (tagp, options.tag_prefix, revision))
                    ret, _ = project.tag(tags[-1])

            if os.path.lexists(temp):
                try:
                    shutil.rmtree(temp)
                except OSError, e:
                    logger.exception(e)

        # push the branches
        if not options.tryrun and not options.local:
            ret = 0
            if self.overrided_value(  # pylint: disable=E1101
                    options.branches, options.all):
                ret = project.push_heads(
                    branch, options.refs, force=options.force)
            # push the tags
            if ret == 0 and tags and \
                self.overrided_value(  # pylint: disable=E1101
                        options.tags, options.all):
                ret = project.push_tags(
                    tags, None, fullname=True, force=options.force)

        return ret

krep: Tool to manage git repository immigration
================================================

The `krep` project on the branch contains the stuffs on the upstream `cm`
branch and was implemented as a workable toolkit with several sub-commands to
handle git repositories and/or [git-repo] projects to immigrate into owned
[gerrit] or git server.

The toolkit based on the tool framework on branch `cm`, which provides most of
the basic `git` functions and [git-repo] supports.

Currently, the toolkit supports the following sub-commands printed by `help`
sub-command:

```bash
$ krep help
Usage: krep subcmd [args] ...
The commands of krep are:

  help           Print the command summaries
  batch          Load and executes projects from specified files
  git-b          Download and import git bare repository
  git-p          Download and import git repository
  pkg-import     Import package file or directory to the remote server
  pki            Alias of "pkg-import"
  repo           Download and import git-repo manifest project
  repo-mirror    Download and import git-repo mirror project
  topic          Print the topic summaries

See more info with "krep help <command>"
```

Though the main idea comes from [git-repo][], it extends to load the component
named `topic` in the directory `topics`, and the sub-commands in the directory
`krep_subcmds`. The implemented sub-commands prefer to use the standard Python
libraries and the exported `class` from the exported `topic` classes, which are
guaranteed to be used continuously. Other classes might be visited but not
encouraged to use at all.

The tool can also support to immigrate the git into a git or gerrit server, for
example, to immigrate the official linux git repository:

```bash
$ krep git-p -n kernel/linux --remote git://some-git-server --refs official \
  --all --git git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
```

And the `repo-mirror` command supports [git-repo] projects, for example, [AOSP]
project:

```bash
$ krep repo-mirror --remote git://some-git-server --refs aosp --all \
  --manifest-url git://android.googlesource.com/platform/manifest
```

The parameters of the two sub-commands can be coded into a XML file, for
example, `project.xml` and use the `batch` sub-command to run together (As
`repo-mirror` supports the multiple threads, it's not supported to run the two
sub-commands in parellel.)

```xml
<?xml version="1.0" encoding="utf-8"?>
<projects>
  <project name="aosp" group="android">
    <option name="manifest" value="git://android.googlesource.com/platform/manifest" />
    <option name="schema" value="repo-mirror" />
    <option name="working-dir" value="mirror" />
    <option name="refs" value="aosp" />
    <replace-patterns category="revision-rp">
      <pattern name="tools/repo$" value="~aosp/~~" />
    </replace-patterns>
  </project>
  <project name="kernel/linux" group="gpl,linux,kernel">
    <option name="git" value="git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git" />
    <option name="schema" value="git-p" />
    <option name="working-dir" value="linux-stable" />
    <option name="refs" value="official" />
  </project>
</projects>
```

With the file, `batch` command could be:

```bash
$ krep batch --remote git://some-git-server -f project.xml
```

The tool would read the tool configuration file from `/etc/default/krepconfig`
and `~/.krepconfig`. Some configurable values can be put to the files to
simplify the command line, for example:

```ini
job = 8
remote = git://some-git-server
```

*NOTE:* The project updates to use *LGPL v3* as the license. It's appreciated to
contribute the fixes and the ideas to improve the tool but it's not mandatory to
open source of the plug-ins.

[AOSP]: https://source.android.com
[gerrit]: https://www.gerritcodereview.com
[git-repo]: https://gerrit.googlesource.com/git-repo

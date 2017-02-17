krep: Tool to manage git repository importing
==============================================

The `krep` project on the branch contains the stuffs on the `base` branch and
adds the supports of the prorject idea, [gerrit], `git` commands,
[git-repo] manifest, etc. One extra sub-command `batch` is implemented to run
other sub-commands with a batch file in the `config` format.

Though the main idea comes from [git-repo], it extends to load the component
named `topic` in the directory `topics`, and the sub-commands in the directory
`krep_subcmds`. The implemented sub-commands can only use the standard Python
libraries and the exported `class` from the exported `topic` classes.

`krep` project is a toolkit containing several tools to handle git repository
and/or [git-repo] projects to import owned [gerrit] or git server.

The toolkit based on the tool framework on branch `cm` of this repository, which
provides most of the basic `git` functions.

Currently, the toolkit supports the commands:

```bash
$ krep help
Usage: krep subcmd [args] ...
The commands of krep are:

  help           Print the command summaries
  batch          Load and executes projects from specified files
  git-b          Download and import git bare repository
  git-p          Download and import git repository
  repo           Download and import git-repo manifest project
  repo-mirror    Download and import git-repo mirror project
  topic          Print the topic summaries

See more info with "krep help <command>"
```

Sub-command `batch` supports to run with `batch` files, which hold other sub-
commands and parameters. `git-b` downloads a git bare repository but `git-p`
downloads a normal one. `repo` is the sub-command to work with a [git-repo]
project while `repo-mirror` works with a mirror [git-repo] project.

Sub-command `topic` lists the supported functions provided by the Python file
in the `topics` directory. At the time, the output of the sub-command is:

```bash
$ ./krep topic
The topics of krep are:

 Command                       Executes a local executable command
 ConfigFile                    No description
 DownloadError                 Indicate the unsuccessful download
 ExecutableNotFoundError       Indicate the executable not found
 FileUtils                     Utility to handle file operations
 Gerrit                        Provides Gerrit access
 GerritError                   Indicate the unsuccessful gerrit processing
 GitProject                    Manages the git repository as a project
 KrepError                     Root exception for krep
 Logger                        Provides the logging methods
 Manifest                      No description
 ManifestException             No description
 OptionMissedError             Indicate the missed option
 Pattern                       Contains pattern categories with the format...
 ProcessingError               Indicate the unsuccessful processing
 RaiseExceptionIfOptionMissed  Raise OptionMissedError if the option or options are missed
 SubCommand                    Supports to run as the tool running command
 SubCommandNotDetectedError    Indicate the sub-command of a command cannot be found
 SubCommandWithThread          Commands with threading method to run with multiple jobs

See more info with "krep topic <topic>"
```

The tool can support the git into a git server w/o gerrit, for example, to
import the official linux git repository:

```bash
$ krep git-p -n kernel/linux --remote ccc@localhost --refs official --all \
  --git git://git.kernel.org/pub/scm/linux/kernel/git/stable/linux-stable.git
```

And the `repo-mirror` command can import a [git-repo] project, for example,
Android project:

```bash
$ krep repo-mirror --remote ccc@localhost --refs aosp --all \
  --manifest-url git://android.googlesource.com/platform/manifest
```

The parameters of the two sub-commands can be put into a XML file, `project.xml`
here and use the `batch` sub-command to run together (As `repo-mirror` supports
the multiple thread, it's not supported to run the two sub-commands in
parellel.)

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

The `batch` command could be simply:

```bash
$ krep batch -f project.xml
```

*NOTE:* The project updates to use *LGPL v3* as the license. It's appreciated to
contribute the fixes and the ideas to improve the tool but it's not mandatory to
open source of the plug-ins.

The framework provides to load the `topics` and subcommands with specified
environment variables, which works like the environment variable `PATH`:

| Variable | Description |
|----------------|-----------------------------------------------------------------|
| `KREP_EXTRA_PATH` | Directories containing the subdirectories `topics` and `subcmd` |
| `KREP_TOPIC_PATH` | Directories containing the `topic` files |
| `KREP_SUBCMD_PATH` | Directories containing the sub-commands |

[gerrit]: https://www.gerritcodereview.com
[git-repo]: https://gerrit.googlesource.com/git-repo

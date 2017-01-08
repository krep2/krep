krep: Tool to manage git repository importing
==============================================

The `krep` project on the branch contains the stuffs on the `base` branch and
adds the supports of the prorject idea, [gerrit][], `git` commands,
[git-repo][] manifest, etc. One extra sub-command `batch` is implemented to run
other sub-commands with a batch file in the `config` format.

Though the main idea comes from [git-repo][], it extends to load the component
named `topic` in the directory `topics`, and the sub-commands in the directory
`krep_subcmds`. The implemented sub-commands can only use the standard Python
libraries and the exported `class` from the exported `topic` classes.

`krep` project is a toolkit containing several tools to handle git repository
and/or [git-repo][] projects to import owned [gerrit][] or git server.

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
downloads a normal one. `repo` is the sub-command to work with a [git-repo][]
project while `repo-mirror` works with a mirror [git-repo][] project.

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

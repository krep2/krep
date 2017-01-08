krep: Tool framework for extension
==================================

The `krep` project on the branch contains the stuffs on the `base` branch and
adds the supports of the prorject idea, [gerrit][], `git` commands,
[git-repo][] manifest, etc. One extra sub-command `batch` is implemented to run
other sub-commands with a batch file in the `config` format.

Though the main idea comes from [git-repo][], it extends to load the component
named `topic` in the directory `topics`, and the sub-commands in the directory
`krep_subcmds`. The implemented sub-commands can only use the standard Python
libraries and the exported `class` from the exported `topic` classes.

Topic
-----

The directory `topics` can contain any of Python files with implemented classes.
Only the class listed in the string `TOPIC_ENTRY` will be loaded and exported
to the run-time system under the module `topic`.

For example, `SubCommand` is the parent class for all sub-commands. It can be
imported like:

```python
from topics import SubCommand
```

Sub-command
-----------

Sub-command is implemented to support specified activities, which can use the
common functions provided by Python libraries and extra functions by `topics`.

As all commands are dynamically loaded, the framework can be easily implemented
with different purpose.


Development
-----------

With the framework, it's not hard to extend it as a `Configuration Management`
tookit with specific sub-commands to run over `git` repositories, or even use
[git-repo][] manifest to operate with the large project in one time.

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

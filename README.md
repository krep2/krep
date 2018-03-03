krep: Tool framework for extension
==================================

The `krep` project on the branch contains the elemental construction to build
an extensible tool.

The main idea for the loaded sub-command refers to Google tool [git-repo][].

It relies on the dynamic language Python to load the components named `topic` in
the directory `topics`, and the sub-commands in the directory `krep_subcmd`.
The implemented sub-commands prefer to use the standard Python libraries and the
exported `class` from the exported `topic` classes, which are guaranteed to be
used continuously. Other classes might be visited but not encouraged to use at
all.

Topic
-----

The directory `topics` can contain any of Python files with implemented classes.
Only the classes listed in the string `TOPIC_ENTRY` with comma as the delimiter
will be loaded and exported to the run-time system under the module `topic`.

For example, `SubCommand` is the parent class for all sub-commands. It can be
imported like:

```python
from topics import SubCommand
```

Sub-command
-----------

Sub-command is implemented to support specified activities, which can use the
common functions provided by Python libraries and extra functions by `topics`.
It can be executed from the command line.

As all commands are dynamically loaded, the framework can be easily implemented
with different purpose.


Development
-----------

With the framework, it's quite easy to implement the owned toolkit.

The basic sense is to implement the common API classes as `topic`s and write
the singleton sub-commands using the `topic`s.

*NOTE:* The project updates to use *LGPL v3* as the license. It's appreciated to
contribute the fixes and the ideas to improve the tool but it's not mandatory to
open source of the plug-ins.

The framework provides to load the `topics` and subcommands with specified
environment variables, which works like the environment variable `PATH`:

| Variable | Description |
|----------------|-----------------------------------------------------------------|
| `KREP_EXTRA_PATH` | Directories containing the subdirectories `topics` and `subcmd` |
| `KREP_HOOK_PATH` | Directories containin the hooks |
| `KREP_TOPIC_PATH` | Directories containing the `topic` files |
| `KREP_SUBCMD_PATH` | Directories containing the sub-commands |

With these variables, external `topic`s and `subcommand`s can be loaded and executed.

[git-repo]: https://gerrit.googlesource.com/git-repo

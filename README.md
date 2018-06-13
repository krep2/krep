![](https://img.shields.io/badge/python-2.7%2C%203.6-blue.svg)

# krep: Tool framework for extension

The `krep` project on the branch contains the elemental construction to build
an extensible tool.

It relies on the dynamic language Python to load the components named `topic` in
directory `topics`, and the sub-commands in directory `krep_subcmd`.
The implemented sub-commands prefer to use the standard Python libraries and the
exported `class` from exported `topic` entries, which are guaranteed to be
used continuously. Other classes might be accessible but not encouraged to use
at all.

## Topic

The directory `topics` can contain Python files as implemented classes.
Only the classes listed in the string `TOPIC_ENTRY` with comma as the delimiter
will be exported to the run-time system under the module `topic` to be used by
sub-commands.

For example, `SubCommand` is the parent class for all sub-commands. It can be
imported like:

```python
from topics import SubCommand
```

The implemented sub-command class needn't know where `SubCommand` is implemented
in the exported list.

## Sub-command

The main idea for the loaded sub-command refers to Google tool [git-repo].

Sub-command is implemented to support specified activities, which can use the
common functions provided by Python libraries and extra functions by `topics`.
It can be executed from the command line.

As all commands are dynamically loaded, the framework can be easily implemented
with different purpose.

## Development

With the framework, it's quite easy to implement the owned toolkit. Following
defined environment variables will impact the program with the framework.

| Variable | Description |
|----------------|-----------------------------------------------------------------|
| `KREP_VERBOSE` | The default verbose for logging |
| `KREP_EXTRA_PATH` | Directories containing the subdirectories `topics` and `subcmd` |
| `KREP_HOOK_PATH` | Directories containin the hooks |
| `KREP_TOPIC_PATH` | Directories containing the `topic` files |
| `KREP_SUBCMD_PATH` | Directories containing the sub-commands |

### sub-commands and topics

The basic sense is to implement the common API classes as `topic`s and write
sub-commands using the `topic`s.

The framework provides to load the `topics` and subcommands with specified
environment variables, which work like the environment variable `PATH`. Not like
the default directories in the code, only one-level directory will be detected
to load the files. 

With these variables, external `topic`s and `subcommand`s can be loaded and
executed. [repo-diff] is a demonstrated and workable project as `krep` plug-in,
which explained how to use the environment variables to load both `topic` and
`subcommand`s.

### options

The framework provides a quite convenient way to add sub-command options beyond
the actual running commands. The base class `SubCommand` will enumerate each
loaded class and check if the method `options` existed to load the functional
options.

With the implementation, every big function can provide its option. What's more,
an injection option is implemented to pass options to wrapped sub-command. And
an extra implementation with the option "extra-option" can supply the options
for the functions, which may call external commands with complicated options and
arguments. To implement the function, just a list named `extra_items` need be
created. For instance, [gerrit.py] can be referred.

Option `verbose` and `dry-run` are supported to debug the framework and plug-ins
exhanced by the framework.

### hooks

Like many tools work in phrase, *hook* is supported by the framework, a option
"hook-dir" is provided to indicate the locations of hooks for running
`subcommand`. The environment variable `KREP_HOOK_PATH` indicates the directory
either for all sub-commands. all hooks named by the phrases will be loaded and
executed from the directories.

If the sub-command uses an XML configurable file, element `hook` could specify
the named hook for delicated phrases explicitly.

The subcommand can define its own phrase with a named string. The corresponding
hook could be invoked with the line:

```python
SubCommand.do_hook(hook_name, options, dryrun=options.dryrun)
```

What's more, an alternative method `SubCommand.run_hook` can be used to execute
an external command as a hook when implementing a sub-command.

### configurations

The framework tries to load two default configuration files if they're existed:

- /etc/default/krepconfig
- ~/.krepconfig

Users can provide the configurable items from the command line. The late ones
will override the items in the previous file.

And two file formats are support:

- [git-config file format](https://git-scm.com/docs/git-config/2.16.0#_configuration_file)
- XML format

within the XML format, many patterns to include (positive) or exclude (negative)
rules are supports. These patterns can help to create the specific rule when
building sub-commands with the framework.

### multi-threading

`sub-command` supports multi-threading with the method
`SubCommandWithThread.run_with_thread`. The thread number is decided by the
option `jobs`.

### logging

Python provides its `logging` method. As `krep` framework can run in
multi-threading method, a specific implementation has been done to run named
logger with thread. Each sub-command can has its own logger named with the
sub-command or the project name if it's set.

`KREP_VERBOSE` could be set to the expected level to debug the loading process
before the option `verbose` has been handled and set to `logging`.

> *NOTE:* The project updates to use *LGPL v3* as the license. It's appreciated to
> contribute the fixes and the ideas to improve the tool but it's not mandatory to
> open source of the plug-ins.

[gerrit.py]: https://github.com/cadappl/krep/blob/cm/topics/gerrit.py
[git-repo]: https://gerrit.googlesource.com/git-repo
[repo-diff]: https://github.com/cadappl/krep_plugin_git_diff

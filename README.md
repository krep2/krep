krep: Tool framework for extension
==================================

The `krep` project on the branch contains the elemental construction to build
an extensible tool.

The main idea for the loaded sub-command refers to Google tool [git-repo][].

It relies on the dynamic language Python to load the component named `topic` in
the directory `topics`, and the sub-commands in the directory `krep_subcmd`.
The implemented sub-commands can only use the standard Python libraries and the
exported `class` from the exported `topic` classes.

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

With the framework, it's quite easy to implement the owned toolkit.

The basic sense is to implement the common API classes as `topic`s and write
the singleton sub-commands using the `topic`s.

[git-repo]: https://gerrit.googlesource.com/git-repo

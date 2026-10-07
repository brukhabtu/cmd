# Plugins

Everything cmd shows comes from a plugin. Plugins live in
`~/Library/Application Support/cmd/plugins`, one directory each, and the `cmd plugin`
command manages them. Until the Homebrew cask puts `cmd` on your `PATH`, run it from the
bundle:

```sh
alias cmd=/Applications/cmd.app/Contents/MacOS/cmd
```

## Install, update, remove

```sh
cmd plugin install calculator      # a plugin from the index
cmd plugin install owner/name      # a plugin from a GitHub repository
cmd plugin list                    # what is installed, and what the index has
cmd plugin update                  # index plugins to their reviewed version, others to their latest
cmd plugin remove calculator
```

A plugin from the [index](catalogue.md) installs at the version someone reviewed. A plugin
from anywhere else runs whatever its author pushes, and cmd says so the first time.

A newly installed plugin starts the next time cmd starts. There is no quit command yet, so
`killall cmd` and open it again (TASK-1.31 will pick new plugins up without that). Editing
an installed plugin's files reloads it straight away. The full usage is on the
[command line](../reference/cli.md) page.

!!! abstract "To be written"
    Choosing plugins, keywords that collide, and plugins that need permissions. Tracked by
    the documentation epic (TASK-1.43).

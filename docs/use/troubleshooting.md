# Troubleshooting

!!! abstract "To be written"
    A page per symptom. Tracked by the documentation epic (TASK-1.43). Until then, the
    common ones:

- **macOS says the app is damaged or cannot be opened.** The build is not signed yet;
  clear the quarantine as [Install](install.md) shows.
- **The line under the input names a plugin that did not start.** The message says why;
  `cmd plugin doctor <directory>` runs that plugin the way the launcher does and prints
  what it answers.
- **Nothing happens on ++option+space++.** Another app may hold the shortcut; quit it or
  change cmd's hotkey (to be documented).
- **The first launch shows "fetching Python" for a long time.** It needs the network once,
  to fetch the Python the plugins run on.

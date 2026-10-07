# Publishing a plugin

A plugin anyone can install is a git repository (or a directory in one) with the three
files the [tutorial](tutorial.md) builds. People install it with
`cmd plugin install owner/name`. To have it in the [index](../use/catalogue.md), where it
installs at a reviewed commit, open a pull request that adds it to `plugins/index.toml`;
[decision 8](../core/decisions/decision-8.md) says how the index works and why.

!!! abstract "To be written"
    The pull request step by step, what review looks for, versions and updates. Tracked by
    the documentation epic (TASK-1.43).

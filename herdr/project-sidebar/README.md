# FirstMate projects

The panel is a separate terminal tree: project folders, with assigned agents
under them. It is not inserted into the native Agents or Spaces sidebar.
Open it only after the plugin is enabled:

```sh
herdr plugin pane open --plugin fm.project-sidebar --entrypoint tree --placement split --direction right --no-focus
```

`j`/`k` move. Enter folds a folder. `q` quits. The panel does not focus,
move, or close panes, and it does not replace the Agents view.

Sidebar labels remain the older optional path. Startup no longer rewrites
them. `reconcile` and `clear` are still explicit actions.

## Configure

A current-home version 1 journal is only a projection attempt. Ownership still requires the task record's Herdr session, workspace, tab, and pane to match the live pane, and that pane's foreground cwd, or its launch cwd when no foreground cwd is present, to match the recorded worktree. A launch cwd cannot override a contradictory foreground cwd. A token in the workspace title is not enough. Version 2 journals keep their stricter binding.

The plugin does nothing until its config names one FirstMate home:

```toml
home = "/path/to/firstmate-home"
```

Put that file at the directory printed by `herdr plugin config-dir fm.project-sidebar`.
Do not point it at a home you have not chosen. The plugin reads only
`state/<task>.meta` project and Herdr endpoint fields, and
`state/<task>.herdr-presentation` version-2 bindings. It does not read chats,
status logs, or credentials.

Sidebar rows are yours to add. This plugin does not edit Herdr config:

```toml
[ui.sidebar.spaces]
rows = [
  ["state_icon", "workspace"],
  ["$project"],
]

[ui.sidebar.agents]
rows = [
  ["state_icon", "$project", "agent"],
]
```

Then reload config yourself. Without `$project`, the order still changes and
the token is visible to `workspace list` / `pane list`.

## Install

Linking registers the plugin for every Herdr session on this user. Do that
only when you want it:

```sh
herdr plugin link /path/to/herdr/project-sidebar
herdr plugin enable fm.project-sidebar
```

Disable or unlink to stop new runs. Tokens already reported stay until
`herdr plugin action invoke clear --plugin fm.project-sidebar`. Clear
removes only this plugin's agent view. It does not restore another tool's view.

Reconcile does not replace a foreign Agents view. It first sends
`agent.view.clear` for its own source. Herdr leaves a different owner's view
unchanged and names that owner in the response. An inactive view, or one this
plugin already owns, may then be set. A foreign owner, a missing source, or an
unreadable response is left alone. Project labels and space order still update.
The only native owner check is that clear. If this plugin already owns the view, the clear removes it, and reconcile sets it again. A foreign view is not removed. The check is not atomic. There is no opt-in that takes over a foreign view.

`install.sh` does not link this plugin.

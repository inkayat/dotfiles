# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- `herdr/config.toml` and `herdr/plugins/usagebar/config.toml` are the tracked Herdr settings; `herdr/plugins.txt` pins the enabled GitHub plugin commits (`owner/repo commit` per line). Run `./install.sh` to install those plugins via the `herdr` CLI and copy the tracked configs into place (only when content differs); it validates with `herdr config check` and reloads a running server without failing if none is running.
- Never commit Herdr's generated state: `plugins.json`, downloaded plugin trees, `*.log`, `session.json`, `release-notes.json`, sockets, or credentials.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.

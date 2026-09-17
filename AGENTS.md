# dotfiles (Herdr)

This repo pins and reconciles Herdr plugins/config via `install.sh`.

## Layout
- `herdr/plugins.txt` — enabled GitHub plugins, one `<owner>/<repo> <pinned-commit>` per line.
- `herdr/config.toml` — main Herdr config, copied to `$XDG_CONFIG_HOME/herdr/config.toml` (or `$HERDR_CONFIG_PATH`). All key mappings for every enabled plugin live here as `[[keys.command]]` blocks.
- `herdr/plugins/<plugin>/config.toml` — per-plugin config, copied to the plugin's `herdr plugin config-dir <plugin>` output. Currently only `usagebar` has one.
- `install.sh` — POSIX `sh`, `set -eu`. Installs every pinned plugin, then copies configs, then runs `herdr config check`.

## herdr CLI quirk (load-bearing)
`herdr plugin install` requires the positional `<owner>/<repo>` argument **before** any `--ref`/`--yes` options. Options given first make it exit 2 with a usage error instead of skipping them. Under `set -eu` this aborts the whole install loop on the very first plugin — this was the root cause of a beta install only registering 0-1 of 4 plugins. Keep the call as `herdr plugin install "$repo" --ref "$ref" --yes`.

## Adding/updating a plugin
1. Add/update the `<owner>/<repo> <commit>` line in `herdr/plugins.txt`.
2. Add its `[[keys.command]]` block(s) to `herdr/config.toml` (and a per-plugin `herdr/plugins/<name>/config.toml` if it has plugin-scoped settings, mirroring `usagebar`).
3. Verify with `tests/test_install_all_plugins.sh` (runs `install.sh` against `tests/fixtures/herdr` — a fake `herdr` binary — on a throwaway `$HOME`, offline) and, if the real `herdr` CLI is available, `herdr config check` against the copied config.

## Tests
`sh tests/test_install_all_plugins.sh` — regression test for the CLI quirk above; asserts a clean-home install registers every pinned plugin and applies every keymap. No network/real `herdr` binary required.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.

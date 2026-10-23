#!/bin/sh
# Herdr plugin PATH is minimal. Prefer the usual interpreters without a daemon.
set -eu
PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$PATH"
export PATH
cd "$(dirname "$0")/.."
if [ "${1:-}" = "tree" ]; then
  exec python3 tree.py
fi
if [ "${1:-}" = "open-tree" ]; then
  herdr_bin="${HERDR_BIN_PATH:-herdr}"
  exec "$herdr_bin" plugin pane open --plugin fm.project-sidebar --entrypoint tree --placement split --direction right --no-focus
fi
exec python3 reconcile.py "$@"

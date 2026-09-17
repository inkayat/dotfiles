#!/bin/sh
# Install/reconcile Herdr plugins and settings from this dotfiles repo.
# Requires only POSIX shell utilities and the `herdr` CLI on PATH.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)

command -v herdr >/dev/null 2>&1 || {
    echo "install.sh: 'herdr' CLI not found on PATH" >&2
    exit 1
}

copy_if_changed() {
    src=$1
    dest=$2
    dest_dir=$(dirname -- "$dest")
    mkdir -p -- "$dest_dir"
    if [ -f "$dest" ] && cmp -s -- "$src" "$dest"; then
        echo "install.sh: $dest already up to date"
    else
        cp -- "$src" "$dest"
        echo "install.sh: wrote $dest"
    fi
}

# --- Install/reconcile pinned plugins ---
manifest="$script_dir/herdr/plugins.txt"
while IFS=' ' read -r repo ref || [ -n "$repo" ]; do
    case "$repo" in
        ''|'#'*) continue ;;
    esac
    echo "install.sh: installing $repo @ $ref"
    herdr plugin install "$repo" --ref "$ref" --yes
done <"$manifest"

# --- Apply main config ---
config_dest=${HERDR_CONFIG_PATH:-${XDG_CONFIG_HOME:-$HOME/.config}/herdr/config.toml}
copy_if_changed "$script_dir/herdr/config.toml" "$config_dest"

# --- Apply usagebar plugin config ---
usagebar_config_dir=$(herdr plugin config-dir usagebar)
copy_if_changed "$script_dir/herdr/plugins/usagebar/config.toml" "$usagebar_config_dir/config.toml"

# --- Validate resulting config ---
herdr config check

# --- Reload a running server if possible; a stopped server is not a failure ---
if herdr server reload-config >/dev/null 2>&1; then
    echo "install.sh: reloaded running server config"
else
    echo "install.sh: no running server reloaded; settings apply on next launch"
fi

echo "install.sh: done"

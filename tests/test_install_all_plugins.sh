#!/bin/sh
# Regression test: a clean ("beta") install must install every plugin
# pinned in herdr/plugins.txt and apply every keymap in herdr/config.toml,
# and a second (idempotent) run must succeed without losing any of that
# state.
#
# Reproduces the reported bug: install.sh invoked
#   herdr plugin install --ref "$ref" --yes "$repo"
# but herdr's CLI requires the positional <owner>/<repo> before its options;
# given options first it exits 2 with a usage error. Under `set -eu` that
# aborted the whole install after the very first plugin, so a fresh
# ("beta") machine ended up with zero/one plugin instead of all four.
#
# Uses tests/fixtures/herdr in place of the real herdr binary so this
# runs offline and deterministically.
set -eu

script_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
repo_root=$(CDPATH= cd -- "$script_dir/.." && pwd -P)

work=$(mktemp -d "${TMPDIR:-/tmp}/dotfiles-install-test.XXXXXX")
trap 'rm -rf -- "$work"' EXIT

export HOME="$work/home"
export XDG_CONFIG_HOME="$work/home/.config"
export HERDR_STUB_LOG="$work/installed.log"
mkdir -p -- "$HOME"
: >"$HERDR_STUB_LOG"

export PATH="$repo_root/tests/fixtures:$PATH"

expected_repos="plannotator/herdr-annotate
jeffarese/herdr-bar
persiyanov/herdr-reviewr
senna-lang/herdr-agent-usage"
want_repos=$(printf '%s\n' "$expected_repos" | sort)

config_dest="$XDG_CONFIG_HOME/herdr/config.toml"
usagebar_config_dest="$XDG_CONFIG_HOME/herdr/plugins/config/usagebar/config.toml"

fail=0

# Asserts the full set of expected plugin/keymap state is present. Call
# after each install.sh run so a rerun can't silently drop state.
check_state() {
    label=$1

    installed_repos=$(cut -d' ' -f1 -- "$HERDR_STUB_LOG" 2>/dev/null | sort -u)
    if [ "$installed_repos" != "$want_repos" ]; then
        echo "FAIL ($label): expected all 4 pinned plugins installed, got:" >&2
        printf '%s\n' "$installed_repos" >&2
        fail=1
    fi

    if [ ! -f "$config_dest" ]; then
        echo "FAIL ($label): config.toml was not applied to $config_dest" >&2
        fail=1
    else
        for cmd in herdr-bar.open usagebar.open-limits usagebar.refresh \
            annotate.capture annotate.copy-context annotate.copy-archive \
            annotate.manage annotate.open annotate.last \
            persiyanov.reviewr.toggle; do
            if ! grep -q "\"$cmd\"" -- "$config_dest"; then
                echo "FAIL ($label): keymap command $cmd missing from installed config.toml" >&2
                fail=1
            fi
        done
    fi

    if [ ! -f "$usagebar_config_dest" ]; then
        echo "FAIL ($label): usagebar plugin config.toml was not applied to $usagebar_config_dest" >&2
        fail=1
    fi
}

if ! sh "$repo_root/install.sh" >"$work/install1.out" 2>&1; then
    echo "FAIL: install.sh exited non-zero on a clean home" >&2
    cat -- "$work/install1.out" >&2
    fail=1
fi
check_state "first run"

if ! sh "$repo_root/install.sh" >"$work/install2.out" 2>&1; then
    echo "FAIL: rerunning install.sh on an already-provisioned home exited non-zero" >&2
    cat -- "$work/install2.out" >&2
    fail=1
fi
check_state "second run"

if [ "$fail" -ne 0 ]; then
    echo "--- first run output ---" >&2
    cat -- "$work/install1.out" >&2
    echo "--- second run output ---" >&2
    cat -- "$work/install2.out" >&2
else
    echo "PASS: all 4 pinned plugins and all keymaps installed, and survive a second (idempotent) run"
fi

exit "$fail"

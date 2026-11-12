#!/usr/bin/env bash
# core-profile.sh - the fm-core profile (Herdr app / herdr-core, backend hc)
# installed and launched beside the classic fm profile on one synthetic HOME:
# separate operational home, env file, FirstMate checkout (and so the Captain
# working directory that Pi and OMP group sessions by) and launcher name;
# neither profile's install, verify, update or launch reaches the other's
# state, and classic environment inherited by a shell never retargets core.
# Uses only the shared fixture's inert stubs; no hc, Herdr, harness or model.
# shellcheck source=firstmate-config/tests/fixture.sh
. "$(dirname "${BASH_SOURCE[0]}")/fixture.sh"

CORE_HOME="$HOME/.firstmate-core"
CORE_ROOT="$HOME/Developer/tools/firstmate-core"
CORE_ENV="$HOME/.config/firstmate-config/core.env"
CLASSIC_ENV="$HOME/.config/firstmate-config/env"

target() { (cd "$(dirname "$1")" && cd -P "$(dirname "$(readlink "$1")")" && printf '%s/%s\n' "$(pwd -P)" "$(basename "$(readlink "$1")")"); }
present() { if [ -e "$1" ] || [ -L "$1" ]; then printf present; else printf absent; fi; }
# Content snapshot of a tree: every directory, file checksum and link text.
snap() {
  local p
  for p in "$@"; do
    [ -e "$p" ] || [ -L "$p" ] || { printf 'absent %s\n' "$p"; continue; }
    find "$p" \( -type l -exec sh -c 'printf "%s -> %s\n" "$1" "$(readlink "$1")"' _ {} \; \) \
      -o \( -type f -exec cksum {} \; \) -o -type d -print
  done | LC_ALL=C sort
}
classic_state() { snap "$FMHOME" "$CLASSIC_ENV" "$OFFICIAL/.git/HEAD" "$HOME/.local/bin/fm"; }
shared_stores() { snap "$HOME/.agents" "$HOME/.omp/agent/agents" "$HOME/.pi/agent/prompts" "$SKILL_CACHE"; }

# --- classic first, then core beside it -------------------------------------------
install_world || { cat "$T/install.out" >&2; bad 'classic fixture install'; finish; }
classic_before=$(classic_state)
shared_before=$(shared_stores)

# A shell that inherited a classic Captain's environment must not retarget core.
out=$(FM_HOME="$FMHOME" FIRSTMATE_ROOT="$OFFICIAL" FM_BACKEND=herdr FM_CONFIG_ENV="$CLASSIC_ENV" \
  "$FMC/install.sh" --core 2>&1); status=$?
check 'core install succeeds beside classic' "$status" 0
has 'core install reports no failure' "$out" 'install: '
check 'core FirstMate is a separate clone of the manifest origin' "$(git -C "$CORE_ROOT" remote get-url origin 2>&1)" "$OFFICIAL_REMOTE"
check 'core checkout is on main tracking origin/main' "$(git -C "$CORE_ROOT" rev-parse --abbrev-ref '@{upstream}' 2>&1)" origin/main
check 'core env file is written' "$(present "$CORE_ENV")" present
core_env=$(cat "$CORE_ENV" 2>/dev/null)
has 'core env selects the core home' "$core_env" "FM_HOME=\"$CORE_HOME\""
has 'core env selects the core checkout' "$core_env" "FIRSTMATE_ROOT=\"$CORE_ROOT\""
has 'core env selects hc' "$core_env" 'FM_BACKEND="hc"'
has 'core env shares this config root' "$core_env" "FM_CONFIG_ROOT=\"$FMC\""
check 'core runtime backend is hc' "$(cat "$CORE_HOME/config/backend" 2>&1)" hc
check 'core routing profile links into dotfiles' "$(target "$CORE_HOME/config/crew-dispatch.json")" "$FMC/firstmate/crew-dispatch.json"
check 'core captain file is seeded from the same template' "$(cat "$CORE_HOME/data/captain.md" 2>&1)" "$(cat "$FMC/firstmate/captain.md")"
for dir in state data config projects; do
  check "core home has $dir/" "$([ -d "$CORE_HOME/$dir" ] && printf yes)" yes
done
check 'fm-core launcher links into dotfiles' "$(target "$HOME/.local/bin/fm-core")" "$FMC/bin/fm-core"
check 'core install leaves every classic file, link and record alone' "$(classic_state)" "$classic_before"
check 'core install leaves shared skills, commands, role agents and the pack cache alone' "$(shared_stores)" "$shared_before"
check 'core install never drives herdr' "$(cat "$HERDR_LOG" 2>/dev/null)" ''

# --- repeat and cross-profile verify -----------------------------------------------
check 'second core install changes nothing' "$("$FMC/install.sh" --core 2>&1 | tail -1)" 'install: 0 change(s), 0 failure(s)'
check 'core verify reports no drift' "$("$FMC/install.sh" --core --verify 2>&1 | tail -1)" 'verify: 0 drift item(s), 0 failure(s)'
check 'flag order does not matter' "$("$FMC/install.sh" --verify --core 2>&1 | tail -1)" 'verify: 0 drift item(s), 0 failure(s)'
core_before=$(snap "$CORE_HOME" "$CORE_ENV" "$HOME/.local/bin/fm-core")
check 'classic verify sees no drift with core installed' "$("$FMC/install.sh" --verify 2>&1 | tail -1)" 'verify: 0 drift item(s), 0 failure(s)'
check 'classic reconcile changes nothing with core installed' "$("$FMC/install.sh" 2>&1 | tail -1)" 'install: 0 change(s), 0 failure(s)'
check 'classic reconcile leaves core alone' "$(snap "$CORE_HOME" "$CORE_ENV" "$HOME/.local/bin/fm-core")" "$core_before"

# --- launch: both entries, from a project, with classic environment inherited ------
project="$T/some-project"
git init -q "$project"
(cd "$project" && FM_HOME="$FMHOME" FIRSTMATE_ROOT="$OFFICIAL" FM_BACKEND=herdr FM_CONFIG_ENV="$CLASSIC_ENV" \
  "$HOME/.local/bin/fm-core" > "$T/core-launch.out" 2>&1); status=$?
check 'fm-core launches' "$status" 0
log=$(cat "$HARNESS_LOG")
has 'core Captain gets the core home' "$log" "FM_HOME=$CORE_HOME"
has 'core Captain workers use hc' "$log" 'FM_BACKEND=hc'
has 'core Captain runs in the core checkout' "$log" "cwd=$(cd "$CORE_ROOT" && pwd -P)"
has 'core Captain shares the config root' "$log" "FM_CONFIG_ROOT=$FMC"
has 'core Captain keeps the default harness and model chain' "$log" 'args=--model openai-codex/gpt-6.1-sol --thinking medium'
has 'core launch directory is a hint' "$log" "FM_FORK_ORIGIN_CWD=$project"
has 'core launch is recorded in the core home' "$(cat "$CORE_HOME/state/.fm-launch" 2>&1)" 'fm_backend=hc'
check 'core launch writes no classic launch record' "$(present "$FMHOME/state/.fm-launch")" absent

(cd "$project" && FM_HOME="$CORE_HOME" FIRSTMATE_ROOT="$CORE_ROOT" FM_BACKEND=hc \
  "$HOME/.local/bin/fm" > /dev/null 2>&1)
log=$(cat "$HARNESS_LOG")
# The classic launch above wrote its own launch record; every later check
# compares classic state against this point.
classic_before=$(classic_state)
has 'classic fm still gets the classic home' "$log" "FM_HOME=$FMHOME"
has 'classic fm still uses herdr' "$log" 'FM_BACKEND=herdr'
has 'classic fm still runs in the classic checkout' "$log" "cwd=$(cd "$OFFICIAL" && pwd -P)"

(cd "$T" && "$HOME/.local/bin/fm-core" --harness omp > /dev/null 2>&1)
log=$(cat "$HARNESS_LOG")
has 'fm-core honors --harness omp' "$log" 'bin=omp'
has 'core OMP Captain runs in the core checkout' "$log" "cwd=$(cd "$CORE_ROOT" && pwd -P)"
has 'core OMP Captain uses hc' "$log" 'FM_BACKEND=hc'

out=$("$HOME/.local/bin/fm-core" --check 2>&1)
has 'fm-core --check resolves the core home' "$out" "FM_HOME=$CORE_HOME"
has 'fm-core --check resolves hc' "$out" 'FM_BACKEND=hc'

mv "$CORE_ENV" "$T/core.env.saved"
out=$(FM_HOME="$FMHOME" FIRSTMATE_ROOT="$OFFICIAL" FM_CONFIG_ENV="$CLASSIC_ENV" "$HOME/.local/bin/fm-core" --check 2>&1)
has 'without its env file fm-core still resolves the core home' "$out" "FM_HOME=$CORE_HOME"
has 'without its env file fm-core still resolves the core checkout' "$out" "FIRSTMATE_ROOT=$CORE_ROOT"
has 'without its env file fm-core still resolves hc' "$out" 'FM_BACKEND=hc'
mv "$T/core.env.saved" "$CORE_ENV"

# --- classic operational-path overrides never reach core -------------------------
# FirstMate resolves its code root (extensions, home tag), state, data, config,
# projects, pending replies and per-task records through these before FM_HOME.
# Sentinels in the classic home stand for its records.
OVERRIDES='FM_ROOT_OVERRIDE FM_STATE_OVERRIDE FM_DATA_OVERRIDE FM_PROJECTS_OVERRIDE FM_CONFIG_OVERRIDE FM_PENDING_REPLY_DIR_OVERRIDE FM_CREW_STATE_META_OVERRIDE FM_CREW_STATE_STATUS_OVERRIDE'
mkdir -p "$FMHOME/state/pending-replies"
printf 'classic sentinel meta\n' > "$FMHOME/state/sentinel-task.meta"
printf 'classic sentinel status\n' > "$FMHOME/state/sentinel-task.status"
printf 'classic sentinel reply\n' > "$FMHOME/state/pending-replies/sentinel"
printf 'classic sentinel registry\n' > "$FMHOME/data/projects.md"
printf 'classic sentinel config\n' > "$FMHOME/config/sentinel.conf"
classic_before=$(classic_state)
with_classic_overrides() {
  env FM_ROOT_OVERRIDE="$OFFICIAL" FM_STATE_OVERRIDE="$FMHOME/state" FM_DATA_OVERRIDE="$FMHOME/data" \
    FM_PROJECTS_OVERRIDE="$FMHOME/projects" FM_CONFIG_OVERRIDE="$FMHOME/config" \
    FM_PENDING_REPLY_DIR_OVERRIDE="$FMHOME/state/pending-replies" \
    FM_CREW_STATE_META_OVERRIDE="$FMHOME/state/sentinel-task.meta" \
    FM_CREW_STATE_STATUS_OVERRIDE="$FMHOME/state/sentinel-task.status" "$@"
}
for harness in pi omp; do
  (cd "$project" && with_classic_overrides "$HOME/.local/bin/fm-core" --harness "$harness" > /dev/null 2>&1); status=$?
  check "$harness fm-core launches under inherited classic path overrides" "$status" 0
  log=$(cat "$HARNESS_LOG")
  has "$harness core Captain still gets the core home" "$log" "FM_HOME=$CORE_HOME"
  for v in $OVERRIDES; do
    has "$harness core Captain does not inherit $v" "$log" "$v=unset"
  done
done
(with_classic_overrides "$FMC/install.sh" --core > /dev/null 2>&1)
check 'core launch and install under classic overrides leave classic records alone' "$(classic_state)" "$classic_before"
check 'no classic record reaches the core home' "$(grep -rl 'classic sentinel' "$CORE_HOME" 2>/dev/null)" ''
(cd "$project" && with_classic_overrides "$HOME/.local/bin/fm" > /dev/null 2>&1)
log=$(cat "$HARNESS_LOG")
has 'classic fm still passes its overrides through' "$log" "FM_STATE_OVERRIDE=$FMHOME/state"
has 'classic fm still passes the root override through' "$log" "FM_ROOT_OVERRIDE=$OFFICIAL"
classic_before=$(classic_state)

# --- drift and repair stay inside the core profile -----------------------------------
printf 'FM_BACKEND="herdr"\n' >> "$CORE_ENV"
rm "$HOME/.local/bin/fm-core"
out=$("$FMC/install.sh" --core --verify 2>&1)
has 'core verify reports the edited env file' "$out" "write $CORE_ENV"
has 'core verify reports the missing launcher' "$out" "link $HOME/.local/bin/fm-core -> $FMC/bin/fm-core"
check 'core verify creates no launcher' "$(present "$HOME/.local/bin/fm-core")" absent
check 'classic verify ignores core drift' "$("$FMC/install.sh" --verify 2>&1 | tail -1)" 'verify: 0 drift item(s), 0 failure(s)'
"$FMC/install.sh" --core > /dev/null 2>&1
check 'core reconcile repairs the env file' "$(grep -c '^FM_BACKEND="hc"$' "$CORE_ENV")/$(grep -c '^FM_BACKEND=' "$CORE_ENV")" 1/1
check 'core reconcile restores the launcher' "$(target "$HOME/.local/bin/fm-core")" "$FMC/bin/fm-core"
check 'core repair leaves classic alone' "$(classic_state)" "$classic_before"

# --- machine-owned and foreign entries are never rewritten ---------------------------
printf 'core preferences\n' > "$CORE_HOME/data/captain.md"
"$FMC/install.sh" --core > /dev/null 2>&1
check 'existing core captain file is never overwritten' "$(cat "$CORE_HOME/data/captain.md")" 'core preferences'

rm "$HOME/.local/bin/fm-core"
printf 'my own fm-core\n' > "$HOME/.local/bin/fm-core"
out=$("$FMC/install.sh" --core 2>&1); status=$?
check 'a user-owned fm-core file does not fail the core install' "$status" 0
has 'core install reports the user-owned fm-core file' "$out" "$HOME/.local/bin/fm-core exists and is not one of ours"
check 'a user-owned fm-core file is never overwritten' "$(cat "$HOME/.local/bin/fm-core")" 'my own fm-core'

rm "$HOME/.local/bin/fm-core"
ln -s "$T/old-config/bin/fm-core" "$HOME/.local/bin/fm-core"
out=$("$FMC/install.sh" --core 2>&1); status=$?
check 'core install fails on a foreign fm-core link' "$status" 1
has 'core install names the foreign fm-core link' "$out" "$HOME/.local/bin/fm-core points at $T/old-config/bin/fm-core"
check 'foreign fm-core link is left untouched' "$(readlink "$HOME/.local/bin/fm-core")" "$T/old-config/bin/fm-core"
rm "$HOME/.local/bin/fm-core"

# A second checkout of the same dotfiles (moved or duplicated) never takes over
# links the first one installed.
git clone -q "$DOTFILES_REMOTE" "$T/relocated"
"$FMC/install.sh" --core > /dev/null 2>&1
out=$("$T/relocated/firstmate-config/install.sh" --core 2>&1); status=$?
check 'a relocated checkout does not take over the core install' "$status" 1
has 'relocated core install names the existing launcher' "$out" "$HOME/.local/bin/fm-core points at"
check 'existing fm-core link still reaches the first checkout' "$(target "$HOME/.local/bin/fm-core")" "$FMC/bin/fm-core"
check 'relocated core install leaves classic alone' "$(classic_state)" "$classic_before"
"$FMC/install.sh" --core > /dev/null 2>&1

# --- update: fm-core moves only the core checkout; fm moves only classic --------
push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v2'
push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
dotfiles_before=$(git -C "$DOTFILES" rev-parse HEAD)
classic_root_before=$(git -C "$OFFICIAL" rev-parse HEAD)
shared_before=$(shared_stores)
(cd "$T" && FM_HOME="$FMHOME" FIRSTMATE_ROOT="$OFFICIAL" FM_CONFIG_ENV="$CLASSIC_ENV" \
  "$HOME/.local/bin/fm-core" update > "$T/core-update.out" 2>&1); status=$?
out=$(cat "$T/core-update.out")
check 'fm-core update succeeds' "$status" 0
check 'fm-core update fast-forwards the core checkout' "$(git -C "$CORE_ROOT" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
check 'fm-core update never moves the classic checkout' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$classic_root_before"
check 'fm-core update never moves the shared dotfiles checkout' "$(git -C "$DOTFILES" rev-parse HEAD)" "$dotfiles_before"
has 'fm-core update verifies the core profile' "$out" 'verify: 0 drift item(s), 0 failure(s)'
has 'fm-core update reports completion' "$out" 'fm-core update complete'
check 'fm-core update leaves classic alone' "$(classic_state)" "$classic_before"
check 'fm-core update leaves shared stores alone' "$(shared_stores)" "$shared_before"

push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v3'
core_root_before=$(git -C "$CORE_ROOT" rev-parse HEAD)
core_before=$(snap "$CORE_HOME" "$CORE_ENV" "$HOME/.local/bin/fm-core")
(cd "$T" && FM_HOME="$CORE_HOME" FIRSTMATE_ROOT="$CORE_ROOT" FM_BACKEND=hc \
  "$HOME/.local/bin/fm" update > "$T/classic-update.out" 2>&1); status=$?
check 'classic fm update still succeeds' "$status" 0
check 'classic fm update fast-forwards the classic checkout' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
check 'classic fm update still fast-forwards dotfiles' "$(git -C "$DOTFILES" rev-parse HEAD)" "$(remote_tip "$DOTFILES_REMOTE")"
check 'classic fm update never moves the core checkout' "$(git -C "$CORE_ROOT" rev-parse HEAD)" "$core_root_before"
check 'classic fm update leaves core alone' "$(snap "$CORE_HOME" "$CORE_ENV" "$HOME/.local/bin/fm-core")" "$core_before"

# Without core.env, an inherited classic FIRSTMATE_ROOT is still never the target.
push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v4'
classic_root_before=$(git -C "$OFFICIAL" rev-parse HEAD)
mv "$CORE_ENV" "$T/core.env.saved2"
(cd "$T" && FIRSTMATE_ROOT="$OFFICIAL" FM_HOME="$FMHOME" FM_CONFIG_ENV="$CLASSIC_ENV" \
  "$HOME/.local/bin/fm-core" update > "$T/core-update-noenv.out" 2>&1); status=$?
check 'fm-core update without core.env succeeds' "$status" 0
check 'fm-core update without core.env fast-forwards the core checkout' "$(git -C "$CORE_ROOT" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
check 'fm-core update without core.env never moves an inherited classic checkout' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$classic_root_before"
has 'fm-core update without core.env rewrites the core env file' "$(cat "$CORE_ENV" 2>&1)" "FIRSTMATE_ROOT=\"$CORE_ROOT\""
check 'fm-core update without core.env leaves classic alone' "$(classic_state)" "$classic_before"

# The same guard in fm-update itself, which `fm-core update` reaches only after
# the launcher already dropped the inherited value.
push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v5'
classic_root_before=$(git -C "$OFFICIAL" rev-parse HEAD)
mv "$CORE_ENV" "$T/core.env.saved3"
(cd "$T" && FIRSTMATE_ROOT="$OFFICIAL" FM_HOME="$FMHOME" FM_CONFIG_ENV="$CLASSIC_ENV" \
  "$FMC/bin/fm-update" --core > "$T/core-update-direct.out" 2>&1); status=$?
check 'fm-update --core without core.env succeeds' "$status" 0
check 'fm-update --core without core.env fast-forwards the core checkout' "$(git -C "$CORE_ROOT" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
check 'fm-update --core without core.env never moves an inherited classic checkout' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$classic_root_before"

# --- shared user stores stay the classic install's business ---------------------
# As on a machine whose classic links still come from another checkout, or where
# one was removed: core neither fails on nor repairs either.
rm "$HOME/.agents/skills/architecture-review" "$HOME/.agents/commands/tlw.md"
ln -s "$T/old-config/skills/architecture-review" "$HOME/.agents/skills/architecture-review"
shared_before=$(shared_stores)
out=$("$FMC/install.sh" --core 2>&1); status=$?
check 'core install does not fail on a shared link owned elsewhere' "$status" 0
check 'core install neither repairs nor replaces shared stores' "$(shared_stores)" "$shared_before"
check 'core verify does not report shared-store drift' "$("$FMC/install.sh" --core --verify 2>&1 | tail -1)" 'verify: 0 drift item(s), 0 failure(s)'

finish

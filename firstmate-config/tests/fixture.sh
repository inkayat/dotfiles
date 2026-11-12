# shellcheck shell=bash
# Shared synthetic fixture for the firstmate-config tests. Sourced, never run.
#
# Everything lives under one mktemp directory removed on exit: a scrubbed HOME,
# TMPDIR and Git config, private bare remotes standing in for official
# FirstMate, a pinned external skill pack and this dotfiles repository, and
# inert `pi`, `omp` and `herdr` stubs that only answer the launcher's
# availability probes and record how they were called. No network, real
# harness, real home or real Herdr is reached.
set -u

FIX_SRC=$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd -P)
T=$(mktemp -d "${TMPDIR:-/tmp}/fmc-test.XXXXXX") || exit 1
T=$(cd "$T" && pwd -P)
trap 'rm -rf -- "$T"' EXIT

export HOME="$T/home" TMPDIR="$T/tmp" XDG_CONFIG_HOME="$T/home/.config"
unset XDG_DATA_HOME FIRSTMATE_ROOT FIRSTMATE_ORIGIN FM_HOME FM_BACKEND FM_CONFIG_ENV FM_CONFIG_ROOT \
  FM_SKILLS_ROOT FM_COMMANDS_ROOT FM_PI_PROMPTS_ROOT PI_CODING_AGENT_DIR FM_OMP_AGENTS_ROOT \
  FM_SKILL_CACHE FM_BIN_DIR FM_PI_BIN FM_OMP_BIN FM_PI_EXTENSIONS FM_FORK_ORIGIN_CWD FM_FORK_ORIGIN_IS_PROJECT \
  FM_ROOT_OVERRIDE FM_STATE_OVERRIDE FM_DATA_OVERRIDE FM_PROJECTS_OVERRIDE FM_CONFIG_OVERRIDE \
  FM_PENDING_REPLY_DIR_OVERRIDE FM_CREW_STATE_META_OVERRIDE FM_CREW_STATE_STATUS_OVERRIDE
export GIT_CONFIG_NOSYSTEM=1 GIT_CONFIG_GLOBAL=/dev/null GIT_TERMINAL_PROMPT=0
export GIT_AUTHOR_NAME=Fixture GIT_AUTHOR_EMAIL=fixture@example.invalid
export GIT_COMMITTER_NAME=Fixture GIT_COMMITTER_EMAIL=fixture@example.invalid
export HARNESS_LOG="$T/harness.log" HERDR_LOG="$T/herdr.log"
mkdir -p "$HOME" "$TMPDIR" "$T/stubs" "$T/remotes"

# Availability probes answer as an authenticated catalog would; any other call
# is a Captain launch and is recorded instead of started.
cat > "$T/stubs/pi" <<'SH'
#!/usr/bin/env bash
case ${1:-} in
  --list-models) printf 'openai-codex gpt-6.1-sol 400K 128K yes yes\n'; exit 0 ;;
  auth) printf '{"status":"ready"}\n'; exit 0 ;;
  list) exit 0 ;;
esac
{
  printf 'bin=pi\ncwd=%s\nargs=%s\n' "$(pwd -P)" "$*"
  for v in FM_HOME FM_BACKEND FM_CONFIG_ROOT FM_FORK_ORIGIN_CWD FM_FORK_ORIGIN_IS_PROJECT CLAUDECODE FM_OMP_HARNESS \
    FM_ROOT_OVERRIDE FM_STATE_OVERRIDE FM_DATA_OVERRIDE FM_PROJECTS_OVERRIDE FM_CONFIG_OVERRIDE \
    FM_PENDING_REPLY_DIR_OVERRIDE FM_CREW_STATE_META_OVERRIDE FM_CREW_STATE_STATUS_OVERRIDE; do
    printf '%s=%s\n' "$v" "${!v-unset}"
  done
} > "$HARNESS_LOG"
SH
cat > "$T/stubs/omp" <<'SH'
#!/usr/bin/env bash
if [ "${1:-}" = models ]; then
  printf '{"models":[{"provider":"openai-codex","id":"gpt-6.1-sol","thinking":["low","medium","high"]}]}\n'
  exit 0
fi
{
  printf 'bin=omp\ncwd=%s\nargs=%s\n' "$(pwd -P)" "$*"
  for v in FM_HOME FM_BACKEND FM_CONFIG_ROOT FM_FORK_ORIGIN_CWD FM_FORK_ORIGIN_IS_PROJECT CLAUDECODE FM_OMP_HARNESS \
    FM_ROOT_OVERRIDE FM_STATE_OVERRIDE FM_DATA_OVERRIDE FM_PROJECTS_OVERRIDE FM_CONFIG_OVERRIDE \
    FM_PENDING_REPLY_DIR_OVERRIDE FM_CREW_STATE_META_OVERRIDE FM_CREW_STATE_STATUS_OVERRIDE; do
    printf '%s=%s\n' "$v" "${!v-unset}"
  done
} > "$HARNESS_LOG"
SH
printf '#!/bin/sh\nprintf "%%s\\n" "$*" >> "$HERDR_LOG"\n' > "$T/stubs/herdr"
chmod +x "$T/stubs/"*
export PATH="$T/stubs:$PATH"

FAILED=0
ok() { printf 'ok   - %s\n' "$1"; }
bad() { printf 'FAIL - %s\n' "$1" >&2; FAILED=1; }
check() { if [ "$2" = "$3" ]; then ok "$1"; else bad "$1 (expected '$3', got '$2')"; fi; }
has() { case $2 in *"$3"*) ok "$1" ;; *) bad "$1 (missing '$3' in: $2)" ;; esac; }
lacks() { case $2 in *"$3"*) bad "$1 (unexpected '$3' in: $2)" ;; *) ok "$1" ;; esac; }
finish() { [ "$FAILED" -eq 0 ] && printf 'PASS\n'; exit "$FAILED"; }

OFFICIAL_REMOTE="$T/remotes/official.git"
PACK_REMOTE="$T/remotes/agent-skills.git"
DOTFILES_REMOTE="$T/remotes/dotfiles.git"
DOTFILES="$T/dotfiles"
FMC="$DOTFILES/firstmate-config"
OFFICIAL="$HOME/Developer/tools/firstmate"
FMHOME="$HOME/.firstmate"
SKILL_CACHE="$HOME/.local/share/firstmate-config/skills-src"

seed_remote() { # <bare> <seed dir with files>
  git init -q -b main "$2"
  git -C "$2" add -A
  git -C "$2" commit -qm seed
  git init -q --bare -b main "$1"
  git -C "$2" push -q "$1" main
}

push_change() { # <bare> <file> <content>: land a new upstream commit
  local w="$T/push.$RANDOM"
  git clone -q "$1" "$w"
  mkdir -p "$(dirname "$w/$2")"
  printf '%s\n' "$3" > "$w/$2"
  git -C "$w" add -A
  git -C "$w" commit -qm "change $2"
  git -C "$w" push -q origin main
  rm -rf -- "$w"
}

remote_tip() { git -C "$1" rev-parse refs/heads/main; }

# Official FirstMate with the four primary extensions the launcher requires;
# an external skill pack shaped like addyosmani/agent-skills, whose skill
# reads an ancestor-relative reference; and this dotfiles repository with its
# manifest and lock pointed at those private remotes. The pack is pre-cloned
# at its pin, as an earlier install would leave it, so no network is needed.
make_world() {
  local s="$T/seed-official" p="$T/seed-pack" d="$T/seed-dotfiles" official_sha pack_sha
  mkdir -p "$s/.pi/extensions" "$s/.omp/extensions" "$p/skills/demo-method" "$p/references" "$d"
  printf 'official firstmate\n' > "$s/AGENTS.md"
  for f in .pi/extensions/fm-primary-pi-watch.ts .pi/extensions/fm-primary-turnend-guard.ts \
    .omp/extensions/fm-primary-omp-watch.ts .omp/extensions/fm-primary-turnend-guard.ts; do
    printf '// fixture\n' > "$s/$f"
  done
  seed_remote "$OFFICIAL_REMOTE" "$s"
  official_sha=$(remote_tip "$OFFICIAL_REMOTE")

  printf -- '---\nname: demo-method\ndescription: fixture\n---\nRead ../../references/checklist.md\n' \
    > "$p/skills/demo-method/SKILL.md"
  printf 'checklist\n' > "$p/references/checklist.md"
  seed_remote "$PACK_REMOTE" "$p"
  pack_sha=$(remote_tip "$PACK_REMOTE")
  git clone -q "$PACK_REMOTE" "$SKILL_CACHE/addyosmani-agent-skills"
  git -C "$SKILL_CACHE/addyosmani-agent-skills" checkout -q "$pack_sha"

  (cd "$FIX_SRC" && tar cf - --exclude ./.git --exclude ./firstmate-config/tests .) | (cd "$d" && tar xf -)
  awk -F '\t' -v OFS='\t' -v url="$OFFICIAL_REMOTE" -v sha="$official_sha" '
    $1 == "firstmate_repo" { $2 = url } $1 == "firstmate_validated_commit" { $2 = sha } { print }' \
    "$FIX_SRC/firstmate-config/firstmate/stack-manifest.tsv" > "$d/firstmate-config/firstmate/stack-manifest.tsv"
  printf 'fixture:demo\taddyosmani/agent-skills\t%s\tskills/demo-method\tdemo-method\n' "$pack_sha" \
    > "$d/firstmate-config/skills/external.lock"
  seed_remote "$DOTFILES_REMOTE" "$d"
  git clone -q "$DOTFILES_REMOTE" "$DOTFILES"
}

install_world() { make_world && "$FMC/install.sh" > "$T/install.out" 2>&1; }

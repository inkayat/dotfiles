#!/usr/bin/env bash
# update.sh - `fm update` against private local remotes: official FirstMate is
# fast-forwarded before dotfiles, the pulled config is reconciled, unsafe
# states are refused before anything moves, and a late failure is reported as
# a partial update. Each scenario runs in its own fresh synthetic world.
set -u

if [ "${1:-}" != --scenario ]; then
  failed=0
  for s in happy dirty_dotfiles dirty_official diverged_dotfiles fork_origin missing_tip unlanded_official partial; do
    printf '# %s\n' "$s"
    bash "${BASH_SOURCE[0]}" --scenario "$s" || failed=1
  done
  [ "$failed" -eq 0 ] && printf 'ALL PASS\n'
  exit "$failed"
fi

# shellcheck source=firstmate-config/tests/fixture.sh
. "$(dirname "${BASH_SOURCE[0]}")/fixture.sh"
install_world || { cat "$T/install.out" >&2; bad 'fixture install'; finish; }

for repo in "$OFFICIAL" "$DOTFILES"; do
  printf '#!/bin/sh\nprintf "%%s\\n" %s >> "%s"\n' "$(basename "$repo")" "$T/order.log" > "$repo/.git/hooks/post-merge"
  chmod +x "$repo/.git/hooks/post-merge"
done
official_before=$(git -C "$OFFICIAL" rev-parse HEAD)
dotfiles_before=$(git -C "$DOTFILES" rev-parse HEAD)
run_update() { (cd "$T" && "$HOME/.local/bin/fm" update > "$T/update.out" 2>&1); }
official_unchanged() { check "$1: official checkout not moved" "$(git -C "$OFFICIAL" rev-parse HEAD)" "$official_before"; }
dotfiles_unchanged() { check "$1: dotfiles checkout not moved" "$(git -C "$DOTFILES" rev-parse HEAD)" "$dotfiles_before"; }

case $2 in
  happy)
    push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v2'
    push_change "$DOTFILES_REMOTE" firstmate-config/roles/new-role/ROLE.md $'---\nname: fm-new-role\ndescription: fixture\n---'
    run_update; status=$?
    check 'update succeeds' "$status" 0
    check 'official is fast-forwarded before dotfiles' "$(tr '\n' ' ' < "$T/order.log")" 'firstmate dotfiles '
    check 'official reaches its remote tip' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
    check 'dotfiles reaches its remote tip' "$(git -C "$DOTFILES" rev-parse HEAD)" "$(remote_tip "$DOTFILES_REMOTE")"
    check 'pulled config is reconciled in the same run' \
      "$(cd "$HOME/.omp/agent/agents" && cd -P "$(dirname "$(readlink fm-new-role.md)")" && pwd -P)" "$FMC/roles/new-role"
    has 'update reports completion' "$(cat "$T/update.out")" 'fm update complete'
    check 'update never drives herdr (no root Herdr installer)' "$(cat "$HERDR_LOG" 2>/dev/null)" ''
    run_update; status=$?
    check 'a repeated update is a clean no-op' "$status" 0
    has 'repeated update reports both up to date' "$(cat "$T/update.out")" 'FirstMate distribution already up to date; dotfiles already up to date'
    ;;
  dirty_dotfiles)
    push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v2'
    printf 'scratch\n' > "$DOTFILES/herdr/untracked-note"
    run_update; status=$?
    check 'dirty dotfiles is refused' "$status" 1
    has 'refusal names the dirty path' "$(cat "$T/update.out")" 'herdr/untracked-note'
    official_unchanged 'dirty dotfiles'
    check 'dirty file is kept' "$(cat "$DOTFILES/herdr/untracked-note")" scratch
    ;;
  dirty_official)
    push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
    printf 'local edit\n' >> "$OFFICIAL/AGENTS.md"
    run_update; status=$?
    check 'dirty official is refused' "$status" 1
    dotfiles_unchanged 'dirty official'
    has 'local official edit is kept' "$(cat "$OFFICIAL/AGENTS.md")" 'local edit'
    ;;
  diverged_dotfiles)
    push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v2'
    push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
    printf 'local\n' > "$DOTFILES/herdr/local-note"
    git -C "$DOTFILES" add -A && git -C "$DOTFILES" commit -qm local
    local_head=$(git -C "$DOTFILES" rev-parse HEAD)
    run_update; status=$?
    check 'diverged dotfiles is refused' "$status" 1
    has 'refusal says diverged' "$(cat "$T/update.out")" 'diverged'
    official_unchanged 'diverged dotfiles'
    check 'local dotfiles commit is kept' "$(git -C "$DOTFILES" rev-parse HEAD)" "$local_head"
    ;;
  fork_origin)
    push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
    git -C "$OFFICIAL" remote set-url origin https://github.com/inkayat/firstmate.git
    run_update; status=$?
    check 'a fork origin is refused' "$status" 1
    has 'refusal names the official origin' "$(cat "$T/update.out")" "expected exactly $OFFICIAL_REMOTE"
    official_unchanged 'fork origin'
    dotfiles_unchanged 'fork origin'
    ;;
  missing_tip)
    push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
    git -C "$OFFICIAL_REMOTE" update-ref -d refs/heads/main
    run_update; status=$?
    check 'a missing official main is refused' "$status" 1
    official_unchanged 'missing tip'
    dotfiles_unchanged 'missing tip'
    ;;
  unlanded_official)
    push_change "$DOTFILES_REMOTE" herdr/note 'upstream'
    printf 'mine\n' > "$OFFICIAL/local-work"
    git -C "$OFFICIAL" add -A && git -C "$OFFICIAL" commit -qm 'unlanded work'
    official_before=$(git -C "$OFFICIAL" rev-parse HEAD)
    run_update; status=$?
    check 'unlanded official work is refused' "$status" 1
    has 'refusal names unlanded work' "$(cat "$T/update.out")" 'unlanded work'
    official_unchanged 'unlanded official'
    dotfiles_unchanged 'unlanded official'
    ;;
  partial)
    push_change "$OFFICIAL_REMOTE" AGENTS.md 'official firstmate v2'
    rm "$HOME/.agents/skills/architecture-review"
    ln -s "$T/elsewhere" "$HOME/.agents/skills/architecture-review"
    run_update; status=$?
    check 'a failed reconcile fails the update' "$status" 1
    has 'failure after the official move is a partial update' "$(cat "$T/update.out")" 'PARTIAL UPDATE'
    check 'official move is kept, not rolled back' "$(git -C "$OFFICIAL" rev-parse HEAD)" "$(remote_tip "$OFFICIAL_REMOTE")"
    check 'foreign skill link is left untouched' "$(readlink "$HOME/.agents/skills/architecture-review")" "$T/elsewhere"
    ;;
esac
finish

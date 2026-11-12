# firstmate-config

A reproducible configuration layer for official
[FirstMate](https://github.com/kunchenguid/firstmate) on its `main` branch:
Captain startup, worker routing, roles, shared skills, and machine-local setup.
It lives in this dotfiles repository and is independent of the root
`install.sh` (Herdr plugins). Project instructions stay project-owned;
credentials and operational state stay outside this repository.

## Install

Use a persistent dotfiles checkout: the installer links live commands and
configuration back to it. **Do not install from a disposable task worktree.**

Have `git`, `pi`, `omp`, and `herdr` on `PATH`; the installer checks them but
does not install them. `jq`, `treehouse`, `gh`, and `bun` are needed for full
fleet behavior. Configure provider authentication in the harness you intend to
use; the installer never stores credentials.

```sh
git clone https://github.com/inkayat/dotfiles.git
dotfiles/firstmate-config/install.sh
```

[`install.sh`](install.sh) creates the operational home, selects Herdr, writes
`~/.config/firstmate-config/env`, links the routing profile, shared skills and
OMP role agents, and installs the `fm` link under `~/.local/bin`. Add that
directory to `PATH`. It never runs the dotfiles root `install.sh`.

If FirstMate is missing, installation clones the manifest's official branch at
the validated commit and tracks that branch. An existing checkout is reported,
never updated or switched by the installer. Re-running installation reconciles
machine state; foreign links are reported as failures and never overwritten.

```sh
dotfiles/firstmate-config/install.sh --verify   # read-only drift report
fm --check                                      # resolve startup without launching
fm
```

`--check` and `--print-command` do not start a Captain, but their preflight can
create missing operational-home directories.

## Daily commands

| Command | Purpose |
| --- | --- |
| `fm` | Start the Pi Captain from any directory, preferring GPT-6.1 Sol medium |
| `fm --harness omp` | Use OMP explicitly; harness fallback is not automatic |
| `fm --model claude` | Choose a model preset for this launch only; also accepts `codex` or `grok` |
| `fm --check` / `fm --print-command` | Inspect startup resolution / the resolved command without launching |
| `fm update` | Fast-forward official FirstMate, then dotfiles, then reconcile and verify this machine |

Startup `--model` and `--harness` flags work in either order; `--model` is not
an `update` option.

## Architecture

```text
fm → Pi Captain (default) or OMP Captain (--harness omp)
   → official FirstMate → Herdr → Pi / OMP workers
```

FirstMate owns task lifecycle, delegation and worktree isolation; Herdr owns
runtime sessions. Captain harness/model selection and worker routing are
independent.

The Captain runs inside the FirstMate distribution checkout, not the launch
directory. It is multi-project: each task resolves its project separately from
an explicit path/name, the FirstMate registry, then the launch directory as a
hint if it is a Git project. Project instructions and skills are not preloaded
as global authority at startup. The exact precedence belongs to
[primary policy §1](firstmate/primary-policy.md#which-project).

### Captain startup model

[`captain-startup-models.tsv`](firstmate/captain-startup-models.tsv) owns the
ordered chain: GPT-6.1 Sol medium, then a harness-specific Sonnet medium fallback.
Rows for a different harness are ignored. Only an authoritative `UNAVAILABLE`
skips a candidate; `UNKNOWN` remains eligible. Launch output explains fallback
decisions.

The Sonnet fallback is `anthropic/claude-sonnet-5-5` on OMP and the unversioned
`pi-claude-code-provider/sonnet` alias on Pi. Claude Code resolves that alias;
it is not a version-pinned Sonnet selector. Its availability uses the provider's
`claude auth status` preflight because Pi's broker does not load extension
providers. OMP probes use `models --json --no-extensions` to avoid writing
FirstMate extension-load markers.

`fm --model codex|claude|grok` selects, respectively,
`openai-codex/gpt-6.1-sol`, `anthropic/claude-sonnet-5-5`, or `xai/grok-4.7`,
all at medium effort. A preset requires `AVAILABLE` for that exact model/effort.
Invalid, unavailable or unverifiable presets warn and use the unchanged default
chain on the same harness. Raw model ids are not accepted; nothing is persisted.
[`fm-captain-lib.sh`](firstmate/fm-captain-lib.sh) is the shared harness and
availability owner.

## Updating

```sh
fm update
```

[`bin/fm-update`](bin/fm-update) checks **both** repositories before changing
either, then fast-forwards the FirstMate checkout's explicit `main` branch,
fast-forwards the dotfiles checkout, and runs `firstmate-config/install.sh` and
`install.sh --verify`. It never runs the dotfiles root `install.sh` or updates
Herdr plugins; run that yourself when Herdr changes.

Both working trees must be clean - for dotfiles, the whole repository, not only
this directory - and fast-forwardable with configured upstreams. FirstMate must
use the manifest's exact official origin
([`stack-manifest.tsv`](firstmate/stack-manifest.tsv)), check out `main`, track
`origin/main`, and set local `origin/HEAD` to that same branch. No unfinished
Git operation or local-only commits are accepted. `fm update --check` verifies
local guards and prints the source, branch, target and pin without fetching,
updating or installing.

Updates never force, stash, reset, rebase, push, or update project/secondmate
checkouts. If the FirstMate checkout moved and a later stage fails, the command
reports `PARTIAL UPDATE`; there is no multi-repository rollback. Fix the stated
error and re-run. Only `fm update complete` means every stage succeeded.

A running Captain is not restarted or notified. Instructions and skills it has
already loaded stay as they are; end that session and run `fm` again to adopt
updates.

External shared skills are pinned by commit in
[`skills/external.lock`](skills/external.lock); `fm update` never moves a pin.
To move one, review the upstream diff, change the sha, and commit.

### Moving a fork installation to official

Installations that followed the retired `https://github.com/inkayat/firstmate.git`
fork keep that origin and its `inkayat-main` branch. `fm update` refuses that
layout before contacting any remote and `install.sh` only warns; neither
converts it. Move it by hand while no Captain or worker uses the checkout.
Every step keeps existing branches, refs and work:

```sh
cd "$FIRSTMATE_ROOT"
git status --porcelain            # must print nothing; preserve any work first
git remote get-url upstream       # must print https://github.com/kunchenguid/firstmate.git
git remote rename origin fork     # inkayat-main and every fork ref stay, now under fork/
git remote rename upstream origin
git fetch origin main
git branch --list main            # if this prints a branch, see below first
git switch -c main --track origin/main
git remote set-head origin main
fm update --check
```

If a local `main` already exists and `git merge-base --is-ancestor main origin/main`
succeeds, use `git switch main`, `git merge --ff-only origin/main` and
`git branch -u origin/main` instead of creating it. Otherwise keep it under
another name first (`git branch -m main pre-official-main`). Stop if any command
fails or prints something unexpected. The fork remote stays until you retire it
deliberately.

### Moving from a standalone firstmate-config checkout

A machine set up from the former standalone `inkayat/firstmate-config`
repository has links into that checkout. `install.sh` from here reports each of
them as a failure and leaves it in place. With no Captain or worker running,
remove only the links it names (`~/.local/bin/fm`,
`$FM_HOME/config/crew-dispatch.json`, `~/.omp/agent/agents/fm-*.md` and the
config-owned `~/.agents/skills/*`), then re-run `install.sh`. The env file is
rewritten to this location. `$FM_HOME/data/captain.md` is never touched; its
`$FM_CONFIG_ROOT/...` pointers resolve here unchanged. Links the old checkout
owned that this configuration no longer provides (`~/.local/bin/ponytail-update`,
`~/.agents/commands/bots.md`, `~/.agents/skills/bot-builder`) are not removed by
anything here.

## Routing

[`crew-dispatch.json`](firstmate/crew-dispatch.json) owns ten semantic categories
and a DEFAULT catch-all. Substantive work prefers Opus 5.5, bounded work may use
Sonnet 5.5, and trivial work uses Haiku/Luna. GPT-6.1 Sol supplies cross-family
routes and implementation alternatives; Astra is reserved for narrow worker
escalations. Explicit Captain choices can override the profile.

Do not maintain a second routing table here: use the full `when`/`why` conditions
in the profile and [primary policy §3](firstmate/primary-policy.md#3-routing).
During the current debugging period, the Captain prints a short
`Routing:` / `Agent:` / `Skills:` block per actual worker/stage.
It is a diagnostic trace, not an enforcement or completion gate; see
[policy §0](firstmate/primary-policy.md#0-routing-agent-and-skill-trace-temporary-debugging-period)
and its checker [`tests/routing-trace.sh`](tests/routing-trace.sh).

## Context and skills

### Worker context and skill classes

Precedence is project-native instructions → project-local skills → role/task
policy → shared worker skills. Each task carries explicit instruction, role and
skill paths resolved against its own worktree, including the role's
`autoloadSkills` defaults; Pi and OMP native discovery alone do not guarantee
the same resolution. Official FirstMate delivers those paths and read-and-apply
requirements, not role or skill bodies: nothing is inlined before the first
model call, a missing path does not refuse the launch, and no selection record
is written.

Keep three populations distinct: official FirstMate internal skills are
Captain-only; this configuration's shared worker skills are installed under
`~/.agents/skills`; project-local skills remain in their project's tracked
skill directories. [Primary policy §2](firstmate/primary-policy.md#2-before-delegating)
owns the handoff, including revisiting context when a new subtree is selected.

### Automatic role selection

[`roles/`](roles/) defines worker contracts and OMP agent definitions;
installation links them as `~/.omp/agent/agents/fm-<role>.md`. The Captain
chooses the narrowest fitting role; coherent mixed work stays with
`senior-fullstack`. Role, skills and route remain separate choices. The
`tenth-man` role is for deliberate adversarial challenge, not routine review.

### Bounded internal delegation

Only FirstMate owns macro orchestration. OMP's native bounded `task` helpers may
work inside the same parent task/project/worktree and authority; the parent
retains verification and completion responsibility. Pi has no bundled equivalent.
[Policy §6](firstmate/primary-policy.md#6-orchestration-boundary) owns this
boundary; [`tests/worker-context.sh`](tests/worker-context.sh) validates fixture
reports against it.

### Completion evidence limits

Context, roles, skill selection and passing fixture reports do not
prove native adoption, read order, application, sandboxing or task completion.
Workers report actual commands, observed outcomes and unverified limits;
browser-visible changes need relevant real-flow evidence.

The selected official FirstMate delivery path owns review, fixes and publication.
This configuration adds no automatic reviewer or trusted completion gate, and no
extra manual reviewer on top of `no-mistakes`. An explicitly requested separate
review is scoped and read-only; no selection grants publication authority.
See [primary policy §7](firstmate/primary-policy.md#7-completion).

## Machine-local state

| Location | Purpose |
| --- | --- |
| `dotfiles/firstmate-config` | Tracked policy, routing, roles, skills and launchers |
| `FIRSTMATE_ROOT` (default `~/Developer/tools/firstmate`) | Official FirstMate distribution checkout |
| `FM_HOME` (default `~/.firstmate`) | Project registry, preferences, task/runtime/session state and local data |
| `~/.config/firstmate-config/env` | Machine-local path resolution |
| `~/.local/share/firstmate-config/skills-src` | Pinned external skill checkouts |

Do not commit credentials, host paths, project knowledge or runtime data here.
Project instructions outrank global defaults.

## Tests

Synthetic only: a throwaway `HOME`, private local Git remotes, and inert
`pi`/`omp`/`herdr` stubs. No network, real harness or real Herdr is used.

```sh
bash firstmate-config/tests/install-launch.sh
bash firstmate-config/tests/update.sh
```

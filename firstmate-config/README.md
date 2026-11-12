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
`~/.config/firstmate-config/env`, links the routing profile, shared skills,
slash commands and OMP role agents, and installs the `fm` link under
`~/.local/bin`. Add that directory to `PATH`. It never runs the dotfiles root
`install.sh`.

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

## Slash commands

[`commands/tlw.md`](commands/tlw.md) is a thin entry for the first-party TLW
skill, typed in an `fm` Captain session on Pi or OMP:

```text
/tlw <task description>
```

It passes the description on as the harness normalizes it, and tells FirstMate to handle it as an ordinary
request: project, authority, assignment and supervision stay FirstMate's, and
whoever carries out the job reads the canonical `first-party/tlw/SKILL.md` from
the `skills` project in the FirstMate registry before anything else. A bare
`/tlw` only asks which job to run. The entry grants no authority, installs
neither TLW nor the skill, and changes no routing; it is not `/skill:tlw`.

`install.sh` links that one file into each harness's own user directory, since
neither reads the other's: OMP `~/.agents/commands` (`FM_COMMANDS_ROOT`) and Pi
`<agent-dir>/prompts` (`PI_CODING_AGENT_DIR`, default `~/.pi/agent`;
`FM_PI_PROMPTS_ROOT`). The usual link rules apply, so a file or foreign link
already there is reported and left alone. There is no separate switch: the entry
is installed by the same `install.sh` as everything else, with the same
prerequisites and migration steps. A running session picks it up after Pi's
`/reload` or a restart of the Captain.

Arguments are normalized by the harness, not forwarded literally. Pi splits them
shell-style (checked: quotes are dropped, line breaks become spaces). OMP
documents a similar quote-aware split, then substitutes the arguments into the
template and renders it through Handlebars, so literal braces in a job description
may be interpreted there (not checked). Name the job on one line, without braces
(repository, issue, lane).

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

## Herdr app / herdr-core profile (`fm-core`)

A second, independent Captain for [Herdr app](https://herdr.dev) and its
herdr-core daemon, beside the classic Herdr `fm`. It runs the same
configuration (policy, routing, roles, skills, model chain, harness choice);
only the instance paths and the worker backend differ. It is experimental:
FirstMate's `hc` backend is, and this profile fixes none of its limits.

```sh
dotfiles/firstmate-config/install.sh --core            # reconcile fm-core only
dotfiles/firstmate-config/install.sh --core --verify   # read-only drift report
fm-core --check
fm-core                                                # also --harness omp, --model
fm-core update
```

| | `fm` | `fm-core` |
| --- | --- | --- |
| Operational home (lock, registry, backlog, state, projects) | `~/.firstmate` | `~/.firstmate-core` |
| Env file | `~/.config/firstmate-config/env` | `~/.config/firstmate-config/core.env` |
| FirstMate checkout = Captain working directory | `~/Developer/tools/firstmate` | `~/Developer/tools/firstmate-core` |
| Worker backend (`FM_BACKEND`, `config/backend`) | `herdr` | `hc`, always |
| Launcher on `PATH` | `fm` | `fm-core` |

`install.sh --core` clones its own official checkout when missing (the same
pinned manifest), creates the core home, seeds its `data/captain.md` from the
same template (never copied from the classic home), links the routing profile
and `fm-core`, and selects `hc`. It needs `herdr-core` (or `hc`, or
`FM_HC_BIN`) instead of the classic `herdr` CLI and only warns when it is
missing; FirstMate checks its version and protocol at each hc spawn. It never
reads `FIRSTMATE_ROOT`, `FM_HOME` or `FM_CONFIG_ENV`, which a shell started
from a classic Captain exports, and `fm-core` sources only `core.env` and
exports `FM_BACKEND=hc` whatever that shell or the terminal it runs in says.
It also drops the operational-path overrides FirstMate resolves before
`FM_HOME` (`FM_ROOT_OVERRIDE`, `FM_STATE_OVERRIDE`, `FM_DATA_OVERRIDE`,
`FM_PROJECTS_OVERRIDE`, `FM_CONFIG_OVERRIDE`, `FM_PENDING_REPLY_DIR_OVERRIDE`,
`FM_CREW_STATE_META_OVERRIDE`, `FM_CREW_STATE_STATUS_OVERRIDE`), so the core
Captain never inherits a pointer into classic records. Neither installer,
verify, update nor launcher touches the other profile's home, env file,
checkout or launcher.

The separate checkout is deliberate. Pi and OMP group sessions by working
directory, so `--continue`, OMP `autoResume` and the session pickers' default
scope stay per profile; FirstMate derives its hc/Herdr home tag from the
checkout path; and `fm-core update` fast-forwards only that checkout. It
never fetches or moves the dotfiles checkout it shares with `fm`: run
`fm update` (or update the checkout yourself), then `fm-core update` to
reconcile core.

Where the `fm-core` Captain's own terminal runs does not choose the worker
backend; `FM_BACKEND=hc` does. Opening a classic `fm` Captain in a Herdr app
terminal still sends its workers to classic Herdr. Workers go to herdr-core's
`default` session, the one Herdr app shows, labelled with this checkout's home
tag; this profile never sets `HC_SESSION`.

Shared, not isolated - a separate home is logical isolation only:

- Accounts, credentials and quotas; the Pi agent directory (`auth.json`,
  `settings.json`, `trust.json`, prompts) and OMP's `~/.omp/agent`
  (config, databases, prompt history).
- `~/.agents/skills`, `~/.agents/commands`, `~/.pi/agent/prompts` and
  `~/.omp/agent/agents`, and the pinned external skill cache: reconciled only by
  `install.sh` without `--core`, used by both Captains and their workers.
- The herdr-core daemon and its `default` session, Treehouse's pool root, the
  `no-mistakes` daemon, `gh`, and every other user-level tool. Concurrency
  there is those tools' business; this profile adds no coordination.
- The dotfiles checkout.

Not supported here, by FirstMate's `hc` backend: `fm-control exit` and
`relaunch`, secondmates, and `/afk` while the Captain runs in a Herdr app
terminal. A new checkout also needs Pi's project trust once. Running tasks never
move between profiles.

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
| `~/.firstmate-core`, `~/.config/firstmate-config/core.env`, `~/Developer/tools/firstmate-core` | The same for `fm-core` ([above](#herdr-app--herdr-core-profile-fm-core)) |

Do not commit credentials, host paths, project knowledge or runtime data here.
Project instructions outrank global defaults.

## Tests

Synthetic only: a throwaway `HOME`, private local Git remotes, and inert
`pi`/`omp`/`herdr` stubs. No network, real harness, Herdr or herdr-core is used.

```sh
bash firstmate-config/tests/install-launch.sh
bash firstmate-config/tests/update.sh
bash firstmate-config/tests/core-profile.sh    # fm-core beside fm
bash firstmate-config/tests/command-entry.sh   # Pi's own loader; skips without the Pi package
```

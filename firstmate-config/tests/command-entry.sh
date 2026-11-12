#!/usr/bin/env bash
# command-entry.sh - the installed /tlw entry as Pi's own prompt-template loader
# and expander see it. The installer places it in a synthetic agent directory;
# the real Pi modules discover and expand it, with no session, model or
# personal configuration involved. OMP ships as a compiled binary with no
# model-free parser to call, so its expansion is not exercised here.
#
# Needs the pi-coding-agent package: set FM_TEST_PI_PACKAGE to its directory,
# or the managed layout next to a `pi` on PATH is tried. Otherwise it skips.
# shellcheck source=firstmate-config/tests/fixture.sh
. "$(dirname "${BASH_SOURCE[0]}")/fixture.sh"

find_pi_package() {
  local real_path=${PATH#"$T/stubs:"} launcher dir version pkg
  if [ -n "${FM_TEST_PI_PACKAGE:-}" ]; then printf '%s\n' "$FM_TEST_PI_PACKAGE"; return; fi
  launcher=$(PATH=$real_path command -v pi) || return 1
  launcher=$(readlink -f "$launcher") || return 1
  dir=$(dirname "$(dirname "$launcher")")
  IFS= read -r version < "$dir/install/current-version" 2>/dev/null || return 1
  pkg="$dir/install/releases/$version/node_modules/@earendil-works/pi-coding-agent"
  [ -d "$pkg" ] && printf '%s\n' "$pkg"
}

PI_PACKAGE=$(find_pi_package) || PI_PACKAGE=''
if [ -z "$PI_PACKAGE" ] || ! command -v node > /dev/null 2>&1; then
  printf 'SKIP - pi-coding-agent package or node not found (set FM_TEST_PI_PACKAGE)\n'
  exit 0
fi

install_world; status=$?
check 'install succeeds' "$status" 0

# Prints the template list, then one JSON-encoded expansion per input argument.
expand() { # <input>...
  node --input-type=module -e '
    const m = await import(process.argv[1] + "/dist/core/prompt-templates.js");
    const r = m.loadPromptTemplates({ cwd: process.argv[2], agentDir: process.argv[3], promptPaths: [], includeDefaults: true });
    console.log(JSON.stringify(r.templates.map((t) => [t.name, Boolean(t.description), t.argumentHint ?? null])));
    console.log(JSON.stringify(r.diagnostics));
    for (const text of process.argv.slice(4)) console.log(JSON.stringify(m.expandPromptTemplate(text, r.templates)));
  ' "$PI_PACKAGE" "$T" "$HOME/.pi/agent" "$@"
}
line() { printf '%s\n' "$2" | sed -n "${1}p"; }
decode() { node -e 'process.stdout.write(JSON.parse(require("fs").readFileSync(0, "utf8")))'; }

NL='
'
out=$(expand '/tlw' '/tlw owner/repo#12 build lane' '/tlw "fix API compat" now' "/tlw line one${NL}line two" '/tlw $1 and $@ stay literal')
check 'Pi discovers the installed entry as /tlw with a description and an argument hint' "$(line 1 "$out")" '[["tlw",true,"<task description>"]]'
check 'Pi loads the installed entry without diagnostics' "$(line 2 "$out")" '[]'
empty=$(line 3 "$out" | decode)
plain=$(line 4 "$out" | decode)
quoted=$(line 5 "$out" | decode)
multi=$(line 6 "$out" | decode)
dollar=$(line 7 "$out" | decode)

has 'the named task reaches the expansion verbatim' "$plain" 'owner/repo#12 build lane'
has 'a quoted phrase keeps its words as one argument' "$quoted" 'fix API compat now'
lacks 'quote characters are consumed by Pi, not forwarded' "$quoted" '"fix'
# Characterization of Pi 1.4.0: whitespace, including newlines, separates arguments
# and $ARGUMENTS rejoins them with single spaces, so line breaks do not survive.
has 'a multiline description arrives with its line break collapsed to a space' "$multi" 'line one line two'
has 'argument text containing dollar patterns is not substituted again' "$dollar" '$1 and $@ stay literal'

for text in "$empty" "$plain"; do
  lacks 'no unresolved placeholder remains' "$text" '$ARGUMENTS'
  has 'the canonical first-party TLW skill is named' "$text" 'first-party/tlw/SKILL.md'
  lacks 'no host-specific absolute path is baked in (macOS)' "$text" '/Users/'
  lacks 'no host-specific absolute path is baked in (Linux)' "$text" '/home/'
done
lacks 'an empty invocation forwards no job text' "$empty" 'owner/repo'

finish

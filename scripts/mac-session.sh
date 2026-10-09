#!/usr/bin/env bash
# The measurements the cloud session could not take, run on the owner's Mac in one go and
# printed as Markdown to paste under decisions 10 and 11 (TASK-2.4, TASK-2.8 step list,
# TASK-3.2 "Owed on the owner's Mac").
#
#   scripts/mac-session.sh [--vault NAME] [--qmd-query TEXT] [--rg-folder DIR] > mac-session.md
#
# It only reads and times, with two exceptions, both in the Obsidian part and both asked
# about first: it appends one line to today's daily note and creates Spike/A.md. Skip
# Obsidian with no --vault. The commands are the vault plugin's guesses (invocations.py),
# so a failure here is a finding, not a bug in this script.
#
# The Dock launch's bare PATH is simulated with `env -i PATH=/usr/bin:/bin`.
set -uo pipefail

vault="" query="meeting" rg_folder=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --vault) vault="$2"; shift 2 ;;
    --qmd-query) query="$2"; shift 2 ;;
    --rg-folder) rg_folder="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

if [[ "$(uname)" != "Darwin" ]]; then
  echo "mac-session.sh measures the Mac; this is $(uname)" >&2
  exit 1
fi

say() { printf '%s\n' "$*"; }
# time_runs N CMD...: seconds for each of N runs, sorted, as "min median p95 max" and the
# distinct exit codes, so a failing command is visible in the numbers.
time_runs() {
  local n="$1"; shift
  local out codes="" i began ended
  out=$(mktemp)
  for ((i = 0; i < n; i++)); do
    began=$(python3 -c 'import time; print(time.monotonic())')
    "$@" >/dev/null 2>&1
    codes+="$? "
    ended=$(python3 -c 'import time; print(time.monotonic())')
    python3 -c "print($ended - $began)" >>"$out"
  done
  sort -n "$out" | python3 -c '
import sys
v = [float(x) for x in sys.stdin]
n = len(v)
print("min %.2f, median %.2f, p95 %.2f, max %.2f" % (v[0], v[n // 2], v[min(n - 1, int(n * 0.95))], v[-1]), end="")'
  printf '; exit codes: %s\n' "$(tr ' ' '\n' <<<"$codes" | sort | uniq -c | awk '{printf "%s with exit %s; ", $1, $2}')"
  rm -f "$out"
}
ask() { local a; read -r -p "$1 [y/N] " a; [[ "$a" == [yY]* ]]; }

say "# Mac session, $(date -u +%Y-%m-%dT%H:%MZ)"
say
say "macOS $(sw_vers -productVersion), $(uname -m)"
say

say "## qmd (decision 11)"
qmd_bin=$(command -v qmd || true)
node_bin=$(command -v node || true)
say "- qmd: \`${qmd_bin:-not found}\`, node: \`${node_bin:-not found}\`"
if [[ -n "$qmd_bin" ]]; then
  say "- version: \`$("$qmd_bin" --version 2>&1 | head -1)\`"
  node_dir=$(dirname "${node_bin:-/usr/bin/node}")
  path_for_qmd="$node_dir:/usr/bin:/bin"
  say "- suggested config: \`bin = \"$qmd_bin\"\`, \`env.PATH = \"$path_for_qmd\"\`"
  say
  say "Warm \`qmd search --json --full-path -n 5 -- $query\`, 20 runs (first discarded):"
  qmd_search() { /usr/bin/env PATH="$path_for_qmd" "$qmd_bin" search --json --full-path -n 5 -- "$query"; }
  qmd_search >/dev/null 2>&1
  say "- with the handoff: $(time_runs 20 qmd_search)"
  bare() { env -i PATH=/usr/bin:/bin "$qmd_bin" search --json -n 5 -- "$query"; }
  say "- bare Dock-like PATH, no handoff: $(time_runs 3 bare)"
  say "- the bare PATH's own message: \`$(bare 2>&1 >/dev/null | head -1)\`"
  say
  say "Cold search: sleep the Mac or wait until the index has left memory, then run:"
  say '    time /usr/bin/env PATH=... qmd search --json --full-path -n 5 -- text'
  say "Record the seconds here: ____ (deadline is 1.0 s)"
  first=$(qmd_search 2>/dev/null | python3 -c 'import json,sys; d=json.load(sys.stdin); print(d[0]["file"] if d else "")' 2>/dev/null)
  if [[ -n "$first" && "$first" == /* ]]; then
    say
    say "First hit: \`$first\`"
    say "- Reveal: run \`open -R '$first'\` and see Finder select it."
    say "- Obsidian URL: \`open \"obsidian://open?path=\$(python3 -c 'import sys,urllib.parse as u; print(u.quote(sys.argv[1], safe=\"/\"))' '$first')\"\`"
  fi
fi
say

if [[ -n "$rg_folder" ]]; then
  say "## ripgrep provider"
  rg_bin=$(command -v rg || true)
  say "- rg: \`${rg_bin:-not found}\`"
  if [[ -n "$rg_bin" ]]; then
    rg_run() { "$rg_bin" -l -0 -i -- "$query" "$rg_folder"; }
    say "- over \`$rg_folder\`: $(time_runs 10 rg_run)"
  fi
  say
fi

if [[ -n "$vault" ]]; then
  say "## Obsidian CLI (decision 10, TASK-2.4)"
  ob=$(command -v obsidian || true)
  say "- \`command -v obsidian\`: \`${ob:-not found}\`"
  [[ -n "$ob" ]] && say "- \`$(ls -l "$ob")\`"
  if [[ -n "$ob" ]]; then
    pgrep -x Obsidian >/dev/null; say "- \`pgrep -x Obsidian\` exit: $? (0 means running)"
    if pgrep -x Obsidian >/dev/null; then
      os() { "$ob" vault="$vault" search query="$query" limit=20; }
      ot() { "$ob" vault="$vault" tasks format=json; }
      say "- warm \`search\`, 20 runs: $(time_runs 20 os)"
      say "- warm \`tasks format=json\`, 20 runs: $(time_runs 20 ot)"
      say "- \`search\` prints: \`$(os 2>&1 | head -3 | tr '\n' '|')\`"
      say "- \`tasks format=json\` first 300 bytes: \`$(ot 2>&1 | head -c 300 | tr '\n' ' ')\`"
      say "- \`read path=Nope.md\`: exit $("$ob" vault="$vault" read path=Nope.md >/dev/null 2>&1; echo $?), says \`$("$ob" vault="$vault" read path=Nope.md 2>&1 | head -1)\`"
      say "- \`daily:read\`: exit $("$ob" vault="$vault" daily:read >/dev/null 2>&1; echo $?)"
      if ask "Write to the vault (append one line to today's daily note, create Spike/A.md)?"; then
        oa() { "$ob" vault="$vault" daily:append content="- [ ] spike from cmd"; }
        say "- 20 warm \`daily:append\`: $(time_runs 20 oa)"
        say "- \`create path=Spike/A.md template=Person\` exit: $("$ob" vault="$vault" create path=Spike/A.md template=Person >/dev/null 2>&1; echo $?); again: $("$ob" vault="$vault" create path=Spike/A.md template=Person 2>&1 | head -1)"
        say "- \`append path=Missing.md content=x\` exit: $("$ob" vault="$vault" append path=Missing.md content=x >/dev/null 2>&1; echo $?)"
      fi
      if ask "Pause Obsidian with SIGSTOP for the hang check (it is resumed after)?"; then
        pid=$(pgrep -x Obsidian | head -1)
        kill -STOP "$pid"
        stopped() { perl -e 'alarm 5; exec @ARGV' "$ob" vault="$vault" daily:read; }
        say "- paused, \`daily:read\` under a 5 s alarm: $(time_runs 1 stopped)"
        kill -CONT "$pid"
      fi
      say
      say "Now quit Obsidian and run this script again with the same --vault for the closed case."
    else
      oc() { "$ob" vault="$vault" daily:read; }
      say "- Obsidian is not running. \`daily:read\`: $(time_runs 1 oc); stderr: \`$(oc 2>&1 >/dev/null | head -1)\`"
      say "- Did it launch Obsidian? \`pgrep -x Obsidian\` now: exit $(pgrep -x Obsidian >/dev/null; echo $?)"
    fi
  fi
  say
fi

say "## By hand"
say "- Launch cmd from the Dock; \`n <text>\` shows hits; Enter opens the note; the 127 row's wording: ____"
say "- Taste calls (status keyword \`search\`, problem rows after hits, no weights, Copy docid only where qmd gives one): ____"

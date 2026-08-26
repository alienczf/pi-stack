#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f overlay/APPEND_SYSTEM.md || fail "missing overlay/APPEND_SYSTEM.md"
test -f overlay/AGENTS.md || fail "missing overlay/AGENTS.md"
test -f overlay/settings.json || fail "missing overlay/settings.json"
test -d prompts || fail "missing prompts/"
test -f prompts/poteto.md || fail "missing prompts/poteto.md"
test -f install.sh || fail "missing install.sh"

grep -q '"grep"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks grep"
grep -q '"find"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks find"
grep -q '"ls"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks ls"
grep -q '"read"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks read"
grep -q 'poteto-mode/SKILL.md' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name poteto-mode/SKILL.md"
grep -q 'pi -p' overlay/AGENTS.md || fail "AGENTS.md must map Task to pi -p"
grep -q 'TODO.md' overlay/AGENTS.md || fail "AGENTS.md must map TodoWrite to TODO.md"
grep -q 'poteto-mode' prompts/poteto.md || fail "prompts/poteto.md must tell the model to read poteto-mode"

chars=$(wc -c < overlay/APPEND_SYSTEM.md)
if [ "$chars" -gt 1200 ]; then
	fail "overlay/APPEND_SYSTEM.md is ${chars} bytes, cap is 1200 (~0.3k tokens)"
fi

help="$(bash install.sh --help)"
printf '%s\n' "$help" | grep -q -- '--repos' && fail "install.sh --help must not name --repos"
printf '%s\n' "$help" | grep -qi workspace && fail "install.sh --help must not name workspace"
printf '%s\n' "$help" | grep -qi trading && fail "install.sh --help must not name trading"

if grep -qiE 'workspace|--repos|trading' install.sh; then
	fail "install.sh source must not name workspace, --repos, or trading"
fi
if grep -R -E '/home/[^$]|workspace root' -- install.sh overlay skills/jig skills/cross-repo | grep -v '^Binary'; then
	fail "hardcoded home path or workspace root in overlay files"
fi

echo "check-overlay ok"

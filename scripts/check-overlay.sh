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
if ! grep -q '.pistack' install.sh; then
	fail "install.sh must clone into .pistack when PSTACK is unset"
fi
if ! grep -q '.pi-stack' install.sh; then
	fail "install.sh must clone into .pi-stack when PI_STACK is unset"
fi
if ! grep -q 'BASH_SOURCE\[0\]:-' install.sh; then
	fail "install.sh must tolerate curl|bash (empty BASH_SOURCE)"
fi
if ! grep -q 'git clone' install.sh; then
	fail "install.sh must git clone when the default tree is missing"
fi
printf '%s\n' "$help" | grep -q PI_STACK || fail "install.sh --help must name PI_STACK"

tmp=$(mktemp -d)
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT
mkdir -p "$tmp/pstack/skills/poteto-mode"
printf '# stub\n' >"$tmp/pstack/skills/poteto-mode/SKILL.md"
stub="$tmp/pstack"
home="$tmp/home"
mkdir -p "$home"

# curl|bash: no checkout beside the process. PI_STACK already has overlay → skip clone.
(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" bash <"$root/install.sh"
) || fail "piped install with existing PI_STACK failed"
test -f "$home/.pi/agent/APPEND_SYSTEM.md" || fail "piped install did not write overlay"
test ! -e "$home/.pi/agent/auth.json" || fail "piped install wrote auth.json"

# curl|bash: PI_STACK unset → clone into $HOME/.pi-stack. Second run must not replace the tree.
home2="$tmp/home2"
mkdir -p "$home2"
(
	cd "$tmp"
	HOME="$home2" PSTACK="$stub" PI_STACK_GIT="$root" bash <"$root/install.sh"
) || fail "piped install with default PI_STACK failed"
test -f "$home2/.pi-stack/overlay/APPEND_SYSTEM.md" || fail "default PI_STACK was not cloned"
printf 'keep\n' >"$home2/.pi-stack/.skip-marker"
(
	cd "$tmp"
	HOME="$home2" PSTACK="$stub" PI_STACK_GIT="$root" bash <"$root/install.sh"
) || fail "second piped install failed"
test -f "$home2/.pi-stack/.skip-marker" || fail "second piped install recloned PI_STACK"

if grep -R -E '/home/[^$]|workspace root' -- install.sh overlay skills/jig skills/cross-repo | grep -v '^Binary'; then
	fail "hardcoded home path or workspace root in overlay files"
fi

echo "check-overlay ok"

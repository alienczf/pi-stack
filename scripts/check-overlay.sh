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
grep -q 'npm:pi-web-access' install.sh || fail "install.sh must install npm:pi-web-access"
grep -q 'npm:pi-hashline-edit' install.sh || fail "install.sh must install npm:pi-hashline-edit"
grep -q 'npm:pi-subagents' install.sh || fail "install.sh must install npm:pi-subagents"
grep -q 'PI_STACK_SKIP_PACKAGES' install.sh || fail "install.sh must honor PI_STACK_SKIP_PACKAGES"
grep -q 'conform-skills.py' install.sh || fail "install.sh must run conform-skills.py"
grep -q 'skills-pstack' install.sh || fail "install.sh must write skills-pstack"
grep -q 'poteto-mode/SKILL.md' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name poteto-mode/SKILL.md"
grep -q 'Do not run `pi -p`' overlay/AGENTS.md || fail "AGENTS.md must forbid bash pi -p"
grep -q 'subagent' overlay/AGENTS.md || fail "AGENTS.md must name the subagent tool"
grep -q 'subagent' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name the subagent tool"
grep -q 'TODO.md' overlay/AGENTS.md || fail "AGENTS.md must map TodoWrite to TODO.md"
grep -q 'web_search' overlay/AGENTS.md || fail "AGENTS.md must name web_search"
grep -q 'fetch_content' overlay/AGENTS.md || fail "AGENTS.md must name fetch_content"
grep -q 'LINE#HASH' overlay/AGENTS.md || fail "AGENTS.md must name LINE#HASH"
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
if grep -q pistack install.sh README.md; then
	fail "stale .pistack name; the only home dir is .pi-stack"
fi
if ! grep -F -q '.pi-stack' install.sh; then
	fail "install.sh must clone into .pi-stack when PI_STACK is unset"
fi
if ! grep -F -q '.plugins' install.sh; then
	fail "install.sh must clone pstack into PI_STACK/.plugins when PSTACK is unset"
fi
if ! grep -q 'BASH_SOURCE\[0\]:-' install.sh; then
	fail "install.sh must tolerate curl|bash (empty BASH_SOURCE)"
fi
if ! grep -q 'git clone' install.sh; then
	fail "install.sh must git clone when the default tree is missing"
fi
grep -q '^\.plugins/' .gitignore || fail ".gitignore must ignore nested .plugins/"
printf '%s\n' "$help" | grep -q PI_STACK || fail "install.sh --help must name PI_STACK"
printf '%s\n' "$help" | grep -F -q '.plugins' || fail "install.sh --help must name .plugins"

tmp=$(mktemp -d)
cleanup() { rm -rf "$tmp"; }
trap cleanup EXIT
mkdir -p "$tmp/pstack/skills/poteto-mode/playbooks"
cat >"$tmp/pstack/skills/poteto-mode/SKILL.md" <<'EOF'
---
name: Poteto Mode
description: stub for install test
---
# stub
EOF
printf 'playbook\n' >"$tmp/pstack/skills/poteto-mode/playbooks/investigation.md"
stub="$tmp/pstack"
home="$tmp/home"
mkdir -p "$home"

# curl|bash: no checkout beside the process. PI_STACK already has overlay → skip clone.
mkdir -p "$home/.pi/agent"
printf '%s\n' '{"theme":"keep-theme","packages":["npm:keep-me"]}' >"$home/.pi/agent/settings.json"
(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "piped install with existing PI_STACK failed"
test -f "$home/.pi/agent/APPEND_SYSTEM.md" || fail "piped install did not write overlay"
test ! -e "$home/.pi/agent/auth.json" || fail "piped install wrote auth.json"
test ! -d "$home/.pi/agent/npm" || fail "PI_STACK_SKIP_PACKAGES=1 still ran pi install"
test ! -d "$root/.plugins" || fail "stub PSTACK must not clone .plugins into this checkout"
python3 - "$home/.pi/agent/settings.json" <<'PY' || fail "piped install dropped packages or skipped required ones"
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
if data.get("theme") != "keep-theme":
	raise SystemExit("theme was dropped")
packages = data.get("packages")
if not isinstance(packages, list):
	raise SystemExit("packages missing")

def source(entry):
	return entry if isinstance(entry, str) else entry.get("source", "")

joined = [source(p) for p in packages]
if "npm:keep-me" not in joined:
	raise SystemExit("npm:keep-me was dropped")
web = next((p for p in packages if "pi-web-access" in source(p)), None)
if not isinstance(web, dict):
	raise SystemExit("pi-web-access missing or not object form")
if "!skills/librarian/**" not in web.get("skills", []):
	raise SystemExit("pi-web-access missing librarian filter")
if not any("pi-hashline-edit" in source(p) for p in packages):
	raise SystemExit("pi-hashline-edit missing")
if not any("pi-subagents" in source(p) for p in packages):
	raise SystemExit("pi-subagents missing")
skills = data.get("skills") or []
if not any("skills-pstack/poteto-mode" in s for s in skills):
	raise SystemExit("skills do not point at skills-pstack/poteto-mode")
if any("/pstack/skills/poteto-mode" in s for s in skills):
	raise SystemExit("skills still point at raw pstack")
PY
grep -q '^name: poteto-mode$' "$home/.pi/agent/skills-pstack/poteto-mode/SKILL.md" || fail "install did not slug Poteto Mode"
grep -q 'name: Poteto Mode' "$stub/skills/poteto-mode/SKILL.md" || fail "install edited upstream pstack"
test -L "$home/.pi/agent/skills-pstack/poteto-mode/playbooks" || fail "install did not symlink playbooks"

fake="$tmp/plugins-src"
mkdir -p "$fake/pstack/skills/poteto-mode"
cat >"$fake/pstack/skills/poteto-mode/SKILL.md" <<'EOF'
---
name: Poteto Mode
description: stub for clone test
---
# stub
EOF
git init -q "$fake"
git -C "$fake" add pstack
git -C "$fake" -c user.email=t@t -c user.name=t commit -qm stub

# Seed repo is this working tree, so the cloned install.sh matches uncommitted edits.
seed="$tmp/seed"
mkdir -p "$seed"
cp -a "$root/install.sh" "$root/overlay" "$root/prompts" "$root/bin" "$root/skills" "$root/.gitignore" "$seed/"
git init -q "$seed"
git -C "$seed" add .
git -C "$seed" -c user.email=t@t -c user.name=t commit -qm seed

# curl|bash: one prefix. Second run must not replace either tree.
home2="$tmp/home2"
mkdir -p "$home2"
(
	cd "$tmp"
	HOME="$home2" PI_STACK_GIT="$seed" PSTACK_GIT="$fake" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "piped install with default PI_STACK failed"
test -f "$home2/.pi-stack/overlay/APPEND_SYSTEM.md" || fail "default PI_STACK was not cloned"
test -f "$home2/.pi-stack/.plugins/pstack/skills/poteto-mode/SKILL.md" || fail "pstack was not cloned into PI_STACK/.plugins"
test ! -d "$home2/.pistack" || fail "install wrote a second home dir .pistack"
printf 'keep\n' >"$home2/.pi-stack/.skip-marker"
printf 'keep\n' >"$home2/.pi-stack/.plugins/.skip-marker"
(
	cd "$tmp"
	HOME="$home2" PI_STACK_GIT="$seed" PSTACK_GIT="$fake" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "second piped install failed"
test -f "$home2/.pi-stack/.skip-marker" || fail "second piped install recloned PI_STACK"
test -f "$home2/.pi-stack/.plugins/.skip-marker" || fail "second piped install recloned .plugins"

if grep -R -E '/home/[^$]|workspace root' -- install.sh overlay skills/jig skills/cross-repo | grep -v '^Binary'; then
	fail "hardcoded home path or workspace root in overlay files"
fi

echo "check-overlay ok"

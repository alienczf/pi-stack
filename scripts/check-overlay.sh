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
test ! -e prompts/goal.md || fail "prompts/goal.md must be replaced by the pi-goal extension"

grep -q '"grep"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks grep"
grep -q '"find"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks find"
grep -q '"ls"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks ls"
grep -q '"read"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks read"
grep -q 'npm:pi-web-access' install.sh || fail "install.sh must install npm:pi-web-access"
grep -q 'npm:pi-hashline-edit' install.sh || fail "install.sh must install npm:pi-hashline-edit"
grep -q 'npm:pi-subagents' install.sh || fail "install.sh must install npm:pi-subagents"
grep -q 'npm:@narumitw/pi-goal' install.sh || fail "install.sh must install npm:@narumitw/pi-goal"
grep -q 'PI_STACK_SKIP_PACKAGES' install.sh || fail "install.sh must honor PI_STACK_SKIP_PACKAGES"
grep -q 'backups/subagents' install.sh || fail "install.sh must name backups/subagents"
grep -q 'agents/' install.sh || fail "install.sh must name agents/"
for name in scout researcher oracle reviewer worker delegate; do
	test -f "overlay/agents/${name}.md" || fail "missing overlay/agents/${name}.md"
	grep -q "name: ${name}" "overlay/agents/${name}.md" || fail "overlay/agents/${name}.md must contain name: ${name}"
done
grep -q 'conform-skills.py' install.sh || fail "install.sh must run conform-skills.py"
grep -q 'skills-pstack' install.sh || fail "install.sh must write skills-pstack"
grep -q 'pi-node' install.sh || fail "install.sh must find pi under pi-node"
grep -q 'inherit' install.sh || fail "install.sh must rewrite cursor subagent models to inherit"
grep -F -q '.local/bin/jig' install.sh || fail "install.sh must link jig into .local/bin"
grep -q 'defaultProjectTrust' install.sh || fail "install.sh must set defaultProjectTrust when missing"
grep -q 'poteto-mode/SKILL.md' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name poteto-mode/SKILL.md"
grep -q 'Do not run `pi -p`' overlay/AGENTS.md || fail "AGENTS.md must forbid bash pi -p"
grep -q 'subagent' overlay/AGENTS.md || fail "AGENTS.md must name the subagent tool"
grep -q 'subagent' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name the subagent tool"
grep -q 'TODO.md' overlay/AGENTS.md || fail "AGENTS.md must map TodoWrite to TODO.md"
grep -q 'web_search' overlay/AGENTS.md || fail "AGENTS.md must name web_search"
grep -q 'fetch_content' overlay/AGENTS.md || fail "AGENTS.md must name fetch_content"
grep -q 'LINE#HASH' overlay/AGENTS.md || fail "AGENTS.md must name LINE#HASH"
grep -q 'poteto-mode' prompts/poteto.md || fail "prompts/poteto.md must tell the model to read poteto-mode"
for token in '/goal' goal_complete goal_blocked goal_wait subagent_wait nonBlocking; do
	grep -q "$token" overlay/AGENTS.md || fail "overlay/AGENTS.md must name $token"
done

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
mkdir -p "$home/.pi/agent/prompts"
cat >"$home/.pi/agent/prompts/goal.md" <<'EOF'
---
description: Pin an exit predicate and drive to it
argument-hint: "<predicate>"
---
Treat the rest of this message as the exit predicate.

${@:-Drive the current task to a checkable done state.}

Write the predicate at the top of `PLAN.md`. Work until it is true. Do not relax it. Log decisions in `decisions.tsv` when the work is long enough that a reviewer will need the trail.
EOF
mkdir -p "$home/.pi/agent/npm/node_modules/@narumitw/pi-goal"
printf '%s\n' '{"name":"@narumitw/pi-goal","version":"0.54.3"}' >"$home/.pi/agent/npm/node_modules/@narumitw/pi-goal/package.json"

# curl|bash: no checkout beside the process. PI_STACK already has overlay → skip clone.
mkdir -p "$home/.pi/agent"
cat >"$home/.pi/agent/settings.json" <<'EOF'
{
  "theme": "keep-theme",
  "packages": ["npm:keep-me"],
  "defaultModel": "cursor/auto",
  "enabledModels": ["cursor/auto", "cursor/composer-2.5"],
  "subagents": {
    "defaultModel": "cursor/auto",
    "agentOverrides": {
      "scout": {"model": "cursor/auto"},
      "oracle": {"model": "openai-codex/gpt-5.4"}
    }
  }
}
EOF
(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "piped install with existing PI_STACK failed"
test -f "$home/.pi/agent/APPEND_SYSTEM.md" || fail "piped install did not write overlay"
test ! -e "$home/.pi/agent/auth.json" || fail "piped install wrote auth.json"
test ! -d "$home/.pi/agent/npm/node_modules/pi-web-access" || fail "PI_STACK_SKIP_PACKAGES=1 still ran pi install"
test ! -e "$home/.pi/agent/prompts/goal.md" || fail "install did not remove the obsolete goal prompt"
python3 - "$home/.pi/agent/pi-goal.json" <<'PY' || fail "fresh install wrote the wrong pi-goal settings"
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
expected = {"continuationLimits": {"automaticTurns": None, "noProgressTurns": 3}}
if data != expected:
	raise SystemExit(f"unexpected pi-goal settings: {data!r}")
PY
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
if joined.count("npm:@narumitw/pi-goal") != 1:
	raise SystemExit("pi-goal missing or duplicated")
skills = data.get("skills") or []
if not any("skills-pstack/poteto-mode" in s for s in skills):
	raise SystemExit("skills do not point at skills-pstack/poteto-mode")
if any("/pstack/skills/poteto-mode" in s for s in skills):
	raise SystemExit("skills still point at raw pstack")
if data.get("defaultModel") != "cursor/auto":
	raise SystemExit("top-level defaultModel was rewritten")
if data.get("enabledModels") != ["cursor/auto", "cursor/composer-2.5"]:
	raise SystemExit("enabledModels was rewritten")
if data.get("defaultProjectTrust") != "always":
	raise SystemExit("defaultProjectTrust was not set to always")
subs = data.get("subagents") or {}
if subs.get("defaultModel") != "inherit":
	raise SystemExit("subagents.defaultModel was not inherit")
overrides = subs.get("agentOverrides") or {}
if (overrides.get("scout") or {}).get("model") != "inherit":
	raise SystemExit("scout model was not inherit")
if (overrides.get("oracle") or {}).get("model") != "openai-codex/gpt-5.4":
	raise SystemExit("oracle model pin was rewritten")
PY
grep -q '^name: poteto-mode$' "$home/.pi/agent/skills-pstack/poteto-mode/SKILL.md" || fail "install did not slug Poteto Mode"
grep -q 'name: Poteto Mode' "$stub/skills/poteto-mode/SKILL.md" || fail "install edited upstream pstack"
test -L "$home/.pi/agent/skills-pstack/poteto-mode/playbooks" || fail "install did not symlink playbooks"
test -L "$home/.local/bin/jig" || fail "install did not link ~/.local/bin/jig"
test -x "$home/.local/bin/jig" || fail "linked jig is not executable"
test -f "$home/.pi/agent/agents/oracle.md" || fail "piped install did not write agents/oracle.md"
grep -q poteto-mode "$home/.pi/agent/agents/worker.md" || fail "worker.md must mention poteto-mode"

mkdir -p "$home/.pi/agent/npm/node_modules/pi-subagents/agents"
printf '%s\n' 'UPSTREAM-ORACLE' >"$home/.pi/agent/npm/node_modules/pi-subagents/agents/oracle.md"
printf '%s\n' 'USER-ORACLE' >"$home/.pi/agent/agents/oracle.md"
stamp_n() {
	local d="$home/.pi/agent/backups/subagents"
	if [[ ! -d "$d" ]]; then
		printf '0'
		return
	fi
	find "$d" -mindepth 1 -maxdepth 1 -type d | wc -l | tr -d ' '
}
printf 'custom goal prompt\n' >"$home/.pi/agent/prompts/goal.md"
printf 'custom goal settings\n' >"$home/.pi/agent/pi-goal.json"
cp "$home/.pi/agent/pi-goal.json" "$tmp/pi-goal.after-custom"
if ! second_out="$(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$second_out" >&2
	fail "second piped install with fake upstream failed"
fi
grep -q '^custom goal prompt$' "$home/.pi/agent/prompts/goal.md" || fail "install removed a custom goal prompt"
printf '%s\n' "$second_out" | grep -q 'keeping it' || fail "install did not warn about the custom goal prompt"
cmp -s "$home/.pi/agent/pi-goal.json" "$tmp/pi-goal.after-custom" || fail "install overwrote existing pi-goal settings"
if grep -q USER-ORACLE "$home/.pi/agent/agents/oracle.md"; then
	fail "dest oracle.md still USER-ORACLE"
fi
grep -q 'name: oracle' "$home/.pi/agent/agents/oracle.md" || fail "dest oracle.md is not the overlay"
grep -R -q USER-ORACLE "$home/.pi/agent/backups/subagents" || fail "backups missing USER-ORACLE"
grep -R -q UPSTREAM-ORACLE "$home/.pi/agent/backups/subagents" || fail "backups missing UPSTREAM-ORACLE"
stamps_after_replace="$(stamp_n)"
[[ "$stamps_after_replace" -ge 1 ]] || fail "replace install created no stamp dir"
cp "$home/.pi/agent/agents/oracle.md" "$tmp/oracle.after-replace"
cp "$home/.pi/agent/settings.json" "$tmp/settings.after-replace"
(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "third piped install failed"
cmp -s "$home/.pi/agent/agents/oracle.md" "$tmp/oracle.after-replace" || fail "third install rewrote dest oracle.md"
cmp -s "$home/.pi/agent/settings.json" "$tmp/settings.after-replace" || fail "third install changed converged settings.json"
[[ "$(stamp_n)" == "$stamps_after_replace" ]] || fail "third install created a new stamp dir"

home_ask="$tmp/home-ask"
mkdir -p "$home_ask/.pi/agent"
printf '%s\n' '{"defaultProjectTrust":"ask","packages":["npm:@narumitw/pi-goal@0.54.3"]}' >"$home_ask/.pi/agent/settings.json"
mkdir -p "$home_ask/.pi/agent/prompts"
mkdir -p "$home_ask/.pi/agent/npm/node_modules/@narumitw/pi-goal"
printf '%s\n' '{"name":"@narumitw/pi-goal","version":"0.54.3"}' >"$home_ask/.pi/agent/npm/node_modules/@narumitw/pi-goal/package.json"
printf 'symlink target\n' >"$tmp/custom-goal-target"
ln -s "$tmp/custom-goal-target" "$home_ask/.pi/agent/prompts/goal.md"
printf 'not json\n' >"$home_ask/.pi/agent/pi-goal.json"
cp "$home_ask/.pi/agent/pi-goal.json" "$tmp/pi-goal.ask.before"
(
	cd "$tmp"
	HOME="$home_ask" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "install with existing defaultProjectTrust failed"
test -L "$home_ask/.pi/agent/prompts/goal.md" || fail "install removed a user-managed goal prompt symlink"
cmp -s "$home_ask/.pi/agent/pi-goal.json" "$tmp/pi-goal.ask.before" || fail "install rewrote existing invalid pi-goal settings"
python3 - "$home_ask/.pi/agent/settings.json" <<'PY' || fail "existing settings were not preserved"
import json
import sys
from pathlib import Path
data = json.loads(Path(sys.argv[1]).read_text())
if data.get("defaultProjectTrust") != "ask":
	raise SystemExit("ask was overwritten")
packages = data.get("packages") or []
sources = [entry if isinstance(entry, str) else entry.get("source", "") for entry in packages]
pinned = "npm:@narumitw/pi-goal@0.54.3"
if sources.count(pinned) != 1:
	raise SystemExit("pinned pi-goal package was replaced")
if "npm:@narumitw/pi-goal" in sources:
	raise SystemExit("pinned pi-goal package was duplicated")
PY

home_nopi="$tmp/home-nopi"
mkdir -p "$home_nopi"
path_nopi="/usr/bin:/bin"
if ! PATH="$path_nopi" command -v python3 >/dev/null 2>&1; then
	fail "need /usr/bin/python3 to test missing pi"
fi
if nopi_out="$(
	cd "$tmp"
	PATH="$path_nopi" HOME="$home_nopi" PI_STACK="$root" PSTACK="$stub" bash "$root/install.sh" 2>&1
)"; then
	fail "install without pi exited 0"
fi
printf '%s\n' "$nopi_out" | grep -q 'pi is not installed' || fail "install without pi did not say to install Pi"

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

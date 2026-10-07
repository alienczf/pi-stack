#!/usr/bin/env bash
set -euo pipefail
export PI_STACK_SKIP_SYSTEMD=1

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

tree_checksum() {
	python3 - "$1" <<'PY'
import hashlib
import os
import sys
from pathlib import Path

root = Path(sys.argv[1])
digest = hashlib.sha256()
paths = sorted(root.rglob("*"), key=lambda path: path.relative_to(root).as_posix())
for path in paths:
	rel = path.relative_to(root).as_posix()
	if path.is_symlink():
		digest.update(f"link {rel}\n{os.readlink(path)}\n".encode())
	elif path.is_file():
		digest.update(f"file {rel}\n".encode())
		digest.update(path.read_bytes())
	elif path.is_dir():
		digest.update(f"dir {rel}\n".encode())
sys.stdout.write(digest.hexdigest())
PY
}

assert_streams_base() {
	local home="$1"
	local skills_text
	test -L "$home/.local/bin/pi-streams" || fail "pi-streams was not linked in $home"
	[[ "$(readlink -- "$home/.local/bin/pi-streams")" == "$root/bin/pi-streams" ]] || fail "pi-streams link target is wrong in $home"
	"$home/.local/bin/pi-streams" --help >/dev/null || fail "installed pi-streams does not run in $home"
	cmp -s "$root/prompts/stream.md" "$home/.pi/agent/prompts/stream.md" || fail "stream prompt was not installed in $home"
	grep -q '^name: stream$' "$home/.pi/agent/skills-pstack/stream/SKILL.md" || fail "stream skill was not installed in $home"
	grep -q '^name: stream-kickoff$' "$home/.pi/agent/skills-pstack/stream-kickoff/SKILL.md" || fail "stream-kickoff skill was not installed in $home"
	skills_text="$(python3 - "$home/.pi/agent/settings.json" <<'PY'
import json
import sys
from pathlib import Path

data = json.loads(Path(sys.argv[1]).read_text())
skills = data.get("skills") or []
print("\n".join(Path(entry).name for entry in skills if isinstance(entry, str)))
PY
)"
	printf '%s\n' "$skills_text" | grep -qx stream || fail "settings.json is missing the stream skill"
	printf '%s\n' "$skills_text" | grep -qx stream-kickoff || fail "settings.json is missing the stream-kickoff skill"
}

assert_streams_layout() {
	local home="$1"
	local xdg="${2:-}"
	local unit_dir
	if [[ -n "$xdg" ]]; then
		unit_dir="$xdg/systemd/user"
	else
		unit_dir="$home/.config/systemd/user"
	fi
	assert_streams_base "$home"
	cmp -s "$root/bin/pi-web-cli" "$home/.local/bin/pi-web-cli" || fail "pi-web-cli content is wrong in $home"
	test -x "$home/.local/bin/pi-web-cli" || fail "pi-web-cli is not executable in $home"
	cmp -s "$root/systemd/pi-streams-tick.service" "$unit_dir/pi-streams-tick.service" || fail "tick service was not installed in $home"
	cmp -s "$root/systemd/pi-streams-tick.timer" "$unit_dir/pi-streams-tick.timer" || fail "tick timer was not installed in $home"
	grep -q '^Type=oneshot$' "$unit_dir/pi-streams-tick.service" || fail "tick service is not oneshot"
	grep -q '^ExecStart=%h/.local/bin/pi-streams tick$' "$unit_dir/pi-streams-tick.service" || fail "tick service ExecStart is wrong"
	grep -q '^OnBootSec=2min$' "$unit_dir/pi-streams-tick.timer" || fail "tick timer OnBootSec is wrong"
	grep -q '^OnUnitActiveSec=5min$' "$unit_dir/pi-streams-tick.timer" || fail "tick timer OnUnitActiveSec is wrong"
	grep -q '^WantedBy=timers.target$' "$unit_dir/pi-streams-tick.timer" || fail "tick timer WantedBy is wrong"
}

assert_streams_not_in_use() {
	local home="$1"
	assert_streams_base "$home"
	test ! -e "$home/.local/bin/pi-web-cli" || fail "install without a pi-streams home installed pi-web-cli in $home"
	test ! -e "$home/.config/systemd" || fail "install without a pi-streams home installed the tick units in $home"
}

register_streams_home() {
	local home="$1"
	mkdir -p "$home/.config/pi-streams"
	printf '%s\n' "$home/proj/streams" >"$home/.config/pi-streams/homes"
}

test -f overlay/APPEND_SYSTEM.md || fail "missing overlay/APPEND_SYSTEM.md"
test -f overlay/AGENTS.md || fail "missing overlay/AGENTS.md"
test -f overlay/settings.json || fail "missing overlay/settings.json"
test -d prompts || fail "missing prompts/"
test -f prompts/poteto.md || fail "missing prompts/poteto.md"
test -f install.sh || fail "missing install.sh"
test -x bin/update-pstack || fail "missing executable bin/update-pstack"
test -x bin/pstackctl.py || fail "missing executable bin/pstackctl.py"
test -x scripts/check-update-pstack.sh || fail "missing executable scripts/check-update-pstack.sh"
test -f skills/update-pstack/SKILL.md || fail "missing update-pstack skill"
test -f prompts/update-pstack.md || fail "missing update-pstack prompt"
test -x bin/pi-streams || fail "missing executable bin/pi-streams"
test -x bin/pi-web-cli || fail "missing executable bin/pi-web-cli"
test -f prompts/stream.md || fail "missing prompts/stream.md"
test -f skills/stream/SKILL.md || fail "missing stream skill"
test -f skills/stream-kickoff/SKILL.md || fail "missing stream-kickoff skill"
test -f systemd/pi-streams-tick.service || fail "missing pi-streams tick service"
test -f systemd/pi-streams-tick.timer || fail "missing pi-streams tick timer"
test ! -e prompts/goal.md || fail "unexpected bundled goal prompt"

grep -q '"grep"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks grep"
grep -q '"find"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks find"
grep -q '"ls"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks ls"
grep -q '"read"' overlay/settings.json || fail "overlay/settings.json defaultTools lacks read"
grep -q 'npm:pi-web-access' install.sh || fail "install.sh must install npm:pi-web-access"
grep -q 'npm:pi-subagents' install.sh || fail "install.sh must install npm:pi-subagents"
grep -q 'PI_STACK_SKIP_PACKAGES' install.sh || fail "install.sh must honor PI_STACK_SKIP_PACKAGES"
grep -q 'backups/subagents' install.sh || fail "install.sh must name backups/subagents"
grep -q 'agents/' install.sh || fail "install.sh must name agents/"
test -f overlay/agents/poteto-agent.md || fail "missing poteto-agent profile"
for name in scout researcher oracle reviewer worker delegate; do
	test ! -e "overlay/agents/${name}.md" || fail "retired overlay agent ${name} remains"
done
grep -q 'conform-skills.py' install.sh || fail "install.sh must run conform-skills.py"
grep -q 'skills-pstack' install.sh || fail "install.sh must write skills-pstack"
grep -q 'pi-node' install.sh || fail "install.sh must find pi under pi-node"
grep -q 'inherit' install.sh || fail "install.sh must rewrite cursor subagent models to inherit"
grep -F -q '.local/bin/update-pstack' install.sh || fail "install.sh must link update-pstack into ~/.local/bin"
grep -q 'without changing project trust' install.sh || fail "install.sh must document project trust preservation"
grep -q 'maintain-verification-skill' install.sh || fail "install.sh must register maintain-verification-skill"
grep -q 'update-pstack' install.sh || fail "install.sh must install update-pstack"
grep -q 'principle-\*/SKILL.md' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must load project Principles"
grep -q 'poteto-mode/SKILL.md' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name poteto-mode/SKILL.md"
grep -q 'Do not run `pi -p`' overlay/AGENTS.md || fail "AGENTS.md must forbid bash pi -p"
grep -q 'subagent' overlay/AGENTS.md || fail "AGENTS.md must name the subagent tool"
grep -q 'subagent' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must name the subagent tool"
grep -q 'TODO.md' overlay/AGENTS.md || fail "AGENTS.md must map TodoWrite to TODO.md"
grep -q 'web_search' overlay/AGENTS.md || fail "AGENTS.md must name web_search"
grep -q 'fetch_content' overlay/AGENTS.md || fail "AGENTS.md must name fetch_content"
grep -q 'built-in `read` and `edit`' overlay/AGENTS.md || fail "AGENTS.md must use built-in editing tools"
grep -q 'poteto-mode' prompts/poteto.md || fail "prompts/poteto.md must tell the model to read poteto-mode"
for token in subagent_wait nonBlocking; do
	grep -q "$token" overlay/AGENTS.md || fail "overlay/AGENTS.md must name $token"
done

chars=$(wc -c < overlay/APPEND_SYSTEM.md)
if [ "$chars" -gt 1200 ]; then
	fail "overlay/APPEND_SYSTEM.md is ${chars} bytes, cap is 1200 (~0.3k tokens)"
fi

help="$(bash install.sh --help)"
printf '%s\n' "$help" | grep -q -- '  -y ' || fail "install.sh --help must document -y"
printf '%s\n' "$help" | grep -q -- '--print-pstack-skills' || fail "install.sh --help must document its pstack skill query"
for flag in --project --pi-web-url --coordinator-model --coordinator-thinking; do
	printf '%s\n' "$help" | grep -q -F -- "$flag" || fail "install.sh --help must document $flag"
done
selected_skills="$(bash install.sh --print-pstack-skills)"
printf '%s\n' "$selected_skills" | grep -qx poteto-mode || fail "selected pstack skills omit poteto-mode"
printf '%s\n' "$selected_skills" | grep -qx reflect || fail "selected pstack skills omit reflect"
printf '%s\n' "$selected_skills" | grep -qx correct || fail "selected pstack skills omit correct"
printf '%s\n' "$selected_skills" | grep -qx maintain-verification-skill || fail "selected pstack skills omit maintain-verification-skill"
if bash install.sh -y extra >/dev/null 2>&1; then
	fail "install.sh accepted an extra argument after -y"
fi
if bash install.sh --project >/dev/null 2>&1; then
	fail "install.sh accepted --project without a root"
fi
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
no_systemctl="$tmp/no-systemctl"
mkdir -p "$no_systemctl"
cat >"$no_systemctl/systemctl" <<'EOF'
#!/bin/sh
printf 'systemctl %s\n' "$*" >&2
exit 99
EOF
chmod +x "$no_systemctl/systemctl"
export PATH="$no_systemctl:$PATH"
while IFS= read -r name; do
	mkdir -p "$tmp/pstack/skills/$name"
	cat >"$tmp/pstack/skills/$name/SKILL.md" <<EOF
---
name: $name
description: stub for $name install test
---
# stub
EOF
done < <(bash "$root/install.sh" --print-pstack-skills)
sed -i 's/^name: poteto-mode$/name: Poteto Mode/' "$tmp/pstack/skills/poteto-mode/SKILL.md"
mkdir -p "$tmp/pstack/skills/poteto-mode/playbooks"
printf 'playbook\n' >"$tmp/pstack/skills/poteto-mode/playbooks/investigation.md"
stub="$tmp/pstack"
test -f "$stub/skills/correct/SKILL.md" || fail "pstack stub is missing correct"
missing_stub="$tmp/missing-pstack"
cp -a "$stub" "$missing_stub"
rm "$missing_stub/skills/how/SKILL.md"
if missing_stub_out="$(HOME="$tmp/missing-home" PI_STACK="$root" PSTACK="$missing_stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	fail "install accepted a missing selected pstack skill"
fi
printf '%s\n' "$missing_stub_out" | grep -q 'predates selected skill how' || fail "missing selected skill error was not useful"
printf '%s\n' "$missing_stub_out" | grep -q 'update-pstack status' || fail "missing selected skill error did not name update-pstack"
test ! -e "$tmp/missing-home/.pi/agent" || fail "missing selected skill was detected after installation began"
missing_correct="$tmp/missing-correct"
cp -a "$stub" "$missing_correct"
rm "$missing_correct/skills/correct/SKILL.md"
if missing_correct_out="$(HOME="$tmp/missing-correct-home" PI_STACK="$root" PSTACK="$missing_correct" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	fail "install accepted a pstack checkout that predates correct"
fi
printf '%s\n' "$missing_correct_out" | grep -q 'update-pstack' || fail "outdated pstack checkout did not name update-pstack"
printf '%s\n' "$missing_correct_out" | grep -q 'predates selected skill correct' || fail "outdated pstack checkout did not name correct"
test ! -e "$tmp/missing-correct-home/.pi/agent" || fail "outdated pstack checkout was detected after installation began"

legacy_home="$tmp/home-legacy-jig"
legacy_agent="$legacy_home/.pi/agent"
mkdir -p "$legacy_agent/jig/bin" "$legacy_agent/bin" "$legacy_agent/prompts" "$legacy_agent/skills-pstack/jig" "$legacy_home/.local/bin"
printf 'launcher\n' >"$legacy_agent/jig/bin/jig.sh"
printf 'nested\n' >"$legacy_agent/jig/bin/extra.txt"
printf 'wrapper\n' >"$legacy_agent/bin/jig"
printf 'prompt\n' >"$legacy_agent/prompts/jig.md"
printf 'skill\n' >"$legacy_agent/skills-pstack/jig/SKILL.md"
ln -s "$legacy_agent/bin/jig" "$legacy_home/.local/bin/jig"
keep_skill="$tmp/unrelated-skill-keep"
python3 - "$legacy_agent/settings.json" "$legacy_agent" "$keep_skill" <<'PY'
import json
import sys
from pathlib import Path

dest, agent, keep = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
dest.write_text(json.dumps({
	"theme": "keep-theme",
	"skills": [
		str(agent / "skills-pstack/jig"),
		str(agent / "jig/skills/jig"),
		keep,
	],
}, indent=2) + "\n")
PY
if ! legacy_out="$(HOME="$legacy_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$legacy_out" >&2
	fail "install did not clean an earlier Jig install"
fi
printf '%s\n' "$legacy_out" | grep -q 'Removed earlier Jig install:' || fail "install did not name the removed Jig artifacts"
for legacy_path in \
	"$legacy_agent/jig" \
	"$legacy_agent/bin/jig" \
	"$legacy_home/.local/bin/jig" \
	"$legacy_agent/prompts/jig.md" \
	"$legacy_agent/skills-pstack/jig" \
	"$legacy_agent/jig/skills/jig"
do
	test ! -e "$legacy_path" || fail "legacy Jig artifact remains: $legacy_path"
	printf '%s\n' "$legacy_out" | grep -F -q "$legacy_path" || fail "removal line omitted $legacy_path"
done
if printf '%s\n' "$legacy_out" | grep -F -q "$keep_skill"; then
	fail "Jig cleanup named an unrelated skill"
fi
python3 - "$legacy_agent/settings.json" "$legacy_agent" "$keep_skill" <<'PY' || fail "Jig cleanup dropped an unrelated skill or left a Jig skill"
import json
import sys
from pathlib import Path

settings, agent, keep = Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3]
data = json.loads(settings.read_text())
if data.get("theme") != "keep-theme":
	raise SystemExit("theme was dropped")
skills = data.get("skills")
if not isinstance(skills, list) or keep not in skills:
	raise SystemExit("unrelated skill was dropped")
jig_root = (agent / "jig").resolve()
for entry in skills:
	if not isinstance(entry, str):
		continue
	text = entry.rstrip("/")
	if text.endswith("/skills-pstack/jig"):
		raise SystemExit("skills-pstack/jig remains")
	candidate = Path(text)
	if candidate.is_absolute():
		resolved = candidate.resolve()
		if resolved == jig_root or jig_root in resolved.parents:
			raise SystemExit("skill under the jig tree remains")
PY
legacy_settings_sum="$(sha256sum "$legacy_agent/settings.json")"
legacy_agent_sum="$(tree_checksum "$legacy_agent")"
if ! legacy_again="$(HOME="$legacy_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$legacy_again" >&2
	fail "second install after Jig cleanup failed"
fi
if printf '%s\n' "$legacy_again" | grep -q 'Removed earlier Jig install:'; then
	fail "second install reported another Jig removal"
fi
[[ "$(sha256sum "$legacy_agent/settings.json")" == "$legacy_settings_sum" ]] || fail "second install changed settings.json"
[[ "$(tree_checksum "$legacy_agent")" == "$legacy_agent_sum" ]] || fail "second install changed the agent tree"

keeper_home="$tmp/home-jig-keeper"
mkdir -p "$keeper_home/.local/bin"
printf 'user jig command\n' >"$keeper_home/.local/bin/jig"
cp "$keeper_home/.local/bin/jig" "$tmp/jig-keeper.before"
if ! keeper_out="$(HOME="$keeper_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$keeper_out" >&2
	fail "install with an unrelated jig command failed"
fi
cmp -s "$keeper_home/.local/bin/jig" "$tmp/jig-keeper.before" || fail "install changed an unrelated jig command"
test ! -L "$keeper_home/.local/bin/jig" || fail "unrelated jig command became a symlink"
if printf '%s\n' "$keeper_out" | grep -q 'Removed earlier Jig install:'; then
	fail "install reported removing an unrelated jig command"
fi

foreign_home="$tmp/home-jig-foreign-link"
mkdir -p "$foreign_home/.local/bin"
ln -s /usr/bin/true "$foreign_home/.local/bin/jig"
if ! foreign_out="$(HOME="$foreign_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$foreign_out" >&2
	fail "install with an unrelated jig symlink failed"
fi
test -L "$foreign_home/.local/bin/jig" || fail "install removed an unrelated jig symlink"
[[ "$(readlink "$foreign_home/.local/bin/jig")" == /usr/bin/true ]] || fail "install retargeted an unrelated jig symlink"
if printf '%s\n' "$foreign_out" | grep -q 'Removed earlier Jig install:'; then
	fail "install reported removing an unrelated jig symlink"
fi

into_home="$tmp/home-jig-into"
into_agent="$into_home/.pi/agent"
mkdir -p "$into_agent/jig/bin" "$into_home/.local/bin"
printf 'launcher\n' >"$into_agent/jig/bin/jig.sh"
ln -s "$into_agent/jig/bin/jig.sh" "$into_home/.local/bin/jig"
if ! into_out="$(HOME="$into_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$into_out" >&2
	fail "install did not remove a symlink into the jig tree"
fi
test ! -e "$into_home/.local/bin/jig" || fail "install left a symlink into the jig tree"
test ! -e "$into_agent/jig" || fail "install left the jig tree"
printf '%s\n' "$into_out" | grep -F -q "$into_home/.local/bin/jig" || fail "removal line omitted the symlink into the jig tree"

home="$tmp/home"
mkdir -p "$home/.pi/agent/prompts"

# curl|bash: no checkout beside the process. PI_STACK already has overlay → skip clone.
mkdir -p "$home/.pi/agent"
cat >"$home/.pi/agent/settings.json" <<'EOF'
{
  "theme": "keep-theme",
  "packages": ["npm:keep-me", "npm:pi-hashline-edit@1.0.0", {"source":"npm:pi-gal@2.0.0","extensions":[]}, "npm:@narumitw/pi-goal"],
  "defaultModel": "cursor/auto",
  "enabledModels": ["cursor/auto", "cursor/composer-2.5"],
  "subagents": {
    "defaultModel": "cursor/auto",
    "agentOverrides": {
      "scout": {"model": "cursor/auto", "disabled": false},
      "oracle": {"model": "openai-codex/gpt-5.4"},
      "planner": {"disabled": false},
      "poteto-agent": {"disabled": true}
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
test ! -e "$home/.pi/agent/prompts/goal.md" || fail "install created a goal prompt"
test ! -e "$home/.pi/agent/pi-goal.json" || fail "install created pi-goal.json"
test ! -e "$home/.pi/agent/npm/node_modules/@narumitw/pi-goal" || fail "install fetched the removed goal package"
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
assert set(joined) == {"npm:keep-me", "npm:pi-web-access", "npm:pi-subagents"}
if not any("pi-subagents" in source(p) for p in packages):
	raise SystemExit("pi-subagents missing")
assert not any(s.startswith("npm:@narumitw/pi-goal") for s in joined), joined
skills = data.get("skills") or []
if not any("skills-pstack/poteto-mode" in s for s in skills):
	raise SystemExit("skills do not point at skills-pstack/poteto-mode")
if any("/pstack/skills/poteto-mode" in s for s in skills):
	raise SystemExit("skills still point at raw pstack")
if not any("skills-pstack/reflect" in s for s in skills):
	raise SystemExit("reflect is not installed")
if not any("skills-pstack/correct" in s for s in skills):
	raise SystemExit("correct is not installed")
if not any("skills-pstack/create-verification-skill" in s for s in skills):
	raise SystemExit("create-verification-skill is not installed")
if not any("skills-pstack/maintain-verification-skill" in s for s in skills):
	raise SystemExit("maintain-verification-skill is not installed")
if not any("skills-pstack/update-pstack" in s for s in skills):
	raise SystemExit("update-pstack is not installed")
if data.get("defaultModel") != "cursor/auto":
	raise SystemExit("top-level defaultModel was rewritten")
if data.get("enabledModels") != ["cursor/auto", "cursor/composer-2.5"]:
	raise SystemExit("enabledModels was rewritten")
if "defaultProjectTrust" in data:
	raise SystemExit("fresh settings gained defaultProjectTrust")
subs = data.get("subagents") or {}
if subs.get("defaultModel") != "inherit":
	raise SystemExit("subagents.defaultModel was not inherit")
overrides = subs.get("agentOverrides") or {}
if (overrides.get("scout") or {}).get("model") != "inherit":
	raise SystemExit("scout model was not inherit")
if (overrides.get("oracle") or {}).get("model") != "openai-codex/gpt-5.4":
	raise SystemExit("oracle model pin was rewritten")
assert subs["disableBuiltins"] is True
for name in ("scout", "researcher", "oracle", "reviewer", "worker", "delegate"):
	assert overrides[name]["disabled"] is True, name
assert overrides["poteto-agent"]["disabled"] is False
assert all(spec["disabled"] is True for name, spec in overrides.items() if name != "poteto-agent")
PY
grep -q '^name: poteto-mode$' "$home/.pi/agent/skills-pstack/poteto-mode/SKILL.md" || fail "install did not slug Poteto Mode"
grep -q 'name: Poteto Mode' "$stub/skills/poteto-mode/SKILL.md" || fail "install edited upstream pstack"
test -L "$home/.pi/agent/skills-pstack/poteto-mode/playbooks" || fail "install did not symlink playbooks"
test ! -e "$home/.pi/agent/jig" || fail "install created the jig tree"
test ! -e "$home/.pi/agent/bin/jig" || fail "install created the jig launcher"
test ! -e "$home/.local/bin/jig" || fail "install linked jig"
test ! -e "$home/.pi/agent/prompts/jig.md" || fail "install copied the jig prompt"
test ! -e "$home/.pi/agent/skills-pstack/jig" || fail "install registered jig"
test -f "$home/.pi/agent/skills-pstack/reflect/SKILL.md" || fail "install did not register reflect"
test -f "$home/.pi/agent/skills-pstack/correct/SKILL.md" || fail "install did not register correct"
test -f "$home/.pi/agent/skills-pstack/create-verification-skill/SKILL.md" || fail "install did not register create-verification-skill"
test -f "$home/.pi/agent/skills-pstack/maintain-verification-skill/SKILL.md" || fail "install did not register maintain-verification-skill"
test -f "$home/.pi/agent/skills-pstack/update-pstack/SKILL.md" || fail "install did not register update-pstack"
test -f "$home/.pi/agent/prompts/update-pstack.md" || fail "install did not copy the update-pstack prompt"
test -x "$home/.pi/agent/update-pstack/bin/update-pstack" || fail "install did not copy the update-pstack command"
test -x "$home/.pi/agent/update-pstack/bin/pstackctl.py" || fail "install did not copy the update-pstack controller"
test -L "$home/.local/bin/update-pstack" || fail "install did not link ~/.local/bin/update-pstack"
test -x "$home/.local/bin/update-pstack" || fail "linked update-pstack is not executable"
grep -F -q "$root" "$home/.pi/agent/bin/update-pstack" || fail "installed update-pstack wrapper forgot its pi-stack source"
"$home/.local/bin/update-pstack" --help | grep -q '^usage: update-pstack' || fail "installed update-pstack command does not run"
assert_streams_not_in_use "$home"
test -f "$home/.pi/agent/agents/poteto-agent.md" || fail "piped install did not write poteto-agent"
grep -q poteto-mode "$home/.pi/agent/agents/poteto-agent.md" || fail "poteto-agent must read poteto-mode"
python3 - "$home" <<'PY'
import json
import sys
from pathlib import Path
config = json.loads((Path(sys.argv[1]) / ".pi/agent/extensions/subagent/config.json").read_text())
assert config == {"intercomBridge": {"mode": "off"}, "control": {"notifyChannels": ["event", "async"]}}
PY
cat >"$home/.pi/agent/extensions/subagent/config.json" <<'EOF'
{"asyncByDefault":true,"intercomBridge":{"mode":"always","instructionFile":"keep.md"},"control":{"enabled":false,"notifyChannels":["intercom","async","intercom"]}}
EOF
cp "$home/.pi/agent/extensions/subagent/config.json" "$tmp/config.before-refresh"

mkdir -p "$home/.pi/agent/npm/node_modules/pi-subagents/agents"
printf '%s\n' 'UPSTREAM-ORACLE' >"$home/.pi/agent/npm/node_modules/pi-subagents/agents/oracle.md"
printf '%s\n' 'USER-ORACLE' >"$home/.pi/agent/agents/oracle.md"
for name in scout researcher reviewer worker delegate; do
	printf 'USER-%s\n' "$name" >"$home/.pi/agent/agents/$name.md"
done
printf 'USER-POTETO\n' >"$home/.pi/agent/agents/poteto-agent.md"
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
cmp -s "$home/.pi/agent/pi-goal.json" "$tmp/pi-goal.after-custom" || fail "install overwrote existing pi-goal settings"
for name in scout researcher reviewer worker delegate oracle; do
	test ! -e "$home/.pi/agent/agents/$name.md" || fail "retired installed agent $name remains"
done
for name in scout researcher reviewer worker delegate; do
	grep -R -q "USER-$name" "$home/.pi/agent/backups/subagents" || fail "missing backup for $name"
done
grep -R -q USER-POTETO "$home/.pi/agent/backups/subagents" || fail "missing poteto backup"
grep -q 'name: poteto-agent' "$home/.pi/agent/agents/poteto-agent.md" || fail "poteto-agent is not the overlay"
grep -R -q USER-ORACLE "$home/.pi/agent/backups/subagents" || fail "backups missing USER-ORACLE"
grep -R -q UPSTREAM-ORACLE "$home/.pi/agent/backups/subagents" || fail "backups missing UPSTREAM-ORACLE"
python3 - "$home" "$tmp/config.before-refresh" <<'PY'
import json
import sys
from pathlib import Path
agent = Path(sys.argv[1]) / ".pi/agent"
original = Path(sys.argv[2]).read_text()
config = json.loads((agent / "extensions/subagent/config.json").read_text())
assert config == {
	"asyncByDefault": True,
	"intercomBridge": {"mode": "off", "instructionFile": "keep.md"},
	"control": {"enabled": False, "notifyChannels": ["event", "async"]},
}
assert any(p.read_text() == original for p in (agent / "backups/subagents").glob("config-*.json"))
PY
cp "$home/.pi/agent/extensions/subagent/config.json" "$tmp/config.after-refresh"
config_backups="$(find "$home/.pi/agent/backups/subagents" -name 'config-*.json' | wc -l)"
stamps_after_replace="$(stamp_n)"
[[ "$stamps_after_replace" -ge 1 ]] || fail "replace install created no stamp dir"
cp "$home/.pi/agent/agents/poteto-agent.md" "$tmp/poteto.after-replace"
cp "$home/.pi/agent/settings.json" "$tmp/settings.after-replace"
(
	cd "$tmp"
	HOME="$home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "third piped install failed"
cmp -s "$home/.pi/agent/agents/poteto-agent.md" "$tmp/poteto.after-replace" || fail "third install rewrote poteto-agent"
for name in scout researcher reviewer worker delegate oracle; do
	test ! -e "$home/.pi/agent/agents/$name.md" || fail "third install restored $name"
done
cmp -s "$home/.pi/agent/settings.json" "$tmp/settings.after-replace" || fail "third install changed converged settings.json"
[[ "$(stamp_n)" == "$stamps_after_replace" ]] || fail "third install created a new stamp dir"
cmp -s "$home/.pi/agent/extensions/subagent/config.json" "$tmp/config.after-refresh" || fail "third install changed subagent config"
[[ "$(find "$home/.pi/agent/backups/subagents" -name 'config-*.json' | wc -l)" == "$config_backups" ]] || fail "third install backed up unchanged subagent config"
assert_streams_not_in_use "$home"

home_ask="$tmp/home-ask"
mkdir -p "$home_ask/.pi/agent"
printf '%s\n' '{"defaultProjectTrust":"ask","packages":["npm:keep-me@1.0.0", "npm:@narumitw/pi-goal@0.54.3", {"source":"npm:@narumitw/pi-goal@0.54.4","extensions":[]}]}' >"$home_ask/.pi/agent/settings.json"
mkdir -p "$home_ask/.pi/agent/prompts"
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
assert sources.count("npm:keep-me@1.0.0") == 1
assert not any(s.startswith("npm:@narumitw/pi-goal") for s in sources), sources
PY

home_nopi="$tmp/home-nopi"
mkdir -p "$home_nopi"
path_nopi="$no_systemctl:/usr/bin:/bin"
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
while IFS= read -r name; do
	mkdir -p "$fake/pstack/skills/$name"
	cat >"$fake/pstack/skills/$name/SKILL.md" <<EOF
---
name: $name
description: stub for $name clone test
---
# stub
EOF
done < <(bash "$root/install.sh" --print-pstack-skills)
sed -i 's/^name: poteto-mode$/name: Poteto Mode/' "$fake/pstack/skills/poteto-mode/SKILL.md"
git init -q "$fake"
git -C "$fake" add pstack
git -C "$fake" -c user.email=t@t -c user.name=t commit -qm stub
initial_pstack_head="$(git -C "$fake" rev-parse HEAD)"

seed="$tmp/seed"
mkdir -p "$seed"
cp -a "$root/install.sh" "$root/overlay" "$root/prompts" "$root/bin" "$root/skills" "$root/systemd" "$root/.gitignore" "$seed/"
git init -q "$seed"
git -C "$seed" add .
git -C "$seed" -c user.email=t@t -c user.name=t commit -qm seed
initial_seed_head="$(git -C "$seed" rev-parse HEAD)"
seed_url="file://$seed"
pstack_url="file://$fake"

home2="$tmp/home2"
mkdir -p "$home2"
(
	cd "$tmp"
	HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash <"$root/install.sh"
) || fail "piped install with default PI_STACK failed"
test -f "$home2/.pi-stack/overlay/APPEND_SYSTEM.md" || fail "default PI_STACK was not cloned"
test -f "$home2/.pi-stack/.plugins/pstack/skills/poteto-mode/SKILL.md" || fail "pstack was not cloned into PI_STACK/.plugins"
test ! -d "$home2/.pistack" || fail "install wrote a second home dir .pistack"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$initial_seed_head" || fail "fresh install cloned the wrong pi-stack revision"
test "$(git -C "$home2/.pi-stack/.plugins" rev-parse HEAD)" = "$initial_pstack_head" || fail "fresh install cloned the wrong pstack revision"
test "$(git -C "$home2/.pi-stack" rev-parse --is-shallow-repository)" = true || fail "default PI_STACK fixture is not shallow"
managed_branch="$(git -C "$home2/.pi-stack" symbolic-ref --short HEAD)"
printf 'keep\n' >"$home2/.pi-stack/.skip-marker"
printf 'keep\n' >"$home2/.pi-stack/.plugins/.skip-marker"

python3 - "$seed/install.sh" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
text = path.read_text()
needle = "\tpi-subagents\n"
if text.count(needle) != 1:
	raise SystemExit("required package insertion point changed")
path.write_text(text.replace(needle, needle + "\tpi-update-fixture\n"))
PY
git -C "$seed" add install.sh
git -C "$seed" -c user.email=t@t -c user.name=t commit -qm update
updated_seed_head="$(git -C "$seed" rev-parse HEAD)"
printf 'updated\n' >"$fake/pstack/update-marker"
git -C "$fake" add pstack/update-marker
git -C "$fake" -c user.email=t@t -c user.name=t commit -qm update
tty_runner="$tmp/run-with-tty.py"
cat >"$tty_runner" <<'PY'
import errno
import os
import pty
import sys

script, answer = sys.argv[1:]
pid, terminal = pty.fork()
if pid == 0:
	script_fd = os.open(script, os.O_RDONLY)
	os.dup2(script_fd, 0)
	if script_fd != 0:
		os.close(script_fd)
	os.execvp("bash", ["bash"])

output = bytearray()
sent = False
while True:
	try:
		chunk = os.read(terminal, 4096)
	except OSError as error:
		if error.errno == errno.EIO:
			break
		raise
	if not chunk:
		break
	output.extend(chunk)
	if not sent and b"? [y/N] " in output:
		os.write(terminal, answer.encode() + b"\n")
		sent = True

_, status = os.waitpid(pid, 0)
sys.stdout.buffer.write(output)
if not sent:
	raise SystemExit("installer did not prompt on /dev/tty")
if os.WIFEXITED(status):
	raise SystemExit(os.WEXITSTATUS(status))
raise SystemExit(128 + os.WTERMSIG(status))
PY
no_tty_runner="$tmp/run-without-tty.py"
cat >"$no_tty_runner" <<'PY'
import subprocess
import sys

with open(sys.argv[1], "rb") as script:
	result = subprocess.run(
		["bash"],
		stdin=script,
		stdout=subprocess.PIPE,
		stderr=subprocess.STDOUT,
		start_new_session=True,
	)
sys.stdout.buffer.write(result.stdout)
raise SystemExit(result.returncode)
PY

if ! reject_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 python3 "$tty_runner" "$root/install.sh" n 2>&1)"; then
	printf '%s\n' "$reject_out" >&2
	fail "update prompt rejection failed"
fi
printf '%s\n' "$reject_out" | grep -q 'Update existing pi-stack checkout' || fail "existing install did not prompt for an update"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$initial_seed_head" || fail "n updated the pi-stack checkout"

if ! piped_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 python3 "$no_tty_runner" "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$piped_out" >&2
	fail "noninteractive piped reinstall failed"
fi
printf '%s\n' "$piped_out" | grep -q 'Rerun with -y' || fail "noninteractive piped reinstall did not explain how to update"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$initial_seed_head" || fail "noninteractive piped reinstall updated without consent"

if ! explicit_out="$(HOME="$home2" PI_STACK="$home2/.pi-stack" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	printf '%s\n' "$explicit_out" >&2
	fail "explicit PI_STACK reinstall failed"
fi
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$initial_seed_head" || fail "-y updated an explicit PI_STACK checkout"
if printf '%s\n' "$explicit_out" | grep -q 'Update existing pi-stack checkout'; then
	fail "-y prompted for an explicit PI_STACK checkout"
fi

if ! direct_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash "$home2/.pi-stack/install.sh" -y 2>&1)"; then
	printf '%s\n' "$direct_out" >&2
	fail "direct checkout reinstall failed"
fi
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$initial_seed_head" || fail "-y updated a directly executed checkout"
if printf '%s\n' "$direct_out" | grep -q 'Update existing pi-stack checkout'; then
	fail "-y prompted for a directly executed checkout"
fi

npm_root="$home2/.pi/agent/npm/node_modules"
for package in pi-web-access pi-subagents; do
	mkdir -p "$npm_root/$package"
done
fake_bin="$tmp/fake-bin"
mkdir -p "$fake_bin"
cat >"$fake_bin/pi" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
[[ "${1:-}" == install || "${1:-}" == remove ]]
[[ "${2:-}" == npm:* ]]
package="${2#npm:}"
if [[ "$1" == remove ]]; then
	printf '%s\n' "$2" >>"$PI_REMOVE_LOG"
	if [[ "${PI_FAKE_REMOVE_NOOP:-}" == 1 ]]; then exit 0; fi
	python3 - "$PI_CODING_AGENT_DIR/npm" "$package" <<'PY'
import json
import shutil
import sys
from pathlib import Path
root, name = Path(sys.argv[1]), sys.argv[2]
shutil.rmtree(root / "node_modules" / name, ignore_errors=True)
p = root / "package.json"
if p.exists():
	data = json.loads(p.read_text())
	for key in ("dependencies", "devDependencies", "optionalDependencies"):
		data.get(key, {}).pop(name, None)
	p.write_text(json.dumps(data))
PY
	exit 0
fi
printf '%s\n' "$2" >>"$PI_INSTALL_LOG"
mkdir -p "$PI_CODING_AGENT_DIR/npm/node_modules/$package"
printf '{"name":"%s","version":"fixture"}\n' "$package" >"$PI_CODING_AGENT_DIR/npm/node_modules/$package/package.json"
EOF
chmod +x "$fake_bin/pi"
cold_log="$tmp/cold-install.log"
for pass in 1 2; do
	PATH="$fake_bin:$PATH" HOME="$tmp/cold-home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=0 PI_INSTALL_LOG="$cold_log" bash "$root/install.sh" >"$tmp/cold-install-$pass.log" 2>&1 || fail "cold package install pass $pass failed"
done
python3 - "$cold_log" <<'PY'
from pathlib import Path
import sys
assert Path(sys.argv[1]).read_text().splitlines() == [
	"npm:pi-web-access", "npm:pi-subagents",
]
PY
test ! -e "$tmp/cold-home/.pi/agent/pi-goal.json" || fail "cold install created pi-goal.json"
test ! -e "$tmp/cold-home/.pi/agent/npm/node_modules/@narumitw/pi-goal" || fail "cold install fetched the removed goal package"
migration_home="$tmp/migration-home"
mkdir -p "$migration_home/.pi/agent/npm/node_modules/pi-hashline-edit"
printf '%s\n' '{"packages":["npm:pi-hashline-edit",{"source":"npm:pi-gal@2.0.0"},"npm:@narumitw/pi-goal@0.54.3","npm:keep-me"]}' >"$migration_home/.pi/agent/settings.json"
printf '%s\n' '{"dependencies":{"pi-hashline-edit":"1","pi-gal":"2","@narumitw/pi-goal":"0.54.3","keep-me":"3"}}' >"$migration_home/.pi/agent/npm/package.json"
if PATH="$fake_bin:$PATH" HOME="$migration_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=0 PI_INSTALL_LOG="$tmp/noop-install.log" PI_REMOVE_LOG="$tmp/noop-remove.log" PI_FAKE_REMOVE_NOOP=1 bash "$root/install.sh" >"$tmp/noop-remove-output.log" 2>&1; then
	fail "install accepted a removal that left a retired package behind"
fi
grep -q 'retired package remains' "$tmp/noop-remove-output.log" || fail "removal failure was not useful"
for pass in 1 2; do
	PATH="$fake_bin:$PATH" HOME="$migration_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=0 PI_INSTALL_LOG="$tmp/migration-install.log" PI_REMOVE_LOG="$tmp/migration-remove.log" bash "$root/install.sh" >"$tmp/migration-$pass.log" 2>&1 || fail "package migration pass $pass failed"
done
python3 - "$migration_home" "$tmp/migration-remove.log" <<'PY'
import json
import sys
from pathlib import Path
agent = Path(sys.argv[1]) / ".pi/agent"
assert Path(sys.argv[2]).read_text().splitlines() == ["npm:pi-hashline-edit", "npm:pi-gal", "npm:@narumitw/pi-goal"]
assert json.loads((agent / "npm/package.json").read_text()) == {"dependencies": {"keep-me": "3"}}
settings = json.loads((agent / "settings.json").read_text())
assert "npm:keep-me" in settings["packages"]
for name in ("pi-hashline-edit", "pi-gal", "@narumitw/pi-goal"):
	assert not (agent / "npm/node_modules" / name).exists()
	for entry in settings["packages"]:
		source = entry if isinstance(entry, str) else entry["source"]
		assert source != f"npm:{name}" and not source.startswith(f"npm:{name}@")
assert not (agent / "pi-goal.json").exists()
backups = list((agent / "backups/packages").glob("settings-*.json"))
assert len(backups) == 1
assert json.loads(backups[0].read_text())["packages"] == ["npm:pi-hashline-edit", {"source": "npm:pi-gal@2.0.0"}, "npm:@narumitw/pi-goal@0.54.3", "npm:keep-me"]
PY
install_log="$tmp/pi-install.log"
if ! accept_out="$(PATH="$fake_bin:$PATH" HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_INSTALL_LOG="$install_log" python3 "$tty_runner" "$root/install.sh" y 2>&1)"; then
	printf '%s\n' "$accept_out" >&2
	fail "update prompt acceptance failed"
fi
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$updated_seed_head" || fail "y did not update the pi-stack checkout"
test "$(git -C "$home2/.pi-stack/.plugins" rev-parse HEAD)" = "$initial_pstack_head" || fail "pi-stack update also updated pstack"
test -f "$home2/.pi-stack/.skip-marker" || fail "pi-stack update removed an untracked file"
test -f "$home2/.pi-stack/.plugins/.skip-marker" || fail "pi-stack update replaced .plugins"
test -d "$npm_root/pi-update-fixture" || fail "updated installer did not install its new dependency"
test "$(cat "$install_log")" = "npm:pi-update-fixture" || fail "updated installer reinstalled existing Pi packages"
grep -q 'npm:pi-update-fixture' "$home2/.pi/agent/settings.json" || fail "updated installer did not register its new dependency"

printf 'next\n' >"$seed/update-marker"
git -C "$seed" add update-marker
git -C "$seed" -c user.email=t@t -c user.name=t commit -qm next
next_seed_head="$(git -C "$seed" rev-parse HEAD)"
printf '\nlocal change\n' >>"$home2/.pi-stack/install.sh"
if dirty_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	fail "-y updated a checkout with tracked changes"
fi
printf '%s\n' "$dirty_out" | grep -q 'has tracked or staged changes' || fail "dirty checkout failure was not useful"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$updated_seed_head" || fail "dirty checkout advanced before failing"
git -C "$home2/.pi-stack" checkout -- install.sh
: >"$install_log"
if ! yes_out="$(PATH="$fake_bin:$PATH" HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_INSTALL_LOG="$install_log" bash -s -- -y <"$root/install.sh" 2>&1)"; then
	printf '%s\n' "$yes_out" >&2
	fail "-y update failed"
fi
if printf '%s\n' "$yes_out" | grep -q 'Update existing pi-stack checkout'; then
	fail "-y prompted before updating"
fi
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$next_seed_head" || fail "-y did not update the pi-stack checkout"
test ! -s "$install_log" || fail "-y reinstalled existing Pi packages"
test "$(git -C "$home2/.pi-stack/.plugins" rev-parse HEAD)" = "$initial_pstack_head" || fail "-y updated pstack"
if ! repeat_out="$(PATH="$fake_bin:$PATH" HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_INSTALL_LOG="$install_log" bash -s -- -y <"$root/install.sh" 2>&1)"; then
	printf '%s\n' "$repeat_out" >&2
	fail "repeated -y update failed"
fi
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$next_seed_head" || fail "repeated -y changed the pi-stack revision"
test ! -s "$install_log" || fail "repeated -y reinstalled existing Pi packages"

printf 'local\n' >"$home2/.pi-stack/local-history"
git -C "$home2/.pi-stack" add local-history
git -C "$home2/.pi-stack" -c user.email=t@t -c user.name=t commit -qm local
local_ahead_head="$(git -C "$home2/.pi-stack" rev-parse HEAD)"
if local_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	fail "-y accepted local pi-stack history"
fi
printf '%s\n' "$local_out" | grep -q 'has local commits' || fail "local-ahead failure was not useful"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$local_ahead_head" || fail "local-ahead history changed while update was refused"
git -C "$home2/.pi-stack" reset --hard -q "$next_seed_head"

printf 'local\n' >"$home2/.pi-stack/local-history"
git -C "$home2/.pi-stack" add local-history
git -C "$home2/.pi-stack" -c user.email=t@t -c user.name=t commit -qm local
diverged_local_head="$(git -C "$home2/.pi-stack" rev-parse HEAD)"
printf 'remote\n' >"$seed/remote-history"
git -C "$seed" add remote-history
git -C "$seed" -c user.email=t@t -c user.name=t commit -qm remote
diverged_seed_head="$(git -C "$seed" rev-parse HEAD)"
if diverged_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	fail "-y accepted diverged pi-stack history"
fi
printf '%s\n' "$diverged_out" | grep -q 'Could not fast-forward' || fail "diverged history failure was not useful"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$diverged_local_head" || fail "diverged history changed while update was refused"
git -C "$home2/.pi-stack" reset --hard -q "$diverged_seed_head"

git -C "$home2/.pi-stack" checkout --detach -q
detached_head="$(git -C "$home2/.pi-stack" rev-parse HEAD)"
if detached_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	fail "-y accepted a detached pi-stack checkout"
fi
printf '%s\n' "$detached_out" | grep -q 'is not on a branch' || fail "detached checkout failure was not useful"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$detached_head" || fail "detached checkout changed while update was refused"
git -C "$home2/.pi-stack" checkout -q "$managed_branch"

git -C "$home2/.pi-stack" branch --unset-upstream
missing_upstream_head="$(git -C "$home2/.pi-stack" rev-parse HEAD)"
if missing_upstream_out="$(HOME="$home2" PI_STACK_GIT="$seed_url" PSTACK_GIT="$pstack_url" PI_STACK_SKIP_PACKAGES=1 bash -s -- -y <"$root/install.sh" 2>&1)"; then
	fail "-y accepted a checkout without an upstream"
fi
printf '%s\n' "$missing_upstream_out" | grep -q 'has no upstream' || fail "missing upstream failure was not useful"
test "$(git -C "$home2/.pi-stack" rev-parse HEAD)" = "$missing_upstream_head" || fail "checkout without upstream changed while update was refused"
git -C "$home2/.pi-stack" branch --set-upstream-to="origin/$managed_branch" >/dev/null

streams_home="$tmp/home-streams"
streams_xdg="$tmp/streams-xdg"
streams_proj="$tmp/proj-root"
mkdir -p "$streams_home/.local/bin" "$streams_xdg" "$streams_proj"
printf 'old pi-web-cli\n' >"$streams_home/.local/bin/pi-web-cli"
cp "$streams_home/.local/bin/pi-web-cli" "$tmp/old-pi-web-cli"
set +e
streams_out="$(
	HOME="$streams_home" \
		XDG_CONFIG_HOME="$streams_xdg" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		PI_WEB_URL="http://127.0.0.1:9" \
		GIT_AUTHOR_NAME="Test" \
		GIT_AUTHOR_EMAIL="test@example.com" \
		GIT_COMMITTER_NAME="Test" \
		GIT_COMMITTER_EMAIL="test@example.com" \
		bash -s -- --project "$streams_proj" -y \
		--pi-web-url "http://127.0.0.1:9" \
		--coordinator-model "acme/widget" \
		--coordinator-thinking "low" <"$root/install.sh" 2>&1
)"
streams_status=$?
set -e
[[ "$streams_status" -eq 1 ]] || fail "install --project exited $streams_status, expected 1 because pi-web is unreachable"
printf '%s\n' "$streams_out" | grep -F -q 'FAIL pi-web: list failed' || fail "doctor did not fail because pi-web is unreachable"
if printf '%s\n' "$streams_out" | grep -F -q '[none]:'; then
	fail "-y asked a setup question"
fi
printf '%s\n' "$streams_out" | grep -F -q "Backed up $streams_home/.local/bin/pi-web-cli to " || fail "install did not report the pi-web-cli backup"
mapfile -t pi_web_cli_baks < <(find "$streams_home/.local/bin" -maxdepth 1 -name 'pi-web-cli.bak-*' -print)
[[ "${#pi_web_cli_baks[@]}" -eq 1 ]] || fail "expected one pi-web-cli backup, found ${#pi_web_cli_baks[@]}"
basename "${pi_web_cli_baks[0]}" | grep -Eq '^pi-web-cli\.bak-[0-9]{8}-[0-9]{6}$' || fail "pi-web-cli backup name is not a UTC timestamp"
cmp -s "$tmp/old-pi-web-cli" "${pi_web_cli_baks[0]}" || fail "pi-web-cli backup does not match the previous file"
cmp -s "$root/bin/pi-web-cli" "$streams_home/.local/bin/pi-web-cli" || fail "pi-web-cli was not replaced with the checkout copy"
test ! -e "$streams_home/.config/systemd/user/pi-streams-tick.service" || fail "tick units ignored XDG_CONFIG_HOME"
test ! -e "$streams_home/.pi/agent/auth.json" || fail "install --project wrote auth.json"
streams_index="$streams_xdg/pi-streams"
streams_toml="$streams_index/projects/proj-root.toml"
test -f "$streams_toml" || fail "project file was not created"
test ! -e "$streams_proj/streams/.git" || fail "project streams directory is a git repo"
test ! -e "$streams_index/.git" || fail "the index is a git repo"
grep -F -q 'http://127.0.0.1:9' "$streams_toml" || fail "pi-web url was not recorded"
grep -F -q 'acme/widget' "$streams_toml" || fail "coordinator model was not recorded"
[[ "$(grep -c 'thinking = "low"' "$streams_toml")" -eq 2 ]] || fail "coordinator thinking was not recorded"
if grep -F -q 'remote = ' "$streams_toml"; then
	fail "project file recorded a remote"
fi
assert_streams_layout "$streams_home" "$streams_xdg"
streams_home_sum="$(tree_checksum "$streams_home")"
streams_xdg_sum="$(tree_checksum "$streams_xdg")"
streams_toml_sum="$(sha256sum "$streams_toml")"
set +e
streams_again="$(
	HOME="$streams_home" \
		XDG_CONFIG_HOME="$streams_xdg" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		PI_WEB_URL="http://127.0.0.1:9" \
		GIT_AUTHOR_NAME="Test" \
		GIT_AUTHOR_EMAIL="test@example.com" \
		GIT_COMMITTER_NAME="Test" \
		GIT_COMMITTER_EMAIL="test@example.com" \
		bash -s -- --project "$streams_proj" -y \
		--pi-web-url "http://127.0.0.1:9" \
		--coordinator-model "acme/widget" \
		--coordinator-thinking "low" <"$root/install.sh" 2>&1
)"
streams_again_status=$?
set -e
[[ "$streams_again_status" -eq 1 ]] || fail "second install --project exited $streams_again_status, expected 1"
if printf '%s\n' "$streams_again" | grep -F -q 'Backed up '; then
	fail "second install backed up pi-web-cli again"
fi
[[ "$(tree_checksum "$streams_home")" == "$streams_home_sum" ]] || fail "second install --project changed the home"
[[ "$(tree_checksum "$streams_xdg")" == "$streams_xdg_sum" ]] || fail "second install --project changed the systemd units"
[[ "$(sha256sum "$streams_toml")" == "$streams_toml_sum" ]] || fail "second install --project changed the project file"
[[ "$(find "$streams_home/.local/bin" -maxdepth 1 -name 'pi-web-cli.bak-*' | wc -l)" -eq 1 ]] || fail "second install created another pi-web-cli backup"

same_home="$tmp/home-same-cli"
mkdir -p "$same_home/.local/bin"
register_streams_home "$same_home"
cp "$root/bin/pi-web-cli" "$same_home/.local/bin/pi-web-cli"
chmod +x "$same_home/.local/bin/pi-web-cli"
same_inode="$(stat -c %i "$same_home/.local/bin/pi-web-cli")"
if ! same_out="$(HOME="$same_home" PI_STACK="$root" PSTACK="$stub" PI_STACK_SKIP_PACKAGES=1 bash "$root/install.sh" 2>&1)"; then
	printf '%s\n' "$same_out" >&2
	fail "install left an identical pi-web-cli and then failed"
fi
[[ "$(stat -c %i "$same_home/.local/bin/pi-web-cli")" == "$same_inode" ]] || fail "install rewrote an identical pi-web-cli"
test -z "$(find "$same_home/.local/bin" -name 'pi-web-cli.bak-*' -print)" || fail "install backed up an identical pi-web-cli"
if printf '%s\n' "$same_out" | grep -F -q 'Backed up '; then
	fail "install reported a backup of an identical pi-web-cli"
fi

fake_npm="$tmp/fake-npm"
mkdir -p "$fake_npm"
cat >"$fake_npm/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
printf '%s\n' "$*" >>"$NPM_LOG"
if [[ "$*" == "install -g @jmfederico/pi-web --allow-scripts=node-pty" ]]; then
	mkdir -p "${HOME}/.local/bin"
	cat >"${HOME}/.local/bin/pi-web" <<'PIWEB'
#!/bin/sh
printf '%s\n' "$*" >>"$PI_WEB_LOG"
PIWEB
	chmod +x "${HOME}/.local/bin/pi-web"
	exit 0
fi
printf 'unexpected npm %s\n' "$*" >&2
exit 1
EOF
chmod +x "$fake_npm/npm"
unused_home="$tmp/home-streams-unused"
unused_log="$tmp/npm-unused.log"
: >"$unused_log"
if ! unused_out="$(
	env -u PI_STACK_SKIP_SYSTEMD \
		PATH="$fake_npm:$no_systemctl:/usr/bin:/bin" \
		HOME="$unused_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		NPM_LOG="$unused_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$unused_out" >&2
	fail "install without a pi-streams home failed"
fi
if printf '%s\n' "$unused_out" | grep -F -q 'npm install -g @jmfederico/pi-web'; then
	fail "install without a pi-streams home offered to install pi-web"
fi
test ! -s "$unused_log" || fail "install without a pi-streams home ran npm"
assert_streams_not_in_use "$unused_home"

noweb_home="$tmp/home-noweb"
register_streams_home "$noweb_home"
noweb_log="$tmp/npm-noweb.log"
: >"$noweb_log"
if ! noweb_out="$(
	PATH="$fake_npm:$no_systemctl:/usr/bin:/bin" \
		HOME="$noweb_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		NPM_LOG="$noweb_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$noweb_out" >&2
	fail "install without pi-web failed while packages were skipped"
fi
printf '%s\n' "$noweb_out" | grep -F -x -q 'npm install -g @jmfederico/pi-web --allow-scripts=node-pty' || fail "install did not say how to install pi-web"
printf '%s\n' "$noweb_out" | grep -F -x -q 'pi-web install' || fail "install did not say how to start pi-web"
test ! -s "$noweb_log" || fail "skipped package install still ran npm"
test ! -e "$noweb_home/.local/bin/pi-web" || fail "skipped package install wrote pi-web"

npm_home="$tmp/home-npm-web"
register_streams_home "$npm_home"
npm_log="$tmp/npm-web.log"
pi_web_log="$tmp/pi-web.log"
: >"$npm_log"
: >"$pi_web_log"
if ! npm_out="$(
	PATH="$fake_npm:$fake_bin:$no_systemctl:/usr/bin:/bin" \
		HOME="$npm_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=0 \
		PI_INSTALL_LOG="$tmp/npm-web-pi.log" \
		NPM_LOG="$npm_log" \
		PI_WEB_LOG="$pi_web_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$npm_out" >&2
	fail "install did not install a missing pi-web"
fi
printf '%s\n' "$npm_out" | grep -F -x -q 'npm install -g @jmfederico/pi-web --allow-scripts=node-pty' || fail "install did not print the pi-web install command"
[[ "$(cat "$npm_log")" == "install -g @jmfederico/pi-web --allow-scripts=node-pty" ]] || fail "npm was not run as pi-web's README says"
test -x "$npm_home/.local/bin/pi-web" || fail "npm install did not put pi-web on the home bin path"
[[ "$(cat "$pi_web_log")" == "install" ]] || fail "install did not run pi-web install"
if ! npm_again="$(
	PATH="$fake_npm:$fake_bin:$no_systemctl:/usr/bin:/bin" \
		HOME="$npm_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=0 \
		PI_INSTALL_LOG="$tmp/npm-web-pi-again.log" \
		NPM_LOG="$npm_log" \
		PI_WEB_LOG="$pi_web_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$npm_again" >&2
	fail "second install with pi-web present failed"
fi
[[ "$(cat "$npm_log")" == "install -g @jmfederico/pi-web --allow-scripts=node-pty" ]] || fail "second install ran npm again"
[[ "$(cat "$pi_web_log")" == "install" ]] || fail "second install ran pi-web install again"
if printf '%s\n' "$npm_again" | grep -F -q 'npm install -g @jmfederico/pi-web'; then
	fail "second install printed the pi-web install command after pi-web was present"
fi

node_home="$tmp/home-piweb-node"
register_streams_home "$node_home"
node_log="$tmp/npm-node.log"
: >"$node_log"
node_pi_web="$node_home/.local/share/pi-node/node-fixture/bin/pi-web"
mkdir -p "$(dirname "$node_pi_web")"
printf '#!/bin/sh\nexit 0\n' >"$node_pi_web"
chmod +x "$node_pi_web"
if ! node_out="$(
	PATH="$fake_npm:$no_systemctl:/usr/bin:/bin" \
		HOME="$node_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		NPM_LOG="$node_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$node_out" >&2
	fail "install did not accept pi-web under pi-node"
fi
if printf '%s\n' "$node_out" | grep -F -q 'npm install -g @jmfederico/pi-web'; then
	fail "install tried to install pi-web that was already under pi-node"
fi
test ! -s "$node_log" || fail "install ran npm even though pi-web was under pi-node"

no_node_path="$tmp/no-node-path"
mkdir -p "$no_node_path"
cp -s -n /usr/bin/* /bin/* "$no_node_path"/ 2>/dev/null || true
rm -f "$no_node_path/node" "$no_node_path/nodejs" "$no_node_path/npm" "$no_node_path/npx"
test -x "$no_node_path/bash" || fail "could not build a PATH without node"

pinode_home="$tmp/home-pinode-npm"
register_streams_home "$pinode_home"
pinode_bin="$pinode_home/.local/share/pi-node/node-fixture/bin"
mkdir -p "$pinode_bin"
printf '#!/bin/sh\nexit 0\n' >"$pinode_bin/node"
cat >"$pinode_bin/npm" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
here="$(cd "$(dirname "$0")" && pwd)"
[[ "$(command -v node)" == "$here/node" ]] || { printf 'npm ran without its node on PATH\n' >&2; exit 1; }
printf '%s\n' "$*" >>"$NPM_LOG"
cat >"$here/pi-web" <<'PIWEB'
#!/usr/bin/env bash
[[ "$(command -v node)" == "$(cd "$(dirname "$0")" && pwd)/node" ]] || { printf 'pi-web ran without its node on PATH\n' >&2; exit 1; }
printf '%s\n' "$*" >>"$PI_WEB_LOG"
PIWEB
chmod +x "$here/pi-web"
EOF
chmod +x "$pinode_bin/node" "$pinode_bin/npm"
pinode_npm_log="$tmp/npm-pinode.log"
pinode_web_log="$tmp/pi-web-pinode.log"
: >"$pinode_npm_log"
: >"$pinode_web_log"
if ! pinode_out="$(
	PATH="$fake_bin:$no_systemctl:$no_node_path" \
		HOME="$pinode_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=0 \
		PI_INSTALL_LOG="$tmp/npm-pinode-pi.log" \
		NPM_LOG="$pinode_npm_log" \
		PI_WEB_LOG="$pinode_web_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$pinode_out" >&2
	fail "install did not install pi-web with the npm under pi-node"
fi
[[ "$(cat "$pinode_npm_log")" == "install -g @jmfederico/pi-web --allow-scripts=node-pty" ]] || fail "install did not run the npm under pi-node"
[[ "$(cat "$pinode_web_log")" == "install" ]] || fail "install did not run pi-web install with its node on PATH"

nonpm_home="$tmp/home-no-npm"
register_streams_home "$nonpm_home"
if nonpm_out="$(
	PATH="$fake_bin:$no_systemctl:$no_node_path" \
		HOME="$nonpm_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=0 \
		PI_INSTALL_LOG="$tmp/no-npm-pi.log" \
		bash "$root/install.sh" 2>&1
)"; then
	fail "install without npm exited 0"
fi
printf '%s\n' "$nonpm_out" | grep -F -x -q 'npm is not on PATH or under ~/.local/share/pi-node. Install Node.js, then run the two commands above.' || fail "install without npm did not say how to get it"

fake_systemctl="$tmp/fake-systemctl"
mkdir -p "$fake_systemctl"
cat >"$fake_systemctl/systemctl" <<'EOF'
#!/bin/sh
printf '%s\n' "$*" >>"$SYSTEMCTL_LOG"
EOF
chmod +x "$fake_systemctl/systemctl"
systemd_home="$tmp/home-systemd"
register_streams_home "$systemd_home"
systemctl_log="$tmp/systemctl.log"
: >"$systemctl_log"
if ! systemd_out="$(
	env -u PI_STACK_SKIP_SYSTEMD \
		PATH="$fake_systemctl:/usr/bin:/bin" \
		HOME="$systemd_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		SYSTEMCTL_LOG="$systemctl_log" \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$systemd_out" >&2
	fail "install with systemctl failed"
fi
[[ "$(cat "$systemctl_log")" == $'--user daemon-reload\n--user enable --now pi-streams-tick.timer' ]] || fail "install did not reload systemd and enable the tick timer"
assert_streams_layout "$systemd_home"

no_systemd_path="$tmp/no-systemd-path"
mkdir -p "$no_systemd_path"
cp -s -n /usr/bin/* /bin/* "$no_systemd_path"/ 2>/dev/null || true
rm -f "$no_systemd_path/systemctl"
test -x "$no_systemd_path/bash" || fail "could not build a PATH without systemctl"
no_systemd_home="$tmp/home-no-systemd"
register_streams_home "$no_systemd_home"
if ! no_systemd_out="$(
	env -u PI_STACK_SKIP_SYSTEMD \
		PATH="$no_systemd_path" \
		HOME="$no_systemd_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		bash "$root/install.sh" 2>&1
)"; then
	printf '%s\n' "$no_systemd_out" >&2
	fail "install without systemctl failed"
fi
printf '%s\n' "$no_systemd_out" | grep -F -x -q 'systemctl not found. Run pi-streams tick every five minutes another way.' || fail "install without systemctl did not say how to run the tick"
assert_streams_layout "$no_systemd_home"

ask_home="$tmp/home-streams-ask"
ask_proj="$tmp/ask-proj"
mkdir -p "$ask_home/.config/pi-web" "$ask_proj"
printf '%s\n' '{"host":"127.0.0.1","port":9}' >"$ask_home/.config/pi-web/config.json"
cp "$ask_home/.config/pi-web/config.json" "$tmp/pi-web-config.before"
cat >"$tmp/run-streams-tty.py" <<'PY'
import errno
import os
import pty
import select
import signal
import sys
import time

argv = sys.argv[1:]
pid, terminal = pty.fork()
if pid == 0:
    os.execvp(argv[0], argv)

output = bytearray()
sent = 0
deadline = time.time() + 60
status = None
while time.time() < deadline:
    ready, _, _ = select.select([terminal], [], [], 0.5)
    if ready:
        try:
            chunk = os.read(terminal, 4096)
        except OSError as error:
            if error.errno != errno.EIO:
                raise
            chunk = b""
        if chunk:
            output.extend(chunk)
            prompts = output.count(b"]: ")
            if prompts > sent:
                os.write(terminal, b"\n" * (prompts - sent))
                sent = prompts
            continue
    waited, code = os.waitpid(pid, os.WNOHANG)
    if waited:
        status = code
        break
else:
    os.kill(pid, signal.SIGKILL)
    os.waitpid(pid, 0)
    sys.stdout.buffer.write(output)
    raise SystemExit("installer prompt did not finish")

while True:
    try:
        chunk = os.read(terminal, 4096)
    except OSError:
        break
    if not chunk:
        break
    output.extend(chunk)

sys.stdout.buffer.write(output)
if status is None:
    _, status = os.waitpid(pid, 0)
if os.WIFEXITED(status):
    raise SystemExit(os.WEXITSTATUS(status))
raise SystemExit(128 + os.WTERMSIG(status))
PY
set +e
ask_out="$(
	HOME="$ask_home" \
		PI_STACK="$root" \
		PSTACK="$stub" \
		PI_STACK_SKIP_PACKAGES=1 \
		PI_WEB_URL="http://127.0.0.1:9" \
		GIT_AUTHOR_NAME="Test" \
		GIT_AUTHOR_EMAIL="test@example.com" \
		GIT_COMMITTER_NAME="Test" \
		GIT_COMMITTER_EMAIL="test@example.com" \
		python3 "$tmp/run-streams-tty.py" bash "$root/install.sh" --project "$ask_proj" 2>&1
)"
ask_status=$?
set -e
[[ "$ask_status" -eq 1 ]] || fail "install --project without -y exited $ask_status, expected 1"
printf '%s\n' "$ask_out" | grep -F -q 'Which URL do you open pi-web at? [http://127.0.0.1:9]:' || fail "url question did not show its default"
printf '%s\n' "$ask_out" | grep -F -q 'Which model should coordinators use? [openai-codex/gpt-6-astra]:' || fail "model question did not show its default"
printf '%s\n' "$ask_out" | grep -F -q 'Which thinking level should coordinators use? [xhigh]:' || fail "thinking question did not show its default"
printf '%s\n' "$ask_out" | grep -F -q 'FAIL pi-web: list failed' || fail "doctor did not fail after the setup questions"
ask_toml="$ask_home/.config/pi-streams/projects/ask-proj.toml"
test -f "$ask_toml" || fail "answering the setup questions did not write the project file"
grep -F -q 'http://127.0.0.1:9' "$ask_toml" || fail "accepted url default was not recorded"
if grep -F -q 'remote = ' "$ask_toml"; then
	fail "accepted setup recorded a remote"
fi
grep -F -q 'openai-codex/gpt-6-astra' "$ask_toml" || fail "accepted model default was not recorded"
cmp -s "$ask_home/.config/pi-web/config.json" "$tmp/pi-web-config.before" || fail "install changed pi-web config.json"
test ! -e "$ask_home/.pi/agent/auth.json" || fail "install without -y wrote auth.json"

if grep -R -E '/home/[^$]|workspace root' -- install.sh overlay skills/cross-repo skills/update-pstack | grep -v '^Binary'; then
	fail "hardcoded home path or workspace root in overlay files"
fi

echo "check-overlay ok"

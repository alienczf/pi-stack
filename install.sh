#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'EOF'
usage: install.sh

Copies the pi-stack overlay into $HOME/.pi/agent.
Rewrites Cursor skill names into $HOME/.pi/agent/skills-pstack. Does not edit pstack.
Merges defaultTools, skills, and packages into settings.json.
Installs npm:pi-web-access, npm:pi-hashline-edit, and npm:pi-subagents when pi is on PATH.
Never writes auth.json, models-store.json, private/, or sessions/.
Does not search for git repositories. Fit a repo later with jig.sh.

If PI_STACK is unset and this script is not in a checkout, uses
$HOME/.pi-stack. Clones alienczf/pi-stack there when overlay/ is missing.
If PSTACK is unset, uses $PI_STACK/.plugins/pstack. Clones cursor/plugins
(sparse, pstack only) into $PI_STACK/.plugins when that tree is missing.
Neither clone is refreshed on a later run.

Environment
  HOME          install target (default is your home)
  PI_STACK      pi-stack checkout with overlay/APPEND_SYSTEM.md
  PI_STACK_GIT  git URL for that clone (default https://github.com/alienczf/pi-stack.git)
  PSTACK        pstack tree with skills/poteto-mode/SKILL.md
  PSTACK_GIT    git URL for the clone (default https://github.com/cursor/plugins.git)
  PI_STACK_SKIP_PACKAGES  if 1, write package names only, do not run pi install
EOF
}

case "${1:-}" in
	-h | --help)
		usage
		exit 0
		;;
	"")
		;;
	*)
		usage >&2
		exit 2
		;;
esac

src="${BASH_SOURCE[0]:-}"
here=""
if [[ -n "$src" && -f "$src" ]]; then
	here="$(cd "$(dirname "$src")" && pwd)"
fi

default_pi_stack="${HOME}/.pi-stack"
pi_stack_git="${PI_STACK_GIT:-https://github.com/alienczf/pi-stack.git}"
if [[ -n "${PI_STACK:-}" ]]; then
	pi_stack="$PI_STACK"
elif [[ -n "$here" && -f "$here/overlay/APPEND_SYSTEM.md" ]]; then
	pi_stack="$here"
else
	pi_stack="$default_pi_stack"
fi

# ponytail: skip clone when overlay exists; git pull when you want a newer tree
if [[ ! -f "$pi_stack/overlay/APPEND_SYSTEM.md" ]]; then
	if [[ -e "$pi_stack" ]]; then
		if [[ ! -d "$pi_stack" ]]; then
			printf '%s exists and is not a directory. Set PI_STACK or remove it.\n' "$pi_stack" >&2
			exit 1
		fi
		if [[ -d "$pi_stack/.git" || -n "$(ls -A "$pi_stack")" ]]; then
			printf '%s exists and is not a pi-stack checkout. Set PI_STACK or remove it.\n' "$pi_stack" >&2
			exit 1
		fi
	fi
	if ! command -v git >/dev/null 2>&1; then
		printf 'git is required to clone pi-stack into %s, or set PI_STACK\n' "$pi_stack" >&2
		exit 1
	fi
	git clone --depth 1 "$pi_stack_git" "$pi_stack"
fi
if [[ ! -f "$pi_stack/overlay/APPEND_SYSTEM.md" ]]; then
	printf 'PI_STACK=%s has no overlay/APPEND_SYSTEM.md\n' "$pi_stack" >&2
	exit 1
fi
pi_stack="$(cd "$pi_stack" && pwd)"
if [[ "$here" != "$pi_stack" ]]; then
	exec bash "$pi_stack/install.sh"
fi

overlay="$here/overlay"

plugins_root="$pi_stack/.plugins"
default_pstack="${plugins_root}/pstack"
pstack_git="${PSTACK_GIT:-https://github.com/cursor/plugins.git}"
pstack="${PSTACK:-}"
if [[ -z "$pstack" ]]; then
	if [[ -f "${default_pstack}/skills/poteto-mode/SKILL.md" ]]; then
		pstack="$default_pstack"
	else
		if [[ -e "$plugins_root" && ! -d "$plugins_root/.git" ]]; then
			printf '%s exists and is not a git clone. Set PSTACK or remove it.\n' "$plugins_root" >&2
			exit 1
		fi
		if ! command -v git >/dev/null 2>&1; then
			printf 'git is required to clone pstack into %s, or set PSTACK\n' "$plugins_root" >&2
			exit 1
		fi
		if [[ ! -d "$plugins_root/.git" ]]; then
			git clone --depth 1 --filter=blob:none --sparse "$pstack_git" "$plugins_root"
		fi
		git -C "$plugins_root" sparse-checkout set pstack
		pstack="$default_pstack"
	fi
fi
if [[ ! -f "$pstack/skills/poteto-mode/SKILL.md" ]]; then
	printf 'PSTACK=%s has no skills/poteto-mode/SKILL.md\n' "$pstack" >&2
	exit 1
fi

agent="${HOME}/.pi/agent"
mkdir -p "$agent/prompts" "$agent/bin"

install_md() {
	local src="$1" dest="$2"
	PSTACK="$pstack" python3 - "$src" "$dest" <<'PY'
import os
import sys
from pathlib import Path

src = Path(sys.argv[1])
dest = Path(sys.argv[2])
text = src.read_text().replace("__PSTACK__", os.environ["PSTACK"])
if dest.exists() and dest.read_text() == text:
	sys.exit(0)
dest.parent.mkdir(parents=True, exist_ok=True)
dest.write_text(text)
PY
}

install_md "$overlay/APPEND_SYSTEM.md" "$agent/APPEND_SYSTEM.md"
install_md "$overlay/AGENTS.md" "$agent/AGENTS.md"
for src in "$here/prompts"/*.md; do
	install_md "$src" "$agent/prompts/$(basename "$src")"
done

if [[ -x "$here/bin/jig.sh" ]]; then
	wrapper="$agent/bin/jig"
	wanted=$'#!/usr/bin/env bash\nexec '"$here/bin/jig.sh"$' "$@"\n'
	if [[ ! -f "$wrapper" ]] || [[ "$(cat "$wrapper")" != "$wanted" ]]; then
		printf '%s' "$wanted" >"$wrapper"
	fi
	chmod +x "$wrapper"
fi

conform_out="${agent}/skills-pstack"
mkdir -p "$conform_out"
conform_src=()
for name in poteto-mode how why architect interrogate tdd unslop technical-writing figure-it-out show-me-your-work reflect create-verification-skill; do
	if [[ -f "$pstack/skills/$name/SKILL.md" ]]; then
		conform_src+=("$pstack/skills/$name")
	fi
done
for name in jig cross-repo; do
	if [[ -f "$here/skills/$name/SKILL.md" ]]; then
		conform_src+=("$here/skills/$name")
	fi
done
if [[ ${#conform_src[@]} -gt 0 ]]; then
	python3 "$here/bin/conform-skills.py" --out "$conform_out" "${conform_src[@]}"
fi

export PI_AGENT_DIR="$agent"
python3 - <<'PY'
import json
import os
import sys
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
path = agent / "settings.json"
conformed = agent / "skills-pstack"

tools = ["read", "write", "edit", "bash", "grep", "find", "ls"]
wanted = [
	"poteto-mode",
	"how",
	"why",
	"architect",
	"interrogate",
	"tdd",
	"unslop",
	"technical-writing",
	"figure-it-out",
	"show-me-your-work",
	"reflect",
	"create-verification-skill",
	"jig",
	"cross-repo",
]
skills = [str((conformed / n).resolve()) for n in wanted if (conformed / n / "SKILL.md").is_file()]
if len(skills) > 14:
	sys.exit("skills allowlist grew past 14")

if path.exists():
	data = json.loads(path.read_text())
	if not isinstance(data, dict):
		sys.exit("settings.json is not an object")
else:
	data = {}

data["defaultTools"] = tools
data["skills"] = skills

def npm_unscoped_name(entry):
	if isinstance(entry, str):
		s = entry
	elif isinstance(entry, dict):
		s = entry.get("source") or ""
	else:
		return None
	if not isinstance(s, str) or not s.startswith("npm:"):
		return None
	rest = s[4:]
	if rest.startswith("@"):
		return None
	return rest.split("@", 1)[0]

packages = data.get("packages")
if packages is None:
	packages = []
if not isinstance(packages, list):
	sys.exit("settings.json packages is not an array")

by_name = {}
for i, pkg in enumerate(packages):
	name = npm_unscoped_name(pkg)
	if name:
		by_name[name] = i

web = "pi-web-access"
web_entry = {"source": "npm:pi-web-access", "skills": ["!skills/librarian/**"]}
if web not in by_name:
	packages.append(web_entry)
else:
	existing = packages[by_name[web]]
	if isinstance(existing, str):
		packages[by_name[web]] = web_entry
	elif isinstance(existing, dict) and "skills" not in existing:
		updated = dict(existing)
		updated["skills"] = ["!skills/librarian/**"]
		packages[by_name[web]] = updated

hashedit = "pi-hashline-edit"
if hashedit not in by_name:
	packages.append("npm:pi-hashline-edit")

subs = "pi-subagents"
if subs not in by_name:
	packages.append("npm:pi-subagents")

data["packages"] = packages
text = json.dumps(data, indent=2) + "\n"
if path.exists() and path.read_text() == text:
	sys.exit(0)
tmp = path.with_name("settings.json.pi-stack-tmp")
tmp.write_text(text)
tmp.replace(path)
PY

if [[ "${PI_STACK_SKIP_PACKAGES:-}" != 1 ]]; then
	if command -v pi >/dev/null 2>&1; then
		npm_root="${agent}/npm/node_modules"
		for spec in pi-web-access pi-hashline-edit pi-subagents; do
			if [[ ! -d "${npm_root}/${spec}" ]]; then
				PI_CODING_AGENT_DIR="$agent" pi install "npm:${spec}"
			fi
		done
	else
		printf 'pi not on PATH. After installing pi, run:\n  pi install npm:pi-web-access\n  pi install npm:pi-hashline-edit\n  pi install npm:pi-subagents\n'
	fi
fi

cat <<'EOF'
pi-stack is installed for this user.
Fit a repo with a jig:
  cd /path/to/repo && jig.sh
or inside Pi:
  /skill:jig
EOF

#!/usr/bin/env bash
set -euo pipefail

usage() {
	cat <<'EOF'
usage: install.sh

Copies the pi-stack overlay into $HOME/.pi/agent.
Writes pstack-aligned user agents into $HOME/.pi/agent/agents/.
Dated backups go to $HOME/.pi/agent/backups/subagents/.
Rewrites Cursor skill names into $HOME/.pi/agent/skills-pstack. Does not edit pstack.
Merges defaultTools, skills, and packages into settings.json.
Finds pi on PATH or under ~/.local/share/pi-node and installs
npm:pi-web-access, npm:pi-hashline-edit, npm:pi-subagents, and
npm:@narumitw/pi-goal.
Creates pi-goal.json with unlimited automatic turns when that file is absent.
Rewrites cursor/* subagent models to inherit. Links jig into ~/.local/bin.
Never writes auth.json, models-store.json, private/, or sessions/.
Does not search for git repositories. Fit a repo later with jig.

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

if ! command -v python3 >/dev/null 2>&1; then
	printf 'python3 is required\n' >&2
	exit 1
fi

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
required_packages=(
	pi-web-access
	pi-hashline-edit
	pi-subagents
	@narumitw/pi-goal
)

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

mkdir -p "${HOME}/.local/bin"
if [[ -x "$agent/bin/jig" ]]; then
	ln -sfn "$agent/bin/jig" "${HOME}/.local/bin/jig"
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
python3 - "${required_packages[@]}" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
path = agent / "settings.json"
conformed = agent / "skills-pstack"
required_packages = sys.argv[1:]

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
if "defaultProjectTrust" not in data:
	data["defaultProjectTrust"] = "always"

def is_cursor_model(value):
	return isinstance(value, str) and (value == "cursor" or value.startswith("cursor/"))

subs = data.get("subagents")
if isinstance(subs, dict):
	if is_cursor_model(subs.get("defaultModel")):
		subs["defaultModel"] = "inherit"
	overrides = subs.get("agentOverrides")
	if isinstance(overrides, dict):
		for spec in overrides.values():
			if isinstance(spec, dict) and is_cursor_model(spec.get("model")):
				spec["model"] = "inherit"
	data["subagents"] = subs

def npm_package_name(entry):
	if isinstance(entry, str):
		source = entry
	elif isinstance(entry, dict):
		source = entry.get("source") or ""
	else:
		return None
	if not isinstance(source, str) or not source.startswith("npm:"):
		return None
	rest = source[4:]
	if rest.startswith("@"):
		slash = rest.find("/")
		if slash < 2:
			return None
		version = rest.find("@", slash + 1)
		return rest if version == -1 else rest[:version]
	name = rest.split("@", 1)[0]
	return name or None

packages = data.get("packages")
if packages is None:
	packages = []
if not isinstance(packages, list):
	sys.exit("settings.json packages is not an array")

by_name = {}
for i, package in enumerate(packages):
	name = npm_package_name(package)
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

for package in required_packages:
	if package != web and package not in by_name:
		packages.append(f"npm:{package}")

data["packages"] = packages
text = json.dumps(data, indent=2) + "\n"
if not path.exists() or path.read_text() != text:
	tmp = path.with_name("settings.json.pi-stack-tmp")
	tmp.write_text(text)
	tmp.replace(path)

goal_settings = agent / "pi-goal.json"
if not goal_settings.exists() and not goal_settings.is_symlink():
	goal_text = json.dumps({
		"continuationLimits": {"automaticTurns": None, "noProgressTurns": 3}
	}, indent=2) + "\n"
	with tempfile.NamedTemporaryFile("w", dir=agent, prefix=".pi-goal.", delete=False) as tmp:
		tmp.write(goal_text)
		goal_tmp = Path(tmp.name)
	try:
		os.link(goal_tmp, goal_settings)
	except FileExistsError:
		pass
	finally:
		goal_tmp.unlink(missing_ok=True)
PY

resolve_pi() {
	if command -v pi >/dev/null 2>&1; then
		command -v pi
		return 0
	fi
	local pi_bins=()
	local saved
	saved="$(shopt -p nullglob || true)"
	shopt -s nullglob
	pi_bins=("${HOME}/.local/bin/pi" "${HOME}/.local/share/pi-node"/node-*/bin/pi)
	eval "$saved"
	local c
	for c in "${pi_bins[@]}"; do
		if [[ -x "$c" ]]; then
			printf '%s\n' "$c"
			return 0
		fi
	done
	return 1
}

npm_root="${agent}/npm/node_modules"

if [[ "${PI_STACK_SKIP_PACKAGES:-}" != 1 ]]; then
	if pi_bin="$(resolve_pi)"; then
		for spec in "${required_packages[@]}"; do
			if [[ ! -d "${npm_root}/${spec}" ]]; then
				PI_CODING_AGENT_DIR="$agent" "$pi_bin" install "npm:${spec}"
			fi
			if [[ ! -d "${npm_root}/${spec}" ]]; then
				printf 'pi install npm:%s did not write %s/%s\n' "$spec" "$npm_root" "$spec" >&2
				exit 1
			fi
		done
	else
		printf 'pi is not installed. Install Pi, then rerun this script:\n  curl -fsSL https://pi.dev/install.sh | sh\n' >&2
		exit 1
	fi
fi

goal_manifest="${npm_root}/@narumitw/pi-goal/package.json"
if [[ -f "$goal_manifest" ]]; then
	python3 - "$goal_manifest" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
data = json.loads(path.read_text())
if data.get("name") != "@narumitw/pi-goal":
	raise SystemExit(f"pi-goal package identity mismatch in {path}")
PY
	python3 - "$agent/prompts/goal.md" <<'PY'
import hashlib
import sys
from pathlib import Path

path = Path(sys.argv[1])
legacy_sha256 = "c17b0e11552afcc0de0fb894ec8f63ba036cce54afb31f3db79ad64c92b9275a"
if path.is_symlink():
	print(f"{path} is not the generated pi-stack goal prompt; keeping it.", file=sys.stderr)
elif path.is_file():
	if hashlib.sha256(path.read_bytes()).hexdigest() == legacy_sha256:
		path.unlink()
	else:
		print(f"{path} is not the generated pi-stack goal prompt; keeping it.", file=sys.stderr)
elif path.exists():
	print(f"{path} is not a regular file; keeping it.", file=sys.stderr)
PY
elif [[ "${PI_STACK_SKIP_PACKAGES:-}" != 1 ]]; then
	printf 'pi-goal package manifest is missing: %s\n' "$goal_manifest" >&2
	exit 1
fi

export PSTACK="$pstack"
export OVERLAY="$overlay"
export PI_AGENT_DIR="$agent"
python3 - <<'PY'
import os
from datetime import datetime, timezone
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
overlay_agents = Path(os.environ["OVERLAY"]) / "agents"
pstack = os.environ["PSTACK"]
skills_pstack = str(agent / "skills-pstack")
dest_dir = agent / "agents"
pkg_dir = agent / "npm" / "node_modules" / "pi-subagents" / "agents"
backup_root = agent / "backups/subagents"

existing = []
if backup_root.is_dir():
	existing = [p.read_bytes() for p in backup_root.rglob("*") if p.is_file()]

pending_backups = []
pending_writes = []
for src in sorted(overlay_agents.glob("*.md")):
	name = src.stem
	wanted = src.read_text().replace("__SKILLS_PSTACK__", skills_pstack).replace("__PSTACK__", pstack)
	dest = dest_dir / (name + ".md")
	if dest.exists():
		if dest.read_text() != wanted:
			pending_backups.append((name + ".md", dest.read_bytes()))
			pending_writes.append((dest, wanted))
	else:
		pending_writes.append((dest, wanted))
	pkg = pkg_dir / (name + ".md")
	if pkg.is_file():
		original = pkg.read_bytes()
		if original not in existing:
			pending_backups.append(("package/" + name + ".md", original))
			existing.append(original)

if pending_backups:
	stamp = backup_root / datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
	stamp.mkdir(parents=True)
	for rel, data in pending_backups:
		out = stamp / rel
		out.parent.mkdir(parents=True, exist_ok=True)
		out.write_bytes(data)

for dest, text in pending_writes:
	if dest.exists() and dest.read_text() == text:
		continue
	dest.parent.mkdir(parents=True, exist_ok=True)
	dest.write_text(text)
PY

skill_n=0
if [[ -d "$conform_out" ]]; then
	skill_n="$(find "$conform_out" -mindepth 2 -maxdepth 2 -name SKILL.md | wc -l | tr -d ' ')"
fi
if [[ "${PI_STACK_SKIP_PACKAGES:-}" == 1 ]]; then
	pkg_msg="names merged, pi install skipped"
else
	package_list="$(printf ', %s' "${required_packages[@]}")"
	pkg_msg="${package_list:2}"
fi
cat <<EOF
pi-stack is installed for this user.
  overlay   ${agent}
  agents    ${agent}/agents
  backups   ${agent}/backups/subagents
  skills    ${skill_n}
  packages  ${pkg_msg}
  jig       ${HOME}/.local/bin/jig
Fit a repo:
  cd /path/to/repo && jig
or inside Pi:
  /skill:jig
EOF

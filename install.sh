#!/usr/bin/env bash
set -euo pipefail

pstack_skill_names=(
	poteto-mode
	how
	why
	architect
	interrogate
	tdd
	unslop
	technical-writing
	figure-it-out
	show-me-your-work
	reflect
	create-verification-skill
	maintain-verification-skill
)

usage() {
	cat <<'EOF'
usage: install.sh [-y | --print-pstack-skills]

Copies the pi-stack overlay into $HOME/.pi/agent.
Installs poteto-agent and retires the six old role profiles in $HOME/.pi/agent/agents/.
Disables builtin agents. Existing children keep their prompts until respawn.
Dated backups go to $HOME/.pi/agent/backups/subagents/.
Rewrites Cursor skill names into $HOME/.pi/agent/skills-pstack. Does not edit pstack.
Copies the Jig launcher, controller, skill, and references into $HOME/.pi/agent/jig/.
Copies the pstack updater command and controller into $HOME/.pi/agent/update-pstack/.
Merges defaultTools, skills, and packages into settings.json without changing project trust.
Finds pi on PATH or under ~/.local/share/pi-node and installs
npm:pi-web-access, npm:pi-hashline-edit, and npm:pi-subagents.
Rewrites cursor/* subagent models to inherit. Links jig and update-pstack into ~/.local/bin.
Never writes auth.json, models-store.json, private/, or sessions/.
Does not search for git repositories. Initialize one Git root later with jig init.

If PI_STACK is unset and this script has no adjacent checkout, uses
$HOME/.pi-stack. Clones alienczf/pi-stack there when overlay/ is missing.
A bootstrap invocation prompts before fast-forwarding that existing checkout.
If PSTACK is unset, uses $PI_STACK/.plugins/pstack. Clones cursor/plugins
(sparse, pstack only) into $PI_STACK/.plugins when that tree is missing.
A later install does not refresh pstack. Use update-pstack after reviewing upstream changes.

Options
  -y            update the bootstrap-selected default checkout without prompting
  --print-pstack-skills  print the pstack skill roots selected by pi-stack

Environment
  HOME          install target (default is your home)
  PI_STACK      pi-stack checkout with overlay/APPEND_SYSTEM.md
  PI_STACK_GIT  git URL for that clone (default https://github.com/alienczf/pi-stack.git)
  PSTACK        pstack tree with skills/poteto-mode/SKILL.md
  PSTACK_GIT    git URL for the clone (default https://github.com/cursor/plugins.git)
  PI_STACK_SKIP_PACKAGES  if 1, write package names only, do not run pi install
EOF
}

update_managed_pi_stack() {
	local checkout="$1"
	local checkout_status branch upstream current_revision upstream_revision
	if ! command -v git >/dev/null 2>&1; then
		printf 'git is required to update %s\n' "$checkout" >&2
		return 1
	fi
	if [[ ! -d "$checkout/.git" ]]; then
		printf '%s is not an installer-managed Git checkout. Set PI_STACK to use it without updates.\n' "$checkout" >&2
		return 1
	fi
	if ! checkout_status="$(git -C "$checkout" status --short --untracked-files=no)"; then
		printf 'Could not inspect %s before updating it.\n' "$checkout" >&2
		return 1
	fi
	if [[ -n "$checkout_status" ]]; then
		printf '%s has tracked or staged changes. Commit or discard them before updating.\n' "$checkout" >&2
		return 1
	fi
	if ! branch="$(git -C "$checkout" symbolic-ref --quiet --short HEAD)"; then
		printf '%s is not on a branch. Check out its tracked branch before updating.\n' "$checkout" >&2
		return 1
	fi
	if ! upstream="$(git -C "$checkout" rev-parse --abbrev-ref --symbolic-full-name '@{upstream}' 2>/dev/null)"; then
		printf 'Branch %s in %s has no upstream. Configure one before updating.\n' "$branch" "$checkout" >&2
		return 1
	fi
	if ! git -C "$checkout" fetch --prune; then
		printf 'Could not fetch the upstream for %s.\n' "$checkout" >&2
		return 1
	fi
	if ! git -C "$checkout" merge --ff-only "$upstream"; then
		printf 'Could not fast-forward %s to %s. Resolve the checkout before retrying.\n' "$checkout" "$upstream" >&2
		return 1
	fi
	if ! current_revision="$(git -C "$checkout" rev-parse HEAD)" || ! upstream_revision="$(git -C "$checkout" rev-parse "$upstream")"; then
		printf 'Could not verify the upstream revision for %s.\n' "$checkout" >&2
		return 1
	fi
	if [[ "$current_revision" != "$upstream_revision" ]]; then
		printf '%s has local commits. Reset it to %s before updating.\n' "$checkout" "$upstream" >&2
		return 1
	fi
}

update_decision="ask"
case "${1:-}" in
	-h | --help)
		usage
		exit 0
		;;
	-y)
		update_decision="yes"
		;;
	--print-pstack-skills)
		if [[ $# -ne 1 ]]; then
			usage >&2
			exit 2
		fi
		printf '%s\n' "${pstack_skill_names[@]}"
		exit 0
		;;
	"")
		;;
	*)
		usage >&2
		exit 2
		;;
esac
if [[ $# -gt 1 ]]; then
	usage >&2
	exit 2
fi

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
	source_kind="explicit"
elif [[ -n "$here" && -f "$here/overlay/APPEND_SYSTEM.md" ]]; then
	pi_stack="$here"
	source_kind="checkout"
else
	pi_stack="$default_pi_stack"
	source_kind="bootstrap"
fi

if [[ "$source_kind" == "bootstrap" && -f "$pi_stack/overlay/APPEND_SYSTEM.md" ]]; then
	if [[ "$update_decision" == "ask" ]]; then
		if { exec 3<>/dev/tty; } 2>/dev/null; then
			while [[ "$update_decision" == "ask" ]]; do
				printf 'Update existing pi-stack checkout at %s? [y/N] ' "$pi_stack" >&3
				if ! IFS= read -r answer <&3; then
					answer=""
				fi
				case "$answer" in
					y | Y) update_decision="yes" ;;
					"" | n | N) update_decision="no" ;;
					*) printf 'Enter y or n.\n' >&3 ;;
				esac
			done
			exec 3>&-
		else
			printf 'Existing pi-stack checkout not updated. Rerun with -y to update %s.\n' "$pi_stack" >&2
			update_decision="no"
		fi
	fi
	if [[ "$update_decision" == "yes" ]]; then
		update_managed_pi_stack "$pi_stack" || exit 1
	fi
fi

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
for name in "${pstack_skill_names[@]}"; do
	if [[ ! -f "$pstack/skills/$name/SKILL.md" ]]; then
		printf 'PSTACK=%s is missing selected skill root: %s\n' "$pstack" "$name" >&2
		exit 1
	fi
done

agent="${HOME}/.pi/agent"
mkdir -p "$agent/prompts" "$agent/bin"
installed_jig="$agent/jig"
installed_update="$agent/update-pstack"
export PI_STACK_SOURCE_ROOT="$here"
export PI_STACK_INSTALLED_JIG="$installed_jig"
export PI_STACK_INSTALLED_UPDATE="$installed_update"
python3 - <<'PY'
import os
import shutil
from pathlib import Path

source = Path(os.environ["PI_STACK_SOURCE_ROOT"])

def sync(destination: Path, relative_files: list[Path]) -> None:
    wanted = {path.as_posix() for path in relative_files}
    destination.mkdir(parents=True, exist_ok=True)
    for current in sorted(destination.rglob("*"), reverse=True):
        relative = current.relative_to(destination).as_posix()
        if current.is_symlink() or current.is_file():
            if relative not in wanted:
                current.unlink()
        elif current.is_dir() and not any(current.iterdir()):
            current.rmdir()
    for relative in relative_files:
        src = source / relative
        dest = destination / relative
        dest.parent.mkdir(parents=True, exist_ok=True)
        data = src.read_bytes()
        if dest.is_symlink() or (dest.exists() and not dest.is_file()):
            if dest.is_dir():
                shutil.rmtree(dest)
            else:
                dest.unlink()
        if not dest.exists() or dest.read_bytes() != data:
            dest.write_bytes(data)
        dest.chmod(src.stat().st_mode & 0o777)

jig_files = [Path("bin/jig.sh"), Path("bin/jigctl.py")]
jig_files.extend(
    path.relative_to(source)
    for path in sorted((source / "skills/jig").rglob("*"))
    if path.is_file() and "__pycache__" not in path.parts
)
sync(Path(os.environ["PI_STACK_INSTALLED_JIG"]), jig_files)
sync(
    Path(os.environ["PI_STACK_INSTALLED_UPDATE"]),
    [Path("bin/update-pstack"), Path("bin/pstackctl.py")],
)
PY

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

if [[ -x "$installed_jig/bin/jig.sh" ]]; then
	wrapper="$agent/bin/jig"
	wanted=$'#!/usr/bin/env bash\nset -euo pipefail\nagent_dir="${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-${HOME}/.pi/agent}}"\nexec "$agent_dir/jig/bin/jig.sh" "$@"\n'
	if [[ ! -f "$wrapper" ]] || [[ "$(cat "$wrapper")" != "$wanted" ]]; then
		printf '%s' "$wanted" >"$wrapper"
	fi
	chmod +x "$wrapper"
fi
if [[ -x "$installed_update/bin/update-pstack" ]]; then
	wrapper="$agent/bin/update-pstack"
	printf -v source_root '%q' "$here"
	printf -v agent_root '%q' "$agent"
	wanted=$(printf '#!/usr/bin/env bash\nset -euo pipefail\ndefault_pi_stack=%s\ndefault_agent=%s\nexport PI_STACK="${PI_STACK:-$default_pi_stack}"\nagent_dir="${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$default_agent}}"\nexec "$agent_dir/update-pstack/bin/update-pstack" "$@"\n' "$source_root" "$agent_root")
	if [[ ! -f "$wrapper" ]] || [[ "$(cat "$wrapper")" != "$wanted" ]]; then
		printf '%s' "$wanted" >"$wrapper"
	fi
	chmod +x "$wrapper"
fi

mkdir -p "${HOME}/.local/bin"
for name in jig update-pstack; do
	if [[ -x "$agent/bin/$name" ]]; then
		ln -sfn "$agent/bin/$name" "${HOME}/.local/bin/$name"
	fi
done

conform_out="${agent}/skills-pstack"
mkdir -p "$conform_out"
conform_src=()
for name in "${pstack_skill_names[@]}"; do
	conform_src+=("$pstack/skills/$name")
done
for name in cross-repo update-pstack; do
	if [[ -f "$here/skills/$name/SKILL.md" ]]; then
		conform_src+=("$here/skills/$name")
	fi
done
conform_src+=("$installed_jig/skills/jig")
if [[ ${#conform_src[@]} -gt 0 ]]; then
	python3 "$here/bin/conform-skills.py" --out "$conform_out" "${conform_src[@]}"
fi

export PI_AGENT_DIR="$agent"
export OVERLAY="$overlay"
python3 - "${#pstack_skill_names[@]}" "${pstack_skill_names[@]}" "${required_packages[@]}" <<'PY'
import json
import os
import sys
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
path = agent / "settings.json"
conformed = agent / "skills-pstack"
pstack_skill_count = int(sys.argv[1])
pstack_skills = sys.argv[2 : 2 + pstack_skill_count]
required_packages = sys.argv[2 + pstack_skill_count :]

tools = ["read", "write", "edit", "bash", "grep", "find", "ls"]
wanted = [*pstack_skills, "jig", "cross-repo", "update-pstack"]
missing_skills = [name for name in wanted if not (conformed / name / "SKILL.md").is_file()]
if missing_skills:
	sys.exit(f"conformed skills are missing: {', '.join(missing_skills)}")
skills = [str((conformed / name).resolve()) for name in wanted]

if path.exists():
	data = json.loads(path.read_text())
	if not isinstance(data, dict):
		sys.exit("settings.json is not an object")
else:
	data = {}

data["defaultTools"] = tools
data["skills"] = skills

def is_cursor_model(value):
	return isinstance(value, str) and (value == "cursor" or value.startswith("cursor/"))

policy = json.loads((Path(os.environ["OVERLAY"]) / "settings.json").read_text())["subagents"]
subs = data.setdefault("subagents", {})
overrides = subs.setdefault("agentOverrides", {})
if is_cursor_model(subs.get("defaultModel")):
	subs["defaultModel"] = "inherit"
for name, spec in overrides.items():
	if is_cursor_model(spec.get("model")):
		spec["model"] = "inherit"
	spec["disabled"] = name != "poteto-agent"
subs["disableBuiltins"] = policy["disableBuiltins"]
for name, spec in policy["agentOverrides"].items():
	overrides.setdefault(name, {}).update(spec)

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

packages = [entry for entry in packages if npm_package_name(entry) != "@narumitw/pi-goal"]
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

export PSTACK="$pstack"
export OVERLAY="$overlay"
export PI_AGENT_DIR="$agent"
python3 - <<'PY'
import json
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
pending_deletes = []
policy = json.loads((overlay_agents.parent / "settings.json").read_text())["subagents"]
retired = [name for name, spec in policy["agentOverrides"].items() if spec["disabled"]]
for name in retired:
	dest = dest_dir / (name + ".md")
	if dest.is_file():
		pending_backups.append((name + ".md", dest.read_bytes()))
		pending_deletes.append(dest)
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
for name in [*retired, *(src.stem for src in overlay_agents.glob("*.md"))]:
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

for dest in pending_deletes:
	dest.unlink()

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
  pstack    ${HOME}/.local/bin/update-pstack
  controller ${installed_jig}/bin/jigctl.py
Configure one Git repository:
  cd /path/to/repo && jig init
Or use the current trusted Pi session:
  /skill:jig init
  /jig init
EOF

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
	correct
	create-verification-skill
	maintain-verification-skill
)

usage() {
	cat <<'EOF'
usage: install.sh [-y] [--project <root>] [--pi-web-url <url>] [--remote <url>]
                  [--coordinator-model <provider/id>] [--coordinator-thinking <level>]
                  [--print-pstack-skills]

Copies the pi-stack overlay into $HOME/.pi/agent.
Installs poteto-agent and retires the six old role profiles in $HOME/.pi/agent/agents/.
Disables builtin agents, the subagent intercom bridge, and intercom notifications.
Existing children keep their prompts until respawn.
Dated backups go to $HOME/.pi/agent/backups/subagents/.
Rewrites Cursor skill names into $HOME/.pi/agent/skills-pstack. Does not edit pstack.
Copies the pstack updater command and controller into $HOME/.pi/agent/update-pstack/.
Merges defaultTools, skills, and packages into settings.json without changing project trust.
Finds pi on PATH or under ~/.local/share/pi-node and installs
npm:pi-web-access and npm:pi-subagents.
Removes retired npm registrations and managed installs; backs up changed settings.
PI_STACK_SKIP_PACKAGES=1 defers physical package removal until a normal install.
Rewrites cursor/* subagent models to inherit. Links update-pstack into ~/.local/bin.
Links pi-streams to this checkout. Installs the stream and stream-kickoff skills
and the stream prompt. With --project, or once pi-streams has a registered home,
also installs pi-web-cli into ~/.local/bin, pi-web when it is missing, and the
tick timer. With --project, runs pi-streams init and then pi-streams doctor.
Never writes auth.json, models-store.json, private/, or sessions/.
Does not change pi-web's config. Does not search for git repositories.

If PI_STACK is unset and this script has no adjacent checkout, uses
$HOME/.pi-stack. Clones alienczf/pi-stack there when overlay/ is missing.
A bootstrap invocation prompts before fast-forwarding that existing checkout.
If PSTACK is unset, uses $PI_STACK/.plugins/pstack. Clones cursor/plugins
(sparse, pstack only) into $PI_STACK/.plugins when that tree is missing.
A later install does not refresh pstack. Use update-pstack after reviewing upstream changes.

Options
  -y            update the bootstrap-selected default checkout without prompting,
                and accept the pi-streams setup defaults
  --project <root>
                after install, run pi-streams init on this project root
  --pi-web-url <url>
                pi-web address to record for the project home
  --remote <url>
                private remote for the project home
  --coordinator-model <provider/id>
                model coordinators use
  --coordinator-thinking <level>
                thinking level coordinators use
  --print-pstack-skills  print the pstack skill roots selected by pi-stack

Environment
  HOME          install target (default is your home)
  PI_STACK      pi-stack checkout with overlay/APPEND_SYSTEM.md
  PI_STACK_GIT  git URL for that clone (default https://github.com/alienczf/pi-stack.git)
  PSTACK        pstack tree with skills/poteto-mode/SKILL.md
  PSTACK_GIT    git URL for the clone (default https://github.com/cursor/plugins.git)
  PI_STACK_SKIP_PACKAGES  if 1, write package names only, do not run pi install or npm install -g pi-web
  PI_STACK_SKIP_SYSTEMD   if 1, copy the tick units and do not run systemctl
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
original_args=("$@")
assume_yes=0
print_skills=0
have_project=0
project_root=""
have_pi_web_url=0
pi_web_url=""
have_remote=0
project_remote=""
have_coordinator_model=0
coordinator_model=""
have_coordinator_thinking=0
coordinator_thinking=""

if [[ "${1:-}" == "-h" || "${1:-}" == "--help" ]]; then
	usage
	exit 0
fi

require_value() {
	if [[ $# -lt 2 || -z "${2:-}" || "${2:-}" == -* ]]; then
		usage >&2
		exit 2
	fi
}

while [[ $# -gt 0 ]]; do
	case "$1" in
	-y)
		update_decision="yes"
		assume_yes=1
		shift
		;;
	--print-pstack-skills)
		print_skills=1
		shift
		;;
	--project)
		require_value "$@"
		project_root="$2"
		have_project=1
		shift 2
		;;
	--pi-web-url)
		require_value "$@"
		pi_web_url="$2"
		have_pi_web_url=1
		shift 2
		;;
	--remote)
		require_value "$@"
		project_remote="$2"
		have_remote=1
		shift 2
		;;
	--coordinator-model)
		require_value "$@"
		coordinator_model="$2"
		have_coordinator_model=1
		shift 2
		;;
	--coordinator-thinking)
		require_value "$@"
		coordinator_thinking="$2"
		have_coordinator_thinking=1
		shift 2
		;;
	*)
		usage >&2
		exit 2
		;;
	esac
done

if [[ "$print_skills" == 1 ]]; then
	if [[ "$assume_yes" == 1 || "$have_project" == 1 || "$have_pi_web_url" == 1 || "$have_remote" == 1 || "$have_coordinator_model" == 1 || "$have_coordinator_thinking" == 1 ]]; then
		usage >&2
		exit 2
	fi
	printf '%s\n' "${pstack_skill_names[@]}"
	exit 0
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
	exec bash "$pi_stack/install.sh" "${original_args[@]}"
fi

overlay="$here/overlay"
required_packages=(
	pi-web-access
	pi-subagents
)
retired_packages=(pi-hashline-edit pi-gal @narumitw/pi-goal)
export PI_STACK_RETIRED_PACKAGES="${retired_packages[*]}"

plugins_root="$pi_stack/.plugins"
default_pstack="${plugins_root}/pstack"
pstack_git="${PSTACK_GIT:-https://github.com/cursor/plugins.git}"
pstack="${PSTACK:-}"
pstack_existed=0
if [[ -n "$pstack" ]]; then
	pstack_existed=1
fi
if [[ -z "$pstack" ]]; then
	if [[ -f "${default_pstack}/skills/poteto-mode/SKILL.md" ]]; then
		pstack="$default_pstack"
		pstack_existed=1
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
		if [[ "$pstack_existed" == 1 ]]; then
			printf 'PSTACK=%s predates selected skill %s. Update it on the reviewed path with /update-pstack in pi, or update-pstack status and the apply command it plans, then rerun the installer.\n' "$pstack" "$name" >&2
		else
			printf 'PSTACK=%s is missing selected skill root: %s\n' "$pstack" "$name" >&2
		fi
		exit 1
	fi
done

agent="${HOME}/.pi/agent"
mkdir -p "$agent/prompts" "$agent/bin"
installed_update="$agent/update-pstack"
export PI_STACK_SOURCE_ROOT="$here"
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

link_pi_streams() {
	local dest="${HOME}/.local/bin/pi-streams"
	local target="$here/bin/pi-streams"
	mkdir -p "${HOME}/.local/bin"
	if [[ -L "$dest" && "$(readlink -- "$dest")" == "$target" ]]; then
		return 0
	fi
	ln -sfn "$target" "$dest"
}

install_pi_web_cli() {
	local src="$here/bin/pi-web-cli"
	local dest="${HOME}/.local/bin/pi-web-cli"
	mkdir -p "${HOME}/.local/bin"
	if [[ -e "$dest" || -L "$dest" ]]; then
		if cmp -s "$src" "$dest"; then
			return 0
		fi
		local stamp backup
		stamp="$(date -u +%Y%m%d-%H%M%S)"
		backup="${dest}.bak-${stamp}"
		if [[ -e "$backup" || -L "$backup" ]]; then
			backup="${backup}-$$"
		fi
		mv -- "$dest" "$backup"
		printf 'Backed up %s to %s\n' "$dest" "$backup"
	fi
	cp -- "$src" "$dest"
	chmod +x "$dest"
}

copy_if_changed() {
	local src="$1" dest="$2"
	if [[ -f "$dest" && ! -L "$dest" ]] && cmp -s "$src" "$dest"; then
		return 0
	fi
	mkdir -p "$(dirname "$dest")"
	if [[ -e "$dest" || -L "$dest" ]]; then
		rm -rf -- "$dest"
	fi
	cp -- "$src" "$dest"
}

install_tick_units() {
	local unit_dir="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
	local name
	for name in pi-streams-tick.service pi-streams-tick.timer; do
		copy_if_changed "$here/systemd/$name" "$unit_dir/$name"
	done
	if [[ "${PI_STACK_SKIP_SYSTEMD:-}" == 1 ]]; then
		return 0
	fi
	if ! command -v systemctl >/dev/null 2>&1; then
		printf 'systemctl not found. Run pi-streams tick every five minutes another way.\n'
		return 0
	fi
	systemctl --user daemon-reload
	systemctl --user enable --now pi-streams-tick.timer
}

resolve_pi_web() {
	if command -v pi-web >/dev/null 2>&1; then
		command -v pi-web
		return 0
	fi
	local bins=()
	local saved
	saved="$(shopt -p nullglob || true)"
	shopt -s nullglob
	bins=("${HOME}/.local/bin/pi-web" "${HOME}/.local/share/pi-node"/node-*/bin/pi-web)
	eval "$saved"
	local c
	for c in "${bins[@]}"; do
		if [[ -x "$c" ]]; then
			printf '%s\n' "$c"
			return 0
		fi
	done
	return 1
}

ensure_pi_web() {
	if resolve_pi_web >/dev/null; then
		return 0
	fi
	printf 'npm install -g @jmfederico/pi-web\n'
	if [[ "${PI_STACK_SKIP_PACKAGES:-}" == 1 ]]; then
		return 0
	fi
	npm install -g @jmfederico/pi-web
	if ! resolve_pi_web >/dev/null; then
		printf 'npm install -g @jmfederico/pi-web did not put pi-web on PATH\n' >&2
		return 1
	fi
}

run_project_setup() {
	local cmd=("${HOME}/.local/bin/pi-streams" init "$project_root")
	if [[ "$have_pi_web_url" == 1 ]]; then
		cmd+=(--pi-web-url "$pi_web_url")
	fi
	if [[ "$have_remote" == 1 ]]; then
		cmd+=(--remote "$project_remote")
	fi
	if [[ "$have_coordinator_model" == 1 ]]; then
		cmd+=(--coordinator-model "$coordinator_model")
	fi
	if [[ "$have_coordinator_thinking" == 1 ]]; then
		cmd+=(--coordinator-thinking "$coordinator_thinking")
	fi
	if [[ "$assume_yes" == 1 ]]; then
		cmd+=(-y)
	fi
	"${cmd[@]}"
	"${HOME}/.local/bin/pi-streams" doctor
}

install_md "$overlay/APPEND_SYSTEM.md" "$agent/APPEND_SYSTEM.md"
install_md "$overlay/AGENTS.md" "$agent/AGENTS.md"
for src in "$here/prompts"/*.md; do
	install_md "$src" "$agent/prompts/$(basename "$src")"
done

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
for name in update-pstack; do
	if [[ -x "$agent/bin/$name" ]]; then
		ln -sfn "$agent/bin/$name" "${HOME}/.local/bin/$name"
	fi
done
streams_homes="${XDG_CONFIG_HOME:-$HOME/.config}/pi-streams/homes"
streams_in_use=0
if [[ "$have_project" == 1 ]] || { [[ -f "$streams_homes" ]] && grep -q '[^[:space:]]' "$streams_homes"; }; then
	streams_in_use=1
fi
link_pi_streams
if [[ "$streams_in_use" == 1 ]]; then
	install_pi_web_cli
fi

conform_out="${agent}/skills-pstack"
mkdir -p "$conform_out"
conform_src=()
for name in "${pstack_skill_names[@]}"; do
	conform_src+=("$pstack/skills/$name")
done
for name in cross-repo update-pstack stream stream-kickoff; do
	if [[ -f "$here/skills/$name/SKILL.md" ]]; then
		conform_src+=("$here/skills/$name")
	fi
done
if [[ ${#conform_src[@]} -gt 0 ]]; then
	python3 "$here/bin/conform-skills.py" --out "$conform_out" "${conform_src[@]}"
fi

# A link is an earlier install only when it points at the launcher or into the jig tree.
legacy_jig=(
	"dir $agent/jig"
	"file $agent/bin/jig"
	"link ${HOME}/.local/bin/jig"
	"file $agent/prompts/jig.md"
	"dir $agent/skills-pstack/jig"
)
legacy_jig_artifact() {
	local kind="$1" path="$2" target resolved
	case "$kind" in
		dir)
			[[ -d "$path" && ! -L "$path" ]]
			;;
		file)
			[[ -f "$path" && ! -L "$path" ]]
			;;
		link)
			[[ -L "$path" ]] || return 1
			target="$(readlink -- "$path")"
			case "$target" in
				"$agent/bin/jig"|"$agent/jig"|"$agent/jig"/*) return 0 ;;
			esac
			resolved="$(readlink -f -- "$path" 2>/dev/null || true)"
			case "$resolved" in
				"$agent/bin/jig"|"$agent/jig"|"$agent/jig"/*) return 0 ;;
			esac
			return 1
			;;
		*)
			return 1
			;;
	esac
}
removed_jig_paths=()
for entry in "${legacy_jig[@]}"; do
	kind="${entry%% *}"
	path="${entry#* }"
	legacy_jig_artifact "$kind" "$path" || continue
	rm -rf -- "$path"
	removed_jig_paths+=("$path")
done
if [[ ${#removed_jig_paths[@]} -gt 0 ]]; then
	PI_STACK_REMOVED_JIG="$(printf '%s\n' "${removed_jig_paths[@]}")"
else
	PI_STACK_REMOVED_JIG=""
fi
export PI_STACK_REMOVED_JIG

export PI_AGENT_DIR="$agent"
export OVERLAY="$overlay"
python3 - "${#pstack_skill_names[@]}" "${pstack_skill_names[@]}" "${required_packages[@]}" <<'PY'
import json
import os
import sys
import tempfile
from pathlib import Path

agent = Path(os.environ["PI_AGENT_DIR"])
path = agent / "settings.json"
conformed = agent / "skills-pstack"
pstack_skill_count = int(sys.argv[1])
pstack_skills = sys.argv[2 : 2 + pstack_skill_count]
required_packages = sys.argv[2 + pstack_skill_count :]

tools = ["read", "write", "edit", "bash", "grep", "find", "ls"]
wanted = [*pstack_skills, "cross-repo", "update-pstack", "stream", "stream-kickoff"]
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

def is_legacy_jig_skill(entry):
	if not isinstance(entry, str):
		return False
	text = entry.rstrip("/")
	if text.endswith("/skills-pstack/jig"):
		return True
	jig_root = (agent / "jig").resolve()
	candidate = Path(text)
	if not candidate.is_absolute():
		candidate = Path.cwd() / candidate
	candidate = candidate.resolve()
	return candidate == jig_root or jig_root in candidate.parents

existing_skills = data.get("skills", [])
removed_jig_skills = []
extras = []
if isinstance(existing_skills, list):
	for entry in existing_skills:
		if is_legacy_jig_skill(entry):
			removed_jig_skills.append(entry)
		elif entry not in skills:
			extras.append(entry)
data["skills"] = [*skills, *extras]

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

retired = set(os.environ["PI_STACK_RETIRED_PACKAGES"].split())
kept_packages = [entry for entry in packages if npm_package_name(entry) not in retired]
if kept_packages != packages or removed_jig_skills:
	backup_dir = agent / "backups/packages"
	backup_dir.mkdir(parents=True, exist_ok=True)
	with tempfile.NamedTemporaryFile("w", dir=backup_dir, prefix="settings-", suffix=".json", delete=False) as backup:
		backup.write(path.read_text())
packages = kept_packages

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

config_path = agent / "extensions/subagent/config.json"
original = config_path.read_text() if config_path.exists() else None
config = json.loads(original) if original is not None else {}
if not isinstance(config, dict):
	sys.exit("subagent config.json is not an object")
bridge = config.setdefault("intercomBridge", {})
control = config.setdefault("control", {})
if not isinstance(bridge, dict) or not isinstance(control, dict):
	sys.exit("subagent intercomBridge and control must be objects")
bridge["mode"] = "off"
control["notifyChannels"] = ["event", "async"]
config_text = json.dumps(config, indent=2) + "\n"
if original != config_text:
	if original is not None:
		backup_dir = agent / "backups/subagents"
		backup_dir.mkdir(parents=True, exist_ok=True)
		with tempfile.NamedTemporaryFile("w", dir=backup_dir, prefix="config-", suffix=".json", delete=False) as backup:
			backup.write(original)
	config_path.parent.mkdir(parents=True, exist_ok=True)
	with tempfile.NamedTemporaryFile("w", dir=config_path.parent, prefix=".config-", delete=False) as tmp:
		tmp.write(config_text)
		config_tmp = Path(tmp.name)
	try:
		config_tmp.replace(config_path)
	finally:
		config_tmp.unlink(missing_ok=True)

removed = [line for line in os.environ.get("PI_STACK_REMOVED_JIG", "").splitlines() if line]
if removed_jig_skills:
	removed.append("settings.json skills: " + ", ".join(str(entry) for entry in removed_jig_skills))
if removed:
	print("Removed earlier Jig install: " + ", ".join(removed))

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
		retired_installed="$(python3 - "$npm_root" <<'PY'
import json
import os
import sys
from pathlib import Path
root = Path(sys.argv[1])
manifest = root.parent / "package.json"
data = json.loads(manifest.read_text()) if manifest.exists() else {}
for name in os.environ["PI_STACK_RETIRED_PACKAGES"].split():
	if (root / name).exists() or any(name in data.get(key, {}) for key in ("dependencies", "devDependencies", "optionalDependencies")):
		print(name)
PY
)"
		for spec in $retired_installed; do
			PI_CODING_AGENT_DIR="$agent" "$pi_bin" remove "npm:${spec}"
			python3 - "$npm_root" "$spec" <<'PY'
import json
import sys
from pathlib import Path
root, name = Path(sys.argv[1]), sys.argv[2]
manifest = root.parent / "package.json"
data = json.loads(manifest.read_text()) if manifest.exists() else {}
if (root / name).exists() or any(name in data.get(key, {}) for key in ("dependencies", "devDependencies", "optionalDependencies")):
	sys.exit(f"retired package remains after pi remove: {name}")
PY
		done
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
if [[ "$streams_in_use" == 1 ]]; then
	ensure_pi_web
	install_tick_units
fi
cat <<EOF
pi-stack is installed for this user.
  overlay   ${agent}
  agents    ${agent}/agents
  backups   ${agent}/backups/subagents
  skills    ${skill_n}
  packages  ${pkg_msg}
  pstack    ${HOME}/.local/bin/update-pstack
EOF
if [[ "$have_project" == 1 ]]; then
	run_project_setup
fi

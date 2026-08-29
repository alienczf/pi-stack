#!/usr/bin/env bash
set -euo pipefail

usage_error() {
	printf 'usage: jig init\n' >&2
	exit 2
}

[[ "$#" -eq 1 && "$1" == "init" ]] || usage_error

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
resource_root="${PI_STACK_ROOT:-$(cd "$here/.." && pwd)}"
controller="$resource_root/bin/jigctl.py"
skill="$resource_root/skills/jig/SKILL.md"
pi_bin="${PI:-pi}"
agent_dir="${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-${HOME}/.pi/agent}}"

[[ -f "$controller" && -f "$skill" ]] || {
	printf 'jig installation is incomplete\n' >&2
	exit 1
}

if ! repo="$(git rev-parse --show-toplevel 2>/dev/null)"; then
	printf 'jig init must run inside one Git repository\n' >&2
	exit 1
fi
repo="$(cd "$repo" && pwd)"
cd "$repo"

manifest_isolation() {
	python3 - <<'PY'
import json
from pathlib import Path
path = Path(".pi/jig/manifest.json")
if path.is_file():
    value = json.loads(path.read_text(encoding="utf-8"))
    print(value.get("resourceIsolation", ""))
PY
}

state_name() {
	python3 -c 'import json,sys; print(json.load(sys.stdin)["state"])'
}

existing_isolation="$(manifest_isolation)"
if [[ -n "$existing_isolation" && "$existing_isolation" != "isolated-shell" ]]; then
	printf 'This campaign records %s and cannot resume as isolated-shell.\n' "$existing_isolation" >&2
	printf 'Resume with /skill:jig init or /jig init in the trusted Pi session.\n' >&2
	exit 1
fi

if ! state="$(python3 "$controller" start --resource-isolation isolated-shell)"; then
	printf 'jig init could not start or resume the controller campaign\n' >&2
	exit 1
fi
printf '%s\n' "$state"
current_state="$(printf '%s' "$state" | state_name)"
if [[ "$current_state" == "initialized" ]]; then
	printf 'Jig initialized. The controller result above is terminal; no second step is available.\n'
	exit 0
fi

resource_args=()
if [[ -n "${PI_STACK_ROOT:-}" && -z "${JIG_SUBAGENTS_EXTENSION:-}" ]]; then
	resource_args+=(-p)
fi
resource_args+=(
	--no-approve
	--no-session
	--no-context-files
	--no-extensions
	--no-prompt-templates
	--no-skills
	--skill "$skill"
)
tool_list='read,grep,find,ls,bash,write,edit'
if [[ -n "${JIG_SUBAGENTS_EXTENSION:-}" || -z "${PI_STACK_ROOT:-}" ]]; then
	subagents_extension="${JIG_SUBAGENTS_EXTENSION:-$agent_dir/npm/node_modules/pi-subagents/index.ts}"
	if [[ ! -f "$subagents_extension" ]]; then
		printf 'jig installation is missing the trusted pi-subagents extension at %s\n' "$subagents_extension" >&2
		exit 1
	fi
	resource_args+=(
		--extension "$subagents_extension"
		--no-themes
		--system-prompt 'You are Pi in a human-started isolated Jig campaign. Load and follow the explicit Jig skill.'
		--append-system-prompt ''
	)
	tool_list+=',subagent,subagent_wait'
fi

prompt='Load the registered jig skill with the exact argument init. This is the isolated-shell campaign started by the human jig launcher. Use JIG_CONTROLLER for every controller operation. Continue through at most one terminal first-step result, or pause honestly at the current controller boundary.'
if [[ -n "${PI_STACK_ROOT:-}" && -z "${JIG_SUBAGENTS_EXTENSION:-}" ]]; then
	prompt+=' Submit the survey profile only through commit-profile.'
fi

set +e
JIG_CONTROLLER="$controller" \
JIG_RESOURCE_ISOLATION=isolated-shell \
"$pi_bin" \
	"${resource_args[@]}" \
	--tools "$tool_list" \
	-- "$prompt"
pi_status="$?"
set -e

if ! final_state="$(python3 "$controller" start --resource-isolation isolated-shell)"; then
	printf 'jig init could not validate the controller state after Pi exited\n' >&2
	exit 1
fi
printf '%s\n' "$final_state"
current_state="$(printf '%s' "$final_state" | state_name)"

if [[ "$current_state" == "initialized" && "$pi_status" -eq 0 ]]; then
	printf 'Jig initialized. The controller result above is terminal; no second step is available.\n'
	exit 0
fi

if [[ "$pi_status" -ne 0 ]]; then
	if [[ "$current_state" != failed-* && "$current_state" != "initialized" ]]; then
		reason="isolated Pi process exited with status $pi_status at $current_state"
		python3 "$controller" record-failure \
			--resource-isolation isolated-shell \
			--state "$current_state" \
			--reason "$reason" >/dev/null || {
			printf 'jig init could not record the incomplete Pi phase safely\n' >&2
			exit 1
		}
	fi
	printf 'jig init Pi phase failed with status %s\n' "$pi_status" >&2
	exit 1
fi

if [[ "$current_state" == "surveying" ]]; then
	python3 "$controller" record-failure \
		--resource-isolation isolated-shell \
		--state surveying \
		--reason 'isolated Pi process exited before committing a valid profile' >/dev/null
	printf 'jig init stopped before the awaiting-commandments boundary\n' >&2
	exit 1
fi

if [[ "$current_state" == "awaiting-commandments" ]]; then
	printf 'Jig is awaiting the target operator COMMANDMENTS response or explicit ratification decision.\n'
else
	printf 'Jig paused at %s. Resume with jig init.\n' "$current_state"
fi

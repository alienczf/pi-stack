#!/usr/bin/env bash
set -euo pipefail

usage_error() {
	printf 'usage: jig init\n' >&2
	exit 2
}

[[ "$#" -eq 1 && "$1" == "init" ]] || usage_error

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
pi_stack_root="${PI_STACK_ROOT:-$(cd "$here/.." && pwd)}"
controller="$pi_stack_root/bin/jigctl.py"
skill="$pi_stack_root/skills/jig/SKILL.md"
pi_bin="${PI:-pi}"

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

state="$(python3 "$controller" start --resource-isolation isolated-shell)"
printf '%s\n' "$state"
if [[ "$state" == *'"state": "awaiting-commandments"'* ]]; then
	printf 'Jig is awaiting the operator COMMANDMENTS interview and ratification.\n'
	exit 0
fi
if [[ "$state" != *'"state": "surveying"'* ]]; then
	printf 'jig controller returned an unsupported state\n' >&2
	exit 1
fi

prompt="Invoke /skill:jig init for the repository at the current working directory. The deterministic controller is $controller. It has committed the surveying boundary. Submit the profile only through: python3 $controller commit-profile --resource-isolation isolated-shell < PROFILE_JSON. Stop at awaiting-commandments. Do not infer, generate, or ratify COMMANDMENTS values."

set +e
"$pi_bin" \
	-p \
	--no-approve \
	--no-session \
	--no-context-files \
	--no-extensions \
	--no-prompt-templates \
	--no-skills \
	--skill "$skill" \
	--tools read,grep,find,ls,bash,write,edit \
	-- "$prompt"
pi_status="$?"
set -e

if ! final_state="$(python3 "$controller" start --resource-isolation isolated-shell)"; then
	printf 'jig init could not validate the controller state after Pi exited\n' >&2
	exit 1
fi

if [[ "$pi_status" -eq 0 && "$final_state" == *'"state": "awaiting-commandments"'* ]]; then
	printf '%s\n' "$final_state"
	printf 'Jig is awaiting the operator COMMANDMENTS interview and ratification.\n'
	exit 0
fi

if [[ "$final_state" == *'"state": "surveying"'* ]]; then
	if [[ "$pi_status" -eq 0 ]]; then
		reason='isolated Pi process exited before committing a valid profile'
	else
		reason="isolated Pi process exited with status $pi_status before init completed"
	fi
	if ! python3 "$controller" record-failure \
		--resource-isolation isolated-shell \
		--state surveying \
		--reason "$reason" >/dev/null; then
		printf 'jig init could not record the incomplete Pi phase safely\n' >&2
		exit 1
	fi
fi

if [[ "$pi_status" -ne 0 ]]; then
	printf 'jig init Pi phase failed with status %s\n' "$pi_status" >&2
else
	printf 'jig init stopped before the awaiting-commandments boundary\n' >&2
fi
exit 1

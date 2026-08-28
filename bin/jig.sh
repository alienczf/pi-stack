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

exec "$pi_bin" \
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

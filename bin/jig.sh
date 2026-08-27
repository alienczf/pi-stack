#!/usr/bin/env bash
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
PI_STACK_ROOT="${PI_STACK_ROOT:-$(cd "$here/.." && pwd)}"
skill="$PI_STACK_ROOT/skills/jig/SKILL.md"
PI="${PI:-pi}"
# Human launcher. Pin tools so this one-shot does not inherit a subagent fanout.

iterate=0
force=0
apply=0
for arg in "$@"; do
	case "$arg" in
		--iterate) iterate=1 ;;
		--force) force=1 ;;
		--apply) apply=1 ;;
		-h | --help)
			printf 'usage: jig.sh [--iterate|--force|--apply]\n'
			exit 0
			;;
		*)
			printf 'unknown flag: %s\n' "$arg" >&2
			exit 2
			;;
	esac
done

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
	printf 'cwd must be one git repo\n' >&2
	exit 1
fi
repo="$(git rev-parse --show-toplevel)"
cd "$repo"

if [[ "$iterate" -eq 0 && "$force" -eq 0 && "$apply" -eq 0 && -f "$repo/.pi/jig/interview.md" ]]; then
	printf 'already fitted. --iterate to refresh the refactor plan.\n'
	exit 0
fi

flagstr="none"
parts=()
[[ "$iterate" -eq 1 ]] && parts+=(--iterate)
[[ "$force" -eq 1 ]] && parts+=(--force)
[[ "$apply" -eq 1 ]] && parts+=(--apply)
if [[ ${#parts[@]} -gt 0 ]]; then
	flagstr="${parts[*]}"
fi

prompt="Read ${skill} in full, including references/interview.md, references/failure-modes.md, and references/lexicon-style.md. Then execute that skill in this git repo. Working tree: ${repo}. Flags: ${flagstr}. Do not git add, git commit, or git mv. Do not write .github/. Never apply refactor.md. Do not read private_key.pem, public_key.pem, .env, auth.json, or other key material."

exec "$PI" -p --approve --no-session --tools read,grep,find,ls,bash,write,edit "$prompt"

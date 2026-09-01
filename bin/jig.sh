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
create_skill="${JIG_CREATE_VERIFICATION_SKILL:-$agent_dir/skills-pstack/create-verification-skill/SKILL.md}"
if [[ ! -f "$create_skill" && -f "$resource_root/.plugins/pstack/skills/create-verification-skill/SKILL.md" ]]; then
	create_skill="$resource_root/.plugins/pstack/skills/create-verification-skill/SKILL.md"
fi

[[ -f "$controller" && -f "$skill" && -f "$create_skill" ]] || {
	printf 'jig installation is incomplete; controller, Jig skill, and create-verification-skill are required\n' >&2
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
import os
import stat

descriptors = []
try:
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    descriptor = os.open(".", os.O_RDONLY | directory | nofollow)
    descriptors.append(descriptor)
    try:
        for part in (".pi", "jig"):
            descriptor = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=descriptor)
            descriptors.append(descriptor)
        descriptor = os.open(
            "manifest.json",
            os.O_RDONLY | os.O_NONBLOCK | nofollow,
            dir_fd=descriptor,
        )
        descriptors.append(descriptor)
    except FileNotFoundError:
        raise SystemExit(0)
    metadata = os.fstat(descriptor)
    if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > 256 * 1024:
        raise SystemExit("jig manifest is not a bounded regular file")
    chunks = []
    total = 0
    while True:
        chunk = os.read(descriptor, min(65536, 256 * 1024 + 1 - total))
        if not chunk:
            break
        chunks.append(chunk)
        total += len(chunk)
        if total > 256 * 1024:
            raise SystemExit("jig manifest exceeds 262144 bytes")
    try:
        value = json.loads(b"".join(chunks).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise SystemExit("jig manifest is not valid UTF-8 JSON") from error
    if isinstance(value, dict):
        print(value.get("resourceIsolation", ""))
except OSError as error:
    raise SystemExit("jig manifest path is unsafe; preserve it and inspect its ancestors") from error
finally:
    for descriptor in reversed(descriptors):
        os.close(descriptor)
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
if [[ "$current_state" == "configured" ]]; then
	printf 'Jig configured this repository. Use /skill:maintain-verification-skill for later verification audits.\n'
	exit 0
fi

prompt='Load the registered jig skill with the exact argument init. This is the isolated-shell campaign started by the human jig launcher. Use JIG_CONTROLLER for every controller operation. Survey one Git root, obtain explicit repository Principles, run the registered create-verification-skill procedure, and stop at configured. Never change product code or choose an improvement.'

set +e
JIG_CONTROLLER="$controller" \
JIG_RESOURCE_ISOLATION=isolated-shell \
JIG_CREATE_VERIFICATION_SKILL="$create_skill" \
"$pi_bin" \
	--no-approve \
	--no-session \
	--no-context-files \
	--no-extensions \
	--no-prompt-templates \
	--no-skills \
	--skill "$skill" \
	--skill "$create_skill" \
	--no-themes \
	--system-prompt 'You are Pi in a human-started isolated Jig campaign. Follow the explicit Jig and create-verification skills.' \
	--append-system-prompt '' \
	--tools 'read,grep,find,ls,bash,write,edit' \
	-- "$prompt"
pi_status="$?"
set -e

if ! final_state="$(python3 "$controller" start --resource-isolation isolated-shell)"; then
	printf 'jig init could not validate the controller state after Pi exited\n' >&2
	exit 1
fi
printf '%s\n' "$final_state"
current_state="$(printf '%s' "$final_state" | state_name)"

if [[ "$current_state" == "configured" && "$pi_status" -eq 0 ]]; then
	printf 'Jig configured this repository. Use /skill:maintain-verification-skill for later verification audits.\n'
	exit 0
fi

if [[ "$pi_status" -ne 0 ]]; then
	if [[ "$current_state" != failed-* && "$current_state" != "configured" ]]; then
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
	printf 'jig init stopped before the repository Principles interview\n' >&2
	exit 1
fi

if [[ "$current_state" == "awaiting-principles" ]]; then
	printf 'Jig is awaiting one complete repository Principles response and explicit digest ratification.\n'
elif [[ "$current_state" == "verification-building" ]]; then
	printf 'Jig is awaiting completion of the registered create-verification-skill procedure. Resume with jig init.\n'
else
	printf 'Jig paused at %s. Resume with jig init.\n' "$current_state"
fi

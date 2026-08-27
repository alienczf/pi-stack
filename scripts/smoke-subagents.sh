#!/usr/bin/env bash
# Live smoke: a parent pi -p must call the subagent tool from this overlay.
# 1) action doctor (no child LLM)
# 2) delegate child, async false, unique token
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
fail() { printf '%s\n' "$*" >&2; exit 1; }

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

pi_bin="$(resolve_pi)" || fail "pi is not installed"
test -d "${HOME}/.pi/agent/npm/node_modules/pi-subagents" || fail "npm:pi-subagents is not installed"

model="${PI_STACK_SMOKE_MODEL:-openai-codex/gpt-5.6-terra:medium}"
token="SMOKE_OK_$$_$RANDOM"
work="$(mktemp -d "${TMPDIR:-/tmp}/pi-stack-smoke.XXXXXX")"
keep="${TMPDIR:-/tmp}/pi-stack-smoke-last"
cleanup() { rm -rf "$work"; }
trap cleanup EXIT
fail() {
	mkdir -p "$keep"
	cp -a "$work"/. "$keep"/ 2>/dev/null || true
	printf '%s\n' "$*" >&2
	printf 'artifacts %s\n' "$keep" >&2
	exit 1
}
git init -q "$work"

run_parent() {
	local prompt="$1"
	local json_out="$2"
	local err_out="$3"
	local timeout_s="$4"
	# Parent may only call subagent. That is the proof. Children rebuild their own tools.
	(
		cd "$work"
		timeout "$timeout_s" env PI_CODING_AGENT_DIR="${HOME}/.pi/agent" \
			"$pi_bin" -p --mode json --no-session --no-skills --thinking off \
			--model "$model" \
			--tools subagent \
			--append-system-prompt "This turn is a setup probe. Call the subagent tool immediately. Do not read files. Do not run bash." \
			-- "$prompt"
	) >"$json_out" 2>"$err_out"
}

parse() {
	python3 - "$1" "$2" <<'PY'
import json
import sys
from pathlib import Path

json_path, err_path = Path(sys.argv[1]), Path(sys.argv[2])
tools = []
texts = []
types = []
for raw in json_path.read_text(errors="replace").splitlines():
	line = raw.strip()
	if not line.startswith("{"):
		continue
	try:
		obj = json.loads(line)
	except json.JSONDecodeError:
		continue
	t = obj.get("type")
	if isinstance(t, str):
		types.append(t)
	ame = obj.get("assistantMessageEvent")
	if isinstance(ame, dict):
		name = ame.get("toolName") or ame.get("name")
		if isinstance(name, str):
			tools.append(name)
		at = ame.get("type")
		if isinstance(at, str):
			types.append("ame:" + at)
	name = obj.get("toolName") or obj.get("name")
	if isinstance(name, str) and obj.get("type") in (
		"toolcall_start",
		"tool_execution_start",
		"tool_call",
	):
		tools.append(name)

	def walk(node):
		if isinstance(node, dict):
			if node.get("type") == "text" and isinstance(node.get("text"), str):
				texts.append(node["text"])
			if isinstance(node.get("text"), str) and node.get("type") != "text":
				if len(node["text"]) > 20:
					texts.append(node["text"])
			for v in node.values():
				walk(v)
		elif isinstance(node, list):
			for item in node:
				walk(item)

	if t in ("tool_execution_end", "toolcall_end", "agent_end", "message_end"):
		walk(obj)

err = err_path.read_text(errors="replace") if err_path.exists() else ""
blob = "\n".join(texts)
print("TOOLS=" + ",".join(tools))
print("TYPES=" + ",".join(sorted(set(types))))
print("ERR_HAS_CURSOR=" + ("yes" if "No matching models found for pattern: cursor/" in err else "no"))
print("---TEXT---")
print(blob)
print("---ERR---")
print(err)
PY
}

assert_subagent_only() {
	local report="$1"
	local tools=""
	local line
	while IFS= read -r line; do
		case "$line" in
			TOOLS=*) tools="${line#TOOLS=}"; break ;;
		esac
	done <<<"$report"
	[[ -n "$tools" ]] || fail "parent called no tools"
	case ",$tools," in
		*,subagent,*) ;;
		*) fail "parent did not call subagent tools=$tools" ;;
	esac
	case ",$tools," in
		*,bash,*) fail "parent called bash instead of staying on subagent tools=$tools" ;;
	esac
	[[ "$report" != *$'\n'"ERR_HAS_CURSOR=yes"$'\n'* && "$report" != "ERR_HAS_CURSOR=yes"$'\n'* ]] \
		|| fail "stderr still has cursor/* model miss"
}

echo "smoke doctor"
doctor_json="$work/doctor.jsonl"
doctor_err="$work/doctor.err"
run_parent "Call the subagent tool once with action doctor. After it returns, quote the agents line from that result. Do not call any other tool." "$doctor_json" "$doctor_err" 180 \
	|| fail "doctor pi -p failed $(cat "$doctor_err") $(tail -c 4000 "$doctor_json")"
doctor_report="$(parse "$doctor_json" "$doctor_err")"
assert_subagent_only "$doctor_report"
printf '%s\n' "$doctor_report" | grep -q 'agents: total' || fail "doctor result missing agents total"
printf '%s\n' "$doctor_report" | grep -q 'builtin' || fail "doctor result missing builtin agents"

echo "smoke spawn"
spawn_json="$work/spawn.jsonl"
spawn_err="$work/spawn.err"
spawn_prompt="Call the subagent tool exactly once with these fields: agent delegate, async false, context fresh, task: Reply with exactly ${token} and no other text. Do not call tools. After the child returns, print ${token} if it appears in the child output. If it failed, print the error."
run_parent "$spawn_prompt" "$spawn_json" "$spawn_err" 300 \
	|| fail "spawn pi -p failed\n$(cat "$spawn_err")\n$(tail -c 8000 "$spawn_json")"
spawn_report="$(parse "$spawn_json" "$spawn_err")"
assert_subagent_only "$spawn_report"
printf '%s\n' "$spawn_report" | grep -Fq "$token" || fail "child did not return ${token}\n$spawn_report"
if printf '%s\n' "$spawn_report" | grep -qiE 'No matching models found for pattern: cursor/|waiting on a model'; then
	fail "child waited on a missing cursor model\n$spawn_report"
fi

echo "check-subagents smoke ok token=${token} model=${model}"

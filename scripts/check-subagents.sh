#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

grep -q 'npm:pi-subagents' install.sh || fail "install.sh must require npm:pi-subagents"
grep -q 'Do not run `pi -p`' overlay/AGENTS.md || fail "AGENTS.md must forbid bash pi -p"
grep -q '{ agent, task }' overlay/AGENTS.md || fail "AGENTS.md must show the one-child subagent call"
grep -q 'workflowScript' overlay/AGENTS.md || fail "AGENTS.md must name workflowScript"
grep -q 'subagent_wait' overlay/AGENTS.md || fail "AGENTS.md must name subagent_wait"
grep -q 'Do not run `pi -p` from bash' overlay/APPEND_SYSTEM.md || fail "APPEND_SYSTEM.md must forbid bash pi -p"
if grep -q '`Task` is `pi -p`' overlay/AGENTS.md; then
	fail "AGENTS.md still maps Task to bash pi -p"
fi

pkg="${HOME}/.pi/agent/npm/node_modules/pi-subagents"
if command -v pi >/dev/null 2>&1 && [[ -d "$pkg" ]]; then
	pi list | grep -q 'npm:pi-subagents' || fail "pi list missing npm:pi-subagents"
	grep -q 'name: "subagent"' "$pkg/src/extension/index.ts" || fail "pi-subagents does not register subagent"
	grep -q 'name: "subagent_wait"' "$pkg/src/runs/background/wait-tool.ts" || fail "pi-subagents does not register subagent_wait"
	for agent in scout worker reviewer oracle delegate researcher; do
		test -f "$pkg/agents/${agent}.md" || fail "missing builtin agent ${agent}.md"
	done
	grep -q 'Do not run `pi -p`' "${HOME}/.pi/agent/AGENTS.md" || fail "live AGENTS.md missing bash pi -p ban"
	grep -q 'subagent' "${HOME}/.pi/agent/APPEND_SYSTEM.md" || fail "live APPEND_SYSTEM.md missing subagent"
fi

echo "check-subagents ok"

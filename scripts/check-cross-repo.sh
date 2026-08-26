#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f skills/cross-repo/SKILL.md || fail "missing skills/cross-repo/SKILL.md"
test -f examples/workspace-AGENTS.md || fail "missing examples/workspace-AGENTS.md"
grep -q 'disable-model-invocation: true' skills/cross-repo/SKILL.md || fail "cross-repo skill must disable model invocation"
grep -q 'pi -p' skills/cross-repo/SKILL.md || fail "skill must dispatch with pi -p"
grep -q 'report' skills/cross-repo/SKILL.md || fail "skill must name report files"
grep -q '.pi/cross-repo/' skills/cross-repo/SKILL.md || fail "skill must name a report directory"
grep -q 'does not edit' skills/cross-repo/SKILL.md || fail "skill must say the parent does not edit children"
grep -qi 'infra' skills/cross-repo/SKILL.md || fail "skill must list infra as an example domain"
grep -qi 'research' skills/cross-repo/SKILL.md || fail "skill must list research as an example domain"
grep -qi 'algo' skills/cross-repo/SKILL.md || fail "skill must list algo as an example domain"
grep -q 'playbooks/investigation.md' overlay/AGENTS.md || fail "overlay AGENTS.md must name investigation.md as the thing not to use"
grep -q 'cross-repo' overlay/AGENTS.md || fail "overlay AGENTS.md must name cross-repo"

if grep -qi 'coding standard' examples/workspace-AGENTS.md; then
	fail "example must not contain coding standard"
fi
if grep -qiE 'alloc|hot path|useEffect' examples/workspace-AGENTS.md; then
	fail "example must stay router-only"
fi
if grep -qiE 'required MCP|use MCP|call MCP' skills/cross-repo/SKILL.md; then
	fail "skill must not require MCP"
fi
grep -q 'ancestor' examples/workspace-AGENTS.md || fail "example must warn that ancestor AGENTS.md still loads"

lines=$(wc -l < examples/workspace-AGENTS.md)
if [ "$lines" -gt 80 ]; then
	fail "examples/workspace-AGENTS.md is ${lines} lines, cap is 80"
fi

echo "check-cross-repo ok"

#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test ! -e examples/workspace-AGENTS.md || fail "examples/workspace-AGENTS.md must not exist"
test -f skills/cross-repo/SKILL.md || fail "missing skills/cross-repo/SKILL.md"
test -f examples/orchestrator/registry.md || fail "missing examples/orchestrator/registry.md"
test -f examples/orchestrator/README.md || fail "missing examples/orchestrator/README.md"

grep -q 'disable-model-invocation: true' skills/cross-repo/SKILL.md || fail "cross-repo skill must disable model invocation"
grep -q 'pi -p' skills/cross-repo/SKILL.md || fail "skill must dispatch with pi -p"
grep -q 'read,grep,find,ls,bash' skills/cross-repo/SKILL.md || fail "child tools must be read,grep,find,ls,bash"
grep -q 'registry.md' skills/cross-repo/SKILL.md || fail "skill must look for registry.md"
grep -q 'siblings.tsv' skills/cross-repo/SKILL.md || fail "skill must look for siblings.tsv"
grep -q 'does not edit' skills/cross-repo/SKILL.md || fail "skill must say the parent does not edit children"
grep -q 'If none of those files exist, stop' skills/cross-repo/SKILL.md || fail "skill must stop when cwd has no registry"

if grep '../AGENTS.md' skills/cross-repo/SKILL.md | grep -qv 'Do not'; then
	fail "cross-repo must not read ../AGENTS.md as a registry"
fi
if grep -qiE 'one level under|sibling \.git|parent folder|workspace root|~/trading' skills/cross-repo/SKILL.md; then
	fail "cross-repo still discovers folder layout"
fi
if grep -qiE 'copy .+ to the folder above|copy this to your workspace' README.md examples/orchestrator/README.md overlay/AGENTS.md skills/cross-repo/SKILL.md; then
	fail "must not instruct copying onto a container folder"
fi
if grep -qiE 'required MCP|use MCP|call MCP' skills/cross-repo/SKILL.md; then
	fail "skill must not require MCP"
fi

grep -q '/skill:cross-repo' overlay/AGENTS.md || fail "overlay AGENTS.md must name /skill:cross-repo"
grep -q 'playbooks/investigation.md' overlay/AGENTS.md || fail "overlay AGENTS.md must name investigation.md as the thing not to use"
grep -q 'Do not place `AGENTS.md` in a directory that has multiple domain git repos as children' overlay/AGENTS.md || fail "overlay AGENTS.md must ban ancestor coding files"

echo "check-cross-repo ok"

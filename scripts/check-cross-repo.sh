#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f skills/cross-repo/SKILL.md || fail "missing skills/cross-repo/SKILL.md"
test -f prompts/cross-repo.md || fail "missing prompts/cross-repo.md"
test ! -e examples/orchestrator || fail "retired cross-repo topology example remains"

grep -q 'disable-model-invocation: true' skills/cross-repo/SKILL.md || fail "cross-repo skill must require explicit invocation"
grep -q 'Use only for /skill:cross-repo or /cross-repo' skills/cross-repo/SKILL.md || fail "cross-repo skill must document explicit routes"
grep -q 'subagent' skills/cross-repo/SKILL.md || fail "skill must dispatch with the subagent tool"
grep -q 'workflowScript' skills/cross-repo/SKILL.md || fail "skill must batch multi-repository dispatch"
grep -q 'cwd' skills/cross-repo/SKILL.md || fail "skill must set the target cwd"
grep -q '\$ARGUMENTS' prompts/cross-repo.md || fail "prompt must forward the explicit request"

if grep -q 'pi -p' skills/cross-repo/SKILL.md prompts/cross-repo.md; then
  grep -q 'does not launch `pi -p`' skills/cross-repo/SKILL.md || fail "cross-repo skill must not launch nested Pi"
fi
if grep -qE '/skill:cross-repo|spans two git repos|multiple domain git repos' overlay/AGENTS.md README.md; then
  fail "global multi-repository guidance remains"
fi
if grep -qiE 'parent does not edit|never MCP|do not walk parent|find sibling \\.git' skills/cross-repo/SKILL.md prompts/cross-repo.md; then
  fail "cross-repo still imposes retired topology constraints"
fi

echo "check-cross-repo ok"

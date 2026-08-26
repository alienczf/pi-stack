#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f skills/jig/SKILL.md || fail "missing skills/jig/SKILL.md"
test -x bin/jig.sh || fail "bin/jig.sh must be executable"
grep -q 'disable-model-invocation: true' skills/jig/SKILL.md || fail "jig skill must disable model invocation"
grep -q interview skills/jig/SKILL.md || fail "SKILL.md must mention interview"
grep -q lexicon skills/jig/SKILL.md || fail "SKILL.md must mention lexicon"
grep -q refactor skills/jig/SKILL.md || fail "SKILL.md must mention refactor"
grep -q iterate skills/jig/SKILL.md || fail "SKILL.md must mention iterate"
grep -q S15 skills/jig/references/failure-modes.md || fail "failure-modes.md missing S15"
grep -q P7 skills/jig/references/failure-modes.md || fail "failure-modes.md missing P7"
grep -q D4 skills/jig/references/failure-modes.md || fail "failure-modes.md missing D4"

desc=$(awk 'BEGIN{d=0} /^---$/{c++; next} c==1 && $0 ~ /^description:/{d=1} c==1 && d{print} c==2{exit}' skills/jig/SKILL.md | wc -c)
if [ "$desc" -gt 400 ]; then
	fail "jig YAML description is ${desc} bytes, cap is 400"
fi
body=$(wc -c < skills/jig/SKILL.md)
if [ "$body" -gt 24000 ]; then
	fail "jig SKILL.md body is ${body} bytes, cap is 24k"
fi

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT
git init -q "$tmp"
mkdir -p "$tmp/src"
# argv check from a subdirectory so git root resolution is proven
out=$(cd "$tmp/src" && PI=echo "$root/bin/jig.sh")
printf '%s\n' "$out" | grep -q -- '-p' || fail "PI=echo argv missing -p"
printf '%s\n' "$out" | grep -q -- '--approve' || fail "PI=echo argv missing --approve"
printf '%s\n' "$out" | grep -q -- '--no-session' || fail "PI=echo argv missing --no-session"
printf '%s\n' "$out" | grep -q 'read,grep,find,ls,bash,write,edit' || fail "PI=echo argv missing tools allowlist"
printf '%s\n' "$out" | grep -q 'skills/jig/SKILL.md' || fail "PI=echo argv missing SKILL.md path"

iter=$(cd "$tmp" && PI=echo "$root/bin/jig.sh" --iterate)
printf '%s\n' "$iter" | grep -q -- '--iterate' || fail "--iterate was not forwarded"

mkdir -p "$tmp/.pi/jig"
echo already >"$tmp/.pi/jig/interview.md"
idle=$(cd "$tmp" && PI=echo "$root/bin/jig.sh")
printf '%s\n' "$idle" | grep -q 'already fitted' || fail "second run with no flags must print already fitted"
printf '%s\n' "$idle" | grep -q -- '--approve' && fail "no-flags second run must not invoke PI"

echo "check-jig ok"

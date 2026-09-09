#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -x "$root/bin/update-pstack" || fail "bin/update-pstack is not executable"
test -x "$root/bin/pstackctl.py" || fail "bin/pstackctl.py is not executable"
python3 -m py_compile "$root/bin/pstackctl.py" || fail "pstackctl.py failed to compile"

tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

pi_stack="$tmp/pi stack"
mkdir -p "$pi_stack"
git init -q -b main "$pi_stack"
printf '.plugins/\n' >"$pi_stack/.gitignore"
cat >"$pi_stack/install.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
if [[ "${1:-}" == "--print-pstack-skills" ]]; then
	printf '%s\n' poteto-mode required-skill
	exit 0
fi
printf '%s\t%s\n' "$PI_STACK" "$PSTACK" >>"$INSTALL_LOG"
if [[ "${FAIL_INSTALL:-}" == 1 ]]; then
	exit 23
fi
if [[ "${MUTATE_PI_STACK:-}" == 1 ]]; then
	printf '# updater fixture mutation\n' >>"$PI_STACK/.gitignore"
	git -C "$PI_STACK" add .gitignore
fi
EOF
chmod +x "$pi_stack/install.sh"
git -C "$pi_stack" add .
git -C "$pi_stack" -c user.name=test -c user.email=test@example.com commit -qm initial
pi_stack_revision="$(git -C "$pi_stack" rev-parse HEAD)"

upstream="$tmp/plugins upstream"
mkdir -p "$upstream/pstack/.cursor-plugin"
git init -q -b main "$upstream"
printf '%s\n' '{"name":"pstack","version":"0.14.5"}' >"$upstream/pstack/.cursor-plugin/plugin.json"
for name in poteto-mode required-skill; do
	mkdir -p "$upstream/pstack/skills/$name"
	printf '%s\n' '---' "name: $name" 'description: fixture' '---' >"$upstream/pstack/skills/$name/SKILL.md"
done
git -C "$upstream" add .
git -C "$upstream" -c user.name=test -c user.email=test@example.com commit -qm initial

plugins="$pi_stack/.plugins"
git clone -q "file://$upstream" "$plugins"
old_pstack_revision="$(git -C "$plugins" rev-parse HEAD)"
pstack="$plugins/pstack"
printf '%s\n' '{"name":"pstack","version":"0.15.0"}' >"$upstream/pstack/.cursor-plugin/plugin.json"
printf '%s\n' 'updated' >"$upstream/pstack/update-marker"
git -C "$upstream" rm -q pstack/skills/required-skill/SKILL.md
git -C "$upstream" add .
git -C "$upstream" -c user.name=test -c user.email=test@example.com commit -qm update-with-missing-skill
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/missing.out" 2>"$tmp/missing.err"; then
	fail "status accepted an upstream with a missing selected skill root"
fi
grep -q 'missing selected skill root: required-skill' "$tmp/missing.err" || fail "missing-skill refusal was not useful"
mkdir -p "$upstream/pstack/skills/required-skill"
printf '%s\n' '---' 'name: required-skill' 'description: fixture' '---' >"$upstream/pstack/skills/required-skill/SKILL.md"
git -C "$upstream" add .
git -C "$upstream" -c user.name=test -c user.email=test@example.com commit -qm restore-required-skill
new_pstack_revision="$(git -C "$upstream" rev-parse HEAD)"

printf '# dirty pi-stack\n' >>"$pi_stack/.gitignore"
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/dirty-pi.out" 2>"$tmp/dirty-pi.err"; then
	fail "status accepted a dirty pi-stack checkout"
fi
grep -q 'pi-stack checkout has tracked or staged changes' "$tmp/dirty-pi.err" || fail "dirty pi-stack refusal was not useful"
git -C "$pi_stack" checkout -q -- .gitignore
pi_stack_status="$(git -C "$pi_stack" status --short --untracked-files=no)"
test -z "$pi_stack_status" || fail "pi-stack fixture is not clean"
plan="$tmp/plan.json"
PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$plan"
python3 - "$plan" "$pi_stack_revision" "$old_pstack_revision" "$new_pstack_revision" <<'PY' || fail "status plan has the wrong shape"
import json
import sys
from pathlib import Path

plan = json.loads(Path(sys.argv[1]).read_text())
pi_revision, old_revision, new_revision = sys.argv[2:]
assert plan["schemaVersion"] == 1
assert plan["piStack"]["revision"] == pi_revision
assert plan["piStack"]["statusSummary"] == []
assert plan["pstack"]["currentRevision"] == old_revision
assert plan["pstack"]["upstreamRevision"] == new_revision
assert plan["pstack"]["currentVersion"] == "0.14.5"
assert plan["pstack"]["upstreamVersion"] == "0.15.0"
assert plan["readiness"] == "ready"
assert any("update-marker" in path for item in plan["changedPaths"] for path in item["paths"])
PY
required_skill="pstack/skills/required-skill/SKILL.md"
git -C "$plugins" update-index --skip-worktree "$required_skill"
rm "$plugins/$required_skill"
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/sparse.out" 2>"$tmp/sparse.err"; then
	fail "status accepted a selected skill missing from the working tree"
fi
grep -q 'not fully materialized' "$tmp/sparse.err" || fail "missing working-tree skill refusal was not useful"
git -C "$plugins" update-index --no-skip-worktree "$required_skill"
git -C "$plugins" checkout -q HEAD -- "$required_skill"
printf '%s\n' outside >"$tmp/outside-skill-content"
ln -s "$tmp/outside-skill-content" "$pstack/skills/required-skill/external.md"
git -C "$plugins" add pstack/skills/required-skill/external.md
git -C "$plugins" -c user.name=test -c user.email=test@example.com commit -qm external-skill-symlink
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/symlink.out" 2>"$tmp/symlink.err"; then
	fail "status accepted a symlink in a selected skill"
fi
grep -q 'selected pstack skill contains a symlink' "$tmp/symlink.err" || fail "selected skill symlink refusal was not useful"
git -C "$plugins" reset -q --hard "$old_pstack_revision"

zero_revision="0000000000000000000000000000000000000000"
install_log="$tmp/install.log"
apply_args=(--expected-pi-stack "$pi_stack_revision" --expected-current "$old_pstack_revision" --expected-upstream "$new_pstack_revision")
if PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" "$root/bin/update-pstack" apply --expected-pi-stack "$pi_stack_revision" --expected-current "$old_pstack_revision" --expected-upstream "$zero_revision" >"$tmp/wrong.out" 2>"$tmp/wrong.err"; then
	fail "apply accepted an unreviewed upstream revision"
fi
grep -q 'no longer matches' "$tmp/wrong.err" || fail "wrong-upstream refusal was not useful"
if PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" "$root/bin/update-pstack" apply --expected-pi-stack "$pi_stack_revision" --expected-current "$zero_revision" --expected-upstream "$new_pstack_revision" >"$tmp/current.out" 2>"$tmp/current.err"; then
	fail "apply accepted an unreviewed current revision"
fi
grep -q 'neither the reviewed current revision' "$tmp/current.err" || fail "wrong-current refusal was not useful"
if PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" "$root/bin/update-pstack" apply --expected-pi-stack "$zero_revision" --expected-current "$old_pstack_revision" --expected-upstream "$new_pstack_revision" >"$tmp/pi.out" 2>"$tmp/pi.err"; then
	fail "apply accepted a changed pi-stack revision"
fi
grep -q 'reviewed pi-stack revision' "$tmp/pi.err" || fail "wrong-pi-stack refusal was not useful"
test "$(git -C "$plugins" rev-parse HEAD)" = "$old_pstack_revision" || fail "refused apply changed pstack"
test ! -e "$install_log" || fail "refused apply ran install.sh"

set +e
PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" FAIL_INSTALL=1 "$root/bin/update-pstack" apply "${apply_args[@]}" >"$tmp/interrupted.out" 2>"$tmp/interrupted.err"
interrupted_status=$?
set -e
test "$interrupted_status" = 23 || fail "interrupted install returned $interrupted_status instead of 23"
test "$(git -C "$plugins" rev-parse HEAD)" = "$new_pstack_revision" || fail "interrupted apply did not fast-forward pstack"
test "$(git -C "$pi_stack" rev-parse HEAD)" = "$pi_stack_revision" || fail "interrupted apply changed pi-stack HEAD"
test "$(git -C "$pi_stack" status --short --untracked-files=no)" = "$pi_stack_status" || fail "interrupted apply changed pi-stack status"
test "$(wc -l <"$install_log" | tr -d ' ')" = 1 || fail "interrupted apply did not run install.sh once"

printf '%s\n' 'published after reviewed endpoint' >"$upstream/pstack/post-review-marker"
git -C "$upstream" add .
git -C "$upstream" -c user.name=test -c user.email=test@example.com commit -qm post-review-update
advanced_pstack_revision="$(git -C "$upstream" rev-parse HEAD)"
test "$advanced_pstack_revision" != "$new_pstack_revision" || fail "fixture did not advance upstream"

PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" "$root/bin/update-pstack" apply "${apply_args[@]}" >"$tmp/apply.json"
test "$(git -C "$plugins" rev-parse HEAD)" = "$new_pstack_revision" || fail "recovery apply changed pstack revision"
test "$(git -C "$plugins" rev-parse origin/main)" = "$new_pstack_revision" || fail "recovery apply fetched a newer unreviewed upstream"
test "$(git -C "$pi_stack" rev-parse HEAD)" = "$pi_stack_revision" || fail "recovery apply changed pi-stack HEAD"
test "$(git -C "$pi_stack" status --short --untracked-files=no)" = "$pi_stack_status" || fail "recovery apply changed pi-stack status"
test "$(wc -l <"$install_log" | tr -d ' ')" = 2 || fail "recovery apply did not reapply install.sh"
python3 - "$tmp/apply.json" "$new_pstack_revision" "$pi_stack_revision" <<'PY' || fail "recovery result has the wrong shape"
import json
import sys
from pathlib import Path

result = json.loads(Path(sys.argv[1]).read_text())
assert result["result"]["pstackRevision"] == sys.argv[2]
assert result["result"]["piStackRevision"] == sys.argv[3]
assert result["result"]["piStackStatusSummary"] == []
assert result["result"]["fastForwarded"] is False
PY

if PI_STACK="$pi_stack" PSTACK="$pstack" INSTALL_LOG="$install_log" MUTATE_PI_STACK=1 "$root/bin/update-pstack" apply "${apply_args[@]}" >"$tmp/mutate.out" 2>"$tmp/mutate.err"; then
	fail "apply accepted an install that changed pi-stack status"
fi
grep -q 'tracked or staged status changed' "$tmp/mutate.err" || fail "pi-stack status change refusal was not useful"
test "$(git -C "$pi_stack" rev-parse HEAD)" = "$pi_stack_revision" || fail "mutation rollback changed pi-stack HEAD"
test "$(git -C "$pi_stack" status --short --untracked-files=no)" = "$pi_stack_status" || fail "updater did not roll back installer pi-stack changes"
test "$(cat "$pi_stack/.gitignore")" = '.plugins/' || fail "updater did not restore the pi-stack file"

printf '%s\n' unreviewed >"$pstack/skills/poteto-mode/unreviewed.md"
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/untracked.out" 2>"$tmp/untracked.err"; then
	fail "status accepted untracked pstack skill content"
fi
grep -q 'untracked, or ignored content' "$tmp/untracked.err" || fail "untracked pstack refusal was not useful"
rm "$pstack/skills/poteto-mode/unreviewed.md"

git -C "$plugins" checkout -q "$old_pstack_revision" -- pstack/.cursor-plugin/plugin.json
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/dirty.out" 2>"$tmp/dirty.err"; then
	fail "status accepted a dirty pstack checkout"
fi
grep -q 'tracked, staged, untracked, or ignored content' "$tmp/dirty.err" || fail "dirty refusal was not useful"
git -C "$plugins" reset -q --hard "$new_pstack_revision"

git -C "$plugins" checkout -q --detach
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/detached.out" 2>"$tmp/detached.err"; then
	fail "status accepted a detached pstack checkout"
fi
grep -q 'not on a branch' "$tmp/detached.err" || fail "detached refusal was not useful"
git -C "$plugins" checkout -q main
git -C "$plugins" fetch -q
git -C "$plugins" merge -q --ff-only origin/main
test "$(git -C "$plugins" rev-parse HEAD)" = "$advanced_pstack_revision" || fail "fixture did not reach advanced upstream"

printf '%s\n' local >"$plugins/pstack/local-marker"
git -C "$plugins" add .
git -C "$plugins" -c user.name=test -c user.email=test@example.com commit -qm local
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/ahead.out" 2>"$tmp/ahead.err"; then
	fail "status accepted local pstack commits"
fi
grep -q 'local commits' "$tmp/ahead.err" || fail "local-ahead refusal was not useful"

printf '%s\n' remote >"$upstream/pstack/remote-marker"
git -C "$upstream" add .
git -C "$upstream" -c user.name=test -c user.email=test@example.com commit -qm remote
if PI_STACK="$pi_stack" PSTACK="$pstack" "$root/bin/update-pstack" status >"$tmp/diverged.out" 2>"$tmp/diverged.err"; then
	fail "status accepted divergent pstack history"
fi
grep -q 'diverged' "$tmp/diverged.err" || fail "divergence refusal was not useful"

coupled="$pi_stack/pstack"
mkdir -p "$coupled/.cursor-plugin" "$coupled/skills/poteto-mode"
printf '%s\n' '{"name":"pstack","version":"0.15.0"}' >"$coupled/.cursor-plugin/plugin.json"
printf '%s\n' skill >"$coupled/skills/poteto-mode/SKILL.md"
if PI_STACK="$pi_stack" PSTACK="$coupled" "$root/bin/update-pstack" status >"$tmp/coupled.out" 2>"$tmp/coupled.err"; then
	fail "status accepted pstack inside the pi-stack checkout"
fi
grep -q 'independent Git checkout' "$tmp/coupled.err" || fail "coupled-checkout refusal was not useful"
test "$(git -C "$pi_stack" rev-parse HEAD)" = "$pi_stack_revision" || fail "refusal cases changed pi-stack HEAD"

echo "check-update-pstack ok"

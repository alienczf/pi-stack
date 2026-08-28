#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f skills/jig/SKILL.md || fail "missing skills/jig/SKILL.md"
test -x bin/jig.sh || fail "bin/jig.sh must be executable"
test -x bin/jigctl.py || fail "bin/jigctl.py must be executable"
grep -q 'git rev-parse --show-toplevel' bin/jig.sh || fail "jig.sh must resolve the Git top level"
if grep -qE 'find .*-name .git|workspace root|~/trading' bin/jig.sh; then
	fail "jig.sh must not discover folder layout"
fi
grep -q 'disable-model-invocation: true' skills/jig/SKILL.md || fail "jig skill must disable model invocation"
grep -q interview skills/jig/SKILL.md || fail "SKILL.md must mention interview"
grep -q lexicon skills/jig/SKILL.md || fail "SKILL.md must mention lexicon"
grep -q refactor skills/jig/SKILL.md || fail "SKILL.md must mention refactor"
grep -q iterate skills/jig/SKILL.md || fail "SKILL.md must mention iterate"
grep -q S15 skills/jig/references/failure-modes.md || fail "failure-modes.md missing S15"
grep -q P7 skills/jig/references/failure-modes.md || fail "failure-modes.md missing P7"
grep -q D4 skills/jig/references/failure-modes.md || fail "failure-modes.md missing D4"
test -f skills/jig/playbooks/init.md || fail "missing Jig init playbook"
test -f skills/jig/references/commandments-interview.md || fail "missing COMMANDMENTS interview"
test -f skills/jig/references/COMMANDMENTS.template.md || fail "missing COMMANDMENTS template"
grep -q 'one question round' skills/jig/playbooks/init.md || fail "init playbook must keep one interview round"
grep -q 'recommended default' skills/jig/playbooks/init.md || fail "init playbook must show recommended defaults"
grep -q 'exact staged candidate bytes and SHA-256 digest' skills/jig/playbooks/init.md || fail "init playbook must show exact digest ratification"
grep -q 'Record amend and defer' skills/jig/playbooks/init.md || fail "init playbook must preserve amend and defer paths"
grep -q 'Do not select one for the operator' skills/jig/playbooks/init.md || fail "init playbook must forbid automatic default selection"
grep -q 'Do not infer values or ask a second round' skills/jig/playbooks/init.md || fail "init playbook must forbid inference and repeat interviews"
grep -q 'Only this deterministic command may publish' skills/jig/references/commandments-interview.md || fail "ratification must stay controller-owned"
grep -q 'does not consume response files on rerun' skills/jig/playbooks/init.md || fail "init playbook must describe the direct controller resume"
if grep -q 'rerun `jig init`' skills/jig/playbooks/init.md skills/jig/references/commandments-interview.md; then
	fail "COMMANDMENTS resume must not claim launcher response-file consumption"
fi

desc=$(awk 'BEGIN{d=0} /^---$/{c++; next} c==1 && $0 ~ /^description:/{d=1} c==1 && d{print} c==2{exit}' skills/jig/SKILL.md | wc -c)
if [ "$desc" -gt 400 ]; then
	fail "jig YAML description is ${desc} bytes, cap is 400"
fi
body=$(wc -c < skills/jig/SKILL.md)
if [ "$body" -gt 24000 ]; then
	fail "jig SKILL.md body is ${body} bytes, cap is 24k"
fi

bash -n bin/jig.sh scripts/check-jig.sh
python3 -m py_compile bin/jigctl.py
python3 -m unittest discover -s scripts/jig_tests -p 'test_*.py'
python3 - <<'PY'
import ast
import sys
from pathlib import Path

path = Path("bin/jigctl.py")
tree = ast.parse(path.read_text(encoding="utf-8"))
imports = {
    node.names[0].name.split(".")[0]
    for node in ast.walk(tree)
    if isinstance(node, ast.Import)
}
imports.update(
    node.module.split(".")[0]
    for node in ast.walk(tree)
    if isinstance(node, ast.ImportFrom) and node.module and node.module != "__future__"
)
external = sorted(imports - sys.stdlib_module_names)
if external:
    raise SystemExit(f"jigctl.py has non-stdlib imports: {', '.join(external)}")

changed = [
    Path("bin/jig.sh"),
    Path("bin/jigctl.py"),
    Path("scripts/check-jig.sh"),
    Path("skills/jig/SKILL.md"),
    Path("skills/jig/playbooks/init.md"),
    Path("skills/jig/references/commandments-interview.md"),
    Path("skills/jig/references/COMMANDMENTS.template.md"),
    *sorted(Path("scripts/jig_tests").glob("**/*.py")),
    *sorted(Path("scripts/jig_tests/fixtures").glob("**/*")),
]
banned = {"\u2013", "\u2014", "\u2018", "\u2019", "\u201c", "\u201d"}
for candidate in changed:
    if not candidate.is_file():
        continue
    text = candidate.read_text(encoding="utf-8")
    found = sorted(character for character in banned if character in text)
    if found:
        raise SystemExit(f"{candidate} contains banned Unicode punctuation")
    if __import__("re").search(r"/ho" r"me/[^/]+/", text):
        raise SystemExit(f"{candidate} contains a machine-specific absolute path")
print("jig scans ok: stdlib imports and portable changed files")
PY

printf 'check-jig ok\n'

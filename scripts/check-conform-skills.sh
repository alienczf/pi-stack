#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

test -f bin/conform-skills.py || fail "missing bin/conform-skills.py"
python3 -m py_compile bin/conform-skills.py || fail "conform-skills.py failed to compile"

tmp=$(mktemp -d)
trap 'rm -rf "$tmp"' EXIT

src="$tmp/src/poteto-mode"
mkdir -p "$src/playbooks"
cat >"$src/SKILL.md" <<'EOF'
---
name: Poteto Mode
description: poteto's agent style for tests
disable-model-invocation: true
mode: true
---

# Poteto mode

See [investigation](playbooks/investigation.md).
EOF
printf 'playbook body\n' >"$src/playbooks/investigation.md"

out="$tmp/out"
python3 "$root/bin/conform-skills.py" --out "$out" "$src"

grep -q '^name: poteto-mode$' "$out/poteto-mode/SKILL.md" || fail "conformed name is not poteto-mode"
grep -q 'name: Poteto Mode' "$src/SKILL.md" || fail "source SKILL.md was edited"
test -L "$out/poteto-mode/playbooks" || fail "playbooks was not symlinked"
grep -q 'playbook body' "$out/poteto-mode/playbooks/investigation.md" || fail "symlinked playbook is unreadable"
grep -q 'disable-model-invocation: true' "$out/poteto-mode/SKILL.md" || fail "Cursor frontmatter was stripped"
python3 - "$root/bin/conform-skills.py" "$src" <<'PY' || fail "in-place rewrite was not refused"
import subprocess
import sys
from pathlib import Path

script, src = sys.argv[1], sys.argv[2]
parent = str(Path(src).parent)
r = subprocess.run(["python3", script, "--out", parent, src], capture_output=True, text=True)
if r.returncode == 0:
	raise SystemExit("in-place rewrite succeeded")
if "in-place" not in r.stderr:
	raise SystemExit(r.stderr or "missing in-place error")
PY

# already-valid name stays, body unchanged besides wrapping
valid="$tmp/src/unslop"
mkdir -p "$valid"
cat >"$valid/SKILL.md" <<'EOF'
---
name: unslop
description: Cut AI tells from any writing. Must always apply.
---

# Unslop
EOF
python3 "$root/bin/conform-skills.py" --out "$out" "$valid"
grep -q '^name: unslop$' "$out/unslop/SKILL.md" || fail "valid name was rewritten incorrectly"

# --tree finds nested SKILL.md and stops at the skill root
tree="$tmp/tree"
mkdir -p "$tree/skills/poteto-mode/playbooks" "$tree/skills/how"
cp "$src/SKILL.md" "$tree/skills/poteto-mode/SKILL.md"
printf 'nested\n' >"$tree/skills/poteto-mode/playbooks/nested.md"
cat >"$tree/skills/how/SKILL.md" <<'EOF'
---
name: how
description: how does it work
---

# How
EOF
tree_out="$tmp/tree-out"
python3 "$root/bin/conform-skills.py" --tree "$tree/skills" --out "$tree_out"
test -f "$tree_out/poteto-mode/SKILL.md" || fail "--tree missed poteto-mode"
test -f "$tree_out/how/SKILL.md" || fail "--tree missed how"
grep -q '^name: poteto-mode$' "$tree_out/poteto-mode/SKILL.md" || fail "--tree did not slug Poteto Mode"

# description cap
long="$tmp/src/long-name-skill"
mkdir -p "$long"
long_desc=$(python3 -c 'print("x"*1100)')
printf '%s\n' "---" "name: Long Name Skill" "description: $long_desc" "---" "# Long" >"$long/SKILL.md"
python3 "$root/bin/conform-skills.py" --out "$out" "$long"
python3 - "$out/long-name-skill/SKILL.md" <<'PY' || fail "description was not capped"
import re
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
fm = text.split("---", 2)[1]
m = re.search(r"^description:\s*(.*)$", fm, re.M)
if not m:
	raise SystemExit("no description")
val = m.group(1).strip().strip('"')
if len(val) > 1024:
	raise SystemExit(f"description still {len(val)}")
if "name: long-name-skill" not in text:
	raise SystemExit("long name was not slugged")
PY

# Pi's own loader: source warns, dest does not
if command -v pi >/dev/null 2>&1; then
	cli="$(readlink -f "$(command -v pi)")"
	pkg="$(cd "$(dirname "$cli")/../.." && pwd)"
	index="$pkg/dist/index.js"
	test -f "$index" || fail "pi package missing dist/index.js at $pkg"
	INDEX="$index" SRC="$src" DST="$out/poteto-mode" node --input-type=module <<'JS'
import { pathToFileURL } from "node:url";

const index = process.env.INDEX;
const sourceDir = process.env.SRC;
const destDir = process.env.DST;
const { loadSkillsFromDir } = await import(pathToFileURL(index).href);

const src = loadSkillsFromDir({ dir: sourceDir, source: "test" });
const dst = loadSkillsFromDir({ dir: destDir, source: "test" });
const srcWarn = src.diagnostics.some((d) => String(d.message).includes("invalid characters"));
const dstWarn = dst.diagnostics.some((d) => String(d.message).includes("invalid characters"));
if (!srcWarn) {
	console.error("Pi loader did not warn on Poteto Mode");
	process.exit(1);
}
if (dstWarn) {
	console.error("Pi loader still warns after conform", dst.diagnostics);
	process.exit(1);
}
if (dst.skills.length !== 1 || dst.skills[0].name !== "poteto-mode") {
	console.error("expected name poteto-mode", dst.skills);
	process.exit(1);
}
JS
else
	fail "pi is not on PATH; cannot verify against Pi's skill loader"
fi

echo "check-conform-skills ok"

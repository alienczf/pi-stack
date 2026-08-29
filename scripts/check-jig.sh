#!/usr/bin/env bash
set -euo pipefail

root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
fail() { printf '%s\n' "$*" >&2; exit 1; }

for path in \
	bin/jig.sh \
	bin/jigctl.py \
	install.sh \
	prompts/jig.md \
	skills/jig/SKILL.md \
	skills/jig/playbooks/init.md \
	skills/jig/playbooks/first-step.md \
	skills/jig/references/public-routes.json \
	skills/jig/references/commandments-interview.md \
	skills/jig/references/runtime-verification.md \
	scripts/render-jig-routes.py \
	scripts/check-readme-commands.py \
	scripts/jig_tests/test_integration.py; do
	test -f "$path" || fail "missing $path"
done

test -x bin/jig.sh || fail "bin/jig.sh must be executable"
test -x bin/jigctl.py || fail "bin/jigctl.py must be executable"
test -x scripts/render-jig-routes.py || fail "render-jig-routes.py must be executable"
test -x scripts/check-readme-commands.py || fail "check-readme-commands.py must be executable"

grep -q 'git rev-parse --show-toplevel' bin/jig.sh || fail "jig.sh must resolve the Git top level"
grep -q 'disable-model-invocation: true' skills/jig/SKILL.md || fail "Jig must require explicit invocation"
grep -q 'first-step.md' skills/jig/playbooks/init.md || fail "init must hand off to the first-step playbook"
grep -q 'create-verification-skill/SKILL.md' skills/jig/playbooks/init.md || fail "init must use the canonical verification procedure"
grep -q 'commit-step-selection' skills/jig/playbooks/first-step.md || fail "first-step playbook must use controller selection"
grep -q 'complete-step-result' skills/jig/playbooks/first-step.md || fail "first-step playbook must use controller completion"

python3 scripts/render-jig-routes.py --check
python3 scripts/check-readme-commands.py >/dev/null

python3 - <<'PY'
import ast
import json
import re
import sys
from pathlib import Path

root = Path(".")
skill = root / "skills/jig/SKILL.md"
prompt = root / "prompts/jig.md"
matrix = json.loads((root / "skills/jig/references/public-routes.json").read_text(encoding="utf-8"))


def frontmatter(path):
    text = path.read_text(encoding="utf-8")
    parts = text.split("---", 2)
    if len(parts) != 3 or parts[0] != "":
        raise SystemExit(f"{path} has invalid frontmatter")
    values = {}
    for line in parts[1].strip().splitlines():
        key, separator, value = line.partition(":")
        if not separator:
            raise SystemExit(f"{path} has malformed frontmatter")
        values[key.strip()] = value.strip().strip('"')
    return values, parts[2]

skill_frontmatter, skill_body = frontmatter(skill)
if skill_frontmatter.get("name") != "jig" or not skill_frontmatter.get("description"):
    raise SystemExit("Jig frontmatter lacks its name or description")
if skill_frontmatter.get("disable-model-invocation") != "true":
    raise SystemExit("Jig must keep disable-model-invocation true")
if len(skill_frontmatter["description"]) > 400 or len(skill.read_bytes()) > 24000:
    raise SystemExit("Jig skill exceeds its size cap")

prompt_frontmatter, prompt_body = frontmatter(prompt)
if not prompt_frontmatter.get("description") or prompt_frontmatter.get("argument-hint") != "init":
    raise SystemExit("Jig prompt frontmatter is incomplete")
if "$ARGUMENTS" not in prompt_body or "registered `jig` skill" not in prompt_body:
    raise SystemExit("Jig prompt does not delegate arguments to the registered skill")
if any(token in prompt_body for token in ("commit-profile", "stage-commandments", "complete-step-result")):
    raise SystemExit("Jig prompt duplicates controller state logic")

required = {
    "route", "userCommand", "trustResourceLoading", "resourceIsolation",
    "controllerLocation", "pauseResumeBehavior", "routeMismatchRecovery", "terminalState",
}
routes = matrix.get("routes")
if matrix.get("schemaVersion") != 1 or not isinstance(routes, list) or len(routes) != 3:
    raise SystemExit("public route matrix has the wrong shape")
if [item.get("userCommand") for item in routes] != ["jig init", "/skill:jig init", "/jig init"]:
    raise SystemExit("public route commands drifted")
for route in routes:
    if set(route) != required:
        raise SystemExit(f"public route has wrong fields: {route.get('route')}")
if [item["resourceIsolation"] for item in routes] != ["isolated-shell", "inherited-session", "inherited-session"]:
    raise SystemExit("public route isolation drifted")

link_pattern = re.compile(r"\[[^]]+\]\(([^)]+)\)")
for path in [skill, *sorted((root / "skills/jig/playbooks").glob("*.md")), *sorted((root / "skills/jig/references").glob("*.md"))]:
    for target in link_pattern.findall(path.read_text(encoding="utf-8")):
        if "://" in target or target.startswith("#"):
            continue
        resolved = (path.parent / target.split("#", 1)[0]).resolve()
        if not resolved.exists():
            raise SystemExit(f"broken Jig link: {path} -> {target}")

controller = root / "bin/jigctl.py"
tree = ast.parse(controller.read_text(encoding="utf-8"))
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
    raise SystemExit("jigctl.py has non-stdlib imports: " + ", ".join(external))

public = [
    root / "README.md", root / "overlay/AGENTS.md", root / "prompts/jig.md",
    root / "bin/jig.sh", root / "install.sh",
    *sorted((root / "skills/jig").rglob("*")),
]
banned_characters = {"\u2013", "\u2014", "\u2018", "\u2019", "\u201c", "\u201d"}
stale = re.compile(r"--apply|--force|--iterate|already fitted|cold[- ]agent|refactor\.md\.draft|jig packages separately", re.I)
for path in public:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    if banned_characters.intersection(text):
        raise SystemExit(f"{path} contains banned Unicode punctuation")
    if re.search(r"/ho" r"me/[^/$]+/", text):
        raise SystemExit(f"{path} contains a machine-specific absolute path")
    match = stale.search(text)
    if match:
        raise SystemExit(f"{path} contains stale Jig prose: {match.group(0)}")
if "makes no claim that Jig improves agent placement, import selection, routing, proof choices, or agent behavior" not in (root / "README.md").read_text():
    raise SystemExit("README lacks the program-evaluation qualification")
if re.search(r"pretend you are|role[- ]play", "\n".join(path.read_text() for path in public if path.is_file()), re.I):
    raise SystemExit("public Jig resources retain a proxy role-play test")
print("jig static contract ok")
PY

bash -n bin/jig.sh install.sh scripts/check-jig.sh
python3 -m py_compile \
	bin/jigctl.py \
	scripts/render-jig-routes.py \
	scripts/check-readme-commands.py \
	scripts/jig_tests/test_integration.py

if command -v pi >/dev/null 2>&1; then
	cli="$(readlink -f "$(command -v pi)")"
	pkg="$(cd "$(dirname "$cli")/../.." && pwd)"
	index="$pkg/dist/index.js"
	prompts="$pkg/dist/core/prompt-templates.js"
	INDEX="$index" PROMPTS="$prompts" ROOT="$root" node --input-type=module <<'JS'
import { pathToFileURL } from "node:url";
const root = process.env.ROOT;
const { loadSkillsFromDir } = await import(pathToFileURL(process.env.INDEX).href);
const { loadPromptTemplates, expandPromptTemplate } = await import(pathToFileURL(process.env.PROMPTS).href);
const skillResult = loadSkillsFromDir({ dir: `${root}/skills/jig`, source: "jig-check" });
if (skillResult.diagnostics.length || skillResult.skills.length !== 1 || skillResult.skills[0].name !== "jig") {
	console.error(skillResult);
	process.exit(1);
}
const templates = loadPromptTemplates({ cwd: root, agentDir: `${root}/.missing-agent`, promptPaths: [`${root}/prompts/jig.md`], includeDefaults: false });
if (templates.length !== 1 || templates[0].name !== "jig" || templates[0].argumentHint !== "init") {
	console.error(templates);
	process.exit(1);
}
const expanded = expandPromptTemplate("/jig init", templates);
if (!expanded.includes("registered `jig` skill") || !expanded.includes("`init`")) {
	console.error(expanded);
	process.exit(1);
}
console.log("Pi skill and prompt loaders ok");
JS
else
	fail "pi is not on PATH; cannot validate with Pi's loaders"
fi

python3 -m unittest discover -s scripts/jig_tests -p 'test_*.py'
printf 'check-jig ok\n'

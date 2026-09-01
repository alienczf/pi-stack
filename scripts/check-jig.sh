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
	skills/jig/references/public-routes.json \
	skills/jig/references/principles-interview.md \
	skills/jig/references/PRINCIPLE.template.md \
	skills/jig/references/schemas/v2/manifest.schema.json \
	scripts/render-jig-routes.py \
	scripts/check-readme-commands.py \
	scripts/jig_tests/test_integration.py \
	scripts/jig_tests/test_jigctl.py; do
	test -f "$path" || fail "missing $path"
done

for removed in \
	skills/jig/playbooks/first-step.md \
	skills/jig/references/runtime-verification.md \
	skills/jig/references/commandments-interview.md \
	skills/jig/references/COMMANDMENTS.template.md \
	skills/jig/references/schemas/v1 \
	scripts/jig_tests/test_commandments.py \
	scripts/jig_tests/test_first_step.py \
	scripts/jig_tests/test_verification.py \
	scripts/jig_tests/fixtures/commandments-answers.json \
	scripts/jig_tests/fixtures/commandments-transcript.md; do
	test ! -e "$removed" || fail "removed Jig v1 path remains: $removed"
done

test -x bin/jig.sh || fail "bin/jig.sh must be executable"
test -x bin/jigctl.py || fail "bin/jigctl.py must be executable"
test -x scripts/render-jig-routes.py || fail "render-jig-routes.py must be executable"
test -x scripts/check-readme-commands.py || fail "check-readme-commands.py must be executable"
grep -q 'git rev-parse --show-toplevel' bin/jig.sh || fail "jig.sh must resolve the Git root"
grep -q 'disable-model-invocation: true' skills/jig/SKILL.md || fail "Jig must require explicit invocation"
grep -q -- '--skill "$create_skill"' bin/jig.sh || fail "shell route must explicitly load create-verification-skill"
grep -q 'maintain-verification-skill' install.sh || fail "installer must register maintain-verification-skill"
grep -q 'complete-configuration' skills/jig/playbooks/init.md || fail "init must complete the v2 configuration"
grep -q 'never selects' skills/jig/SKILL.md || fail "Jig must reject product improvement ownership"
if grep -qE 'commit-step-selection|prepare-step-worktree|verify-step-output|complete-step-result|begin-verification|complete-verification' bin/jigctl.py; then
	fail "Jig controller retains removed first-step or verification commands"
fi

python3 scripts/render-jig-routes.py --check
python3 scripts/check-readme-commands.py >/dev/null

python3 - <<'PY'
import ast
import importlib.util
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


skill_frontmatter, _ = frontmatter(skill)
if skill_frontmatter.get("name") != "jig" or not skill_frontmatter.get("description"):
    raise SystemExit("Jig frontmatter lacks name or description")
if skill_frontmatter.get("disable-model-invocation") != "true":
    raise SystemExit("Jig must keep disable-model-invocation true")

prompt_frontmatter, prompt_body = frontmatter(prompt)
if not prompt_frontmatter.get("description") or prompt_frontmatter.get("argument-hint") != "init":
    raise SystemExit("Jig prompt frontmatter is incomplete")
if "$ARGUMENTS" not in prompt_body or "registered `jig` skill" not in prompt_body:
    raise SystemExit("Jig prompt does not delegate arguments")

required = {
    "route", "userCommand", "trustResourceLoading", "resourceIsolation",
    "controllerLocation", "pauseResumeBehavior", "routeMismatchRecovery", "terminalState",
}
if matrix.get("schemaVersion") != 2 or len(matrix.get("routes", [])) != 3:
    raise SystemExit("public route matrix has the wrong v2 shape")
for route in matrix["routes"]:
    if set(route) != required or route["terminalState"] != "configured":
        raise SystemExit("public route contract drifted")

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

spec = importlib.util.spec_from_file_location("jigctl_check", controller)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
valid = json.loads((root / "skills/jig/references/schemas/v2/examples/manifest.valid.json").read_text())
module.validate_manifest(valid)
try:
    module.validate_manifest({"schemaVersion": 1})
except module.ValidationError as error:
    if "unsupported legacy Jig v1 campaign" not in str(error):
        raise
else:
    raise SystemExit("legacy v1 manifest was accepted")

public = [root / "README.md", root / "overlay/AGENTS.md", root / "prompts/jig.md", root / "bin/jig.sh", *sorted((root / "skills/jig").rglob("*"))]
for path in public:
    if not path.is_file():
        continue
    text = path.read_text(encoding="utf-8")
    if any(char in text for char in "–—‘’“”"):
        raise SystemExit(f"{path} contains banned Unicode punctuation")
    if re.search(r"/ho" r"me/[^/$]+/", text):
        raise SystemExit(f"{path} contains a machine-specific path")
print("jig static contract ok")
PY

bash -n bin/jig.sh install.sh scripts/check-jig.sh
python3 -m py_compile bin/jigctl.py scripts/render-jig-routes.py scripts/check-readme-commands.py scripts/jig_tests/test_integration.py scripts/jig_tests/test_jigctl.py

if command -v pi >/dev/null 2>&1; then
	cli="$(readlink -f "$(command -v pi)")"
	pkg="$(cd "$(dirname "$cli")/../.." && pwd)"
	index="$pkg/dist/index.js"
	prompts="$pkg/dist/core/prompt-templates.js"
	package_manager="$pkg/dist/core/package-manager.js"
	settings_manager="$pkg/dist/core/settings-manager.js"
	INDEX="$index" PROMPTS="$prompts" PACKAGE_MANAGER="$package_manager" SETTINGS_MANAGER="$settings_manager" ROOT="$root" node --input-type=module <<'JS'
import { mkdirSync, mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { pathToFileURL } from "node:url";
const root = process.env.ROOT;
const { loadSkills, loadSkillsFromDir } = await import(pathToFileURL(process.env.INDEX).href);
const { loadPromptTemplates, expandPromptTemplate } = await import(pathToFileURL(process.env.PROMPTS).href);
const { DefaultPackageManager } = await import(pathToFileURL(process.env.PACKAGE_MANAGER).href);
const { SettingsManager } = await import(pathToFileURL(process.env.SETTINGS_MANAGER).href);
const skillResult = loadSkillsFromDir({ dir: `${root}/skills/jig`, source: "jig-check" });
if (skillResult.diagnostics.length || skillResult.skills.length !== 1 || skillResult.skills[0].name !== "jig") {
  console.error(skillResult);
  process.exit(1);
}
const templates = loadPromptTemplates({ cwd: root, agentDir: `${root}/.missing-agent`, promptPaths: [`${root}/prompts/jig.md`], includeDefaults: false });
if (templates.length !== 1 || !expandPromptTemplate("/jig init", templates).includes("`init`")) {
  console.error(templates);
  process.exit(1);
}
const project = mkdtempSync(join(tmpdir(), "jig-principle-"));
try {
  const principleDir = join(project, ".cursor/skills/principle-repository");
  mkdirSync(principleDir, { recursive: true });
  writeFileSync(join(principleDir, "SKILL.md"), "---\nname: principle-repository\ndescription: Repository constraints.\n---\n\n# Repository Principles\n");
  const projectConfig = join(project, ".pi");
  const agentDir = join(project, ".agent");
  mkdirSync(projectConfig, { recursive: true });
  mkdirSync(agentDir, { recursive: true });
  writeFileSync(join(projectConfig, "settings.json"), '{"skills":["../.cursor/skills"]}\n');
  const settings = SettingsManager.create(project, agentDir, { projectTrusted: true });
  const packageManager = new DefaultPackageManager({ cwd: project, agentDir, settingsManager: settings });
  const resources = await packageManager.resolve();
  const skillPaths = resources.skills.filter((resource) => resource.enabled).map((resource) => resource.path);
  const loaded = loadSkills({ cwd: project, agentDir, skillPaths, includeDefaults: false });
  if (!loaded.skills.some((skill) => skill.name === "principle-repository")) {
    console.error(loaded);
    process.exit(1);
  }
} finally {
  rmSync(project, { recursive: true, force: true });
}
console.log("Pi skill and prompt loaders ok");
JS
else
	fail "pi is not on PATH; cannot validate with Pi's loaders"
fi

python3 -m unittest discover -s scripts/jig_tests -p 'test_*.py'
printf 'check-jig ok\n'

#!/usr/bin/env python3
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "scripts/fixtures/poteto-mode/SKILL.md"
NAMES = ("poteto-mode", "architect", "principle-exhaust-the-design-space")


def run(*args, cwd=ROOT, env=None, check=True):
    return subprocess.run(
        [str(arg) for arg in args], cwd=cwd, env=env,
        check=check, text=True, capture_output=True,
    )


def snapshot(root):
    return {str(path.relative_to(root)): path.read_bytes()
            for path in root.rglob("*") if path.is_file()}


class SkillOverlays(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.pstack = self.base / "pstack"
        names = run("bash", ROOT / "install.sh", "--print-pstack-skills").stdout.splitlines()
        for name in names:
            skill = self.pstack / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {name}\ndescription: Upstream fixture.\n---\n\n# Upstream fixture\n"
            )
        shutil.copyfile(FIXTURE, self.pstack / "skills/poteto-mode/SKILL.md")
        for name, folder, filename in (
            ("poteto-mode", "playbooks", "investigation.md"),
            ("architect", "references", "runner-prompt.md"),
        ):
            refs = self.pstack / "skills" / name / folder
            refs.mkdir()
            (refs / filename).write_text("Upstream supporting file.\n")
        self.out = self.base / "out"

    def conform(self, *extra, overlays=True, out=None, check=True):
        args = ["python3", ROOT / "bin/conform-skills.py", "--out", out or self.out]
        if overlays:
            args.extend(["--overlays", ROOT / "overlay/skills"])
        args.extend(self.pstack / "skills" / name for name in NAMES)
        return run(*args, *extra, check=check)

    def assert_policy(self, out):
        poteto = (out / "poteto-mode/SKILL.md").read_text()
        self.assertIn("Keep this unrelated instruction unchanged.", poteto)
        self.assertIn("Use same-model children only for disjoint workstreams", poteto)
        self.assertIn("Do not fan out across model types.", poteto)
        self.assertIn("let the parent pick if needed, then implement.", poteto)
        self.assertIn("Sequential or parent-inline sketches with one model are sufficient.", poteto)
        self.assertIn("Use the parent's model for every child.", poteto)
        for forbidden in ("**arena**", "**swarm**", "multi-model", "diverse-model",
                          "2-3 competing", "different model", "grok-", "claude-", "gpt-"):
            self.assertNotIn(forbidden, poteto)
        architect = (out / "architect/SKILL.md").read_text()
        self.assertIn("Start with one sketch.", architect)
        self.assertIn("the parent compares their evidence and picks one", architect)
        self.assertIn("Same-model parallel work is allowed for disjoint implementation workstreams.", architect)
        for forbidden in ("arena", "runner-prompt", "rationale-template", "Design it twice", "interrogate"):
            self.assertNotIn(forbidden, architect)
        self.assertFalse((out / "architect/references").exists())
        principle = (out / "principle-exhaust-the-design-space/SKILL.md").read_text()
        self.assertIn("Sequential or parent-inline sketches with one model are sufficient.", principle)
        self.assertNotIn("2-3", principle)
        self.assertIn("Same-model parallel work is allowed for disjoint workstreams.", principle)
        for name in NAMES:
            path = out / name / "SKILL.md"
            text = path.read_text()
            self.assertRegex(text, rf"(?m)^name: {name}$")
            self.assertRegex(text, r"(?m)^description: .+$")
            for link in re.findall(r"\]\(([^)]+)\)", text):
                self.assertTrue((path.parent / link).exists(), link)
        self.assertTrue((out / "poteto-mode/playbooks").is_symlink())
        self.assertEqual((out / "poteto-mode/playbooks/investigation.md").read_text(), "Upstream supporting file.\n")

    def test_replacement_patch_migration_and_idempotence(self):
        original = snapshot(self.pstack)
        self.conform(overlays=False)
        self.assertTrue((self.out / "architect/references").is_symlink())
        self.conform()
        self.assert_policy(self.out)
        installed = snapshot(self.out)
        self.conform()
        self.assertEqual(snapshot(self.out), installed)
        self.assertEqual(snapshot(self.pstack), original)

    def test_missing_or_duplicate_patch_anchor_leaves_installed_skill_unchanged(self):
        self.conform()
        installed = snapshot(self.out)
        path = self.pstack / "skills/poteto-mode/SKILL.md"
        original = path.read_text()
        anchor = "A second opinion is the same prompt against a different model. Agreement is high-signal."
        for changed in (original.replace(anchor, "Upstream changed this rule."), original + anchor):
            with self.subTest(changed=changed[-100:]):
                path.write_text(changed)
                result = self.conform(check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("overlay drift", result.stderr)
                self.assertEqual(snapshot(self.out), installed)
                self.assertEqual(path.read_text(), changed)

    def test_source_symlink_is_not_written_through(self):
        original = snapshot(self.pstack)
        dest = self.out / "poteto-mode"
        dest.mkdir(parents=True)
        (dest / "SKILL.md").symlink_to(self.pstack / "skills/poteto-mode/SKILL.md")
        self.conform()
        self.assertFalse((dest / "SKILL.md").is_symlink())
        self.assertEqual(snapshot(self.pstack), original)
        self.assert_policy(self.out)

    def test_replacement_refuses_in_place_output(self):
        original = snapshot(self.pstack)
        for output in (self.pstack / "skills", ROOT / "overlay/skills"):
            with self.subTest(output=output):
                result = run("python3", ROOT / "bin/conform-skills.py", "--out", output,
                             "--overlays", ROOT / "overlay/skills", self.pstack / "skills/architect",
                             check=False)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("in-place", result.stderr)
        self.assertEqual(snapshot(self.pstack), original)

    def test_real_install_and_update_reapply_overlays(self):
        stack = self.base / "pi-stack"
        stack.mkdir()
        for name in ("bin", "overlay", "prompts", "skills"):
            shutil.copytree(ROOT / name, stack / name, ignore=shutil.ignore_patterns("__pycache__"))
        shutil.copyfile(ROOT / "install.sh", stack / "install.sh")
        (stack / ".gitignore").write_text("__pycache__/\n")
        run("git", "init", "-q", "-b", "main", stack)
        run("git", "add", ".", cwd=stack)
        run("git", "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-qm", "fixture", cwd=stack)
        upstream = self.base / "upstream"
        upstream.mkdir()
        shutil.copytree(self.pstack, upstream / "pstack")
        manifest = upstream / "pstack/.cursor-plugin/plugin.json"
        manifest.parent.mkdir()
        manifest.write_text('{"name":"pstack","version":"0.1.0"}\n')
        run("git", "init", "-q", "-b", "main", upstream)
        run("git", "add", ".", cwd=upstream)
        run("git", "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-qm", "fixture", cwd=upstream)
        plugins = self.base / "plugins"
        run("git", "clone", "-q", upstream, plugins)
        home = self.base / "home"
        env = {**os.environ, "HOME": str(home), "PI_STACK": str(stack),
               "PSTACK": str(plugins / "pstack"), "PI_STACK_SKIP_PACKAGES": "1"}
        original = snapshot(plugins / "pstack")
        run("bash", stack / "install.sh", env=env)
        agent = home / ".pi/agent"
        installed = agent / "skills-pstack"
        self.assert_policy(installed)
        self.assertEqual(snapshot(plugins / "pstack"), original)
        settings = json.loads((agent / "settings.json").read_text())
        for name in NAMES:
            self.assertIn(str(installed / name), settings["skills"])
        for entry in ("APPEND_SYSTEM.md", "prompts/poteto.md", "agents/poteto-agent.md"):
            text = (agent / entry).read_text()
            self.assertIn(str(installed / "poteto-mode/SKILL.md"), text)
            self.assertNotIn(str(plugins / "pstack"), text)
            self.assertNotIn("__SKILLS_PSTACK__", text)
        self.assertIn("Do not fan out across model types", (agent / "AGENTS.md").read_text())
        expected = snapshot(installed)
        self.out = installed
        self.conform(overlays=False)
        self.assertTrue((installed / "architect/references").is_symlink())
        manifest.write_text('{"name":"pstack","version":"0.2.0"}\n')
        run("git", "add", ".", cwd=upstream)
        run("git", "-c", "user.name=test", "-c", "user.email=test@example.com",
            "commit", "-qm", "refresh", cwd=upstream)
        updater = home / ".local/bin/update-pstack"
        plan = json.loads(run(updater, "status", env=env).stdout)
        args = ("apply", "--expected-pi-stack", plan["piStack"]["revision"],
                "--expected-current", plan["pstack"]["currentRevision"],
                "--expected-upstream", plan["pstack"]["upstreamRevision"])
        run(updater, *args, env=env)
        self.assert_policy(installed)
        self.assertEqual(snapshot(installed), expected)
        self.assertEqual(snapshot(plugins / "pstack"), snapshot(upstream / "pstack"))
        owned = snapshot(agent)
        run(updater, *args, env=env)
        self.assertEqual(snapshot(agent), owned)
        self.assertEqual(run("git", "status", "--porcelain", cwd=plugins).stdout, "")
        self.assertEqual(run("git", "status", "--porcelain", cwd=stack).stdout, "")


if __name__ == "__main__":
    unittest.main()

import hashlib
import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.jig_tests import test_jigctl

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.sh"
MATRIX = ROOT / "skills" / "jig" / "references" / "public-routes.json"


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.pstack = self.base / "pstack"
        for name, title in (
            ("poteto-mode", "Poteto Mode"),
            ("create-verification-skill", "create-verification-skill"),
            ("maintain-verification-skill", "maintain-verification-skill"),
        ):
            skill = self.pstack / "skills" / name
            skill.mkdir(parents=True)
            (skill / "SKILL.md").write_text(
                f"---\nname: {title}\ndescription: fixture {name}\n---\n\n# Fixture\n",
                encoding="utf-8",
            )

    def tearDown(self):
        self.temporary.cleanup()

    def install(self, home):
        return subprocess.run(
            ["bash", str(INSTALLER)],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "PI_STACK": str(ROOT),
                "PSTACK": str(self.pstack),
                "PI_STACK_SKIP_PACKAGES": "1",
            },
        )

    def init_repo(self, path):
        path.mkdir(parents=True)
        (path / "README.md").write_text("# Fixture\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(path)], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.email", "jig@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(path), "config", "user.name", "Jig Fixture"], check=True)
        subprocess.run(["git", "-C", str(path), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(path), "commit", "-qm", "fixture"], check=True)

    def profile_stub(self, path):
        path.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, subprocess, sys\n"
            "open(os.environ['JIG_ARGV_RECEIPT'], 'w').write(json.dumps(sys.argv[1:]))\n"
            "revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
            "evidence = [{'path': 'README.md', 'line': 1, 'note': 'Fixture.'}]\n"
            "profile = {'schemaVersion': 2, 'repositoryRevision': revision, "
            "'productType': {'value': 'fixture', 'evidence': evidence}, "
            "'entryPoints': [], 'existingPolicies': [], 'unknowns': []}\n"
            "result = subprocess.run([sys.executable, os.environ['JIG_CONTROLLER'], 'commit-profile', "
            "'--resource-isolation', os.environ['JIG_RESOURCE_ISOLATION']], input=json.dumps(profile), text=True)\n"
            "raise SystemExit(result.returncode)\n",
            encoding="utf-8",
        )
        path.chmod(0o755)

    def owned_digest(self, home):
        roots = [
            home / ".pi/agent/jig",
            home / ".pi/agent/bin/jig",
            home / ".pi/agent/skills-pstack/jig/SKILL.md",
            home / ".pi/agent/prompts/jig.md",
        ]
        result = {}
        for root in roots:
            paths = sorted(path for path in root.rglob("*") if path.is_file()) if root.is_dir() else [root]
            for path in paths:
                result[path.relative_to(home).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def test_public_route_matrix_owns_generated_docs(self):
        document = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual(document["schemaVersion"], 2)
        self.assertEqual([route["userCommand"] for route in document["routes"]], [
            "jig init", "/skill:jig init", "/jig init",
        ])
        self.assertEqual({route["terminalState"] for route in document["routes"]}, {"configured"})
        checked = subprocess.run(
            ["python3", str(ROOT / "scripts/render-jig-routes.py"), "--check"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_install_twice_is_self_contained_and_removes_stale_jig_files(self):
        home = self.base / "home"
        settings = home / ".pi/agent/settings.json"
        settings.parent.mkdir(parents=True)
        settings.write_text(json.dumps({
            "defaultProjectTrust": "ask",
            "theme": "keep",
            "packages": ["npm:keep-me"],
        }), encoding="utf-8")
        first = self.install(home)
        self.assertEqual(first.returncode, 0, first.stderr)
        first_digest = self.owned_digest(home)
        second = self.install(home)
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(self.owned_digest(home), first_digest)
        installed_settings = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(installed_settings["defaultProjectTrust"], "ask")
        self.assertEqual(installed_settings["theme"], "keep")
        self.assertIn("npm:keep-me", installed_settings["packages"])
        skills = installed_settings["skills"]
        self.assertTrue(any("create-verification-skill" in path for path in skills))
        self.assertTrue(any("maintain-verification-skill" in path for path in skills))
        stale = home / ".pi/agent/jig/skills/jig/playbooks/first-step.md"
        stale.parent.mkdir(parents=True, exist_ok=True)
        stale.write_text("stale\n", encoding="utf-8")
        third = self.install(home)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertFalse(stale.exists())
        installed = home / ".pi/agent/jig"
        source_bytes = str(ROOT).encode()
        for path in installed.rglob("*"):
            if path.is_file():
                self.assertNotIn(source_bytes, path.read_bytes(), path)

    def test_installed_shell_route_loads_only_jig_and_pstack_generator_then_pauses(self):
        home = self.base / "shell-home"
        home.mkdir()
        installed = self.install(home)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        repo = self.base / "shell-repo"
        self.init_repo(repo)
        (repo / "AGENTS.md").write_text("untrusted target context\n", encoding="utf-8")
        (repo / ".pi/skills/untrusted").mkdir(parents=True)
        (repo / ".pi/settings.json").write_text("{}\n", encoding="utf-8")
        subdirectory = repo / "packages/example"
        subdirectory.mkdir(parents=True)
        stub = self.base / "pi-stub.py"
        receipt = self.base / "argv.json"
        self.profile_stub(stub)
        result = subprocess.run(
            [str(home / ".local/bin/jig"), "init"],
            cwd=subdirectory,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={
                **os.environ,
                "HOME": str(home),
                "PI": str(stub),
                "JIG_ARGV_RECEIPT": str(receipt),
                "JIG_PI_VERSION": "fixture-pi",
            },
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(receipt.read_text(encoding="utf-8"))
        jig_skill = str(home / ".pi/agent/jig/skills/jig/SKILL.md")
        create_skill = str(home / ".pi/agent/skills-pstack/create-verification-skill/SKILL.md")
        self.assertEqual(argv.count("--skill"), 2)
        self.assertIn(jig_skill, argv)
        self.assertIn(create_skill, argv)
        self.assertIn("--no-context-files", argv)
        self.assertIn("--no-extensions", argv)
        self.assertNotIn("--extension", argv)
        self.assertNotIn(str(repo / "AGENTS.md"), argv)
        manifest = json.loads((repo / ".pi/jig/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["schemaVersion"], 2)
        self.assertEqual(manifest["resourceIsolation"], "isolated-shell")
        self.assertEqual(manifest["currentState"], "awaiting-principles")
        self.assertIn("awaiting one complete repository Principles", result.stdout)

    def test_shell_route_rejects_manifest_symlinks_before_reading_them(self):
        home = self.base / "unsafe-shell-home"
        home.mkdir()
        installed = self.install(home)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        repo = self.base / "unsafe-shell-repo"
        self.init_repo(repo)
        outside = self.base / "outside-manifest.json"
        outside.write_text('{"resourceIsolation":"isolated-shell"}\n', encoding="utf-8")
        manifest = repo / ".pi/jig/manifest.json"
        manifest.parent.mkdir(parents=True)
        manifest.symlink_to(outside)
        result = subprocess.run(
            [str(home / ".local/bin/jig"), "init"],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "HOME": str(home), "PI": "/bin/false"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("manifest path is unsafe", result.stderr)
        self.assertEqual(outside.read_text(encoding="utf-8"), '{"resourceIsolation":"isolated-shell"}\n')


    def test_complete_fixture_has_no_product_diff_and_reaches_configured(self):
        case = test_jigctl.JigControllerTest(methodName="runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        case.ratify()
        verification = case.write_verification_skill()
        case.output(
            case.ctl(
                "complete-configuration",
                input_value={"schemaVersion": 2, "verificationSkillPath": verification.relative_to(case.repo).as_posix()},
            )
        )
        manifest = case.manifest()
        self.assertEqual(manifest["currentState"], "configured")
        self.assertNotIn("firstStep", manifest)
        changed = subprocess.check_output(
            ["git", "-C", str(case.repo), "status", "--short", "--", ":!/.pi", ":!/.cursor"],
            text=True,
        )
        self.assertEqual(changed, "")


if __name__ == "__main__":
    unittest.main()

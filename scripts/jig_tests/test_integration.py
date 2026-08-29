import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.jig_tests import test_first_step

ROOT = Path(__file__).resolve().parents[2]
INSTALLER = ROOT / "install.sh"
CONTROLLER = ROOT / "bin" / "jigctl.py"
MATRIX = ROOT / "skills" / "jig" / "references" / "public-routes.json"


class IntegrationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.base = Path(self.temporary.name)
        self.pstack = self.base / "pstack"
        skill = self.pstack / "skills" / "poteto-mode"
        skill.mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            "---\nname: Poteto Mode\ndescription: fixture\n---\n\n# Fixture\n",
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
            "profile = {'schemaVersion': 1, 'repositoryRevision': revision, "
            "'productType': {'value': 'fixture', 'evidence': [{'path': 'README.md', 'line': 1, 'note': 'Fixture.'}]}, "
            "'languages': [], 'frameworks': [], 'buildTools': [], 'ci': [], 'entryPoints': [], "
            "'topology': [], 'unknowns': [], 'failureModes': []}\n"
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
                relative = path.relative_to(home).as_posix()
                result[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
        return result

    def test_public_route_matrix_owns_generated_docs(self):
        document = json.loads(MATRIX.read_text(encoding="utf-8"))
        self.assertEqual(document["schemaVersion"], 1)
        self.assertEqual([route["userCommand"] for route in document["routes"]], [
            "jig init", "/skill:jig init", "/jig init",
        ])
        required = {
            "route", "userCommand", "trustResourceLoading", "resourceIsolation",
            "controllerLocation", "pauseResumeBehavior", "routeMismatchRecovery", "terminalState",
        }
        for route in document["routes"]:
            self.assertEqual(set(route), required)
        checked = subprocess.run(
            ["python3", str(ROOT / "scripts/render-jig-routes.py"), "--check"],
            cwd=ROOT,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(checked.returncode, 0, checked.stderr)

    def test_install_twice_is_self_contained_and_preserves_settings(self):
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
        stale = home / ".pi/agent/jig/stale.txt"
        stale.write_text("stale\n", encoding="utf-8")
        third = self.install(home)
        self.assertEqual(third.returncode, 0, third.stderr)
        self.assertFalse(stale.exists())
        installed = home / ".pi/agent/jig"
        source_bytes = str(ROOT).encode()
        for path in installed.rglob("*"):
            if path.is_file():
                self.assertNotIn(source_bytes, path.read_bytes(), path)
        self.assertNotIn(source_bytes, (home / ".pi/agent/bin/jig").read_bytes())
        installed_text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in installed.rglob("*")
            if path.is_file() and path.suffix in {".md", ".json", ".sh"}
        )
        self.assertIsNone(re.search(
            r"--apply|--force|--iterate|already fitted|cold[- ]agent|refactor\.md\.draft",
            installed_text,
            re.IGNORECASE,
        ))

    def test_fresh_install_does_not_set_project_trust(self):
        home = self.base / "fresh-home"
        home.mkdir()
        installed = self.install(home)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        settings = json.loads((home / ".pi/agent/settings.json").read_text(encoding="utf-8"))
        self.assertNotIn("defaultProjectTrust", settings)

    def test_installed_shell_route_pins_resources_and_pauses(self):
        home = self.base / "shell-home"
        home.mkdir()
        installed = self.install(home)
        self.assertEqual(installed.returncode, 0, installed.stderr)
        extension = home / ".pi/agent/npm/node_modules/pi-subagents/index.ts"
        extension.parent.mkdir(parents=True)
        extension.write_text("export default function () {}\n", encoding="utf-8")
        repo = self.base / "shell-repo"
        self.init_repo(repo)
        (repo / "AGENTS.md").write_text("untrusted target context\n", encoding="utf-8")
        (repo / ".pi/skills/untrusted").mkdir(parents=True)
        (repo / ".pi/prompts").mkdir()
        (repo / ".pi/extensions").mkdir()
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
        expected = [
            "--no-approve", "--no-session", "--no-context-files", "--no-extensions",
            "--no-prompt-templates", "--no-skills", "--skill",
            str(home / ".pi/agent/jig/skills/jig/SKILL.md"), "--extension", str(extension),
            "--no-themes", "--system-prompt",
            "You are Pi in a human-started isolated Jig campaign. Load and follow the explicit Jig skill.",
            "--append-system-prompt", "", "--tools",
            "read,grep,find,ls,bash,write,edit,subagent,subagent_wait", "--",
        ]
        self.assertEqual(argv[:-1], expected)
        self.assertNotIn("-p", argv)
        self.assertNotIn(str(repo / "AGENTS.md"), argv)
        manifest = json.loads((repo / ".pi/jig/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["resourceIsolation"], "isolated-shell")
        self.assertEqual(manifest["currentState"], "awaiting-commandments")
        self.assertIn("awaiting the target operator COMMANDMENTS", result.stdout)

    def test_route_mismatch_refuses_before_nested_process(self):
        home = self.base / "mismatch-home"
        home.mkdir()
        self.assertEqual(self.install(home).returncode, 0)
        repo = self.base / "mismatch-repo"
        self.init_repo(repo)
        marker = self.base / "nested.marker"
        stub = self.base / "must-not-run.sh"
        stub.write_text(f"#!/usr/bin/env bash\ntouch {marker}\n", encoding="utf-8")
        stub.chmod(0o755)
        started = subprocess.run(
            ["python3", str(home / ".pi/agent/jig/bin/jigctl.py"), "start", "--resource-isolation", "inherited-session"],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PI": str(stub), "JIG_PI_VERSION": "fixture-pi"},
        )
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertFalse(marker.exists())
        mismatch = subprocess.run(
            [str(home / ".local/bin/jig"), "init"],
            cwd=repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "HOME": str(home), "PI": str(stub)},
        )
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertFalse(marker.exists())
        self.assertIn("/skill:jig init or /jig init", mismatch.stderr)
        manifest = json.loads((repo / ".pi/jig/manifest.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["resourceIsolation"], "inherited-session")

    def test_complete_primary_fixture_reaches_one_kept_result(self):
        case = test_first_step.FirstStepTest(methodName="runTest")
        case.setUp()
        self.addCleanup(case.tearDown)
        _worktree, _worker, output = case.proved_candidate()
        verdict = case.ctl("commit-step-verdict", input_value=case.verdict_draft(output))
        self.assertEqual(verdict.returncode, 0, verdict.stderr)
        prepared = case.ctl("prepare-step-result")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        completed = case.ctl("complete-step-result")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        manifest = case.manifest()
        result = json.loads((case.repo / ".pi/jig/steps/0001/result.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["currentState"], "initialized")
        self.assertEqual(manifest["firstStep"]["outcome"], "kept")
        self.assertEqual(result["outcome"], "kept")
        self.assertEqual(result["independentVerdict"]["status"], "passed")
        self.assertTrue((case.repo / result["worktree"]).is_dir())
        generated_text = "\n".join(
            path.read_text(encoding="utf-8")
            for base in (case.repo / ".pi/skills", case.repo / ".pi/jig")
            for path in base.rglob("*")
            if path.is_file()
        )
        self.assertNotIn(str(ROOT), generated_text)
        self.assertNotIn(str(self.pstack), generated_text)
        self.assertIsNone(re.search(
            r"--apply|--force|--iterate|already fitted|cold[- ]agent|refactor\.md\.draft",
            generated_text,
            re.IGNORECASE,
        ))


if __name__ == "__main__":
    unittest.main()

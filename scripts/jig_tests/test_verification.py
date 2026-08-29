import importlib.util
import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "bin" / "jigctl.py"
FIXTURE = ROOT / "scripts" / "jig_tests" / "fixtures" / "runtime-app"
ANSWERS = ROOT / "scripts" / "jig_tests" / "fixtures" / "commandments-answers.json"

spec = importlib.util.spec_from_file_location("jigctl_verification", CONTROLLER)
jigctl = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(jigctl)


class VerificationTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        for name in ("app.py", "client.py", "test_weak.py"):
            shutil.copy2(FIXTURE / name, self.repo / name)
        self.git("init", "-q")
        self.git("config", "user.email", "jig@example.invalid")
        self.git("config", "user.name", "Jig Fixture")
        self.git("add", "app.py", "client.py", "test_weak.py")
        self.git("commit", "-qm", "fixture")
        self.answers = json.loads(ANSWERS.read_text(encoding="utf-8"))
        self.answers["protectedUserPath"] = {
            "selection": "custom",
            "value": {
                "action": "Run python3 client.py add --title \"Release\" --body \"Ship it\" using the launched fixture.",
                "visibleResult": "The public list command returns the saved Release note.",
                "evidence": "Capture the add command, list output, and persisted notes.json bytes.",
                "cleanup": "Stop only the exact process recorded by the verification run and remove its disposable data.",
                "thresholds": "Complete within five seconds.",
            },
        }
        self.prepare_ratified()

    def tearDown(self):
        state = self.repo / ".pi/jig/verification/runtime/state.json"
        if state.exists():
            try:
                value = json.loads(state.read_text())
                os.kill(value["pid"], signal.SIGKILL)
            except (OSError, ValueError, KeyError):
                pass
        self.temporary.cleanup()

    def git(self, *arguments):
        return subprocess.run(["git", "-C", str(self.repo), *arguments], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True).stdout

    def ctl(self, *arguments, input_value=None):
        return subprocess.run(
            [sys.executable, str(CONTROLLER), *arguments, "--resource-isolation", "isolated-shell"],
            cwd=self.repo,
            input=None if input_value is None else json.dumps(input_value),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi"},
        )

    def manifest(self):
        return json.loads((self.repo / ".pi/jig/manifest.json").read_text())

    def prepare_ratified(self):
        self.assertEqual(self.ctl("start").returncode, 0)
        revision = self.git("rev-parse", "HEAD").strip()
        profile = {
            "schemaVersion": 1,
            "repositoryRevision": revision,
            "productType": {"value": "desktop-style process fixture", "evidence": [{"path": "app.py", "line": 1, "note": "Long-lived application process."}]},
            "languages": [{"value": "Python", "evidence": [{"path": "app.py", "line": 1, "note": "Runtime."}]}],
            "frameworks": [],
            "buildTools": [],
            "ci": [],
            "entryPoints": [{"value": "client.py", "evidence": [{"path": "client.py", "line": 1, "note": "Public command."}]}],
            "topology": [],
            "unknowns": [],
            "failureModes": [],
        }
        self.assertEqual(self.ctl("commit-profile", input_value=profile).returncode, 0)
        self.assertEqual(self.ctl("present-commandments").returncode, 0)
        staged = self.ctl("stage-commandments", input_value=self.answers)
        self.assertEqual(staged.returncode, 0, staged.stderr)
        value = json.loads(staged.stdout)
        ratified = self.ctl("ratify-commandments", "--candidate-sha", value["candidateSha256"], "--operator-marker", value["intendedMarker"])
        self.assertEqual(ratified.returncode, 0, ratified.stderr)

    def plan(self, timeout=15):
        revision = self.git("rev-parse", "HEAD").strip()
        feature_ids = ["create-note", "list-notes", "search-notes"]
        feature_paths = [f".pi/skills/jig-verification/references/features/{item}.md" for item in feature_ids]
        helpers = [".pi/skills/jig-verification/helpers/fixture-control.py"]
        return {
            "schemaVersion": 1,
            "kind": "verification-plan",
            "sourceRevision": revision,
            "commandmentsSha256": self.manifest()["commandments"]["sha256"],
            "protectedUserPath": self.answers["protectedUserPath"]["value"],
            "protectedFeatureId": "create-note",
            "skillPath": ".pi/skills/jig-verification/SKILL.md",
            "featureIndexPath": ".pi/skills/jig-verification/references/features/index.md",
            "featureIds": feature_ids,
            "featurePaths": feature_paths,
            "helperPaths": helpers,
            "selfTestCommand": ["python3", helpers[0], "self-test"],
            "timeoutSeconds": timeout,
            "cleanupOwner": "fixture-control.py PID plus Linux process start identity",
            "reservedPaths": [".pi/skills/jig-verification/SKILL.md", ".pi/skills/jig-verification/references/features/index.md", *feature_paths, *helpers],
        }

    def begin(self, plan=None):
        result = self.ctl("begin-verification", input_value=self.plan() if plan is None else plan)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def install_generated(self):
        target = self.repo / ".pi/skills/jig-verification"
        (target / "references/features").mkdir(parents=True, exist_ok=True)
        (target / "helpers").mkdir(parents=True, exist_ok=True)
        shutil.copy2(FIXTURE / "generated/SKILL.md", target / "SKILL.md")
        shutil.copy2(FIXTURE / "generated/index.md", target / "references/features/index.md")
        for feature in ("create-note", "list-notes", "search-notes"):
            shutil.copy2(FIXTURE / f"generated/{feature}.md", target / f"references/features/{feature}.md")
        shutil.copy2(FIXTURE / "generated/fixture-control.py", target / "helpers/fixture-control.py")
        (target / "helpers/fixture-control.py").chmod(0o755)

    def test_documented_manual_phases_compose(self):
        self.begin()
        self.install_generated()
        helper = self.repo / ".pi/skills/jig-verification/helpers/fixture-control.py"
        completed = {}
        snapshots = {}
        for command in ("launch", "doctor", "drive", "evidence", "cleanup"):
            completed[command] = subprocess.run(
                [sys.executable, str(helper), command],
                cwd=self.repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(completed[command].returncode, 0, completed[command].stderr)
            if command == "launch":
                launched = json.loads(completed[command].stdout)
                notes_path = Path(launched["dataDir"]) / "notes.json"
            elif command in ("drive", "evidence"):
                snapshots[command] = json.loads(notes_path.read_text())

        driven = json.loads(completed["drive"].stdout)
        artifacts = json.loads(completed["evidence"].stdout)
        evidence_root = self.repo / ".pi/jig/verification/evidence"
        action = json.loads((evidence_root / "protected-action.json").read_text())
        result = json.loads((evidence_root / "protected-result.json").read_text())

        self.assertEqual(driven["listed"], [{"body": "Ship it", "id": 1, "title": "Release"}])
        self.assertEqual(snapshots["drive"], driven["persisted"])
        self.assertEqual(snapshots["evidence"], snapshots["drive"])
        self.assertEqual(action["command"], ["python3", "client.py", "add", "--title", "Release", "--body", "Ship it"])
        self.assertEqual(result["observed"], driven["listed"])
        self.assertEqual(result["persisted"], driven["persisted"])
        self.assertEqual(len(artifacts), 2)
        self.assertFalse((self.repo / ".pi/jig/verification/runtime").exists())
        self.assertFalse((Path("/proc") / str(launched["pid"])).exists())
        self.assertTrue(all((self.repo / artifact["path"]).exists() for artifact in artifacts))


    def test_real_runtime_reaches_ready_and_preserves_evidence(self):
        started = self.begin()
        self.assertEqual(started["state"], "verification-building")
        self.assertFalse((self.repo / ".pi/skills/jig-verification").exists())
        self.install_generated()
        unrelated = subprocess.Popen(["sleep", "30"])
        try:
            completed = self.ctl("complete-verification")
            self.assertEqual(completed.returncode, 0, completed.stderr)
            self.assertIsNone(unrelated.poll())
            manifest = self.manifest()
            self.assertEqual(manifest["currentState"], "verification-ready")
            self.assertEqual(len(manifest["verification"]), 1)
            action = json.loads((self.repo / ".pi/jig/verification/evidence/protected-action.json").read_text())
            result = json.loads((self.repo / ".pi/jig/verification/evidence/protected-result.json").read_text())
            self.assertEqual(action["kind"], "protected-action")
            self.assertEqual(result["persisted"][0]["body"], "Ship it")
            self.assertFalse((self.repo / ".pi/jig/verification/runtime").exists())
            self.assertEqual(self.ctl("validate-verification").returncode, 0)
        finally:
            unrelated.terminate()
            unrelated.wait()

    def test_unregistered_state_does_not_authorize_exception_cleanup(self):
        self.begin()
        self.install_generated()
        unrelated = subprocess.Popen(["sleep", "30"])
        try:
            raw = (Path("/proc") / str(unrelated.pid) / "stat").read_text()
            process_start = raw[raw.rfind(")") + 2:].split()[19]
            state = self.repo / ".pi/jig/verification/runtime/state.json"
            state.parent.mkdir(parents=True)
            unknown = (json.dumps({"pid": unrelated.pid, "processStart": process_start, "unknown": "preserve"}, indent=2) + "\n").encode()
            state.write_bytes(unknown)

            completed = self.ctl("complete-verification")

            self.assertNotEqual(completed.returncode, 0)
            self.assertEqual(self.manifest()["currentState"], "verification-building")
            self.assertIsNone(unrelated.poll())
            self.assertEqual(state.read_bytes(), unknown)
        finally:
            if unrelated.poll() is None:
                unrelated.terminate()
            unrelated.wait()


    def test_plan_precedes_generation_and_partial_state_does_not_advance(self):
        conflict = self.repo / ".pi/skills/jig-verification"
        conflict.mkdir(parents=True)
        (conflict / "unknown").write_text("preserve\n")
        rejected = self.ctl("begin-verification", input_value=self.plan())
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual((conflict / "unknown").read_text(), "preserve\n")
        shutil.rmtree(self.repo / ".pi/skills")
        self.begin()
        target = self.repo / ".pi/skills/jig-verification"
        target.mkdir(parents=True)
        shutil.copy2(FIXTURE / "generated/SKILL.md", target / "SKILL.md")
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(json.loads(resumed.stdout)["state"], "verification-building")
        failed = self.ctl("complete-verification")
        self.assertNotEqual(failed.returncode, 0)
        self.assertEqual(self.manifest()["currentState"], "verification-building")

    def test_map_drift_and_unrelated_source_drift_fail_closed(self):
        self.begin()
        self.install_generated()
        protected = self.repo / ".pi/skills/jig-verification/references/features/create-note.md"
        original = protected.read_text()
        protected.write_text(original.replace("The public list command returns the saved Release note.", "Wrong result."))
        self.assertNotEqual(self.ctl("complete-verification").returncode, 0)
        protected.write_text(original)
        unrelated = self.repo / "unrelated.txt"
        unrelated.write_text("drift\n")
        start = self.ctl("start")
        self.assertNotEqual(start.returncode, 0)
        unrelated.unlink()
        self.assertEqual(self.ctl("complete-verification").returncode, 0)
        protected.write_text(original + "changed\n")
        self.assertNotEqual(self.ctl("validate-verification").returncode, 0)

    def test_interrupted_owned_process_cleanup_and_retry(self):
        self.begin()
        self.install_generated()
        helper = self.repo / ".pi/skills/jig-verification/helpers/fixture-control.py"
        launched = subprocess.run([sys.executable, str(helper), "launch"], cwd=self.repo, check=True, text=True, stdout=subprocess.PIPE)
        state = json.loads(launched.stdout)
        os.kill(state["pid"], signal.SIGKILL)
        for _ in range(50):
            if not (Path("/proc") / str(state["pid"])).exists():
                break
            time.sleep(0.02)
        cleanup = subprocess.run([sys.executable, str(helper), "cleanup"], cwd=self.repo)
        self.assertEqual(cleanup.returncode, 0)
        self.assertEqual(self.ctl("complete-verification").returncode, 0)

    def test_invalid_plan_and_timeout_cannot_reach_ready(self):
        wrong = self.plan()
        wrong["protectedUserPath"] = dict(wrong["protectedUserPath"], visibleResult="Invented")
        before = (self.repo / ".pi/jig/manifest.json").read_bytes()
        self.assertNotEqual(self.ctl("begin-verification", input_value=wrong).returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), before)
        plan = self.plan(timeout=2)
        self.begin(plan)
        self.install_generated()
        helper = self.repo / ".pi/skills/jig-verification/helpers/fixture-control.py"
        helper.write_text("#!/usr/bin/env python3\nimport time\ntime.sleep(20)\n")
        helper.chmod(0o755)
        timed = self.ctl("complete-verification")
        self.assertNotEqual(timed.returncode, 0)
        self.assertIn("timed out", timed.stderr)
        self.assertEqual(self.manifest()["currentState"], "verification-building")


    def test_transition_crashes_and_failed_state_recover(self):
        plan = self.plan()
        with mock.patch.object(jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                jigctl.begin_verification(
                    self.repo, "isolated-shell", json.dumps(plan).encode()
                )
        self.assertEqual(self.manifest()["currentState"], "commandments-ratified")
        self.assertEqual(self.ctl("start").returncode, 0)
        self.begin(plan)
        self.install_generated()
        with mock.patch.object(jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                jigctl.complete_verification(self.repo, "isolated-shell")
        self.assertEqual(self.manifest()["currentState"], "verification-building")
        self.assertEqual(self.ctl("start").returncode, 0)
        completed = self.ctl("complete-verification")
        self.assertEqual(completed.returncode, 0, completed.stderr)
        runtime_files = list((self.repo / ".pi/jig/verification/receipts").glob("runtime-*.json"))
        registered = {item["path"] for item in self.manifest()["artifacts"]}
        self.assertTrue(runtime_files)
        self.assertTrue(all(path.relative_to(self.repo).as_posix() in registered for path in runtime_files))

    def test_fake_success_extra_file_and_failed_state_cannot_advance(self):
        self.begin()
        self.install_generated()
        helper = self.repo / ".pi/skills/jig-verification/helpers/fixture-control.py"
        helper.write_text(
            "#!/usr/bin/env python3\n"
            "import json\n"
            "print(json.dumps({'schemaVersion': 1, 'kind': 'verification-self-test'}))\n"
        )
        helper.chmod(0o755)
        fake = self.ctl("complete-verification")
        self.assertNotEqual(fake.returncode, 0)
        self.assertEqual(self.manifest()["currentState"], "verification-building")
        self.install_generated()
        extra = self.repo / ".pi/skills/jig-verification/extra.md"
        extra.write_text("unknown\n")
        self.assertNotEqual(self.ctl("complete-verification").returncode, 0)
        extra.unlink()
        failed = self.ctl(
            "record-failure",
            "--state",
            "verification-building",
            "--reason",
            "seeded verification failure",
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-verification-building")
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual(self.manifest()["currentState"], "verification-building")
        self.assertEqual(self.ctl("complete-verification").returncode, 0)


if __name__ == "__main__":
    unittest.main()

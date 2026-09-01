import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "bin" / "jigctl.py"


class JigControllerTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name) / "repo"
        self.repo.mkdir()
        (self.repo / "README.md").write_text("# Fixture CLI\n\nRun `fixture`.\n", encoding="utf-8")
        subprocess.run(["git", "init", "-q", str(self.repo)], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.email", "jig@example.invalid"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "config", "user.name", "Jig Fixture"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "add", "README.md"], check=True)
        subprocess.run(["git", "-C", str(self.repo), "commit", "-qm", "fixture"], check=True)
        self.revision = subprocess.check_output(["git", "-C", str(self.repo), "rev-parse", "HEAD"], text=True).strip()

    def tearDown(self):
        self.temporary.cleanup()

    def ctl(self, command, *arguments, input_value=None, isolation="isolated-shell"):
        return subprocess.run(
            [sys.executable, str(CONTROLLER), command, "--resource-isolation", isolation, *arguments],
            cwd=self.repo,
            input=None if input_value is None else json.dumps(input_value),
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi"},
        )

    def output(self, result):
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def manifest(self):
        return json.loads((self.repo / ".pi/jig/manifest.json").read_text(encoding="utf-8"))

    def profile(self):
        evidence = [{"path": "README.md", "line": 1, "note": "Documents the fixture CLI."}]
        return {
            "schemaVersion": 2,
            "repositoryRevision": self.revision,
            "productType": {"value": "CLI", "evidence": evidence},
            "entryPoints": [{"value": "fixture", "evidence": evidence}],
            "existingPolicies": [],
            "unknowns": [],
        }

    def answers(self, marker="I ratify these repository Principles."):
        return {
            "schemaVersion": 2,
            "protectedUserPaths": [
                {
                    "name": "Run the CLI",
                    "action": "Run fixture from a clean checkout.",
                    "visibleResult": "The CLI prints the fixture result.",
                    "thresholds": "Exit zero within five seconds.",
                }
            ],
            "forbiddenOutcomes": ["Do not delete user-owned fixture data."],
            "compatibilityPolicy": "Breaking the documented CLI requires operator approval.",
            "priorityTradeoffs": ["Preserve CLI correctness", "Keep startup below five seconds"],
            "authority": {
                "owner": "Fixture Operator",
                "exceptions": ["No standing exceptions."],
                "amendmentPolicy": "The operator approves an exact replacement digest.",
                "ratificationMarker": marker,
            },
            "freeTextAmendments": "",
        }

    def reach_awaiting(self):
        started = self.output(self.ctl("start"))
        self.assertEqual(started["state"], "surveying")
        committed = self.output(self.ctl("commit-profile", input_value=self.profile()))
        self.assertEqual(committed["state"], "awaiting-principles")

    def ratify(self):
        self.reach_awaiting()
        interview = self.output(self.ctl("present-principles"))
        self.assertEqual(interview["kind"], "repository-principles-interview")
        self.assertNotIn("recommendedDefault", json.dumps(interview))
        staged = self.output(self.ctl("stage-principles", input_value=self.answers()))
        candidate = self.repo / staged["candidatePath"]
        self.assertEqual(staged["candidateSha256"], __import__("hashlib").sha256(candidate.read_bytes()).hexdigest())
        answers_path = self.repo / ".pi/jig/principles/answers.input.json"
        self.assertEqual(json.loads(answers_path.read_text(encoding="utf-8")), self.answers())
        answers_digest = __import__("hashlib").sha256(answers_path.read_bytes()).hexdigest()
        artifact = next(item for item in self.manifest()["artifacts"] if item["path"] == ".pi/jig/principles/answers.input.json")
        self.assertEqual(artifact, {"path": ".pi/jig/principles/answers.input.json", "owner": "human", "sha256": answers_digest})
        ratified = self.output(
            self.ctl(
                "ratify-principles",
                "--candidate-sha",
                staged["candidateSha256"],
                "--operator-marker",
                staged["intendedMarker"],
            )
        )
        self.assertEqual(ratified["state"], "verification-building")
        principle = self.repo / ".cursor/skills/principle-repository/SKILL.md"
        self.assertEqual(principle.read_bytes(), candidate.read_bytes())
        self.assertIn("name: principle-repository", principle.read_text(encoding="utf-8"))
        return staged

    def write_verification_skill(self, name="fixture"):
        path = self.repo / f".cursor/skills/verify-{name}/SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            f"---\nname: verify-{name}\ndescription: Drive and verify the fixture CLI.\n---\n\n# Verify fixture\n",
            encoding="utf-8",
        )
        return path

    def test_v2_flow_configures_principle_verification_and_pi_path_idempotently(self):
        self.ratify()
        settings = self.repo / ".pi/settings.json"
        settings.write_text(json.dumps({"theme": "keep", "skills": ["../other/skills"]}), encoding="utf-8")
        verification = self.write_verification_skill()
        completion = {"schemaVersion": 2, "verificationSkillPath": verification.relative_to(self.repo).as_posix()}
        configured = self.output(self.ctl("complete-configuration", input_value=completion))
        self.assertEqual(configured["state"], "configured")
        self.assertEqual(configured["outcome"], "configured")
        self.assertIn("maintain-verification-skill", configured["maintenance"])
        merged = json.loads(settings.read_text(encoding="utf-8"))
        self.assertEqual(merged["theme"], "keep")
        self.assertEqual(merged["skills"], ["../other/skills", "../.cursor/skills"])
        before = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in (self.repo / ".pi").rglob("*")
            if path.is_file()
        }
        repeated = self.output(self.ctl("complete-configuration", input_value=completion))
        self.assertEqual(repeated["state"], "configured")
        wrong_repeat = self.ctl(
            "complete-configuration",
            input_value={"schemaVersion": 2, "verificationSkillPath": ".cursor/skills/verify-other/SKILL.md"},
        )
        self.assertNotEqual(wrong_repeat.returncode, 0)
        after = {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in (self.repo / ".pi").rglob("*")
            if path.is_file()
        }
        self.assertEqual(after, before)
        self.output(self.ctl("validate-configuration"))
        manifest = self.manifest()
        self.assertEqual(manifest["schemaVersion"], 2)
        self.assertEqual(manifest["verification"]["createdBy"], "pstack/skills/create-verification-skill/SKILL.md")
        self.assertEqual(manifest["verification"]["maintainedBy"], "pstack/skills/maintain-verification-skill/SKILL.md")
        self.assertNotIn("firstStep", manifest)

    def test_ratification_requires_exact_digest_and_marker(self):
        self.reach_awaiting()
        staged = self.output(self.ctl("stage-principles", input_value=self.answers()))
        wrong_digest = self.ctl(
            "ratify-principles",
            "--candidate-sha",
            "0" * 64,
            "--operator-marker",
            staged["intendedMarker"],
        )
        self.assertNotEqual(wrong_digest.returncode, 0)
        wrong_marker = self.ctl(
            "ratify-principles",
            "--candidate-sha",
            staged["candidateSha256"],
            "--operator-marker",
            "different",
        )
        self.assertNotEqual(wrong_marker.returncode, 0)
        self.assertFalse((self.repo / ".cursor/skills/principle-repository/SKILL.md").exists())

    def test_existing_principle_is_preserved_and_can_be_adopted(self):
        self.reach_awaiting()
        principle = self.repo / ".cursor/skills/principle-repository/SKILL.md"
        principle.parent.mkdir(parents=True)
        existing = (
            "---\nname: principle-repository\ndescription: Existing repository constraints.\n---\n\n"
            "# Repository Principles\n\nStatus: RATIFIED\nOwner: Existing\nVersion: 4\nRatified at: 2026-09-01T00:00:00Z\n"
        ).encode()
        principle.write_bytes(existing)
        refused = self.ctl("stage-principles", input_value=self.answers())
        self.assertNotEqual(refused.returncode, 0)
        staged = self.output(self.ctl("stage-principles", "--adopt-existing", input_value=self.answers()))
        self.assertTrue(staged["adoptedExisting"])
        self.assertEqual((self.repo / staged["candidatePath"]).read_bytes(), existing)
        self.output(
            self.ctl(
                "ratify-principles",
                "--candidate-sha",
                staged["candidateSha256"],
                "--operator-marker",
                staged["intendedMarker"],
            )
        )
        self.assertEqual(principle.read_bytes(), existing)
        manifest = self.manifest()
        self.assertEqual(manifest["principle"]["version"], 4)
        self.assertEqual(manifest["principle"]["ratifiedAt"], "2026-09-01T00:00:00Z")

    def test_verification_path_and_symlink_escape_fail_closed(self):
        self.ratify()
        outside = Path(self.temporary.name) / "outside.md"
        outside.write_text("---\nname: verify-outside\ndescription: outside\n---\n", encoding="utf-8")
        target = self.repo / ".cursor/skills/verify-fixture/SKILL.md"
        target.parent.mkdir(parents=True)
        target.symlink_to(outside)
        rejected = self.ctl(
            "complete-configuration",
            input_value={"schemaVersion": 2, "verificationSkillPath": ".cursor/skills/verify-fixture/SKILL.md"},
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not a contained regular file", rejected.stderr)
        traversal = self.ctl(
            "complete-configuration",
            input_value={"schemaVersion": 2, "verificationSkillPath": ".cursor/skills/verify-fixture/../../outside.md"},
        )
        self.assertNotEqual(traversal.returncode, 0)
        self.assertEqual(self.manifest()["currentState"], "verification-building")

    def test_configured_validation_rejects_settings_symlinks(self):
        self.ratify()
        verification = self.write_verification_skill()
        completion = {"schemaVersion": 2, "verificationSkillPath": verification.relative_to(self.repo).as_posix()}
        self.output(self.ctl("complete-configuration", input_value=completion))
        settings = self.repo / ".pi/settings.json"
        outside = Path(self.temporary.name) / "outside-settings.json"
        outside.write_text('{"skills":["../.cursor/skills"]}\n', encoding="utf-8")
        settings.unlink()
        settings.symlink_to(outside)
        rejected = self.ctl("validate-configuration")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("not a contained regular file", rejected.stderr)


    def test_settings_conflicts_fail_without_overwrite(self):
        self.ratify()
        verification = self.write_verification_skill()
        settings = self.repo / ".pi/settings.json"
        settings.parent.mkdir(parents=True, exist_ok=True)
        settings.write_text('{"skills":"wrong","theme":"keep"}\n', encoding="utf-8")
        before = settings.read_bytes()
        rejected = self.ctl(
            "complete-configuration",
            input_value={"schemaVersion": 2, "verificationSkillPath": verification.relative_to(self.repo).as_posix()},
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(settings.read_bytes(), before)
        self.assertEqual(self.manifest()["currentState"], "verification-building")

    def test_lock_rejects_symlinked_ancestors_and_incomplete_owner_records(self):
        outside = Path(self.temporary.name) / "outside"
        outside.mkdir()
        (self.repo / ".pi").symlink_to(outside, target_is_directory=True)
        rejected = self.ctl("start")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("controller directory is unsafe", rejected.stderr)
        self.assertFalse((outside / "jig").exists())
        (self.repo / ".pi").unlink()
        lock = self.repo / ".pi/jig/init.lock"
        lock.parent.mkdir(parents=True)
        lock.write_bytes(b"")
        incomplete = self.ctl("start")
        self.assertNotEqual(incomplete.returncode, 0)
        self.assertIn("lock owner is uncertain", incomplete.stderr)
        self.assertEqual(lock.read_bytes(), b"")

    def test_concurrent_controller_cannot_take_a_live_lock(self):
        holder_code = (
            "import importlib.util,sys,time\n"
            "from pathlib import Path\n"
            "spec=importlib.util.spec_from_file_location('jigctl',sys.argv[1])\n"
            "module=importlib.util.module_from_spec(spec)\n"
            "spec.loader.exec_module(module)\n"
            "with module.RepositoryLock(Path(sys.argv[2])):\n"
            " print('locked',flush=True)\n"
            " time.sleep(30)\n"
        )
        holder = subprocess.Popen(
            [sys.executable, "-c", holder_code, str(CONTROLLER), str(self.repo)],
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        try:
            self.assertEqual(holder.stdout.readline().strip(), "locked")
            rejected = self.ctl("start")
            self.assertNotEqual(rejected.returncode, 0)
            self.assertIn("live or uncertain owner", rejected.stderr)
        finally:
            holder.terminate()
            holder.wait(timeout=10)
            holder.stdout.close()
            holder.stderr.close()

    def test_ratification_recovers_after_exact_principle_publication(self):
        self.reach_awaiting()
        staged = self.output(self.ctl("stage-principles", input_value=self.answers()))
        candidate = self.repo / staged["candidatePath"]
        target = self.repo / ".cursor/skills/principle-repository/SKILL.md"
        target.parent.mkdir(parents=True)
        target.write_bytes(candidate.read_bytes())
        ratified = self.output(
            self.ctl(
                "ratify-principles",
                "--candidate-sha",
                staged["candidateSha256"],
                "--operator-marker",
                staged["intendedMarker"],
            )
        )
        self.assertEqual(ratified["state"], "verification-building")
        self.assertEqual(target.read_bytes(), candidate.read_bytes())

    def test_configuration_requires_exactly_one_verification_skill(self):
        self.ratify()
        verification = self.write_verification_skill("fixture")
        self.write_verification_skill("other")
        rejected = self.ctl(
            "complete-configuration",
            input_value={"schemaVersion": 2, "verificationSkillPath": verification.relative_to(self.repo).as_posix()},
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("exactly one", rejected.stderr)
        self.assertEqual(self.manifest()["currentState"], "verification-building")

    def test_source_and_profile_drift_fail_closed(self):
        self.output(self.ctl("start"))
        (self.repo / "README.md").write_text("changed\n", encoding="utf-8")
        source_drift = self.ctl("commit-profile", input_value=self.profile())
        self.assertNotEqual(source_drift.returncode, 0)
        self.assertIn("source revision or dirty summary changed", source_drift.stderr)

        subprocess.run(["git", "-C", str(self.repo), "checkout", "--", "README.md"], check=True)
        self.output(self.ctl("commit-profile", input_value=self.profile()))
        profile_path = self.repo / ".pi/jig/profile.json"
        profile_path.write_text("{}\n", encoding="utf-8")
        profile_drift = self.ctl("present-principles")
        self.assertNotEqual(profile_drift.returncode, 0)
        self.assertIn("manifest artifact changed", profile_drift.stderr)


    def test_legacy_v1_manifest_is_rejected_with_preservation_guidance(self):
        path = self.repo / ".pi/jig/manifest.json"
        path.parent.mkdir(parents=True)
        path.write_text('{"schemaVersion":1}\n', encoding="utf-8")
        rejected = self.ctl("start")
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("unsupported legacy Jig v1 campaign", rejected.stderr)
        self.assertIn("preserve .pi/jig", rejected.stderr)
        self.assertEqual(path.read_text(encoding="utf-8"), '{"schemaVersion":1}\n')

    def test_route_mismatch_and_failed_state_recovery_are_explicit(self):
        self.output(self.ctl("start", isolation="inherited-session"))
        mismatch = self.ctl("start", isolation="isolated-shell")
        self.assertNotEqual(mismatch.returncode, 0)
        self.assertIn("/skill:jig init or /jig init", mismatch.stderr)
        failed = self.output(
            self.ctl(
                "record-failure",
                "--state",
                "surveying",
                "--reason",
                "fixture interruption",
                isolation="inherited-session",
            )
        )
        self.assertEqual(failed["state"], "failed-surveying")
        recovered = self.output(self.ctl("start", isolation="inherited-session"))
        self.assertEqual(recovered["state"], "surveying")


if __name__ == "__main__":
    unittest.main()

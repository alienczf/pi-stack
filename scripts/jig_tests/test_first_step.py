import json
import os
import subprocess
import sys
import unittest
from unittest import mock

from scripts.jig_tests import test_verification


class FirstStepTest(unittest.TestCase):
    def setUp(self):
        self.fixture = test_verification.VerificationTest(methodName="runTest")
        self.fixture.setUp()
        self.repo = self.fixture.repo
        self.fixture.begin()
        self.fixture.install_generated()
        completed = self.fixture.ctl("complete-verification")
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def tearDown(self):
        self.fixture.tearDown()

    def ctl(self, *arguments, input_value=None):
        return self.fixture.ctl(*arguments, input_value=input_value)

    def manifest(self):
        return self.fixture.manifest()

    def selection_draft(self, candidates=None, selected=None, summary="No eligible candidate."):
        manifest = self.manifest()
        return {
            "schemaVersion": 1,
            "stepId": "0001",
            "repositoryRevision": manifest["source"]["revision"],
            "commandmentsSha256": manifest["commandments"]["sha256"],
            "candidates": [] if candidates is None else candidates,
            "selectedCandidateId": selected,
            "rankingSummary": summary,
        }

    def rejected_candidate(self):
        return {
            "id": "candidate-one",
            "title": "Rejected fixture candidate",
            "commandmentIds": ["CMD-001"],
            "evidence": [{"path": "app.py", "line": 1, "note": "Fixture source."}],
            "responseLayer": "code",
            "expectedGain": {key: value for key, value in (
                ("priority", "medium"), ("severity", "medium"), ("recurrence", "low"),
                ("preventionValue", "medium"), ("confidence", "high"),
            )},
            "riskCost": {
                "implementationCost": "low", "blastRadius": "low",
                "uncertainty": "low", "rollbackDifficulty": "low",
            },
            "eligibility": {"eligible": False, "rejectionReasons": ["missing-proof-path"]},
            "verificationPlan": ["Run the fixture verification."],
            "rollback": "Revert the candidate change.",
            "potetoPlaybook": "pstack/skills/poteto-mode/playbooks/feature.md",
            "behavioralEval": "not-required",
        }

    def commit_selection(self, draft):
        return self.ctl("commit-step-selection", input_value=draft)

    def test_ready_enters_selecting_without_step_artifacts(self):
        before = self.manifest()
        selected = self.ctl("begin-step-selection")
        self.assertEqual(selected.returncode, 0, selected.stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual(len(manifest["transitions"]), len(before["transitions"]) + 1)
        transition = manifest["transitions"][-1]
        self.assertEqual((transition["from"], transition["to"]), ("verification-ready", "step-selecting"))
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        runtime = manifest["verification"][0]["receiptPath"]
        runtime_artifact = next(item for item in manifest["artifacts"] if item["path"] == runtime)
        self.assertEqual(receipt["kind"], "step-selection-started")
        self.assertEqual(receipt["resourceIsolation"], manifest["resourceIsolation"])
        self.assertEqual(receipt["commandmentsSha256"], manifest["commandments"]["sha256"])
        self.assertEqual((receipt["runtimeReceiptPath"], receipt["runtimeReceiptSha256"]), (runtime, runtime_artifact["sha256"]))
        self.assertEqual(manifest["firstStep"]["outcome"], "pending")
        self.assertFalse((self.repo / ".pi/jig/steps/0001").exists())

    def test_matching_rerun_is_idempotent_and_drift_fails_closed(self):
        first = self.ctl("begin-step-selection")
        self.assertEqual(first.returncode, 0, first.stderr)
        original = (self.repo / ".pi/jig/manifest.json").read_bytes()
        rerun = self.ctl("begin-step-selection")
        self.assertEqual(rerun.returncode, 0, rerun.stderr)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), original)
        wrong_route = subprocess.run(
            [
                sys.executable,
                str(test_verification.CONTROLLER),
                "begin-step-selection",
                "--resource-isolation",
                "inherited-session",
            ],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi"},
        )
        self.assertNotEqual(wrong_route.returncode, 0)
        (self.repo / "drift.txt").write_text("drift\n")
        drifted = self.ctl("begin-step-selection")
        self.assertNotEqual(drifted.returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), original)

    def test_failure_and_start_reconcile_only_selecting(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        failed = self.ctl("record-failure", "--state", "step-selecting", "--reason", "seeded selection failure")
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-step-selecting")
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual((manifest["transitions"][-1]["from"], manifest["transitions"][-1]["to"]), ("failed-step-selecting", "step-selecting"))
        self.assertFalse((self.repo / ".pi/jig/steps/0001").exists())

    def test_empty_selection_commits_only_schema_valid_selection(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        committed = self.commit_selection(self.selection_draft())
        self.assertEqual(committed.returncode, 0, committed.stderr)
        output = json.loads(committed.stdout)
        path = self.repo / ".pi/jig/steps/0001/selection.json"
        selection = json.loads(path.read_text())
        test_verification.jigctl.validate_instance(
            selection, test_verification.jigctl.load_schema("selection")
        )
        self.assertEqual(output["state"], "step-selecting")
        self.assertEqual(output["selection"]["path"], ".pi/jig/steps/0001/selection.json")
        self.assertEqual(list(path.parent.iterdir()), [path])
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual(manifest["firstStep"]["selectedCandidateId"], None)
        self.assertEqual(manifest["firstStep"]["outcome"], "pending")
        self.assertIsNone(manifest["firstStep"]["proposalPath"])
        self.assertIsNone(manifest["firstStep"]["resultPath"])

    def test_rejected_candidates_commit_and_invalid_candidates_fail_closed(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        candidate = self.rejected_candidate()
        duplicate = json.loads(json.dumps(candidate))
        bad_evidence = json.loads(json.dumps(candidate))
        bad_evidence["evidence"][0]["line"] = 999
        bad_path = json.loads(json.dumps(candidate))
        bad_path["evidence"][0]["path"] = "missing.py"
        bad_id = json.loads(json.dumps(candidate))
        bad_id["commandmentIds"] = ["CMD-999"]
        eligible = json.loads(json.dumps(candidate))
        eligible["eligibility"] = {"eligible": True, "rejectionReasons": []}
        invalid = [
            self.selection_draft([candidate, duplicate]),
            self.selection_draft([bad_evidence]),
            self.selection_draft([bad_path]),
            self.selection_draft([bad_id]),
            self.selection_draft([eligible]),
            self.selection_draft([candidate], selected="candidate-one"),
        ]
        selection_path = self.repo / ".pi/jig/steps/0001/selection.json"
        for draft in invalid:
            with self.subTest(draft=draft):
                rejected = self.commit_selection(draft)
                self.assertNotEqual(rejected.returncode, 0)
                self.assertFalse(selection_path.exists())
        committed = self.commit_selection(self.selection_draft([candidate]))
        self.assertEqual(committed.returncode, 0, committed.stderr)
        self.assertEqual(json.loads(selection_path.read_text())["candidates"][0]["id"], "candidate-one")

    def test_selection_retry_and_interrupted_manifest_write_converge(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        draft = self.selection_draft()
        with mock.patch.object(
            test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.commit_step_selection(
                    self.repo, "isolated-shell", json.dumps(draft).encode()
                )
        path = self.repo / ".pi/jig/steps/0001/selection.json"
        before = (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
        recovered = self.commit_selection(draft)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)
        manifest_before = (self.repo / ".pi/jig/manifest.json").read_bytes()
        retried = self.commit_selection(draft)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), manifest_before)
        changed = self.commit_selection(self.selection_draft(summary="Changed selection."))
        self.assertNotEqual(changed.returncode, 0)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)


if __name__ == "__main__":
    unittest.main()

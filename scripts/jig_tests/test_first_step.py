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

    def eligible_candidate(self, candidate_id="client-app-boundary"):
        candidate = self.rejected_candidate()
        candidate.update({
            "id": candidate_id,
            "title": "Decouple the public client from the server implementation",
            "evidence": [
                {"path": "client.py", "line": 8, "note": "The public client imports the server module."},
                {"path": "app.py", "line": 9, "note": "The server owns the imported API version."},
            ],
            "eligibility": {"eligible": True, "rejectionReasons": []},
            "verificationPlan": ["Run the fixture client against the launched server."],
        })
        return candidate

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

    def test_selected_eligible_candidate_commits_without_execution_artifacts(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        candidate = self.eligible_candidate()
        worktrees_before = self.fixture.git("worktree", "list", "--porcelain")
        committed = self.commit_selection(self.selection_draft([candidate], selected=candidate["id"]))
        self.assertEqual(committed.returncode, 0, committed.stderr)
        manifest = self.manifest()
        self.assertEqual(manifest["currentState"], "step-selecting")
        self.assertEqual(manifest["firstStep"], {
            "selectionPath": ".pi/jig/steps/0001/selection.json",
            "selectedCandidateId": candidate["id"], "proposalPath": None,
            "resultPath": None, "outcome": "pending",
        })
        step_dir = self.repo / ".pi/jig/steps/0001"
        self.assertEqual({path.name for path in step_dir.iterdir()}, {"selection.json"})
        self.assertEqual(self.fixture.git("worktree", "list", "--porcelain"), worktrees_before)

    def test_selected_candidate_validation_accepts_model_ranking_and_fails_closed(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        first = self.eligible_candidate()
        second = self.eligible_candidate("client-app-boundary-two")
        rejected = self.rejected_candidate()
        behavioral = self.eligible_candidate("behavioral-check")
        behavioral["responseLayer"] = "behavioral-eval"
        invalid = [
            self.selection_draft([first], selected="unknown-candidate"),
            self.selection_draft([first, rejected], selected=rejected["id"]),
            self.selection_draft([first, json.loads(json.dumps(first))], selected=first["id"]),
            self.selection_draft([behavioral], selected=behavioral["id"]),
        ]
        path = self.repo / ".pi/jig/steps/0001/selection.json"
        for draft in invalid:
            with self.subTest(selected=draft["selectedCandidateId"]):
                self.assertNotEqual(self.commit_selection(draft).returncode, 0)
                self.assertFalse(path.exists())
        committed = self.commit_selection(
            self.selection_draft([first, second], selected=second["id"], summary="Prefer the second eligible option.")
        )
        self.assertEqual(committed.returncode, 0, committed.stderr)
        self.assertEqual(json.loads(path.read_text())["selectedCandidateId"], second["id"])
        self.assertEqual(self.manifest()["firstStep"]["selectedCandidateId"], second["id"])

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

    def test_selected_selection_retry_and_interrupted_manifest_write_converge(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        candidate = self.eligible_candidate()
        draft = self.selection_draft([candidate], selected=candidate["id"])
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
        manifest_path = self.repo / ".pi/jig/manifest.json"
        manifest_before = manifest_path.read_bytes()
        retried = self.commit_selection(draft)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        changed = self.commit_selection(self.selection_draft([candidate], selected=candidate["id"], summary="Changed selection."))
        self.assertNotEqual(changed.returncode, 0)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)
        mismatched = json.loads(manifest_before)
        mismatched["firstStep"]["selectedCandidateId"] = "different-candidate"
        manifest_path.write_text(json.dumps(mismatched))
        mismatch_bytes = manifest_path.read_bytes()
        self.assertNotEqual(self.commit_selection(draft).returncode, 0)
        self.assertEqual(manifest_path.read_bytes(), mismatch_bytes)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), before)

    def test_empty_selection_finalizes_schema_valid_no_candidate_result(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        self.assertEqual(self.commit_selection(self.selection_draft()).returncode, 0)
        refs_before = self.fixture.git("for-each-ref", "--format=%(refname):%(objectname)")
        finalized = self.ctl("finalize-no-candidate")
        self.assertEqual(finalized.returncode, 0, finalized.stderr)
        manifest = self.manifest()
        result_path = self.repo / ".pi/jig/steps/0001/result.json"
        result = json.loads(result_path.read_text())
        test_verification.jigctl.validate_instance(result, test_verification.jigctl.load_schema("result"))
        self.assertEqual(manifest["currentState"], "initialized")
        self.assertEqual(manifest["firstStep"], {
            "selectionPath": ".pi/jig/steps/0001/selection.json",
            "selectedCandidateId": None, "proposalPath": None,
            "resultPath": ".pi/jig/steps/0001/result.json",
            "outcome": "no-eligible-candidate",
        })
        self.assertEqual(
            {key: result[key] for key in ("proposalPath", "proposalSha256", "inputRevision",
                "outputRevision", "branch", "worktree", "diffSha256", "independentVerdict")},
            {key: None for key in ("proposalPath", "proposalSha256", "inputRevision",
                "outputRevision", "branch", "worktree", "diffSha256", "independentVerdict")},
        )
        self.assertEqual(result["commands"], [])
        selection_path = self.repo / result["selectionPath"]
        self.assertEqual(result["selectionSha256"], test_verification.jigctl.sha256_file(selection_path))
        transition = manifest["transitions"][-1]
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        self.assertEqual((transition["from"], transition["to"], receipt["kind"]),
            ("step-selecting", "initialized", "no-candidate-finalized"))
        self.assertEqual((receipt["selectionSha256"], receipt["resultSha256"]),
            (result["selectionSha256"], test_verification.jigctl.sha256_file(result_path)))
        self.assertEqual(self.fixture.git("for-each-ref", "--format=%(refname):%(objectname)"), refs_before)

    def test_rejected_selection_finalizes_idempotently(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        draft = self.selection_draft([self.rejected_candidate()])
        self.assertEqual(self.commit_selection(draft).returncode, 0)
        self.assertEqual(self.ctl("finalize-no-candidate").returncode, 0)
        paths = [
            self.repo / ".pi/jig/steps/0001/result.json",
            self.repo / self.manifest()["transitions"][-1]["receiptPath"],
            self.repo / ".pi/jig/manifest.json",
        ]
        before = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
        self.assertEqual(self.ctl("finalize-no-candidate").returncode, 0)
        self.assertEqual(self.ctl("start").returncode, 0)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], before)

    def test_finalization_collisions_and_interruptions_fail_or_converge(self):
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        self.assertNotEqual(self.ctl("finalize-no-candidate").returncode, 0)
        self.assertEqual(self.commit_selection(self.selection_draft()).returncode, 0)
        selection_path = self.repo / ".pi/jig/steps/0001/selection.json"
        selection_raw = selection_path.read_bytes()
        selection = json.loads(selection_raw)
        selection["rankingSummary"] = "Changed after commitment."
        selection_path.write_text(json.dumps(selection))
        self.assertNotEqual(self.ctl("finalize-no-candidate").returncode, 0)
        selection_path.write_bytes(selection_raw)
        collision = selection_path.parent / "proposal.json"
        collision.write_text("preserve me\n")
        self.assertNotEqual(self.ctl("finalize-no-candidate").returncode, 0)
        self.assertEqual(collision.read_text(), "preserve me\n")
        collision.unlink()
        with mock.patch.object(test_verification.jigctl, "append_transition", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.finalize_no_candidate(self.repo, "isolated-shell")
        result_path = selection_path.parent / "result.json"
        result_before = (result_path.read_bytes(), result_path.stat().st_ino, result_path.stat().st_mtime_ns)
        result_path.write_bytes(result_before[0] + b" ")
        self.assertNotEqual(self.ctl("finalize-no-candidate").returncode, 0)
        self.assertEqual(result_path.read_bytes(), result_before[0] + b" ")
        result_path.write_bytes(result_before[0])
        result_before = (result_path.read_bytes(), result_path.stat().st_ino, result_path.stat().st_mtime_ns)
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.finalize_no_candidate(self.repo, "isolated-shell")
        transition_path = self.repo / ".pi/jig/receipts/transition-0007-initialized.json"
        transition_before = (transition_path.read_bytes(), transition_path.stat().st_ino, transition_path.stat().st_mtime_ns)
        recovered = self.ctl("finalize-no-candidate")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual((result_path.read_bytes(), result_path.stat().st_ino, result_path.stat().st_mtime_ns), result_before)
        self.assertEqual((transition_path.read_bytes(), transition_path.stat().st_ino, transition_path.stat().st_mtime_ns), transition_before)


if __name__ == "__main__":
    unittest.main()

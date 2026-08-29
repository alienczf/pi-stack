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

    def selected_fixture(self):
        candidate = self.eligible_candidate()
        candidate.update({
            "responseLayer": "deterministic-guard",
            "potetoPlaybook": "pstack/skills/poteto-mode/playbooks/refactoring.md",
            "behavioralEval": "not-required",
        })
        self.assertEqual(self.ctl("begin-step-selection").returncode, 0)
        self.assertEqual(
            self.commit_selection(self.selection_draft([candidate], selected=candidate["id"])).returncode, 0
        )
        return candidate

    def proposal_draft(self, candidate):
        manifest = self.manifest()
        selection_path = self.repo / ".pi/jig/steps/0001/selection.json"
        command_set = lambda command, expected: {"commands": [command], "expected": expected}
        return {
            "schemaVersion": 1, "stepId": "0001", "candidateId": candidate["id"],
            "repositoryRevision": manifest["source"]["revision"],
            "commandmentsSha256": manifest["commandments"]["sha256"],
            "selectionSha256": test_verification.jigctl.sha256_file(selection_path),
            "commandmentIds": candidate["commandmentIds"], "failureIds": ["WEAK-IMPORT-PROOF"],
            "responseLayer": candidate["responseLayer"],
            "expectedGain": "Prevent the public client from depending on the server implementation.",
            "evidence": candidate["evidence"],
            "blastRadius": candidate["riskCost"]["blastRadius"],
            "uncertainty": candidate["riskCost"]["uncertainty"],
            "potetoPlaybook": candidate["potetoPlaybook"],
            "baseline": command_set("python3 -m unittest test_weak", "The weak existing proof passes."),
            "proof": {
                "targeted": command_set("python3 test_dependency.py", "The dependency guard passes."),
                "regression": command_set("python3 -m unittest", "The fixture suite passes."),
                "protectedUserPath": command_set(
                    f"python3 {self.repo / '.pi/skills/jig-verification/helpers/fixture-control.py'} self-test",
                    "The real add/list/search path persists and cleans up."),
                "seededViolation": command_set("python3 test_dependency.py --seed", "The guard rejects the seeded import."),
                "independentReview": True,
            },
            "rollback": {"method": "Revert the dependency guard change.", "commands": ["git revert --no-edit HEAD"]},
            "evalDecision": {"status": "not-required", "reason": "The deterministic guard proves the claim."},
        }

    def commit_proposal(self, draft):
        return self.ctl("commit-step-proposal", input_value=draft)

    def worker_draft(self, session="fresh-worker-1", allowed=None, proposal=None):
        candidate = self.selected_fixture()
        self.assertEqual(self.commit_proposal(
            self.proposal_draft(candidate) if proposal is None else proposal).returncode, 0)
        self.assertEqual(self.ctl("prepare-step-worktree").returncode, 0)
        return {
            "schemaVersion": 1, "stepId": "0001", "workerSessionId": session,
            "allowedPaths": ["app.py", "client.py", "contract.py", "test_dependency.py"] if allowed is None else allowed,
        }

    def activated_worker(self, proposal=None):
        draft = self.worker_draft(proposal=proposal)
        activated = self.ctl("activate-step-worker", input_value=draft)
        self.assertEqual(activated.returncode, 0, activated.stderr)
        worker = json.loads((self.repo / ".pi/jig/steps/0001/worker.json").read_text())
        return self.repo / worker["worktree"], worker

    def commit_improvement(self, proposal=None):
        worktree, worker = self.activated_worker(proposal)
        app = worktree / "app.py"
        app.write_text(app.read_text().replace("from urllib.parse import parse_qs, urlparse\n",
            "from urllib.parse import parse_qs, urlparse\n\nfrom contract import API_VERSION\n").replace(
            "\nAPI_VERSION = \"fixture-v1\"\n", "\n"))
        client = worktree / "client.py"
        client.write_text(client.read_text().replace("from app import API_VERSION", "from contract import API_VERSION"))
        (worktree / "contract.py").write_text('API_VERSION = "fixture-v1"\n')
        (worktree / "test_dependency.py").write_text(
            "import ast\nimport sys\nfrom pathlib import Path\n\n"
            "path = Path('client.py')\noriginal = path.read_bytes()\n\n"
            "def check():\n    tree = ast.parse(path.read_text())\n    if any((isinstance(n, ast.Import) and "
            "any(x.name == 'app' for x in n.names)) or (isinstance(n, ast.ImportFrom) and n.module == 'app') "
            "for n in ast.walk(tree)):\n        raise SystemExit('client.py imports app.py')\n\n"
            "if '--seed' in sys.argv:\n    try:\n        path.write_bytes(original + b'\\nfrom app import API_VERSION\\n')\n"
            "        try:\n            check()\n        except SystemExit:\n            pass\n        else:\n            raise SystemExit('seed escaped guard')\n"
            "    finally:\n        path.write_bytes(original)\nelse:\n    check()\n")
        self.fixture.git("-C", str(worktree), "add", "app.py", "client.py", "contract.py", "test_dependency.py")
        self.fixture.git("-C", str(worktree), "commit", "-qm", "decouple client contract")
        return worktree, worker

    def proved_candidate(self, proposal=None):
        worktree, worker = self.commit_improvement(proposal)
        self.assertEqual(self.ctl("record-step-output").returncode, 0)
        proved = self.ctl("verify-step-output")
        self.assertEqual(proved.returncode, 0, proved.stderr)
        output = json.loads((self.repo / ".pi/jig/steps/0001/output.json").read_text())
        return worktree, worker, output

    def verdict_draft(self, output, **changed):
        draft = {
            "schemaVersion": 1, "stepId": "0001", "status": "passed",
            "revision": output["outputRevision"], "reviewerSessionId": "external-review-run-1",
            "reviewerModel": "stand-in-model",
            "report": "Deterministic stand-in report. The parent different-model gate remains external.\n",
        }
        draft.update(changed)
        return draft

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

    def test_selected_fixture_proposal_commits_without_execution_artifacts(self):
        candidate = self.selected_fixture()
        draft = self.proposal_draft(candidate)
        worktrees_before = self.fixture.git("worktree", "list", "--porcelain")
        refs_before = self.fixture.git("for-each-ref", "--format=%(refname):%(objectname)")
        committed = self.commit_proposal(draft)
        self.assertEqual(committed.returncode, 0, committed.stderr)
        path = self.repo / ".pi/jig/steps/0001/proposal.json"
        proposal = json.loads(path.read_text())
        test_verification.jigctl.validate_instance(proposal, test_verification.jigctl.load_schema("proposal"))
        manifest = self.manifest()
        self.assertEqual(manifest["firstStep"]["proposalPath"], ".pi/jig/steps/0001/proposal.json")
        self.assertEqual(manifest["firstStep"]["resultPath"], None)
        self.assertEqual((manifest["currentState"], manifest["firstStep"]["outcome"]), ("step-selecting", "pending"))
        self.assertEqual({item.name for item in path.parent.iterdir()}, {"selection.json", "proposal.json"})
        self.assertEqual(self.fixture.git("worktree", "list", "--porcelain"), worktrees_before)
        self.assertEqual(self.fixture.git("for-each-ref", "--format=%(refname):%(objectname)"), refs_before)

    def test_proposal_mismatches_and_unbounded_commands_fail_closed(self):
        candidate = self.selected_fixture()
        draft = self.proposal_draft(candidate)
        invalid = []
        for key, value in (
            ("candidateId", "other-candidate"),
            ("selectionSha256", "0" * 64),
            ("repositoryRevision", "0" * 40),
            ("commandmentsSha256", "0" * 64),
            ("evidence", [{"path": "app.py", "line": 1, "note": "Different evidence."}]),
            ("responseLayer", "code"),
            ("blastRadius", "high"),
            ("uncertainty", "high"),
            ("potetoPlaybook", "pstack/skills/poteto-mode/playbooks/feature.md"),
        ):
            changed = json.loads(json.dumps(draft))
            changed[key] = value
            invalid.append(changed)
        changed = json.loads(json.dumps(draft))
        changed["evalDecision"]["status"] = "required"
        invalid.append(changed)
        for commands in (["echo ok"] * 5, ["echo first\necho second"], ["x" * 1001], ["   "]):
            changed = json.loads(json.dumps(draft))
            changed["baseline"]["commands"] = commands
            invalid.append(changed)
        changed = json.loads(json.dumps(draft))
        changed["rollback"]["commands"] = [" "]
        invalid.append(changed)
        path = self.repo / ".pi/jig/steps/0001/proposal.json"
        for proposal in invalid:
            with self.subTest(proposal=proposal):
                self.assertNotEqual(self.commit_proposal(proposal).returncode, 0)
                self.assertFalse(path.exists())

    def test_proposal_retry_interruption_and_collisions_fail_or_converge(self):
        candidate = self.selected_fixture()
        draft = self.proposal_draft(candidate)
        path = self.repo / ".pi/jig/steps/0001/proposal.json"
        path.write_text("preserve me\n")
        self.assertNotEqual(self.commit_proposal(draft).returncode, 0)
        self.assertEqual(path.read_text(), "preserve me\n")
        path.unlink()
        collision = path.parent / "unknown.json"
        collision.write_text("preserve me\n")
        self.assertNotEqual(self.commit_proposal(draft).returncode, 0)
        self.assertEqual(collision.read_text(), "preserve me\n")
        collision.unlink()
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.commit_step_proposal(
                    self.repo, "isolated-shell", json.dumps(draft).encode()
                )
        proposal_before = (path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
        recovered = self.commit_proposal(draft)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest_path = self.repo / ".pi/jig/manifest.json"
        manifest_before = manifest_path.read_bytes()
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), proposal_before)
        self.assertEqual(self.commit_proposal(draft).returncode, 0)
        self.assertEqual(manifest_path.read_bytes(), manifest_before)
        self.assertEqual((path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns), proposal_before)
        path.write_bytes(proposal_before[0] + b" ")
        self.assertNotEqual(self.commit_proposal(draft).returncode, 0)
        self.assertEqual(path.read_bytes(), proposal_before[0] + b" ")
        path.write_bytes(proposal_before[0])
        mismatched = json.loads(manifest_before)
        mismatched["firstStep"]["proposalPath"] = None
        manifest_path.write_text(json.dumps(mismatched))
        mismatch_bytes = manifest_path.read_bytes()
        self.assertNotEqual(self.commit_proposal(draft).returncode, 0)
        self.assertEqual(manifest_path.read_bytes(), mismatch_bytes)

    def test_prepare_worktree_pins_only_the_passing_baseline(self):
        candidate = self.selected_fixture()
        self.assertEqual(self.commit_proposal(self.proposal_draft(candidate)).returncode, 0)
        head = self.fixture.git("rev-parse", "HEAD").strip()
        source = {name: (self.repo / name).read_bytes() for name in ("app.py", "client.py", "test_weak.py")}
        prepared = self.ctl("prepare-step-worktree")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        manifest = self.manifest()
        selection_sha = test_verification.jigctl.sha256_file(self.repo / ".pi/jig/steps/0001/selection.json")
        branch = f"jig/init-step-0001-{selection_sha[:12]}"
        worktree = self.repo / ".pi/jig/worktrees/0001"
        receipt_path = self.repo / ".pi/jig/steps/0001/commands/baseline-01.json"
        before_path = self.repo / ".pi/jig/steps/0001/before.json"
        receipt = json.loads(receipt_path.read_text())
        before = json.loads(before_path.read_text())
        self.assertEqual((receipt["phase"], receipt["index"], receipt["command"]), ("baseline", 1, "python3 -m unittest test_weak"))
        self.assertEqual((receipt["branch"], receipt["revision"], receipt["exitCode"], receipt["timedOut"]), (branch, head, 0, False))
        self.assertEqual((before["branch"], before["worktree"], before["inputRevision"]), (branch, ".pi/jig/worktrees/0001", head))
        self.assertEqual(before["commands"][0]["receiptSha256"], test_verification.jigctl.sha256_file(receipt_path))
        artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
        self.assertEqual(artifacts[".pi/jig/steps/0001/before.json"], test_verification.jigctl.sha256_file(before_path))
        self.assertEqual(self.fixture.git("rev-parse", branch).strip(), head)
        self.assertEqual(self.fixture.git("-C", str(worktree), "rev-parse", "HEAD").strip(), head)
        self.assertEqual((manifest["currentState"], manifest["firstStep"]["outcome"], manifest["firstStep"]["resultPath"]), ("step-selecting", "pending", None))
        self.assertEqual(self.fixture.git("rev-parse", "HEAD").strip(), head)
        self.assertEqual({name: (self.repo / name).read_bytes() for name in source}, source)
        self.assertFalse((worktree / "__pycache__").exists())

    def test_prepare_retry_and_file_before_manifest_recovery_are_stable(self):
        candidate = self.selected_fixture()
        self.assertEqual(self.commit_proposal(self.proposal_draft(candidate)).returncode, 0)
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.prepare_step_worktree(self.repo, "isolated-shell")
        paths = [
            self.repo / ".pi/jig/steps/0001/commands/baseline-01.json",
            self.repo / ".pi/jig/steps/0001/before.json",
        ]
        snapshots = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
        topology = self.fixture.git("worktree", "list", "--porcelain")
        recovered = self.ctl("prepare-step-worktree")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest = (self.repo / ".pi/jig/manifest.json").read_bytes()
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], snapshots)
        self.assertEqual(self.fixture.git("worktree", "list", "--porcelain"), topology)
        self.assertEqual(self.ctl("prepare-step-worktree").returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), manifest)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], snapshots)

    def test_prepare_rejects_wrong_branch_and_mutating_baseline_without_before(self):
        cases = [(self, "printf changed >> app.py"), (FirstStepTest(methodName="runTest"), None)]
        for case, command in cases:
            if case is not self:
                case.setUp()
            try:
                candidate = case.selected_fixture()
                draft = case.proposal_draft(candidate)
                if command is not None:
                    draft["baseline"]["commands"] = [command]
                self.assertEqual(case.commit_proposal(draft).returncode, 0)
                head = case.fixture.git("rev-parse", "HEAD").strip()
                app = (case.repo / "app.py").read_bytes()
                if command is None:
                    selection = case.repo / ".pi/jig/steps/0001/selection.json"
                    branch = f"jig/init-step-0001-{test_verification.jigctl.sha256_file(selection)[:12]}"
                    case.fixture.git("commit", "--allow-empty", "-qm", "wrong branch")
                    wrong = case.fixture.git("rev-parse", "HEAD").strip()
                    case.fixture.git("reset", "--hard", head)
                    case.fixture.git("branch", branch, wrong)
                rejected = case.ctl("prepare-step-worktree")
                self.assertNotEqual(rejected.returncode, 0)
                self.assertFalse((case.repo / ".pi/jig/steps/0001/before.json").exists())
                self.assertEqual((case.manifest()["currentState"], case.manifest()["firstStep"]["outcome"]), ("step-selecting", "pending"))
                self.assertEqual(case.fixture.git("rev-parse", "HEAD").strip(), head)
                self.assertEqual((case.repo / "app.py").read_bytes(), app)
            finally:
                if case is not self:
                    case.tearDown()


    def test_activation_enters_running_and_renders_bounded_handoff(self):
        draft = self.worker_draft()
        source = {name: (self.repo / name).read_bytes() for name in ("app.py", "client.py")}
        activated = self.ctl("activate-step-worker", input_value=draft)
        self.assertEqual(activated.returncode, 0, activated.stderr)
        output, manifest = json.loads(activated.stdout), self.manifest()
        worker_path = self.repo / ".pi/jig/steps/0001/worker.json"
        worker = json.loads(worker_path.read_text())
        transition = manifest["transitions"][-1]
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        self.assertEqual((manifest["currentState"], transition["from"], transition["to"]),
            ("step-running", "step-selecting", "step-running"))
        self.assertEqual((receipt["kind"], receipt["workerSha256"]),
            ("step-worker-activated", test_verification.jigctl.sha256_file(worker_path)))
        self.assertEqual(output["workerHandoff"], {
            "worktree": ".pi/jig/worktrees/0001", "workerSessionId": "fresh-worker-1",
            "selectedCandidateId": "client-app-boundary",
            "proposalPath": ".pi/jig/steps/0001/proposal.json",
            "potetoPlaybook": "pstack/skills/poteto-mode/playbooks/refactoring.md",
            "allowedPaths": draft["allowedPaths"],
            "protectedPaths": [".git", ".pi", "COMMANDMENTS.md", "eval", "evals"],
        })
        self.assertEqual({name: (self.repo / name).read_bytes() for name in source}, source)
        self.assertEqual((manifest["firstStep"]["outcome"], manifest["firstStep"]["resultPath"]), ("pending", None))

    def test_activation_retry_and_interruptions_converge_or_fail_closed(self):
        draft = self.worker_draft()
        with mock.patch.object(test_verification.jigctl, "append_transition", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.activate_step_worker(
                    self.repo, "isolated-shell", json.dumps(draft).encode())
        worker_path = self.repo / ".pi/jig/steps/0001/worker.json"
        worker_raw = worker_path.read_bytes()
        worker_path.write_bytes(worker_raw + b" ")
        self.assertNotEqual(self.ctl("activate-step-worker", input_value=draft).returncode, 0)
        worker_path.write_bytes(worker_raw)
        worker_before = (worker_path.read_bytes(), worker_path.stat().st_ino, worker_path.stat().st_mtime_ns)
        recovered = self.ctl("activate-step-worker", input_value=draft)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest_path = self.repo / ".pi/jig/manifest.json"
        transition_path = self.repo / self.manifest()["transitions"][-1]["receiptPath"]
        stable = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in (worker_path, transition_path, manifest_path)]
        self.assertEqual(self.ctl("activate-step-worker", input_value=draft).returncode, 0)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in (worker_path, transition_path, manifest_path)], stable)
        changed = dict(draft, workerSessionId="different-worker")
        self.assertNotEqual(self.ctl("activate-step-worker", input_value=changed).returncode, 0)
        self.assertEqual((worker_path.read_bytes(), worker_path.stat().st_ino, worker_path.stat().st_mtime_ns), worker_before)
        case = FirstStepTest(methodName="runTest")
        case.setUp()
        try:
            other = case.worker_draft(session="fresh-worker-2")
            with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
                with self.assertRaises(RuntimeError):
                    test_verification.jigctl.activate_step_worker(
                        case.repo, "isolated-shell", json.dumps(other).encode())
            receipt = case.repo / ".pi/jig/receipts/transition-0007-step-running.json"
            before = (receipt.read_bytes(), receipt.stat().st_ino, receipt.stat().st_mtime_ns)
            self.assertEqual(case.ctl("activate-step-worker", input_value=other).returncode, 0)
            self.assertEqual((receipt.read_bytes(), receipt.stat().st_ino, receipt.stat().st_mtime_ns), before)
        finally:
            case.tearDown()

    def test_running_scope_and_failed_recovery_fail_closed(self):
        draft = self.worker_draft()
        self.assertEqual(self.ctl("activate-step-worker", input_value=draft).returncode, 0)
        worker = self.repo / ".pi/jig/worktrees/0001"
        (worker / "app.py").write_text((worker / "app.py").read_text() + "\n")
        self.assertEqual(self.ctl("start").returncode, 0)
        (worker / "outside.py").write_text("outside\n")
        self.assertNotEqual(self.ctl("start").returncode, 0)
        (worker / "outside.py").unlink()
        branch = json.loads((self.repo / ".pi/jig/steps/0001/worker.json").read_text())["branch"]
        self.fixture.git("-C", str(worker), "checkout", "--detach", "-q")
        self.assertNotEqual(self.ctl("start").returncode, 0)
        self.fixture.git("-C", str(worker), "checkout", "-q", branch)
        failed = self.ctl("record-failure", "--state", "step-running", "--reason", "seeded worker failure")
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-step-running")
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertEqual((self.manifest()["currentState"], self.manifest()["transitions"][-1]["from"]),
            ("step-running", "failed-step-running"))

    def test_record_output_pins_exact_committed_fixture_diff(self):
        main_head = self.fixture.git("rev-parse", "HEAD").strip()
        source = {name: (self.repo / name).read_bytes() for name in ("app.py", "client.py")}
        worktree, worker = self.commit_improvement()
        output_head = self.fixture.git("-C", str(worktree), "rev-parse", "HEAD").strip()
        recorded = self.ctl("record-step-output")
        self.assertEqual(recorded.returncode, 0, recorded.stderr)
        output_path = self.repo / ".pi/jig/steps/0001/output.json"
        diff_path = self.repo / ".pi/jig/steps/0001/candidate.diff"
        receipt = json.loads(output_path.read_text())
        expected_diff = subprocess.run(["git", "-C", str(worktree), "diff", "--binary", "--full-index",
            "--no-ext-diff", f"{worker['inputRevision']}..{output_head}", "--"], check=True, stdout=subprocess.PIPE).stdout
        self.assertEqual(diff_path.read_bytes(), expected_diff)
        self.assertEqual(receipt["diffSha256"], test_verification.jigctl.sha256_bytes(expected_diff))
        self.assertEqual((receipt["inputRevision"], receipt["outputRevision"], receipt["commitCount"]),
            (worker["inputRevision"], output_head, 1))
        self.assertEqual(receipt["changedPaths"], ["app.py", "client.py", "contract.py", "test_dependency.py"])
        manifest = self.manifest()
        self.assertEqual((manifest["currentState"], manifest["firstStep"]["outcome"], manifest["firstStep"]["resultPath"]),
            ("step-running", "pending", None))
        self.assertEqual(self.fixture.git("rev-parse", "HEAD").strip(), main_head)
        self.assertEqual({name: (self.repo / name).read_bytes() for name in source}, source)
        started = self.ctl("start")
        self.assertEqual(started.returncode, 0, started.stderr)
        self.assertEqual(json.loads(started.stdout)["stepOutput"]["outputRevision"], output_head)
        self.assertNotIn("resume", json.loads(started.stdout))

    def test_record_output_rejects_unfinished_or_unsafe_candidates(self):
        scenarios = ("unchanged", "dirty", "non-descendant", "too-many", "symlink", "submodule", "outside")
        for scenario in scenarios:
            case = FirstStepTest(methodName="runTest")
            case.setUp()
            try:
                worktree, worker = case.activated_worker()
                if scenario == "dirty":
                    (worktree / "app.py").write_text((worktree / "app.py").read_text() + "\n")
                elif scenario == "non-descendant":
                    case.fixture.git("-C", str(worktree), "checkout", "--orphan", "replacement", "-q")
                    case.fixture.git("-C", str(worktree), "add", "-A")
                    case.fixture.git("-C", str(worktree), "commit", "-qm", "replacement")
                    case.fixture.git("-C", str(worktree), "branch", "-M", worker["branch"])
                elif scenario == "too-many":
                    for index in range(5):
                        case.fixture.git("-C", str(worktree), "commit", "--allow-empty", "-qm", f"empty {index}")
                    (worktree / "contract.py").write_text('API_VERSION = "fixture-v1"\n')
                    case.fixture.git("-C", str(worktree), "add", "contract.py")
                    case.fixture.git("-C", str(worktree), "commit", "-qm", "sixth")
                elif scenario == "symlink":
                    (worktree / "contract.py").symlink_to("app.py")
                    case.fixture.git("-C", str(worktree), "add", "contract.py")
                    case.fixture.git("-C", str(worktree), "commit", "-qm", "symlink")
                elif scenario == "submodule":
                    head = case.fixture.git("-C", str(worktree), "rev-parse", "HEAD").strip()
                    case.fixture.git("-C", str(worktree), "update-index", "--add", "--cacheinfo", f"160000,{head},contract.py")
                    case.fixture.git("-C", str(worktree), "commit", "-qm", "gitlink")
                elif scenario == "outside":
                    (worktree / "outside.py").write_text("outside\n")
                    case.fixture.git("-C", str(worktree), "add", "outside.py")
                    case.fixture.git("-C", str(worktree), "commit", "-qm", "outside")
                rejected = case.ctl("record-step-output")
                self.assertNotEqual(rejected.returncode, 0, scenario)
                self.assertFalse((case.repo / ".pi/jig/steps/0001/output.json").exists(), scenario)
            finally:
                case.tearDown()

    def test_output_retry_interruption_and_mutation_fail_closed(self):
        worktree, _worker = self.commit_improvement()
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.record_step_output(self.repo, "isolated-shell")
        paths = [self.repo / ".pi/jig/steps/0001/candidate.diff", self.repo / ".pi/jig/steps/0001/output.json"]
        before = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
        recovered = self.ctl("record-step-output")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest = (self.repo / ".pi/jig/manifest.json").read_bytes()
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], before)
        self.assertEqual(self.ctl("record-step-output").returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), manifest)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], before)
        paths[0].write_bytes(paths[0].read_bytes() + b"collision")
        self.assertNotEqual(self.ctl("start").returncode, 0)
        for mutation in ("head", "branch", "collision"):
            case = FirstStepTest(methodName="runTest")
            case.setUp()
            try:
                candidate, _worker = case.commit_improvement()
                if mutation == "collision":
                    diff = case.repo / ".pi/jig/steps/0001/candidate.diff"
                    diff.write_bytes(b"preserve me\n")
                    self.assertNotEqual(case.ctl("record-step-output").returncode, 0)
                    self.assertEqual(diff.read_bytes(), b"preserve me\n")
                    continue
                self.assertEqual(case.ctl("record-step-output").returncode, 0)
                if mutation == "head":
                    (candidate / "app.py").write_text((candidate / "app.py").read_text() + "\n")
                    case.fixture.git("-C", str(candidate), "add", "app.py")
                    case.fixture.git("-C", str(candidate), "commit", "-qm", "later mutation")
                else:
                    case.fixture.git("-C", str(candidate), "checkout", "--detach", "-q")
                self.assertNotEqual(case.ctl("start").returncode, 0)
            finally:
                case.tearDown()

    def test_proof_passes_ordered_phases_against_pinned_output(self):
        worktree, _worker = self.commit_improvement()
        self.assertEqual(self.ctl("record-step-output").returncode, 0)
        output_path = self.repo / ".pi/jig/steps/0001/output.json"
        diff = (self.repo / ".pi/jig/steps/0001/candidate.diff").read_bytes()
        proved = self.ctl("verify-step-output")
        self.assertEqual(proved.returncode, 0, proved.stderr)
        after = json.loads((self.repo / ".pi/jig/steps/0001/after.json").read_text())
        self.assertEqual(after["status"], "passed")
        self.assertIsNone(after["firstFailure"])
        self.assertEqual([item["phase"] for item in after["commands"]], [
            "targeted", "regression", "protected-user-path", "seeded-violation"])
        self.assertEqual(after["outputSha256"], test_verification.jigctl.sha256_file(output_path))
        self.assertEqual((self.repo / ".pi/jig/steps/0001/candidate.diff").read_bytes(), diff)
        protected = json.loads((self.repo / after["commands"][2]["receiptPath"]).read_text())
        self.assertIn('"cleanup": true', protected["stdout"])
        self.assertEqual(self.fixture.git("-C", str(worktree), "status", "--porcelain=v1",
            "--untracked-files=all", "--", ".", ":(exclude).pi"), "")
        manifest = self.manifest()
        self.assertEqual((manifest["currentState"], manifest["firstStep"]["outcome"],
            manifest["firstStep"]["resultPath"]), ("step-running", "pending", None))

    def test_mutating_proof_fails_stops_and_restores_pinned_candidate(self):
        candidate = self.selected_fixture()
        proposal = self.proposal_draft(candidate)
        proposal["proof"]["targeted"]["commands"] = ["printf '\\n# contamination\\n' >> client.py"]
        worktree, _worker = self.commit_improvement(proposal)
        output_head = self.fixture.git("-C", str(worktree), "rev-parse", "HEAD").strip()
        self.assertEqual(self.ctl("record-step-output").returncode, 0)
        proved = self.ctl("verify-step-output")
        self.assertEqual(proved.returncode, 0, proved.stderr)
        after = json.loads((self.repo / ".pi/jig/steps/0001/after.json").read_text())
        self.assertEqual((after["status"], len(after["commands"]), after["firstFailure"]["reason"]),
            ("failed", 1, "source-mutation"))
        self.assertFalse((self.repo / ".pi/jig/steps/0001/commands/regression-01.json").exists())
        self.assertEqual(self.fixture.git("-C", str(worktree), "rev-parse", "HEAD").strip(), output_head)
        self.assertEqual(self.fixture.git("-C", str(worktree), "status", "--porcelain=v1",
            "--untracked-files=all", "--", ".", ":(exclude).pi"), "")
        self.assertFalse((self.repo / ".pi/jig/steps/0001/result.json").exists())
        self.assertEqual(self.manifest()["firstStep"]["outcome"], "pending")

    def test_proof_retry_interruption_and_collisions_fail_closed(self):
        worktree, _worker = self.commit_improvement()
        self.assertEqual(self.ctl("record-step-output").returncode, 0)
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.verify_step_output(self.repo, "isolated-shell")
        command_paths = sorted((self.repo / ".pi/jig/steps/0001/commands").glob("*.json"))
        after_path = self.repo / ".pi/jig/steps/0001/after.json"
        paths = [*command_paths, after_path]
        snapshots = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
        recovered = self.ctl("verify-step-output")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest = (self.repo / ".pi/jig/manifest.json").read_bytes()
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns)
            for path in paths], snapshots)
        self.assertEqual(self.ctl("verify-step-output").returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), manifest)
        after_raw = after_path.read_bytes()
        after_path.write_bytes(after_raw + b" ")
        self.assertNotEqual(self.ctl("verify-step-output").returncode, 0)
        self.assertEqual(after_path.read_bytes(), after_raw + b" ")
        after_path.write_bytes(after_raw)
        (worktree / "client.py").write_text((worktree / "client.py").read_text() + "\n")
        self.assertNotEqual(self.ctl("verify-step-output").returncode, 0)
        self.assertEqual((self.repo / ".pi/jig/manifest.json").read_bytes(), manifest)

    def test_external_verdict_binds_passed_candidate_without_outcome(self):
        _worktree, _worker, output = self.proved_candidate()
        draft = self.verdict_draft(output)
        committed = self.ctl("commit-step-verdict", input_value=draft)
        self.assertEqual(committed.returncode, 0, committed.stderr)
        report = draft["report"].encode()
        digest = test_verification.jigctl.sha256_bytes(report)
        report_relative = f".pi/jig/steps/0001/reviews/{digest}.md"
        verdict_path = self.repo / ".pi/jig/steps/0001/verdict.json"
        verdict = json.loads(verdict_path.read_text())
        after_path = self.repo / ".pi/jig/steps/0001/after.json"
        self.assertEqual((self.repo / report_relative).read_bytes(), report)
        self.assertEqual(verdict, {
            "schemaVersion": 1, "kind": "step-verdict", "stepId": "0001",
            "status": "passed", "outputRevision": output["outputRevision"],
            "reviewerSessionId": "external-review-run-1", "reviewerModel": "stand-in-model",
            "reportPath": report_relative, "reportSha256": digest,
            "afterPath": ".pi/jig/steps/0001/after.json",
            "afterSha256": test_verification.jigctl.sha256_file(after_path),
            "recordedAt": verdict["recordedAt"],
        })
        manifest = self.manifest()
        artifacts = {item["path"]: item["sha256"] for item in manifest["artifacts"]}
        self.assertEqual(artifacts[report_relative], digest)
        self.assertEqual(artifacts[".pi/jig/steps/0001/verdict.json"],
            test_verification.jigctl.sha256_file(verdict_path))
        self.assertEqual((manifest["currentState"], manifest["firstStep"]["outcome"],
            manifest["firstStep"]["resultPath"]), ("step-running", "pending", None))
        self.assertFalse((self.repo / ".pi/jig/steps/0001/result.json").exists())
        started = json.loads(self.ctl("start").stdout)
        self.assertEqual(started["verdict"], {"status": "passed", "path": ".pi/jig/steps/0001/verdict.json"})
        self.assertNotIn("resume", started)

    def test_verdict_invalid_review_or_boundary_fails_closed(self):
        _worktree, worker, output = self.proved_candidate()
        base = self.verdict_draft(output)
        invalid = [
            dict(base, reviewerSessionId=worker["workerSessionId"]),
            dict(base, reviewerSessionId=""), dict(base, reviewerSessionId="x" * 201),
            dict(base, revision="0" * 40), dict(base, status="unknown"),
            dict(base, reviewerModel=" "), dict(base, report=""),
            dict(base, report="nul\0report"), dict(base, report="x" * (256 * 1024 + 1)),
            {**base, "extra": True},
        ]
        for draft in invalid:
            with self.subTest(draft={key: len(value) if key == "report" else value
                    for key, value in draft.items()}):
                self.assertNotEqual(self.ctl("commit-step-verdict", input_value=draft).returncode, 0)
                self.assertFalse((self.repo / ".pi/jig/steps/0001/verdict.json").exists())
        for scenario in ("failed-proof", "review-not-required", "candidate-drift"):
            case = FirstStepTest(methodName="runTest")
            case.setUp()
            try:
                candidate = case.selected_fixture()
                proposal = case.proposal_draft(candidate)
                if scenario == "failed-proof":
                    proposal["proof"]["targeted"]["commands"] = ["exit 1"]
                elif scenario == "review-not-required":
                    proposal["proof"]["independentReview"] = False
                worktree, _worker, output = case.proved_candidate(proposal)
                if scenario == "candidate-drift":
                    (worktree / "client.py").write_text((worktree / "client.py").read_text() + "\n")
                rejected = case.ctl("commit-step-verdict", input_value=case.verdict_draft(output))
                self.assertNotEqual(rejected.returncode, 0, scenario)
                self.assertFalse((case.repo / ".pi/jig/steps/0001/verdict.json").exists())
            finally:
                case.tearDown()

    def test_verdict_retry_interruption_changes_and_collisions_fail_or_converge(self):
        _worktree, _worker, output = self.proved_candidate()
        draft = self.verdict_draft(output)
        raw = json.dumps(draft).encode()
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.commit_step_verdict(self.repo, "isolated-shell", raw)
        digest = test_verification.jigctl.sha256_bytes(draft["report"].encode())
        paths = [self.repo / f".pi/jig/steps/0001/reviews/{digest}.md", self.repo / ".pi/jig/steps/0001/verdict.json"]
        before = [(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths]
        recovered = self.ctl("commit-step-verdict", input_value=draft)
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest_path = self.repo / ".pi/jig/manifest.json"
        manifest = (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], before)
        self.assertEqual(self.ctl("commit-step-verdict", input_value=draft).returncode, 0)
        self.assertEqual((manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns), manifest)
        self.assertEqual([(path.read_bytes(), path.stat().st_ino, path.stat().st_mtime_ns) for path in paths], before)
        self.assertNotEqual(self.ctl("commit-step-verdict", input_value=dict(draft, report="changed\n")).returncode, 0)
        paths[0].write_bytes(b"collision\n")
        self.assertNotEqual(self.ctl("start").returncode, 0)
        for collision in ("report", "verdict"):
            case = FirstStepTest(methodName="runTest")
            case.setUp()
            try:
                _worktree, _worker, output = case.proved_candidate()
                draft = case.verdict_draft(output)
                digest = test_verification.jigctl.sha256_bytes(draft["report"].encode())
                path = case.repo / (f".pi/jig/steps/0001/reviews/{digest}.md"
                    if collision == "report" else ".pi/jig/steps/0001/verdict.json")
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"preserve me\n")
                self.assertNotEqual(case.ctl("commit-step-verdict", input_value=draft).returncode, 0)
                self.assertEqual(path.read_bytes(), b"preserve me\n")
            finally:
                case.tearDown()

    def test_result_stages_kept_from_exact_proof_and_verdict_evidence(self):
        main_head = self.fixture.git("rev-parse", "HEAD").strip()
        _worktree, worker, output = self.proved_candidate()
        draft = self.verdict_draft(output)
        self.assertEqual(self.ctl("commit-step-verdict", input_value=draft).returncode, 0)
        first_step = self.manifest()["firstStep"].copy()
        prepared = self.ctl("prepare-step-result")
        self.assertEqual(prepared.returncode, 0, prepared.stderr)
        path = self.repo / ".pi/jig/steps/0001/result.json"
        result = json.loads(path.read_text())
        test_verification.jigctl.validate_instance(
            result, test_verification.jigctl.load_schema("result"))
        before = json.loads((self.repo / ".pi/jig/steps/0001/before.json").read_text())
        after = json.loads((self.repo / ".pi/jig/steps/0001/after.json").read_text())
        expected = before["commands"] + after["commands"]
        self.assertEqual([item["command"] for item in result["commands"]],
            [item["command"] for item in expected])
        for summary in result["commands"]:
            receipt = json.loads((self.repo / summary["receiptPath"]).read_text())
            self.assertEqual(summary, {key: value for key, value in (
                ("command", receipt["command"]), ("exitCode", receipt["exitCode"]),
                ("receiptPath", summary["receiptPath"]), ("outputSha256", receipt["outputSha256"]),
                ("finishedAt", receipt["finishedAt"]),
            )})
        verdict = json.loads((self.repo / ".pi/jig/steps/0001/verdict.json").read_text())
        self.assertEqual(result, {
            "schemaVersion": 1, "stepId": "0001", "outcome": "kept",
            "selectionPath": ".pi/jig/steps/0001/selection.json",
            "selectionSha256": worker["selectionSha256"],
            "proposalPath": ".pi/jig/steps/0001/proposal.json",
            "proposalSha256": worker["proposalSha256"],
            "inputRevision": worker["inputRevision"], "outputRevision": output["outputRevision"],
            "branch": worker["branch"], "worktree": worker["worktree"], "commands": result["commands"],
            "diffSha256": output["diffSha256"], "independentVerdict": {
                "status": verdict["status"], "evidencePath": verdict["reportPath"],
                "evidenceSha256": verdict["reportSha256"], "revision": output["outputRevision"],
            }, "recordedAt": result["recordedAt"],
        })
        manifest = self.manifest()
        self.assertEqual((manifest["currentState"], manifest["firstStep"]), ("step-running", first_step))
        self.assertEqual(self.fixture.git("rev-parse", "HEAD").strip(), main_head)
        started = json.loads(self.ctl("start").stdout)
        self.assertEqual(started["stagedResult"],
            {"outcome": "kept", "path": ".pi/jig/steps/0001/result.json"})
        self.assertNotIn("resume", started)

    def test_result_derives_reverted_and_missing_required_verdict_fails_closed(self):
        for scenario in ("failed-proof", "failed-verdict", "inconclusive-verdict", "missing-verdict"):
            case = FirstStepTest(methodName="runTest")
            case.setUp()
            try:
                candidate = case.selected_fixture()
                proposal = case.proposal_draft(candidate)
                if scenario == "failed-proof":
                    proposal["proof"]["targeted"]["commands"] = ["exit 1"]
                _worktree, _worker, output = case.proved_candidate(proposal)
                if scenario.endswith("verdict") and scenario != "missing-verdict":
                    status = scenario.removesuffix("-verdict")
                    self.assertEqual(case.ctl("commit-step-verdict",
                        input_value=case.verdict_draft(output, status=status)).returncode, 0)
                prepared = case.ctl("prepare-step-result")
                if scenario == "missing-verdict":
                    self.assertNotEqual(prepared.returncode, 0)
                    self.assertFalse((case.repo / ".pi/jig/steps/0001/result.json").exists())
                else:
                    self.assertEqual(prepared.returncode, 0, prepared.stderr)
                    result = json.loads((case.repo / ".pi/jig/steps/0001/result.json").read_text())
                    self.assertEqual(result["outcome"], "reverted")
                    self.assertEqual(case.manifest()["firstStep"]["outcome"], "pending")
            finally:
                case.tearDown()

    def test_result_retry_interruption_collision_and_evidence_drift_fail_closed(self):
        _worktree, _worker, output = self.proved_candidate()
        self.assertEqual(self.ctl("commit-step-verdict", input_value=self.verdict_draft(output)).returncode, 0)
        with mock.patch.object(test_verification.jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                test_verification.jigctl.prepare_step_result(self.repo, "isolated-shell")
        result_path = self.repo / ".pi/jig/steps/0001/result.json"
        result_before = (result_path.read_bytes(), result_path.stat().st_ino, result_path.stat().st_mtime_ns)
        recovered = self.ctl("prepare-step-result")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        manifest_path = self.repo / ".pi/jig/manifest.json"
        manifest_before = (manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns)
        self.assertEqual(self.ctl("prepare-step-result").returncode, 0)
        self.assertEqual((result_path.read_bytes(), result_path.stat().st_ino, result_path.stat().st_mtime_ns),
            result_before)
        self.assertEqual((manifest_path.read_bytes(), manifest_path.stat().st_ino, manifest_path.stat().st_mtime_ns),
            manifest_before)
        after_path = self.repo / ".pi/jig/steps/0001/after.json"
        after = after_path.read_bytes()
        after_path.write_bytes(after + b" ")
        self.assertNotEqual(self.ctl("prepare-step-result").returncode, 0)
        self.assertEqual(result_path.read_bytes(), result_before[0])
        after_path.write_bytes(after)
        result_path.write_bytes(b"preserve collision\n")
        self.assertNotEqual(self.ctl("prepare-step-result").returncode, 0)
        self.assertEqual(result_path.read_bytes(), b"preserve collision\n")


if __name__ == "__main__":
    unittest.main()

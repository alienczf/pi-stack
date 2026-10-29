"""Computed close is new functionality; broad staging is an existing-path correction."""
import hashlib
import json
import subprocess
from pathlib import Path
from dataclasses import replace
from unittest.mock import patch
from prime_support import PrimeCase, project, state
from engine import StreamsError


class NarrowStageTests(PrimeCase):
    def test_legacy_staging_does_not_capture_scratch(self):
        project.git(self.stream, "config", "user.name", "Test")
        project.git(self.stream, "config", "user.email", "test@example.com")
        (self.stream / "scratch.txt").write_text("not authorized\n")
        project.commit_repo(self.stream, "owned state only")
        self.assertNotIn("scratch.txt", project.git(self.stream, "ls-files").splitlines())
        self.assertEqual((self.stream / "scratch.txt").read_text(), "not authorized\n")
        self.assertNotIn(".prime/agent/settings.json", project.git(self.stream, "ls-files").splitlines())

    def test_foreign_staged_path_refuses_without_changing_index(self):
        (self.stream / "scratch.txt").write_text("foreign staged content\n")
        project.git(self.stream, "add", "scratch.txt")
        before = project.git(self.stream, "diff", "--cached", "--binary")
        with self.assertRaisesRegex(StreamsError, "unrelated staged"):
            project.commit_repo(self.stream, "must refuse")
        self.assertEqual(project.git(self.stream, "diff", "--cached", "--binary"), before)


class ComputedCloseTests(PrimeCase):
    def setUp(self):
        super().setUp()
        self.product = self.root / "product"
        self.product.mkdir()
        project.git(self.product, "init")
        project.git(self.product, "config", "user.name", "Test")
        project.git(self.product, "config", "user.email", "test@example.com")
        (self.product / "check_fixture.py").write_text('from pathlib import Path\np = Path("count")\np.write_text(str(int(p.read_text()) + 1) if p.exists() else "1")\nprint("actual deterministic check ran")\n')
        (self.product / "test_alternative.py").write_text('import unittest\nclass Alternative(unittest.TestCase):\n    def test_valid(self): self.assertEqual(2 + 2, 4)\n')
        project.git(self.product, "add", "--", "check_fixture.py", "test_alternative.py")
        project.git(self.product, "commit", "-m", "fixture")
        self.original = self.active()
        current = state.check_state(self.stream)
        goals = replace(current.goals, work=tuple(replace(w, workers=({"session": "worker", "worktree": str(self.product), "work": "A and B"},)) for w in current.goals.work))
        state.update_state(self.stream, expect=current.sha256, goals=goals, rules=None,
                           entry={"subject": "Assignment", "body": {}, "original_entries": [self.original]})
        proof = state.append_log(self.stream, subject="Findings", body={"original_entries": [self.original], "media_type": "text/plain", "text": "Implemented A and verified B against the whole intent", "sha256": state.sha256("Implemented A and verified B against the whole intent")})
        self.proofs = [{"entry": proof["entry"], "sha256": state.sha256(state.read_entry(self.stream, proof["entry"])), "representation": "full"}]
        self.report = self.product / "report.txt"
        self.report.write_text("Actual target and result report\n")
        output = self.product / "answer.json"
        output.write_text('{"answer": 5}\n')
        self.target = {"repo": str(self.product), "commit": project.git(self.product, "rev-parse", "HEAD").strip(),
                       "diff_sha256": state.sha256(project.git(self.product, "diff", "--binary", "--no-ext-diff", "HEAD", "--")),
                       "artifacts": {"answer.json": hashlib.sha256(output.read_bytes()).hexdigest()}}

    def close(self, **changes):
        args = {"expect": state.check_state(self.stream).sha256,
                "entry": {"subject": "Whole request checked", "original_entries": [self.original], "body": {"findings": "A and B answered against the original intent"}},
                "target": self.target, "check": {"argv": ["python3", "check_fixture.py"], "cwd": str(self.product)},
                "report": {"path": str(self.report), "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()},
                "proof_entries": self.proofs, "review": None}
        args.update(changes)
        return state.close_work(self.stream, **args)

    def test_actual_check_closes_whole_work_keeps_proof_and_null_review(self):
        first = self.close()
        saved = state._parse_entry(state.read_entry(self.stream, first["entry"]))
        self.assertEqual(saved.body["result"]["computed"]["argv"], ["python3", "check_fixture.py"])
        self.assertEqual(saved.body["result"]["computed"]["cwd"], str(self.product))
        self.assertEqual(saved.body["result"]["computed"]["exit"], 0)
        self.assertEqual(saved.body["result"]["computed"]["stdout"], "actual deterministic check ran\n")
        self.assertEqual(saved.body["review"], None)
        self.assertEqual(state.check_state(self.stream).goals.work, ())
        second = self.close()
        self.assertEqual(second["entry"], first["entry"])
        self.assertEqual((self.product / "count").read_text(), "1")
        self.assertIn("Implement A and verify B", state.read_entry(self.stream, self.original))

    def test_wrong_original_target_report_and_missing_proof_leave_work_open(self):
        before = state.check_state(self.stream)
        cases = [
            {"entry": {"subject": "Wrong original", "original_entries": [], "body": {"findings": "claimed"}}},
            {"target": {**self.target, "commit": "0" * 40}},
            {"report": {"path": str(self.report), "sha256": "0" * 64}},
            {"proof_entries": []},
            {"proof_entries": [{**self.proofs[0], "sha256": "0" * 64}]},
            {"check": {"argv": ["sbatch", "uncertain-job.sh"], "cwd": str(self.product)}},
        ]
        for change in cases:
            with self.subTest(change=change):
                with self.assertRaises(StreamsError):
                    self.close(**change)
                self.assertEqual(state.check_state(self.stream).sha256, before.sha256)
        self.assertFalse((self.product / "count").exists())

    def test_cli_runs_the_same_computed_check_and_returns_exact_schema(self):
        payload = {"goals": None, "rules": None, "entry": {"subject": "CLI computed close", "original_entries": [self.original], "body": {"findings": "A and B verified"}},
                   "target": self.target, "check": {"argv": ["python3", "check_fixture.py"], "cwd": str(self.product)},
                   "report": {"path": str(self.report), "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()}, "proof_entries": self.proofs, "review": None}
        cli = Path(__file__).resolve().parents[2] / "bin/pi-streams"
        result = subprocess.run([str(cli), "state", "close", str(self.stream), "--expect", state.check_state(self.stream).sha256], input=json.dumps(payload), text=True, capture_output=True)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        data = json.loads(result.stdout)
        self.assertEqual(set(data), {"success", "reason", "state_sha256", "history_files"})
        self.assertEqual(data["success"], True)
        self.assertEqual((self.product / "count").read_text(), "1")
        self.assertEqual(state.check_state(self.stream).goals.work, ())

    def test_changed_untracked_product_after_passing_check_cannot_close(self):
        from checks import state as checker
        output = self.product / "answer.json"
        output.write_text('{"answer": 5}\n')
        actual = checker.run_check
        def mutate(check, target):
            result = actual(check, target)
            self.assertEqual(result["exit"], 0)
            output.write_text('{"answer": 6}\n')
            return result
        with patch.object(checker, "run_check", side_effect=mutate):
            with self.assertRaisesRegex(StreamsError, "target.*artifact|artifact.*target"):
                self.close()
        self.assertEqual(len(state.check_state(self.stream).goals.work), 1)
        self.assertEqual(output.read_text(), '{"answer": 6}\n')

    def test_report_traversal_is_rejected_before_reading_outside_target(self):
        from checks.state import report_bytes
        outside = self.root / "outside-report.txt"
        outside.write_text("outside target\n")
        with self.assertRaisesRegex(StreamsError, "traversal|escape"):
            report_bytes({"repo": str(self.product)}, {"path": str(self.product / "../outside-report.txt"), "sha256": hashlib.sha256(outside.read_bytes()).hexdigest()})
        self.assertEqual(report_bytes(self.target, {"path": str(self.report), "sha256": hashlib.sha256(self.report.read_bytes()).hexdigest()}), self.report.read_bytes())

    def test_target_output_manifest_is_required_and_cannot_traverse(self):
        missing = {key: value for key, value in self.target.items() if key != "artifacts"}
        with self.assertRaisesRegex(StreamsError, "target artifacts"):
            self.close(target=missing)
        with self.assertRaisesRegex(StreamsError, "traversal"):
            self.close(target={**self.target, "artifacts": {"../outside.json": "0" * 64}})
        self.assertEqual(len(state.check_state(self.stream).goals.work), 1)
        self.assertFalse((self.product / "count").exists())

    def test_actual_failed_check_keeps_request_open(self):
        with self.assertRaisesRegex(StreamsError, "computed check failed"):
            self.close(check={"argv": ["python3", "-m", "unittest", "nonexistent_test"], "cwd": str(self.product)})
        self.assertEqual(len(state.check_state(self.stream).goals.work), 1)

    def test_excerpt_proof_requires_the_exact_named_original_range(self):
        full = state.append_log(self.stream, subject="Full proof", body={"original_entries": [self.original], "media_type": "text/plain", "text": "first\nsecond 原文\n", "sha256": state.sha256("first\nsecond 原文\n")})
        excerpt = state.append_log(self.stream, subject="Excerpt", body={"original_entries": [self.original], "media_type": "text/plain", "text": "second 原文\n", "sha256": state.sha256("second 原文\n")})
        proof = {"entry": excerpt["entry"], "sha256": state.sha256(state.read_entry(self.stream, excerpt["entry"])), "representation": "excerpt", "original": full["entry"], "range": [1, 1]}
        with self.assertRaisesRegex(StreamsError, "named original line range"):
            self.close(proof_entries=[proof])
        proof["range"] = [2, 2]
        self.assertEqual(self.close(proof_entries=[proof])["success"], True)
        self.assertEqual(state.check_state(self.stream).goals.work, ())

    def test_valid_alternative_test_is_accepted(self):
        result = self.close(check={"argv": ["python3", "-m", "unittest", "test_alternative"], "cwd": str(self.product)})
        self.assertEqual(result["success"], True)
        self.assertEqual(state.check_state(self.stream).goals.work, ())

    def test_changed_instructions_during_check_refuse_publication_and_lock_is_free(self):
        from checks import state as checker
        actual = checker.run_check
        def change(check, target):
            with project.stream_lock(self.stream):
                current = state.check_state(self.stream)
                state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="paused"), rules=None,
                    entry={"subject": "Operator changed instructions", "body": {}, "original_entries": []}, locked=True)
            return actual(check, target)
        with patch.object(checker, "run_check", side_effect=change):
            with self.assertRaisesRegex(StreamsError, "stale Goals/Rules"):
                self.close()
        self.assertEqual(state.check_state(self.stream).goals.status, "paused")
        self.assertEqual(len(state.check_state(self.stream).goals.work), 1)
        self.assertEqual((self.product / "count").read_text(), "1")

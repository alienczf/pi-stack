import hashlib
import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "bin" / "jigctl.py"
FIXTURES = ROOT / "scripts" / "jig_tests" / "fixtures"

spec = importlib.util.spec_from_file_location("jigctl_commandments", CONTROLLER)
jigctl = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(jigctl)


class CommandmentsTest(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.external = tempfile.TemporaryDirectory()
        self.repo = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "jig@example.invalid")
        self.git("config", "user.name", "Jig Fixture")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "fixture")
        self.answers = json.loads(
            (FIXTURES / "commandments-answers.json").read_text(encoding="utf-8")
        )

    def tearDown(self):
        self.external.cleanup()
        self.temporary.cleanup()

    def git(self, *arguments):
        return subprocess.run(
            ["git", "-C", str(self.repo), *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        ).stdout

    def ctl(self, *arguments, input_value=None, input_text=None, isolation="isolated-shell"):
        command = [sys.executable, str(CONTROLLER), *arguments]
        if arguments and arguments[0] != "validate-schema" and "--resource-isolation" not in arguments:
            command += ["--resource-isolation", isolation]
        if input_value is not None:
            input_text = json.dumps(input_value)
        return subprocess.run(
            command,
            cwd=self.repo,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi"},
        )

    def manifest_path(self):
        return self.repo / ".pi" / "jig" / "manifest.json"

    def manifest(self):
        return json.loads(self.manifest_path().read_text(encoding="utf-8"))

    def profile(self):
        return {
            "schemaVersion": 1,
            "repositoryRevision": self.git("rev-parse", "HEAD").strip(),
            "productType": {
                "value": "test repository",
                "evidence": [{"path": "README.md", "line": 1, "note": "Fixture evidence."}],
            },
            "languages": [],
            "frameworks": [],
            "buildTools": [],
            "ci": [],
            "entryPoints": [],
            "topology": [],
            "unknowns": [],
            "failureModes": [],
        }

    def prepare(self, present=True, isolation="isolated-shell"):
        started = self.ctl("start", isolation=isolation)
        self.assertEqual(started.returncode, 0, started.stderr)
        committed = self.ctl("commit-profile", input_value=self.profile(), isolation=isolation)
        self.assertEqual(committed.returncode, 0, committed.stderr)
        if present:
            shown = self.ctl("present-commandments", isolation=isolation)
            self.assertEqual(shown.returncode, 0, shown.stderr)
            return json.loads(shown.stdout)
        return None

    def stage(self, answers=None, *extra, isolation="isolated-shell"):
        result = self.ctl(
            "stage-commandments",
            *extra,
            input_value=self.answers if answers is None else answers,
            isolation=isolation,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads(result.stdout)

    def ratify(self, staging, marker="I ratify these exact repository COMMANDMENTS."):
        return self.ctl(
            "ratify-commandments",
            "--candidate-sha",
            staging["candidateSha256"],
            "--operator-marker",
            marker,
        )

    def snapshot(self):
        return {
            path.relative_to(self.repo).as_posix(): path.read_bytes()
            for path in self.repo.rglob("*")
            if path.is_file() and ".git" not in path.parts and path.name != "init.lock"
        }

    def test_interview_presentation_is_one_durable_idempotent_round(self):
        first = self.prepare()
        path = self.repo / ".pi" / "jig" / "commandments" / "interview.json"
        raw = path.read_bytes()
        second = self.ctl("present-commandments")
        self.assertEqual(second.returncode, 0, second.stderr)
        self.assertEqual(path.read_bytes(), raw)
        self.assertEqual(json.loads(second.stdout), first)
        self.assertEqual(first["round"], 1)
        self.assertEqual(len(first["questions"]), 8)
        self.assertTrue(all("recommendedDefault" in item for item in first["questions"]))
        self.assertNotIn("answers", first)
        self.assertIn("Do not start a second interview round.", first["rules"])

    def test_missing_partial_and_unselected_defaults_cannot_stage(self):
        presentation = self.prepare()
        default_text = presentation["questions"][0]["recommendedDefault"]
        for value in ({}, {"schemaVersion": 1}, {**self.answers, "authority": {"selection": "custom"}}):
            before = self.snapshot()
            result = self.ctl("stage-commandments", input_value=value)
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.snapshot(), before)
        custom = json.loads(json.dumps(self.answers))
        custom["requiredInitOutcome"] = {"selection": "custom", "value": "Finish one explicit result."}
        staged = self.stage(custom)
        candidate = (self.repo / staged["candidatePath"]).read_text(encoding="utf-8")
        self.assertNotIn(default_text, candidate)
        self.assertIn("Finish one explicit result.", candidate)

    def test_explicit_free_text_answers_render_hard_and_directional_entries(self):
        self.prepare()
        answers = json.loads(json.dumps(self.answers))
        answers["hardForbiddenOutcomes"] = {
            "selection": "custom",
            "value": ["Never remove saved user data.", "Never publish without proof."],
        }
        answers["protectedUserPath"] = {
            "selection": "custom",
            "value": {
                "action": "Run example save.",
                "visibleResult": "The saved value appears.",
                "evidence": "Read the persisted value.",
                "cleanup": "Delete the fixture value.",
                "thresholds": "Complete within two seconds.",
            },
        }
        staged = self.stage(answers)
        text = (self.repo / staged["candidatePath"]).read_text(encoding="utf-8")
        self.assertIn("### CMD-001. Required init outcome", text)
        self.assertIn("### CMD-002. Forbidden outcomes", text)
        self.assertIn("### CMD-101. Protect the user path", text)
        self.assertIn("### CMD-102. Apply the tradeoff order", text)
        self.assertIn("Never remove saved user data.", text)
        self.assertIn("Run example save.", text)
        self.assertIn("Keep the public command stable.", text)

    def test_candidate_matches_template_structure_and_digest_is_stable(self):
        self.prepare()
        first = self.stage()
        raw = (self.repo / first["candidatePath"]).read_bytes()
        self.assertEqual(hashlib.sha256(raw).hexdigest(), first["candidateSha256"])
        metadata = jigctl.validate_commandments_bytes(raw)
        self.assertEqual(metadata["version"], 1)
        self.assertNotIn(b"{{", raw)
        template = (ROOT / "skills" / "jig" / "references" / "COMMANDMENTS.template.md").read_text()
        for heading in (
            "## Hard commandments",
            "## Directional commandments",
            "## Protected user path",
            "## Proof policy",
            "## Ratification",
        ):
            self.assertEqual(raw.decode().count(heading), template.count(heading))
        second = self.stage()
        self.assertEqual(second["candidateSha256"], first["candidateSha256"])
        self.assertEqual((self.repo / second["candidatePath"]).read_bytes(), raw)

    def test_ratification_requires_exact_digest_and_marker(self):
        self.prepare()
        staged = self.stage()
        root = self.repo / "COMMANDMENTS.md"
        for digest, marker in (("0" * 64, staged["intendedMarker"]), (staged["candidateSha256"], "wrong marker")):
            result = self.ctl(
                "ratify-commandments",
                "--candidate-sha",
                digest,
                "--operator-marker",
                marker,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertFalse(root.exists())
            self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        result = self.ratify(staged)
        self.assertEqual(result.returncode, 0, result.stderr)
        manifest = self.manifest()
        candidate = (self.repo / staged["candidatePath"]).read_bytes()
        self.assertEqual(root.read_bytes(), candidate)
        self.assertEqual(manifest["currentState"], "commandments-ratified")
        self.assertEqual(manifest["commandments"]["sha256"], staged["candidateSha256"])
        self.assertIn(
            {"path": "COMMANDMENTS.md", "owner": "human", "sha256": staged["candidateSha256"]},
            manifest["artifacts"],
        )

    def test_amend_and_defer_never_advance_or_publish(self):
        self.prepare()
        staged = self.stage()
        for decision in ("defer", "amend"):
            result = self.ctl(
                "record-commandments-decision",
                "--decision",
                decision,
                "--candidate-sha",
                staged["candidateSha256"],
                "--operator-marker",
                f"Operator chose {decision}.",
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
            self.assertFalse((self.repo / "COMMANDMENTS.md").exists())

    def test_amendment_requires_current_digest_and_complete_new_answers(self):
        self.prepare()
        first = self.stage()
        changed = json.loads(json.dumps(self.answers))
        changed["compatibilityPolicy"] = {"selection": "custom", "value": "Keep every public command."}
        before_rejected = self.snapshot()
        rejected = self.ctl("stage-commandments", input_value=changed)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.snapshot(), before_rejected)
        wrong = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            "0" * 64,
            "--operator-marker",
            "Amend compatibility.",
        )
        self.assertNotEqual(wrong.returncode, 0)
        accepted = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            first["candidateSha256"],
            "--operator-marker",
            "Amend compatibility.",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        second = self.stage(changed, "--amend-candidate-sha", first["candidateSha256"])
        self.assertNotEqual(second["candidateSha256"], first["candidateSha256"])
        stale = self.ratify(first)
        self.assertNotEqual(stale.returncode, 0)

    def test_matching_rerun_and_force_like_retry_are_byte_stable(self):
        self.prepare()
        staged = self.stage()
        self.assertEqual(self.ratify(staged).returncode, 0)
        before = self.snapshot()
        self.assertEqual(self.ratify(staged).returncode, 0)
        self.assertEqual(self.ctl("start").returncode, 0)
        self.assertEqual(self.snapshot(), before)
        forced = self.ctl("start", "--force")
        self.assertEqual(forced.returncode, 2)
        self.assertEqual(self.snapshot(), before)

    def test_changed_root_hash_fails_closed_without_repair(self):
        self.prepare()
        staged = self.stage()
        self.assertEqual(self.ratify(staged).returncode, 0)
        root = self.repo / "COMMANDMENTS.md"
        root.write_text(root.read_text() + "changed\n", encoding="utf-8")
        changed = root.read_bytes()
        before = self.manifest_path().read_bytes()
        for command in (("start",), ("validate-commandments",)):
            result = self.ctl(*command)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("amendment and re-ratification", result.stderr)
            self.assertEqual(root.read_bytes(), changed)
            self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_preexisting_unknown_root_is_preserved_then_exactly_adopted(self):
        self.prepare()
        existing = jigctl.render_commandments_candidate(
            jigctl.validate_commandments_answers(self.answers)[0],
            "2026-01-01T00:00:00Z",
        )
        existing = existing.replace(
            b"**Scope.** Jig init through the first terminal improvement outcome.",
            b"**Scope.** Manually authored repository initialization policy.",
            1,
        )
        root = self.repo / "COMMANDMENTS.md"
        root.write_bytes(existing)
        generated = self.stage()
        rejected = self.ratify(generated)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(root.read_bytes(), existing)
        adopted_answers = json.loads(json.dumps(self.answers))
        accepted = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            generated["candidateSha256"],
            "--operator-marker",
            "Adopt the existing exact file.",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        adopted = self.stage(
            adopted_answers,
            "--amend-candidate-sha",
            generated["candidateSha256"],
            "--adopt-existing",
        )
        self.assertEqual((self.repo / adopted["candidatePath"]).read_bytes(), existing)
        self.assertEqual(self.ratify(adopted).returncode, 0)
        self.assertEqual(root.read_bytes(), existing)

    def test_agent_amendment_proposal_is_separate_and_non_authoritative(self):
        self.prepare()
        staged = self.stage()
        self.assertEqual(self.ratify(staged).returncode, 0)
        before = self.manifest()["commandments"].copy()
        root = (self.repo / "COMMANDMENTS.md").read_bytes()
        proposal = self.ctl(
            "propose-commandments-amendment",
            input_text="# Proposed amendment\n\nChange CMD-102 after operator review.\n",
        )
        self.assertEqual(proposal.returncode, 0, proposal.stderr)
        receipt = json.loads(proposal.stdout)
        self.assertIn("/proposals/", receipt["path"])
        self.assertEqual(self.manifest()["commandments"], before)
        self.assertEqual((self.repo / "COMMANDMENTS.md").read_bytes(), root)

    def test_candidate_staging_crash_reconciles_without_duplicate_interview(self):
        self.prepare()
        with mock.patch.object(jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                jigctl.stage_commandments(
                    self.repo,
                    "isolated-shell",
                    json.dumps(self.answers).encode(),
                    None,
                    False,
                )
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        resumed = self.stage()
        paths = {item["path"] for item in self.manifest()["artifacts"]}
        self.assertIn(resumed["candidatePath"], paths)
        self.assertIn(resumed["answersPath"], paths)
        self.assertEqual(self.ctl("present-commandments").returncode, 0)

    def test_root_publication_crash_window_converges(self):
        self.prepare()
        staged = self.stage()
        candidate = (self.repo / staged["candidatePath"]).read_bytes()
        (self.repo / "COMMANDMENTS.md").write_bytes(candidate)
        self.assertEqual(self.ctl("start").returncode, 0)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        self.assertEqual(self.ratify(staged).returncode, 0)

    def test_receipt_and_manifest_crash_window_converges(self):
        self.prepare()
        staged = self.stage()
        with mock.patch.object(jigctl, "write_manifest", side_effect=RuntimeError("crash")):
            with self.assertRaises(RuntimeError):
                jigctl.ratify_commandments(
                    self.repo,
                    "isolated-shell",
                    staged["candidateSha256"],
                    staged["intendedMarker"],
                )
        receipt = self.repo / ".pi" / "jig" / "receipts" / "transition-0003-commandments-ratified.json"
        self.assertTrue(receipt.is_file())
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        self.assertEqual(self.ctl("start").returncode, 0)
        self.assertTrue(receipt.is_file())
        self.assertEqual(self.ratify(staged).returncode, 0)
        self.assertEqual(self.manifest()["currentState"], "commandments-ratified")

    def test_manifest_temporary_window_does_not_infer_ratification(self):
        self.prepare()
        staged = self.stage()
        temporary = self.repo / ".pi" / "jig" / f".jigctl-manifest.json.1.{uuid.uuid4().hex}.tmp"
        temporary.write_bytes(b"partial manifest")
        before_candidate = (self.repo / staged["candidatePath"]).read_bytes()
        result = self.ctl("start")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        self.assertFalse(temporary.exists())
        self.assertEqual((self.repo / staged["candidatePath"]).read_bytes(), before_candidate)

    def test_ratification_receipt_has_exact_kind_source_index_and_digests(self):
        self.prepare()
        staged = self.stage()
        self.assertEqual(self.ratify(staged).returncode, 0)
        manifest = self.manifest()
        transition = manifest["transitions"][-1]
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        self.assertEqual(receipt["kind"], "commandments-ratified")
        self.assertEqual(receipt["from"], "awaiting-commandments")
        self.assertEqual(receipt["to"], "commandments-ratified")
        self.assertEqual(receipt["commandmentsSha256"], staged["candidateSha256"])
        self.assertEqual(receipt["resourceIsolation"], "isolated-shell")
        jigctl.validate_transition_receipt(
            self.repo,
            receipt,
            ("awaiting-commandments", "commandments-ratified"),
            manifest["source"],
            transition["at"],
        )

    def test_invalid_or_stale_ratification_receipt_is_preserved_and_rejected(self):
        self.prepare()
        staged = self.stage()
        path = self.repo / ".pi" / "jig" / "receipts" / "transition-0003-commandments-ratified.json"
        path.write_text("{}\n", encoding="utf-8")
        before = path.read_bytes()
        result = self.ratify(staged)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(path.read_bytes(), before)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        self.assertFalse((self.repo / "COMMANDMENTS.md").exists())

    def test_expected_commandments_change_does_not_mask_unrelated_source_drift(self):
        self.prepare()
        staged = self.stage()
        (self.repo / "COMMANDMENTS.md").write_bytes((self.repo / staged["candidatePath"]).read_bytes())
        self.assertEqual(self.ctl("start").returncode, 0)
        (self.repo / "unrelated.txt").write_text("drift\n", encoding="utf-8")
        before = self.manifest_path().read_bytes()
        result = self.ratify(staged)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source revision or dirty summary changed", result.stderr)
        self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_current_session_and_shell_routes_remain_honest(self):
        self.prepare(isolation="inherited-session")
        presentation = self.ctl("present-commandments", isolation="inherited-session")
        self.assertEqual(presentation.returncode, 0, presentation.stderr)
        shown = json.loads(presentation.stdout)
        self.assertEqual(shown["resourceIsolation"], "inherited-session")
        self.assertIn("cannot be unloaded", shown["routeNotice"])
        wrong = self.ctl("present-commandments", isolation="isolated-shell")
        self.assertNotEqual(wrong.returncode, 0)
        self.assertIn("different resourceIsolation route", wrong.stderr)
        self.assertEqual(self.manifest()["resourceIsolation"], "inherited-session")

    def test_noninteractive_resume_operations_execute_through_ratification(self):
        self.prepare(present=False)
        awaiting = self.ctl("start")
        self.assertEqual(awaiting.returncode, 0, awaiting.stderr)
        output = json.loads(awaiting.stdout)
        operations = {
            item["name"]: item for item in output["resume"]["operations"]
        }
        self.assertEqual(output["state"], "awaiting-commandments")
        self.assertIn("does not consume response files", output["resume"]["note"])
        self.assertEqual(
            operations["stage"]["stdin"],
            ".pi/jig/commandments/answers.input.json",
        )
        presented = self.ctl(*operations["present"]["command"])
        self.assertEqual(presented.returncode, 0, presented.stderr)
        staged = self.ctl(
            *operations["stage"]["command"], input_value=self.answers
        )
        self.assertEqual(staged.returncode, 0, staged.stderr)
        staged_output = json.loads(staged.stdout)
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        resumed_output = json.loads(resumed.stdout)
        self.assertEqual(
            resumed_output["candidate"]["sha256"],
            staged_output["candidateSha256"],
        )
        next_operations = {
            item["name"]: item
            for item in resumed_output["resume"]["operations"]
        }
        self.assertIn(
            staged_output["candidateSha256"],
            next_operations["amend"]["followUp"]["command"],
        )
        ratified = self.ctl(*next_operations["ratify"]["command"])
        self.assertEqual(ratified.returncode, 0, ratified.stderr)
        self.assertEqual(self.manifest()["currentState"], "commandments-ratified")

    def test_amended_staging_manifest_crash_converges(self):
        self.prepare()
        first = self.stage()
        accepted = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            first["candidateSha256"],
            "--operator-marker",
            "Amend compatibility.",
        )
        self.assertEqual(accepted.returncode, 0, accepted.stderr)
        changed = json.loads(json.dumps(self.answers))
        changed["compatibilityPolicy"] = {
            "selection": "custom",
            "value": "Keep every public command.",
        }
        with mock.patch.object(
            jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                jigctl.stage_commandments(
                    self.repo,
                    "isolated-shell",
                    json.dumps(changed).encode(),
                    first["candidateSha256"],
                    False,
                )
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        recovery_operations = {
            item["name"]: item
            for item in json.loads(resumed.stdout)["resume"]["operations"]
        }
        self.assertIn(
            first["candidateSha256"], recovery_operations["stage"]["command"]
        )
        staged_result = self.ctl(
            *recovery_operations["stage"]["command"], input_value=changed
        )
        self.assertEqual(staged_result.returncode, 0, staged_result.stderr)
        second = json.loads(staged_result.stdout)
        ratified = self.ratify(second)
        self.assertEqual(ratified.returncode, 0, ratified.stderr)

    def test_root_publication_temporary_reconciles_by_candidate_token(self):
        self.prepare()
        staged = self.stage()
        candidate = (self.repo / staged["candidatePath"]).read_bytes()
        temporaries = [
            self.repo / (
                f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
                f"424242.{uuid.uuid4().hex}.tmp"
            ),
            self.repo / (
                f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
                f"424243.{uuid.uuid4().hex}.tmp"
            ),
        ]
        temporaries[0].write_bytes(candidate)
        temporaries[1].write_bytes(candidate[: len(candidate) // 2])
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        self.assertTrue(all(not path.exists() for path in temporaries))
        recovered = [
            item
            for item in self.manifest()["artifacts"]
            if "interrupted-write" in item["path"]
        ]
        self.assertEqual(len(recovered), 2)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")

    def test_unknown_root_temporary_is_preserved_and_blocks_source_drift(self):
        self.prepare()
        staged = self.stage()
        candidate = (self.repo / staged["candidatePath"]).read_bytes()
        temporary = self.repo / (
            f".jigctl-COMMANDMENTS.md.{'0' * 64}."
            f"424242.{uuid.uuid4().hex}.tmp"
        )
        temporary.write_bytes(candidate[: len(candidate) // 2])
        resumed = self.ctl("start")
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("source revision or dirty summary changed", resumed.stderr)
        self.assertTrue(temporary.exists())

    def test_root_temporary_lookalikes_with_public_digest_are_preserved(self):
        self.prepare()
        staged = self.stage()
        candidate = (self.repo / staged["candidatePath"]).read_bytes()
        wrong_content = self.repo / (
            f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
            f"424242.{uuid.uuid4().hex}.tmp"
        )
        tokenless = self.repo / (
            f".jigctl-COMMANDMENTS.md.424243.{uuid.uuid4().hex}.tmp"
        )
        empty = self.repo / (
            f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
            f"424244.{uuid.uuid4().hex}.tmp"
        )
        wrong_content.write_bytes(b"not candidate bytes")
        tokenless.write_bytes(candidate[: len(candidate) // 2])
        empty.write_bytes(b"")
        resumed = self.ctl("start")
        self.assertNotEqual(resumed.returncode, 0)
        self.assertIn("source revision or dirty summary changed", resumed.stderr)
        self.assertTrue(wrong_content.exists())
        self.assertTrue(tokenless.exists())
        self.assertTrue(empty.exists())
        recovered = [
            item
            for item in self.manifest()["artifacts"]
            if "interrupted-write" in item["path"]
        ]
        self.assertEqual(recovered, [])

    def test_matching_root_temporary_symlink_and_fifo_are_preserved(self):
        self.prepare()
        staged = self.stage()
        outside = Path(self.external.name) / "outside"
        outside.write_bytes(b"outside")
        symlink = self.repo / (
            f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
            f"424242.{uuid.uuid4().hex}.tmp"
        )
        fifo = self.repo / (
            f".jigctl-COMMANDMENTS.md.{staged['candidateSha256']}."
            f"424243.{uuid.uuid4().hex}.tmp"
        )
        symlink.symlink_to(outside)
        os.mkfifo(fifo)
        recovered = jigctl.reconcile_commandments_root_temporaries(
            self.repo, self.manifest()
        )
        self.assertEqual(recovered, [])
        self.assertTrue(symlink.is_symlink())
        self.assertTrue(fifo.exists())
        self.assertEqual(outside.read_bytes(), b"outside")

    def test_adoption_validator_rejects_blank_and_misplaced_fields(self):
        resolved, _modes = jigctl.validate_commandments_answers(self.answers)
        raw = jigctl.render_commandments_candidate(
            resolved, "2026-01-01T00:00:00Z"
        )
        blank = raw.replace(
            b"**Proof.** Prove the changed behavior",
            b"**Proof.** ",
            1,
        )
        with self.assertRaises(jigctl.ValidationError):
            jigctl.validate_commandments_bytes(blank)
        text = raw.decode()
        misplaced = text.replace(
            "## Hard commandments", "## TEMP", 1
        ).replace(
            "## Directional commandments", "## Hard commandments", 1
        ).replace("## TEMP", "## Directional commandments", 1)
        with self.assertRaises(jigctl.ValidationError):
            jigctl.validate_commandments_bytes(misplaced.encode())
        self.prepare()
        (self.repo / "COMMANDMENTS.md").write_bytes(blank)
        rejected = self.ctl(
            "stage-commandments",
            "--adopt-existing",
            input_value=self.answers,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertNotIn("COMMANDMENTS.md", {
            item["path"] for item in self.manifest()["artifacts"]
        })

    def test_adoption_validator_rejects_empty_required_sections(self):
        resolved, _modes = jigctl.validate_commandments_answers(self.answers)
        raw = jigctl.render_commandments_candidate(
            resolved, "2026-01-01T00:00:00Z"
        )
        text = raw.decode()
        sections = (
            ("## Protected user path", "## Proof policy"),
            ("## Proof policy", "## Compatibility policy"),
            ("## Compatibility policy", "## Autonomy policy"),
            ("## Autonomy policy", "## Tradeoff order"),
            ("## Tradeoff order", "## Amendment policy"),
            ("## Amendment policy", "## Ratification"),
        )
        self.prepare()
        before = self.manifest_path().read_bytes()
        for heading, next_heading in sections:
            start = text.index("\n", text.index(heading)) + 1
            end = text.index(next_heading)
            empty = (text[:start] + "\n" + text[end:]).encode()
            with self.subTest(section=heading):
                with self.assertRaises(jigctl.ValidationError):
                    jigctl.validate_commandments_bytes(empty)
                (self.repo / "COMMANDMENTS.md").write_bytes(empty)
                rejected = self.ctl(
                    "stage-commandments",
                    "--adopt-existing",
                    input_value=self.answers,
                )
                self.assertNotEqual(rejected.returncode, 0)
                self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_adoption_validator_rejects_duplicate_and_misordered_policy_fields(self):
        resolved, _modes = jigctl.validate_commandments_answers(self.answers)
        raw = jigctl.render_commandments_candidate(
            resolved, "2026-01-01T00:00:00Z"
        )
        duplicate = raw.replace(
            b"**Action.** Run",
            b"**Action.** Duplicate.\n\n**Action.** Run",
            1,
        )
        reordered = raw.replace(
            b"- Baseline requirement:",
            b"- TEMP requirement:",
            1,
        ).replace(
            b"- Targeted verification:",
            b"- Baseline requirement:",
            1,
        ).replace(
            b"- TEMP requirement:",
            b"- Targeted verification:",
            1,
        )
        bad_order = raw.replace(b"2. User-visible", b"3. User-visible", 1)
        duplicate_autonomy = raw.replace(
            b"- Agents may open pull requests and drive them to merge-ready.",
            b"- Agents may edit and test in isolated worktrees.",
            1,
        )
        duplicate_tradeoff = raw.replace(
            b"2. User-visible reliability",
            b"2. Correctness and safety",
            1,
        )
        control = raw.replace(
            b"\n\nDo not introduce a user-visible",
            b"\n\n\tDo not introduce a user-visible",
            1,
        )
        values = (
            duplicate,
            reordered,
            bad_order,
            duplicate_autonomy,
            duplicate_tradeoff,
            control,
        )
        for value in values:
            self.assertNotEqual(value, raw)
            with self.assertRaises(jigctl.ValidationError):
                jigctl.validate_commandments_bytes(value)
        self.prepare()
        before = self.manifest_path().read_bytes()
        for value in values:
            (self.repo / "COMMANDMENTS.md").write_bytes(value)
            rejected = self.ctl(
                "stage-commandments",
                "--adopt-existing",
                input_value=self.answers,
            )
            self.assertNotEqual(rejected.returncode, 0)
            self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_exact_adoption_staging_crashes_emit_complete_retries(self):
        self.prepare()
        resolved, _modes = jigctl.validate_commandments_answers(self.answers)
        existing = jigctl.render_commandments_candidate(
            resolved, "2026-01-01T00:00:00Z"
        )
        (self.repo / "COMMANDMENTS.md").write_bytes(existing)
        with mock.patch.object(
            jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                jigctl.stage_commandments(
                    self.repo,
                    "isolated-shell",
                    json.dumps(self.answers).encode(),
                    None,
                    True,
                )
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        operation = {
            item["name"]: item
            for item in json.loads(resumed.stdout)["resume"]["operations"]
        }["stage"]
        self.assertIn("--adopt-existing", operation["command"])
        retried = self.ctl(*operation["command"], input_value=self.answers)
        self.assertEqual(retried.returncode, 0, retried.stderr)
        first = json.loads(retried.stdout)
        decision = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            first["candidateSha256"],
            "--operator-marker",
            "Amend exact adoption.",
        )
        self.assertEqual(decision.returncode, 0, decision.stderr)
        changed = json.loads(json.dumps(self.answers))
        changed["compatibilityPolicy"] = {
            "selection": "custom",
            "value": "Preserve every public command.",
        }
        with mock.patch.object(
            jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                jigctl.stage_commandments(
                    self.repo,
                    "isolated-shell",
                    json.dumps(changed).encode(),
                    first["candidateSha256"],
                    True,
                )
        resumed = self.ctl("start")
        self.assertEqual(resumed.returncode, 0, resumed.stderr)
        operation = {
            item["name"]: item
            for item in json.loads(resumed.stdout)["resume"]["operations"]
        }["stage"]
        self.assertIn("--adopt-existing", operation["command"])
        self.assertIn(first["candidateSha256"], operation["command"])
        retried = self.ctl(*operation["command"], input_value=changed)
        self.assertEqual(retried.returncode, 0, retried.stderr)

    def test_generated_staging_requires_candidate_answer_equality(self):
        self.prepare()
        staged = self.stage()
        alternate_answers = json.loads(json.dumps(self.answers))
        alternate_answers["compatibilityPolicy"] = {
            "selection": "custom",
            "value": "A different compatibility policy.",
        }
        alternate_resolved, _modes = jigctl.validate_commandments_answers(
            alternate_answers
        )
        alternate = jigctl.render_commandments_candidate(
            alternate_resolved,
            staged["prospectiveRatifiedAt"],
            staged["version"],
        )
        alternate_digest = hashlib.sha256(alternate).hexdigest()
        alternate_path = (
            f".pi/jig/commandments/candidates/{alternate_digest}.md"
        )
        jigctl.write_exact_artifact(self.repo, alternate_path, alternate)
        pointer_path = self.repo / ".pi/jig/commandments/staging.json"
        pointer = json.loads(pointer_path.read_text())
        pointer["candidatePath"] = alternate_path
        pointer["candidateSha256"] = alternate_digest
        pointer_path.write_bytes(jigctl.canonical_json(pointer))
        before = self.manifest_path().read_bytes()
        rejected = self.ctl("stage-commandments", input_value=self.answers)
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.manifest_path().read_bytes(), before)
        self.assertNotIn(
            alternate_path, {item["path"] for item in self.manifest()["artifacts"]}
        )

    def test_adopted_staging_requires_exact_answer_marker(self):
        self.prepare()
        resolved, _modes = jigctl.validate_commandments_answers(self.answers)
        candidate = jigctl.render_commandments_candidate(
            resolved, "2026-01-01T00:00:00Z"
        )
        root_path = self.repo / "COMMANDMENTS.md"
        root_path.write_bytes(candidate)
        with mock.patch.object(
            jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                jigctl.stage_commandments(
                    self.repo,
                    "isolated-shell",
                    json.dumps(self.answers).encode(),
                    None,
                    True,
                )
        pointer_path = self.repo / ".pi/jig/commandments/staging.json"
        pointer = json.loads(pointer_path.read_text())
        changed_answers = json.loads(json.dumps(self.answers))
        changed_answers["authority"]["value"]["ratificationMarker"] = (
            "I ratify marker TWO."
        )
        _resolved, modes = jigctl.validate_commandments_answers(changed_answers)
        answers_raw = jigctl.canonical_json(changed_answers)
        answers_path, answers_digest = jigctl.content_addressed_artifact(
            self.repo, "answers", "json", answers_raw
        )
        pointer["answersPath"] = answers_path
        pointer["answersSha256"] = answers_digest
        pointer["choiceModes"] = modes
        pointer_path.write_bytes(jigctl.canonical_json(pointer))
        manifest_before = self.manifest_path().read_bytes()
        root_before = root_path.read_bytes()
        staging_before = pointer_path.read_bytes()
        registered_before = {
            item["path"] for item in self.manifest()["artifacts"]
        }
        self.assertNotIn(answers_path, registered_before)
        self.assertNotIn(pointer["candidatePath"], registered_before)
        rejected = self.ctl(
            "stage-commandments",
            "--adopt-existing",
            input_value=changed_answers,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(rejected.stdout, "")
        self.assertIn("marker", rejected.stderr)
        self.assertEqual(self.manifest_path().read_bytes(), manifest_before)
        self.assertEqual(root_path.read_bytes(), root_before)
        self.assertEqual(pointer_path.read_bytes(), staging_before)
        registered_after = {
            item["path"] for item in self.manifest()["artifacts"]
        }
        self.assertNotIn(answers_path, registered_after)
        self.assertNotIn(pointer["candidatePath"], registered_after)

    def test_explicit_decision_retry_registers_completed_orphan(self):
        self.prepare()
        staged = self.stage()
        with mock.patch.object(
            jigctl, "write_manifest", side_effect=RuntimeError("crash")
        ):
            with self.assertRaises(RuntimeError):
                jigctl.record_commandments_decision(
                    self.repo,
                    "isolated-shell",
                    "amend",
                    staged["candidateSha256"],
                    "Amend exact candidate.",
                )
        retried = self.ctl(
            "record-commandments-decision",
            "--decision",
            "amend",
            "--candidate-sha",
            staged["candidateSha256"],
            "--operator-marker",
            "Amend exact candidate.",
        )
        self.assertEqual(retried.returncode, 0, retried.stderr)
        decisions = list(
            (self.repo / ".pi/jig/commandments/decisions").glob("*.json")
        )
        registered = {item["path"] for item in self.manifest()["artifacts"]}
        self.assertEqual(len(decisions), 1)
        self.assertIn(decisions[0].relative_to(self.repo).as_posix(), registered)

    def test_ratification_keeps_manifest_update_time_monotonic(self):
        self.prepare()
        staged = self.stage()
        deferred = self.ctl(
            "record-commandments-decision",
            "--decision",
            "defer",
            "--candidate-sha",
            staged["candidateSha256"],
            "--operator-marker",
            "Defer this exact candidate.",
        )
        self.assertEqual(deferred.returncode, 0, deferred.stderr)
        before = self.manifest()["updatedAt"]
        ratified = self.ratify(staged)
        self.assertEqual(ratified.returncode, 0, ratified.stderr)
        self.assertGreaterEqual(self.manifest()["updatedAt"], before)

    def test_unsupported_and_out_of_order_commands_fail_before_writes(self):
        self.ctl("start")
        before = self.snapshot()
        for arguments in (
            ("present-commandments",),
            ("stage-commandments",),
            ("ratify-commandments", "--candidate-sha", "0" * 64, "--operator-marker", "marker"),
            ("stage-commandments", "--candidate-path", "../outside"),
        ):
            result = self.ctl(*arguments, input_value=self.answers)
            self.assertNotEqual(result.returncode, 0, arguments)
            self.assertEqual(self.snapshot(), before, arguments)

    def test_answer_input_rejects_duplicate_keys_constants_and_invalid_utf8(self):
        self.prepare()
        valid = json.dumps(self.answers)
        cases = (
            valid.replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 1', 1),
            valid.replace('"schemaVersion": 1', '"schemaVersion": NaN', 1),
        )
        before = self.snapshot()
        for raw in cases:
            result = self.ctl("stage-commandments", input_text=raw)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("not valid UTF-8 JSON", result.stderr)
            self.assertEqual(self.snapshot(), before)
        with self.assertRaises(jigctl.ValidationError):
            jigctl.read_json_bytes(b"\xff", "answers")
        with self.assertRaises(jigctl.ValidationError):
            jigctl.read_json_bytes(b"{}" * (jigctl.MAX_INPUT_BYTES // 2 + 1), "answers")

    def test_symlink_special_file_and_content_collision_attacks_fail_closed(self):
        self.prepare()
        commandment_dir = self.repo / ".pi" / "jig" / "commandments"
        outside = Path(self.external.name)
        answers_dir = commandment_dir / "answers"
        answers_dir.symlink_to(outside, target_is_directory=True)
        before = self.manifest_path().read_bytes()
        result = self.ctl("stage-commandments", input_value=self.answers)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])
        self.assertEqual(self.manifest_path().read_bytes(), before)
        answers_dir.unlink()
        answers_dir.mkdir()
        raw = jigctl.canonical_json(self.answers)
        digest = hashlib.sha256(raw).hexdigest()
        collision = answers_dir / f"{digest}.json"
        collision.write_bytes(b"different")
        result = self.ctl("stage-commandments", input_value=self.answers)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(collision.read_bytes(), b"different")
        collision.unlink()
        os.mkfifo(collision)
        result = self.ctl("stage-commandments", input_value=self.answers)
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(collision.exists())

    def test_root_symlink_is_never_followed(self):
        self.prepare()
        staged = self.stage()
        outside = Path(self.external.name) / "outside.md"
        outside.write_text("outside\n", encoding="utf-8")
        (self.repo / "COMMANDMENTS.md").symlink_to(outside)
        result = self.ratify(staged)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(outside.read_text(), "outside\n")
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")

    def test_failed_ratified_state_recovers_to_the_valid_boundary(self):
        self.prepare()
        staged = self.stage()
        self.assertEqual(self.ratify(staged).returncode, 0)
        failed = self.ctl(
            "record-failure",
            "--state",
            "commandments-ratified",
            "--reason",
            "seeded post-ratification failure",
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-commandments-ratified")
        recovered = self.ctl("start")
        self.assertEqual(recovered.returncode, 0, recovered.stderr)
        self.assertEqual(self.manifest()["currentState"], "commandments-ratified")

    def test_inherited_session_ratification_receipt_never_claims_shell_isolation(self):
        self.prepare(isolation="inherited-session")
        staged_result = self.ctl(
            "stage-commandments",
            input_value=self.answers,
            isolation="inherited-session",
        )
        self.assertEqual(staged_result.returncode, 0, staged_result.stderr)
        staged = json.loads(staged_result.stdout)
        ratified = self.ctl(
            "ratify-commandments",
            "--candidate-sha",
            staged["candidateSha256"],
            "--operator-marker",
            staged["intendedMarker"],
            isolation="inherited-session",
        )
        self.assertEqual(ratified.returncode, 0, ratified.stderr)
        transition = self.manifest()["transitions"][-1]
        receipt = json.loads((self.repo / transition["receiptPath"]).read_text())
        self.assertEqual(receipt["resourceIsolation"], "inherited-session")
        self.assertEqual(self.manifest()["resourceIsolation"], "inherited-session")


    def test_transcript_fixture_names_exact_candidate_digest_and_ratification(self):
        self.prepare()
        staged = self.stage()
        candidate = (self.repo / staged["candidatePath"]).read_text(encoding="utf-8")
        fixture = (FIXTURES / "commandments-transcript.md").read_text(encoding="utf-8")
        rendered = fixture.replace("{{CANDIDATE_SHA256}}", staged["candidateSha256"]).replace(
            "{{CANDIDATE_BYTES}}", candidate.rstrip("\n")
        )
        self.assertNotIn("{{CANDIDATE", rendered)
        self.assertIn(staged["candidateSha256"], rendered)
        self.assertIn(staged["intendedMarker"], rendered)
        self.assertIn("Decision: ratify.", rendered)


if __name__ == "__main__":
    unittest.main()

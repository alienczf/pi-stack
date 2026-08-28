import ast
import importlib.util
import hashlib
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
from unittest import mock
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONTROLLER = ROOT / "bin" / "jigctl.py"
LAUNCHER = ROOT / "bin" / "jig.sh"
SCHEMAS = ROOT / "skills" / "jig" / "references" / "schemas" / "v1"

spec = importlib.util.spec_from_file_location("jigctl", CONTROLLER)
jigctl = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(jigctl)


class JigControllerTest(unittest.TestCase):
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

    def ctl(self, *arguments, cwd=None, input_text=None, python=sys.executable, env=None):
        environment = os.environ.copy()
        environment["JIG_PI_VERSION"] = "fixture-pi"
        if env:
            environment.update(env)
        return subprocess.run(
            [python, str(CONTROLLER), *arguments],
            cwd=cwd or self.repo,
            input=input_text,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )

    def start(self, cwd=None):
        result = self.ctl("start", "--resource-isolation", "isolated-shell", cwd=cwd)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result

    def manifest_path(self):
        return self.repo / ".pi" / "jig" / "manifest.json"

    def manifest(self):
        return json.loads(self.manifest_path().read_text(encoding="utf-8"))

    def profile(self, evidence="README.md"):
        revision = self.git("rev-parse", "HEAD").strip()
        return {
            "schemaVersion": 1,
            "repositoryRevision": revision,
            "productType": {
                "value": "test repository",
                "evidence": [{"path": evidence, "line": 1, "note": "Fixture evidence."}],
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

    def commit_profile(self, profile=None):
        value = self.profile() if profile is None else profile
        return self.ctl(
            "commit-profile",
            "--resource-isolation",
            "isolated-shell",
            input_text=json.dumps(value),
        )

    def valid_lock(self, pid=999999999, host=None, process_start=None):
        return {
            "schemaVersion": 1,
            "pid": pid,
            "host": socket.gethostname() if host is None else host,
            "processStart": process_start,
            "token": uuid.uuid4().hex,
            "acquiredAt": "2026-01-01T00:00:00Z",
        }

    def jig_snapshot(self):
        jig = self.repo / ".pi" / "jig"
        return {
            path.relative_to(jig).as_posix(): path.read_bytes()
            for path in sorted(jig.rglob("*"))
            if path.is_file() and path.name != "init.lock"
        }

    def assert_source_drift_fails_without_state_changes(self):
        before = self.jig_snapshot()
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("source revision or dirty summary changed", result.stderr)
        self.assertEqual(self.jig_snapshot(), before)

    def test_outside_git_fails_without_writes(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        result = self.ctl("start", "--resource-isolation", "isolated-shell", cwd=outside)
        self.assertNotEqual(result.returncode, 0)
        self.assertFalse((outside / ".pi").exists())

    def test_subdirectory_resolves_same_root(self):
        child = self.repo / "src" / "nested"
        child.mkdir(parents=True)
        self.start(cwd=child)
        self.assertTrue(self.manifest_path().is_file())
        self.assertFalse((child / ".pi").exists())

    def test_clean_run_and_explicit_profile_commit(self):
        self.start()
        before = self.manifest()
        self.assertEqual(before["currentState"], "surveying")
        self.assertEqual(before["commandments"], {
            "path": "COMMANDMENTS.md", "sha256": None, "version": None, "ratifiedAt": None
        })
        result = self.commit_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        after = self.manifest()
        self.assertEqual(after["currentState"], "awaiting-commandments")
        self.assertEqual([item["to"] for item in after["transitions"]], ["surveying", "awaiting-commandments"])
        self.assertFalse((self.repo / "COMMANDMENTS.md").exists())

    def test_idempotent_rerun_at_both_boundaries(self):
        self.start()
        surveying = self.manifest_path().read_bytes()
        self.start()
        self.assertEqual(self.manifest_path().read_bytes(), surveying)
        self.assertEqual(self.commit_profile().returncode, 0)
        awaiting = self.manifest_path().read_bytes()
        self.start()
        self.assertEqual(self.manifest_path().read_bytes(), awaiting)
        self.assertEqual(self.commit_profile().returncode, 0)
        self.assertEqual(self.manifest_path().read_bytes(), awaiting)

    def test_failed_state_reconciliation_returns_to_last_valid_boundary(self):
        self.start()
        failed = self.ctl(
            "record-failure",
            "--resource-isolation", "isolated-shell",
            "--state", "surveying",
            "--reason", "seeded survey failure",
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.start()
        self.assertEqual(self.manifest()["currentState"], "surveying")
        result = self.commit_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        failed = self.ctl(
            "record-failure",
            "--resource-isolation", "isolated-shell",
            "--state", "awaiting-commandments",
            "--reason", "seeded interview-boundary failure",
        )
        self.assertEqual(failed.returncode, 0, failed.stderr)
        self.start()
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")

    def test_invalid_and_file_only_profiles_do_not_advance(self):
        self.start()
        before = self.manifest_path().read_bytes()
        invalid = self.profile()
        invalid["schemaVersion"] = 2
        result = self.commit_profile(invalid)
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.manifest_path().read_bytes(), before)
        profile_path = self.repo / ".pi" / "jig" / "profile.json"
        profile_path.write_text(json.dumps(self.profile()), encoding="utf-8")
        self.start()
        self.assertEqual(self.manifest()["currentState"], "surveying")
        self.assertEqual(len(self.manifest()["transitions"]), 1)

    def test_profile_input_requires_strict_json_and_canonical_json_is_finite(self):
        self.start()
        profile = json.dumps(self.profile())
        lexical_cases = [
            profile.replace('"schemaVersion": 1', '"schemaVersion": 1, "schemaVersion": 1', 1),
            profile.replace('"line": 1', '"line": NaN', 1),
            profile.replace('"line": 1', '"line": Infinity', 1),
            profile.replace('"line": 1', '"line": -Infinity', 1),
        ]
        before = self.jig_snapshot()
        for raw in lexical_cases:
            with self.subTest(raw=raw[:80]):
                result = self.ctl(
                    "commit-profile",
                    "--resource-isolation",
                    "isolated-shell",
                    input_text=raw,
                )
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not valid UTF-8 JSON", result.stderr)
                self.assertNotIn("Traceback", result.stderr)
                self.assertLess(len(result.stderr), 600)
                self.assertEqual(self.jig_snapshot(), before)
        for value in (float("nan"), float("inf"), float("-inf")):
            with self.subTest(value=value):
                with self.assertRaises(jigctl.ValidationError):
                    jigctl.canonical_json(value)

    def test_interrupted_temporary_write_is_retained_as_evidence(self):
        self.start()
        temporary = self.repo / ".pi" / "jig" / f".jigctl-manifest.json.123.{uuid.uuid4().hex}.tmp"
        temporary.write_bytes(b"partial")
        self.start()
        self.assertFalse(temporary.exists())
        evidence = list((self.repo / ".pi" / "jig" / "receipts").glob("interrupted-write-*.bin"))
        self.assertEqual(len(evidence), 1)
        paths = {item["path"] for item in self.manifest()["artifacts"]}
        self.assertIn(evidence[0].relative_to(self.repo).as_posix(), paths)

    def test_zero_byte_and_malformed_manifest_fail_closed(self):
        self.start()
        for raw in (b"", b"{not-json"):
            self.manifest_path().write_bytes(raw)
            result = self.ctl("start", "--resource-isolation", "isolated-shell")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.manifest_path().read_bytes(), raw)
            self.assertIn("Recovery:", result.stderr)

    def test_unsupported_version_and_corrupt_state_fail_closed(self):
        self.start()
        manifest = self.manifest()
        manifest["schemaVersion"] = 2
        self.manifest_path().write_text(json.dumps(manifest), encoding="utf-8")
        raw = self.manifest_path().read_bytes()
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.manifest_path().read_bytes(), raw)
        manifest["schemaVersion"] = 1
        manifest["currentState"] = "awaiting-commandments"
        self.manifest_path().write_text(json.dumps(manifest), encoding="utf-8")
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("transition", result.stderr)

    def test_stale_lock_is_reclaimed_with_evidence(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        lock.write_text(json.dumps(self.valid_lock()), encoding="utf-8")
        result = self.start()
        self.assertEqual(result.returncode, 0)
        evidence = list((self.repo / ".pi" / "jig" / "receipts").glob("lock-reclaimed-*.json"))
        self.assertEqual(len(evidence), 1)
        self.assertFalse(lock.exists())
        self.assertIn(evidence[0].relative_to(self.repo).as_posix(), {item["path"] for item in self.manifest()["artifacts"]})

    def test_live_and_uncertain_locks_are_refused(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        live = self.valid_lock(
            pid=os.getpid(),
            process_start=jigctl.process_start(os.getpid()),
        )
        for raw in (json.dumps(live).encode(), b"uncertain"):
            lock.write_bytes(raw)
            result = self.ctl("start", "--resource-isolation", "isolated-shell")
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(lock.read_bytes(), raw)
            lock.unlink()

    def test_lexical_path_rejection(self):
        self.start()
        for path in ("/tmp/outside", "../outside", "dir//file"):
            profile = self.profile(path)
            before = self.manifest_path().read_bytes()
            result = self.commit_profile(profile)
            self.assertNotEqual(result.returncode, 0, path)
            self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_controller_output_directory_symlink_cannot_escape_root(self):
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        (self.repo / ".pi").symlink_to(outside, target_is_directory=True)
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(list(outside.iterdir()), [])

    def test_symlink_escape_and_symlinked_ancestor_rejection(self):
        self.start()
        outside = Path(tempfile.mkdtemp())
        self.addCleanup(shutil.rmtree, outside)
        (outside / "evidence.txt").write_text("secret\n", encoding="utf-8")
        (self.repo / "escape").symlink_to(outside / "evidence.txt")
        (self.repo / "linked").symlink_to(outside, target_is_directory=True)
        for path in ("escape", "linked/evidence.txt"):
            before = self.manifest_path().read_bytes()
            result = self.commit_profile(self.profile(path))
            self.assertNotEqual(result.returncode, 0)
            self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_shell_rejects_package_scope_and_extra_arguments_before_writes(self):
        forms = [[], ["run"], ["--force"], ["init", "package"], ["init", "."]]
        for arguments in forms:
            result = subprocess.run(
                ["bash", str(LAUNCHER), *arguments],
                cwd=self.repo,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
            self.assertEqual(result.returncode, 2, arguments)
            self.assertFalse((self.repo / ".pi").exists(), arguments)

    def test_source_revision_and_dirty_state_are_captured(self):
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        self.start()
        source = self.manifest()["source"]
        self.assertEqual(source["revision"], self.git("rev-parse", "HEAD").strip())
        self.assertTrue(source["dirty"])
        self.assertIn("?? dirty.txt", source["statusSummary"])

    def test_shell_argv_disables_project_resources_and_pins_skill(self):
        (self.repo / "AGENTS.md").write_text("untrusted\n", encoding="utf-8")
        (self.repo / ".pi" / "skills" / "bad").mkdir(parents=True)
        (self.repo / ".pi" / "extensions").mkdir()
        (self.repo / ".pi" / "prompts").mkdir()
        (self.repo / ".pi" / "settings.json").write_text("{}\n", encoding="utf-8")
        external = Path(self.external.name)
        receipt = external / "argv.json"
        stub = external / "pi-stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\nimport json, os, sys\n"
            "open(os.environ['ARGV_RECEIPT'], 'w').write(json.dumps(sys.argv[1:]))\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        environment = os.environ.copy()
        environment.update({"PI": str(stub), "PI_STACK_ROOT": str(ROOT), "JIG_PI_VERSION": "fixture-pi", "ARGV_RECEIPT": str(receipt)})
        result = subprocess.run(
            ["bash", str(LAUNCHER), "init"],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=environment,
        )
        self.assertNotEqual(result.returncode, 0, result.stderr)
        argv = json.loads(receipt.read_text(encoding="utf-8"))
        expected_prefix = [
            "-p", "--no-approve", "--no-session", "--no-context-files", "--no-extensions",
            "--no-prompt-templates", "--no-skills", "--skill", str(ROOT / "skills" / "jig" / "SKILL.md"),
            "--tools", "read,grep,find,ls,bash,write,edit", "--",
        ]
        self.assertEqual(argv[:-1], expected_prefix)
        self.assertIn("commit-profile", argv[-1])
        self.assertEqual(self.manifest()["resourceIsolation"], "isolated-shell")
        self.assertEqual(self.manifest()["currentState"], "failed-surveying")
        self.assertIn("before the awaiting-commandments boundary", result.stderr)
        transition = self.manifest()["transitions"][-1]
        failure_receipt = json.loads((self.repo / transition["receiptPath"]).read_text(encoding="utf-8"))
        self.assertEqual(failure_receipt["kind"], "phase-failed")

    def test_controller_runs_without_site_packages_or_jsonschema(self):
        result = self.ctl(
            "start", "--resource-isolation", "isolated-shell", python=sys.executable,
            env={"PYTHONPATH": ""},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        isolated = subprocess.run(
            [sys.executable, "-S", str(CONTROLLER), "start", "--resource-isolation", "isolated-shell"],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "JIG_PI_VERSION": "fixture-pi", "PYTHONPATH": ""},
        )
        self.assertEqual(isolated.returncode, 0, isolated.stderr)
        imports = {
            node.names[0].name.split(".")[0]
            for node in ast.walk(ast.parse(CONTROLLER.read_text(encoding="utf-8")))
            if isinstance(node, ast.Import)
        }
        imports.update(
            node.module.split(".")[0]
            for node in ast.walk(ast.parse(CONTROLLER.read_text(encoding="utf-8")))
            if isinstance(node, ast.ImportFrom) and node.module and node.module != "__future__"
        )
        self.assertTrue(imports <= sys.stdlib_module_names, imports - sys.stdlib_module_names)

    def test_controller_matches_draft_202012_examples(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("development-only jsonschema is unavailable")
        for schema_path in sorted(SCHEMAS.glob("*.schema.json")):
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.Draft202012Validator.check_schema(schema)
            validator = jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker())
            prefix = schema_path.name.removesuffix(".schema.json")
            examples = sorted((SCHEMAS / "examples").glob(f"{prefix}.*.json"))
            examples += sorted((SCHEMAS / "examples").glob(f"{prefix}.json"))
            seen = set()
            for example in examples:
                if example in seen:
                    continue
                seen.add(example)
                value = json.loads(example.read_text(encoding="utf-8"))
                conforming = validator.is_valid(value)
                try:
                    jigctl.validate_instance(value, schema)
                    controller = True
                except jigctl.ValidationError:
                    controller = False
                self.assertEqual(controller, conforming, example.name)
                self.assertEqual(controller, ".invalid." not in example.name, example.name)

    def test_scalar_equality_matches_draft_202012_validator(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("development-only jsonschema is unavailable")
        cases = [
            ({"type": "integer"}, True, False),
            ({"type": "integer"}, 1, True),
            ({"type": "integer"}, 1.0, True),
            ({"type": "integer"}, -0.0, True),
            ({"type": "integer"}, 1.5, False),
            ({"const": 1}, True, False),
            ({"const": 0}, False, False),
            ({"const": 1}, 1.0, True),
            ({"const": {"nested": [1]}}, {"nested": [1.0]}, True),
            ({"const": {"nested": [True]}}, {"nested": [1]}, False),
            ({"enum": [1]}, True, False),
            ({"enum": [0]}, False, False),
            ({"enum": [1]}, 1.0, True),
            ({"enum": [{"nested": [1]}]}, {"nested": [1.0]}, True),
            ({"enum": [{"nested": [False]}]}, {"nested": [0]}, False),
            ({"type": "array", "uniqueItems": True}, [True, 1], True),
            ({"type": "array", "uniqueItems": True}, [False, 0], True),
            ({"type": "array", "uniqueItems": True}, [1, 1.0], False),
            (
                {"type": "array", "uniqueItems": True},
                [{"nested": [True]}, {"nested": [1]}],
                True,
            ),
            (
                {"type": "array", "uniqueItems": True},
                [{"nested": [1]}, {"nested": [1.0]}],
                False,
            ),
        ]
        for schema, instance, expected in cases:
            with self.subTest(schema=schema, instance=instance):
                conforming = jsonschema.Draft202012Validator(schema).is_valid(instance)
                try:
                    jigctl.validate_instance(instance, schema)
                    controller = True
                except jigctl.ValidationError:
                    controller = False
                self.assertEqual(conforming, expected)
                self.assertEqual(controller, conforming)

    def test_datetime_format_matches_draft_202012_checker(self):
        try:
            import jsonschema
        except ImportError:
            self.skipTest("development-only jsonschema is unavailable")
        values = [
            "2026-01-01T00:00:00Z",
            "2026-01-01t00:00:00z",
            "1937-01-01T12:00:27.87+00:20",
            "2026-01-01T00:00:00.123z",
            "2026-01-01T00:00:00.1Z",
            "2026-01-01T00:00:00.123456789123Z",
            "2026-01-01t00:00:00+23:59",
            "2026-01-01 00:00:00Z",
            "2026-01-01T24:00:00Z",
            "2026-02-29T00:00:00Z",
            "1990-12-31T23:59:60Z",
            "2026-01-01T00:00:00+24:00",
            "2026-01-01T00:00:00,Z",
            "٢٠٢٦-٠١-٠١T٠٠:٠٠:٠٠Z",
            "２０２６-０１-０１T００:００:００Z",
        ]
        checker = jsonschema.FormatChecker()
        for value in values:
            try:
                checker.check(value, "date-time")
                conforming = True
            except jsonschema.exceptions.FormatError:
                conforming = False
            self.assertEqual(jigctl.valid_datetime(value), conforming, value)

    def test_dirty_summary_drift_fails_at_surveying(self):
        self.start()
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        self.assert_source_drift_fails_without_state_changes()

    def test_dirty_summary_drift_fails_at_awaiting_commandments(self):
        self.start()
        self.assertEqual(self.commit_profile().returncode, 0)
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        self.assert_source_drift_fails_without_state_changes()

    def test_head_drift_fails_at_surveying(self):
        self.start()
        (self.repo / "README.md").write_text("new head\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "new head")
        self.assert_source_drift_fails_without_state_changes()

    def test_head_drift_fails_at_awaiting_commandments(self):
        self.start()
        self.assertEqual(self.commit_profile().returncode, 0)
        (self.repo / "README.md").write_text("new head\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "new head")
        self.assert_source_drift_fails_without_state_changes()

    def test_mutating_commands_reject_source_drift_before_writes(self):
        self.start()
        (self.repo / "dirty.txt").write_text("dirty\n", encoding="utf-8")
        before = self.jig_snapshot()
        failure = self.ctl(
            "record-failure",
            "--resource-isolation", "isolated-shell",
            "--state", "surveying",
            "--reason", "must not be recorded",
        )
        profile = self.commit_profile()
        self.assertNotEqual(failure.returncode, 0)
        self.assertNotEqual(profile.returncode, 0)
        self.assertEqual(self.jig_snapshot(), before)

    def test_lock_records_are_validated_before_liveness(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        malformed = [
            {"pid": 999999999, "host": socket.gethostname()},
            {**self.valid_lock(), "unexpected": True},
            {**self.valid_lock(), "schemaVersion": 2},
            {**self.valid_lock(), "processStart": "not-numeric"},
            {**self.valid_lock(), "token": "short"},
            {**self.valid_lock(), "acquiredAt": "not-a-date"},
            self.valid_lock(host="foreign.invalid"),
        ]
        for value in malformed:
            with self.subTest(value=value):
                raw = json.dumps(value).encode("utf-8")
                lock.write_bytes(raw)
                result = self.ctl("start", "--resource-isolation", "isolated-shell")
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(lock.read_bytes(), raw)
                lock.unlink()

    def test_lock_scalar_shapes_and_oversized_pid_fail_bounded(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        invalid = [
            {**self.valid_lock(), "schemaVersion": True},
            {**self.valid_lock(), "schemaVersion": 1.0},
            {**self.valid_lock(), "pid": 1.0},
            {**self.valid_lock(), "pid": 10**100},
        ]
        for value in invalid:
            with self.subTest(value=value):
                raw = json.dumps(value).encode("utf-8")
                lock.write_bytes(raw)
                result = self.ctl("start", "--resource-isolation", "isolated-shell")
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertLess(len(result.stderr), 600)
                self.assertEqual(lock.read_bytes(), raw)
                lock.unlink()

    def test_stale_lock_hard_link_failure_is_bounded_and_preserves_bytes(self):
        self.start()
        lock_path = self.repo / ".pi" / "jig" / "init.lock"
        raw = json.dumps(self.valid_lock(), sort_keys=True).encode("utf-8")
        lock_path.write_bytes(raw)
        before = self.jig_snapshot()
        lock = jigctl.RepositoryLock(self.repo)
        with mock.patch.object(jigctl.os, "link", side_effect=OSError("hard links unsupported")):
            with self.assertRaises(jigctl.JigError) as caught:
                lock.acquire()
        message = str(caught.exception)
        self.assertNotIn("Traceback", message)
        self.assertLess(len(message), 600)
        self.assertEqual(lock_path.read_bytes(), raw)
        self.assertEqual(self.jig_snapshot(), before)

    def test_stale_lock_collision_with_different_evidence_fails_closed(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        raw = json.dumps(self.valid_lock(), sort_keys=True).encode("utf-8")
        lock.write_bytes(raw)
        evidence = self.repo / ".pi" / "jig" / "receipts" / f"lock-reclaimed-{hashlib.sha256(raw).hexdigest()[:16]}.json"
        existing = b"existing evidence\n"
        evidence.write_bytes(existing)
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(lock.read_bytes(), raw)
        self.assertEqual(evidence.read_bytes(), existing)

    def test_stale_lock_collision_with_same_evidence_reconciles(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        raw = json.dumps(self.valid_lock(), sort_keys=True).encode("utf-8")
        lock.write_bytes(raw)
        evidence = self.repo / ".pi" / "jig" / "receipts" / f"lock-reclaimed-{hashlib.sha256(raw).hexdigest()[:16]}.json"
        evidence.write_bytes(raw)
        before = evidence.read_bytes()
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertFalse(lock.exists())
        self.assertEqual(evidence.read_bytes(), before)
        self.assertIn(evidence.relative_to(self.repo).as_posix(), {item["path"] for item in self.manifest()["artifacts"]})

    def test_concurrent_stale_lock_reclamation_preserves_evidence(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        raw = json.dumps(self.valid_lock(), sort_keys=True).encode("utf-8")
        lock.write_bytes(raw)
        command = [sys.executable, str(CONTROLLER), "start", "--resource-isolation", "isolated-shell"]
        environment = {**os.environ, "JIG_PI_VERSION": "fixture-pi"}
        processes = [
            subprocess.Popen(command, cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
            for _ in range(2)
        ]
        results = [process.communicate(timeout=10) + (process.returncode,) for process in processes]
        self.assertTrue(any(returncode == 0 for _stdout, _stderr, returncode in results), results)
        evidence = list((self.repo / ".pi" / "jig" / "receipts").glob("lock-reclaimed-*.json"))
        self.assertEqual(len(evidence), 1)
        self.assertEqual(evidence[0].read_bytes(), raw)
        self.assertFalse(lock.exists())
        jigctl.validate_manifest_semantics(self.repo, self.manifest(), jigctl.load_schema("manifest"))

    def test_transition_receipt_source_contradiction_fails_closed(self):
        self.start()
        manifest = self.manifest()
        transition = manifest["transitions"][0]
        receipt_path = self.repo / transition["receiptPath"]
        receipt = json.loads(receipt_path.read_text(encoding="utf-8"))
        receipt["sourceDirty"] = not manifest["source"]["dirty"]
        raw = jigctl.canonical_json(receipt)
        receipt_path.write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        transition["receiptSha256"] = digest
        for artifact in manifest["artifacts"]:
            if artifact["path"] == transition["receiptPath"]:
                artifact["sha256"] = digest
        self.manifest_path().write_bytes(jigctl.canonical_json(manifest))
        before = self.jig_snapshot()
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("receipt", result.stderr)
        self.assertEqual(self.jig_snapshot(), before)

    def test_manifest_semantics_are_validated_before_write(self):
        self.start()
        before = self.manifest_path().read_bytes()
        manifest = self.manifest()
        manifest["artifacts"][0]["owner"] = "repository"
        with self.assertRaises(jigctl.ValidationError):
            jigctl.write_manifest(self.repo, manifest)
        self.assertEqual(self.manifest_path().read_bytes(), before)

    def test_control_characters_are_bounded_path_failures(self):
        self.start()
        for path in ("README.md\0suffix", "README.md\nsuffix", "README.md\x7fsuffix"):
            with self.subTest(path=repr(path)):
                before = self.jig_snapshot()
                result = self.commit_profile(self.profile(path))
                self.assertNotEqual(result.returncode, 0)
                self.assertNotIn("Traceback", result.stderr)
                self.assertLess(len(result.stderr), 600)
                self.assertEqual(self.jig_snapshot(), before)

    def test_profile_evidence_must_be_a_regular_file(self):
        directory = self.repo / "evidence-dir"
        fifo = self.repo / "evidence-fifo"
        unix_socket_path = self.repo / "evidence.sock"
        directory.mkdir()
        os.mkfifo(fifo)
        unix_socket = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.addCleanup(unix_socket.close)
        unix_socket.bind(str(unix_socket_path))
        self.start()
        for path in (directory, fifo, unix_socket_path):
            with self.subTest(path=path.name):
                before = self.jig_snapshot()
                result = self.commit_profile(self.profile(path.name))
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("not a regular file", result.stderr)
                self.assertEqual(self.jig_snapshot(), before)

    def test_unknown_lookalike_temporary_file_is_preserved(self):
        self.start()
        unknown_directory = self.repo / ".pi" / "jig" / "unknown"
        unknown_directory.mkdir()
        identifier = uuid.uuid4().hex
        unknown = unknown_directory / f".jigctl-manifest.json.123.{identifier}.tmp"
        unknown.write_bytes(b"unknown\n")
        genuine = self.repo / ".pi" / "jig" / f".jigctl-manifest.json.123.{uuid.uuid4().hex}.tmp"
        genuine.write_bytes(b"genuine\n")
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(unknown.read_bytes(), b"unknown\n")
        self.assertFalse(genuine.exists())
        artifact_paths = {item["path"] for item in self.manifest()["artifacts"]}
        self.assertNotIn(unknown.relative_to(self.repo).as_posix(), artifact_paths)
        self.assertTrue(any(path.startswith(".pi/jig/receipts/interrupted-write-") for path in artifact_paths))

    def test_receipt_lookalikes_remain_unclaimed_across_reruns(self):
        receipts = self.repo / ".pi" / "jig" / "receipts"
        receipts.mkdir(parents=True)
        names = [
            "lock-reclaimed-not-a-digest.json",
            "lock-reclaimed-0000000000000000.json",
            "interrupted-write-not-a-digest.bin",
            f"interrupted-write-{'0' * 64}.bin",
            "interrupted-transition-not-a-digest.json",
            f"interrupted-transition-{'0' * 64}.json",
        ]
        seeded = {}
        for index, name in enumerate(names):
            path = receipts / name
            raw = f"unknown receipt {index}\n".encode("utf-8")
            path.write_bytes(raw)
            seeded[path] = raw
        self.start()
        first = self.manifest_path().read_bytes()
        artifact_paths = {item["path"] for item in self.manifest()["artifacts"]}
        for path, raw in seeded.items():
            self.assertEqual(path.read_bytes(), raw)
            self.assertNotIn(path.relative_to(self.repo).as_posix(), artifact_paths)
        self.start()
        self.assertEqual(self.manifest_path().read_bytes(), first)
        artifact_paths = {item["path"] for item in self.manifest()["artifacts"]}
        for path, raw in seeded.items():
            self.assertEqual(path.read_bytes(), raw)
            self.assertNotIn(path.relative_to(self.repo).as_posix(), artifact_paths)

    def test_shell_valid_profile_stub_reaches_awaiting_commandments(self):
        external = Path(self.external.name)
        stub = external / "pi-profile-stub.py"
        stub.write_text(
            "#!/usr/bin/env python3\n"
            "import json, os, subprocess, sys\n"
            "revision = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()\n"
            "profile = {'schemaVersion': 1, 'repositoryRevision': revision, 'productType': {'value': 'fixture', 'evidence': [{'path': 'README.md', 'line': 1, 'note': 'Fixture.'}]}, 'languages': [], 'frameworks': [], 'buildTools': [], 'ci': [], 'entryPoints': [], 'topology': [], 'unknowns': [], 'failureModes': []}\n"
            "controller = os.path.join(os.environ['PI_STACK_ROOT'], 'bin', 'jigctl.py')\n"
            "result = subprocess.run([sys.executable, controller, 'commit-profile', '--resource-isolation', 'isolated-shell'], input=json.dumps(profile), text=True)\n"
            "raise SystemExit(result.returncode)\n",
            encoding="utf-8",
        )
        stub.chmod(0o755)
        result = subprocess.run(
            ["bash", str(LAUNCHER), "init"],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PI": str(stub), "PI_STACK_ROOT": str(ROOT), "JIG_PI_VERSION": "fixture-pi"},
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")

    def test_shell_nonzero_stub_records_failure(self):
        stub = Path(self.external.name) / "pi-failing-stub.sh"
        stub.write_text("#!/usr/bin/env bash\nexit 7\n", encoding="utf-8")
        stub.chmod(0o755)
        result = subprocess.run(
            ["bash", str(LAUNCHER), "init"],
            cwd=self.repo,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env={**os.environ, "PI": str(stub), "PI_STACK_ROOT": str(ROOT), "JIG_PI_VERSION": "fixture-pi"},
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("status 7", result.stderr)
        self.assertEqual(self.manifest()["currentState"], "failed-surveying")

    def test_failure_guidance_is_bounded_and_unknown_state_is_preserved(self):
        self.start()
        self.manifest_path().write_text("{}\n", encoding="utf-8")
        before = self.manifest_path().read_bytes()
        result = self.ctl("start", "--resource-isolation", "isolated-shell")
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(self.manifest_path().read_bytes(), before)
        self.assertLess(len(result.stderr), 600)
        self.assertIn("preserve .pi/jig", result.stderr)
        self.assertNotIn("delete", result.stderr.lower())

    def test_concurrent_attempts_leave_one_transition_and_valid_manifest(self):
        command = [sys.executable, str(CONTROLLER), "start", "--resource-isolation", "isolated-shell"]
        environment = {**os.environ, "JIG_PI_VERSION": "fixture-pi"}
        processes = [
            subprocess.Popen(command, cwd=self.repo, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=environment)
            for _ in range(2)
        ]
        results = [process.communicate(timeout=10) + (process.returncode,) for process in processes]
        self.assertTrue(any(returncode == 0 for _stdout, _stderr, returncode in results), results)
        manifest = self.manifest()
        jigctl.validate_instance(manifest, jigctl.load_schema("manifest"))
        self.assertEqual(len(manifest["transitions"]), 1)
        self.assertEqual(manifest["currentState"], "surveying")
        self.assertFalse((self.repo / ".pi" / "jig" / "init.lock").exists())


if __name__ == "__main__":
    unittest.main()

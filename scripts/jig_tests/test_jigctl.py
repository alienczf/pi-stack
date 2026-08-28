import ast
import importlib.util
import json
import os
import shutil
import socket
import subprocess
import sys
import tempfile
import unittest
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
        self.repo = Path(self.temporary.name)
        self.git("init", "-q")
        self.git("config", "user.email", "jig@example.invalid")
        self.git("config", "user.name", "Jig Fixture")
        (self.repo / "README.md").write_text("fixture\n", encoding="utf-8")
        self.git("add", "README.md")
        self.git("commit", "-qm", "fixture")

    def tearDown(self):
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
        manifest = self.manifest()
        jigctl.append_transition(
            self.repo, manifest, "surveying", "failed-surveying", "seeded-failure"
        )
        jigctl.write_manifest(self.repo, manifest)
        self.start()
        self.assertEqual(self.manifest()["currentState"], "surveying")
        result = self.commit_profile()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.manifest()["currentState"], "awaiting-commandments")
        manifest = self.manifest()
        jigctl.append_transition(
            self.repo, manifest, "awaiting-commandments", "failed-awaiting-commandments", "seeded-failure"
        )
        jigctl.write_manifest(self.repo, manifest)
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
        lock.write_text(json.dumps({
            "schemaVersion": 1,
            "pid": 999999999,
            "host": socket.gethostname(),
            "processStart": None,
            "token": "stale",
            "acquiredAt": "2026-01-01T00:00:00Z",
        }), encoding="utf-8")
        result = self.start()
        self.assertEqual(result.returncode, 0)
        evidence = list((self.repo / ".pi" / "jig" / "receipts").glob("lock-reclaimed-*.json"))
        self.assertEqual(len(evidence), 1)
        self.assertFalse(lock.exists())
        self.assertIn(evidence[0].relative_to(self.repo).as_posix(), {item["path"] for item in self.manifest()["artifacts"]})

    def test_live_and_uncertain_locks_are_refused(self):
        self.start()
        lock = self.repo / ".pi" / "jig" / "init.lock"
        live = {
            "schemaVersion": 1,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "processStart": jigctl.process_start(os.getpid()),
            "token": "live",
            "acquiredAt": "2026-01-01T00:00:00Z",
        }
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
        receipt = self.repo / "argv.json"
        stub = self.repo / "pi-stub.py"
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
        self.assertEqual(result.returncode, 0, result.stderr)
        argv = json.loads(receipt.read_text(encoding="utf-8"))
        expected_prefix = [
            "-p", "--no-approve", "--no-session", "--no-context-files", "--no-extensions",
            "--no-prompt-templates", "--no-skills", "--skill", str(ROOT / "skills" / "jig" / "SKILL.md"),
            "--tools", "read,grep,find,ls,bash,write,edit", "--",
        ]
        self.assertEqual(argv[:-1], expected_prefix)
        self.assertIn("commit-profile", argv[-1])
        self.assertEqual(self.manifest()["resourceIsolation"], "isolated-shell")

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

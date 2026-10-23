"""New shared verifier negatives. Offline fixtures do not establish native PASS."""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import poc, project, state, prime
from engine.install_prime import prepare_project, write_wrappers, tree_hash, digest, PRIME_REVISION


class EvidenceTests(unittest.TestCase):
    def sample(self):
        return {"prime_source_revision": PRIME_REVISION, "model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "threshold_percent": .1, "observed_percentages": [.2],
                "stream": "one", "session_id": "durable", "active_session_id": "routing", "protocol": 7, "schema": 30,
                "stages": {name: {"verified": True, "evidence": ["offline fixture reference"]} for name in poc.STAGES},
                "trace": [{"operation": "write", "command": "prompt_and_wait", "command_id": "command", "fields": {"message": 'Current files for stream "one", Prime session "durable", command "command".', "activeSessionId": "routing", "streamingBehavior": "steer"}},
                          {"operation": "write", "command": "compact", "fields": {"activeSessionId": "routing"}}]}

    def test_each_missing_or_unverified_stage_is_rejected(self):
        full = self.sample()
        self.assertEqual(poc.assess(full), [])
        self.assertNotIn("status", full)
        for name in poc.STAGES:
            for replacement in (None, {"verified": False, "evidence": ["claim"]}, {"verified": True, "evidence": []}):
                report = copy.deepcopy(full)
                report["stages"][name] = replacement
                self.assertIn(name, poc.assess(report))

    def test_equal_unknown_percentage_wrong_identity_and_duplicate_compact_cannot_pass(self):
        full = self.sample()
        for percents in ([.1], [], [None], [float("nan")]):
            self.assertIn("actual_percentage_crossing", poc.assess({**full, "observed_percentages": percents}))
        self.assertIn("stock_model_identity", poc.assess({**full, "thinking": "off"}))
        self.assertIn("same_durable_session", poc.assess({**full, "session_id": "foreign"}))
        duplicate = copy.deepcopy(full)
        duplicate["trace"].append(duplicate["trace"][-1])
        self.assertIn("one_direct_compact", poc.assess(duplicate))


class SharedPocTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory(prefix="shared-poc-test-")
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name) / "prefix"
        self.root.mkdir()
        self.poteto = self.root / "src/plugins/pstack/skills/poteto-mode/SKILL.md"
        self.poteto.parent.mkdir(parents=True)
        self.poteto.write_text("offline fixture process entry\n")
        runtime = self.root / "libexec/prime-agent-runtime"
        for name in ("pyproject.toml", "src/rlm/__init__.py", "src/rlm/repl.py"):
            path = runtime / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("offline fixture runtime\n")
        binary = self.root / "libexec/prime-agent"
        binary.write_text("#!/bin/sh\nprintf '0.10.1\\n'\n")
        binary.chmod(0o755)
        write_wrappers(self.root, project.repo_root())
        prepare_project(self.root, self.root / "project", "openai-codex/gpt-6.1-sol", "xhigh", .1, self.poteto)
        self.installation = {"root": str(self.root), "project": str(self.root / "project"), "pi_stack_revision": project.git(project.repo_root(), "rev-parse", "HEAD").strip(),
            "prime_source_revision": PRIME_REVISION, "prime_version": "0.10.1", "prime_binary_sha256": digest(binary), "prime_runtime_sha256": tree_hash(runtime), "pstack_revision": "c" * 40,
            "model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "threshold_percent": .1, "paths": {"poteto": str(self.poteto), "checkout": str(project.repo_root())}}
        (self.root / "reports").mkdir()
        (self.root / "reports/install.json").write_text(json.dumps(self.installation))

    def doctor_git(self, repo, *args):
        if repo == self.root / "src/prime-agent":
            return PRIME_REVISION + "\n"
        if repo == self.root / "src/plugins":
            return "c" * 40 + "\n"
        return self.actual_git(repo, *args)

    def test_init_is_shared_idempotent_and_sets_controllers_before_any_native_session(self):
        result = poc.init(self.root, "one")
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["checks"]["native_session_created"], False)
        stream = self.root / "project/streams/one"
        self.assertEqual(prime.validate_stream_settings(stream)["compaction"], {"enabled": False, "agentCallable": False, "thresholdPercent": .1})
        self.assertEqual(poc.init(self.root, "one")["status"], "PASS")
        self.assertEqual((stream / "AGENTS.md").read_bytes(), (project.templates_dir() / "prime/AGENTS.md").read_bytes())
        self.assertEqual(poc._rotation(self.root, "one")["verified"], True)

    def test_doctor_uses_actual_owned_hashes_and_rejects_changed_sidecar(self):
        poc.init(self.root, "one")
        self.actual_git = project.git
        with patch.object(project, "git", side_effect=self.doctor_git):
            good = poc.doctor(self.root, "one")
            self.assertEqual(good["status"], "PASS")
            (self.root / "libexec/prime-agent-runtime/src/rlm/repl.py").write_text("wrong revision")
            bad = poc.doctor(self.root, "one")
        self.assertEqual(bad["status"], "FAIL")
        self.assertEqual(bad["checks"]["runtime_sidecar"], False)

    def test_verify_refuses_existing_socket_without_contact_or_daemon_start(self):
        poc.init(self.root, "one")
        path = self.root / "prime/poc-one.sock"
        path.parent.mkdir(exist_ok=True)
        path.write_text("foreign socket stand-in")
        self.actual_git = project.git
        with patch.object(project, "git", side_effect=self.doctor_git), patch.object(prime, "start_owned_daemon", side_effect=AssertionError("must never start")):
            result = poc.verify(self.root, "one")
        self.assertEqual(result["status"], "FAIL")
        self.assertIn("existing test socket", result["reason"])
        self.assertEqual(path.read_text(), "foreign socket stand-in")
        self.assertEqual(poc.verify(self.root, "one")["status"], "BLOCKED")

    def test_shutdown_does_not_contact_a_replacement_socket(self):
        import io
        class Process:
            returncode = None
            def poll(self): return self.returncode
            def terminate(self): self.returncode = -15
            def wait(self): return self.returncode
        path = self.root / "replacement.sock"
        path.write_text("replacement must not be contacted")
        process = Process()
        handle = io.BytesIO()
        owned = prime.OwnedDaemon(process, path, handle, (0, 0))
        with patch.object(prime, "PrimeClient", side_effect=AssertionError("foreign socket contact")):
            prime.stop_owned_daemon(owned)
        self.assertEqual(process.poll(), -15)
        self.assertEqual(path.read_text(), "replacement must not be contacted")
        self.assertEqual(handle.closed, True)

    def test_init_refuses_existing_work(self):
        poc.init(self.root, "one")
        stream = self.root / "project/streams/one"
        state.save_message(stream, text="Existing whole request", command_id="00000000-0000-0000-0000-000000000001", session_id="fixture", sender="operator", send_as="steer")
        with self.assertRaisesRegex(Exception, "existing working stream"):
            poc.init(self.root, "one")
        self.assertEqual(len(state.check_state(stream).goals.work), 1)

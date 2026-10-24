"""New shared verifier negatives. Offline fixtures do not establish native PASS."""
import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import poc, project, state, prime
from engine.install_prime import prepare_project, write_wrappers, tree_hash, digest, PRIME_REVISION
from stub_prime import StubPrime
from prime_poc_fixture import PocScenario


class EvidenceTests(unittest.TestCase):
    def sample(self):
        return {"prime_source_revision": PRIME_REVISION, "model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "threshold_percent": .1, "observed_percentages": [.2],
                "expected_identity": {"model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "worker_model": "openai-codex/gpt-6-luna", "worker_thinking": "xhigh"},
                "worker_model": "openai-codex/gpt-6-luna", "worker_thinking": "xhigh",
                "native_identities": {"coordinator": {"model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "entries": [{"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6.1-sol"}, {"type": "thinking_level_change", "thinkingLevel": "xhigh"}], "sha256": "a" * 64, "session_id": "durable"},
                                      "worker": {"model": "openai-codex/gpt-6-luna", "thinking": "xhigh", "entries": [{"type": "model_change", "provider": "openai-codex", "modelId": "gpt-6-luna"}, {"type": "thinking_level_change", "thinkingLevel": "xhigh"}], "sha256": "b" * 64, "session_id": "worker"}},
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

    def test_explicit_alternative_identity_is_not_a_default_model_violation(self):
        report = self.sample()
        report.update(model="explicit-provider/explicit-model", thinking="high", worker_model="explicit-provider/worker", worker_thinking="low",
                      expected_identity={"model": "explicit-provider/explicit-model", "thinking": "high", "worker_model": "explicit-provider/worker", "worker_thinking": "low"})
        report["native_identities"]["coordinator"].update(model="explicit-provider/explicit-model", thinking="high")
        report["native_identities"]["worker"].update(model="explicit-provider/worker", thinking="low")
        for role, model_id, level in (("coordinator", "explicit-model", "high"), ("worker", "worker", "low")):
            report["native_identities"][role]["entries"] = [{"type": "model_change", "provider": "explicit-provider", "modelId": model_id}, {"type": "thinking_level_change", "thinkingLevel": level}]
        self.assertEqual(poc.assess(report), [])

    def test_native_worker_coordinator_alias_and_missing_thinking_are_rejected(self):
        report = self.sample()
        report["native_identities"]["worker"]["entries"][0]["modelId"] = "gpt-6.1-sol"
        self.assertIn("worker_native_identity", poc.assess(report))
        report = self.sample()
        report["native_identities"]["coordinator"]["entries"].pop()
        self.assertIn("coordinator_native_identity", poc.assess(report))
        report = self.sample()
        report["worker_model"] = report["model"]
        self.assertIn("worker_model_identity", poc.assess(report))

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
            "model": "openai-codex/gpt-6.1-sol", "thinking": "xhigh", "worker_model": "openai-codex/gpt-6-luna", "worker_thinking": "xhigh", "threshold_percent": .1, "paths": {"poteto": str(self.poteto), "checkout": str(project.repo_root())}}
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

    def assembled(self, mode="success"):
        poc.init(self.root, "one")
        scenario = PocScenario(self.root, mode)
        socket = self.root / "prime/poc-one.sock"
        self.actual_git = project.git
        class FixtureClient(poc.RecordingClient):
            def __init__(self, path, stream):
                super().__init__(path, stream)
                self.timeout = 2
        stub = None
        def start(binary, path, log, **kwargs):
            nonlocal stub
            self.assertEqual(path, socket)
            stub = StubPrime(scenario.handle, path=socket)
            stub.__enter__()
            return prime.OwnedDaemon(scenario.process, path, io.BytesIO())
        def stop(owned):
            self.assertIs(owned.process, scenario.process)
            scenario.process.returncode = 0
            owned.process.wait()
            owned.log_handle.close()
            scenario.stopped = True
        with patch.object(project, "git", side_effect=self.doctor_git), patch.object(prime, "start_owned_daemon", side_effect=start), patch.object(prime, "stop_owned_daemon", side_effect=stop), patch.object(poc, "RecordingClient", FixtureClient):
            try:
                report = poc.verify(self.root, "one")
            finally:
                if stub is not None:
                    stub.__exit__(None, None, None)
        self.assertIsNotNone(stub, report.get("reason"))
        self.assertEqual(report["owned_daemon_stopped"], True)
        self.assertEqual(scenario.stopped, True)
        return report, scenario, stub.requests

    def test_offline_assembled_verifier_completes_actual_socket_and_artifact_sequence(self):
        report, scenario, requests = self.assembled()
        self.assertEqual(report["status"], "PASS", report.get("reason"))
        self.assertEqual(poc.assess(report, self.installation), [])
        self.assertEqual(state.check_state(scenario.stream).goals.work, ())
        self.assertEqual(report["check"]["argv"], ["python3", "check_fixture.py"])
        self.assertEqual(report["check"]["exit"], 0)
        self.assertIn("marker, answer and protected behavior verified", report["check"]["stdout"])
        self.assertEqual(json.loads((scenario.product / "answer.json").read_text())["answer"], 5)
        self.assertFalse((scenario.product / "STATE.md").exists())
        self.assertLess(scenario.events.index("checked-save"), scenario.events.index("compact"))
        self.assertLess(scenario.events.index("resume-parked"), scenario.events.index("release"))
        self.assertLess(scenario.events.index("release"), scenario.events.index("resume-result"))
        self.assertEqual([r["command"]["type"] for r in requests].count("compact"), 1)
        self.assertIn("busy-steer", scenario.events)
        self.assertIn("self-review", scenario.events)
        creates = [r["command"]["config"] for r in requests if r["command"]["type"] == "create"]
        self.assertEqual([(c["provider"], c["model"], c["thinking"]) for c in creates], [("openai-codex", "gpt-6.1-sol", "xhigh"), ("openai-codex", "gpt-6-luna", "xhigh")])
        self.assertEqual(report["native_identities"]["worker"]["model"], "openai-codex/gpt-6-luna")

    def failed_assembled(self, mode, reason):
        report, scenario, requests = self.assembled(mode)
        self.assertNotEqual(report["status"], "PASS")
        self.assertIn(reason, report["reason"])
        self.assertEqual(len(state.check_state(scenario.stream).goals.work), 2)
        self.assertNotIn("computed_close", report["stages"])
        return report, scenario, requests

    def test_native_shaped_verifier_wait_is_resolved_only_after_saved_worker_result(self):
        report, scenario, requests = self.assembled("waiting_for_verifier")
        self.assertEqual(report["status"], "PASS", report.get("reason"))
        self.assertIn("resume-result", scenario.events)
        self.assertEqual(state.check_state(scenario.stream).goals.work, ())

    def test_assembled_waits_for_delayed_steer_before_worker_snapshot(self):
        report, scenario, requests = self.assembled("delayed_steer_state")
        self.assertEqual(report["status"], "PASS", report.get("reason"))
        self.assertLess(scenario.events.index("delayed-steer-finished"), scenario.events.index("worker"))
        self.assertEqual(state.check_state(scenario.stream).goals.work, ())

    def test_assembled_native_intake_failure_stops_before_steer_or_worker(self):
        report, scenario, requests = self.assembled("intake_failure")
        self.assertEqual(report["status"], "BLOCKED")
        self.assertIn("native intake refused", report["reason"])
        self.assertEqual(len(state.check_state(scenario.stream).goals.work), 1)
        self.assertNotIn("busy-steer", scenario.events)
        self.assertNotIn("worker", scenario.events)

    def test_assembled_native_steer_failure_stops_before_worker_dispatch(self):
        report, scenario, requests = self.failed_assembled("steer_failure", "native steer refused")
        self.assertNotIn("worker", scenario.events)
        self.assertEqual([r["command"]["type"] for r in requests].count("create"), 1)

    def test_assembled_worker_failure_cannot_start_compaction(self):
        report, scenario, requests = self.failed_assembled("worker_failure", "worker check failed")
        self.assertNotIn("compact", scenario.events)
        self.assertNotIn("computed_close", report["stages"])

    def test_assembled_save_after_compact_is_refused_before_any_compact(self):
        report, scenario, requests = self.failed_assembled("save_after_compact", "checked update")
        self.assertNotIn("compact", [r["command"]["type"] for r in requests])

    def test_assembled_compact_error_has_no_resume(self):
        report, scenario, requests = self.failed_assembled("compact_failure", "compact refused")
        self.assertNotIn("resume-parked", scenario.events)
        self.assertIn("release", scenario.events)

    def test_assembled_in_memory_only_compaction_has_no_resume(self):
        report, scenario, requests = self.failed_assembled("missing_disk", "persisted")
        self.assertNotIn("resume-parked", scenario.events)
        self.assertIn("release", scenario.events)

    def test_assembled_wrong_native_summary_has_no_resume(self):
        report, scenario, requests = self.failed_assembled("wrong_summary", "matching")
        self.assertNotIn("resume-parked", scenario.events)

    def test_assembled_release_failure_cannot_be_a_successful_continuation(self):
        self.failed_assembled("release_failure", "release refused")

    def test_assembled_missing_resume_result_is_unknown_not_success(self):
        self.failed_assembled("missing_resume_result", "timed out")

    def test_assembled_missing_stream_review_cannot_close(self):
        self.failed_assembled("missing_review", "adversarial self-review")

    def test_assembled_changed_untracked_output_after_green_check_cannot_close(self):
        report, scenario, requests = self.failed_assembled("changed_output_after_check", "artifact bytes")
        self.assertEqual(json.loads((scenario.product / "answer.json").read_text())["answer"], 6)
        self.assertTrue((scenario.product / "report.txt").exists())

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

    def test_doctor_refuses_coordinator_identity_in_worker_config(self):
        poc.init(self.root, "one")
        path = self.root / "index/projects/project.toml"
        path.write_text(path.read_text().replace('model = "openai-codex/gpt-6-luna"', 'model = "openai-codex/gpt-6.1-sol"'))
        self.actual_git = project.git
        with patch.object(project, "git", side_effect=self.doctor_git):
            result = poc.doctor(self.root, "one")
        self.assertEqual(result["status"], "FAIL")
        self.assertEqual(result["checks"]["worker_model_thinking"], False)

    def test_init_refuses_existing_work(self):
        poc.init(self.root, "one")
        stream = self.root / "project/streams/one"
        state.save_message(stream, text="Existing whole request", command_id="00000000-0000-0000-0000-000000000001", session_id="fixture", sender="operator", send_as="steer")
        with self.assertRaisesRegex(Exception, "existing working stream"):
            poc.init(self.root, "one")
        self.assertEqual(len(state.check_state(stream).goals.work), 1)

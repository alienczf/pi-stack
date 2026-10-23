"""New shared transport functionality and preserved CLI contracts."""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine import StreamsError, project, state
from engine.prime import PrimeClient, CliError, resolve_session, create_stream_session, save_reply
from stub_prime import StubPrime


class TransportTests(unittest.TestCase):
    def test_long_owned_socket_path_uses_the_same_filesystem_socket(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp) / ("a" * 70) / ("b" * 70)
            directory.mkdir(parents=True)
            with StubPrime(lambda s, r: s.response(r, {"owned": "same inode"})) as stub:
                path = directory / "owned.sock"
                os.link(stub.path, path)
                try:
                    with PrimeClient(str(path)) as client:
                        self.assertEqual(client.query("get_state"), {"owned": "same inode"})
                finally:
                    if not stub.requests:
                        with PrimeClient(stub.path) as cleanup:
                            cleanup.query("get_state")
                self.assertEqual(path.stat().st_ino, Path(stub.path).stat().st_ino)

    def test_schema_and_protocol_mismatch(self):
        for schema, protocol in ((29, 7), (30, 6)):
            with StubPrime(lambda s, r: s.response(r), schema=schema, protocol=protocol) as stub:
                with self.assertRaisesRegex(CliError, "protocol 7/schema 30"):
                    PrimeClient(stub.path).connect()
            self.assertEqual(stub.requests, [])

    def test_multiplex_pending_prompt_release_events_and_actual_failure(self):
        prompt = []
        def handle(stub, request):
            kind = request["command"]["type"]
            if kind == "prompt_and_wait":
                prompt.append(request)
                return {"type": "session_event", "event": {"type": "message_update"}}
            return [stub.response(request, {"released": True}), stub.response(prompt[0], success=False, error="provider preflight refused")]
        with StubPrime(handle) as stub, PrimeClient(stub.path) as client:
            pending = client.write("prompt_and_wait", activeSessionId="routing", message="雪", streamingBehavior="followUp")
            released = client.query("release_session_input_pause", activeSessionId="routing", pauseId="pause")
            result = client.wait(pending)
            self.assertEqual(released, {"released": True})
            self.assertEqual((result["success"], result["error"]), (False, "provider preflight refused"))
            self.assertEqual(len(client.events), 1)
            with self.assertRaisesRegex(CliError, "already written"):
                client.write("prompt_and_wait", command_id=pending, message="same")
        self.assertEqual([r["command"]["type"] for r in stub.requests], ["prompt_and_wait", "release_session_input_pause"])

    def test_unknown_response_is_not_success_or_automatic_resend(self):
        with StubPrime(lambda s, r: None) as stub, PrimeClient(stub.path, timeout=0.05) as client:
            command = client.write("prompt_and_wait", message="one")
            with self.assertRaises(TimeoutError):
                client.wait(command)
            with self.assertRaises(CliError):
                client.write("prompt_and_wait", command_id=command, message="one")
        self.assertEqual(len(stub.requests), 1)

    def test_durable_and_routing_ids_are_distinct(self):
        with StubPrime(lambda s, r: s.response(r, {"sessionId": "durable", "activeSessionId": "routing"})) as stub, PrimeClient(stub.path) as client:
            identity, _ = resolve_session(client, "durable", "routing")
            self.assertEqual((identity.session_id, identity.active_session_id), ("durable", "routing"))
            with self.assertRaises(CliError):
                resolve_session(client, "foreign", "routing")
        self.assertEqual(stub.requests[0]["command"]["activeSessionId"], "routing")

    def test_configuration_before_create_and_thinking_must_not_clamp(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp)
            def handle(stub, request):
                if request["command"]["type"] == "create":
                    self.assertEqual(json.loads((stream / ".prime/agent/settings.json").read_text())["compaction"]["enabled"], False)
                    return stub.response(request, {"sessionId": "durable", "activeSessionId": "routing"})
                return stub.response(request, {"sessionId": "durable", "activeSessionId": "routing", "cwd": str(stream), "thinkingLevel": "off", "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}})
            with StubPrime(handle) as stub, PrimeClient(stub.path) as client:
                with self.assertRaises(StreamsError):
                    create_stream_session(client, stream, "openai-codex/gpt-6.1-sol", "xhigh")
                settings = stream / ".prime/agent/settings.json"
                settings.parent.mkdir(parents=True)
                settings.write_text(json.dumps({"compaction": {"enabled": False, "agentCallable": False, "thresholdPercent": 1}}))
                with self.assertRaisesRegex(CliError, "changed requested thinking"):
                    create_stream_session(client, stream, "openai-codex/gpt-6.1-sol", "xhigh")
            self.assertEqual(len(stub.requests), 2)

    def test_actual_error_reply_is_saved_without_assistant(self):
        with tempfile.TemporaryDirectory() as tmp:
            stream = Path(tmp)
            project.git(stream, "init")
            project.copy_missing(project.templates_dir() / "prime", stream)
            command = str(uuid4())
            result = save_reply(stream, session_id="durable", command_id=command, sent_text="actual sent text", frame={"command": "prompt_and_wait", "success": False, "error": "preflight refused"}, messages=[])
            raw = state.read_entry(stream, result["entry"])
            self.assertIn('"error": "preflight refused"', raw)
            self.assertIn('"messages": []', raw)
            self.assertEqual(len(state.check_state(stream).log), 1)

    def test_project_prime_fields_round_trip(self):
        info = project.ProjectSection("demo", "/project", "", "", "", backend="prime", prime_binary="/owned/bin/prime-agent", prime_socket="/owned/test.sock", prime_agent_dir="/owned/agent", prime_sessions_dir="/owned/sessions", poteto_path="/owned/poteto/SKILL.md")
        model = project.ModelSettings("openai-codex/gpt-6.1-sol", "xhigh")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "demo.toml"
            path.write_text(project.dump_project(project.Project(info, model, model, project.Caps(), [])))
            parsed = project.load_project(path)
            self.assertEqual(parsed.info, info)
            self.assertEqual(parsed.coordinator.thinking, "xhigh")

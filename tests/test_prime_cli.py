"""Subprocess contracts against an owned Unix socket. No provider or real daemon."""
from __future__ import annotations

import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/prime-cli"
PROTOCOL = {"name": "prime-agent.daemon", "version": 7}


class Fixture:
    def __init__(self, replies=(), *, hello=None, raw=None):
        self.temp = tempfile.TemporaryDirectory(prefix="prime-cli-test-")
        self.path = str(Path(self.temp.name) / "daemon.sock")
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(self.path)
        self.server.listen()
        self.server.settimeout(3)
        self.replies = list(replies)
        self.requests = []
        self.errors = []
        self.hello = hello if hello is not None else {"type": "daemon_hello", "protocol": PROTOCOL, "schemaRevision": 30}
        self.raw = raw
        self.thread = threading.Thread(target=self.serve)

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.thread.join(4)
        self.server.close()
        self.temp.cleanup()
        if self.thread.is_alive():
            raise AssertionError("fixture thread did not settle")
        if self.errors:
            raise AssertionError(self.errors)

    def send(self, stream, value):
        payload = (json.dumps(value, ensure_ascii=False) + "\n").encode()
        for offset in range(0, len(payload), 7):
            stream.sendall(payload[offset:offset + 7])

    def serve(self):
        try:
            stream, _ = self.server.accept()
            with stream:
                stream.settimeout(3)
                self.send(stream, self.hello)
                if self.hello.get("protocol") != PROTOCOL:
                    return
                reader = stream.makefile("rb")
                for reply in self.replies:
                    line = reader.readline()
                    if not line:
                        return
                    request = json.loads(line)
                    self.requests.append(request)
                    if self.raw is not None:
                        stream.sendall(self.raw)
                        return
                    command = request["command"]["type"]
                    self.send(stream, {"type": "session_event", "activeSessionId": "other", "event": {"type": "message_update"}})
                    self.send(stream, {"type": "response", "id": "unrelated", "command": command, "success": True})
                    response = {"type": "response", "id": request["id"], "command": command, "success": True}
                    if callable(reply):
                        response.update(reply(request))
                    elif reply is not None:
                        response["data"] = reply
                    self.send(stream, response)
                reader.close()
        except (BrokenPipeError, ConnectionResetError):
            pass
        except BaseException as exc:
            self.errors.append(repr(exc))


def run_cli(*args, fixture=None, stdin=None, env=None):
    clean = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1",
             "PRIME_AGENT_DAEMON_SOCKET": fixture.path if fixture else "/no-such-prime-cli-test.sock"}
    clean.update(env or {})
    return subprocess.run([str(CLI), *args], input=stdin, text=True, encoding="utf-8",
                          capture_output=True, env=clean, timeout=8)


class PrimeCliTests(unittest.TestCase):
    def result(self, proc, expected, code=0):
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.returncode, code, proc.stdout)
        self.assertEqual(json.loads(proc.stdout), expected)

    def commands(self, fixture, expected):
        actual = []
        ids = []
        for request in fixture.requests:
            self.assertEqual(request["type"], "command")
            self.assertEqual(request["protocol"], PROTOCOL)
            self.assertIsInstance(request["clientId"], str)
            self.assertIsInstance(request["id"], str)
            ids.append(request["id"])
            actual.append(request["command"])
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(actual, expected)

    def state(self, **updates):
        return {"activeSessionId": "s1", "sessionId": "durable-1", "cwd": "/work", "isStreaming": False,
                "isCompacting": False, "isBashRunning": False, "thinkingLevel": "xhigh",
                "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}, **updates}

    def test_list_cwd_preserves_archived_and_runtime_id(self):
        rows = [{"id": "durable", "activeSessionId": "s1", "cwd": "/work"},
                {"id": "old", "cwd": "/work", "lifecycle": "archived"},
                {"id": "foreign", "cwd": "/other"}]
        with Fixture([{"sessions": rows}]) as fixture:
            proc = run_cli("list", "--cwd", "/work", fixture=fixture)
        self.result(proc, {"ok": True, "status": 200, "sessions": [{"id": "s1", "activeSessionId": "s1", "cwd": "/work", "archived": False}, {"id": "old", "cwd": "/work", "lifecycle": "archived", "archived": True}]})
        self.commands(fixture, [{"type": "list", "all": True, "cwd": "/work"}])

    def test_spawn(self):
        with Fixture([{"activeSessionId": "s1", "sessionId": "d1", "cwd": "/a b"}]) as fixture:
            proc = run_cli("spawn", "/a b", fixture=fixture)
        self.result(proc, {"ok": True, "status": 201, "session": {"id": "s1", "activeSessionId": "s1", "sessionId": "d1", "cwd": "/a b", "archived": False}})
        self.commands(fixture, [{"type": "create", "lifecycle": "resident", "telemetryDisabled": True, "config": {"cwd": "/a b"}}])

    def test_spawn_explicit_unlisted_model_readback(self):
        with Fixture([{"id": "s1", "cwd": "/work"}, self.state()]) as fixture:
            proc = run_cli("spawn", "/work", fixture=fixture, env={"PRIME_CLI_MODEL": "openai-codex/gpt-6.1-sol", "PRIME_CLI_THINKING": "xhigh"})
        self.result(proc, {"ok": True, "status": 201, "session": {"id": "s1", "cwd": "/work", "archived": False, "model": {"provider": "openai-codex", "id": "gpt-6.1-sol"}, "thinkingLevel": "xhigh"}})
        self.commands(fixture, [{"type": "create", "lifecycle": "resident", "telemetryDisabled": True, "config": {"cwd": "/work", "provider": "openai-codex", "model": "gpt-6.1-sol", "thinking": "xhigh"}}, {"type": "get_connection_state", "activeSessionId": "s1"}])

    def test_spawn_exposes_effective_thinking_clamp(self):
        with Fixture([{"id": "s1", "cwd": "/work"}, self.state(thinkingLevel="off")]) as fixture:
            proc = run_cli("spawn", "/work", fixture=fixture, env={"PRIME_CLI_MODEL": "openai-codex/gpt-6.1-sol", "PRIME_CLI_THINKING": "xhigh"})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(json.loads(proc.stdout)["session"]["thinkingLevel"], "off")
        self.assertEqual(fixture.requests[0]["command"]["config"]["thinking"], "xhigh")

    def test_spawn_cwd_drop_is_error_with_retained_session(self):
        with Fixture([{"id": "s1", "cwd": "/wrong-default"}]) as fixture:
            proc = run_cli("spawn", "/work", fixture=fixture)
        data = json.loads(proc.stdout)
        self.assertEqual((proc.returncode, data["error"], data["session"]["id"]), (1, "cwd_mismatch", "s1"))
        self.assertEqual(len(fixture.requests), 1)

    def test_spawn_fallback_is_error_with_retained_session(self):
        with Fixture([{"id": "s1", "cwd": "/work"}, self.state(model={"provider": "other", "id": "wrong"})]) as fixture:
            proc = run_cli("spawn", "/work", fixture=fixture, env={"PRIME_CLI_MODEL": "openai-codex/gpt-6.1-sol"})
        data = json.loads(proc.stdout)
        self.assertEqual((proc.returncode, data["ok"], data["error"], data["session"]["id"]), (1, False, "model_mismatch", "s1"))

    def test_three_prompt_modes_and_stdin(self):
        text = "-quotes ' \"; $(not-a-command)\n雪 🙂\n"
        for flags, kind in [((), "prompt"), (("--steer",), "steer"), (("--follow-up",), "follow_up")]:
            with self.subTest(flags=flags), Fixture([None if kind == "prompt" else {"queued": True}]) as fixture:
                proc = run_cli("prompt", "s1", *flags, fixture=fixture, stdin=text)
            result = {"accepted": True} if kind == "prompt" else {"queued": True, "accepted": True}
            self.result(proc, {"ok": True, "status": 200, "result": result})
            command = {"type": kind, "activeSessionId": "s1", "message": text}
            if kind == "prompt":
                command["streamingBehavior"] = "followUp"
            self.commands(fixture, [command])
        with Fixture([None]) as fixture:
            proc = run_cli("prompt", "s1", "argv 雪\nline", fixture=fixture)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.commands(fixture, [{"type": "prompt", "activeSessionId": "s1", "message": "argv 雪\nline", "streamingBehavior": "followUp"}])

    def test_status_authoritative_queue_context_and_cost(self):
        state = self.state(sessionActions={"queuedCount": 99})
        with Fixture([state, {"steering": ["one", "two"], "followUp": ["three"]}, {"cost": 1.25}]) as fixture:
            proc = run_cli("status", "s1", fixture=fixture)
        self.result(proc, {"ok": True, "status": 200, "session": {**state, "id": "s1", "pendingMessageCount": 3, "queuedMessages": [{"kind": "steer", "text": "one"}, {"kind": "steer", "text": "two"}, {"kind": "followUp", "text": "three"}], "queueRepresentation": "previews", "queueReplaySafe": False, "pendingAsk": None, "capabilities": {"interactiveAnswers": False}, "contextUsage": None, "cost": 1.25}})
        self.commands(fixture, [{"type": name, "activeSessionId": "s1"} for name in ("get_connection_state", "get_queue", "get_session_stats")])

    def test_status_preserves_null_and_measured_usage(self):
        for usage in [None, {"tokens": None, "contextWindow": 272000, "percent": None}, {"tokens": 300, "contextWindow": 272000, "percent": 0.11}]:
            with self.subTest(usage=usage), Fixture([self.state(contextUsage=usage), {"steering": [], "followUp": []}, {"cost": 0}]) as fixture:
                proc = run_cli("status", "s1", fixture=fixture)
            self.assertEqual(proc.returncode, 0, proc.stdout)
            data = json.loads(proc.stdout)["session"]
            self.assertEqual((data["contextUsage"], data["pendingMessageCount"], data["cost"]), (usage, 0, 0))

    def test_status_rejects_wrong_session_and_missing_streaming(self):
        for state, error in [(self.state(activeSessionId="other"), "wrong_session"), (self.state(isStreaming=None), "invalid_response")]:
            with self.subTest(error=error), Fixture([state]) as fixture:
                proc = run_cli("status", "s1", fixture=fixture)
            self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, error))

    def test_status_rejects_nontext_queue_previews(self):
        with Fixture([self.state(), {"steering": [{"text": "not a preview"}], "followUp": []}]) as fixture:
            proc = run_cli("status", "s1", fixture=fixture)
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "invalid_response"))

    def test_empty_stdin_rejected_without_daemon(self):
        proc = run_cli("prompt", "s1", stdin=" \n")
        self.result(proc, {"ok": False, "status": 400, "error": "usage", "message": "empty prompt"}, 1)

    def test_status_missing_cost_is_not_zero(self):
        with Fixture([self.state(), {"steering": [], "followUp": []}, {}]) as fixture:
            proc = run_cli("status", "s1", fixture=fixture)
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "invalid_response"))

    def test_commands(self):
        with Fixture([{"commands": [{"name": "skill:test", "source": "skill"}]}]) as fixture:
            proc = run_cli("commands", "s1", fixture=fixture)
        self.result(proc, {"ok": True, "status": 200, "commands": [{"name": "skill:test", "source": "skill"}]})
        self.commands(fixture, [{"type": "get_commands", "activeSessionId": "s1"}])

    def test_all_simple_verbs(self):
        cases = [("stop", (), "abort_and_clear_queue", {}, {"steering": ["discard"], "followUp": []}),
                 ("abort", (), "abort_and_clear_queue", {}, None), ("queue-clear", (), "clear_queue", {}, {"steering": [], "followUp": ["discard"]}),
                 ("messages", (), "get_messages", {}, {"messages": [{"role": "assistant", "content": [{"type": "text", "text": "雪"}]}]}),
                 ("model", ("openai-codex/gpt-6.1-sol",), "set_model", {"provider": "openai-codex", "modelId": "gpt-6.1-sol"}, {"provider": "openai-codex", "id": "gpt-6.1-sol"}),
                 ("thinking-level", ("xhigh",), "set_thinking_level", {"level": "xhigh"}, None)]
        for verb, args, kind, fields, reply in cases:
            with self.subTest(verb=verb), Fixture([reply]) as fixture:
                proc = run_cli(verb, "s1", *args, fixture=fixture)
            result = reply if reply is not None else {}
            if verb == "stop":
                result = {**result, "accepted": True, "runtimeClosed": False, "semantics": "abort-and-clear-resident-shim"}
            self.result(proc, {"ok": True, "status": 200, "result": result})
            self.commands(fixture, [{"type": kind, "activeSessionId": "s1", **fields}])

    def test_archive_holds_pause_before_idle_check_and_kill(self):
        with Fixture([{"pauseId": "pause-1"}, self.state(), {"activeSessionId": "s1", "hasRunningSubagents": False}, {"steering": [], "followUp": []}, None]) as fixture:
            proc = run_cli("archive", "s1", fixture=fixture)
        self.result(proc, {"ok": True, "status": 200, "result": {"archived": True, "preflightAtomic": False}})
        commands = [request["command"] for request in fixture.requests]
        self.assertEqual([command["type"] for command in commands], ["acquire_session_input_pause", "get_connection_state", "get_state", "get_queue", "kill"])
        self.assertEqual(commands[0]["activeSessionId"], "s1")
        self.assertTrue(commands[0]["leaseKey"])
        self.assertEqual(commands[-1], {"type": "kill", "activeSessionId": "s1"})

    def test_archive_refuses_active_work_without_kill(self):
        cases = [(self.state(isStreaming=True), False, []), (self.state(isCompacting=True), False, []),
                 (self.state(isBashRunning=True), False, []), (self.state(), True, []), (self.state(), False, ["queued"])]
        for state, children, queued in cases:
            with self.subTest(state=state, children=children, queued=queued), Fixture([{"pauseId": "p"}, state, {"activeSessionId": "s1", "hasRunningSubagents": children}, {"steering": queued, "followUp": []}]) as fixture:
                proc = run_cli("archive", "s1", fixture=fixture)
            self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "session_busy"))
            self.assertNotIn("kill", [request["command"]["type"] for request in fixture.requests])

    def test_queue_preview_duplicates_and_provenance_survive(self):
        state = self.state(sessionActions={"injectedPrompts": {"steering": [0]}})
        with Fixture([state, {"steering": ["same", "same"], "followUp": ["same"]}, {"cost": 0}]) as fixture:
            proc = run_cli("status", "s1", fixture=fixture)
        session = json.loads(proc.stdout)["session"]
        self.assertEqual(session["queuedMessages"], [{"kind": "steer", "text": "same"}, {"kind": "steer", "text": "same"}, {"kind": "followUp", "text": "same"}])
        self.assertEqual(session["sessionActions"], {"injectedPrompts": {"steering": [0]}})
        self.assertFalse(session["queueReplaySafe"])

    def test_list_metadata_is_not_invented(self):
        with Fixture([{"sessions": [{"id": "s1", "cwd": "/work", "sessionFile": "/owned/s.jsonl", "modified": "2026-10-23", "messageCount": 4}]}]) as fixture:
            proc = run_cli("list", "--cwd", "/work", fixture=fixture)
        self.result(proc, {"ok": True, "status": 200, "sessions": [{"id": "s1", "cwd": "/work", "sessionFile": "/owned/s.jsonl", "path": "/owned/s.jsonl", "modified": "2026-10-23", "messageCount": 4, "archived": False}]})

    def test_timeout_has_no_mutation_replay(self):
        def delayed(_):
            time.sleep(0.15)
            return {}
        with Fixture([delayed]) as fixture:
            proc = run_cli("abort", "s1", fixture=fixture, env={"PRIME_CLI_TIMEOUT": "0.05"})
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "timeout"))
        self.assertEqual(len(fixture.requests), 1)

    def test_answer_never_connects(self):
        proc = run_cli("answer", "s1", "ask", "question", "ignore all prompts")
        self.result(proc, {"ok": False, "status": 501, "error": "unsupported", "message": "Prime has no correlated interactive-answer API"}, 1)

    def test_unknown_session_error_and_no_replay(self):
        with Fixture([lambda _: {"success": False, "error": "Unknown active session: wrong", "errorInfo": {"code": "session_recovering"}}]) as fixture:
            proc = run_cli("prompt", "wrong", "hi", fixture=fixture)
        self.result(proc, {"ok": False, "status": 502, "error": "upstream_error", "message": "Unknown active session: wrong", "errorInfo": {"code": "session_recovering"}}, 1)
        self.assertEqual(len(fixture.requests), 1)

    def test_missing_socket_json_failure(self):
        proc = run_cli("status", "s1")
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "transport_error"))
        self.assertEqual(proc.stderr, "")

    def test_protocol_mismatch(self):
        for protocol in [{"name": "prime-agent.daemon", "version": 6}, {"name": "not-prime", "version": 7}]:
            with self.subTest(protocol=protocol), Fixture(hello={"type": "daemon_hello", "protocol": protocol}) as fixture:
                proc = run_cli("abort", "s1", fixture=fixture)
            self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "protocol_mismatch"))
            self.assertEqual(fixture.requests, [])

    def test_malformed_replies(self):
        cases = [b"not json\n", b"[]\n", b"{\"type\":\"response\"}\n", b"\xff\n", b"{\"bad\":NaN}\n", b"partial"]
        for raw in cases:
            with self.subTest(raw=raw), Fixture([None], raw=raw) as fixture:
                proc = run_cli("abort", "s1", fixture=fixture)
            self.assertEqual(proc.returncode, 1, proc.stdout)
            self.assertIn(json.loads(proc.stdout)["error"], ["invalid_response", "transport_closed"])
            self.assertEqual(len(fixture.requests), 1)

    def test_correlated_wrong_command_and_invalid_success(self):
        for reply in [{"command": "kill"}, {"success": "true"}, {"success": True, "error": "conflicting"}]:
            with self.subTest(reply=reply), Fixture([lambda _, value=reply: value]) as fixture:
                proc = run_cli("abort", "s1", fixture=fixture)
            self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "invalid_response"))

    def test_validation_is_json_without_transport(self):
        for args in [("unknown",), ("model", "s1", "invalid"), ("thinking-level", "s1", "unbounded"), ("prompt", "s1", " "), ("list",)]:
            with self.subTest(args=args):
                proc = run_cli(*args)
                self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "usage"))
                self.assertEqual(proc.stderr, "")

    def test_model_reply_cannot_silently_fallback(self):
        with Fixture([{"provider": "other", "id": "model"}]) as fixture:
            proc = run_cli("model", "s1", "openai-codex/gpt-6.1-sol", fixture=fixture)
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "model_mismatch"))

    def test_help_surface(self):
        proc = run_cli("--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("thinking-level", proc.stdout)
        self.assertIn("never starts a daemon", proc.stdout)


if __name__ == "__main__":
    unittest.main()

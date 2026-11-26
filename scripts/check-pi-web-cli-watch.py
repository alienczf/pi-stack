#!/usr/bin/env python3
"""Exercise the installed command shape through the checked-in executable. No service required."""
from __future__ import annotations

import base64
import hashlib
import json
import os
from pathlib import Path
import struct
import subprocess
import tempfile
import threading
import time
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, urlsplit

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "bin/pi-web-cli"
SID = "fresh-one"
PREFIX = "/api/sessions/" + quote(SID, safe="")
USER = {"role": "user", "content": "Initial prompt", "timestamp": 1}
FINAL = {"role": "assistant", "content": [{"type": "text", "text": "Final answer"}], "stopReason": "stop", "responseId": "response-final"}
EARLIER = {"role": "assistant", "content": "Earlier answer", "stopReason": "stop"}


class Server(ThreadingHTTPServer):
    daemon_threads = True
    block_on_close = False

    def handle_error(self, request, client_address):
        pass


class Fixture:
    def __init__(self, scenario="complete", **options):
        self.scenario = scenario
        self.options = options
        self.messages = []
        self.status = {"sessionId": SID, "isStreaming": False, "isCompacting": False, "isBashRunning": False,
                       "pendingMessageCount": 0, "messageCount": 0, "queuedMessages": [],
                       "sessionFileDiagnostics": [], "persisted": False,
                       "model": {"provider": "prov", "id": "mod"}, "thinkingLevel": "off"}
        self.requests = []
        self.started = False
        self.stop = threading.Event()
        self.lock = threading.Lock()
        self.seq = 100
        self.ws = None
        self.watch_status_count = 0
        self.slow_paths = {}
        fixture = self

        class Handler(BaseHTTPRequestHandler):
            protocol_version = "HTTP/1.1"

            def log_message(self, *_args):
                pass

            def send_json(self, value, code=200):
                raw = json.dumps(value).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers.get("Content-Length", 0))))
                with fixture.lock:
                    fixture.requests.append(("POST", self.path, body))
                options = fixture.options
                if self.path == "/api/sessions":
                    return self.send_json({"error": "spawn refused"}, 500) if options.get("spawn_fail") else self.send_json({"id": SID, "cwd": body["cwd"]})
                if self.path == PREFIX + "/model":
                    if options.get("model_fail"):
                        return self.send_json({"error": "unknown model"}, 400)
                    if not options.get("model_ignored"):
                        fixture.status["model"] = {"provider": body["provider"], "id": body["modelId"]}
                    return self.send_json({"ok": True})
                if self.path == PREFIX + "/thinking-level":
                    fixture.status["thinkingLevel"] = body["level"]
                    return self.send_json({"ok": True})
                if options.get("prompt_reject"):
                    return self.send_json({"accepted": False, "error": "busy"}, options["prompt_reject"])
                with fixture.lock:
                    fixture.started = True
                    fixture.messages = [USER]
                    fixture.status.update(isStreaming=True, persisted=True, messageCount=1)
                    if fixture.scenario in ("fast", "fast_live", "partial_frame", "stalled_upgrade", "disconnect", "tool_error", "oversized", "output_limit", "fast_error"):
                        terminal = dict(FINAL)
                        if fixture.scenario == "output_limit":
                            terminal["content"] = "x" * (1024 * 1024 + 1)
                        if fixture.scenario == "fast_error":
                            terminal.update(stopReason="error", errorMessage="Provider failed")
                        fixture.messages = [USER, terminal]
                        fixture.status.update(isStreaming=False, messageCount=2)
                    if fixture.scenario == "malformed_history":
                        fixture.messages = [USER, {"role": "assistant", "stopReason": "stop", "content": [{"type": "text", "text": 123}, {"type": "text", "text": "Incomplete extraction"}]}]
                        fixture.status.update(isStreaming=False, messageCount=2)
                    if fixture.scenario in ("settling_hooks", "settlement_during_read"):
                        fixture.messages = [USER, EARLIER]
                        fixture.status.update(isStreaming=False, messageCount=2)
                    if fixture.scenario == "multiple_users":
                        fixture.messages = [USER, EARLIER, {"role": "user", "content": "Another prompt"}]
                    if fixture.scenario in ("questions", "dialog"):
                        fixture.status["pendingDialogs"] = [{"dialogId": "dialog-1"}, {"dialogId": "dialog-2"}]
                        if fixture.scenario == "questions":
                            fixture.status["pendingAsk"] = {"askId": "ask-1", "questions": [{"id": "q-1"}, {"id": "q-2"}]}
                if options.get("prompt_drop"):
                    self.close_connection = True
                    return
                if options.get("prompt_hang"):
                    fixture.stop.wait(options["prompt_hang"])
                result = {"accepted": True}
                if "deliveryId" in body:
                    result["deliveryId"] = body["deliveryId"]
                self.send_json(result)

            def do_GET(self):
                with fixture.lock:
                    fixture.requests.append(("GET", self.path, None))
                path = urlsplit(self.path).path
                if path == PREFIX + "/events":
                    if fixture.scenario == "stalled_upgrade":
                        fixture.stop.wait(10)
                        return
                    key = self.headers["Sec-WebSocket-Key"]
                    accept = base64.b64encode(hashlib.sha1((key + "258EAFA5-E914-47DA-95CA-C5AB0DC85B11").encode()).digest()).decode()
                    self.send_response(101)
                    self.send_header("Upgrade", "websocket")
                    self.send_header("Connection", "Upgrade")
                    self.send_header("Sec-WebSocket-Accept", accept)
                    self.end_headers()
                    fixture.events(self.connection)
                    self.close_connection = True
                    return
                with fixture.lock:
                    started = fixture.started
                    slow = False
                    if started and fixture.scenario in ("slow_status", "slow_messages") and path.endswith("/" + fixture.scenario.split("_")[1]):
                        fixture.slow_paths[path] = fixture.slow_paths.get(path, 0) + 1
                        slow = fixture.slow_paths[path] == 1
                if slow:
                    # Mirrors a live backend that answers a read after about 2.5 s while a run is active.
                    fixture.stop.wait(2.5)
                with fixture.lock:
                    status = dict(fixture.status)
                    messages = list(fixture.messages)
                if started and fixture.scenario == "stalled_headers" and path.endswith("/status"):
                    fixture.stop.wait(10)
                    return
                if started and fixture.scenario == "trickle" and path.endswith("/messages"):
                    self.send_response(200)
                    self.send_header("Content-Length", "100000")
                    self.end_headers()
                    self.wfile.write(b"[")
                    self.wfile.flush()
                    while not fixture.stop.wait(0.03):
                        self.wfile.write(b" ")
                        self.wfile.flush()
                    return
                if started and fixture.scenario == "oversized" and path.endswith("/messages"):
                    raw = b" " * (4 * 1024 * 1024 + 1)
                    self.send_response(200)
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    self.wfile.write(raw)
                    return
                if started and fixture.scenario == "settlement_during_read" and path.endswith("/status"):
                    fixture.watch_status_count += 1
                    if fixture.watch_status_count == 2:
                        fixture.finish(fixture.ws)
                if path.endswith("/status"):
                    self.send_json(status)
                elif path.endswith("/messages"):
                    if fixture.scenario == "paged":
                        messages = {"messages": messages, "start": 0, "total": len(messages)}
                    elif started and fixture.scenario == "incomplete_page":
                        messages = {"messages": [], "start": 1, "total": 2}
                    self.send_json(messages)
                elif path.endswith("/commands"):
                    self.send_json([{"name": "model"}])
                else:
                    self.send_error(404)

        self.server = Server(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={"poll_interval": 0.02}, daemon=True)
        self.env = {**os.environ, "PI_WEB_URL": "http://127.0.0.1:" + str(self.server.server_port)}

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=1)

    def emit(self, connection, event):
        self.seq += 1
        payload = json.dumps({**event, "seq": self.seq}).encode()
        opcode = 2 if self.scenario in ("binary", "fragmented_binary") else 1
        header = bytes((128 | opcode, len(payload))) if len(payload) < 126 else bytes((128 | opcode, 126)) + struct.pack("!H", len(payload))
        if self.scenario in ("fragmented", "fragmented_binary") and event.get("eventType") == "agent_settled":
            split = len(payload) // 2
            connection.sendall(bytes((opcode, split)) + payload[:split] + b"\x89\x01?" + bytes((128, len(payload) - split)) + payload[split:])
        else:
            connection.sendall(header + payload)

    def finish(self, connection, message=FINAL):
        with self.lock:
            self.messages = [*self.messages, message]
            if self.scenario == "trailing_compaction":
                self.messages.append({"role": "system", "source": "compaction", "content": "Compacted history"})
            self.status.update(isStreaming=False, isCompacting=False, isBashRunning=False, pendingMessageCount=0, queuedMessages=[], messageCount=len(self.messages))
        self.emit(connection, {"type": "pi.event", "eventType": "agent_settled"})

    def events(self, connection):
        self.ws = connection
        try:
            while self.options and not self.started and not self.stop.wait(0.01):
                pass
            if self.scenario == "frame_limit":
                with self.lock:
                    self.messages = [USER, FINAL]
                    self.status.update(isStreaming=False, messageCount=2)
                connection.sendall(b"\x81\x7f" + struct.pack("!Q", 2 * 1024 * 1024))
            elif self.scenario == "partial_frame":
                connection.sendall(b'\x81\x7e\x00\x40{"seq"')
            elif self.scenario == "fast_live":
                self.emit(connection, {"type": "pi.event", "eventType": "agent_settled"})
            elif self.scenario in ("fast", "stalled_upgrade", "questions", "dialog", "multiple_users", "oversized", "incomplete_page", "stalled_headers", "trickle", "output_limit", "fast_error", "settlement_during_read") or not self.started:
                pass
            elif self.scenario == "disconnect":
                self.emit(connection, {"type": "agent.end"})
                return
            elif self.scenario == "tool_error":
                self.emit(connection, {"type": "tool.end", "isError": True})
                self.emit(connection, {"type": "agent.end"})
            else:
                self.emit(connection, {"type": "agent.start"})
                if self.stop.wait(self.options.get("settle_after", 0.16)):
                    return
                if self.scenario == "retry":
                    with self.lock:
                        self.messages.append({"role": "assistant", "content": "", "stopReason": "error", "errorMessage": "Retry me"})
                    self.emit(connection, {"type": "agent.end"})
                    self.emit(connection, {"type": "tool.end", "isError": True})
                    self.emit(connection, {"type": "pi.event", "eventType": "auto_retry_start"})
                    if self.stop.wait(0.16):
                        return
                    with self.lock:
                        self.messages.extend([EARLIER, {"role": "system", "source": "compaction", "content": "Summary"}])
                        self.status.update(isCompacting=True, pendingMessageCount=1, queuedMessages=[{"kind": "followUp", "text": "Continue"}])
                    self.emit(connection, {"type": "agent.end"})
                    self.emit(connection, {"type": "pi.event", "eventType": "auto_compaction_start"})
                    if self.stop.wait(0.16):
                        return
                if self.scenario == "changed_history":
                    with self.lock:
                        self.messages = [{"role": "user", "content": "Replaced prompt"}]
                if self.scenario == "session_error":
                    self.emit(connection, {"type": "session.error", "message": "Settlement extension failed"})
                if self.scenario in ("failure", "abort", "ambiguous"):
                    with self.lock:
                        self.messages.append(EARLIER)
                    stop_reason = {"failure": "error", "abort": "aborted", "ambiguous": "length"}[self.scenario]
                    self.finish(connection, {"role": "assistant", "content": "Latest evidence", "stopReason": stop_reason, "errorMessage": "Provider failed"})
                elif self.scenario in ("queued", "queue_cleared", "compacting", "bash"):
                    with self.lock:
                        self.messages.append(FINAL)
                        self.status.update(isStreaming=False, messageCount=2)
                        if self.scenario in ("queued", "queue_cleared"):
                            self.status.update(pendingMessageCount=1, queuedMessages=[{"kind": "followUp", "text": "Continue"}])
                        else:
                            self.status["isCompacting" if self.scenario == "compacting" else "isBashRunning"] = True
                    self.emit(connection, {"type": "pi.event", "eventType": "agent_settled"})
                    if self.scenario == "queue_cleared" and not self.stop.wait(0.25):
                        with self.lock:
                            self.status.update(pendingMessageCount=0, queuedMessages=[])
                else:
                    if self.scenario == "sequence_gap":
                        self.seq += 1
                    final = dict(FINAL)
                    if self.scenario == "blocked_output":
                        final["content"] = "x" * 200000
                    if self.scenario == "not_persisted":
                        with self.lock:
                            self.status["persisted"] = False
                    self.finish(connection, final)
            self.stop.wait(10)
        except OSError:
            pass


class WatchTests(unittest.TestCase):
    def invoke(self, fixture, *args, timeout=4, stdin=None):
        started = time.monotonic()
        process = subprocess.run([str(CLI), *args], env=fixture.env, capture_output=True, timeout=timeout, input=stdin)
        elapsed = time.monotonic() - started
        self.assertEqual(process.stderr, b"")
        decoder = json.JSONDecoder()
        value, end = decoder.raw_decode(process.stdout.decode())
        self.assertEqual(process.stdout.decode()[end:].strip(), "", "stdout must contain exactly one JSON value")
        self.assertLessEqual(len(process.stdout), 1024 * 1024)
        return process.returncode, value, elapsed

    def baseline(self, fixture, directory):
        mark = len(fixture.requests)
        code, value, _ = self.invoke(fixture, "watch", SID, "--baseline", "--timeout", "1")
        self.assertEqual(code, 0, value)
        self.assertEqual(value["kind"], "baseline")
        self.assertIs(value["ok"], True)
        self.assertEqual(value["history"]["count"], 0)
        self.assertEqual(value["sessionId"], SID)
        self.assertEqual([request[0] for request in fixture.requests[mark:]], ["GET", "GET", "GET"])
        path = Path(directory) / "baseline.json"
        path.write_text(json.dumps(value))
        return path

    def prompt(self, fixture):
        code, value, _ = self.invoke(fixture, "prompt", SID, USER["content"], "--delivery-id", "receipt-only")
        self.assertEqual(code, 0)
        self.assertEqual(value, {"ok": True, "transportAccepted": True, "status": 200, "result": {"accepted": True, "deliveryId": "receipt-only"}})

    def run_watch(self, scenario, expected, seconds=0.75, send_prompt=True, timeout=4, bound=None):
        with Fixture(scenario) as fixture, tempfile.TemporaryDirectory() as directory:
            baseline = self.baseline(fixture, directory)
            if send_prompt:
                self.prompt(fixture)
            mark = len(fixture.requests)
            code, value, elapsed = self.invoke(fixture, "watch", SID, "--since", str(baseline), "--timeout", str(seconds), timeout=timeout)
            self.assertEqual(code, 0 if expected == "completed" else 1, value)
            self.assertEqual(value["outcome"], expected, value)
            self.assertEqual(value["ok"], expected == "completed")
            self.assertEqual(value["sessionId"], SID)
            self.assertEqual(set(value), {"schemaVersion", "kind", "ok", "sessionId", "outcome", "reason", "finalAssistant", "candidateAssistant", "questions", "evidence"})
            self.assertLess(elapsed, bound or seconds + 0.65, (scenario, elapsed))
            observed = fixture.requests[mark:]
            self.assertTrue(observed)
            self.assertTrue(all(method == "GET" and path in (PREFIX + "/status", PREFIX + "/messages", PREFIX + "/events") for method, path, _body in observed), observed)
            if expected != "completed":
                self.assertIsNone(value["finalAssistant"])
            return value, elapsed

    def test_live_completion_and_reference(self):
        value, _ = self.run_watch("complete", "completed", seconds=1.5)
        digest = hashlib.sha256(json.dumps(FINAL, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()).hexdigest()
        self.assertEqual(value["reason"], "native_settled_and_reconciled")
        self.assertEqual(value["finalAssistant"], {"text": "Final answer", "stopReason": "stop", "reference": {"sessionId": SID, "historyIndex": 1, "sha256": digest, "responseId": "response-final"}})
        self.assertIsNone(value["candidateAssistant"])
        self.assertEqual(value["questions"], {"askId": None, "questionIds": [], "dialogIds": []})

    def test_fast_live_settlement_needs_no_observed_start_or_streaming(self):
        value, _ = self.run_watch("fast_live", "completed", seconds=1.5)
        self.assertEqual(value["finalAssistant"]["text"], "Final answer")
        self.assertEqual(value["finalAssistant"]["reference"]["historyIndex"], 1)
        self.assertEqual(value["evidence"]["events"]["settled_seq"], 101)
        self.assertEqual(value["evidence"]["events"]["last_seq"], 101)
        self.assertFalse(value["evidence"]["status"]["isStreaming"])

    def test_paged_history_and_fragmented_websocket_with_ping(self):
        for scenario in ("paged", "fragmented"):
            with self.subTest(scenario=scenario):
                self.run_watch(scenario, "completed", seconds=1.5)

    def test_proxy_binary_websocket_events(self):
        for scenario in ("binary", "fragmented_binary"):
            with self.subTest(scenario=scenario):
                self.run_watch(scenario, "completed", seconds=1.5)

    def test_slow_read_below_the_command_deadline_is_not_a_timeout(self):
        for scenario in ("slow_status", "slow_messages"):
            with self.subTest(scenario=scenario):
                value, elapsed = self.run_watch(scenario, "completed", seconds=10, timeout=15, bound=10.65)
                self.assertGreater(elapsed, 2.4)
                self.assertEqual(value["reason"], "native_settled_and_reconciled")

    def test_trailing_compaction_preserves_final_assistant_reference(self):
        value, _ = self.run_watch("trailing_compaction", "completed", seconds=1.5)
        self.assertEqual(value["finalAssistant"]["text"], "Final answer")
        self.assertEqual(value["finalAssistant"]["reference"]["historyIndex"], 1)
        self.assertEqual(value["evidence"]["historyCount"], 3)

    def test_settlement_must_precede_the_history_used_for_completion(self):
        for scenario in ("settling_hooks", "settlement_during_read"):
            with self.subTest(scenario=scenario):
                value, _ = self.run_watch(scenario, "completed", seconds=1.5)
                self.assertEqual(value["finalAssistant"]["text"], "Final answer")
                self.assertEqual(value["finalAssistant"]["reference"]["historyIndex"], 2)

    def test_initial_idle_is_not_completion(self):
        value, elapsed = self.run_watch("idle", "timeout", send_prompt=False)
        self.assertEqual(value["evidence"]["historyCount"], 0)
        self.assertIsNone(value["candidateAssistant"])
        self.assertGreater(elapsed, 0.5)

    def test_missed_fast_settlement_retains_only_candidate(self):
        for scenario in ("fast", "fast_error"):
            with self.subTest(scenario=scenario):
                value, _ = self.run_watch(scenario, "unknown")
                self.assertEqual(value["reason"], "settlement_unproven")
                self.assertEqual(value["candidateAssistant"]["text"], "Final answer")

    def test_questions_override_streaming(self):
        value, _ = self.run_watch("questions", "needs_input")
        self.assertEqual(value["questions"], {"askId": "ask-1", "questionIds": ["q-1", "q-2"], "dialogIds": ["dialog-1", "dialog-2"]})
        self.assertTrue(value["evidence"]["status"]["isStreaming"])
        value, _ = self.run_watch("dialog", "needs_input")
        self.assertEqual(value["questions"], {"askId": None, "questionIds": [], "dialogIds": ["dialog-1", "dialog-2"]})

    def test_retry_compaction_and_continuation_wait_for_native_settlement(self):
        value, elapsed = self.run_watch("retry", "completed", seconds=1.8)
        self.assertGreater(elapsed, 0.48)
        self.assertEqual(value["finalAssistant"]["text"], "Final answer")
        self.assertEqual(value["finalAssistant"]["reference"]["historyIndex"], 4)
        self.assertEqual(value["evidence"]["events"]["errors"][0]["type"], "tool.end")

    def test_session_error_is_evidence_not_success(self):
        value, _ = self.run_watch("session_error", "unknown", seconds=1.5)
        self.assertEqual(value["reason"], "session_error_observed")
        self.assertEqual(value["candidateAssistant"]["text"], "Final answer")
        self.assertEqual(value["evidence"]["events"]["errors"], [{"seq": 102, "type": "session.error", "message": "Settlement extension failed", "messageTruncated": False}])

    def test_latest_error_abort_and_ambiguous_stop_never_use_earlier_answer(self):
        for scenario, expected, stop in (("failure", "failed", "error"), ("abort", "interrupted", "aborted"), ("ambiguous", "unknown", "length")):
            with self.subTest(scenario=scenario):
                value, _ = self.run_watch(scenario, expected, seconds=1.5)
                self.assertEqual(value["candidateAssistant"]["text"], "Latest evidence")
                self.assertEqual(value["candidateAssistant"]["stopReason"], stop)
                self.assertEqual(value["candidateAssistant"]["errorMessage"], "Provider failed")

    def test_queue_compaction_bash_and_tool_errors_are_not_success(self):
        for scenario in ("queued", "compacting", "bash"):
            with self.subTest(scenario=scenario):
                self.run_watch(scenario, "timeout")
        value, _ = self.run_watch("queue_cleared", "unknown")
        self.assertEqual(value["reason"], "settlement_unproven")
        self.run_watch("tool_error", "unknown")

    def test_transport_gaps_never_prove_success(self):
        for scenario in ("disconnect", "sequence_gap", "partial_frame", "stalled_upgrade", "frame_limit"):
            with self.subTest(scenario=scenario):
                self.run_watch(scenario, "unknown")

    def test_attribution_and_history_boundary(self):
        for scenario, reason in (("multiple_users", "initial_prompt_attribution_lost"), ("changed_history", "history_boundary_changed"), ("incomplete_page", "incomplete_history"), ("malformed_history", "invalid_history")):
            with self.subTest(scenario=scenario):
                value, _ = self.run_watch(scenario, "unknown")
                self.assertEqual(value["reason"], reason)

    def test_persistence_is_required_but_not_claimed_as_fsync(self):
        value, _ = self.run_watch("not_persisted", "unknown", seconds=1.5)
        self.assertEqual(value["reason"], "history_persistence_unproven")

    def test_stalled_http_and_body_limits(self):
        for scenario in ("stalled_headers", "trickle"):
            with self.subTest(scenario=scenario):
                self.run_watch(scenario, "timeout", seconds=0.5)
        value, _ = self.run_watch("oversized", "unknown")
        self.assertEqual(value["reason"], "http_body_limit")
        value, _ = self.run_watch("output_limit", "unknown")
        self.assertEqual(value["reason"], "output_limit")
        self.assertIsNone(value["candidateAssistant"])

    def test_baseline_rejects_used_or_busy_session_and_mismatched_origin(self):
        with Fixture() as fixture, tempfile.TemporaryDirectory() as directory:
            baseline = self.baseline(fixture, directory)
            saved = json.loads(baseline.read_text())
            saved["apiOrigin"] = "http://another-origin.invalid"
            baseline.write_text(json.dumps(saved))
            code, value, _ = self.invoke(fixture, "watch", SID, "--since", str(baseline), "--timeout", "1")
            self.assertEqual(code, 1)
            self.assertEqual(value["reason"], "invalid_baseline")
            self.prompt(fixture)
            code, value, _ = self.invoke(fixture, "watch", SID, "--baseline", "--timeout", "1")
            self.assertEqual(code, 1)
            self.assertEqual(value["reason"], "baseline_requires_fresh_idle_session")

    def test_invalid_baselines_and_timeout_values_are_structured(self):
        with Fixture() as fixture, tempfile.TemporaryDirectory() as directory:
            baseline = self.baseline(fixture, directory)
            valid = baseline.read_text()
            cases = [("x" * 65537, "baseline_file_limit"), ("{", "invalid_json")]
            busy = json.loads(valid)
            busy["status"]["isStreaming"] = True
            cases.append((json.dumps(busy), "invalid_baseline"))
            boolean_version = json.loads(valid)
            boolean_version["schemaVersion"] = True
            cases.append((json.dumps(boolean_version), "invalid_baseline"))
            for raw, reason in cases:
                with self.subTest(reason=reason):
                    baseline.write_text(raw)
                    mark = len(fixture.requests)
                    code, value, _ = self.invoke(fixture, "watch", SID, "--since", str(baseline), "--timeout", "0.5")
                    self.assertEqual((code, value["outcome"], value["reason"]), (1, "unknown", reason))
                    self.assertEqual(fixture.requests[mark:], [])
            for seconds in ("0", "nan", "inf"):
                with self.subTest(seconds=seconds):
                    code, value, _ = self.invoke(fixture, "watch", SID, "--baseline", "--timeout", seconds)
                    self.assertEqual((code, value["outcome"]), (1, "unknown"))
                    self.assertEqual(value["reason"], "timeout_must_be_between_0.1_and_86400")

    def test_baseline_validates_status_and_pending_work(self):
        with Fixture() as fixture:
            fresh = dict(fixture.status)
            cases = [({"isStreaming": True}, "baseline_requires_fresh_idle_session"),
                     ({"pendingMessageCount": 1, "queuedMessages": [{"kind": "followUp", "text": "queued"}]}, "baseline_requires_fresh_idle_session"),
                     ({"pendingAsk": {"askId": "ask", "questions": [{"id": "q"}]}}, "baseline_requires_fresh_idle_session"),
                     ({"sessionFileDiagnostics": [{"message": "Persistence failed"}]}, "baseline_requires_fresh_idle_session"),
                     ({"isStreaming": "false"}, "invalid_status"),
                     ({"pendingMessageCount": 1}, "contradictory_queue"),
                     ({"sessionId": "different"}, "invalid_status_identity")]
            for changed, reason in cases:
                with self.subTest(reason=reason, changed=changed):
                    fixture.status = {**fresh, **changed}
                    code, value, _ = self.invoke(fixture, "watch", SID, "--baseline", "--timeout", "0.75")
                    self.assertEqual((code, value["outcome"], value["reason"]), (1, "unknown", reason))

    def test_stalled_baseline_file_is_bounded(self):
        with Fixture() as fixture, tempfile.TemporaryDirectory() as directory:
            fifo = Path(directory) / "no-writer"
            os.mkfifo(fifo)
            code, value, elapsed = self.invoke(fixture, "watch", SID, "--since", str(fifo), "--timeout", "0.4")
            self.assertEqual(code, 1)
            self.assertEqual(value["outcome"], "timeout")
            self.assertLess(elapsed, 1.05)
            self.assertEqual(fixture.requests, [])

    def test_short_deadline_exits_with_open_socket(self):
        with Fixture("fast") as fixture, tempfile.TemporaryDirectory() as directory:
            baseline = self.baseline(fixture, directory)
            self.prompt(fixture)
            for attempt in range(5):
                with self.subTest(attempt=attempt):
                    code, value, _ = self.invoke(
                        fixture, "watch", SID, "--since", str(baseline), "--timeout", "0.1", timeout=1.25
                    )
                    self.assertEqual(code, 1, value)
                    self.assertIn(value["outcome"], ("unknown", "timeout"))

    def test_stalled_output_reader_cannot_keep_process_alive(self):
        with Fixture("blocked_output") as fixture, tempfile.TemporaryDirectory() as directory:
            baseline = self.baseline(fixture, directory)
            self.prompt(fixture)
            started = time.monotonic()
            process = subprocess.Popen([str(CLI), "watch", SID, "--since", str(baseline), "--timeout", "0.8"], env=fixture.env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                self.assertEqual(process.wait(timeout=1.7), 1)
                self.assertLess(time.monotonic() - started, 1.45)
                output, errors = process.communicate(timeout=1)
                self.assertEqual(errors, b"")
                self.assertLess(len(output), 200000)
            finally:
                if process.poll() is None:
                    process.kill()
                    process.communicate()

    RUN_KEYS = {"schemaVersion", "kind", "ok", "outcome", "reason", "sessionId", "cwd", "settings", "failedStep", "error",
                "finalAssistant", "candidateAssistant", "questions", "evidence", "baseline"}
    PROMPT = "Run the task \u2014 d\u00e9j\u00e0 vu \u2713"

    def run_cli(self, scenario="complete", seconds=5, stdin=None, model="prov/mod", thinking="high", bound=None, **options):
        fixture = Fixture(scenario, run_mode=True, **options)
        with fixture:
            code, value, elapsed = self.invoke(fixture, "run", "/work", "--model", model, "--thinking", thinking, "--timeout", str(seconds),
                                               timeout=seconds + 8, stdin=(self.PROMPT if stdin is None else stdin).encode())
            self.assertEqual(set(value), self.RUN_KEYS)
            self.assertEqual((value["schemaVersion"], value["kind"], value["cwd"]), (1, "run", "/work"))
            self.assertEqual(code, 0 if value["outcome"] == "completed" else 1, value)
            self.assertEqual(value["ok"], value["outcome"] == "completed")
            self.assertLess(elapsed, bound or seconds + 0.65, elapsed)
            posts = [request for request in fixture.requests if request[0] == "POST"]
            self.assertFalse([request for request in fixture.requests if request[0] in ("DELETE",) or request[1].endswith(("/stop", "/archive", "/abort"))])
            return value, fixture, posts, elapsed

    def test_run_completes_end_to_end(self):
        value, fixture, posts, _ = self.run_cli()
        self.assertEqual((value["outcome"], value["reason"], value["failedStep"], value["error"]), ("completed", "native_settled_and_reconciled", None, None))
        self.assertEqual((value["sessionId"], value["settings"]), (SID, {"model": "prov/mod", "thinkingLevel": "high"}))
        self.assertEqual(value["finalAssistant"]["text"], "Final answer")
        self.assertEqual(value["baseline"]["kind"], "baseline")
        self.assertEqual((value["baseline"]["sessionId"], value["baseline"]["history"]["count"]), (SID, 0))
        self.assertEqual(posts, [("POST", "/api/sessions", {"cwd": "/work"}),
                                 ("POST", PREFIX + "/model", {"provider": "prov", "modelId": "mod"}),
                                 ("POST", PREFIX + "/thinking-level", {"level": "high"}),
                                 ("POST", PREFIX + "/prompt", {"text": self.PROMPT})])
        order = [(method, path) for method, path, _body in fixture.requests]
        self.assertLess(order.index(("GET", PREFIX + "/events")), order.index(("POST", PREFIX + "/prompt")))
        self.assertLess(max(index for index, request in enumerate(order) if request == ("POST", PREFIX + "/thinking-level")), order.index(("GET", PREFIX + "/events")))
        # The returned baseline is accepted by a later watch --since of the same session.
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "baseline.json"
            path.write_text(json.dumps(value["baseline"]))
            fixture.messages, fixture.status["messageCount"] = [], 0
            code, again, _ = self.invoke(fixture, "watch", SID, "--since", str(path), "--timeout", "0.5")
            self.assertNotEqual(again["reason"], "invalid_baseline")

    def test_run_setup_failures_report_the_step_and_send_no_prompt(self):
        cases = [({"spawn_fail": True}, "spawn", None, 500, 1), ({"model_fail": True}, "model", SID, 400, 2), ({"model_ignored": True, "model": "prov/other"}, "settings_check", SID, 200, 3)]
        for options, step, sid, status, posted in cases:
            with self.subTest(step=step):
                value, _, posts, _ = self.run_cli(**options)
                self.assertEqual((value["outcome"], value["failedStep"], value["sessionId"], value["error"]["status"]), ("setup_failed", step, sid, status))
                self.assertIsNone(value["baseline"] if step != "settings_check" else value["settings"])
                self.assertIsNone(value["finalAssistant"])
                self.assertLessEqual(len(value["error"]["detail"]), 500)
                self.assertEqual(len(posts), posted)
                self.assertFalse([post for post in posts if post[1].endswith("/prompt")])

    def test_run_invalid_input_never_touches_the_backend(self):
        for kwargs, reason in (({"stdin": "  \n"}, "empty_prompt"), ({"model": "nomodel"}, "invalid_input"), ({"thinking": " "}, "invalid_input")):
            with self.subTest(**kwargs):
                value, fixture, posts, _ = self.run_cli(**kwargs)
                self.assertEqual((value["outcome"], value["failedStep"], value["reason"]), ("setup_failed", None, reason))
                self.assertEqual(fixture.requests, [])
        fixture = Fixture()
        with fixture:
            code, value, _ = self.invoke(fixture, "run", "/work", "--model", "prov/mod", "--thinking", "high", "--timeout", "0", stdin=b"x")
            self.assertEqual((code, value["outcome"], value["reason"]), (1, "setup_failed", "invalid_input"))
            code, value, _ = self.invoke(fixture, "run", "/work", "--model", "prov/mod", "--thinking", "high", "--timeout", "2", stdin=b"\xff\xfe")
            self.assertEqual((code, value["outcome"], value["reason"], value["failedStep"]), (1, "setup_failed", "invalid_prompt", None))
            self.assertEqual(fixture.requests, [])

    def test_run_prompt_transport_errors_keep_watching(self):
        value, _, posts, _ = self.run_cli(prompt_drop=True)
        self.assertEqual(value["outcome"], "completed")
        self.assertIsNone(value["error"]["status"])
        self.assertEqual(len([post for post in posts if post[1].endswith("/prompt")]), 1)
        value, _, _, elapsed = self.run_cli(seconds=4, prompt_hang=6, settle_after=2.8, bound=4.65)
        self.assertEqual(value["outcome"], "completed")
        self.assertIsNone(value["error"]["status"])
        self.assertIn("timed out", value["error"]["detail"])
        self.assertGreater(elapsed, 2.7)

    def test_run_definite_prompt_rejection_is_setup_failed(self):
        value, _, _, _ = self.run_cli(prompt_reject=409)
        self.assertEqual((value["outcome"], value["failedStep"], value["sessionId"]), ("setup_failed", "prompt", SID))
        self.assertEqual(value["error"]["status"], 409)
        self.assertEqual(value["baseline"]["sessionId"], SID)

    def test_run_survives_slow_status_and_messages(self):
        for scenario in ("slow_status", "slow_messages"):
            with self.subTest(scenario=scenario):
                value, _, _, elapsed = self.run_cli(scenario, seconds=10, bound=10.65)
                self.assertEqual(value["outcome"], "completed", value)
                self.assertGreater(elapsed, 2.4)

    def test_run_deadline_keeps_session_and_baseline(self):
        value, _, _, elapsed = self.run_cli("bash", seconds=1.5)
        self.assertEqual((value["outcome"], value["reason"], value["failedStep"]), ("timeout", "deadline", None))
        self.assertEqual((value["sessionId"], value["settings"]["model"], value["baseline"]["sessionId"]), (SID, "prov/mod", SID))
        self.assertGreater(elapsed, 1.3)

    def test_run_deadline_before_the_socket_opens_is_a_subscribe_failure(self):
        value, _, posts, _ = self.run_cli("stalled_upgrade", seconds=1.5)
        self.assertEqual((value["outcome"], value["failedStep"], value["reason"], value["sessionId"]), ("setup_failed", "subscribe", "deadline", SID))
        self.assertFalse([post for post in posts if post[1].endswith("/prompt")])

    def test_run_oversized_output_keeps_identity(self):
        value, _, _, _ = self.run_cli("output_limit", seconds=2)
        self.assertEqual((value["outcome"], value["reason"], value["sessionId"]), ("unknown", "output_limit", SID))
        self.assertIsNone(value["candidateAssistant"])
        self.assertEqual(value["baseline"]["sessionId"], SID)

    def test_run_stalled_output_reader_cannot_keep_process_alive(self):
        with Fixture("blocked_output", run_mode=True) as fixture:
            started = time.monotonic()
            process = subprocess.Popen([str(CLI), "run", "/work", "--model", "prov/mod", "--thinking", "high", "--timeout", "1.5"], env=fixture.env,
                                       stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            try:
                process.stdin.write(b"go")
                process.stdin.close()
                self.assertEqual(process.wait(timeout=3), 1)
                self.assertLess(time.monotonic() - started, 2.2)
            finally:
                if process.poll() is None:
                    process.kill()
                process.wait()
                process.stdout.close()
                process.stderr.close()

    def test_existing_read_commands_keep_wrappers(self):
        with Fixture() as fixture:
            code, value, _ = self.invoke(fixture, "status", SID)
            self.assertEqual(code, 0)
            self.assertEqual(value, {"ok": True, "status": 200, "session": fixture.status})
            code, value, _ = self.invoke(fixture, "messages", SID)
            self.assertEqual((code, value), (0, {"ok": True, "status": 200, "result": []}))
            code, value, _ = self.invoke(fixture, "commands", SID)
            self.assertEqual((code, value), (0, {"ok": True, "status": 200, "commands": [{"name": "model"}]}))


if __name__ == "__main__":
    unittest.main(verbosity=2)

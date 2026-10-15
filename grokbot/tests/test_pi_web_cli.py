from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import threading
import time
import unittest


CLI = Path(__file__).resolve().parents[2] / "bin/pi-web-cli"
SID = "test-session"


def assistant(reason="stop", text="Finished.\n", error=""):
    return {"role": "assistant", "stopReason": reason, "errorMessage": error,
            "content": [{"type": "thinking", "thinking": "private reasoning"}, {"type": "text", "text": text}],
            "timestamp": 1234567890}


def idle():
    return {"sessionId": SID, "isStreaming": False, "isCompacting": False, "isBashRunning": False,
            "pendingMessageCount": 0, "messageCount": 2, "contextUsage": {"percent": 42.5}}


class FakeAPI:
    def __init__(self):
        self.status = idle()
        self.messages = [{"role": "user", "content": "work"}, assistant()]
        self.statuses = []
        self.status_code = 200
        self.message_code = 200
        self.message_override = None
        self.trickle = False
        self.trickle_headers = False
        self.requests = []
        self.posts = []
        self.responses = {}
        self.raw_response = None
        self.malformed_http = False
        self.lock = threading.Lock()

    @contextmanager
    def server(self):
        state = self

        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *_args):
                pass

            def do_GET(self):
                if state.malformed_http:
                    self.wfile.write(b"INVALID HTTP RESPONSE\r\n\r\n")
                    return
                with state.lock:
                    state.requests.append(self.path)
                    if ("GET", self.path) in state.responses:
                        code, data = state.responses["GET", self.path]
                    elif self.path.endswith("/status"):
                        data = state.statuses.pop(0) if state.statuses else state.status
                        code = state.status_code
                    else:
                        data = state.message_override if state.message_override is not None else {
                            "messages": deepcopy(state.messages), "start": 0, "total": len(state.messages),
                        }
                        code = state.message_code
                raw = state.raw_response if state.raw_response is not None else json.dumps(data).encode()
                try:
                    if state.trickle_headers:
                        for byte in b"HTTP/1.0 200 OK\r\nContent-Type: application/json\r\n\r\n":
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.025)
                        return
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    if code == 302:
                        self.send_header("Location", "/redirect-target")
                    self.end_headers()
                    if state.trickle:
                        for byte in raw:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.025)
                    else:
                        self.wfile.write(raw)
                except OSError:
                    pass

            def do_POST(self):
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                with state.lock:
                    state.posts.append((self.path, body))
                    code, data = state.responses.get(("POST", self.path), (200, {"accepted": True}))
                raw = json.dumps(data).encode()
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers()
                self.wfile.write(raw)

        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=2)


class CommandCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.api = FakeAPI()
        self.api_url = self.enterContext(self.api.server())
        self.env = {**os.environ, "PI_WEB_URL": self.api_url,
                    "PI_WEB_SESSIONS_DIR": str(self.root / "sessions")}

    def run_cli(self, *args, timeout=8):
        return subprocess.run([sys.executable, str(CLI), *args], env=self.env, capture_output=True, text=True, timeout=timeout)

    def wait(self, timeout="0.15"):
        return self.run_cli("wait", SID, "--timeout", timeout, "--poll-interval", "0.01")

    def header(self, cwd="/work/repo", sid=SID, kind="session", name="one"):
        folder = self.root / "sessions" / name
        folder.mkdir(parents=True)
        path = folder / f"2026_{SID}.jsonl"
        path.write_text(json.dumps({"type": kind, "id": sid, "cwd": cwd}) + "\n")
        return path


class CLIBehavior(CommandCase):
    def test_idle_json_and_verified_cwd(self):
        self.header()
        result = self.wait()
        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual({key: payload[key] for key in ("sid", "cwd", "event", "context_percent", "last_assistant_line")},
                         {"sid": SID, "cwd": "/work/repo", "event": "idle", "context_percent": 42.5, "last_assistant_line": "Finished."})
        self.assertEqual(payload["ok"], True)
        self.assertIsNotNone(datetime.fromisoformat(payload["ts"].replace("Z", "+00:00")).tzinfo)
        self.assertEqual(self.api.requests, [f"/api/sessions/{SID}/status", f"/api/sessions/{SID}/messages?limit=50", f"/api/sessions/{SID}/status"])

    def test_unknown_conflicting_or_unverified_cwd_is_null(self):
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path = self.header(sid="wrong")
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path.write_text(json.dumps({"type": "message", "id": SID, "cwd": "/wrong"}) + "\n")
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path.write_text(json.dumps({"type": "session", "id": SID, "cwd": "/first"}) + "\n")
        self.header(cwd="/second", name="two")
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])

    def test_cwd_metadata_rejects_unsafe_or_invalid_headers(self):
        path = self.header(cwd="relative")
        for raw in (path.read_text(), "not json\n", "x" * 8193):
            path.write_text(raw)
            self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path.unlink()
        os.mkfifo(path)
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path.unlink()
        target = self.root / "header.jsonl"
        target.write_text(json.dumps({"type": "session", "id": SID, "cwd": "/untrusted"}))
        path.symlink_to(target)
        self.assertIsNone(json.loads(self.wait().stdout)["cwd"])
        path.unlink()
        path.write_text(json.dumps({"type": "session", "id": SID, "cwd": "/verified"}) + "\n")
        self.assertEqual(json.loads(self.wait().stdout)["cwd"], "/verified")

    def test_each_busy_flag_and_queue_keeps_waiting(self):
        for field, value in (("isStreaming", True), ("isCompacting", True), ("isBashRunning", True), ("pendingMessageCount", 1)):
            with self.subTest(field=field):
                self.api.status = {**idle(), field: value}
                result = self.wait()
                self.assertEqual(result.returncode, 124, result.stdout + result.stderr)
                self.assertEqual(json.loads(result.stdout)["event"], "timeout")

    def test_busy_to_idle_and_reconciliation(self):
        busy = {**idle(), "isStreaming": True}
        self.api.statuses = [busy, idle()]
        result = self.wait("1")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["event"], "idle")
        self.assertEqual(len(self.api.requests), 6)

    def test_context_can_be_unknown(self):
        self.api.status.pop("contextUsage")
        self.assertIsNone(json.loads(self.wait().stdout)["context_percent"])
        self.api.status["contextUsage"] = {"percent": None}
        self.assertIsNone(json.loads(self.wait().stdout)["context_percent"])
        self.api.status["contextUsage"] = {"percent": 105.0}
        self.assertEqual(json.loads(self.wait().stdout)["context_percent"], 105.0)

    def test_error_and_abort_exit_three(self):
        for reason in ("error", "aborted"):
            self.api.messages = [assistant(reason, error="ordinary failure")]
            result = self.wait()
            self.assertEqual(result.returncode, 3)
            self.assertEqual(json.loads(result.stdout)["event"], "error")

    def test_busy_generic_error_is_not_terminal(self):
        self.api.status["isStreaming"] = True
        self.api.messages = [assistant("error", error="temporary network failure")]
        self.assertEqual(self.wait().returncode, 124)

    def test_usage_error_precedes_busy_and_uses_error_evidence_only(self):
        for error in ("You have hit your ChatGPT usage limit", "insufficient_quota", "GoUsageLimitError", "quota exceeded", "usage_not_included", "billing quota exhausted"):
            self.api.messages = [assistant("error", error=error)]
            self.api.status["isStreaming"] = True
            result = self.wait()
            self.assertEqual(result.returncode, 4, result.stdout)
            self.assertEqual(json.loads(result.stdout)["event"], "usage_limit")
        self.api.status = idle()
        self.api.messages = [assistant(text="Explain the usage limit and quota exceeded documentation.")]
        self.assertEqual(self.wait().returncode, 0)
        self.api.messages = [assistant("error", error="HTTP 429 too many requests")]
        self.assertEqual(self.wait().returncode, 3)

    def test_new_user_or_successful_retry_supersedes_old_error(self):
        old = assistant("error", error="usage limit reached")
        for messages in ([old, {"role": "user", "content": "new work"}], [old, assistant()]):
            self.api.messages = messages
            self.assertEqual(self.wait().returncode, 0)

    def test_quiescent_turns_are_idle_and_text_excludes_thinking(self):
        for reason in ("stop", "length", "toolUse"):
            self.api.messages = [assistant(reason, text="first\n\n" + "z" * 400 + "\n")]
            result = self.wait()
            self.assertEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["event"], "idle")
            self.assertEqual(payload["last_assistant_line"], "z" * 280)
        self.api.messages = []
        result = self.wait()
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["last_assistant_line"], "")

    def test_invalid_schema_and_wrong_sid_are_api_failures(self):
        cases = [[], {**idle(), "sessionId": "other"}, {**idle(), "isStreaming": 0},
                 {**idle(), "isBashRunning": None}, {**idle(), "pendingMessageCount": True},
                 {**idle(), "messageCount": -1}, {**idle(), "contextUsage": []},
                 {key: value for key, value in idle().items() if key != "isCompacting"},
                 {**idle(), "contextUsage": {"percent": float("nan")}},
                 {**idle(), "contextUsage": {"percent": 10 ** 500}}]
        for status in cases:
            with self.subTest(status=status):
                self.api.status = status
                result = self.wait()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertEqual(result.stderr, "")
        self.api.status = idle()
        for data in ([], {"messages": [], "start": False, "total": 0},
                     {"messages": [{**assistant(), "stopReason": []}], "start": 0, "total": 1}):
            self.api.message_override = data
            result = self.wait()
            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stderr, "")

    def test_invalid_assistant_content_and_page_are_api_failures(self):
        for message in (None, {**assistant(), "stopReason": "unknown"},
                        {**assistant(), "errorMessage": []}, {**assistant(), "content": "text"},
                        {**assistant(), "content": [{"type": "text", "text": 1}]},
                        {**assistant(), "timestamp": True}):
            with self.subTest(message=message):
                self.api.messages = [message]
                result = self.wait()
                self.assertEqual(result.returncode, 1)
                self.assertFalse(json.loads(result.stdout)["ok"])
                self.assertEqual(result.stderr, "")
        for page in ({"messages": [], "total": 0}, {"messages": [], "start": 0, "total": -1}):
            self.api.message_override = page
            self.assertEqual(self.wait().returncode, 1)

    def test_http_failure_and_independent_message_byte_cap(self):
        self.api.status_code = 404
        self.assertEqual(self.wait().returncode, 1)
        self.api.status_code = 200
        self.api.message_code = 503
        self.assertEqual(self.wait().returncode, 1)
        self.api.message_code = 200
        self.api.messages = [assistant(text="x" * (4 * 1024 * 1024 + 1))]
        result = self.wait("2")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "response_too_large")

    def test_status_byte_cap_is_independent(self):
        self.api.status["extra"] = "x" * 262144
        result = self.wait("2")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "response_too_large"})

    def test_hard_deadline_interrupts_trickled_response(self):
        self.api.trickle = True
        start = time.monotonic()
        result = self.wait("0.12")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertLess(time.monotonic() - start, 1)

    def test_hard_deadline_interrupts_trickled_headers(self):
        self.api.trickle_headers = True
        start = time.monotonic()
        result = self.wait("0.12")
        self.assertEqual(result.returncode, 124, result.stderr)
        self.assertEqual(json.loads(result.stdout)["event"], "timeout")
        self.assertLess(time.monotonic() - start, 1)

    def test_unavailable_transport_is_an_api_failure(self):
        self.env["PI_WEB_URL"] = "http://127.0.0.1:1"
        result = self.wait()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "api_unavailable_or_invalid"})
        self.assertEqual(result.stderr, "")

    def test_malformed_http_still_returns_json(self):
        self.api.malformed_http = True
        result = self.wait()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "api_unavailable_or_invalid"})
        self.assertEqual(result.stderr, "")

    def test_redirects_html_and_invalid_json_are_api_failures(self):
        self.api.status_code = 302
        result = self.wait()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.api.requests, [f"/api/sessions/{SID}/status"])
        self.api.status_code = 200
        for raw in (b"<!doctype html><html>not an API</html>", b"{broken json", b""):
            self.api.raw_response = raw
            result = self.wait()
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "api_unavailable_or_invalid"})

    def test_timeout_argument_validation(self):
        for value in ("0", "-1", "301", "nan", "inf", "nope"):
            result = self.run_cli("wait", SID, "--timeout", value)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(self.wait("300").returncode, 0)

    def test_wait_requires_timeout_valid_sid_and_finite_interval(self):
        self.assertEqual(self.run_cli("wait", SID).returncode, 2)
        for sid in ("../other", "", "x" * 129):
            self.assertEqual(self.run_cli("wait", sid, "--timeout", "1").returncode, 2)
        for value in ("0", "-1", "61", "nan", "inf", "nope"):
            self.assertEqual(self.run_cli("wait", SID, "--timeout", "1", "--poll-interval", value).returncode, 2)

    def test_existing_status_and_prompt_contracts_unchanged(self):
        result = self.run_cli("status", SID)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["session"], idle())
        result = self.run_cli("prompt", SID, "")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "empty prompt")

    def test_original_get_commands_remain_compatible(self):
        for args, path, data, field in (
            (("list", "--cwd", "/work/repo"), "/api/sessions?cwd=%2Fwork%2Frepo", [{"id": SID}], "sessions"),
            (("commands", SID), f"/api/sessions/{SID}/commands", [{"name": "compact"}], "commands"),
            (("messages", SID), f"/api/sessions/{SID}/messages", {"messages": []}, "result"),
        ):
            self.api.responses["GET", path] = (200, data)
            result = self.run_cli(*args)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(json.loads(result.stdout), {"ok": True, "status": 200, field: data})
            self.assertEqual(self.api.requests[-1], path)
        self.assertEqual(self.run_cli("list").returncode, 2)

    def test_original_post_commands_remain_compatible(self):
        cases = [
            (("spawn", "/work/repo"), "/api/sessions", {"cwd": "/work/repo"}, {"id": SID}, 201, "session"),
            (("prompt", SID, "work"), f"/api/sessions/{SID}/prompt", {"text": "work"}, {"accepted": True}, 200, "result"),
            (("prompt", SID, "fix", "--steer"), f"/api/sessions/{SID}/prompt", {"text": "fix", "streamingBehavior": "steer"}, {"accepted": True}, 200, "result"),
            (("prompt", SID, "next", "--follow-up"), f"/api/sessions/{SID}/prompt", {"text": "next", "streamingBehavior": "followUp"}, {"accepted": True}, 200, "result"),
            (("model", SID, "provider/model-id"), f"/api/sessions/{SID}/model", {"provider": "provider", "modelId": "model-id"}, {}, 200, "result"),
            (("thinking-level", SID, "high"), f"/api/sessions/{SID}/thinking-level", {"level": "high"}, {}, 200, "result"),
            (("answer", SID, "ask", "question", "answer text"), f"/api/sessions/{SID}/ask/submit", {"askId": "ask", "answers": [{"id": "question", "values": [], "otherText": "answer text"}]}, {}, 200, "result"),
        ]
        for verb, suffix in (("stop", "stop"), ("abort", "abort"), ("queue-clear", "queue/clear"), ("archive", "archive")):
            cases.append(((verb, SID), f"/api/sessions/{SID}/{suffix}", {}, {}, 200, "result"))
        for args, path, body, response, code, field in cases:
            with self.subTest(args=args):
                self.api.responses["POST", path] = (code, response)
                result = self.run_cli(*args)
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertEqual(self.api.posts[-1], (path, body))
                self.assertEqual(json.loads(result.stdout), {"ok": True, "status": code, field: response})
        result = self.run_cli("model", SID, "invalid")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout), {"ok": False, "error": "model must be provider/modelId"})

    def test_help_lists_only_original_commands_and_wait(self):
        result = self.run_cli("--help")
        self.assertEqual(result.returncode, 0)
        self.assertIn("{list,spawn,prompt,status,commands,wait,stop,abort,queue-clear,archive,messages,model,thinking-level,answer}", result.stdout)


if __name__ == "__main__":
    unittest.main()

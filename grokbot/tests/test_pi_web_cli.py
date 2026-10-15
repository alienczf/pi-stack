from contextlib import contextmanager
from copy import deepcopy
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import stat
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
        self.delay = 0
        self.requests = []
        self.posts = []
        self.codes = [204]
        self.location = None
        self.drop_response = False
        self.webhook_trickle = False
        self.response_body = b""
        self.malformed_http = False
        self.lock = threading.Lock()
        self.received = threading.Event()

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
                    is_status = self.path.endswith("/status")
                    if is_status:
                        data = state.statuses.pop(0) if state.statuses else state.status
                        code = state.status_code
                    else:
                        data = state.message_override if state.message_override is not None else {
                            "messages": deepcopy(state.messages), "start": 0, "total": len(state.messages),
                        }
                        code = state.message_code
                raw = json.dumps(data).encode()
                time.sleep(state.delay)
                try:
                    self.send_response(code)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(raw)))
                    self.end_headers()
                    if state.trickle:
                        for byte in raw:
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.025)
                    else:
                        self.wfile.write(raw)
                except (OSError, BrokenPipeError):
                    pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
                with state.lock:
                    state.posts.append((self.path, dict(self.headers), body))
                    code = state.codes.pop(0) if len(state.codes) > 1 else state.codes[0]
                state.received.set()
                if state.drop_response:
                    self.connection.close()
                    return
                try:
                    if state.webhook_trickle:
                        for byte in b"HTTP/1.0 204 No Content\r\n\r\n":
                            self.wfile.write(bytes([byte]))
                            self.wfile.flush()
                            time.sleep(0.1)
                        return
                    self.send_response(code)
                    if state.location:
                        self.send_header("Location", state.location)
                    self.send_header("Content-Length", str(len(state.response_body)))
                    self.end_headers()
                    self.wfile.write(state.response_body)
                except OSError:
                    pass

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
                    "PI_WEB_SESSIONS_DIR": str(self.root / "sessions"), "XDG_STATE_HOME": str(self.root / "state")}

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
        self.assertEqual(self.wait("1").returncode, 0)
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

    def test_invalid_schema_and_wrong_sid_are_api_failures(self):
        cases = [{**idle(), "sessionId": "other"}, {**idle(), "isStreaming": 0},
                 {**idle(), "pendingMessageCount": True}, {**idle(), "messageCount": -1},
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

    def test_http_failure_and_independent_message_byte_cap(self):
        self.api.status_code = 404
        self.assertEqual(self.wait().returncode, 1)
        self.api.status_code = 200
        self.api.message_code = 503
        self.assertEqual(self.wait().returncode, 1)
        self.api.message_code = 200
        self.api.messages = [assistant(text="x" * (4 * 1024 * 1024 + 1))]
        self.assertEqual(self.wait("2").returncode, 1)

    def test_hard_deadline_interrupts_trickled_response(self):
        self.api.trickle = True
        start = time.monotonic()
        result = self.wait("0.12")
        self.assertEqual(result.returncode, 124, result.stderr)
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

    def test_timeout_argument_validation(self):
        for value in ("0", "-1", "301", "nan", "inf", "nope"):
            result = self.run_cli("wait", SID, "--timeout", value)
            self.assertEqual(result.returncode, 2)
        self.assertEqual(self.wait("300").returncode, 0)

    def test_existing_status_and_prompt_contracts_unchanged(self):
        result = self.run_cli("status", SID)
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["session"], idle())
        result = self.run_cli("prompt", SID, "")
        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["error"], "empty prompt")


@unittest.skipUnless(shutil.which("systemd-run") and subprocess.run(
    ["systemctl", "--user", "show-environment"], capture_output=True).returncode == 0,
    "detached integration requires an active systemd user manager")
class NotifyBehavior(CommandCase):
    def setUp(self):
        super().setUp()
        self.hook = FakeAPI()
        self.hook_url = self.enterContext(self.hook.server()) + "/private-webhook-url"
        self.url_file = self.root / "webhook-url"
        self.key_file = self.root / "sender-key"
        self.key = "Bearer private-sender-key"
        self.url_file.write_text(self.hook_url + "\n")
        self.key_file.write_text(self.key + "\n")
        self.url_file.chmod(0o600)
        self.key_file.chmod(0o600)
        self.units = []
        self.addCleanup(self.stop_units)

    def stop_units(self):
        for unit in self.units:
            subprocess.run(["systemctl", "--user", "stop", unit], capture_output=True)
            subprocess.run(["systemctl", "--user", "reset-failed", unit], capture_output=True)

    def notify(self, *extra):
        result = self.run_cli("notify", SID, "--webhook-url-file", str(self.url_file),
                              "--key-file", str(self.key_file), "--watch-timeout", "3",
                              "--delivery-timeout", "20", "--poll-interval", "0.02", *extra)
        if result.returncode == 0:
            self.units.append(json.loads(result.stdout)["unit"])
        return result

    def finished(self, result, marker, timeout=6):
        info = json.loads(result.stdout)
        log = Path(info["log_file"])
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            text = log.read_text()
            if marker in text:
                break
            time.sleep(0.025)
        else:
            self.fail(f"missing log outcome {marker!r}: {log.read_text()}")
        while time.monotonic() < deadline:
            state = subprocess.run(["systemctl", "--user", "show", info["unit"], "--property=ActiveState", "--value"], capture_output=True, text=True)
            if state.stdout.strip() not in {"active", "activating", "deactivating"}:
                break
            time.sleep(0.025)
        else:
            self.fail("detached watcher did not exit")
        output = result.stdout + result.stderr + log.read_text()
        self.assertNotIn(self.key, output)
        self.assertNotIn(self.hook_url, output)
        self.assertNotIn("Finished.", log.read_text())
        self.assertEqual(stat.S_IMODE(log.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(log.parent.stat().st_mode), 0o700)
        return log.read_text()

    def test_real_detach_survives_launcher_and_private_argv(self):
        self.api.status["isStreaming"] = True
        result = self.notify("--once", "--header-name", "X-Sender-Key")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        info = json.loads(result.stdout)
        pid = subprocess.check_output(["systemctl", "--user", "show", info["unit"], "--property=MainPID", "--value"], text=True).strip()
        argv = Path(f"/proc/{pid}/cmdline").read_bytes().decode().replace("\x00", " ")
        self.assertNotIn(self.key, argv)
        self.assertNotIn(self.hook_url, argv)
        self.assertIn(str(self.key_file), argv)
        self.assertFalse(self.hook.received.is_set())
        self.api.status = idle()
        self.assertTrue(self.hook.received.wait(3))
        self.finished(result, "delivered")
        self.assertEqual(len(self.hook.posts), 1)
        path, headers, raw = self.hook.posts[0]
        self.assertEqual(path, "/private-webhook-url")
        self.assertEqual(headers["X-Sender-Key"], self.key)
        self.assertEqual(json.loads(raw)["event"], "done")

    def test_cancel_stops_the_detached_watcher(self):
        self.api.status["isStreaming"] = True
        result = self.notify()
        self.assertEqual(result.returncode, 0)
        info = json.loads(result.stdout)
        stopped = subprocess.run(["systemctl", "--user", "stop", info["unit"]], capture_output=True)
        self.assertEqual(stopped.returncode, 0)
        state = subprocess.run(["systemctl", "--user", "show", info["unit"], "--property=ActiveState", "--value"], capture_output=True, text=True)
        self.assertNotIn(state.stdout.strip(), {"active", "activating", "deactivating"})
        self.assertEqual(self.hook.posts, [])

    def test_initial_done_payload_is_small_and_done_beats_idle(self):
        self.header()
        self.api.messages = [assistant(text="first\n" + "z" * 400 + "\n")]
        result = self.notify()
        self.assertEqual(result.returncode, 0, result.stdout)
        self.finished(result, "delivered")
        raw = self.hook.posts[0][2]
        payload = json.loads(raw)
        self.assertEqual(set(payload), {"sid", "cwd", "event", "context_percent", "last_assistant_line", "ts"})
        self.assertEqual(payload["event"], "done")
        self.assertEqual(payload["cwd"], "/work/repo")
        self.assertEqual(payload["last_assistant_line"], "z" * 280)
        self.assertLess(len(raw), 1024)

    def test_done_requires_stop_and_idle_selection(self):
        for reason in ("length", "toolUse"):
            self.api.messages = [assistant(reason)]
            result = self.notify("--events", "done", "--watch-timeout", "0.15")
            self.finished(result, "watch_timeout")
            self.assertEqual(self.hook.posts, [])
        self.api.messages = []
        result = self.notify("--events", "idle")
        self.finished(result, "delivered")
        self.assertEqual(json.loads(self.hook.posts[0][2])["event"], "idle")

    def test_retry_429_and_server_error_uses_identical_payload(self):
        self.hook.codes = [429, 503, 204]
        result = self.notify()
        log = self.finished(result, "delivered", timeout=7)
        self.assertEqual(len(self.hook.posts), 3)
        self.assertEqual(self.hook.posts[0][2], self.hook.posts[1][2])
        self.assertEqual(self.hook.posts[1][2], self.hook.posts[2][2])
        self.assertIn("delivery_attempt_3", log)

    def test_five_attempts_then_exit(self):
        self.hook.codes = [500]
        result = self.notify()
        self.finished(result, "delivery_exhausted", timeout=19)
        self.assertEqual(len(self.hook.posts), 5)
        self.assertEqual(len({post[2] for post in self.hook.posts}), 1)

    def test_transport_failure_retries_and_deadline_bounds_delivery(self):
        self.hook.drop_response = True
        result = self.notify("--delivery-timeout", "1.5")
        self.finished(result, "delivery_timeout", timeout=4)
        self.assertEqual(len(self.hook.posts), 2)
        self.assertEqual(self.hook.posts[0][2], self.hook.posts[1][2])

    def test_delivery_hard_deadline_interrupts_trickled_headers(self):
        self.hook.webhook_trickle = True
        result = self.notify("--delivery-timeout", "0.2")
        self.finished(result, "delivery_timeout", timeout=2)
        self.assertEqual(len(self.hook.posts), 1)

    def test_redirect_and_permanent_4xx_do_not_retry_or_forward(self):
        target = FakeAPI()
        url = self.enterContext(target.server()) + "/redirect-target"
        self.hook.location = url
        self.hook.response_body = (self.key + " " + self.hook_url).encode()
        for code in (302, 401):
            self.hook.posts.clear()
            self.hook.codes = [code]
            result = self.notify()
            self.finished(result, f"delivery_rejected_http_{code}")
            self.assertEqual(len(self.hook.posts), 1)
            self.assertEqual(target.posts, [])
            self.assertEqual(target.requests, [])

    def test_usage_limit_and_error_notifications(self):
        for error, event in (("usage_limit_reached", "usage_limit"), ("ordinary failure", "error")):
            self.hook.posts.clear()
            self.api.messages = [assistant("error", error=error)]
            result = self.notify()
            self.finished(result, "delivered")
            self.assertEqual(json.loads(self.hook.posts[0][2])["event"], event)
        self.api.status["isStreaming"] = True
        self.api.messages = [assistant("error", error="usage limit reached")]
        self.hook.posts.clear()
        result = self.notify("--events", "done")
        self.finished(result, "terminal_event_not_selected")
        self.assertEqual(self.hook.posts, [])

    def test_api_failure_is_not_completion(self):
        self.api.status_code = 503
        self.api.status = {"error": self.key + " " + self.hook_url}
        result = self.notify()
        self.finished(result, "watch_failed")
        self.assertEqual(self.hook.posts, [])

    def test_private_file_modes_symlinks_fifo_oversize_and_multiline(self):
        for field in (self.url_file, self.key_file):
            original = field.read_text()
            for mode in (0o644, 0o400, 0o660, 0o1600):
                field.chmod(mode)
                result = self.notify()
                self.assertEqual(result.returncode, 1)
                self.assertNotIn(self.key, result.stdout + result.stderr)
                self.assertNotIn(self.hook_url, result.stdout + result.stderr)
            field.chmod(0o600)
            field.write_text(original + "second line\n")
            self.assertEqual(self.notify().returncode, 1)
            field.write_text("x" * 8193)
            self.assertEqual(self.notify().returncode, 1)
            field.unlink()
            os.mkfifo(field, 0o600)
            self.assertEqual(self.notify().returncode, 1)
            field.unlink()
            target = field.with_suffix(".real")
            target.write_text(original)
            target.chmod(0o600)
            field.symlink_to(target)
            self.assertEqual(self.notify().returncode, 1)
            field.unlink()
            field.write_text(original)
            field.chmod(0o600)
        self.assertEqual(self.hook.posts, [])
        result = self.notify()
        self.finished(result, "delivered")
        self.assertEqual(len(self.hook.posts), 1)

    def test_header_url_and_event_validation(self):
        for header in ("Content-Length", "HOST", "Transfer-Encoding", "X-Bad\r\nAuthorization", ""):
            self.assertEqual(self.notify("--header-name", header).returncode, 2)
        for events in ("done,bogus", "", "Idle"):
            self.assertEqual(self.notify("--events", events).returncode, 2)
        original = self.url_file.read_text()
        for url in ("http://public.example/hook", "file:///tmp/hook", "https://user:pass@example.test", "https://example.test/#fragment"):
            self.url_file.write_text(url)
            self.assertEqual(self.notify().returncode, 1)
        self.url_file.write_text(original)
        self.key_file.write_text("RawSenderKey")
        result = self.notify("--header-name", "X-Routine-Key")
        self.finished(result, "delivered")
        self.assertEqual(self.hook.posts[0][1]["X-Routine-Key"], "RawSenderKey")


if __name__ == "__main__":
    unittest.main()

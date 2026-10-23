"""New stream admission, exact freshness, stale and best-effort abort behavior."""
from dataclasses import replace
from unittest.mock import patch
from uuid import uuid4

from prime_support import PrimeCase, state
from engine import StreamsError
from engine.prime import PrimeClient, send_stream_message, stop_session
from stub_prime import StubPrime


class MessageTests(PrimeCase):
    def test_original_and_fresh_files_exist_before_first_prompt_write(self):
        text = '原文\r\n```\n{stream_id_json}\n'
        observed = []
        def handler(stub, request):
            if request["command"]["type"] == "prompt_and_wait":
                current = state.check_state(self.stream)
                self.assertEqual(current.goals.work[0].required, None)
                original = state._entries(self.stream, current)[current.goals.work[0].original_entry]
                self.assertEqual(original.body["text"], text)
                observed.append(request["command"]["message"])
                self.assertIn(state._json(current.text), observed[-1])
                self.assertIn(current.sha256, observed[-1])
            return self.handler(stub, request)
        with StubPrime(handler) as stub, PrimeClient(stub.path) as client:
            result = send_stream_message(client, self.stream, self.identity, body=text, sender="operator", lane="steer")
        self.assertEqual(result["sending_status"], "Prime replied")
        self.assertEqual(stub.requests[1]["command"]["streamingBehavior"], "steer")
        self.assertEqual(len(observed), 1)
        self.assertEqual(len(state.check_state(self.stream).goals.work), 1)

    def test_save_failure_and_attachments_produce_no_native_commands(self):
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            with patch.object(state, "save_message", side_effect=StreamsError("disk failed")):
                with self.assertRaisesRegex(StreamsError, "disk failed"):
                    send_stream_message(client, self.stream, self.identity, body="request")
            with self.assertRaisesRegex(StreamsError, "attachments"):
                send_stream_message(client, self.stream, self.identity, body="request", attachments=["image"])
        self.assertEqual(stub.requests, [])
        self.assertEqual(state.check_state(self.stream).goals.status, "unset")

    def test_duplicate_unknown_send_is_not_replayed(self):
        command = str(uuid4())
        with StubPrime(lambda s, r: self.handler(s, r) if r["command"]["type"] != "prompt_and_wait" else None) as stub, PrimeClient(stub.path, timeout=.05) as client:
            with self.assertRaises(TimeoutError):
                send_stream_message(client, self.stream, self.identity, body="once", command_id=command)
            result = send_stream_message(client, self.stream, self.identity, body="once", command_id=command)
        self.assertEqual(result["sending_status"], "unknown after connection loss")
        self.assertEqual([r["command"]["type"] for r in stub.requests].count("prompt_and_wait"), 1)

    def test_stale_goal_refused_but_log_only_change_is_tolerated(self):
        self.active()
        before = state.check_state(self.stream)
        state.append_log(self.stream, subject="Unrelated", body={"finding": "kept"})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            result = send_stream_message(client, self.stream, self.identity, body="advance", mode="automatic", expected=before.goals_rules_sha256)
            current = state.check_state(self.stream)
            state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="paused"), rules=None,
                entry={"subject": "Stop", "body": {}, "original_entries": []})
            with self.assertRaises(StreamsError):
                send_stream_message(client, self.stream, self.identity, body="stale", mode="automatic", expected=before.goals_rules_sha256)
        self.assertEqual(result["frame"]["success"], True)
        self.assertEqual([r["command"]["type"] for r in stub.requests].count("prompt_and_wait"), 1)

    def test_stop_success_failure_and_timeout_never_guarantee_termination(self):
        self.active()
        for outcome in ("success", "failure", "timeout"):
            def handler(stub, request):
                if request["command"]["type"] == "abort":
                    if outcome == "timeout":
                        return None
                    return stub.response(request) if outcome == "success" else stub.response(request, success=False, error="abort refused")
                return self.handler(stub, request)
            with StubPrime(handler) as stub, PrimeClient(stub.path, timeout=.05) as client:
                result = stop_session(client, self.stream, self.identity, sender="operator")
            self.assertEqual(result["termination_guaranteed"], False)
            self.assertEqual(stub.requests[0]["command"]["type"], "abort")
            self.assertEqual(state.check_state(self.stream).goals.status, "paused")
            if outcome == "timeout":
                self.assertEqual(result["result"], "unknown")
            else:
                self.assertEqual(result["frame"]["success"], outcome == "success")

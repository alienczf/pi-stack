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
        prompts = [r["command"] for r in stub.requests if r["command"]["type"] == "prompt_and_wait"]
        self.assertEqual(prompts[0]["streamingBehavior"], "steer")
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

    def test_human_steer_can_arrive_while_a_known_prompt_is_pending(self):
        with StubPrime(lambda s, r: self.handler(s, r) if r["command"]["type"] != "prompt_and_wait" else None) as stub, PrimeClient(stub.path) as client:
            first = send_stream_message(client, self.stream, self.identity, body="initial finite ask", wait_result=False)
            second = send_stream_message(client, self.stream, self.identity, body="new steer while busy", lane="steer", wait_result=False)
        prompts = [r["command"] for r in stub.requests if r["command"]["type"] == "prompt_and_wait"]
        self.assertEqual(len(prompts), 2)
        self.assertEqual(prompts[-1]["streamingBehavior"], "steer")
        self.assertIn("new steer while busy", prompts[-1]["message"])

    def test_usage_failure_is_retained_and_stops_before_more_native_queries(self):
        from engine.prime import UsageQuotaError
        def handler(stub, request):
            if request["command"]["type"] == "prompt_and_wait":
                return stub.response(request, success=False, error="fixture usage limit", errorInfo={"code": "usage_limit"})
            return self.handler(stub, request)
        with StubPrime(handler) as stub, PrimeClient(stub.path) as client:
            with self.assertRaises(UsageQuotaError):
                send_stream_message(client, self.stream, self.identity, body="finite fixture")
        commands = [r["command"]["type"] for r in stub.requests]
        self.assertEqual(commands[-1], "prompt_and_wait")
        current = state.check_state(self.stream)
        reply = next(e for e in current.log if "sent_text_sha256" in e.body)
        self.assertEqual(reply.body["error"], "fixture usage limit")
        self.assertEqual(reply.body["messages"], [])

    def test_worker_stop_pauses_only_its_assignment_not_independent_stream_work(self):
        from engine.prime import SessionIdentity, eligible, stream_entries
        self.active()
        self.active()
        current = state.check_state(self.stream)
        assigned = replace(current.goals.work[0], workers=({"session": "worker-durable", "worktree": "/assigned/product", "work": "dependent part"},))
        independent = current.goals.work[1]
        state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, work=(assigned, independent)), rules=None,
            entry={"subject": "Worker assignment", "body": {}, "original_entries": [assigned.original_entry]})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            result = stop_session(client, self.stream, SessionIdentity("worker-durable", "worker-routing"), sender="operator")
        after, entries = stream_entries(self.stream)
        self.assertEqual(after.goals.status, "active")
        self.assertEqual(after.goals.work[1], independent)
        self.assertEqual(after.goals.work[0].waiting_for, "stopped worker worker-durable")
        self.assertEqual(eligible(after, entries), True)
        self.assertEqual(stub.requests[0]["command"], {"type": "abort", "activeSessionId": "worker-routing"})
        self.assertEqual(result["termination_guaranteed"], False)

    def test_stream_stop_without_an_objective_still_pauses_maintenance(self):
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            result = stop_session(client, self.stream, self.identity, sender="operator")
        current = state.check_state(self.stream)
        self.assertEqual(current.goals.objective, None)
        self.assertEqual(current.goals.status, "paused")
        self.assertEqual(result["termination_guaranteed"], False)
        self.assertEqual(stub.requests[0]["command"]["type"], "abort")

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

"""New event-free Prime wake uses existing tick observations and stream Log."""
from dataclasses import replace
from uuid import uuid4
from prime_support import PrimeCase, state
from engine.prime import PrimeClient
from engine.tick import wake_prime_if_needed
from stub_prime import StubPrime


class PrimeTickTests(PrimeCase):
    def test_event_free_wake_once_and_independent_work_eligible(self):
        self.active()
        self.active()
        current = state.check_state(self.stream)
        goals = replace(current.goals, work=(current.goals.work[0], replace(current.goals.work[1], waiting_for="worker-1")))
        state.update_state(self.stream, expect=current.sha256, goals=goals, rules=None, entry={"subject": "Worker wait", "body": {}, "original_entries": []})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            first = wake_prime_if_needed(client, self.stream, self.identity)
            second = wake_prime_if_needed(client, self.stream, self.identity)
        self.assertEqual(first["frame"]["success"], True)
        self.assertEqual(second, None)
        self.assertEqual([r["command"]["type"] for r in stub.requests].count("prompt_and_wait"), 1)

    def test_assigned_busy_clean_worker_blocks_only_its_dependent_goal(self):
        self.active()
        current = state.check_state(self.stream)
        assigned = replace(current.goals.work[0], workers=({"session": "worker-durable", "worktree": "/assigned/product", "work": "dependent work"},), waiting_for=None)
        state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, work=(assigned,)), rules=None,
                           entry={"subject": "Assignment", "body": {}, "original_entries": [assigned.original_entry]})
        def handler(stub, request):
            if request["command"]["type"] == "get_connection_state" and request["command"].get("activeSessionId") == "worker-durable":
                return stub.response(request, {"sessionId": "worker-durable", "activeSessionId": "worker-routing", "cwd": "/assigned/product", "isStreaming": True, "isCompacting": False, "isBashRunning": False})
            return self.handler(stub, request)
        with StubPrime(handler) as stub, PrimeClient(stub.path) as client:
            self.assertEqual(wake_prime_if_needed(client, self.stream, self.identity), None)
            self.assertEqual([r for r in stub.requests if r["command"]["type"] == "prompt_and_wait"], [])
            self.active()
            result = wake_prime_if_needed(client, self.stream, self.identity)
            self.assertEqual(result["frame"]["success"], True)
        self.assertEqual([r["command"]["type"] for r in stub.requests].count("prompt_and_wait"), 1)
        self.assertTrue(any(r["command"].get("activeSessionId") == "worker-durable" for r in stub.requests))
        self.assertEqual(state.check_state(self.stream).goals.work[0].workers, assigned.workers)

    def test_idle_worker_needs_a_captured_result_before_dependent_review_wake(self):
        from engine.prime import save_reply
        source = self.active()
        current = state.check_state(self.stream)
        work = replace(current.goals.work[0], workers=({"session": "worker-durable", "worktree": "/assigned/product", "work": "dependent work"},), waiting_for="worker-durable")
        state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="waiting", work=(work,)), rules=None,
                           entry={"subject": "Waiting for worker", "body": {}, "original_entries": [source]})
        command = str(uuid4())
        handover = "Exact clean worker handover"
        state.append_log(self.stream, subject="Worker kickoff", session_id="worker-durable", command_id=command,
            purpose="worker-before-send", body={"handover": handover, "original_entries": [source], "result": "unknown until reply saved"})
        children = {"busy": True}
        def handler(stub, request):
            if request["command"]["type"] == "get_connection_state" and request["command"].get("activeSessionId") == "worker-durable":
                return stub.response(request, {"sessionId": "worker-durable", "activeSessionId": "worker-routing", "cwd": "/assigned/product", "isStreaming": False, "isCompacting": False, "isBashRunning": False})
            if request["command"]["type"] == "get_state" and request["command"].get("activeSessionId") == "worker-routing":
                return stub.response(request, {"hasRunningSubagents": children["busy"]})
            return self.handler(stub, request)
        with StubPrime(handler) as stub, PrimeClient(stub.path) as client:
            self.assertEqual(wake_prime_if_needed(client, self.stream, self.identity), None)
            save_reply(self.stream, session_id="worker-durable", command_id=command, sent_text=handover,
                       frame={"command": "prompt_and_wait", "success": True, "data": {"summary": "Reported result, not task completion"}}, messages=[])
            self.assertEqual(wake_prime_if_needed(client, self.stream, self.identity), None)
            children["busy"] = False
            result = wake_prime_if_needed(client, self.stream, self.identity)
            self.assertEqual(result["frame"]["success"], True)
        self.assertEqual([r["command"]["type"] for r in stub.requests].count("prompt_and_wait"), 1)
        self.assertEqual(state.check_state(self.stream).goals.work[0].original_entry, source)
        self.assertEqual(state.check_state(self.stream).goals.work[0].waiting_for, "worker-durable")

    def test_unread_and_real_wait_produce_no_wake(self):
        self.active()
        current = state.check_state(self.stream)
        state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="waiting"), rules=None,
                           entry={"subject": "Human wait", "body": {}, "original_entries": []})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.assertEqual(wake_prime_if_needed(client, self.stream, self.identity), None)
        self.assertEqual([r["command"]["type"] for r in stub.requests], ["get_connection_state"])
        self.assertEqual(state.check_state(self.stream).goals.status, "waiting")

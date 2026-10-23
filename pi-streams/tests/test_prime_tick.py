"""New event-free Prime wake uses existing tick observations and stream Log."""
from dataclasses import replace
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

    def test_unread_and_real_wait_produce_no_wake(self):
        self.active()
        current = state.check_state(self.stream)
        state.update_state(self.stream, expect=current.sha256, goals=replace(current.goals, status="waiting"), rules=None,
                           entry={"subject": "Human wait", "body": {}, "original_entries": []})
        with StubPrime(self.handler) as stub, PrimeClient(stub.path) as client:
            self.assertEqual(wake_prime_if_needed(client, self.stream, self.identity), None)
        self.assertEqual([r["command"]["type"] for r in stub.requests], ["get_connection_state"])
        self.assertEqual(state.check_state(self.stream).goals.status, "waiting")

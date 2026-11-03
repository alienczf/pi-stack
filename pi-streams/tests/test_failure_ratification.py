from __future__ import annotations

from tick_support import TickCase


class KickoffOnlyRatificationTests(TickCase):
    def test_runtime_ratify_command_is_removed(self):
        result = self.run_streams("failure", "ratify", "etl", "--session", "coi", "--episode", "old")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("invalid choice", result.stderr)
        self.assertFalse(self.stub.requests)

    def test_runtime_ratify_api_is_removed(self):
        from engine import failure
        self.assertFalse(hasattr(failure, "ratify_locked"))

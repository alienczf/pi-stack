from __future__ import annotations

from tick_support import TickCase, got_list, got_status, row, status


class ObservationAdmissionTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.stream = self.make_stream(
            self.home, "etl",
            row("coord-1", "coordinator", str(self.home / "etl"))
            + row("t-1", "worker", "/wt/worker"),
        )
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)),
        ])

    def test_legacy_passive_tick_observes_without_recovery_admission(self) -> None:
        config = self.stream / "stream.toml"
        config.write_text(config.read_text().replace("state_schema = 1\n", "", 1))
        result = self.tick("2026-11-06T16:00:00Z")
        self.assertEqual((result.returncode, result.stdout, result.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [
            got_list(str(self.stream)),
            got_status("coord-1"),
            got_status("t-1"),
            got_list("/wt/worker"),
        ])
        self.assertEqual(self.state(self.stream)["sessions"]["t-1"]["busy"], True)

    def test_explicit_recovery_still_validates_state_before_native_effects(self) -> None:
        state = self.stream / "STATE.md"
        state.write_text(state.read_text().replace("## Rules\n", "", 1))
        self.stub.requests.clear()
        result = self.run_streams("resume", "etl", "--all-parked")
        self.assertEqual(result.returncode, 1)
        self.assertIn("STATE requires one Goals, Rules, and Log section", result.stderr)
        self.assertEqual(self.stub.requests, [])

"""tick fires a subscription when its source changes after the first reading."""
from __future__ import annotations

import unittest

from tick_support import PROMPTS, TickCase, got_list, got_prompt, got_status, info, row, status

DAILY = "daily\tschedule\t\t09:00\tPost the daily status to ZF."


class ScheduleTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.etl = self.make_stream(self.home, "etl", row("coord-1", "coordinator", str((self.home / "etl").resolve())))
        self.stub.set_routes([
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1", streaming=True)),
            ("GET", "/api/sessions", 200, [info("coord-1", str(self.etl), self.log_path("coord-1"))]),
            PROMPTS,
        ])

    def test_a_schedule_fires_once_a_day_at_the_first_tick_at_or_after_its_time(self) -> None:
        self.subscribe(self.etl, DAILY)
        first = self.tick("2026-10-06T08:55:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "", ""))
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "daily": {"fingerprint": "2026-10-05", "watch": ["schedule", "", "09:00"]},
        })

        due = self.tick("2026-10-06T09:00:00Z")
        self.assertEqual((due.returncode, due.stdout, due.stderr), (0, f"{self.etl}\tsubscription=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt(
                "coord-1",
                "pi-streams tick 2026-10-06T09:00:00Z:\nsubscription daily: Post the daily status to ZF.",
                "followUp",
            ),
        ])

        for at in ("2026-10-06T09:05:00Z", "2026-10-07T08:59:59Z"):
            quiet = self.tick(at)
            self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))
            self.assertEqual(self.stub.requests, [got_list(str(self.etl))])

        next_day = self.tick("2026-10-07T09:03:00Z")
        self.assertEqual((next_day.returncode, next_day.stdout), (0, f"{self.etl}\tsubscription=1\n"))
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T09:00:00Z", "kind": "subscription", "session": "", "role": "", '
            '"detail": "daily: Post the daily status to ZF."}\n'
            '{"at": "2026-10-07T09:03:00Z", "kind": "subscription", "session": "", "role": "", '
            '"detail": "daily: Post the daily status to ZF."}\n',
        )

    def test_a_schedule_first_read_after_its_time_waits_for_the_next_day(self) -> None:
        self.subscribe(self.etl, DAILY)
        for at in ("2026-10-06T10:00:00Z", "2026-10-06T23:59:00Z"):
            quiet = self.tick(at)
            self.assertEqual((quiet.returncode, quiet.stdout), (0, ""))
        due = self.tick("2026-10-07T09:00:00Z")
        self.assertEqual((due.returncode, due.stdout), (0, f"{self.etl}\tsubscription=1\n"))

    def test_an_edited_row_takes_a_new_reading_before_it_can_fire(self) -> None:
        self.subscribe(self.etl, DAILY)
        self.assertEqual(self.tick("2026-10-06T10:00:00Z").stdout, "")
        self.subscribe(self.etl, "daily\tschedule\t\t18:00\tPost the daily status to ZF.")
        moved = self.tick("2026-10-06T10:05:00Z")
        self.assertEqual((moved.returncode, moved.stdout), (0, ""))
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "daily": {"fingerprint": "2026-10-05", "watch": ["schedule", "", "18:00"]},
        })
        evening = self.tick("2026-10-06T18:00:00Z")
        self.assertEqual((evening.returncode, evening.stdout), (0, f"{self.etl}\tsubscription=1\n"))

    def test_an_unknown_source_or_a_failing_one_is_a_tick_error_naming_the_row(self) -> None:
        self.subscribe(
            self.etl,
            "issue\tgh-issue\towner/repo#1\t\tLook at the issue.",
            "late\tschedule\t\t9am\tPing ZF.",
            DAILY,
        )
        proc = self.tick("2026-10-06T08:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (
            1,
            f"{self.etl}\ttick-error=2\n",
            f"{self.etl}: subscription issue: unknown source gh-issue\n"
            f"{self.etl}: subscription late: when is not HH:MM: 9am\n",
        ))
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T08:00:00Z", "kind": "tick-error", "session": "", "role": "", '
            '"detail": "subscription issue: unknown source gh-issue"}\n'
            '{"at": "2026-10-06T08:00:00Z", "kind": "tick-error", "session": "", "role": "", '
            '"detail": "subscription late: when is not HH:MM: 9am"}\n',
        )
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "daily": {"fingerprint": "2026-10-05", "watch": ["schedule", "", "09:00"]},
        })

        due = self.tick("2026-10-06T09:00:00Z")
        self.assertEqual((due.returncode, due.stdout), (1, f"{self.etl}\tsubscription=1\ttick-error=2\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            "pi-streams tick 2026-10-06T09:00:00Z:\nsubscription daily: Post the daily status to ZF.",
            "followUp",
        ))


if __name__ == "__main__":
    unittest.main()

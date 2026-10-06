"""tick resends a message that has waited in a thread's queue as a steer."""
from __future__ import annotations

import unittest

from tick_support import PROMPTS, TickCase, got_list, got_post, got_prompt, got_status, info, row, status

BARS = "Use the 1m bars."
RERUN = "Then rerun checks/datapull.sh."


class SteerTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        etl = str((self.home / "etl").resolve())
        self.etl = self.make_stream(
            self.home,
            "etl",
            row("coord-1", "coordinator", etl) + row("t-1", "datapull", "/wt/datapull"),
        )

    def thread(self, *queued: tuple[str, str]) -> list[tuple]:
        return [
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, queued=queued)),
            ("POST", "/api/sessions/t-1/queue/clear", 200, status("t-1", streaming=True)),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1")),
            ("GET", "/api/sessions", 200, [
                info("coord-1", str(self.etl), self.log_path("coord-1")),
                info("t-1", "/wt/datapull", self.log_path("t-1")),
            ]),
            PROMPTS,
        ]

    def test_a_message_queued_for_ten_minutes_is_resent_as_a_steer(self) -> None:
        self.stub.set_routes(self.thread(("followUp", BARS)))
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout), (0, ""))

        self.stub.set_routes(self.thread(("followUp", BARS), ("followUp", RERUN)))
        early = self.tick("2026-10-06T12:09:59Z")
        self.assertEqual((early.returncode, early.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["queued"], {
            BARS: "2026-10-06T12:00:00Z",
            RERUN: "2026-10-06T12:09:59Z",
        })

        due = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((due.returncode, due.stdout, due.stderr), (0, f"{self.etl}\tstale-steer=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_post("t-1", "queue/clear"),
            got_prompt("t-1", BARS, "steer"),
            got_prompt("t-1", RERUN, "followUp"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt("coord-1", f"pi-streams tick 2026-10-06T12:10:00Z:\nstale-steer t-1 datapull {BARS}"),
        ])
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:10:00Z", "kind": "stale-steer", "session": "t-1", "role": "datapull", '
            f'"detail": "{BARS}"}}\n',
        )
        self.assertEqual(self.state(self.etl), {
            "claims": [],
            "outages": [],
            "pending": [],
            "rotating": False,
            "subscriptions": {},
            "sessions": {"t-1": {"asks": [], "busy": True, "context": False, "queued": {
                BARS: "2026-10-06T12:10:00Z",
                RERUN: "2026-10-06T12:09:59Z",
            }, "replay": []}},
        })

    def test_a_steer_that_still_waits_is_left_alone(self) -> None:
        self.stub.set_routes(self.thread(("steer", BARS)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        late = self.tick("2026-10-06T12:30:00Z")
        self.assertEqual((late.returncode, late.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["queued"], {BARS: "2026-10-06T12:00:00Z"})

    def test_every_copy_of_a_repeated_message_is_resent(self) -> None:
        self.stub.set_routes(self.thread(("followUp", BARS), ("followUp", BARS)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        due = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((due.returncode, due.stdout), (0, f"{self.etl}\tstale-steer=1\n"))
        self.assertEqual(self.stub.requests[:5], [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_post("t-1", "queue/clear"),
            got_prompt("t-1", BARS, "steer"),
            got_prompt("t-1", BARS, "steer"),
        ])

    def test_a_resend_that_fails_after_the_clear_is_finished_on_the_next_tick(self) -> None:
        self.stub.set_routes(self.thread(("followUp", BARS)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        refused = ("POST", "/api/sessions/t-1/prompt", 500, {"error": "pi-web restarting"})
        self.stub.set_routes([refused, *self.thread(("followUp", BARS), ("followUp", RERUN))])
        due = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual(due.returncode, 1)
        self.assertEqual(self.stub.requests[2:], [got_post("t-1", "queue/clear"), got_prompt("t-1", BARS, "steer")])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["replay"], [[BARS, "steer"], [RERUN, "follow-up"]])

        self.stub.set_routes(self.thread())
        again = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.stub.requests[:3], [
            got_status("t-1"),
            got_prompt("t-1", BARS, "steer"),
            got_prompt("t-1", RERUN, "followUp"),
        ])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["replay"], [])

    def test_a_resend_whose_clear_failed_sends_each_message_once(self) -> None:
        self.stub.set_routes(self.thread(("followUp", BARS)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        refused = ("POST", "/api/sessions/t-1/queue/clear", 500, {"error": "pi-web restarting"})
        self.stub.set_routes([refused, *self.thread(("followUp", BARS), ("followUp", RERUN))])
        self.assertEqual(self.tick("2026-10-06T12:10:00Z").returncode, 1)

        self.stub.set_routes(self.thread(("followUp", BARS), ("followUp", RERUN)))
        again = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual(again.returncode, 0, again.stderr)
        self.assertEqual(self.stub.requests[:5], [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_post("t-1", "queue/clear"),
            got_prompt("t-1", BARS, "steer"),
            got_prompt("t-1", RERUN, "followUp"),
        ])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["replay"], [])

    def test_a_message_that_left_the_queue_waits_from_its_return(self) -> None:
        self.stub.set_routes(self.thread(("steer", BARS)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        self.stub.set_routes(self.thread())
        self.assertEqual(self.tick("2026-10-06T12:05:00Z").returncode, 0)

        self.stub.set_routes(self.thread(("steer", BARS)))
        back = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((back.returncode, back.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertEqual(self.state(self.etl)["sessions"]["t-1"]["queued"], {BARS: "2026-10-06T12:10:00Z"})


if __name__ == "__main__":
    unittest.main()

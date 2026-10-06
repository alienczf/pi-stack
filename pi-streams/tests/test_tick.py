"""tick reports thread events to the coordinator, warm while small and recent, rotated otherwise."""
from __future__ import annotations

import unittest

from support import git
from tick_support import (
    HEADER,
    PROMPTS,
    TickCase,
    got_list,
    got_post,
    got_prompt,
    got_status,
    info,
    rotation,
    row,
    status,
)

ASK = {
    "askId": "ask-1",
    "askedAt": "2026-10-06T11:59:00.000Z",
    "questions": [
        {"id": "venue", "question": "Which venue first?", "options": []},
        {"id": "window", "question": "One day or one week?", "options": [], "allowOther": True},
    ],
}
ASK_2 = {
    "askId": "ask-2",
    "askedAt": "2026-10-06T12:09:00.000Z",
    "questions": [{"id": "dataset", "question": "May I write to Test?", "options": []}],
}


class TickTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        etl = str((self.home / "etl").resolve())
        self.etl = self.make_stream(
            self.home,
            "etl",
            row("coord-1", "coordinator", etl) + row("t-1", "datapull", "/wt/datapull"),
        )

    def listed(self, modified: str = "2026-10-06T11:00:00.000Z") -> tuple:
        return ("GET", "/api/sessions", 200, [
            info("coord-1", str(self.etl), self.log_path("coord-1"), modified),
            info("t-1", "/wt/datapull", self.log_path("t-1")),
        ])

    def coordinator(self, body: dict[str, object], modified: str = "2026-10-06T11:00:00.000Z") -> list[tuple]:
        return [("GET", "/api/sessions/coord-1/status", 200, body), self.listed(modified), PROMPTS]

    def test_a_thread_that_stops_streaming_wakes_the_coordinator(self) -> None:
        self.stub.set_routes([("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)), self.listed()])
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertFalse((self.etl / "log" / "events.jsonl").exists())
        self.assertEqual(self.state(self.etl), {
            "outages": [],
            "pending": [],
            "rotating": False,
            "subscriptions": {},
            "sessions": {"t-1": {"asks": [], "busy": True, "context": False, "queued": {}, "replay": []}},
        })
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s"), "pi-streams tick\n")
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1")),
            *self.coordinator(status("coord-1", tokens=None)),
        ])
        second = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((second.returncode, second.stdout, second.stderr), (0, f"{self.etl}\tidle=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt("coord-1", "pi-streams tick 2026-10-06T12:05:00Z:\nidle t-1 datapull"),
        ])
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:05:00Z", "kind": "idle", "session": "t-1", "role": "datapull", "detail": ""}\n',
        )
        self.assertEqual(self.state(self.etl), {
            "outages": [],
            "pending": [],
            "rotating": False,
            "subscriptions": {},
            "sessions": {"t-1": {"asks": [], "busy": False, "context": False, "queued": {}, "replay": []}},
        })
        self.assertEqual(git(self.home, self.env, "rev-list", "--count", "HEAD"), "2\n")

    def test_a_thread_that_finished_before_the_first_tick_wakes_the_coordinator(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1")),
            *self.coordinator(status("coord-1")),
        ])
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, f"{self.etl}\tidle=1\n", ""))
        self.assertEqual(
            self.stub.requests[-1],
            got_prompt("coord-1", "pi-streams tick 2026-10-06T12:00:00Z:\nidle t-1 datapull"),
        )
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((again.returncode, again.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])

    def test_an_ask_and_a_full_context_are_reported_once(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, tokens=150000, ask=ASK)),
            *self.coordinator(status("coord-1")),
        ])
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout), (0, f"{self.etl}\task=1\tcontext=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            "pi-streams tick 2026-10-06T12:00:00Z:\n"
            "ask t-1 datapull Which venue first? / One day or one week?\n"
            "context t-1 datapull 150000 tokens",
        ))

        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((again.returncode, again.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, tokens=160000, ask=ASK_2)),
            *self.coordinator(status("coord-1")),
        ])
        newer = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((newer.returncode, newer.stdout), (0, f"{self.etl}\task=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            "pi-streams tick 2026-10-06T12:10:00Z:\nask t-1 datapull May I write to Test?",
        ))
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:00:00Z", "kind": "ask", "session": "t-1", "role": "datapull", '
            '"detail": "Which venue first?\\nOne day or one week?"}\n'
            '{"at": "2026-10-06T12:00:00Z", "kind": "context", "session": "t-1", "role": "datapull", '
            '"detail": "150000 tokens"}\n'
            '{"at": "2026-10-06T12:10:00Z", "kind": "ask", "session": "t-1", "role": "datapull", '
            '"detail": "May I write to Test?"}\n',
        )
        self.assertEqual(self.state(self.etl), {
            "outages": [],
            "pending": [],
            "rotating": False,
            "subscriptions": {},
            "sessions": {"t-1": {"asks": ["ask-2"], "busy": True, "context": True, "queued": {}, "replay": []}},
        })

    def test_a_streaming_coordinator_gets_the_events_as_a_follow_up(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK_2)),
            *self.coordinator(status("coord-1", streaming=True, tokens=90000)),
        ])
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (0, f"{self.etl}\task=1\n"))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt(
                "coord-1",
                "pi-streams tick 2026-10-06T12:00:00Z:\nask t-1 datapull May I write to Test?",
                "followUp",
            ),
        ])

    def test_a_coordinator_at_the_context_cap_is_rotated_and_the_new_one_gets_the_events(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK_2)),
            ("POST", "/api/sessions", 200, info("coord-2", str(self.etl), self.log_path("coord-2"))),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2", tokens=None)),
            *self.coordinator(status("coord-1", tokens=60000)),
        ])
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, f"{self.etl}\task=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_post("coord-1", "archive"),
            got_list(str(self.etl)),
            ("POST", "/api/sessions", "", {"cwd": str(self.etl)}),
            got_post("coord-2", "model", {"provider": "openai-codex", "modelId": "gpt-6-astra"}),
            got_post("coord-2", "thinking-level", {"level": "xhigh"}),
            got_status("coord-2"),
            got_prompt("coord-2", rotation("etl")),
            got_prompt(
                "coord-2",
                "pi-streams tick 2026-10-06T12:00:00Z:\nask t-1 datapull May I write to Test?",
                "followUp",
            ),
        ])
        self.assertEqual(
            self.rows(self.etl),
            HEADER
            + row("coord-1", "coordinator", str(self.etl), status="archived")
            + row("t-1", "datapull", "/wt/datapull")
            + f"coord-2\tcoordinator\t\t{self.etl}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T12:00:00Z\n",
        )
        self.assertEqual(self.state(self.etl)["pending"], [])
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

    def test_a_coordinator_idle_for_six_hours_is_rotated(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK)),
            *self.coordinator(status("coord-1", tokens=None), modified="2026-10-06T06:00:00.000Z"),
        ])
        warm = self.tick("2026-10-06T11:59:59Z")
        self.assertEqual((warm.returncode, warm.stdout), (0, f"{self.etl}\task=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            "pi-streams tick 2026-10-06T11:59:59Z:\nask t-1 datapull Which venue first? / One day or one week?",
        ))

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK_2)),
            ("POST", "/api/sessions", 200, info("coord-2", str(self.etl), self.log_path("coord-2"))),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2", tokens=None)),
            *self.coordinator(status("coord-1", tokens=None), modified="2026-10-06T06:00:00.000Z"),
        ])
        cold = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((cold.returncode, cold.stdout, cold.stderr), (0, f"{self.etl}\task=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_post("coord-1", "archive"),
            got_list(str(self.etl)),
            ("POST", "/api/sessions", "", {"cwd": str(self.etl)}),
            got_post("coord-2", "model", {"provider": "openai-codex", "modelId": "gpt-6-astra"}),
            got_post("coord-2", "thinking-level", {"level": "xhigh"}),
            got_status("coord-2"),
            got_prompt("coord-2", rotation("etl")),
            got_prompt(
                "coord-2",
                "pi-streams tick 2026-10-06T12:00:00Z:\nask t-1 datapull May I write to Test?",
                "followUp",
            ),
        ])

    def test_tick_runs_every_registered_home_unless_one_is_given(self) -> None:
        other_root = self.tmp / "other"
        other_root.mkdir()
        proc = self.run_streams("init", str(other_root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        ops = str((other_root / "streams" / "ops").resolve())
        ops_dir = self.make_stream(
            other_root / "streams",
            "ops",
            row("coord-9", "coordinator", ops) + row("t-9", "review", "/wt/review"),
        )
        listed = ("GET", "/api/sessions", 200, [
            *self.listed()[3],
            info("coord-9", ops, self.log_path("coord-9")),
            info("t-9", "/wt/review", self.log_path("t-9")),
        ])
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)),
            ("GET", "/api/sessions/t-9/status", 200, status("t-9", streaming=True)),
            listed,
        ])
        both = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((both.returncode, both.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("t-9"),
            got_list("/wt/review"),
            got_list(ops),
        ])

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1")),
            ("GET", "/api/sessions/t-9/status", 200, status("t-9")),
            ("GET", "/api/sessions/coord-9/status", 200, status("coord-9")),
            listed,
            PROMPTS,
        ])
        one = self.tick("2026-10-06T12:05:00Z", "--home", str(other_root / "streams"))
        self.assertEqual((one.returncode, one.stdout, one.stderr), (0, f"{ops_dir}\tidle=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-9"),
            got_list("/wt/review"),
            got_list(ops),
            got_status("coord-9"),
            got_prompt("coord-9", "pi-streams tick 2026-10-06T12:05:00Z:\nidle t-9 review"),
        ])
        self.assertEqual(
            self.state(self.etl)["sessions"],
            {"t-1": {"asks": [], "busy": True, "context": False, "queued": {}, "replay": []}},
        )


if __name__ == "__main__":
    unittest.main()

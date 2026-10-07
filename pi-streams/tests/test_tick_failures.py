"""tick records a failure in one stream or home and still ticks the others."""
from __future__ import annotations

import json
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
    "questions": [{"id": "venue", "question": "Which venue first?", "options": []}],
}
ASKED = {"at": "2026-10-06T12:00:00Z", "kind": "ask", "session": "t-1", "role": "datapull", "detail": "Which venue first?"}
RESTARTING = '{\n  "ok": false,\n  "status": 500,\n  "session": {\n    "error": "pi runtime is restarting"\n  }\n}'
SPAWN_FAILED = '{\n  "ok": false,\n  "status": 500,\n  "session": {\n    "error": "pi exited with code 1"\n  }\n}'


class FailureTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.etl = self.make_stream(
            self.home,
            "etl",
            row("coord-1", "coordinator", str((self.home / "etl").resolve())) + row("t-1", "datapull", "/wt/datapull"),
        )

    def listed(self, *extra: dict[str, object]) -> tuple:
        return ("GET", "/api/sessions", 200, [
            info("coord-1", str(self.etl), self.log_path("coord-1")),
            info("t-1", "/wt/datapull", self.log_path("t-1")),
            *extra,
        ])

    def test_a_pi_web_failure_is_recorded_and_the_next_stream_still_ticks(self) -> None:
        ops = self.make_stream(
            self.home,
            "ops",
            row("coord-2", "coordinator", str((self.home / "ops").resolve())) + row("t-2", "review", "/wt/review"),
        )
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 500, {"error": "pi runtime is restarting"}),
            ("GET", "/api/sessions/t-2/status", 200, status("t-2", streaming=True, ask=ASK)),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2")),
            self.listed(info("coord-2", str(ops), self.log_path("coord-2")), info("t-2", "/wt/review", self.log_path("t-2"))),
            PROMPTS,
        ])
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (
            1,
            f"{self.etl}\ttick-error=1\n{ops}\task=1\n",
            f"{self.etl}: pi-web-cli status t-1 failed: {RESTARTING}\n",
        ))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_status("t-2"),
            got_list("/wt/review"),
            got_list(str(ops)),
            got_status("coord-2"),
            got_prompt("coord-2", "pi-streams tick 2026-10-06T12:00:00Z:\nask t-2 review Which venue first?"),
        ])
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:00:00Z", "kind": "tick-error", "session": "", "role": "", '
            '"detail": "pi-web-cli status t-1 failed: {\\n  \\"ok\\": false,\\n  \\"status\\": 500,\\n  '
            '\\"session\\": {\\n    \\"error\\": \\"pi runtime is restarting\\"\\n  }\\n}"}\n',
        )
        self.assertEqual(
            self.state(self.etl),
            {"claims": [], "outages": [], "pending": [], "rotating": False, "sessions": {}, "subscriptions": {}},
        )
        self.assertEqual(git(self.etl, self.env, "status", "--porcelain"), "")
        self.assertEqual(git(ops, self.env, "status", "--porcelain"), "")

    def test_a_stream_whose_log_cannot_be_written_does_not_stop_the_others(self) -> None:
        (self.etl / "log" / "events.jsonl").mkdir(parents=True)
        ops = self.make_stream(
            self.home,
            "ops",
            row("coord-2", "coordinator", str((self.home / "ops").resolve())) + row("t-2", "review", "/wt/review"),
        )
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK)),
            ("GET", "/api/sessions/t-2/status", 200, status("t-2", streaming=True, ask=ASK)),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2")),
            self.listed(info("coord-2", str(ops), self.log_path("coord-2")), info("t-2", "/wt/review", self.log_path("t-2"))),
            PROMPTS,
        ])
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (1, f"{self.etl}\task=1\ttick-error=1\n{ops}\task=1\n"))
        self.assertTrue(proc.stderr.startswith(f"{self.etl}: [Errno 21] Is a directory"), proc.stderr)
        self.assertEqual(self.stub.requests[-1], got_prompt("coord-2", "pi-streams tick 2026-10-06T12:00:00Z:\nask t-2 review Which venue first?"))
        self.assertEqual(git(self.etl, self.env, "status", "--porcelain"), "")
        self.assertEqual(git(ops, self.env, "status", "--porcelain"), "")

    def test_a_rotation_that_fails_after_its_archive_is_finished_by_the_next_tick(self) -> None:
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK)),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1", tokens=60000)),
            ("POST", "/api/sessions", 500, {"error": "pi exited with code 1"}),
            self.listed(),
            PROMPTS,
        ])
        failed = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (
            1,
            f"{self.etl}\task=1\ttick-error=1\n",
            f"{self.etl}: pi-web-cli spawn {self.etl} failed: {SPAWN_FAILED}\n",
        ))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_post("coord-1", "archive"),
            got_list(str(self.etl)),
            ("POST", "/api/sessions", "", {"cwd": str(self.etl)}),
        ])
        archived = HEADER + row("coord-1", "coordinator", str(self.etl), status="archived")
        archived += row("t-1", "datapull", "/wt/datapull")
        self.assertEqual(self.rows(self.etl), archived)
        self.assertEqual((self.state(self.etl)["rotating"], self.state(self.etl)["pending"]), (True, [ASKED]))

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK)),
            ("POST", "/api/sessions", 200, info("coord-2", str(self.etl), self.log_path("coord-2"))),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2", tokens=None)),
            self.listed(),
            PROMPTS,
        ])
        healed = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((healed.returncode, healed.stdout, healed.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            ("POST", "/api/sessions", "", {"cwd": str(self.etl)}),
            got_post("coord-2", "model", {"provider": "openai-codex", "modelId": "gpt-6-astra"}),
            got_post("coord-2", "thinking-level", {"level": "xhigh"}),
            got_status("coord-2"),
            got_prompt("coord-2", rotation("etl")),
            got_prompt("coord-2", "pi-streams tick 2026-10-06T12:05:00Z:\nask t-1 datapull Which venue first?", "followUp"),
        ])
        self.assertEqual(
            self.rows(self.etl),
            archived
            + f"coord-2\tcoordinator\t\t{self.etl}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T12:05:00Z\n",
        )
        self.assertEqual((self.state(self.etl)["rotating"], self.state(self.etl)["pending"]), (False, []))

    def test_a_rotation_that_stopped_after_pi_web_archived_the_coordinator_is_finished(self) -> None:
        state = {"outages": [], "pending": [ASKED], "rotating": True, "sessions": {}}
        (self.etl / "log").mkdir()
        (self.etl / "log" / "tick-state.json").write_text(json.dumps(state), encoding="utf-8")
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1")),
            ("POST", "/api/sessions", 200, info("coord-2", str(self.etl), self.log_path("coord-2"))),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2", tokens=None)),
            ("GET", "/api/sessions", 200, [
                {**info("coord-1", str(self.etl), self.log_path("coord-1")), "archived": True},
                info("t-1", "/wt/datapull", self.log_path("t-1")),
            ]),
            PROMPTS,
        ])
        proc = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_list(str(self.etl)),
            ("POST", "/api/sessions", "", {"cwd": str(self.etl)}),
            got_post("coord-2", "model", {"provider": "openai-codex", "modelId": "gpt-6-astra"}),
            got_post("coord-2", "thinking-level", {"level": "xhigh"}),
            got_status("coord-2"),
            got_prompt("coord-2", rotation("etl")),
            got_prompt("coord-2", "pi-streams tick 2026-10-06T12:05:00Z:\nask t-1 datapull Which venue first?", "followUp"),
        ])
        self.assertEqual(
            self.rows(self.etl),
            HEADER
            + row("coord-1", "coordinator", str(self.etl), status="archived")
            + row("t-1", "datapull", "/wt/datapull")
            + f"coord-2\tcoordinator\t\t{self.etl}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T12:05:00Z\n",
        )
        self.assertEqual((self.state(self.etl)["rotating"], self.state(self.etl)["pending"]), (False, []))

    def test_a_state_file_that_does_not_parse_is_left_alone(self) -> None:
        state = self.etl / "log" / "tick-state.json"
        state.parent.mkdir()
        state.write_text('{"sessions": {', encoding="utf-8")
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (
            1,
            f"{self.etl}\ttick-error=1\n",
            f"{self.etl}: {state}: Expecting property name enclosed in double quotes: line 1 column 15 (char 14)\n",
        ))
        self.assertEqual(self.stub.requests, [])
        self.assertEqual(state.read_text(encoding="utf-8"), '{"sessions": {')

    def test_a_registered_home_that_is_gone_fails_the_tick_but_not_the_other_homes(self) -> None:
        gone = self.tmp / "gone" / "streams"
        homes = self.xdg / "pi-streams" / "homes"
        homes.write_text(f"{gone}\n" + homes.read_text(encoding="utf-8"), encoding="utf-8")
        self.stub.set_routes([("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)), self.listed()])
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (
            1,
            "",
            f"{gone}: [Errno 2] No such file or directory: '{gone}/.pi-streams.lock'\n",
        ))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])


if __name__ == "__main__":
    unittest.main()

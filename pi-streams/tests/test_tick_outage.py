"""tick turns a failed model call into an alert, and clears it once a call succeeds."""
from __future__ import annotations

import unittest
from pathlib import Path

from support import git
from tick_support import (
    HEADER,
    PROMPTS,
    TickCase,
    failure,
    got_list,
    got_post,
    got_prompt,
    got_status,
    info,
    reply,
    rotation,
    row,
    status,
    thinking_change,
    user,
)

LIMIT = (
    "429 usage_limit_reached: You have hit your ChatGPT usage limit (pro plan). Try again in ~154 min.\n"
    "POST https://chatgpt.com/backend-api/codex/responses model=gpt-6-astra account=acct_7Qx2 "
    "retries=3 last_attempt=2026-10-06T11:58:41Z trace=0f3a9c51d2e84b7a"
)
SHOWN = (
    "429 usage_limit_reached: You have hit your ChatGPT usage limit (pro plan). Try again in ~154 min. "
    "POST https://chatgpt.com/backend-api/codex/responses model=gpt-6-astra account=acct_7Qx2 retries=3 las"
)
ASK = {
    "askId": "ask-1",
    "askedAt": "2026-10-06T11:59:00.000Z",
    "questions": [{"id": "venue", "question": "Which venue first?", "options": []}],
}


class OutageTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        etl = str((self.home / "etl").resolve())
        self.etl = self.make_stream(
            self.home,
            "etl",
            row("coord-1", "coordinator", etl) + row("t-1", "datapull", "/wt/datapull"),
        )

    def routes(self, thread: dict[str, object]) -> list[tuple]:
        return [
            ("GET", "/api/sessions/t-1/status", 200, thread),
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1")),
            ("GET", "/api/sessions", 200, [
                info("coord-1", str(self.etl), self.log_path("coord-1")),
                info("t-1", "/wt/datapull", self.log_path("t-1")),
            ]),
            PROMPTS,
        ]

    def test_a_failed_model_call_puts_the_thread_on_quota_until_a_call_succeeds(self) -> None:
        self.write_log("t-1", "/wt/datapull", user("Pull the 1m bars."), failure(LIMIT), thinking_change())
        self.stub.set_routes(self.routes(status("t-1")))
        down = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((down.returncode, down.stdout, down.stderr), (0, f"{self.etl}\tidle=1\toutage=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt("coord-1", f"pi-streams tick 2026-10-06T12:00:00Z:\nidle t-1 datapull\noutage t-1 datapull {SHOWN}"),
        ])
        self.assertEqual(
            self.rows(self.etl),
            HEADER
            + row("coord-1", "coordinator", str(self.etl))
            + row("t-1", "datapull", "/wt/datapull", status="waiting_quota"),
        )
        self.assertEqual(self.alerts(), f"2026-10-06T12:00:00Z etl t-1 datapull {SHOWN}\n")
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

        still = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((still.returncode, still.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertEqual(self.alerts(), f"2026-10-06T12:00:00Z etl t-1 datapull {SHOWN}\n")

        long_reply = "Pulled the 1m bars. " + "ok " * 40000
        self.write_log(
            "t-1",
            "/wt/datapull",
            user("Pull the 1m bars."),
            failure(LIMIT),
            thinking_change(),
            user("Continue."),
            reply(long_reply),
        )
        back = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((back.returncode, back.stdout, back.stderr), (0, f"{self.etl}\trecovered=1\n", ""))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            "pi-streams tick 2026-10-06T12:10:00Z:\nrecovered t-1 datapull",
        ))
        self.assertEqual(
            self.rows(self.etl),
            HEADER + row("coord-1", "coordinator", str(self.etl)) + row("t-1", "datapull", "/wt/datapull"),
        )
        self.assertEqual(self.alerts(), "")
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:00:00Z", "kind": "idle", "session": "t-1", "role": "datapull", "detail": ""}\n'
            '{"at": "2026-10-06T12:00:00Z", "kind": "outage", "session": "t-1", "role": "datapull", '
            f'"detail": "{SHOWN}"}}\n'
            '{"at": "2026-10-06T12:10:00Z", "kind": "recovered", "session": "t-1", "role": "datapull", '
            '"detail": ""}\n',
        )
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

    def test_a_log_with_no_reply_does_not_end_an_outage(self) -> None:
        self.write_log("t-1", "/wt/datapull", user("Pull the 1m bars."), failure(LIMIT))
        self.stub.set_routes(self.routes(status("t-1")))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").returncode, 0)
        out = HEADER + row("coord-1", "coordinator", str(self.etl)) + row("t-1", "datapull", "/wt/datapull", status="waiting_quota")
        alert = f"2026-10-06T12:00:00Z etl t-1 datapull {SHOWN}\n"

        Path(self.log_path("t-1")).unlink()
        gone = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((gone.returncode, gone.stdout), (0, ""))
        self.write_log("t-1", "/wt/datapull", user("Continue."))
        unanswered = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((unanswered.returncode, unanswered.stdout), (0, ""))
        self.assertEqual((self.rows(self.etl), self.alerts()), (out, alert))

    def test_a_coordinator_in_an_outage_stays_active_and_gets_its_events_after(self) -> None:
        self.write_log("coord-1", str(self.etl), user("/skill:stream-kickoff"), failure(LIMIT))
        self.stub.set_routes(self.routes(status("t-1", streaming=True, ask=ASK)))
        down = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((down.returncode, down.stdout, down.stderr), (0, f"{self.etl}\task=1\toutage=1\n", ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])
        self.assertEqual(
            self.rows(self.etl),
            HEADER + row("coord-1", "coordinator", str(self.etl)) + row("t-1", "datapull", "/wt/datapull"),
        )
        self.assertEqual(self.alerts(), f"2026-10-06T12:00:00Z etl coord-1 coordinator {SHOWN}\n")
        self.assertEqual(self.state(self.etl)["outages"], ["coord-1"])
        self.assertEqual(self.state(self.etl)["pending"], [
            {
                "at": "2026-10-06T12:00:00Z",
                "kind": "ask",
                "session": "t-1",
                "role": "datapull",
                "detail": "Which venue first?",
            },
            {
                "at": "2026-10-06T12:00:00Z",
                "kind": "outage",
                "session": "coord-1",
                "role": "coordinator",
                "detail": SHOWN,
            },
        ])

        still = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((still.returncode, still.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("t-1"), got_list("/wt/datapull"), got_list(str(self.etl))])

        self.write_log(
            "coord-1", str(self.etl), user("/skill:stream-kickoff"), failure(LIMIT), user("Continue."), reply("Back.")
        )
        back = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((back.returncode, back.stdout, back.stderr), (0, f"{self.etl}\trecovered=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_status("t-1"),
            got_list("/wt/datapull"),
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt(
                "coord-1",
                "pi-streams tick 2026-10-06T12:10:00Z:\n"
                "ask t-1 datapull Which venue first?\n"
                f"outage coord-1 coordinator {SHOWN}\n"
                "recovered coord-1 coordinator",
            ),
        ])
        self.assertEqual(self.alerts(), "")
        self.assertEqual((self.state(self.etl)["outages"], self.state(self.etl)["pending"]), ([], []))

    def test_a_coordinator_archived_during_its_outage_is_replaced(self) -> None:
        self.write_log("coord-1", str(self.etl), user("/skill:stream-kickoff"), failure(LIMIT))
        self.stub.set_routes(self.routes(status("t-1", streaming=True, ask=ASK)))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").stdout, f"{self.etl}\task=1\toutage=1\n")

        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True, ask=ASK)),
            ("POST", "/api/sessions", 200, info("coord-2", str(self.etl), self.log_path("coord-2"))),
            ("GET", "/api/sessions/coord-2/status", 200, status("coord-2", tokens=None)),
            ("GET", "/api/sessions", 200, [
                {**info("coord-1", str(self.etl), self.log_path("coord-1")), "archived": True},
                info("t-1", "/wt/datapull", self.log_path("t-1")),
            ]),
            PROMPTS,
        ])
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((later.returncode, later.stdout, later.stderr), (0, "", ""))
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
            got_prompt(
                "coord-2",
                "pi-streams tick 2026-10-06T12:05:00Z:\n"
                "ask t-1 datapull Which venue first?\n"
                f"outage coord-1 coordinator {SHOWN}",
                "followUp",
            ),
        ])
        self.assertEqual(
            self.rows(self.etl),
            HEADER
            + row("coord-1", "coordinator", str(self.etl), status="archived")
            + row("t-1", "datapull", "/wt/datapull")
            + f"coord-2\tcoordinator\t\t{self.etl}\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T12:05:00Z\n",
        )
        self.assertEqual(self.alerts(), "")
        self.assertEqual((self.state(self.etl)["outages"], self.state(self.etl)["pending"]), ([], []))

    def test_an_alert_goes_once_its_thread_is_archived(self) -> None:
        self.write_log("t-1", "/wt/datapull", user("Pull the 1m bars."), failure(LIMIT))
        self.stub.set_routes(self.routes(status("t-1")))
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").stdout, f"{self.etl}\tidle=1\toutage=1\n")
        self.assertEqual(self.alerts(), f"2026-10-06T12:00:00Z etl t-1 datapull {SHOWN}\n")

        (self.etl / "threads.tsv").write_text(
            HEADER
            + row("coord-1", "coordinator", str(self.etl))
            + row("t-1", "datapull", "/wt/datapull", status="archived"),
            encoding="utf-8",
        )
        later = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((later.returncode, later.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_list(str(self.etl))])
        self.assertEqual(self.alerts(), "")


if __name__ == "__main__":
    unittest.main()

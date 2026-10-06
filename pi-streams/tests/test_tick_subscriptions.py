"""tick fires a subscription when its source changes after the first reading.

pr_view() is a body in the shape that gh 2.45.0 prints for pr view --json.
"""
from __future__ import annotations

import json
import os
import unittest

from tick_support import HEADER, PROMPTS, TickCase, got_list, got_prompt, got_status, info, row, status

DAILY = "daily\tschedule\t\t09:00\tPost the daily status to ZF."
ROWS = "rows\tcmd\tcat watch.txt\t\tCheck the row count against the template."
ROWS_ACTION = "subscription rows: Check the row count against the template."
PR = "pr\tgh-pr\talienczf/pi-stack#412\t\tReview the PR once its checks pass."
PR_ACTION = "subscription pr: Review the PR once its checks pass."
GH_ARGV = "pr\nview\n412\n--repo\nalienczf/pi-stack\n--json\nstate,reviewDecision,statusCheckRollup,mergedAt,reviews\n\n"
FAKE_GH = r"""#!/bin/sh
printf '%s\n' "$@" "" >> "${0%/*}/gh-calls"
if [ -f "${0%/*}/pr.json" ]; then
    exec cat "${0%/*}/pr.json"
fi
echo "error connecting to api.github.com" >&2
echo "check your internet connection or https://githubstatus.com" >&2
exit 1
"""


def check_run(name: str, conclusion: str = "", progress: str = "IN_PROGRESS") -> dict[str, object]:
    return {
        "__typename": "CheckRun",
        "completedAt": "2026-10-06T12:08:00Z" if conclusion else "0001-01-01T00:00:00Z",
        "conclusion": conclusion,
        "detailsUrl": f"https://github.com/alienczf/pi-stack/actions/runs/7001/job/{name}",
        "name": name,
        "startedAt": "2026-10-06T12:01:00Z",
        "status": "COMPLETED" if conclusion else progress,
        "workflowName": "CI",
    }


def status_context(context: str, state: str) -> dict[str, object]:
    return {
        "__typename": "StatusContext",
        "context": context,
        "startedAt": "2026-10-06T12:01:00Z",
        "state": state,
        "targetUrl": f"https://ci.example.com/alienczf/pi-stack/412/{context}",
    }


def review(state: str) -> dict[str, object]:
    return {
        "id": "PRR_kwDOAlphaLab412",
        "author": {"login": "zf"},
        "authorAssociation": "OWNER",
        "body": "Looks right.",
        "submittedAt": "2026-10-06T14:30:00Z",
        "includesCreatedEdit": False,
        "reactionGroups": [],
        "state": state,
        "commit": {"oid": "4f2a9c0e1b7d3a5f8c6e2d4b9a1f3c5e7d9b0a2c"},
    }


def pr_view(
    *checks: dict[str, object],
    state: str = "OPEN",
    decision: str = "REVIEW_REQUIRED",
    merged_at: str | None = None,
    reviews: tuple[dict[str, object], ...] = (),
) -> dict[str, object]:
    return {
        "mergedAt": merged_at,
        "reviewDecision": decision,
        "reviews": list(reviews),
        "state": state,
        "statusCheckRollup": list(checks),
    }


class SubscriptionTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.etl = self.make_stream(self.home, "etl", row("coord-1", "coordinator", str((self.home / "etl").resolve())))
        self.stub.set_routes([
            ("GET", "/api/sessions/coord-1/status", 200, status("coord-1", streaming=True)),
            ("GET", "/api/sessions", 200, [info("coord-1", str(self.etl), self.log_path("coord-1"))]),
            PROMPTS,
        ])

    def gh_on_path(self) -> None:
        self.bin = self.tmp / "bin"
        self.bin.mkdir()
        gh = self.bin / "gh"
        gh.write_text(FAKE_GH, encoding="utf-8")
        gh.chmod(0o755)
        self.env["PATH"] = f"{self.bin}{os.pathsep}/usr/bin:/bin"

    def gh_answers(self, view: dict[str, object] | None) -> None:
        answer = self.bin / "pr.json"
        if view is None:
            answer.unlink()
        else:
            answer.write_text(json.dumps(view), encoding="utf-8")

    def gh_calls(self) -> str:
        return (self.bin / "gh-calls").read_text(encoding="utf-8")

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

    def test_a_cmd_fires_when_its_exit_code_or_its_stdout_changes(self) -> None:
        self.subscribe(self.etl, ROWS)
        watch = self.etl / "watch.txt"
        watch.write_text("rows 432000\n", encoding="utf-8")
        for at in ("2026-10-06T12:00:00Z", "2026-10-06T12:05:00Z"):
            quiet = self.tick(at)
            self.assertEqual((quiet.returncode, quiet.stdout, quiet.stderr), (0, "", ""))
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "rows": {
                "fingerprint": "exit=0 sha256=16de491a8b693cc8f9c638ece7086732da962b93c0fa37b1ce087da1a72d46bd",
                "watch": ["cmd", "cat watch.txt", ""],
            },
        })

        watch.write_text("".join(f"row {n}\n" for n in range(1, 26)), encoding="utf-8")
        grew = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((grew.returncode, grew.stdout, grew.stderr), (0, f"{self.etl}\tsubscription=1\n", ""))
        last_20 = " / ".join(f"row {n}" for n in range(6, 26))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            f"pi-streams tick 2026-10-06T12:10:00Z:\n{ROWS_ACTION} / {last_20}",
            "followUp",
        ))

        watch.unlink()
        failed = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (0, f"{self.etl}\tsubscription=1\n", ""))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            f"pi-streams tick 2026-10-06T12:15:00Z:\n{ROWS_ACTION} / cat: watch.txt: No such file or directory",
            "followUp",
        ))
        self.assertEqual(
            self.state(self.etl)["subscriptions"]["rows"]["fingerprint"],
            "exit=1 sha256=e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
        )

    def test_a_gh_pr_fires_when_a_check_concludes_or_the_pr_is_reviewed_or_merged(self) -> None:
        self.gh_on_path()
        self.subscribe(self.etl, PR)
        self.gh_answers(pr_view(
            check_run("lint", "SUCCESS"),
            check_run("test", progress="QUEUED"),
            status_context("codecov/patch", "PENDING"),
        ))
        first = self.tick("2026-10-06T12:02:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "", ""))
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "pr": {
                "fingerprint": "state=OPEN reviewDecision=REVIEW_REQUIRED "
                "checks=codecov/patch:PENDING,lint:SUCCESS,test:PENDING mergedAt=- reviews=0",
                "watch": ["gh-pr", "alienczf/pi-stack#412", ""],
            },
        })

        self.gh_answers(pr_view(
            status_context("codecov/patch", "PENDING"),
            check_run("test"),
            check_run("lint", "SUCCESS"),
        ))
        running = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((running.returncode, running.stdout, running.stderr), (0, "", ""))

        self.gh_answers(pr_view(
            check_run("lint", "SUCCESS"),
            check_run("test", "FAILURE"),
            status_context("codecov/patch", "SUCCESS"),
        ))
        failed = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((failed.returncode, failed.stdout, failed.stderr), (0, f"{self.etl}\tsubscription=1\n", ""))
        self.assertEqual(self.stub.requests, [
            got_list(str(self.etl)),
            got_status("coord-1"),
            got_prompt(
                "coord-1",
                f"pi-streams tick 2026-10-06T12:10:00Z:\n{PR_ACTION} / state=OPEN reviewDecision=REVIEW_REQUIRED "
                "checks=codecov/patch:SUCCESS,lint:SUCCESS,test:FAILURE mergedAt=- reviews=0",
                "followUp",
            ),
        ])

        passed = (check_run("lint", "SUCCESS"), check_run("test", "SUCCESS"), status_context("codecov/patch", "SUCCESS"))
        self.gh_answers(pr_view(*passed, decision="APPROVED", reviews=(review("APPROVED"),)))
        approved = self.tick("2026-10-06T14:35:00Z")
        self.assertEqual((approved.returncode, approved.stdout), (0, f"{self.etl}\tsubscription=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            f"pi-streams tick 2026-10-06T14:35:00Z:\n{PR_ACTION} / state=OPEN reviewDecision=APPROVED "
            "checks=codecov/patch:SUCCESS,lint:SUCCESS,test:SUCCESS mergedAt=- reviews=1",
            "followUp",
        ))

        self.gh_answers(pr_view(
            *passed,
            state="MERGED",
            decision="APPROVED",
            merged_at="2026-10-06T15:00:00Z",
            reviews=(review("APPROVED"),),
        ))
        merged = self.tick("2026-10-06T15:05:00Z")
        self.assertEqual((merged.returncode, merged.stdout), (0, f"{self.etl}\tsubscription=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            f"pi-streams tick 2026-10-06T15:05:00Z:\n{PR_ACTION} / state=MERGED reviewDecision=APPROVED "
            "checks=codecov/patch:SUCCESS,lint:SUCCESS,test:SUCCESS mergedAt=2026-10-06T15:00:00Z reviews=1",
            "followUp",
        ))
        self.assertEqual(self.gh_calls(), GH_ARGV * 5)

    def test_a_gh_pr_that_gh_cannot_read_is_a_tick_error_and_keeps_its_baseline(self) -> None:
        self.gh_on_path()
        self.subscribe(self.etl, PR, "typo\tgh-pr\talienczf/pi-stack/412\t\tReview the PR.")
        self.gh_answers(pr_view(check_run("test", "SUCCESS")))
        typo = f"{self.etl}: subscription typo: target is not owner/repo#N: alienczf/pi-stack/412\n"
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (1, f"{self.etl}\ttick-error=1\n", typo))

        self.gh_answers(None)
        offline = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((offline.returncode, offline.stdout, offline.stderr), (
            1,
            f"{self.etl}\ttick-error=2\n",
            f"{self.etl}: subscription pr: gh exited 1: error connecting to api.github.com / "
            "check your internet connection or https://githubstatus.com\n" + typo,
        ))
        self.assertEqual(self.state(self.etl)["subscriptions"], {
            "pr": {
                "fingerprint": "state=OPEN reviewDecision=REVIEW_REQUIRED checks=test:SUCCESS mergedAt=- reviews=0",
                "watch": ["gh-pr", "alienczf/pi-stack#412", ""],
            },
        })

        self.gh_answers(pr_view(check_run("test", "SUCCESS"), decision="APPROVED", reviews=(review("APPROVED"),)))
        back = self.tick("2026-10-06T14:35:00Z")
        self.assertEqual((back.returncode, back.stdout), (1, f"{self.etl}\tsubscription=1\ttick-error=1\n"))
        self.assertEqual(self.stub.requests[-1], got_prompt(
            "coord-1",
            f"pi-streams tick 2026-10-06T14:35:00Z:\n{PR_ACTION} / state=OPEN reviewDecision=APPROVED "
            "checks=test:SUCCESS mergedAt=- reviews=1",
            "followUp",
        ))
        self.assertEqual(self.gh_calls(), GH_ARGV * 3)

    def test_a_stream_without_an_active_coordinator_runs_none_of_its_commands(self) -> None:
        (self.etl / "threads.tsv").write_text(
            HEADER + row("coord-1", "coordinator", str(self.etl), status="done"),
            encoding="utf-8",
        )
        self.subscribe(self.etl, "hello\tcmd\ttouch ran\t\tSay hello.")
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [got_status("coord-1")])
        self.assertFalse((self.etl / "ran").exists())
        self.assertEqual(self.state(self.etl)["subscriptions"], {})


if __name__ == "__main__":
    unittest.main()

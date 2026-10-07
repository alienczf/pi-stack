"""tick alerts when rows in two streams share a worktree, or share both a repo and a branch."""
from __future__ import annotations

import unittest
from pathlib import Path

from tick_support import HEADER, PROMPTS, TickCase, got_list, got_prompt, got_status, info, row, status

SHARED = "/wt/alpha/feat-a"
WORKTREES = {
    "r-2": SHARED,
    "t-4": "/wt/beta/datapull-tester",
    "w-1": SHARED,
    "b-3": "/wt/beta/etl-builder",
}
ALERTS = (
    "2026-10-06T12:00:00Z claim datapull/r-2,etl/w-1 reviewer and worker share worktree /wt/alpha/feat-a\n"
    "2026-10-06T12:00:00Z claim datapull/t-4,etl/b-3 tester and builder share beta branch x\n"
)
BRANCH_ALERT = "2026-10-06T12:00:00Z claim datapull/t-4,etl/b-3 tester and builder share beta branch x\n"
KEYS = ["datapull/r-2,etl/w-1", "datapull/t-4,etl/b-3"]
DATAPULL_EVENTS = (
    '{"at": "2026-10-06T12:00:00Z", "kind": "claim", "session": "r-2", "role": "reviewer", '
    '"detail": "shares worktree /wt/alpha/feat-a with etl worker w-1"}\n'
    '{"at": "2026-10-06T12:00:00Z", "kind": "claim", "session": "t-4", "role": "tester", '
    '"detail": "shares beta branch x with etl builder b-3"}\n'
)
ETL_EVENTS = (
    '{"at": "2026-10-06T12:00:00Z", "kind": "claim", "session": "w-1", "role": "worker", '
    '"detail": "shares worktree /wt/alpha/feat-a with datapull reviewer r-2"}\n'
    '{"at": "2026-10-06T12:00:00Z", "kind": "claim", "session": "b-3", "role": "builder", '
    '"detail": "shares beta branch x with datapull tester t-4"}\n'
)


def observed(stream_dir: Path, *sessions: str) -> list[tuple[str, str, str, object]]:
    found: list[tuple[str, str, str, object]] = []
    for sid in sessions:
        found += [got_status(sid), got_list(WORKTREES[sid])]
    return [*found, got_list(str(stream_dir))]


class ClaimTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.datapull = self.make_stream(self.home, "datapull", self.datapull_rows())
        self.etl = self.make_stream(self.home, "etl", self.etl_rows())
        cwds = {"coord-d": str(self.datapull), "coord-e": str(self.etl), **WORKTREES}
        self.stub.set_routes([
            *[
                ("GET", f"/api/sessions/{sid}/status", 200, status(sid, streaming=True))
                for sid in cwds
            ],
            ("GET", "/api/sessions", 200, [info(sid, cwd, self.log_path(sid)) for sid, cwd in cwds.items()]),
            PROMPTS,
        ])

    def datapull_rows(self) -> str:
        return (
            row("coord-d", "coordinator", str((self.home / "datapull").resolve()))
            + row("r-2", "reviewer", SHARED, branch="feat-a")
            + row("t-4", "tester", WORKTREES["t-4"], repo="beta", branch="x")
            + row("a-6", "worker", SHARED, status="archived", branch="feat-a")
        )

    def etl_rows(self, worker: str = "active") -> str:
        return (
            row("coord-e", "coordinator", str((self.home / "etl").resolve()))
            + row("w-1", "worker", SHARED, status=worker, branch="feat-a")
            + row("b-3", "builder", WORKTREES["b-3"], status="done", repo="beta", branch="x")
            + row("g-5", "loader", "/wt/gamma/etl-loader", status="done", repo="gamma", branch="x")
            + row("h-7", "checker", "/wt/gamma/etl-loader", status="done", repo="gamma", branch="x")
        )

    def test_rows_of_two_streams_that_share_a_worktree_or_a_branch_alert_once_until_one_is_archived(self) -> None:
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual(
            (first.returncode, first.stdout, first.stderr),
            (0, f"{self.datapull}\tclaim=2\n{self.etl}\tclaim=2\n", ""),
        )
        self.assertEqual(self.stub.requests, [
            *observed(self.datapull, "r-2", "t-4"),
            got_status("coord-d"),
            got_prompt(
                "coord-d",
                "pi-streams tick 2026-10-06T12:00:00Z:\n"
                "claim r-2 reviewer shares worktree /wt/alpha/feat-a with etl worker w-1\n"
                "claim t-4 tester shares beta branch x with etl builder b-3",
                "followUp",
            ),
            *observed(self.etl, "w-1"),
            got_status("coord-e"),
            got_prompt(
                "coord-e",
                "pi-streams tick 2026-10-06T12:00:00Z:\n"
                "claim w-1 worker shares worktree /wt/alpha/feat-a with datapull reviewer r-2\n"
                "claim b-3 builder shares beta branch x with datapull tester t-4",
                "followUp",
            ),
        ])
        self.assertEqual(self.alerts(), ALERTS)
        self.assertEqual((self.events(self.datapull), self.events(self.etl)), (DATAPULL_EVENTS, ETL_EVENTS))
        self.assertEqual((self.state(self.datapull)["claims"], self.state(self.etl)["claims"]), (KEYS, KEYS))

        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((again.returncode, again.stdout, again.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [
            *observed(self.datapull, "r-2", "t-4"),
            *observed(self.etl, "w-1"),
        ])
        self.assertEqual(self.alerts(), ALERTS)

        (self.etl / "threads.tsv").write_text(HEADER + self.etl_rows(worker="archived"), encoding="utf-8")
        archived = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((archived.returncode, archived.stdout, archived.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [*observed(self.datapull, "r-2", "t-4"), *observed(self.etl)])
        self.assertEqual(self.alerts(), BRANCH_ALERT)
        self.assertEqual((self.events(self.datapull), self.events(self.etl)), (DATAPULL_EVENTS, ETL_EVENTS))
        self.assertEqual(
            (self.state(self.datapull)["claims"], self.state(self.etl)["claims"]),
            (KEYS[1:], KEYS[1:]),
        )

    def test_a_stream_whose_rows_do_not_read_leaves_every_claim_as_it_was(self) -> None:
        self.assertEqual(self.tick("2026-10-06T12:00:00Z").stdout, f"{self.datapull}\tclaim=2\n{self.etl}\tclaim=2\n")
        rows = self.datapull / "threads.tsv"
        rows.write_text("session\trole\n", encoding="utf-8")
        (self.etl / "threads.tsv").write_text(HEADER + self.etl_rows(worker="archived"), encoding="utf-8")
        broken = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((broken.returncode, broken.stdout, broken.stderr), (
            1,
            f"{self.datapull}\ttick-error=1\n",
            f"{self.datapull}: {rows} has an unexpected header\n",
        ))
        self.assertEqual(self.alerts(), ALERTS)
        self.assertEqual(self.state(self.etl)["claims"], KEYS)

        rows.write_text(HEADER + self.datapull_rows(), encoding="utf-8")
        mended = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((mended.returncode, mended.stdout, mended.stderr), (0, "", ""))
        self.assertEqual(self.alerts(), BRANCH_ALERT)
        self.assertEqual(
            (self.events(self.datapull), self.events(self.etl)),
            (
                DATAPULL_EVENTS + '{"at": "2026-10-06T12:05:00Z", "kind": "tick-error", "session": "", "role": "", '
                f'"detail": "{rows} has an unexpected header"}}\n',
                ETL_EVENTS,
            ),
        )


if __name__ == "__main__":
    unittest.main()

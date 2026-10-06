"""tick archives a closed stream's coordinator once pi-web would accept it."""
from __future__ import annotations

import unittest

from support import git
from tick_support import HEADER, TickCase, got_post, got_status, row, status


class ClosedStreamTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.etl = self.make_stream(
            self.home,
            "etl",
            row("coord-1", "coordinator", str((self.home / "etl").resolve()), status="done")
            + row("t-1", "datapull", "/wt/datapull", status="archived"),
        )

    def test_a_done_coordinator_is_archived_once_it_stops_working(self) -> None:
        done = HEADER + row("coord-1", "coordinator", str(self.etl), status="done")
        done += row("t-1", "datapull", "/wt/datapull", status="archived")
        self.stub.set_routes([("GET", "/api/sessions/coord-1/status", 200, status("coord-1", streaming=True))])
        streaming = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((streaming.returncode, streaming.stdout, streaming.stderr), (0, "", ""))
        self.assertEqual(self.stub.requests, [got_status("coord-1")])
        self.assertEqual(self.rows(self.etl), done)

        self.stub.set_routes([("GET", "/api/sessions/coord-1/status", 200, {**status("coord-1"), "isCompacting": True})])
        compacting = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((compacting.returncode, compacting.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [got_status("coord-1")])
        self.assertEqual(self.rows(self.etl), done)

        self.stub.set_routes([("GET", "/api/sessions/coord-1/status", 200, status("coord-1"))])
        idle = self.tick("2026-10-06T12:10:00Z")
        self.assertEqual((idle.returncode, idle.stdout, idle.stderr), (0, f"{self.etl}\tarchived=1\n", ""))
        self.assertEqual(self.stub.requests, [got_status("coord-1"), got_post("coord-1", "archive")])
        self.assertEqual(
            self.rows(self.etl),
            HEADER
            + row("coord-1", "coordinator", str(self.etl), status="archived")
            + row("t-1", "datapull", "/wt/datapull", status="archived"),
        )
        self.assertEqual(
            self.events(self.etl),
            '{"at": "2026-10-06T12:10:00Z", "kind": "archived", "session": "coord-1", "role": "coordinator", '
            '"detail": ""}\n',
        )
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

        after = self.tick("2026-10-06T12:15:00Z")
        self.assertEqual((after.returncode, after.stdout), (0, ""))
        self.assertEqual(self.stub.requests, [])


if __name__ == "__main__":
    unittest.main()

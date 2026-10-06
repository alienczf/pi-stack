"""close needs every open thread's handover, archives the threads, and marks the coordinator done."""
from __future__ import annotations

import unittest

from support import EngineCase, git

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
WHEN = "2026-10-06T00:00:00Z"


def row(sid: str, role: str, status: str) -> str:
    repo = "" if role == "coordinator" else "alpha"
    return f"{sid}\t{role}\t{repo}\t/wt/{role}\t\t\topenai-codex/gpt-6-astra\txhigh\t{status}\t{WHEN}\n"


ROWS = (
    HEADER
    + row("coord-1", "coordinator", "active")
    + row("t-1", "datapull", "active")
    + row("t-2", "review", "done")
    + row("t-0", "scout", "archived")
)
BUSY = {"error": "Stop current session activity before archiving"}


class CloseTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stream_dir = self.home / "etl"
        (self.stream_dir / "handover").mkdir(parents=True)
        (self.stream_dir / "STREAM.md").write_text("ratified: 2026-10-06 yes\n", encoding="utf-8")
        (self.stream_dir / "threads.tsv").write_text(ROWS, encoding="utf-8")
        (self.stream_dir / "handover" / "datapull.md").write_text("intent: pull\n", encoding="utf-8")
        self.stub.requests.clear()

    def statuses(self) -> list[str]:
        lines = (self.stream_dir / "threads.tsv").read_text(encoding="utf-8").splitlines()[1:]
        return [f"{line.split(chr(9))[0]} {line.split(chr(9))[8]}" for line in lines]

    def test_refuses_without_every_open_threads_handover(self) -> None:
        (self.stream_dir / "handover" / "review.md").write_text("  \n", encoding="utf-8")
        refused = self.run_streams("close", "etl")
        self.assertEqual(refused.returncode, 1)
        self.assertEqual(refused.stderr, "stream etl has no handover/review.md\n")
        self.assertEqual(self.stub.requests, [])
        self.assertEqual((self.stream_dir / "threads.tsv").read_text(encoding="utf-8"), ROWS)

    def test_archives_open_threads_and_marks_the_coordinator_done(self) -> None:
        (self.stream_dir / "handover" / "review.md").write_text("intent: review\n", encoding="utf-8")
        closed = self.run_streams("close", "etl")
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertEqual(closed.stdout, "archived t-1 datapull\narchived t-2 review\ndone coord-1 coordinator\n")
        self.assertEqual(self.stub.requests, [
            ("POST", "/api/sessions/t-1/archive", "", {}),
            ("POST", "/api/sessions/t-2/archive", "", {}),
        ])
        self.assertEqual(self.statuses(), ["coord-1 done", "t-1 archived", "t-2 archived", "t-0 archived"])
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s").strip(), "pi-streams close etl")
        self.assertEqual(
            git(self.home, self.env, "ls-files", "etl/handover").splitlines(),
            ["etl/handover/datapull.md", "etl/handover/review.md"],
        )
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")

    def test_rerun_after_a_busy_thread_archives_only_what_is_left(self) -> None:
        (self.stream_dir / "handover" / "review.md").write_text("intent: review\n", encoding="utf-8")
        self.stub.set_routes([("POST", "/api/sessions/t-2/archive", 409, BUSY)])
        stopped = self.run_streams("close", "etl")
        self.assertEqual(stopped.returncode, 1)
        self.assertIn("Stop current session activity before archiving", stopped.stderr)
        self.assertEqual(self.statuses(), ["coord-1 active", "t-1 archived", "t-2 done", "t-0 archived"])
        self.stub.requests.clear()
        self.stub.set_routes([])
        closed = self.run_streams("close", "etl")
        self.assertEqual(closed.returncode, 0, closed.stderr)
        self.assertEqual(closed.stdout, "archived t-2 review\ndone coord-1 coordinator\n")
        self.assertEqual(self.stub.requests, [("POST", "/api/sessions/t-2/archive", "", {})])
        self.assertEqual(self.statuses(), ["coord-1 done", "t-1 archived", "t-2 archived", "t-0 archived"])
        self.assertEqual(git(self.home, self.env, "log", "-1", "--format=%s").strip(), "pi-streams close etl")


if __name__ == "__main__":
    unittest.main()

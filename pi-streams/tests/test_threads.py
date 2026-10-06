"""Thread rows, the status table, and threads.tsv bytes."""
from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine.threads import Status, Thread, load_threads, save_threads, transition

ALLOWED = {
    Status.active: {Status.waiting_quota, Status.done, Status.archived},
    Status.waiting_quota: {Status.active, Status.archived},
    Status.done: {Status.archived},
    Status.archived: set(),
}

TSV = (
    "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
    "sess-1\tcoordinator\t\t/stream\t\t\topenai-codex/gpt-6-astra\txhigh\tactive\t2026-10-06T01:02:03Z\n"
    "sess-2\tdatapull\talpha\t/wt\tstream/etl/datapull\tabc\topenai-codex/gpt-6-astra\txhigh\tdone\t2026-10-06T01:02:04Z\n"
)


class TransitionTests(unittest.TestCase):
    def test_table_accepts_and_rejects(self) -> None:
        for current in Status:
            for new in Status:
                row = Thread(
                    "sess-1",
                    "datapull",
                    "alpha",
                    "/wt",
                    "stream/etl/datapull",
                    "abc",
                    "openai-codex/gpt-6-astra",
                    "xhigh",
                    current,
                    "2026-10-06T00:00:00Z",
                )
                if new in ALLOWED[current]:
                    transition(row, new)
                    self.assertIs(row.status, new)
                else:
                    with self.assertRaises(ValueError):
                        transition(row, new)
                    self.assertIs(row.status, current)


class ThreadsFileTests(unittest.TestCase):
    def test_literal_tsv(self) -> None:
        directory = Path(tempfile.mkdtemp(prefix="pi-streams-tsv-"))
        self.addCleanup(lambda: shutil.rmtree(directory, ignore_errors=True))
        path = directory / "threads.tsv"
        path.write_text(TSV, encoding="utf-8")
        rows = load_threads(path)
        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].session, "sess-1")
        self.assertEqual(rows[0].role, "coordinator")
        self.assertEqual(rows[0].repo, "")
        self.assertEqual(rows[0].worktree, "/stream")
        self.assertEqual(rows[0].branch, "")
        self.assertEqual(rows[0].base, "")
        self.assertEqual(rows[0].model, "openai-codex/gpt-6-astra")
        self.assertEqual(rows[0].thinking, "xhigh")
        self.assertEqual(rows[0].status, Status.active)
        self.assertEqual(rows[0].started, "2026-10-06T01:02:03Z")
        self.assertEqual(rows[1].session, "sess-2")
        self.assertEqual(rows[1].role, "datapull")
        self.assertEqual(rows[1].repo, "alpha")
        self.assertEqual(rows[1].worktree, "/wt")
        self.assertEqual(rows[1].branch, "stream/etl/datapull")
        self.assertEqual(rows[1].base, "abc")
        self.assertEqual(rows[1].status, Status.done)
        self.assertEqual(rows[1].started, "2026-10-06T01:02:04Z")
        save_threads(path, rows)
        self.assertEqual(path.read_text(encoding="utf-8"), TSV)


if __name__ == "__main__":
    unittest.main()

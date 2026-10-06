"""Template bytes the engine copies into a project home and a stream."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PROJECT = ROOT / "pi-streams" / "templates" / "project"
STREAM = ROOT / "pi-streams" / "templates" / "stream"

AGENTS = """\
You are the coordinator of the stream whose folder is your working directory. You never write product code.

On every turn:
1. Read STREAM.md, STATE.md, the newest lines of log/events.jsonl, and ../context/README.md.
2. Act only within STREAM.md's AUTONOMY section. Anything else, ask ZF with options and a recommended default, and continue on the default.
3. Delegate with `pi-streams thread spawn` and steer with `pi-web-cli prompt --steer`. Never resume a thread just to check on it; read `pi-web-cli status`.
4. Accept done only when the matching checks/ script passes. Check that a new thread's first reply restates its brief correctly.
5. Rewrite STATE.md before ending the turn.

Relay numbers only from check output or files, with their path.
"""

STREAM_MD = """\
ratified: no

GOAL
<what this stream delivers>

TARGET
<the artifact and its pin>

ACCEPTANCE
<named checks and what passing means>

E2E PATH
<the path on the real artifact>

WRITES
<what this stream may change>

END STATE
<what is true when the stream is finished>

AUTONOMY
<what the coordinator may do alone>

NO-GO
<what this stream must not do>
"""


class TemplateTests(unittest.TestCase):
    def test_project_template(self) -> None:
        self.assertEqual((PROJECT / "AGENTS.md").read_text(encoding="utf-8"), AGENTS)
        self.assertEqual((PROJECT / ".gitignore").read_text(encoding="utf-8"), "*/log/\n")
        self.assertEqual((PROJECT / "ALERTS").read_bytes(), b"")
        self.assertEqual((PROJECT / "context" / "README.md").read_text(encoding="utf-8"), "# Shared context\n")

    def test_stream_template(self) -> None:
        self.assertEqual((STREAM / "STREAM.md").read_text(encoding="utf-8"), STREAM_MD)
        self.assertEqual((STREAM / "STATE.md").read_text(encoding="utf-8"), "# STATE\n\nplan:\nopen threads:\nwaiting-on:\nnext step:\n")
        self.assertEqual((STREAM / "DECISIONS.md").read_text(encoding="utf-8"), "# DECISIONS\n")
        self.assertEqual(
            (STREAM / "threads.tsv").read_text(encoding="utf-8"),
            "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n",
        )
        self.assertEqual(
            (STREAM / "subscriptions.tsv").read_text(encoding="utf-8"),
            "id\tsource\ttarget\twhen\taction\n",
        )
        self.assertEqual((STREAM / "checks" / ".gitkeep").read_bytes(), b"")
        self.assertEqual((STREAM / "handover" / ".gitkeep").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()

"""Template bytes and artifact names copied into a canonical stream repo."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STREAM = ROOT / "pi-streams" / "templates" / "stream"

AGENTS = """\
You coordinate this stream. You never write product code.
Do not use TODO.md or PLAN.md in a pi-streams role. Goals plus Log in STATE.md replace them.

On every turn:
1. Read AGENTS.md and STATE.md.
2. Follow the current Goals, Charter, and active Rules. Decide reversible details within the explicit grant. Stop before an unauthorized action and report the required decision. Silence is not permission.
3. Delegate with `pi-streams thread spawn` and steer with `pi-web-cli prompt --steer`. Inspect `pi-streams status <stream-id> --json` or `pi-web-cli status`; never resume a thread merely to check it.
4. Verify the requested acceptance on the real artifact. Reuse existing checks when sufficient. Do not demand a new check script for every small ask.
5. Append completed work, failures, and new ZF steers through `pi-streams state append <stream-id> --subject SUBJECT --body-file - --request-id ID`. Keep the request ID stable on retry. These receipts prove artifact recording, not steer application.

Update only the current objective with `pi-streams state objective <stream-id> --body-file -`. North Star and Charter change only with human authorization. A finished objective never completes the North Star.
Use `pi-streams state ruling <stream-id> --subject SUBJECT --body-file - --notice-id NOTICE` only for a sourced human ruling. Retire superseded text through the engine with its exact source span, never by hiding an active rule in history.

On demand, open history/, context/ and its context/README.md index, checks/, or handover/. They are not per-turn reads.
Never read engine-only registries, threads.tsv, subscriptions.tsv, stream.toml, events, tick-state, locks, or failures/. Use CLI views instead.
Only Log is capped at 30 entries. The engine rotates overflow every tick; agents never prune or rotate it. Goals and Rules are rewritten in place, not appended as history.
No resource cap or spend budget applies unless the incoming task explicitly supplies it.
For environment/auth/resource failures, stop affected task effects, log, and report. Do not self-remedy the environment or author remedial rules, skills, or memory without explicit human instructions.
Relay numbers only with their actual check output or source path.
"""

STATE_MD = """\
## Goals
ratified: no

### North Star
<the single human-authorized outcome>

### Current objective

### Charter
TARGET
<artifact references and pins>

ACCEPTANCE
<human-agreed oracle and any explicitly required checks>

E2E PATH
<authorized end-to-end verification path>

WRITES
<authorized locations and effects>

END STATE
<the requested result and any authorized cleanup>

AUTONOMY
<the explicit decision grant>

NO-GO
<prohibitions that remain in force>

## Rules

## Log
"""


class TemplateTests(unittest.TestCase):
    def test_stream_template(self) -> None:
        self.assertEqual((STREAM / "AGENTS.md").read_text(encoding="utf-8"), AGENTS)
        self.assertEqual((STREAM / "STATE.md").read_text(encoding="utf-8"), STATE_MD)
        self.assertEqual((STREAM / ".gitignore").read_text(encoding="utf-8"), "log/\n")
        self.assertEqual((STREAM / "context" / "README.md").read_text(encoding="utf-8"), "# Shared context\n")
        for retired in ("STREAM.md", "DECISIONS.md", "GOAL.md", "ACTIONS.md", "TODO.md", "PLAN.md"):
            self.assertFalse((STREAM / retired).exists(), retired)
        self.assertEqual(
            (STREAM / "threads.tsv").read_text(encoding="utf-8"),
            "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n",
        )
        self.assertEqual(
            (STREAM / "subscriptions.tsv").read_text(encoding="utf-8"),
            "id\tsource\ttarget\twhen\taction\n",
        )
        for directory in ("checks", "handover", "history", "failures"):
            self.assertEqual((STREAM / directory / ".gitkeep").read_bytes(), b"")


if __name__ == "__main__":
    unittest.main()

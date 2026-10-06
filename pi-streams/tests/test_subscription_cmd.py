"""A cmd subscription past its timeout fails fast and leaves no process behind."""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from engine import StreamsError, subscriptions
from engine.subscriptions import Subscription


def _alive(pid: int) -> bool:
    try:
        stat = Path(f"/proc/{pid}/stat").read_text(encoding="utf-8")
    except FileNotFoundError:
        return False
    return stat.rsplit(")", 1)[1].split()[0] != "Z"


class CmdTimeoutTests(unittest.TestCase):
    def test_a_cmd_past_its_timeout_is_killed_with_its_children(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stream_dir = Path(tmp)
            # The background sleep keeps stdout open even after bash is killed.
            sub = Subscription("slow", "cmd", "sleep 30 & echo $! >child.pid; wait", "", "check")
            started = time.monotonic()
            with mock.patch.object(subscriptions, "TIMEOUT_SECONDS", 1):
                with self.assertRaises(StreamsError) as caught:
                    subscriptions.read_cmd(sub, stream_dir, datetime.now(timezone.utc))
            self.assertLess(time.monotonic() - started, 10)
            self.assertEqual(str(caught.exception), "timed out after 1 s")
            child = int((stream_dir / "child.pid").read_text(encoding="utf-8"))
            deadline = time.monotonic() + 5
            while _alive(child) and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(_alive(child))


if __name__ == "__main__":
    unittest.main()

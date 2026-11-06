from __future__ import annotations

import copy
import importlib.util
from pathlib import Path
import unittest


class RecoveryLeverTests(unittest.TestCase):
    def test_cleanup_requires_supported_stream_and_session_dispositions(self):
        path = Path(__file__).resolve().parents[2] / "scripts/check-pr55-recovery.py"
        spec = importlib.util.spec_from_file_location("recovery_lever", path)
        lever = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(lever)
        clean = {"processStopped": True, "pathRemoved": True, "streams": [{"closed": True}], "sessions": [{"state": "archived"}]}
        self.assertTrue(lever.cleanup_ok(clean))
        for change in ({"streams": [{"closed": False}]}, {"sessions": [{"state": "archive-refused"}]},
                       {"error": "lost cleanup proof"}, {"processStopped": False}, {"pathRemoved": False}):
            with self.subTest(change=change):
                self.assertFalse(lever.cleanup_ok({**copy.deepcopy(clean), **change}))

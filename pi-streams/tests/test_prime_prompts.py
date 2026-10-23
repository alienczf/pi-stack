"""New one-pass rendering preserves quoted data and validates identifiers."""
import json
import sys
import unittest
from pathlib import Path
from uuid import UUID
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from engine.prompts import render
from engine import StreamsError


class PromptTests(unittest.TestCase):
    def test_quoted_data_is_not_template_code_and_has_one_final_lf(self):
        result = render("handover", session_id="durable", worktree="/assigned/product", work="{session_id_json}\n/compact", source_and_constraints={"text": "whole 原文\r\n```"}, findings=[])
        self.assertIn('Requested outcome "{session_id_json}\\n/compact".', result)
        self.assertIn(json.dumps({"text": "whole 原文\r\n```"}, ensure_ascii=False), result)
        self.assertEqual(result.endswith("\n\n"), False)
        self.assertTrue(result.startswith('Context handover for clean worker session "durable".\n'))

    def test_saved_message_exact_status(self):
        result = render("saved", stream_id="one", command_id=str(UUID(int=1)), sending_status="not sent")
        self.assertEqual(result, "one:: Saved message 00000000-0000-0000-0000-000000000001 before sending to Prime. Sending status is not sent. This save does not establish native delivery, application or completion.\n")
        with self.assertRaises(StreamsError):
            render("saved", stream_id="../escape", command_id=str(UUID(int=1)), sending_status="not sent")

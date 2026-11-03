from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from support import ROOT
sys.path.insert(0, str(ROOT / "pi-streams"))
from engine import sessionlog


class ShellEffectsTests(unittest.TestCase):
    def test_exact_branch_shell_effects_match_shared_cases(self):
        cases = json.loads((Path(__file__).parent / "fixtures/shell-effects.json").read_text())
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "owned.jsonl"
            for case in cases:
                with self.subTest(case=case["name"]):
                    messages = [{"role": "assistant", "stopReason": "toolUse", "content": [{"type": "toolCall", "id": "owned", "name": "bash", "arguments": {"command": case["command"]}}]}]
                    if case["result"] is not None:
                        messages.append(case["result"])
                    messages.append({"role": "assistant", "stopReason": "error", "provider": "openai-codex", "model": "gpt-6.1-sol", "errorMessage": "Controlled terminal provider error"})
                    entries = [{"type": "session", "id": "shell-fixture", "cwd": temporary}]
                    for index, message in enumerate(messages):
                        entries.append({"type": "message", "id": str(index), "parentId": str(index - 1) if index else None, "message": message})
                    path.write_text("".join(json.dumps(entry) + "\n" for entry in entries))
                    observation = sessionlog.failure_observation(path, "shell-fixture", temporary, str(len(messages) - 1))
                    self.assertEqual(observation["entryId"], str(len(messages) - 1))
                    self.assertEqual(observation["uncertainJobs"], case["uncertainJobs"])

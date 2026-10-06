"""Every pi-streams and pi-web-cli command named in the stream prose exists, with its flags."""
from __future__ import annotations

import os
import re
import subprocess
import unittest

from support import ROOT

PROSE = (
    "skills/stream/SKILL.md",
    "skills/stream-kickoff/SKILL.md",
    "prompts/stream.md",
    "prompts/thread-brief.md",
    "pi-streams/templates/project/AGENTS.md",
)
COMMAND = re.compile(r"`((?:pi-streams|pi-web-cli) [^`]+)`")


def named_commands() -> list[str]:
    found: list[str] = []
    for name in PROSE:
        found.extend(COMMAND.findall((ROOT / name).read_text(encoding="utf-8")))
    return found


def command_path(snippet: str) -> list[str]:
    words = snippet.split()
    depth = 3 if words[:2] == ["pi-streams", "thread"] else 2
    return words[:depth]


class ProseCommandTests(unittest.TestCase):
    def test_the_prose_names_these_commands(self) -> None:
        self.assertEqual(sorted({" ".join(command_path(item)) for item in named_commands()}), [
            "pi-streams close",
            "pi-streams new",
            "pi-streams status",
            "pi-streams thread adopt",
            "pi-streams thread spawn",
            "pi-web-cli answer",
            "pi-web-cli list",
            "pi-web-cli messages",
            "pi-web-cli prompt",
            "pi-web-cli status",
        ])

    def test_each_named_command_and_flag_exists(self) -> None:
        env = {"PATH": "/usr/bin:/bin", "PI_WEB_URL": "http://127.0.0.1:9", "LANG": "C.UTF-8"}
        for snippet in named_commands():
            path = command_path(snippet)
            with self.subTest(snippet=snippet):
                proc = subprocess.run(
                    [os.fspath(ROOT / "bin" / path[0]), *path[1:], "--help"],
                    env=env,
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    check=False,
                )
                self.assertEqual(proc.returncode, 0, proc.stderr)
                for flag in [word for word in snippet.split() if word.startswith("--")]:
                    self.assertIn(flag, proc.stdout)


if __name__ == "__main__":
    unittest.main()

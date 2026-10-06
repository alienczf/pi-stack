"""tick pushes the project home when it has a remote and is ahead of it."""
from __future__ import annotations

import shutil
import unittest

from support import git
from tick_support import TickCase, info, row, status


class PushTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.remote = self.tmp / "streams.git"
        toml = self.home / "project.toml"
        text = toml.read_text(encoding="utf-8")
        self.assertEqual(text.count('remote = ""\n'), 1)
        toml.write_text(text.replace('remote = ""\n', f'remote = "{self.remote}"\n'), encoding="utf-8")
        etl = str((self.home / "etl").resolve())
        self.etl = self.make_stream(self.home, "etl", row("coord-1", "coordinator", etl) + row("t-1", "datapull", "/wt/datapull"))
        git(self.home, self.env, "add", "-A")
        git(self.home, self.env, "commit", "-m", "remote and stream")
        self.branch = git(self.home, self.env, "branch", "--show-current").strip()
        self.stub.set_routes([
            ("GET", "/api/sessions/t-1/status", 200, status("t-1", streaming=True)),
            ("GET", "/api/sessions", 200, [
                info("coord-1", etl, self.log_path("coord-1")),
                info("t-1", "/wt/datapull", self.log_path("t-1")),
            ]),
        ])

    def test_tick_pushes_the_home_only_when_it_is_ahead(self) -> None:
        git(self.tmp, self.env, "init", "--bare", "--quiet", str(self.remote))
        first = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((first.returncode, first.stdout, first.stderr), (0, "", ""))
        head = git(self.home, self.env, "rev-parse", "HEAD")
        self.assertEqual(git(self.remote, self.env, "rev-parse", self.branch), head)
        self.assertEqual(git(self.home, self.env, "remote", "get-url", "origin"), f"{self.remote}\n")

        shutil.rmtree(self.remote)
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((again.returncode, again.stdout, again.stderr), (0, "", ""))
        self.assertEqual(git(self.home, self.env, "rev-parse", "HEAD"), head)

    def test_a_push_that_fails_fails_the_tick(self) -> None:
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (1, ""))
        self.assertTrue(proc.stderr.startswith(f"{self.home.resolve()}: "), proc.stderr)
        self.assertIn(str(self.remote), proc.stderr)
        self.assertEqual(git(self.home, self.env, "status", "--porcelain"), "")


if __name__ == "__main__":
    unittest.main()

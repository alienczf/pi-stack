"""tick pushes a stream repo when stream.toml names a remote and HEAD is ahead."""
from __future__ import annotations

import shutil
import unittest

from support import git
from tick_support import TickCase, info, row, status


class PushTests(TickCase):
    def setUp(self) -> None:
        super().setUp()
        self.remote = self.tmp / "streams.git"
        etl = str((self.home / "etl").resolve())
        self.etl = self.make_stream(self.home, "etl", row("coord-1", "coordinator", etl) + row("t-1", "datapull", "/wt/datapull"))
        toml = self.etl / "stream.toml"
        text = toml.read_text(encoding="utf-8")
        self.assertNotIn("remote = ", text)
        toml.write_text(text + f'remote = "{self.remote}"\n', encoding="utf-8")
        git(self.etl, self.env, "add", "-A")
        git(self.etl, self.env, "commit", "-m", "remote")
        self.branch = git(self.etl, self.env, "branch", "--show-current").strip()
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
        head = git(self.etl, self.env, "rev-parse", "HEAD")
        self.assertEqual(git(self.remote, self.env, "rev-parse", self.branch), head)
        self.assertEqual(git(self.etl, self.env, "remote", "get-url", "origin"), f"{self.remote}\n")

        shutil.rmtree(self.remote)
        again = self.tick("2026-10-06T12:05:00Z")
        self.assertEqual((again.returncode, again.stdout, again.stderr), (0, "", ""))
        self.assertEqual(git(self.etl, self.env, "rev-parse", "HEAD"), head)

    def test_a_push_that_fails_fails_the_tick(self) -> None:
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (1, ""))
        self.assertTrue(proc.stderr.startswith(f"{self.etl}: "), proc.stderr)
        self.assertIn(str(self.remote), proc.stderr)
        self.assertEqual(git(self.etl, self.env, "status", "--porcelain"), "")

    def test_tick_will_not_push_to_an_origin_stream_toml_does_not_name(self) -> None:
        other = self.tmp / "other.git"
        for bare in (self.remote, other):
            git(self.tmp, self.env, "init", "--bare", "--quiet", str(bare))
        git(self.etl, self.env, "remote", "add", "origin", str(other))
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (1, ""))
        self.assertEqual(
            proc.stderr,
            f"{self.etl}: origin is {other}, but stream.toml names remote {self.remote}\n",
        )
        for bare in (self.remote, other):
            self.assertEqual(git(bare, self.env, "for-each-ref"), "")

    def test_tick_will_not_push_a_detached_head(self) -> None:
        git(self.tmp, self.env, "init", "--bare", "--quiet", str(self.remote))
        git(self.etl, self.env, "checkout", "--quiet", "--detach")
        proc = self.tick("2026-10-06T12:00:00Z")
        self.assertEqual((proc.returncode, proc.stdout), (1, ""))
        self.assertEqual(
            proc.stderr,
            f"{self.etl}: HEAD is detached, so tick cannot push it to {self.remote}\n",
        )
        self.assertEqual(git(self.remote, self.env, "for-each-ref"), "")


if __name__ == "__main__":
    unittest.main()

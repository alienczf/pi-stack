"""pi-streams doctor prints PASS and FAIL lines."""
from __future__ import annotations

import os
import urllib.parse

from support import EngineCase

SKILLS = (
    "correct",
    "reflect",
    "create-verification-skill",
    "maintain-verification-skill",
)


class DoctorTests(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stub.requests.clear()
        log = self.home / "etl" / "log"
        log.mkdir(parents=True)
        (log / "events.jsonl").write_text("{}\n", encoding="utf-8")
        base = self.user_home / ".pi" / "agent" / "skills-pstack"
        for name in SKILLS:
            dest = base / name
            dest.mkdir(parents=True)
            (dest / "SKILL.md").write_text("# skill\n", encoding="utf-8")

    def _pi_on_path(self) -> str:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        pi = bindir / "pi"
        pi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pi.chmod(0o755)
        self.env["PATH"] = f"{bindir}{os.pathsep}/usr/bin:/bin"
        return str(pi.resolve())

    def _lines(self, pi: str, pi_web: str) -> str:
        home = str(self.home.resolve())
        return (
            f"PASS pi: found at {pi}\n"
            f"{pi_web}\n"
            "PASS steer: prompt accepts --steer\n"
            f"PASS home: {home} is a clean git repo and project.toml parses\n"
            "PASS skills: present\n"
        )

    def test_doctor_pass(self) -> None:
        pi = self._pi_on_path()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, self._lines(pi, "PASS pi-web: list ok"))
        method, path, query, body = self.stub.requests[0]
        self.assertEqual(method, "GET")
        self.assertEqual(path, "/api/sessions")
        self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [str(self.home.resolve())]})
        self.assertIsNone(body)

    def test_doctor_fail_when_stub_is_down(self) -> None:
        pi = self._pi_on_path()
        self.stub.stop()
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, self._lines(pi, "FAIL pi-web: list failed"))

    def test_doctor_warns_about_jig_and_leaves_it(self) -> None:
        pi = self._pi_on_path()
        jig = self.fx.alpha / ".pi" / "jig"
        jig.mkdir(parents=True)
        (jig / "state").write_text("kept\n", encoding="utf-8")
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok") + "WARN jig: alpha still holds .pi/jig/ (left alone)\n",
        )
        self.assertEqual((jig / "state").read_text(encoding="utf-8"), "kept\n")

    def test_doctor_finds_pi_under_pi_node(self) -> None:
        pi = self.user_home / ".local" / "share" / "pi-node" / "bin" / "pi"
        pi.parent.mkdir(parents=True)
        pi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pi.chmod(0o755)
        self.env["PATH"] = "/usr/bin:/bin"
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, self._lines(str(pi.resolve()), "PASS pi-web: list ok"))


if __name__ == "__main__":
    unittest.main()

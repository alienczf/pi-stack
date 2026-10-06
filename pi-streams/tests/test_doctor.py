"""pi-streams doctor prints PASS and FAIL lines."""
from __future__ import annotations

import json
import os
import time
import urllib.parse

from support import EngineCase, git

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
        unit_dir = self.xdg / "systemd" / "user"
        unit_dir.mkdir(parents=True)
        for name in ("pi-streams-tick.service", "pi-streams-tick.timer"):
            (unit_dir / name).write_text("unit\n", encoding="utf-8")
        self._write_projects([str(self.root.resolve())])

    def _write_projects(self, paths: list[str]) -> None:
        projects = self.user_home / ".pi-web" / "projects.json"
        projects.parent.mkdir(parents=True, exist_ok=True)
        projects.write_text(
            json.dumps(
                {
                    "projects": [
                        {
                            "id": f"p{index}",
                            "name": f"proj{index}",
                            "path": path,
                            "createdAt": "2026-10-06T00:00:00Z",
                        }
                        for index, path in enumerate(paths)
                    ]
                }
            )
            + "\n",
            encoding="utf-8",
        )

    def _add_stream(self, name: str = "etl") -> Path:
        stream = self.home / name
        (stream / "log").mkdir(parents=True, exist_ok=True)
        (stream / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        git(self.home, self.env, "add", "-A")
        git(self.home, self.env, "commit", "-m", "stream")
        return stream

    def _pi_on_path(self) -> str:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        pi = bindir / "pi"
        pi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pi.chmod(0o755)
        self.env["PATH"] = f"{bindir}{os.pathsep}/usr/bin:/bin"
        return str(pi.resolve())

    def _report(self, pi: str, pi_web: str, tail: str) -> str:
        home = str(self.home.resolve())
        return (
            f"PASS pi: found at {pi}\n"
            f"{pi_web}\n"
            "PASS steer: prompt accepts --steer\n"
            f"PASS home: {home} is a clean git repo and project.toml parses\n"
            "PASS skills: present\n"
            f"{tail}"
        )

    def _lines(self, pi: str, pi_web: str, extra: str = "") -> str:
        return self._report(
            pi,
            pi_web,
            extra + "PASS systemd: pi-streams-tick.service and pi-streams-tick.timer are installed\n",
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
            self._lines(pi, "PASS pi-web: list ok", "WARN jig: alpha still holds .pi/jig/ (left alone)\n"),
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

    def test_doctor_fails_when_tick_units_are_missing(self) -> None:
        pi = self._pi_on_path()
        unit_dir = self.xdg / "systemd" / "user"
        for name in ("pi-streams-tick.service", "pi-streams-tick.timer"):
            (unit_dir / name).unlink()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(
            proc.stdout,
            self._report(pi, "PASS pi-web: list ok", "FAIL systemd: missing pi-streams-tick.service, pi-streams-tick.timer\n"),
        )

    def test_doctor_names_the_one_missing_tick_unit(self) -> None:
        pi = self._pi_on_path()
        (self.xdg / "systemd" / "user" / "pi-streams-tick.timer").unlink()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(
            proc.stdout,
            self._report(pi, "PASS pi-web: list ok", "FAIL systemd: missing pi-streams-tick.timer\n"),
        )

    def test_doctor_warns_when_a_stream_has_no_tick_state(self) -> None:
        pi = self._pi_on_path()
        self._add_stream()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + "WARN tick: no tick-state.json under any home is newer than 15 minutes\n",
        )

    def test_doctor_warns_when_tick_state_is_older_than_15_minutes(self) -> None:
        pi = self._pi_on_path()
        state = self._add_stream() / "log" / "tick-state.json"
        state.write_text("{}\n", encoding="utf-8")
        old = time.time() - (16 * 60)
        os.utime(state, (old, old))
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + "WARN tick: no tick-state.json under any home is newer than 15 minutes\n",
        )

    def test_doctor_accepts_a_fresh_tick_state(self) -> None:
        pi = self._pi_on_path()
        state = self._add_stream() / "log" / "tick-state.json"
        state.write_text("{}\n", encoding="utf-8")
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, self._lines(pi, "PASS pi-web: list ok"))

    def test_doctor_warns_when_home_is_outside_pi_web_projects(self) -> None:
        pi = self._pi_on_path()
        path = self.user_home / ".pi-web" / "projects.json"
        self._write_projects(["/tmp/pi-streams-other-project"])
        before = path.read_bytes()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        home = str(self.home.resolve())
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + f"WARN pi-web-project: {home} is not inside a directory listed in ~/.pi-web/projects.json\n",
        )
        self.assertEqual(path.read_bytes(), before)

    def test_doctor_warns_when_projects_json_is_missing_and_does_not_create_it(self) -> None:
        pi = self._pi_on_path()
        path = self.user_home / ".pi-web" / "projects.json"
        path.unlink()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        home = str(self.home.resolve())
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + f"WARN pi-web-project: {home} is not inside a directory listed in ~/.pi-web/projects.json\n",
        )
        self.assertFalse(path.exists())

    def test_doctor_accepts_a_home_registered_as_its_own_pi_web_project(self) -> None:
        pi = self._pi_on_path()
        self._write_projects([str(self.home.resolve())])
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, self._lines(pi, "PASS pi-web: list ok"))


if __name__ == "__main__":
    unittest.main()

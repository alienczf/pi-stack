"""pi-streams doctor prints PASS and FAIL lines."""
from __future__ import annotations

import json
import os
import shutil
import time
import urllib.parse

from support import EngineCase, git, pi_stack_revision

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
        stream = self.register_stream(name)
        (stream / "log").mkdir(parents=True, exist_ok=True)
        (stream / "STREAM.md").write_text("ratified: no\n", encoding="utf-8")
        (stream / ".gitignore").write_text("log/\n", encoding="utf-8")
        (stream / "stream.toml").write_text(
            f'project = "{self.root.name}"\npi_stack_revision = "{pi_stack_revision()}"\n',
            encoding="utf-8",
        )
        if not (stream / "threads.tsv").is_file():
            (stream / "threads.tsv").write_text(
                "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n",
                encoding="utf-8",
            )
        if not (stream / ".git").exists():
            git(stream, self.env, "init", "--quiet")
        git(stream, self.env, "add", "-A")
        if git(stream, self.env, "status", "--porcelain").strip() != "":
            git(stream, self.env, "commit", "-m", "stream")
        return stream

    def _pi_on_path(self) -> str:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        for name in ("pi", "systemctl"):
            tool = bindir / name
            tool.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
            tool.chmod(0o755)
        self.env["PATH"] = f"{bindir}{os.pathsep}/usr/bin:/bin"
        return str((bindir / "pi").resolve())

    def _report(self, pi: str, pi_web: str, tail: str, streams: str = "") -> str:
        project = str(self.project_file.resolve())
        return (
            f"PASS pi: found at {pi}\n"
            f"{pi_web}\n"
            "PASS steer: prompt accepts --steer\n"
            f"PASS project: {project} parses\n"
            f"{streams}"
            "PASS skills: present\n"
            f"{tail}"
        )

    def _lines(self, pi: str, pi_web: str, extra: str = "", streams: str = "") -> str:
        return self._report(
            pi,
            pi_web,
            extra + "PASS systemd: pi-streams-tick.service and pi-streams-tick.timer are installed\n",
            streams,
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
        self.assertEqual(urllib.parse.parse_qs(query), {"cwd": [str(self.index.resolve())]})
        self.assertIsNone(body)

    def test_doctor_fail_when_stub_is_down(self) -> None:
        pi = self._pi_on_path()
        self.stub.stop()
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 1)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(proc.stdout, self._lines(pi, "FAIL pi-web: list failed"))

    def test_doctor_reaches_pi_web_from_its_config_without_pi_web_url(self) -> None:
        pi = self._pi_on_path()
        self.assertIn('pi_web_url = "http://127.0.0.1:8504"\n', self.project_file.read_text(encoding="utf-8"))
        del self.env["PI_WEB_URL"]
        config = self.user_home / ".config" / "pi-web" / "config.json"
        config.parent.mkdir(parents=True)
        port = urllib.parse.urlsplit(self.stub.url).port
        config.write_text(json.dumps({"host": "127.0.0.1", "port": port}) + "\n", encoding="utf-8")
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, self._lines(pi, "PASS pi-web: list ok"))
        self.assertEqual([(method, path) for method, path, _query, _body in self.stub.requests], [("GET", "/api/sessions")])

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

    def test_doctor_warns_without_systemctl_whether_or_not_the_units_are_there(self) -> None:
        bindir = self.tmp / "bin"
        bindir.mkdir()
        pi = bindir / "pi"
        pi.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        pi.chmod(0o755)
        for name in ("python3", "git"):
            (bindir / name).symlink_to(shutil.which(name, path="/usr/bin:/bin"))
        self.env["PATH"] = str(bindir)
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        expected = self._report(
            str(pi.resolve()),
            "PASS pi-web: list ok",
            "WARN systemd: systemctl not found, so run pi-streams tick every five minutes another way\n",
        )
        # install.sh copies the units even where systemctl is missing.
        installed = self.run_streams("doctor")
        self.assertEqual((installed.returncode, installed.stdout), (0, expected), installed.stderr)
        for name in ("pi-streams-tick.service", "pi-streams-tick.timer"):
            (self.xdg / "systemd" / "user" / name).unlink()
        missing = self.run_streams("doctor")
        self.assertEqual((missing.returncode, missing.stdout), (0, expected), missing.stderr)

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
            self._lines(
                pi,
                "PASS pi-web: list ok",
                streams=f"PASS revision: etl records {pi_stack_revision()}\n",
            )
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
            self._lines(
                pi,
                "PASS pi-web: list ok",
                streams=f"PASS revision: etl records {pi_stack_revision()}\n",
            )
            + "WARN tick: no tick-state.json under any home is newer than 15 minutes\n",
        )

    def test_doctor_accepts_a_fresh_tick_state(self) -> None:
        pi = self._pi_on_path()
        state = self._add_stream() / "log" / "tick-state.json"
        state.write_text("{}\n", encoding="utf-8")
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok", streams=f"PASS revision: etl records {pi_stack_revision()}\n"),
        )

    def test_doctor_warns_when_home_is_outside_pi_web_projects(self) -> None:
        pi = self._pi_on_path()
        path = self.user_home / ".pi-web" / "projects.json"
        self._write_projects(["/tmp/pi-streams-other-project"])
        before = path.read_bytes()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        root = str(self.root.resolve())
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + f"WARN pi-web-project: {root} is not inside a directory listed in ~/.pi-web/projects.json\n",
        )
        self.assertEqual(path.read_bytes(), before)

    def test_doctor_warns_when_projects_json_is_missing_and_does_not_create_it(self) -> None:
        pi = self._pi_on_path()
        path = self.user_home / ".pi-web" / "projects.json"
        path.unlink()
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        root = str(self.root.resolve())
        self.assertEqual(
            proc.stdout,
            self._lines(pi, "PASS pi-web: list ok")
            + f"WARN pi-web-project: {root} is not inside a directory listed in ~/.pi-web/projects.json\n",
        )
        self.assertFalse(path.exists())

    def test_doctor_accepts_a_project_root_inside_a_listed_directory(self) -> None:
        pi = self._pi_on_path()
        self._write_projects([str(self.tmp)])
        self.stub.set_routes([("GET", "/api/sessions", 200, [])])
        proc = self.run_streams("doctor")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(proc.stdout, self._lines(pi, "PASS pi-web: list ok"))


if __name__ == "__main__":
    unittest.main()

"""Executable routing, SSH quoting, and isolated installer/check-script behavior."""
from __future__ import annotations

import json
import os
from pathlib import Path
import shlex
import shutil
import socket
import subprocess
import tempfile
import threading
import unittest

from test_prime_cli import Fixture, ROOT


ECHO = '''#!/usr/bin/env python3
import json, os, sys
print(json.dumps({"tool": os.path.basename(sys.argv[0]), "argv": sys.argv[1:], "stdin": sys.stdin.read()}, ensure_ascii=False))
raise SystemExit(int(os.environ.get("ECHO_EXIT", "0")))
'''


class OwnedSupervisor:
    def __init__(self, root, fail_command=None, *, fail_after_admission=False):
        self.root = root
        self.fail_command = fail_command
        self.fail_after_admission = fail_after_admission
        self.admission_failure_sent = False
        self.pauses = set()
        self.admitted_inputs = []
        self.runnable_inputs = []
        self.events = []
        self.server = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.server.bind(str(root / "daemon.sock"))
        self.server.listen()
        self.server.settimeout(0.1)
        self.stopped = threading.Event()
        self.thread = threading.Thread(target=self.serve)
        self.workers = []
        self.requests = []
        self.queue = {"steering": [], "followUp": []}
        self.archived = False
        self.active_id = "owned-active"
        self.lock = threading.Lock()

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *_):
        self.stopped.set()
        self.thread.join(2)
        self.server.close()
        for worker in self.workers:
            worker.join(2)

    def serve(self):
        while not self.stopped.is_set():
            try:
                stream, _ = self.server.accept()
            except socket.timeout:
                continue
            worker = threading.Thread(target=self.connection, args=(stream,))
            self.workers.append(worker)
            worker.start()

    def connection(self, stream):
        owner = object()
        with stream:
            reader = stream.makefile("rb")
            try:
                stream.sendall(b'{"type":"daemon_hello","protocol":{"name":"prime-agent.daemon","version":7}}\n')
                for line in reader:
                    request = json.loads(line)
                    with self.lock:
                        self.requests.append(request["command"])
                        self.events.append(request["command"]["type"])
                        response = self.response(request["command"], owner)
                    stream.sendall((json.dumps({"type": "response", "id": request["id"], "command": request["command"]["type"], **response}) + "\n").encode())
            finally:
                reader.close()
                with self.lock:
                    if owner in self.pauses:
                        self.pauses.remove(owner)
                        self.events.append("pause_owner_disconnected")
                        self.release_runnable_inputs()

    def release_runnable_inputs(self):
        if not self.pauses:
            self.runnable_inputs.extend(self.queue["steering"] + self.queue["followUp"])
            self.queue = {"steering": [], "followUp": []}

    def response(self, command, owner):
        kind = command["type"]
        if "activeSessionId" in command and command["activeSessionId"] not in (self.active_id, "owned-durable"):
            return {"success": False, "error": "Wrong session"}
        if kind == self.fail_command:
            return {"success": False, "error": "Explicit owned fixture refusal"}
        if kind == "get_queue" and self.fail_after_admission and self.admitted_inputs and not self.admission_failure_sent:
            self.admission_failure_sent = True
            return {"success": False, "error": "Injected post-admission failure"}
        row = {"id": self.active_id, "activeSessionId": self.active_id, "sessionId": "owned-durable",
               "cwd": str(self.root / "work"), "sessionFile": str(self.root / "owned.jsonl"),
               "messageCount": 0, "modified": "2026-10-23", "lifecycle": "archived" if self.archived else "live"}
        model = {"provider": "openai-codex", "id": "gpt-6.1-sol"}
        data = None
        if kind == "create":
            if command.get("config", {}).get("cwd") != row["cwd"]:
                return {"success": False, "error": "Create requires nested config"}
            data = row
        elif kind == "get_connection_state":
            data = {**row, "isStreaming": False, "isCompacting": False, "isBashRunning": False,
                    "model": model, "thinkingLevel": "xhigh", "compactionCount": 0}
        elif kind == "get_state":
            data = {**row, "hasRunningSubagents": False}
        elif kind == "get_session_stats":
            data = {"cost": 0}
        elif kind == "list":
            data = {"sessions": [row]}
        elif kind == "get_queue":
            data = self.queue
        elif kind in ("prompt", "steer", "follow_up"):
            lane = "steering" if kind == "steer" else "followUp"
            self.queue[lane].append(command["message"])
            self.admitted_inputs.append(command["message"])
            self.release_runnable_inputs()
            data = {"queued": True}
        elif kind in ("clear_queue", "abort_and_clear_queue"):
            data = self.queue
            self.queue = {"steering": [], "followUp": []}
        elif kind == "get_messages":
            data = {"messages": []}
        elif kind == "get_commands":
            data = {"commands": []}
        elif kind == "set_model":
            data = model
        elif kind == "acquire_session_input_pause":
            self.pauses.add(owner)
            data = {"pauseId": "owned-pause"}
        elif kind == "release_session_input_pause":
            self.pauses.discard(owner)
            self.release_runnable_inputs()
        elif kind == "kill":
            self.archived = True
        elif kind != "set_thinking_level":
            return {"success": False, "error": "Unknown fixture command"}
        return {"success": True, "data": data}


class PrimeToolsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="prime-tools-test-")
        self.root = Path(self.temp.name)
        self.env = {"PATH": os.environ["PATH"], "LANG": "C.UTF-8", "PYTHONDONTWRITEBYTECODE": "1"}

    def tearDown(self):
        self.temp.cleanup()

    def executable(self, path, text):
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text)
        path.chmod(0o755)
        return path

    def run_tool(self, tool, *args, text="", env=None):
        return subprocess.run([str(tool), *args], input=text, text=True, encoding="utf-8", capture_output=True,
                              env={**self.env, **(env or {})}, timeout=10)

    def test_dispatcher_default_pi_explicit_prime_and_environment(self):
        dispatcher = self.root / "agent-cli"
        shutil.copy2(ROOT / "bin/agent-cli", dispatcher)
        for name in ("pi-web-cli", "prime-cli"):
            self.executable(self.root / name, ECHO)
        for flags, env, tool in [((), {}, "pi-web-cli"), (("--backend", "prime"), {}, "prime-cli"),
                                  ((), {"PI_STACK_BACKEND": "prime"}, "prime-cli"),
                                  (("--backend", "pi"), {"PI_STACK_BACKEND": "prime"}, "pi-web-cli")]:
            with self.subTest(flags=flags, env=env):
                proc = self.run_tool(dispatcher, *flags, "prompt", "s 1", "--steer", text="雪\n'quoted'\n", env={**env, "ECHO_EXIT": "7"})
                self.assertEqual(proc.returncode, 7)
                self.assertEqual(proc.stderr, "")
                self.assertEqual(json.loads(proc.stdout), {"tool": tool, "argv": ["prompt", "s 1", "--steer"], "stdin": "雪\n'quoted'\n"})

    def test_real_dispatcher_prime_uses_socket_and_preserves_stdin(self):
        with Fixture([{"queued": True}]) as fixture:
            proc = self.run_tool(ROOT / "bin/agent-cli", "--backend", "prime", "prompt", "s1", "--follow-up",
                                 text="exact\n雪", env={"PRIME_AGENT_DAEMON_SOCKET": fixture.path})
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertEqual(json.loads(proc.stdout), {"ok": True, "status": 200, "result": {"queued": True, "accepted": True}})
        self.assertEqual(fixture.requests[0]["command"], {"type": "follow_up", "activeSessionId": "s1", "message": "exact\n雪"})

    def test_dispatcher_validation_and_help(self):
        for args, env in [((), {}), (("--backend", "other", "list"), {}), (("list",), {"PI_STACK_BACKEND": "other"})]:
            with self.subTest(args=args):
                proc = self.run_tool(ROOT / "bin/agent-cli", *args, env=env)
                self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "usage"))
                self.assertEqual(proc.stderr, "")
        proc = self.run_tool(ROOT / "bin/agent-cli", "--help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("Pi remains the default", proc.stdout)

    def test_remote_shell_roundtrip_and_stdin_without_twingate_restart(self):
        remote = self.executable(self.root / "remote dir/prime-cli", ECHO)
        ssh = self.executable(self.root / "options-01-ssh", '''#!/usr/bin/env python3
import json, os, sys
from pathlib import Path
Path(os.environ["SSH_ARG_LOG"]).write_text(json.dumps(sys.argv[1:]))
os.execv("/bin/sh", ["sh", "-c", sys.argv[1]])
''')
        log = self.root / "ssh-args.json"
        attack = "'quoted' \"double\"; $(touch SHOULD_NOT_EXIST)\n雪 🙂"
        args = ["prompt", "s id", attack, "--steer"]
        proc = self.run_tool(ROOT / "bin/prime-cli-remote", *args, text="stdin\n雪\n",
                             env={"OPTIONS_01_SSH": str(ssh), "PRIME_CLI_REMOTE_BIN": str(remote),
                                  "SSH_ARG_LOG": str(log), "ECHO_EXIT": "9"})
        self.assertEqual(proc.returncode, 9)
        self.assertEqual(proc.stderr, "")
        self.assertEqual(json.loads(proc.stdout), {"tool": "prime-cli", "argv": args, "stdin": "stdin\n雪\n"})
        ssh_args = json.loads(log.read_text())
        self.assertEqual(len(ssh_args), 1)
        self.assertEqual(shlex.split(ssh_args[0]), [str(remote), *args])
        self.assertNotIn("--ensure-tg", ssh_args)
        self.assertFalse((ROOT / "SHOULD_NOT_EXIST").exists())

    def test_remote_default_lookup_is_options_wrapper(self):
        self.executable(self.root / "options-01-ssh", ECHO)
        proc = self.run_tool(ROOT / "bin/prime-cli-remote", "status", "s 1", env={"PATH": str(self.root) + os.pathsep + self.env["PATH"]})
        self.assertEqual(proc.returncode, 0)
        data = json.loads(proc.stdout)
        self.assertEqual(data["tool"], "options-01-ssh")
        self.assertEqual(shlex.split(data["argv"][0]), ["$HOME/.local/bin/prime-cli", "status", "s 1"])

    def test_remote_default_home_expansion_is_quoted(self):
        self.executable(self.root / ".local/bin/prime-cli", ECHO)
        ssh = self.executable(self.root / "ssh wrapper", '''#!/usr/bin/env python3
import os, sys
os.execv("/bin/sh", ["sh", "-c", sys.argv[1]])
''')
        proc = self.run_tool(ROOT / "bin/prime-cli-remote", "status", "s 1", env={"HOME": str(self.root), "OPTIONS_01_SSH": str(ssh)})
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.assertEqual(json.loads(proc.stdout)["argv"], ["status", "s 1"])
        invalid = self.run_tool(ROOT / "bin/prime-cli-remote", "status", "s", env={"PRIME_CLI_REMOTE_BIN": "relative-cli"})
        self.assertEqual((invalid.returncode, json.loads(invalid.stdout)["error"]), (1, "usage"))

    def test_remote_missing_wrapper_is_json_failure(self):
        proc = self.run_tool(ROOT / "bin/prime-cli-remote", "list", "--cwd", "/work", env={"OPTIONS_01_SSH": str(self.root / "missing")})
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["error"]), (1, "remote_unavailable"))
        self.assertEqual(proc.stderr, "")

    def test_focused_install_isolated_links_and_idempotent(self):
        home = self.root / "home"
        home.mkdir()
        command = ["bash", str(ROOT / "scripts/install-agent-clis.sh")]
        env = {**self.env, "HOME": str(home)}
        for _ in range(2):
            proc = subprocess.run(command, capture_output=True, text=True, env=env, timeout=10)
            self.assertEqual((proc.returncode, proc.stdout, proc.stderr), (0, "", ""))
        installed = home / ".local/bin"
        self.assertEqual(sorted(path.name for path in installed.iterdir()), ["agent-cli", "prime-cli", "prime-cli-remote"])
        for name in ("agent-cli", "prime-cli", "prime-cli-remote"):
            self.assertEqual((installed / name).resolve(), ROOT / "bin" / name)
        proc = self.run_tool(installed / "agent-cli", "--backend", "prime", "answer", "s", "ask", "q", "not injected")
        self.assertEqual((proc.returncode, json.loads(proc.stdout)["status"]), (1, 501))
        self.assertEqual(sorted(path.name for path in home.iterdir()), [".local"])

    def test_live_check_prepares_only_nonsecret_owned_files(self):
        proc = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "prepare"],
                              capture_output=True, text=True, env={**self.env, "TMPDIR": str(self.root)}, timeout=10)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        data = json.loads(proc.stdout)
        owned = Path(data["root"])
        self.assertEqual(owned.parent, self.root)
        self.assertEqual(sorted(str(path.relative_to(owned)) for path in owned.rglob("*")),
                         ["agent", "agent/settings.json", "prime-cli-check-owner.json", "work"])
        settings = json.loads((owned / "agent/settings.json").read_text())
        self.assertEqual(settings["allowedModels"], ["openai-codex/gpt-6.1-sol"])
        self.assertFalse(settings["retry"]["failover"]["enabled"])
        self.assertFalse((owned / "daemon.sock").exists())
        self.assertEqual(data["launchEnv"], {"PRIME_AGENT_CODING_AGENT_DIR": str(owned / "agent")})
        failed = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "run", "--root", str(owned), "--timeout", "1"],
                                capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(failed.returncode, 1)
        result = json.loads(failed.stdout)
        self.assertFalse(result["ok"])
        self.assertEqual(result["retainedOwnedSessions"], [])
        self.assertEqual(result["error"]["error"], "transport_error")

    def test_live_check_complete_control_run_and_failure_cleanup_are_owned(self):
        for fail_command in (None, "get_commands"):
            with self.subTest(fail_command=fail_command):
                prepared = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "prepare"], capture_output=True, text=True,
                                          env={**self.env, "TMPDIR": str(self.root)}, timeout=10)
                owned = Path(json.loads(prepared.stdout)["root"])
                with OwnedSupervisor(owned, fail_command) as server:
                    proc = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "run", "--root", str(owned), "--timeout", "2"],
                                          capture_output=True, text=True, env=self.env, timeout=20)
                result = json.loads(proc.stdout)
                self.assertEqual(proc.stderr, "")
                self.assertEqual(proc.returncode, 0 if fail_command is None else 1, proc.stdout)
                self.assertEqual(result["retainedOwnedSessions"], [])
                self.assertTrue(server.archived)
                self.assertTrue(server.requests)
                self.assertEqual([command["type"] for command in server.requests].count("create"), 1)
                self.assertNotIn("shutdown", [command["type"] for command in server.requests])
                self.assertTrue(all(command["activeSessionId"] in ("owned-durable", "owned-active") for command in server.requests if "activeSessionId" in command))

    def test_control_only_never_admits_input_on_post_admission_fault(self):
        prepared = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "prepare"], capture_output=True, text=True,
                                  env={**self.env, "TMPDIR": str(self.root)}, timeout=10)
        owned = Path(json.loads(prepared.stdout)["root"])
        with OwnedSupervisor(owned, fail_after_admission=True) as server:
            proc = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "run", "--root", str(owned), "--timeout", "2"],
                                  capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(server.admitted_inputs, [], f"default run admitted runnable text: {server.admitted_inputs}")
        self.assertEqual(server.runnable_inputs, [])
        self.assertEqual(proc.returncode, 0, proc.stdout)
        self.assertTrue(server.archived)

    def test_inference_queue_failure_cancels_before_pause_disconnect(self):
        prepared = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "prepare"], capture_output=True, text=True,
                                  env={**self.env, "TMPDIR": str(self.root)}, timeout=10)
        owned = Path(json.loads(prepared.stdout)["root"])
        with OwnedSupervisor(owned, fail_after_admission=True) as server:
            proc = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "run", "--root", str(owned), "--timeout", "2", "--inference"],
                                  capture_output=True, text=True, env=self.env, timeout=20)
        self.assertEqual(proc.returncode, 1, proc.stdout)
        self.assertEqual(len(server.admitted_inputs), 3)
        self.assertEqual(server.runnable_inputs, [], f"pause disconnect released runnable inputs: {server.events}")
        self.assertLess(server.events.index("abort_and_clear_queue"), server.events.index("pause_owner_disconnected"))
        self.assertEqual(json.loads(proc.stdout)["retainedOwnedSessions"], [])
        self.assertTrue(server.archived)

    def test_durable_id_survives_active_replacement_without_binding_events(self):
        owned = self.root / "owned"
        owned.mkdir()
        with OwnedSupervisor(owned) as server:
            env = {"PRIME_AGENT_DAEMON_SOCKET": str(owned / "daemon.sock")}
            spawned = self.run_tool(ROOT / "bin/prime-cli", "spawn", str(owned / "work"), env=env)
            sid = json.loads(spawned.stdout)["session"]["id"]
            with server.lock:
                server.active_id = "replacement-active"
            results = {}
            for name, args in [("prompt", ("prompt", sid, "Owned fixture input")), ("status", ("status", sid)),
                               ("list", ("list", "--cwd", str(owned / "work"))), ("archive", ("archive", sid)),
                               ("archived-list", ("list", "--cwd", str(owned / "work")))]:
                results[name] = self.run_tool(ROOT / "bin/prime-cli", *args, env=env)
        with self.subTest(operation="spawn"):
            self.assertEqual(sid, "owned-durable")
        for name, proc in results.items():
            with self.subTest(operation=name):
                self.assertEqual(proc.returncode, 0, proc.stdout)
                data = json.loads(proc.stdout)
                if name == "status":
                    self.assertEqual(data["session"]["id"], "owned-durable")
                    self.assertEqual(data["session"]["activeSessionId"], "replacement-active")
                if name in ("list", "archived-list"):
                    self.assertEqual(data["sessions"][0]["id"], "owned-durable")
                    self.assertEqual(data["sessions"][0]["activeSessionId"], "replacement-active")
                    self.assertEqual(data["sessions"][0]["archived"], name == "archived-list")
        pauses = [command for command in server.requests if command["type"] == "acquire_session_input_pause"]
        self.assertEqual(pauses[0]["activeSessionId"], "owned-durable")
        self.assertEqual(server.requests[-2], {"type": "kill", "activeSessionId": "replacement-active"})
        self.assertNotIn("attach", [command["type"] for command in server.requests])

    def test_live_check_refuses_unprepared_root(self):
        proc = subprocess.run(["python3", str(ROOT / "scripts/check-prime-cli-live.py"), "run", "--root", str(self.root)],
                              capture_output=True, text=True, env=self.env, timeout=10)
        self.assertEqual(proc.returncode, 1)
        self.assertFalse(json.loads(proc.stdout)["ok"])
        self.assertEqual(list(self.root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()

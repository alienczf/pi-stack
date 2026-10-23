#!/usr/bin/env python3
"""Prepare an isolated daemon configuration, then check only newly created sessions."""
from __future__ import annotations

import argparse
from dataclasses import dataclass, field
import json
import math
import os
from pathlib import Path
import stat
import subprocess
import sys
import tempfile
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "bin"))
from prime_cli import CliError, PrimeClient

MODEL = "openai-codex/gpt-6.1-sol"
THINKING = "xhigh"
MARKER = "prime-cli-check-owner.json"


def prepare() -> dict:
    root = Path(tempfile.mkdtemp(prefix="prime-cli-check-"))
    agent = root / "agent"
    agent.mkdir(mode=0o700)
    (root / "work").mkdir()
    settings = {"allowedModels": [MODEL], "retry": {"enabled": False, "failover": {"enabled": False},
                "provider": {"waitForUsage": {"enabled": False, "pauseUntilReset": False}}}}
    (agent / "settings.json").write_text(json.dumps(settings, indent=2) + "\n")
    (root / MARKER).write_text(json.dumps({"model": MODEL, "thinking": THINKING}) + "\n")
    return {"ok": True, "root": str(root), "launchEnv": {"PRIME_AGENT_CODING_AGENT_DIR": str(agent)},
            "daemonArgv": ["prime-agent", "--mode", "daemon", "--daemon-socket", str(root / "daemon.sock")],
            "note": "Launch separately. No runtime was started and no credentials were accessed."}


@dataclass
class VerificationRuntime:
    root: Path
    executable: Path
    timeout: float
    process: subprocess.Popen | None = field(default=None, init=False)
    lock_fd: int | None = field(default=None, init=False)
    socket_identity: tuple[int, int] | None = field(default=None, init=False)
    evidence: dict = field(default_factory=lambda: {"started": False, "stopped": True, "socketRemoved": True})

    @property
    def socket(self) -> Path:
        return self.root / "daemon.sock"

    def start(self) -> None:
        try:
            self.lock_fd = os.open(self.root / "verification.lock", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
        except FileExistsError as exc:
            raise CliError("runtime_collision", "Verification root is already locked", 409) from exc
        if os.path.lexists(self.socket):
            raise CliError("runtime_collision", "Dedicated daemon socket already exists; no daemon was contacted", 409)
        self.process = subprocess.Popen(
            [str(self.executable), "--mode", "daemon", "--daemon-socket", str(self.socket)],
            env={**os.environ, "PRIME_AGENT_CODING_AGENT_DIR": str(self.root / "agent")},
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.evidence.update(started=True, stopped=False)
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            if self.process.poll() is not None:
                raise CliError("runtime_start_failed", "Dedicated daemon exited before becoming ready")
            try:
                info = self.socket.lstat()
            except FileNotFoundError:
                time.sleep(0.05)
                continue
            if not stat.S_ISSOCK(info.st_mode):
                raise CliError("runtime_collision", "Dedicated socket path is not a socket", 409)
            self.socket_identity = (info.st_dev, info.st_ino)
            self.evidence["socketRemoved"] = False
            return
        raise CliError("runtime_start_failed", "Dedicated daemon did not create its socket", 504)

    def close(self) -> None:
        try:
            if self.process is not None:
                if self.process.poll() is None:
                    self.process.terminate()
                    try:
                        self.process.wait(timeout=self.timeout)
                    except subprocess.TimeoutExpired:
                        self.process.kill()
                        self.process.wait(timeout=self.timeout)
                self.evidence["stopped"] = self.process.poll() is not None
                if self.evidence["stopped"] and self.socket_identity is not None:
                    try:
                        info = self.socket.lstat()
                    except FileNotFoundError:
                        self.evidence["socketRemoved"] = True
                    else:
                        if stat.S_ISSOCK(info.st_mode) and (info.st_dev, info.st_ino) == self.socket_identity:
                            self.socket.unlink()
                            self.evidence["socketRemoved"] = True
        finally:
            if self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
                (self.root / "verification.lock").unlink()


class Check:
    def __init__(self, root: Path, timeout: float):
        self.root = root.resolve()
        self.timeout = timeout
        self.socket = str(self.root / "daemon.sock")
        self.cwd = str(self.root / "work")
        self.created: list[str] = []
        self.evidence: list[dict] = []
        self.gaps: list[str] = []
        marker = json.loads((self.root / MARKER).read_text())
        settings = json.loads((self.root / "agent/settings.json").read_text())
        if marker != {"model": MODEL, "thinking": THINKING}:
            raise ValueError("Root was not prepared for this exact model")
        if settings.get("allowedModels") != [MODEL] or settings.get("retry", {}).get("failover", {}).get("enabled") is not False:
            raise ValueError("Owned settings must pin the exact model and disable provider failover")
        self.env = {**os.environ, "PRIME_AGENT_DAEMON_SOCKET": self.socket,
                    "PRIME_CLI_MODEL": MODEL, "PRIME_CLI_THINKING": THINKING,
                    "PRIME_CLI_TIMEOUT": str(timeout), "PYTHONDONTWRITEBYTECODE": "1"}

    def call(self, *args: str, expected: int | None = 0, text: str | None = None) -> dict:
        proc = subprocess.run([str(ROOT / "bin/prime-cli"), *args], input=text, capture_output=True,
                              text=True, encoding="utf-8", env=self.env, timeout=self.timeout + 5)
        data = json.loads(proc.stdout)
        if args[0] == "spawn":
            session = data.get("session", {})
            if isinstance(session.get("id"), str):
                self.created.append(session["id"])
        self.evidence.append({"command": args[0], "exit": proc.returncode, "ok": data.get("ok"),
                              "error": data.get("error")})
        if expected is not None and proc.returncode != expected:
            raise CliError(data.get("error", "check_failed"), data.get("message", f"{args[0]} failed"),
                           details={"command": args[0]})
        return data

    def messages(self, sid: str) -> list:
        messages = self.call("messages", sid)["result"]["messages"]
        for row in messages:
            if row.get("stopReason") in ("error", "aborted"):
                raise CliError("model_error", row.get("errorMessage", "Model run failed or aborted"))
        return messages

    def wait(self, sid: str, condition) -> dict:
        deadline = time.monotonic() + self.timeout
        while time.monotonic() < deadline:
            session = self.call("status", sid)["session"]
            if session.get("isQuotaParked"):
                raise CliError("quota", "Quota parked the owned session; stop and report")
            messages = self.messages(sid)
            if condition(session, messages):
                return session
            time.sleep(0.1)
        raise CliError("check_timeout", "Owned session did not satisfy the completion check", 504)

    def run(self, inference: bool) -> None:
        session = self.call("spawn", self.cwd)["session"]
        sid = session["id"]
        state = self.call("status", sid)["session"]
        if state["model"].get("provider") != "openai-codex" or state["model"].get("id") != "gpt-6.1-sol":
            raise CliError("selection_mismatch", "Owned server did not retain the exact model")
        if state["thinkingLevel"] != THINKING:
            self.gaps.append(f"Requested xhigh was clamped to {state['thinkingLevel']}. No xhigh inference is claimed.")
        self.evidence.append({"requestedThinking": THINKING, "effectiveThinking": state["thinkingLevel"]})
        sessions = self.call("list", "--cwd", self.cwd)["sessions"]
        own = next(row for row in sessions if row["id"] == sid)
        if own.get("archived") is not False or not all(key in own for key in ("path", "messageCount", "modified")):
            raise CliError("metadata_gap", "Owned list row lacks required metadata")
        self.call("commands", sid)
        self.call("messages", sid)
        answer = self.call("answer", sid, "owned-ask", "owned-question", "not injected", expected=1)
        if answer.get("status") != 501 or answer.get("error") != "unsupported":
            raise CliError("answer_gap_hidden", "Interactive answer must be explicitly unsupported")
        selection = self.call("model", sid, MODEL, expected=None)
        if not selection.get("ok"):
            if selection.get("error") != "upstream_error":
                raise CliError("model_check_failed", "Exact native model selection failed unexpectedly")
            self.gaps.append("Native set_model rejected the exact requested selector. No substitute was selected.")
        if inference:
            with PrimeClient(self.socket, self.timeout) as wire:
                pause = wire.request("acquire_session_input_pause", activeSessionId=sid, leaseKey=str(uuid.uuid4()))
                try:
                    for mode in ((), ("--steer",), ("--follow-up",)):
                        self.call("prompt", sid, *mode, text="Owned inference-enabled queue check.")
                    queued = self.call("status", sid)["session"]
                    if queued["pendingMessageCount"] != 3:
                        raise CliError("queue_mismatch", "The paused owned session did not retain three inputs")
                    self.call("queue-clear", sid)
                    self.call("prompt", sid, "--steer", text="Owned inference-enabled abort check.")
                    self.call("abort", sid)
                    if self.call("status", sid)["session"]["pendingMessageCount"] != 0:
                        raise CliError("abort_mismatch", "Abort did not clear the owned queue")
                finally:
                    wire.request("abort_and_clear_queue", activeSessionId=sid)
                wire.request("release_session_input_pause", activeSessionId=sid, pauseId=pause["pauseId"])
        else:
            self.call("queue-clear", sid)
            self.call("abort", sid)
        stopped = self.call("stop", sid)["result"]
        if stopped.get("runtimeClosed") is not False:
            raise CliError("stop_gap_hidden", "Stop must disclose the resident-retaining shim")
        self.call("thinking-level", sid, THINKING)
        effective = self.call("status", sid)["session"]["thinkingLevel"]
        self.evidence.append({"thinkingSetterAccepted": True, "effectiveThinking": effective})
        if inference:
            token = f"PRIME_CLI_VERIFIED_{uuid.uuid4().hex}"
            self.evidence.append({"command": "prompt_and_wait", "transport": "native-completion-probe"})
            with PrimeClient(self.socket, self.timeout) as wire:
                wire.request("prompt_and_wait", activeSessionId=sid,
                             message=f"Reply with exactly {token}. Do not use tools.", streamingBehavior="followUp")
            self.wait(sid, lambda state, rows: not state["isStreaming"] and state["pendingMessageCount"] == 0 and any(
                row.get("role") == "assistant" and token in json.dumps(row.get("content"), ensure_ascii=False) for row in rows))
            before = self.call("status", sid)["session"]["compactionCount"]
            self.call("prompt", sid, "/compact Preserve the verification marker.")
            self.wait(sid, lambda state, _: state["compactionCount"] > before and not state["isCompacting"])
        self.call("archive", sid)
        self.created.remove(sid)
        rows = self.call("list", "--cwd", self.cwd)["sessions"]
        archived = [row for row in rows if row.get("sessionId") == session.get("sessionId") or row["id"] == sid]
        if not archived or any(row.get("archived") is not True for row in archived):
            raise CliError("archive_mismatch", "Owned session lacks an archived compatibility row")

    def cleanup(self) -> list[str]:
        remaining = []
        for sid in self.created:
            try:
                self.call("stop", sid)
                deadline = time.monotonic() + self.timeout
                while time.monotonic() < deadline:
                    state = self.call("status", sid)["session"]
                    if not any(state.get(key) for key in ("isStreaming", "isCompacting", "isBashRunning")):
                        break
                    time.sleep(0.1)
                self.call("archive", sid)
            except (CliError, OSError, ValueError, subprocess.SubprocessError):
                remaining.append(sid)
        return remaining


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("prepare")
    for mode in ("run", "verify"):
        run = sub.add_parser(mode)
        run.add_argument("--root", type=Path, required=True)
        run.add_argument("--timeout", type=float, default=60)
        run.add_argument("--inference", action="store_true")
        if mode == "verify":
            run.add_argument("--runtime", type=Path, required=True)
    args = parser.parse_args()
    if args.mode == "prepare":
        print(json.dumps(prepare(), indent=2))
        return 0
    check = None
    runtime = None
    result = {"ok": False, "model": MODEL, "inferenceRequested": args.inference,
              "retainedOwnedSessions": []}
    if args.mode == "verify":
        result["runtime"] = {"started": False, "stopped": True, "socketRemoved": True}
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise CliError("usage", "timeout must be finite and positive", 400)
        check = Check(args.root, args.timeout)
        if args.mode == "verify":
            runtime = VerificationRuntime(check.root, args.runtime.resolve(), args.timeout)
            runtime.start()
        check.run(args.inference)
        result["ok"] = True
    except (CliError, OSError, ValueError, StopIteration, subprocess.SubprocessError) as exc:
        result["error"] = exc.output if isinstance(exc, CliError) else str(exc)
    finally:
        if check:
            result["retainedOwnedSessions"] = check.cleanup()
            result["checks"] = check.evidence
            result["knownGaps"] = check.gaps
            if check.gaps or result["retainedOwnedSessions"]:
                result["ok"] = False
        if runtime:
            try:
                runtime.close()
            except (OSError, subprocess.SubprocessError):
                result["error"] = CliError("runtime_cleanup_failed", "Owned runtime cleanup failed").output
                result["ok"] = False
            result["runtime"] = runtime.evidence
            if not runtime.evidence["stopped"] or not runtime.evidence["socketRemoved"]:
                result["ok"] = False
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

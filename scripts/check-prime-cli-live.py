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
from prime_cli import CliError, LEVELS, PrimeClient, array_field, object_data, reject_json_constant

MODEL = "openai-codex/gpt-6.1-sol"
THINKING = "xhigh"
MARKER = "prime-cli-check-owner.json"
MODEL_DEFINITION = ROOT / "scripts/prime-models/openai-codex-gpt-6.1-sol.json"
METADATA_LIMITATIONS = [
    "Tiered costs, inputLimits, type, and extra compatibility flags are not represented by this whitelist. "
    "Reported native flat cost is not exact tiered billing.",
    "Metadata declares capabilities; authentication, entitlement, effective reasoning, and inference require separate checks.",
]


@dataclass(frozen=True)
class ModelDefinition:
    provider: str
    id: str
    name: str
    api: str
    reasoning: bool
    thinking_level_map: dict[str, str | None]
    input: tuple[str, ...]
    context_window: int
    max_tokens: int
    cost: dict[str, float]

    @classmethod
    def parse(cls, data: object) -> ModelDefinition:
        expected = {"provider", "id", "name", "api", "reasoning", "thinkingLevelMap", "input",
                    "contextWindow", "maxTokens", "cost"}
        if not isinstance(data, dict) or set(data) != expected:
            raise ValueError("Expected only the complete metadata whitelist")
        if (data["provider"], data["id"], data["api"]) != ("openai-codex", "gpt-6.1-sol", "openai-codex-responses"):
            raise ValueError("Metadata must describe the exact requested provider, model, and API")
        if not isinstance(data["name"], str) or not data["name"].strip() or type(data["reasoning"]) is not bool:
            raise ValueError("Invalid model name or reasoning flag")
        mapping = data["thinkingLevelMap"]
        if (not isinstance(mapping, dict) or set(mapping) != set(LEVELS)
                or any(value is not None and value not in LEVELS for value in mapping.values())):
            raise ValueError("Expected an explicit complete supported thinking-level map")
        inputs = data["input"]
        if (not isinstance(inputs, list) or not inputs or any(value not in ("text", "image") for value in inputs)
                or len(set(inputs)) != len(inputs)):
            raise ValueError("Expected unique supported model inputs")
        context, output = data["contextWindow"], data["maxTokens"]
        if type(context) is not int or type(output) is not int or not 0 < output <= context <= 2**64 - 1:
            raise ValueError("Expected positive native token limits with maxTokens <= contextWindow")
        cost = data["cost"]
        if not isinstance(cost, dict) or set(cost) != {"input", "output", "cacheRead", "cacheWrite"}:
            raise ValueError("Expected four explicit flat model costs")
        for value in cost.values():
            try:
                valid = type(value) in (int, float) and math.isfinite(value) and value >= 0
            except OverflowError:
                valid = False
            if not valid:
                raise ValueError("Expected finite nonnegative model costs")
        return cls(data["provider"], data["id"], data["name"], data["api"], data["reasoning"],
                   dict(mapping), tuple(inputs), context, output, dict(cost))

    @classmethod
    def load(cls, path: Path) -> ModelDefinition:
        try:
            return cls.parse(json.loads(path.read_text(), parse_constant=reject_json_constant))
        except (ValueError, OSError, TypeError) as exc:
            raise CliError("invalid_model_definition", "Expected a complete validated secret-free model definition", 400) from exc

    def model(self) -> dict:
        return {"id": self.id, "name": self.name, "api": self.api, "reasoning": self.reasoning,
                "thinkingLevelMap": self.thinking_level_map, "input": list(self.input),
                "contextWindow": self.context_window, "maxTokens": self.max_tokens, "cost": self.cost}

    def native_config(self) -> dict:
        return {"providers": {self.provider: {"models": [self.model()]}}}

    def expect(self, data: object) -> None:
        if isinstance(data, dict):
            projected = {"provider": data.get("provider"), **{key: data.get(key) for key in self.model()}}
            try:
                if self.parse(projected) == self:
                    return
            except (ValueError, TypeError):
                pass
        raise CliError("model_metadata_mismatch", "Native model metadata differs from the supplied definition", 409)


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


@dataclass(frozen=True)
class AgentDirectory:
    path: Path
    owned: bool

    @classmethod
    def select(cls, root: Path) -> AgentDirectory:
        path = Path(os.environ.get("PRIME_AGENT_CODING_AGENT_DIR", str(root / "agent")))
        try:
            info = path.lstat()
            if not path.is_absolute() or not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise ValueError("Expected an existing owned directory")
            path = path.resolve()
            owned = path == root / "agent"
            if not owned and (path.is_relative_to(root) or root.is_relative_to(path)):
                raise ValueError("Existing agent directory must be separate from the verification root")
            return cls(path, owned)
        except (OSError, ValueError) as exc:
            raise CliError("unsafe_agent_directory", "Expected an existing owned real agent directory", 400) from exc


@dataclass
class VerificationRuntime:
    root: Path
    executable: Path
    timeout: float
    definition: ModelDefinition
    agent: AgentDirectory | None = None
    model_identity: tuple[int, int] | None = field(default=None, init=False)
    settings_snapshot: bytes | None = field(default=None, init=False, repr=False)
    settings_mode: int = field(default=0o600, init=False)
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
            self.evidence["socketRemoved"] = False
            raise CliError("runtime_collision", "Dedicated daemon socket already exists; no daemon was contacted", 409)
        self.agent = self.agent or AgentDirectory.select(self.root)
        if self.agent.owned:
            try:
                model_fd = os.open(self.root / "agent/models.json", os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
            except FileExistsError as exc:
                raise CliError("model_registration_collision", "Native models.json already exists; it was not read or replaced", 409) from exc
            with os.fdopen(model_fd, "w") as config:
                info = os.fstat(config.fileno())
                self.model_identity = (info.st_dev, info.st_ino)
                json.dump(self.definition.native_config(), config, allow_nan=False)
                config.write("\n")
            settings = self.root / "agent/settings.json"
            self.settings_snapshot = settings.read_bytes()
            self.settings_mode = stat.S_IMODE(settings.stat().st_mode)
        else:
            self.prepare_project_settings()
        self.process = subprocess.Popen(
            [str(self.executable), "--mode", "daemon", "--daemon-socket", str(self.socket)],
            env={**os.environ, "PRIME_AGENT_CODING_AGENT_DIR": str(self.agent.path),
                 "PRIME_AGENT_SESSION_DIR": str(self.root / "agent/sessions"),
                 "PRIME_AGENT_DAEMON_SOCKET": str(self.socket), "DO_NOT_TRACK": "1", "PI_OFFLINE": "1"},
            cwd=self.root / "work", umask=0o077,
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

    def prepare_project_settings(self) -> None:
        directory = self.root / "work/.prime"
        for path in (directory, directory / "agent"):
            if not os.path.lexists(path):
                path.mkdir(mode=0o700)
            info = path.lstat()
            if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                raise CliError("unsafe_verification_root", "Project configuration directory is not owned", 400)
        path = directory / "agent/settings.json"
        retry = json.loads((self.root / "agent/settings.json").read_text())["retry"]
        expected = {"retry": retry}
        if os.path.lexists(path):
            info = path.lstat()
            if (not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid()
                    or json.loads(path.read_text()) != expected):
                raise CliError("runtime_collision", "Project retry settings already differ", 409)
        else:
            with os.fdopen(os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "w") as out:
                json.dump(expected, out, allow_nan=False)
                out.write("\n")

    def close(self) -> None:
        try:
            if self.process is not None:
                if self.process.poll() is None:
                    try:
                        info = self.socket.lstat()
                        if (info.st_dev, info.st_ino) != self.socket_identity:
                            raise OSError("Owned socket identity changed")
                        with PrimeClient(str(self.socket), self.timeout) as wire:
                            wire.request("shutdown", force=True)
                    except (OSError, CliError):
                        try:
                            self.process.terminate()
                        except ProcessLookupError:
                            pass
                    try:
                        self.process.wait(timeout=self.timeout)
                    except subprocess.TimeoutExpired:
                        try:
                            self.process.kill()
                        except ProcessLookupError:
                            pass
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
                elif self.evidence["stopped"]:
                    self.evidence["socketRemoved"] = not os.path.lexists(self.socket)
        finally:
            if self.evidence["stopped"] and self.settings_snapshot is not None:
                settings = self.root / "agent/settings.json"
                info = settings.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise OSError("Settings ownership changed during verification")
                with tempfile.NamedTemporaryFile(dir=settings.parent, prefix=".verification-settings-", delete=False) as saved:
                    temporary = Path(saved.name)
                    try:
                        saved.write(self.settings_snapshot)
                        saved.flush()
                        os.fchmod(saved.fileno(), self.settings_mode)
                        os.replace(temporary, settings)
                    finally:
                        temporary.unlink(missing_ok=True)
            if self.evidence["stopped"] and self.model_identity is not None:
                path = self.root / "agent/models.json"
                try:
                    info = path.lstat()
                except FileNotFoundError:
                    pass
                else:
                    if stat.S_ISREG(info.st_mode) and (info.st_dev, info.st_ino) == self.model_identity:
                        path.unlink()
            if self.evidence["stopped"] and self.lock_fd is not None:
                os.close(self.lock_fd)
                self.lock_fd = None
                (self.root / "verification.lock").unlink()


class Check:
    def __init__(self, root: Path, timeout: float, definition: ModelDefinition | None = None):
        self.definition = definition
        if root.is_symlink():
            raise CliError("unsafe_verification_root", "Verification root must not be a symlink", 400)
        self.root = root.resolve()
        self.timeout = timeout
        self.socket = str(self.root / "daemon.sock")
        self.cwd = str(self.root / "work")
        self.created: list[str] = []
        self.evidence: list[dict] = []
        self.gaps: list[str] = []
        try:
            for directory in (self.root, self.root / "agent", self.root / "work"):
                info = directory.lstat()
                if not stat.S_ISDIR(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("Expected owned real directories")
            for directory in (self.root, self.root / "agent"):
                if directory.stat().st_mode & 0o077:
                    raise ValueError("Expected private root and agent directories")
            for path in (self.root / MARKER, self.root / "agent/settings.json"):
                info = path.lstat()
                if not stat.S_ISREG(info.st_mode) or info.st_uid != os.getuid():
                    raise ValueError("Expected owned regular configuration files")
            marker = json.loads((self.root / MARKER).read_text())
            settings = json.loads((self.root / "agent/settings.json").read_text())
            retry = settings.get("retry", {})
            usage = retry.get("provider", {}).get("waitForUsage", {})
            if (marker != {"model": MODEL, "thinking": THINKING} or settings.get("allowedModels") != [MODEL]
                    or retry.get("enabled") is not False or retry.get("failover", {}).get("enabled") is not False
                    or usage.get("enabled") is not False or usage.get("pauseUntilReset") is not False):
                raise ValueError("Expected exact model pinning with retry, failover, and quota waiting disabled")
        except (OSError, ValueError, AttributeError, TypeError) as exc:
            raise CliError("unsafe_verification_root", "Expected the existing private isolated root with safe nonsecret settings", 400) from exc
        self.agent = AgentDirectory.select(self.root)
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
            info = data.get("errorInfo")
            details = {"errorInfo": info} if isinstance(info, dict) else {}
            raise CliError(data.get("error", "check_failed"), data.get("message", f"{args[0]} failed"),
                           data.get("status", 502), details={"command": args[0]}, **details)
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
                raise CliError("quota", "Quota parked the owned session; stop and report", 429)
            messages = self.messages(sid)
            if condition(session, messages):
                return session
            time.sleep(0.1)
        raise CliError("check_timeout", "Owned session did not satisfy the completion check", 504)

    def run(self, inference: bool) -> None:
        session = self.call("spawn", self.cwd)["session"]
        sid = session["id"]
        state = self.call("status", sid)["session"]
        if state.get("isQuotaParked"):
            raise CliError("quota", "Quota parked the owned session; stop and report", 429)
        if state["model"].get("provider") != "openai-codex" or state["model"].get("id") != "gpt-6.1-sol":
            raise CliError("selection_mismatch", "Owned server did not retain the exact model")
        if state["thinkingLevel"] != THINKING:
            self.gaps.append(f"Requested xhigh was clamped to {state['thinkingLevel']}. No xhigh inference is claimed.")
        self.evidence.append({"requestedThinking": THINKING, "effectiveThinking": state["thinkingLevel"]})
        if self.definition:
            with PrimeClient(self.socket, self.timeout) as wire:
                catalog = object_data(wire.request("get_model_catalog", activeSessionId=sid))
            models = array_field(catalog, "models")
            matches = [model for model in models if isinstance(model, dict)
                       and (model.get("provider"), model.get("id")) == (self.definition.provider, self.definition.id)]
            self.definition.expect(matches[0] if len(matches) == 1 else None)
            if state["thinkingLevel"] != THINKING:
                raise CliError("model_thinking_mismatch", "Native thinking level differs from the requested level", 409)
            self.evidence.append({"modelMetadataMatched": True})
        sessions = self.call("list", "--cwd", self.cwd)["sessions"]
        own = next(row for row in sessions if row["id"] == sid)
        if own.get("archived") is not False or not all(key in own for key in ("path", "messageCount", "modified")):
            raise CliError("metadata_gap", "Owned list row lacks required metadata")
        self.call("commands", sid)
        self.call("messages", sid)
        answer = self.call("answer", sid, "owned-ask", "owned-question", "not injected", expected=1)
        if answer.get("status") != 501 or answer.get("error") != "unsupported":
            raise CliError("answer_gap_hidden", "Interactive answer must be explicitly unsupported")
        if self.agent.owned:
            selection = self.call("model", sid, MODEL)
            if self.definition:
                self.definition.expect(selection["result"])
        else:
            self.evidence.append({"command": "model", "skipped": "Existing agent defaults are read-only"})
        if inference:
            with PrimeClient(self.socket, self.timeout) as wire:
                pause = wire.request("acquire_session_input_pause", activeSessionId=sid, leaseKey=str(uuid.uuid4()))
                try:
                    for mode in ((), ("--steer",), ("--follow-up",)):
                        self.call("prompt", sid, *mode, text="Owned inference-enabled queue check.")
                    queued = self.call("status", sid)["session"]
                    if queued["pendingMessageCount"] != 3:
                        raise CliError("queue_mismatch", "The paused owned session did not retain three inputs")
                    self.call("queue-resume", sid)
                    resumed = self.call("status", sid)["session"]
                    if resumed["queuedMessages"] != queued["queuedMessages"]:
                        raise CliError("queue_mismatch", "Native resume changed the paused queue previews")
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
        if self.agent.owned:
            self.call("thinking-level", sid, THINKING)
        else:
            self.evidence.append({"command": "thinking-level", "skipped": "Existing agent defaults are read-only"})
        effective = self.call("status", sid)["session"]["thinkingLevel"]
        self.evidence.append({"thinkingSetterAccepted": self.agent.owned, "effectiveThinking": effective})
        if self.definition and effective != THINKING:
            raise CliError("model_thinking_mismatch", "Native thinking setter did not retain the requested level", 409)
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
            run.add_argument("--model-definition", type=Path, default=MODEL_DEFINITION)
    args = parser.parse_args()
    if args.mode == "prepare":
        print(json.dumps(prepare(), indent=2))
        return 0
    check = None
    runtime = None
    result = {"ok": False, "model": MODEL, "inferenceRequested": args.inference,
              "parityComplete": False,
              "unsupportedCapabilities": ["interactiveAnswers", "runtimeDisposal", "internalQueueReplay"],
              "retainedOwnedSessions": []}
    if args.mode == "verify":
        result["runtime"] = {"started": False, "stopped": True, "socketRemoved": True}
    try:
        if not math.isfinite(args.timeout) or args.timeout <= 0:
            raise CliError("usage", "timeout must be finite and positive", 400)
        definition = ModelDefinition.load(args.model_definition) if args.mode == "verify" else None
        check = Check(args.root, args.timeout, definition)
        if args.mode == "verify":
            result["modelMetadata"] = {"source": str(args.model_definition), "limitations": METADATA_LIMITATIONS,
                                       "registration": "temporary-owned" if check.agent.owned else "existing-agent"}
            runtime = VerificationRuntime(check.root, args.runtime.resolve(), args.timeout, definition, agent=check.agent)
            runtime.start()
        if args.mode == "verify":
            check.run(False)
            if args.inference:
                check.run(True)
        else:
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
                result["cleanupError"] = CliError("runtime_cleanup_failed", "Owned runtime cleanup failed").output
                result.setdefault("error", result["cleanupError"])
                result["ok"] = False
            result["runtime"] = runtime.evidence
            if not runtime.evidence["stopped"] or not runtime.evidence["socketRemoved"]:
                result["ok"] = False
    print(json.dumps(result, indent=2))
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

"""Prime supervisor JSONL transport and pi-web-cli-compatible projections."""
from __future__ import annotations

import argparse
import json
import math
import os
import socket
import sys
import tempfile
import time
import uuid
from dataclasses import dataclass
from typing import Any, Literal

PROTOCOL = {"name": "prime-agent.daemon", "version": 7}
LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")


class CliError(Exception):
    def __init__(self, code: str, message: str, status: int = 502, **details: Any):
        super().__init__(message)
        self.output = {"ok": False, "status": status, "error": code, "message": message, **details}


def transport_failure(error: OSError) -> CliError:
    if isinstance(error, TimeoutError):
        return CliError("timeout", "Prime daemon timed out; command outcome may be uncertain", 504)
    return CliError("transport_error", f"Prime daemon transport failed: {error.strerror or type(error).__name__}")


class Parser(argparse.ArgumentParser):
    def error(self, message: str) -> None:
        raise CliError("usage", message, 400)


def reject_json_constant(value: str) -> None:
    raise ValueError(f"Invalid JSON constant {value}")


def object_data(value: Any) -> dict:
    if not isinstance(value, dict):
        raise CliError("invalid_response", "Expected an object in response data")
    return value


def array_field(data: dict, name: str) -> list:
    value = data.get(name)
    if not isinstance(value, list):
        raise CliError("invalid_response", f"Expected array field {name}")
    return value


@dataclass(frozen=True)
class QueuePreview:
    steering: tuple[str, ...]
    follow_up: tuple[str, ...]
    representation: Literal["previews"] = "previews"
    replay_safe: Literal[False] = False

    @classmethod
    def parse(cls, value: Any) -> QueuePreview:
        queue = object_data(value)
        steering, follow_up = array_field(queue, "steering"), array_field(queue, "followUp")
        if any(not isinstance(text, str) for text in [*steering, *follow_up]):
            raise CliError("invalid_response", "Prime queue previews must be strings")
        return cls(tuple(steering), tuple(follow_up))

    def messages(self) -> list[dict]:
        return [{"kind": kind, "text": text} for kind, lane in (("steer", self.steering), ("followUp", self.follow_up)) for text in lane]


@dataclass(frozen=True)
class ObservedCapabilities:
    interactive_answers: Literal[False] = False
    runtime_disposal: Literal[False] = False
    internal_queue_replay: Literal[False] = False
    same_session_queue_resume: Literal[True] = True

    def projection(self) -> dict:
        return {"interactiveAnswers": self.interactive_answers, "runtimeDisposal": self.runtime_disposal,
                "internalQueueReplay": self.internal_queue_replay, "sameSessionQueueResume": self.same_session_queue_resume}


@dataclass(frozen=True)
class SessionIdentity:
    session_id: str
    active_session_id: str | None

    @classmethod
    def parse(cls, data: dict, *, require_active: bool = False) -> SessionIdentity:
        sid, active = data.get("sessionId"), data.get("activeSessionId")
        if not isinstance(sid, str) or not sid:
            raise CliError("invalid_response", "Prime response lacks a durable sessionId")
        if require_active and (not isinstance(active, str) or not active):
            raise CliError("invalid_response", "Prime connection state has no active session id")
        return cls(sid, active if isinstance(active, str) and active else None)


def split_model(selector: str) -> tuple[str, str]:
    provider, slash, model = selector.partition("/")
    if not slash or not provider or not model or selector != selector.strip():
        raise CliError("usage", "model must be provider/modelId", 400)
    return provider, model


@dataclass(frozen=True)
class Command:
    kind: str
    fields: dict

    def envelope(self, request_id: str, client_id: str) -> dict:
        return {"type": "command", "id": request_id, "protocol": PROTOCOL,
                "clientId": client_id, "command": {"type": self.kind, **self.fields}}


class PrimeClient:
    def __init__(self, path: str, timeout: float = 20):
        self.path = path
        self.timeout = timeout
        self.client_id = f"prime-cli:{uuid.uuid4()}"
        self.buffer = bytearray()
        self.stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)

    def __enter__(self) -> PrimeClient:
        try:
            self.stream.settimeout(self.timeout)
            self.stream.connect(self.path)
            hello = self.read_frame(time.monotonic() + self.timeout)
            protocol = hello.get("protocol")
            if (hello.get("type") != "daemon_hello" or not isinstance(protocol, dict)
                    or protocol.get("name") != PROTOCOL["name"]
                    or type(protocol.get("version")) is not int or protocol["version"] != 7):
                raise CliError("protocol_mismatch", "Expected Prime daemon protocol 7")
            return self
        except BaseException:
            self.stream.close()
            raise

    def __exit__(self, *_: Any) -> None:
        self.stream.close()

    def read_frame(self, deadline: float) -> dict:
        while b"\n" not in self.buffer:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("Prime daemon response deadline elapsed")
            self.stream.settimeout(remaining)
            chunk = self.stream.recv(65536)
            if not chunk:
                raise CliError("transport_closed", "Prime daemon closed the connection; command outcome may be uncertain")
            self.buffer.extend(chunk)
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        try:
            frame = json.loads(line.decode("utf-8"), parse_constant=reject_json_constant)
        except (UnicodeDecodeError, ValueError) as exc:
            raise CliError("invalid_response", "Prime daemon sent malformed JSONL") from exc
        return object_data(frame)

    def request(self, kind: str, **fields: Any) -> Any:
        request_id = str(uuid.uuid4())
        command = Command(kind, fields)
        deadline = time.monotonic() + self.timeout
        self.stream.settimeout(self.timeout)
        self.stream.sendall((json.dumps(command.envelope(request_id, self.client_id), ensure_ascii=False) + "\n").encode("utf-8"))
        while True:
            frame = self.read_frame(deadline)
            frame_type = frame.get("type")
            if frame_type != "response":
                if not isinstance(frame_type, str):
                    raise CliError("invalid_response", "Prime daemon frame has no type")
                if frame_type == "daemon_closing":
                    raise CliError("transport_closed", "Prime daemon is closing; command outcome may be uncertain")
                continue
            if not isinstance(frame.get("id"), str):
                raise CliError("invalid_response", "Prime response has no correlation id")
            if frame["id"] != request_id:
                continue
            if frame.get("command") != kind or type(frame.get("success")) is not bool:
                raise CliError("invalid_response", "Prime response does not match the command contract")
            if not frame["success"]:
                error = frame.get("error")
                if not isinstance(error, str):
                    raise CliError("invalid_response", "Prime failure response has no error")
                info = frame.get("errorInfo")
                details = {"errorInfo": info} if isinstance(info, dict) else {}
                raise CliError("upstream_error", error, **details)
            if "error" in frame:
                raise CliError("invalid_response", "Prime success response also contains an error")
            return frame.get("data")

    def session_state(self, sid: str) -> dict:
        state = object_data(self.request("get_connection_state", activeSessionId=sid))
        identity = SessionIdentity.parse(state, require_active=True)
        if identity.session_id != sid:
            raise CliError("wrong_session", "Prime returned state for a different durable session")
        if type(state.get("isStreaming")) is not bool:
            raise CliError("invalid_response", "Prime connection state has no streaming flag")
        return state


def session_row(row: Any) -> dict:
    row = object_data(row)
    sid = SessionIdentity.parse(row).session_id
    if not isinstance(row.get("cwd"), str):
        raise CliError("invalid_response", "Prime session row lacks cwd")
    state = row.get("state")
    archived = row.get("lifecycle") == "archived" or isinstance(state, dict) and state.get("status") == "archived"
    result = {**row, "id": sid, "archived": archived}
    if isinstance(row.get("sessionFile"), str):
        result["path"] = row["sessionFile"]
    return result


def expect_model(data: Any, requested: tuple[str, str]) -> dict:
    model = object_data(data)
    if (model.get("provider"), model.get("id")) != requested:
        raise CliError("model_mismatch", "Prime did not select the requested provider/model", 409)
    return model


def spawn(client: PrimeClient, cwd: str) -> dict:
    selection = os.environ.get("PRIME_CLI_MODEL")
    thinking = os.environ.get("PRIME_CLI_THINKING")
    requested = split_model(selection) if selection else None
    fields: dict[str, Any] = {"cwd": cwd}
    if requested:
        fields.update(provider=requested[0], model=requested[1])
    if thinking:
        if thinking not in LEVELS:
            raise CliError("usage", "Invalid PRIME_CLI_THINKING", 400)
        fields["thinking"] = thinking
    row = session_row(client.request("create", lifecycle="resident", telemetryDisabled=True, config=fields))
    if row["cwd"] != cwd:
        raise CliError("cwd_mismatch", "Prime did not use the requested cwd", 409, session=row)
    if requested:
        try:
            state = client.session_state(row["id"])
            if state.get("cwd") != cwd:
                raise CliError("cwd_mismatch", "Prime connection state has a different cwd", 409)
            expect_model(state.get("model"), requested)
            row.update(activeSessionId=state["activeSessionId"], model=state["model"], thinkingLevel=state.get("thinkingLevel"))
        except (CliError, OSError) as exc:
            failure = exc if isinstance(exc, CliError) else transport_failure(exc)
            failure.output["session"] = row
            raise failure
    return {"ok": True, "status": 201, "session": row}


def status(client: PrimeClient, sid: str) -> dict:
    state = client.session_state(sid)
    active = state["activeSessionId"]
    queue = QueuePreview.parse(client.request("get_queue", activeSessionId=active))
    stats = object_data(client.request("get_session_stats", activeSessionId=active))
    cost = stats.get("cost")
    if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost):
        raise CliError("invalid_response", "Prime session stats have no numeric cost")
    usage = state.get("contextUsage")
    if usage is not None and not isinstance(usage, dict):
        raise CliError("invalid_response", "Prime context usage is neither an object nor null")
    queued = queue.messages()
    session = {**state, "id": state["sessionId"], "pendingMessageCount": len(queued), "queuedMessages": queued,
               "queueRepresentation": queue.representation, "queueReplaySafe": queue.replay_safe,
               "pendingAsk": None, "capabilities": ObservedCapabilities().projection(),
               "contextUsage": usage, "cost": cost}
    return {"ok": True, "status": 200, "session": session}


SIMPLE_VERBS = {
    "stop": ("abort_and_clear_queue", ()),
    "abort": ("abort_and_clear_queue", ()),
    "queue-clear": ("clear_queue", ()),
    "queue-resume": ("resume_queue", ()),
    "archive": ("kill", ()),
    "messages": ("get_messages", ()),
    "model": ("set_model", ("model",)),
    "thinking-level": ("set_thinking_level", ("level",)),
}


def parser() -> Parser:
    root = Parser(description="Prime supervisor control plane; never starts a daemon")
    root.add_argument("--socket", help="supervisor Unix socket; overrides PRIME_AGENT_DAEMON_SOCKET")
    sub = root.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list").add_argument("--cwd", required=True)
    sub.add_parser("spawn").add_argument("cwd")
    prompt = sub.add_parser("prompt")
    prompt.add_argument("sid")
    prompt.add_argument("text", nargs="?")
    modes = prompt.add_mutually_exclusive_group()
    modes.add_argument("--steer", action="store_true")
    modes.add_argument("--follow-up", action="store_true")
    for name in ("status", "commands", *SIMPLE_VERBS):
        verb = sub.add_parser(name)
        verb.add_argument("sid")
        if name == "stop":
            verb.add_argument("--require-runtime-close", action="store_true")
        elif name == "queue-clear":
            verb.add_argument("--require-replay-safe", action="store_true")
        if name in SIMPLE_VERBS:
            for positional in SIMPLE_VERBS[name][1]:
                verb.add_argument(positional, **({"choices": LEVELS} if positional == "level" else {}))
    answer = sub.add_parser("answer")
    for name in ("sid", "ask_id", "question_id", "text"):
        answer.add_argument(name)
    return root


def execute(client: PrimeClient, args: argparse.Namespace) -> dict:
    if args.cmd == "spawn":
        return spawn(client, args.cwd)
    if args.cmd == "status":
        return status(client, args.sid)
    if args.cmd == "list":
        data = object_data(client.request("list", all=True, cwd=args.cwd))
        sessions = [session_row(row) for row in array_field(data, "sessions")]
        sessions = [row for row in sessions if row["cwd"] == args.cwd]
        return {"ok": True, "status": 200, "sessions": sessions}
    if args.cmd == "commands":
        data = object_data(client.request("get_commands", activeSessionId=args.sid))
        return {"ok": True, "status": 200, "commands": array_field(data, "commands")}
    if args.cmd == "prompt":
        text = args.text
        kind = "steer" if args.steer else "follow_up" if args.follow_up else "prompt"
        fields = {"activeSessionId": args.sid, "message": text}
        if kind == "prompt":
            fields["streamingBehavior"] = "followUp"
        data = client.request(kind, **fields)
        result = {} if data is None else object_data(data)
        return {"ok": True, "status": 200, "result": {**result, "accepted": True}}
    kind, _ = SIMPLE_VERBS[args.cmd]
    fields = {"activeSessionId": args.sid}
    if args.cmd == "archive":
        pause = object_data(client.request("acquire_session_input_pause", activeSessionId=args.sid, leaseKey=str(uuid.uuid4())))
        if not isinstance(pause.get("pauseId"), str) or not pause["pauseId"]:
            raise CliError("invalid_response", "Prime returned no input-pause lease")
        state = client.session_state(args.sid)
        active = state["activeSessionId"]
        summary = object_data(client.request("get_state", activeSessionId=active))
        if summary.get("activeSessionId") != active or summary.get("sessionId") != args.sid:
            raise CliError("wrong_session", "Prime returned a different session during archive preflight")
        queue = QueuePreview.parse(client.request("get_queue", activeSessionId=active))
        flags = [state.get(name) for name in ("isStreaming", "isCompacting", "isBashRunning")]
        flags.append(summary.get("hasRunningSubagents"))
        if any(type(flag) is not bool for flag in flags):
            raise CliError("invalid_response", "Prime archive preflight lacks activity flags")
        if any(flags) or queue.steering or queue.follow_up:
            raise CliError("session_busy", "Cannot archive a session with active or queued work", 409)
        fields["activeSessionId"] = active
    requested = None
    if args.cmd == "model":
        requested = split_model(args.model)
        fields.update(provider=requested[0], modelId=requested[1])
    elif args.cmd == "thinking-level":
        fields["level"] = args.level
    data = client.request(kind, **fields)
    if requested:
        expect_model(data, requested)
    if args.cmd == "messages":
        array_field(object_data(data), "messages")
    if args.cmd == "archive":
        data = {"archived": True, "preflightAtomic": False}
    elif args.cmd == "stop":
        data = {**({} if data is None else object_data(data)), "accepted": True,
                "runtimeClosed": False, "semantics": "abort-and-clear-resident-shim"}
    return {"ok": True, "status": 200, "result": data if data is not None else {}}


def main(argv: list[str] | None = None) -> int:
    try:
        args = parser().parse_args(argv)
        if args.cmd == "answer":
            raise CliError("unsupported", "Prime has no correlated interactive-answer API", 501)
        if args.cmd == "stop" and args.require_runtime_close:
            raise CliError("unsupported", "Prime cannot dispose an existing resident root without archival", 501,
                           capability="runtimeDisposal")
        if args.cmd == "queue-clear" and args.require_replay_safe:
            raise CliError("unsupported", "Prime cannot export replay-safe internal queue items", 501,
                           capability="internalQueueReplay")
        if args.cmd == "model":
            split_model(args.model)
        if args.cmd == "prompt":
            if args.text is None:
                args.text = sys.stdin.read()
            if not args.text.strip():
                raise CliError("usage", "empty prompt", 400)
        path = args.socket or os.environ.get("PRIME_AGENT_DAEMON_SOCKET") or os.path.join(
            os.environ.get("TMPDIR", tempfile.gettempdir()), f"prime-agent-{os.getuid()}", "daemon.sock")
        try:
            timeout = float(os.environ.get("PRIME_CLI_TIMEOUT", "20"))
        except ValueError as exc:
            raise CliError("usage", "PRIME_CLI_TIMEOUT must be a positive number", 400) from exc
        if not math.isfinite(timeout) or timeout <= 0:
            raise CliError("usage", "PRIME_CLI_TIMEOUT must be a positive number", 400)
        with PrimeClient(path, timeout) as client:
            output = execute(client, args)
    except CliError as exc:
        output = exc.output
    except OSError as exc:
        output = transport_failure(exc).output
    print(json.dumps(output, indent=2, ensure_ascii=False, allow_nan=False))
    return 0 if output["ok"] else 1

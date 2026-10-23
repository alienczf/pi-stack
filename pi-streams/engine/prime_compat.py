"""Legacy CLI projections over the shared public Prime transport."""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import tempfile
import uuid
from dataclasses import dataclass

from engine.prime import (CliError, LEVELS, PrimeClient, SessionIdentity, array_field,
                          object_data, transport_failure)


class Parser(argparse.ArgumentParser):
    def error(self, message):
        raise CliError("usage", message, 400)


@dataclass(frozen=True)
class QueuePreview:
    steering: tuple[str, ...]
    follow_up: tuple[str, ...]
    representation: str = "previews"
    replay_safe: bool = False

    @classmethod
    def parse(cls, value):
        queue = object_data(value)
        steering, follow_up = array_field(queue, "steering"), array_field(queue, "followUp")
        if any(not isinstance(text, str) for text in [*steering, *follow_up]):
            raise CliError("invalid_response", "Prime queue previews must be strings")
        return cls(tuple(steering), tuple(follow_up))

    def messages(self):
        return [{"kind": kind, "text": text} for kind, lane in (("steer", self.steering), ("followUp", self.follow_up)) for text in lane]


def split_model(selector):
    provider, slash, model = selector.partition("/")
    if not slash or not provider or not model or selector != selector.strip():
        raise CliError("usage", "model must be provider/modelId", 400)
    return provider, model


def session_row(row):
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


def expect_model(data, requested):
    model = object_data(data)
    if (model.get("provider"), model.get("id")) != requested:
        raise CliError("model_mismatch", "Prime did not select the requested provider/model", 409)
    return model


def spawn(client, cwd):
    selection = os.environ.get("PRIME_CLI_MODEL")
    thinking = os.environ.get("PRIME_CLI_THINKING")
    requested = split_model(selection) if selection else None
    fields = {"cwd": cwd}
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


def status(client, sid):
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
               "pendingAsk": None, "capabilities": {"interactiveAnswers": False, "runtimeDisposal": False,
               "internalQueueReplay": False, "sameSessionQueueResume": True}, "contextUsage": usage, "cost": cost}
    return {"ok": True, "status": 200, "session": session}


SIMPLE_VERBS = {
    "stop": ("abort_and_clear_queue", ()), "abort": ("abort_and_clear_queue", ()),
    "queue-clear": ("clear_queue", ()), "queue-resume": ("resume_queue", ()),
    "archive": ("kill", ()), "messages": ("get_messages", ()),
    "model": ("set_model", ("model",)), "thinking-level": ("set_thinking_level", ("level",)),
}


def parser():
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


def execute(client, args):
    if args.cmd == "spawn":
        return spawn(client, args.cwd)
    if args.cmd == "status":
        return status(client, args.sid)
    if args.cmd == "list":
        data = object_data(client.request("list", all=True, cwd=args.cwd))
        sessions = [session_row(row) for row in array_field(data, "sessions")]
        return {"ok": True, "status": 200, "sessions": [row for row in sessions if row["cwd"] == args.cwd]}
    if args.cmd == "commands":
        data = object_data(client.request("get_commands", activeSessionId=args.sid))
        return {"ok": True, "status": 200, "commands": array_field(data, "commands")}
    if args.cmd == "prompt":
        kind = "steer" if args.steer else "follow_up" if args.follow_up else "prompt"
        fields = {"activeSessionId": args.sid, "message": args.text}
        if kind == "prompt":
            fields["streamingBehavior"] = "followUp"
        data = client.request(kind, **fields)
        return {"ok": True, "status": 200, "result": {**({} if data is None else object_data(data)), "accepted": True}}
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


def main(argv=None):
    try:
        args = parser().parse_args(argv)
        if args.cmd == "answer":
            raise CliError("unsupported", "Prime has no correlated interactive-answer API", 501)
        if args.cmd == "stop" and args.require_runtime_close:
            raise CliError("unsupported", "Prime cannot dispose an existing resident root without archival", 501, capability="runtimeDisposal")
        if args.cmd == "queue-clear" and args.require_replay_safe:
            raise CliError("unsupported", "Prime cannot export replay-safe internal queue items", 501, capability="internalQueueReplay")
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

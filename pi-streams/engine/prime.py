"""Public protocol 7/schema 30 transport and explicitly owned Prime sessions."""
from __future__ import annotations

import json
import math
import os
import socket
import stat
import subprocess
import sys
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from engine import StreamsError

PROTOCOL = {"name": "prime-agent.daemon", "version": 7}
LEVELS = ("off", "minimal", "low", "medium", "high", "xhigh", "max")


class CliError(StreamsError):
    def __init__(self, code: str, message: str, status: int = 502, **details: Any):
        super().__init__(message)
        self.output = {"ok": False, "status": status, "error": code, "message": message, **details}


class UsageQuotaError(CliError):
    def __init__(self, frame):
        info = frame.get("errorInfo")
        super().__init__("upstream_error", frame.get("error", "provider usage or quota failure"),
                         **({"errorInfo": info} if isinstance(info, dict) else {}))
        self.frame = frame


def usage_or_quota(frame):
    text = str(frame.get("error", "")) + " " + str(frame.get("errorInfo", {}))
    return frame.get("success") is False and any(word in text.lower() for word in ("quota", "usage", "rate_limit", "rate limit"))


def transport_failure(error: OSError) -> CliError:
    if isinstance(error, TimeoutError):
        return CliError("timeout", "Prime daemon timed out; command outcome may be uncertain", 504)
    return CliError("transport_error", f"Prime daemon transport failed: {error.strerror or type(error).__name__}")


def reject_json_constant(value):
    raise ValueError(f"Invalid JSON constant {value}")


def object_data(value):
    if not isinstance(value, dict):
        raise CliError("invalid_response", "Expected an object in response data")
    return value


def array_field(data, name):
    value = data.get(name)
    if not isinstance(value, list):
        raise CliError("invalid_response", f"Expected array field {name}")
    return value


@dataclass(frozen=True)
class SessionIdentity:
    session_id: str
    active_session_id: str | None

    @classmethod
    def parse(cls, data, *, require_active=False):
        sid, active = data.get("sessionId"), data.get("activeSessionId")
        if not isinstance(sid, str) or not sid:
            raise CliError("invalid_response", "Prime response lacks a durable sessionId")
        if require_active and (not isinstance(active, str) or not active):
            raise CliError("invalid_response", "Prime connection state has no active session id")
        return cls(sid, active if isinstance(active, str) and active else None)


@dataclass(frozen=True)
class Command:
    kind: str
    fields: dict

    def envelope(self, request_id, client_id):
        return {"type": "command", "id": request_id, "protocol": PROTOCOL,
                "clientId": client_id, "command": {"type": self.kind, **self.fields}}


class PrimeClient:
    def __init__(self, path: str, timeout: float | None = None):
        self.path, self.timeout = str(path), timeout
        self.client_id = f"pi-stack:{uuid.uuid4()}"
        self.buffer = bytearray()
        self.stream = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.pending: dict[str, str] = {}
        self.replies: dict[str, dict] = {}
        self.events: list[dict] = []
        self.write_lock = threading.Lock()
        self.read_lock = threading.Lock()
        self.connected = False

    def __enter__(self):
        return self.connect()

    def __exit__(self, *_):
        self.close()

    def connect(self):
        try:
            self.stream.settimeout(self.timeout)
            if sys.platform == "linux" and len(os.fsencode(self.path)) > 107:
                path = Path(self.path)
                fd = os.open(path.parent, getattr(os, "O_PATH", os.O_RDONLY) | os.O_DIRECTORY)
                try:
                    self.stream.connect(f"/proc/self/fd/{fd}/{path.name}")
                finally:
                    os.close(fd)
            else:
                self.stream.connect(self.path)
            hello = self.read_frame(self._deadline())
            protocol = hello.get("protocol")
            if (hello.get("type") != "daemon_hello" or protocol != PROTOCOL
                    or type(protocol.get("version")) is not int
                    or type(hello.get("schemaRevision")) is not int or hello["schemaRevision"] != 30):
                raise CliError("protocol_mismatch", "Expected Prime daemon protocol 7/schema 30")
            self.connected = True
            return self
        except BaseException:
            self.close()
            raise

    def close(self):
        self.connected = False
        self.stream.close()

    def _deadline(self):
        return None if self.timeout is None else time.monotonic() + self.timeout

    def read_frame(self, deadline=None):
        while b"\n" not in self.buffer:
            remaining = None if deadline is None else deadline - time.monotonic()
            if remaining is not None and remaining <= 0:
                raise TimeoutError("Prime daemon response deadline elapsed")
            self.stream.settimeout(remaining)
            chunk = self.stream.recv(65536)
            if not chunk:
                raise CliError("transport_closed", "Prime daemon closed the connection; command outcome may be uncertain")
            self.buffer.extend(chunk)
        line, _, rest = self.buffer.partition(b"\n")
        self.buffer = bytearray(rest)
        try:
            return object_data(json.loads(line.decode("utf-8"), parse_constant=reject_json_constant))
        except (UnicodeDecodeError, ValueError) as exc:
            raise CliError("invalid_response", "Prime daemon sent malformed JSONL") from exc

    def write(self, kind: str, *, command_id: str | None = None, **fields):
        request_id = command_id or str(uuid.uuid4())
        if str(uuid.UUID(request_id)) != request_id:
            raise CliError("usage", "Command id must be a canonical UUID", 400)
        with self.write_lock:
            if request_id in self.pending or request_id in self.replies:
                raise CliError("duplicate_command", "Command already written; inspect its result, do not resend", 409)
            self.pending[request_id] = kind
            payload = Command(kind, fields).envelope(request_id, self.client_id)
            self.stream.sendall((json.dumps(payload, ensure_ascii=False, allow_nan=False) + "\n").encode())
        return request_id

    def wait(self, request_id: str):
        if request_id not in self.pending:
            raise CliError("unknown_command", "Command was not written on this connection", 409)
        deadline = self._deadline()
        with self.read_lock:
            while request_id not in self.replies:
                frame = self.read_frame(deadline)
                kind = frame.get("type")
                if kind != "response":
                    if not isinstance(kind, str):
                        raise CliError("invalid_response", "Prime daemon frame has no type")
                    if kind == "daemon_closing":
                        raise CliError("transport_closed", "Prime daemon is closing; command outcome may be uncertain")
                    self.events.append(frame)
                    continue
                if not isinstance(frame.get("id"), str):
                    raise CliError("invalid_response", "Prime response has no correlation id")
                target = frame["id"]
                if target not in self.pending:
                    continue
                if frame.get("command") != self.pending[target] or type(frame.get("success")) is not bool:
                    raise CliError("invalid_response", "Prime response does not match the command contract")
                if frame["success"] and "error" in frame or not frame["success"] and not isinstance(frame.get("error"), str):
                    raise CliError("invalid_response", "Prime response has conflicting or missing error")
                if target in self.replies and self.replies[target] != frame:
                    raise CliError("invalid_response", "Conflicting duplicate Prime response")
                self.replies[target] = frame
                if usage_or_quota(frame):
                    raise UsageQuotaError(frame)
            return self.replies[request_id]

    def query(self, kind, **fields):
        frame = self.wait(self.write(kind, **fields))
        if not frame["success"]:
            info = frame.get("errorInfo")
            raise CliError("upstream_error", frame["error"], **({"errorInfo": info} if isinstance(info, dict) else {}))
        return frame.get("data")

    request = query

    def session_state(self, sid):
        state = object_data(self.query("get_connection_state", activeSessionId=sid))
        identity = SessionIdentity.parse(state, require_active=True)
        if identity.session_id != sid:
            raise CliError("wrong_session", "Prime returned state for a different durable session")
        if type(state.get("isStreaming")) is not bool:
            raise CliError("invalid_response", "Prime connection state has no streaming flag")
        return state


def resolve_session(client, durable_id, active_id=None):
    data = object_data(client.query("get_connection_state", activeSessionId=active_id or durable_id))
    identity = SessionIdentity.parse(data, require_active=True)
    if identity.session_id != durable_id or active_id is not None and identity.active_session_id != active_id:
        raise CliError("wrong_session", "Prepared Prime session no longer matches")
    return identity, data


def validate_stream_settings(stream):
    path = Path(stream) / ".prime" / "agent" / "settings.json"
    if any(p.is_symlink() for p in (path, path.parent, path.parent.parent)):
        raise StreamsError("symlink Prime settings")
    try:
        data = json.loads(path.read_text(), parse_constant=reject_json_constant)
        compaction = data["compaction"]
        percent = compaction["thresholdPercent"]
        if (compaction["enabled"] is not False or compaction["agentCallable"] is not False
                or isinstance(percent, bool) or not isinstance(percent, (int, float))
                or not math.isfinite(percent) or not 0 < percent <= 100):
            raise ValueError("invalid compaction settings")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise StreamsError(f"invalid owned Prime settings: {exc}") from exc
    return data


def create_stream_session(client, stream, model, thinking):
    validate_stream_settings(stream)
    return _create_session(client, Path(stream), model, thinking)


def _create_session(client, worktree, model, thinking):
    from engine.prime_compat import split_model, expect_model
    provider, model_id = split_model(model)
    if thinking not in LEVELS:
        raise StreamsError("invalid thinking level")
    row = object_data(client.query("create", lifecycle="resident", telemetryDisabled=True,
                                   config={"cwd": str(worktree.resolve()), "provider": provider, "model": model_id, "thinking": thinking}))
    identity = SessionIdentity.parse(row)
    resolved, data = resolve_session(client, identity.session_id, identity.active_session_id)
    expect_model(data.get("model"), (provider, model_id))
    if data.get("thinkingLevel") != thinking or data.get("cwd") != str(worktree.resolve()):
        raise CliError("configuration_mismatch", "Prime changed requested thinking or worktree", 409, sessionId=resolved.session_id)
    return resolved


def save_reply(stream, *, session_id, command_id, sent_text, frame, messages):
    from engine.state import append_log, sha256
    return append_log(stream, subject="Prime reply", session_id=session_id, command_id=command_id, purpose="reply",
                      body={"command": frame["command"], "sent_text_sha256": sha256(sent_text), "success": frame["success"],
                            "error": frame.get("error"), "data": frame.get("data"), "messages": messages})


@dataclass
class OwnedDaemon:
    process: subprocess.Popen
    socket: Path
    log_handle: Any
    socket_identity: tuple[int, int] | None = None


def start_owned_daemon(binary, socket_path, log_path, *, env=None):
    path = Path(socket_path)
    if path.exists() or path.is_symlink():
        raise StreamsError("refusing existing daemon socket")
    path.parent.mkdir(parents=True, exist_ok=True)
    handle = open(log_path, "xb")
    try:
        process = subprocess.Popen([str(binary), "--mode", "daemon", "--daemon-socket", str(path)], env=env, stdout=handle, stderr=subprocess.STDOUT)
        owned = OwnedDaemon(process, path, handle)
        while not path.exists():
            if process.poll() is not None:
                raise StreamsError(f"owned daemon exited with {process.returncode}")
            time.sleep(0.05)
        info = path.lstat()
        if not stat.S_ISSOCK(info.st_mode):
            raise StreamsError("owned daemon did not create a socket")
        owned.socket_identity = (info.st_dev, info.st_ino)
        return owned
    except BaseException:
        if 'process' in locals() and process.poll() is None:
            process.terminate()
            process.wait()
        handle.close()
        raise


def stop_owned_daemon(owned):
    try:
        if owned.process.poll() is None:
            try:
                info = owned.socket.lstat()
                if not stat.S_ISSOCK(info.st_mode) or (info.st_dev, info.st_ino) != owned.socket_identity:
                    raise StreamsError("owned daemon socket identity changed; no replacement was contacted")
                with PrimeClient(str(owned.socket)) as client:
                    client.query("shutdown", force=True)
            except (StreamsError, OSError):
                if owned.process.poll() is None:
                    owned.process.terminate()
        owned.process.wait()
    finally:
        owned.log_handle.close()


@dataclass(frozen=True)
class PendingMessage:
    command_id: str
    identity: SessionIdentity
    text: str
    original_entries: tuple[str, ...]
    mode: str


def create_worker_session(client, worktree, model, thinking):
    return _create_session(client, Path(worktree), model, thinking)


def send_worker(client, stream, identity, text, original_entries):
    from engine.state import append_log
    command = str(uuid.uuid4())
    append_log(Path(stream), subject="Before clean worker kickoff", session_id=identity.session_id,
               command_id=command, purpose="worker-before-send", body={"handover": text, "original_entries": list(original_entries), "result": "unknown until reply saved"})
    client.write("prompt_and_wait", command_id=command, activeSessionId=identity.active_session_id,
                 message=text, streamingBehavior="followUp")
    return finish_message(client, stream, PendingMessage(command, identity, text, tuple(original_entries), "worker"))


def stream_entries(stream):
    from engine import state
    current = state.check_state(stream)
    return current, state._entries(stream, current)


def coordinator_id(stream):
    from engine.threads import load_threads, Status
    rows = [row for row in load_threads(Path(stream) / "threads.tsv") if row.role == "coordinator" and row.status is Status.active]
    if len(rows) != 1:
        raise StreamsError("stream needs exactly one current coordinator")
    return rows[0].session


def unresolved(entries):
    before = {e.command for e in entries.values() if "goals_rules_sha256" in e.body}
    replies = {e.command for e in entries.values() if "sent_text_sha256" in e.body}
    return before - replies


def eligible(current, entries):
    if current.goals.status != "active" or not current.goals.objective:
        return False
    if unresolved(entries) or any(w.required is None for w in current.goals.work):
        return False
    replies = [e for e in entries.values() if "sent_text_sha256" in e.body]
    if replies and max(replies, key=lambda e: e.timestamp).body["success"] is not True:
        return False
    return any(w.required and not w.waiting_for for w in current.goals.work)


def check_current_command(stream, identity, expected, *, mode="automatic"):
    from engine import state
    from engine.prompts import render
    try:
        current = state.check_current_text(stream, expected)
    except StreamsError as exc:
        raise StreamsError(render("stale", stream_id=Path(stream).name, command_name=mode).strip()) from exc
    _, entries = stream_entries(stream)
    if coordinator_id(stream) != identity.session_id or mode not in {"human", "save", "input"} and not eligible(current, entries):
        raise StreamsError(render("stale", stream_id=Path(stream).name, command_name=mode).strip())
    if current.goals.status == "paused" and mode != "human":
        raise StreamsError("operator stop supersedes automatic work")
    return current


def send_stream_message(client, stream, identity, *, body, command_id=None, sender=None,
                        lane="followUp", mode="human", expected=None, original_entries=(),
                        attachments=(), wait_result=True, metadata=None, sessions_dir=None):
    from engine import state
    from engine.project import stream_lock
    from engine.prompts import render
    stream = Path(stream)
    if attachments:
        raise StreamsError("attachments are not supported")
    if lane not in {"steer", "followUp"}:
        raise StreamsError("invalid streaming lane")
    command = command_id or str(uuid.uuid4())
    with stream_lock(stream):
        current, entries = stream_entries(stream)
        if mode == "human":
            saved = state.save_message(stream, text=body, command_id=command, session_id=identity.session_id,
                                       sender=sender, send_as=lane, locked=True)
            original_entries = (saved["entry"],)
            current, entries = stream_entries(stream)
        prior = [e for e in entries.values() if e.command == command and "goals_rules_sha256" in e.body]
        if prior:
            replies = [e for e in entries.values() if e.command == command and "sent_text_sha256" in e.body]
            return {"sending_status": "Prime replied" if replies else "unknown after connection loss", "entry": replies[0].file if replies else prior[0].file}
    if mode in {"human", "automatic"}:
        maintenance = check_compaction(client, stream, identity, sessions_dir=sessions_dir)
        if maintenance["status"] == "held" and (mode != "human" or maintenance.get("reason") == "pending or unknown DCR"):
            return {"sending_status": "not sent", "held": maintenance}
    with stream_lock(stream):
        current, entries = stream_entries(stream)
        prior = [e for e in entries.values() if e.command == command and "goals_rules_sha256" in e.body]
        if prior:
            return {"sending_status": "Prime replied", "entry": prior[0].file}
        expected = expected or current.goals_rules_sha256
        check_current_command(stream, identity, expected, mode=mode)
        resolve_session(client, identity.session_id, identity.active_session_id)
        note = {"command": {"type": "prompt_and_wait", "session": identity.session_id, "lane": lane},
                "body": body, "original_entries": list(original_entries), "goals_rules_sha256": expected,
                "result": "unknown until reply saved"}
        if metadata:
            note.update(metadata)
        state.append_log(stream, subject="Before send", body=note, session_id=identity.session_id,
                         command_id=command, purpose="before-send", locked=True)
        current = state.check_state(stream)
        agents = state._read(state._path(stream, "AGENTS.md"))
        text = render("stream", stream_id=stream.name, session_id=identity.session_id, command_id=command,
                      agents_path=str(stream / "AGENTS.md"), agents_sha256=state.sha256(agents), agents_text=agents,
                      state_path=str(stream / "STATE.md"), state_sha256=current.sha256, state_text=current.text,
                      original_entries=list(original_entries), body_text=body)
        client.write("prompt_and_wait", command_id=command, activeSessionId=identity.active_session_id,
                     message=text, streamingBehavior=lane)
    pending = PendingMessage(command, identity, text, tuple(original_entries), mode)
    return finish_message(client, stream, pending, sessions_dir=sessions_dir) if wait_result else pending


def finish_message(client, stream, pending, *, sessions_dir=None):
    try:
        frame = client.wait(pending.command_id)
    except UsageQuotaError as exc:
        save_reply(stream, session_id=pending.identity.session_id, command_id=pending.command_id,
                   sent_text=pending.text, frame=exc.frame, messages=[])
        raise
    if usage_or_quota(frame):
        save_reply(stream, session_id=pending.identity.session_id, command_id=pending.command_id,
                   sent_text=pending.text, frame=frame, messages=[])
        raise UsageQuotaError(frame)
    data = object_data(client.query("get_messages", activeSessionId=pending.identity.active_session_id))
    messages = array_field(data, "messages")
    saved = save_reply(stream, session_id=pending.identity.session_id, command_id=pending.command_id,
                       sent_text=pending.text, frame=frame, messages=messages)
    result = {"sending_status": "Prime replied", "frame": frame, "entry": saved["entry"], "pending": pending}
    if pending.mode in {"human", "automatic"} and frame["success"]:
        result["compaction"] = check_compaction(client, stream, pending.identity, sessions_dir=sessions_dir)
    return result


def stop_session(client, stream, identity, *, sender=None, command_id=None):
    from dataclasses import replace
    from datetime import datetime, timezone
    from engine import state
    from engine.project import stream_lock
    command = command_id or str(uuid.uuid4())
    storage_error = None
    try:
        with stream_lock(Path(stream)):
            current = state.check_state(Path(stream))
            state.append_log(Path(stream), subject="Operator stop", body={"text": None,
                "command": {"type": "abort", "session": identity.session_id}, "sender": sender,
                "received_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")},
                command_id=command, session_id=identity.session_id, purpose="stop", locked=True)
            current = state.check_state(Path(stream))
            if identity.session_id == coordinator_id(stream):
                stopped = replace(current.goals, status="paused")
                affected = []
            else:
                affected = [w.original_entry for w in current.goals.work
                            if any(worker["session"] == identity.session_id for worker in w.workers)]
                stopped = replace(current.goals, work=tuple(
                    replace(w, next=None, waiting_for="stopped worker " + identity.session_id)
                    if w.original_entry in affected else w for w in current.goals.work))
            if stopped != current.goals:
                state.update_state(Path(stream), expect=current.sha256, goals=stopped, rules=None,
                    entry={"subject": "Paused by operator stop", "body": {"command": "abort"}, "original_entries": affected}, locked=True)
    except (StreamsError, OSError) as exc:
        storage_error = str(exc)
    try:
        sent = client.write("abort", command_id=command, activeSessionId=identity.active_session_id)
        frame = client.wait(sent)
        observed = client.query("get_connection_state", activeSessionId=identity.active_session_id)
        result = {"frame": frame, "observed": observed, "termination_guaranteed": False, "storage_error": storage_error}
    except (StreamsError, OSError) as exc:
        result = {"result": "unknown", "error": str(exc), "termination_guaranteed": False, "storage_error": storage_error}
    try:
        state.append_log(Path(stream), subject="Abort observation", body=result, session_id=identity.session_id,
                         command_id=command, purpose="abort-result")
    except (StreamsError, OSError):
        result["unsaved"] = True
    return result


def native_idle(client, identity):
    _, connection = resolve_session(client, identity.session_id, identity.active_session_id)
    summary = object_data(client.query("get_state", activeSessionId=identity.active_session_id))
    queue = object_data(client.query("get_queue", activeSessionId=identity.active_session_id))
    idle = all(connection.get(key) is False for key in ("isStreaming", "isCompacting", "isBashRunning"))
    idle = idle and summary.get("hasRunningSubagents") is False and queue.get("steering") == [] and queue.get("followUp") == []
    idle = idle and not connection.get("activeToolNames")
    return bool(idle), connection


def branch_entries(tree):
    nodes = array_field(object_data(tree), "flatNodes")
    entries = {}
    for node in nodes:
        entry = object_data(object_data(node).get("entry"))
        if not isinstance(entry.get("id"), str) or entry["id"] in entries:
            raise StreamsError("invalid native tree entry identity")
        entries[entry["id"]] = entry
    branch, seen, leaf = [], set(), tree.get("leafId")
    while leaf is not None:
        if leaf in seen or leaf not in entries:
            raise StreamsError("native branch is missing or cyclic")
        seen.add(leaf)
        entry = entries[leaf]
        branch.append(entry)
        leaf = entry.get("parentId")
    return branch


def read_compaction_entry(tree, before_ids, native_result, session_file, sessions_dir, identity):
    from engine.state import sha256
    summary = object_data(native_result).get("summary")
    if not isinstance(summary, str) or not summary:
        raise StreamsError("compact reply has no actual summary")
    candidates = [e for e in branch_entries(tree) if e.get("type") == "compaction" and e["id"] not in before_ids]
    if len(candidates) != 1 or candidates[0].get("summary") != summary:
        raise StreamsError("missing or ambiguous new matching current-branch compaction")
    path, root = Path(session_file), Path(sessions_dir)
    if not path.is_absolute() or not root.is_absolute() or not path.is_relative_to(root) or path == root:
        raise StreamsError("native transcript is outside the owned session directory")
    if any(item.is_symlink() for item in (path, *path.parents, root, *root.parents)):
        raise StreamsError("native transcript symlink escape")
    try:
        text = path.read_bytes().decode("utf-8")
        rows = [json.loads(line, parse_constant=reject_json_constant) for line in text.split("\n") if line]
    except (OSError, ValueError, UnicodeError) as exc:
        raise StreamsError(f"native compaction disk readback failed: {exc}") from exc
    if not rows or rows[0].get("type") != "session" or rows[0].get("id") != identity.session_id:
        raise StreamsError("native transcript durable identity differs")
    matches = [row for row in rows[1:] if row.get("id") == candidates[0]["id"]]
    if len(matches) != 1 or any(matches[0].get(key) != candidates[0].get(key) for key in ("id", "type", "summary")):
        raise StreamsError("native compaction is not persisted with matching ID/type/summary")
    return {"id": matches[0]["id"], "type": matches[0]["type"], "summary": summary, "path": str(path), "sha256": sha256(text)}


def dcr_entries(entries, session_id):
    return sorted((e for e in entries.values() if "threshold_percent" in e.body and e.session == session_id), key=lambda e: e.timestamp)


def check_compaction(client, stream, identity, *, sessions_dir=None):
    settings = validate_stream_settings(stream)
    current, entries = stream_entries(stream)
    notes = dcr_entries(entries, identity.session_id)
    if notes and notes[-1].body["result"] in {"requested", "saving", "paused", "compacting", "unknown", "verified"}:
        return {"status": "held", "reason": "pending or unknown DCR"}
    if unresolved(entries):
        return {"status": "held", "reason": "unknown prior send"}
    replies = [e for e in entries.values() if "sent_text_sha256" in e.body]
    if replies and max(replies, key=lambda e: e.timestamp).body["success"] is not True:
        return {"status": "held", "reason": "native failure"}
    _, connection = resolve_session(client, identity.session_id, identity.active_session_id)
    usage = connection.get("contextUsage")
    percent = usage.get("percent") if isinstance(usage, dict) else None
    if isinstance(percent, bool) or not isinstance(percent, (int, float)) or not math.isfinite(percent) or not 0 <= percent <= 100:
        return {"status": "unknown", "reason": "native percentage is unknown"}
    threshold = settings["compaction"]["thresholdPercent"]
    if percent <= threshold:
        return {"status": "not-due", "percent": percent}
    if sessions_dir is None:
        raise StreamsError("compaction is due but owned native session storage is unwired")
    return run_compaction(client, stream, identity, trigger="percentage", percent=percent,
                          sessions_dir=sessions_dir, threshold_percent=threshold)


def _dcr_current(stream, identity, baseline):
    from engine import state
    current = state.check_state(stream)
    if coordinator_id(stream) != identity.session_id or current.goals.status == "paused":
        raise StreamsError("stop or target change supersedes DCR")
    if current.rules_text != baseline.rules_text or (current.goals.north_star, current.goals.original_entry, current.goals.objective, current.goals.status) != (baseline.goals.north_star, baseline.goals.original_entry, baseline.goals.objective, baseline.goals.status):
        raise StreamsError("unrelated current instruction change supersedes DCR")
    old = {w.original_entry: w for w in baseline.goals.work}
    new = {w.original_entry: w for w in current.goals.work}
    if any(new.get(ref) != item for ref, item in old.items()):
        raise StreamsError("current work changed during DCR")
    if any(worker["worktree"] == str(stream) for work in current.goals.work for worker in work.workers):
        raise StreamsError("known worker mutates the stream worktree")
    return current


def run_compaction(client, stream, identity, *, trigger, sessions_dir, threshold_percent=None, percent=None, command_id=None):
    from engine import state
    from engine.project import stream_lock
    from engine.prompts import render
    stream = Path(stream)
    threshold = validate_stream_settings(stream)["compaction"]["thresholdPercent"]
    if threshold_percent is not None and threshold_percent != threshold or trigger not in {"explicit", "percentage"}:
        raise StreamsError("invalid DCR trigger or threshold")
    command = command_id or str(uuid.uuid4())
    pause = None
    with stream_lock(stream):
        baseline, entries = stream_entries(stream)
        previous = dcr_entries(entries, identity.session_id)
        if previous and previous[-1].body["result"] in {"requested", "saving", "paused", "compacting", "unknown", "verified"}:
            return {"status": "held", "reason": "pending or unknown DCR"}
        repeated = [e for e in previous if e.command == command]
        if repeated:
            return {"status": repeated[-1].body["result"], "command": command}
        if previous and previous[-1].body["result"] == "deferred" and previous[-1].body["dump_entry"] is None:
            command = previous[-1].command
        if unresolved(entries) or baseline.goals.status == "paused":
            return {"status": "held", "reason": "stopped or unknown native send"}
        note = {"command": command, "trigger": trigger, "percent": percent, "threshold_percent": threshold,
                "before_entry": None, "dump_entry": None, "compaction_entry": None, "next_command": None,
                "result": "requested", "error": None}
        retained = [e for e in previous if e.command == command and e.file.endswith("-dcr-request.md")]
        if retained:
            note = dict(retained[0].body)
        def record(purpose, result, error=None):
            note["result"], note["error"] = result, error
            return state.append_log(stream, subject="DCR " + result, body=dict(note), session_id=identity.session_id,
                                    command_id=command, purpose="dcr-" + purpose, locked=True)
        record("request", "requested")
    try:
        idle, connection = native_idle(client, identity)
        if not idle:
            with stream_lock(stream):
                record("deferred", "deferred")
            return {"status": "deferred", "command": command}
        before = set(entries)
        dump = send_stream_message(client, stream, identity, body=render("save"), mode="save", original_entries=[w.original_entry for w in baseline.goals.work], sessions_dir=sessions_dir)
        if dump.get("frame", {}).get("success") is not True:
            raise StreamsError("save-STATE native result failed or unknown")
        baseline, after = stream_entries(stream)
        checked_saves = [e for ref, e in after.items() if ref not in before and e.file.endswith("-update.md")]
        if not checked_saves:
            raise StreamsError("save-STATE turn did not perform a checked update")
        if baseline.goals.status == "paused":
            raise StreamsError("operator stop supersedes DCR")
        idle, connection = native_idle(client, identity)
        note["before_entry"] = connection.get("leafId")
        note["dump_entry"] = connection.get("leafId")
        with stream_lock(stream):
            record("saved", "saving")
        paused = object_data(client.query("acquire_session_input_pause", activeSessionId=identity.active_session_id, leaseKey=command))
        pause = paused.get("pauseId")
        if not isinstance(pause, str) or not pause:
            raise StreamsError("native input pause has no ID")
        note["pause_id"] = pause
        with stream_lock(stream):
            record("paused", "paused")
        idle, connection = native_idle(client, identity)
        if not idle:
            with stream_lock(stream):
                record("deferred-after-save", "deferred")
            return {"status": "deferred", "command": command}
        tree = client.query("get_session_tree", activeSessionId=identity.active_session_id)
        before_ids = {e["id"] for e in branch_entries(tree) if e.get("type") == "compaction"}
        with stream_lock(stream):
            _dcr_current(stream, identity, baseline)
            record("before-compact", "compacting")
            compact_id = client.write("compact", activeSessionId=identity.active_session_id, customInstructions=render("compact"))
        compact = client.wait(compact_id)
        if usage_or_quota(compact):
            raise UsageQuotaError(compact)
        if compact["success"] is not True:
            raise StreamsError("native compact failed: " + str(compact.get("error")))
        _, connection = resolve_session(client, identity.session_id, identity.active_session_id)
        tree = client.query("get_session_tree", activeSessionId=identity.active_session_id)
        readback = read_compaction_entry(tree, before_ids, compact.get("data"), connection.get("sessionFile", ""), sessions_dir, identity)
        note["compaction_entry"] = readback["id"]
        with stream_lock(stream):
            current = _dcr_current(stream, identity, baseline)
            note["readback"] = readback
            note["native_result"] = compact
            record("verified", "verified")
            _, after = stream_entries(stream)
            sent = {e.command for e in after.values() if "goals_rules_sha256" in e.body}
            incoming = sorted((e for e in after.values() if state._original(e) and e.command not in sent), key=lambda e: e.timestamp)
            if incoming:
                source = incoming[0]
                next_body, next_id, mode, refs = source.body["text"], source.command, "input", [source.file]
            elif eligible(current, after):
                next_body, next_id, mode, refs = render("resume", compaction_entry_id=readback["id"], session_id=identity.session_id), str(uuid.uuid4()), "resume", [w.original_entry for w in current.goals.work]
            else:
                next_body = None
        pending = None
        if next_body is not None:
            pending = send_stream_message(client, stream, identity, body=next_body, command_id=next_id, mode=mode,
                         expected=current.goals_rules_sha256, original_entries=refs, lane="followUp", wait_result=False, sessions_dir=sessions_dir)
            note["next_command"] = pending.command_id
        client.query("release_session_input_pause", activeSessionId=identity.active_session_id, pauseId=pause)
        pause = None
        result = finish_message(client, stream, pending, sessions_dir=sessions_dir) if pending else None
        if result and result.get("frame", {}).get("success") is not True:
            raise StreamsError("post-compaction input result failed")
        with stream_lock(stream):
            record("complete", "complete")
        return {"status": "verified", "command": command, "readback": readback, "dump": dump, "continuation": result}
    except (StreamsError, OSError) as exc:
        if isinstance(exc, UsageQuotaError):
            raise
        if isinstance(exc, CliError) and usage_or_quota({"success": False, "error": str(exc.output)}):
            raise UsageQuotaError({"success": False, "error": str(exc)}) from exc
        with stream_lock(stream):
            record("unknown", "unknown", str(exc))
        return {"status": "unknown", "command": command, "error": str(exc)}
    finally:
        if pause:
            client.query("release_session_input_pause", activeSessionId=identity.active_session_id, pauseId=pause)

from __future__ import annotations

import hashlib
import json
import os
import stat
import uuid
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from engine import StreamsError, artifacts, delivery, piweb
from engine.project import Project, _write, commit_repo, git, require_stream
from engine.threads import KICKOFF, Status, _canonical_stream, _has_ratified_authority, _save_start, _start_record, _validated_handover, dump_threads, ensure_coordinator, load_threads, resolve_coordinator, save_threads, transition


@contextmanager
def _regular_reader(path: Path):
    descriptor = None
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise StreamsError(f"checkpoint source must be a regular owned file: {path}")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StreamsError(f"checkpoint source must be a regular owned file: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            yield handle
    except OSError as exc:
        raise StreamsError(f"checkpoint source is unavailable: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


def _digest(path: Path) -> str:
    with _regular_reader(path) as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def _save(stream: Path, key: str, value: dict) -> None:
    data = artifacts._read_tick_data(stream)
    data[key] = value
    artifacts._save_tick_data(stream, data)


def _workers(stream: Path) -> list[dict]:
    result = []
    for row in load_threads(stream / "threads.tsv"):
        if row.role == "coordinator" or row.status is Status.archived:
            continue
        path = Path(row.worktree)
        if path.is_symlink() or not path.is_dir():
            raise StreamsError(f"unfinished worker {row.session} has no stable owned worktree reference")
        pointer = path / ".stream"
        if pointer.is_symlink() or not pointer.is_file() or pointer.read_text().strip() != str(stream):
            raise StreamsError(f"unfinished worker {row.session} has an invalid stream ownership reference")
        result.append({"session": row.session, "role": row.role, "worktree": row.worktree, "repo": row.repo, "branch": row.branch})
    return result


def _validate_checkpoint_inputs(stream: Path, checkpoint: dict, project: Project, *, retired: bool = False, owner: str | None = None) -> None:
    if checkpoint.get("state") != _digest(stream / "STATE.md") or checkpoint.get("references") != _workers(stream):
        raise StreamsError("checkpoint STATE or unfinished-work references changed")
    if delivery._evidence(stream, checkpoint["handover"])["sha256"] != checkpoint.get("handover_sha256"):
        raise StreamsError("checkpoint handover changed")
    if any(item["state"] not in ("applied", "blocked") for item in delivery.receipts(stream)):
        raise StreamsError("checkpoint has unresolved delivery/application state")
    original = checkpoint.get("threads_source")
    if not isinstance(original, str) or hashlib.sha256(original.encode()).hexdigest() != checkpoint.get("threads"):
        raise StreamsError("checkpoint registry snapshot is unavailable or malformed")
    current = (stream / "threads.tsv").read_bytes().decode("utf-8")
    start = _start_record(stream)
    if retired and start is not None and start.operation == owner and start.phase == "accepted":
        retained = []
        for line in current.splitlines(keepends=True):
            cells = line.rstrip("\r\n").split("\t")
            if cells and cells[0] == start.session:
                if len(cells) != 10 or cells[1:9] != ["coordinator", "", str(stream), "", "", project.coordinator.model, project.coordinator.thinking, "active"]:
                    raise StreamsError("checkpoint successor registry transition changed")
                continue
            retained.append(line)
        current = "".join(retained)
    allowed = [original]
    if retired:
        after = checkpoint.get("threads_after_archive")
        if not isinstance(after, str):
            raise StreamsError("checkpoint archived registry transition is unavailable")
        allowed.append(after)
    if current not in allowed:
        raise StreamsError("checkpoint registry or unfinished-work snapshot changed")
    if git(stream, "diff", "--cached", "--name-only").strip() or git(stream, "ls-files", "--others", "--exclude-standard").strip():
        raise StreamsError("checkpoint requires a clean tree without foreign staged/untracked input")
    changed_paths = set(git(stream, "diff", checkpoint["commit"], "--name-only").splitlines())
    permitted = {"threads.tsv"} if retired else set()
    if changed_paths - permitted or (not retired and git(stream, "rev-parse", "HEAD").strip() != checkpoint.get("commit")):
        raise StreamsError("checkpoint stream tree changed beyond the recorded registry transition")


def prepare_checkpoint_locked(stream: Path, session: str) -> dict:
    if not _canonical_stream(stream):
        raise StreamsError("canonical STATE and explicit legacy migration are required before a coordinator checkpoint")
    resolved = resolve_coordinator(stream)
    if resolved is None or resolved.row.session != session:
        raise StreamsError("checkpoint must name the designated exact coordinator")
    handover = _validated_handover(stream, resolved.row)
    references = _workers(stream)
    commit_repo(stream, f"pi-streams checkpoint {stream.name}", paths=(handover,))
    if git(stream, "status", "--porcelain").strip():
        raise StreamsError("checkpoint requires a clean stream tree and stable owned references")
    control, _allowed = piweb.automatic_admission(resolved.native.status, session, str(stream), "wake")
    checkpoint = {
        "id": uuid.uuid4().hex, "session": session, "cwd": str(stream),
        "state": _digest(stream / "STATE.md"), "threads": _digest(stream / "threads.tsv"),
        "threads_source": (stream / "threads.tsv").read_bytes().decode("utf-8"),
        "threads_after_archive": dump_threads([replace(row, status=Status.archived) if row.session == session else row for row in load_threads(stream / "threads.tsv")]),
        "handover": handover, "handover_sha256": delivery._evidence(stream, handover)["sha256"],
        "references": references, "generation": control["generation"],
        "commit": git(stream, "rev-parse", "HEAD").strip(),
    }
    _save(stream, "coordinator_checkpoint", checkpoint)
    return {"checkpoint": checkpoint["id"], "session": session, "acknowledge": f"Rotation checkpoint ready: {checkpoint['id']}"}


def _native_ack(path: Path, session: str, checkpoint: str) -> dict:
    last = None
    raw_last = b""
    try:
        with _regular_reader(path) as handle:
            header = json.loads(handle.readline())
            if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != session:
                raise StreamsError("checkpoint native evidence has the wrong session identity")
            for raw in handle:
                if not raw.strip():
                    continue
                entry = json.loads(raw)
                if not isinstance(entry, dict):
                    raise StreamsError("checkpoint native evidence is malformed")
                if entry.get("id") is not None:
                    last, raw_last = entry, raw
    except (OSError, ValueError) as exc:
        raise StreamsError(f"checkpoint native evidence is unavailable or incomplete: {exc}") from exc
    message = last.get("message") if last is not None else None
    if not isinstance(message, dict) or message.get("role") != "assistant" or message.get("stopReason") != "stop":
        raise StreamsError("checkpoint requires the coordinator's complete final acknowledgement")
    content = message.get("content")
    texts = [content] if isinstance(content, str) else [item.get("text", "") for item in content if isinstance(item, dict) and item.get("type") == "text"] if isinstance(content, list) else []
    if f"Rotation checkpoint ready: {checkpoint}" not in "\n".join(texts):
        raise StreamsError("checkpoint was not acknowledged by the current coordinator turn")
    return {"entry": last["id"], "sha256": hashlib.sha256(raw_last).hexdigest(), "raw": raw_last}


def _idle(resolved) -> None:
    status = resolved.native.status
    if any(status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning")) or status.get("pendingMessageCount", 0) != 0 or status.get("queuedMessages"):
        raise StreamsError("coordinator is busy or has queued input; explicit rotation never aborts it")
    if status.get("pendingAsk") is not None or status.get("pendingDialogs"):
        raise StreamsError("coordinator has unresolved human input; refusing rotation")
    safety = status.get("rotationSafety")
    if not isinstance(safety, dict) or safety.get("callbacksKnown") is not True:
        raise StreamsError("native callback ownership is unavailable; checkpoint rotation capability required")
    children = safety.get("nativeChildCallbacks")
    if not isinstance(children, list) or children:
        raise StreamsError("native child callback ownership still needs the original coordinator")
    if resolved.native.info.get("childSessionsElsewhere", 0):
        raise StreamsError("native child references still need the original coordinator")


def _pickup(stream: Path) -> str:
    state = artifacts._read_stream_state_locked(stream)
    if not _has_ratified_authority(state):
        return KICKOFF
    return (
        f"You are the new coordinator for stream {stream.name}. "
        f"Read {stream}/AGENTS.md and {stream}/STATE.md before acting. "
        "Use Goals' current objective, falling back to North Star. Current Goals and Rules take precedence. "
        "Open history/, context/, checks/, and handover/ only on demand. "
        f"Goal at pickup:\n{artifacts.resolve_current_goal(state)}"
    )


def rotate_locked(index: Path, project: Project, stream_id: str) -> str:
    stream = require_stream(index, project.info.name, stream_id)
    data = artifacts._read_tick_data(stream)
    checkpoint = data.get("coordinator_checkpoint")
    operation = data.get("coordinator_rotation")
    rows = load_threads(stream / "threads.tsv")
    if not any(row.role == "coordinator" for row in rows):
        raise StreamsError(f"stream {stream_id} has no coordinator; run pi-streams new {stream_id}")
    if not isinstance(checkpoint, dict):
        raise StreamsError("current coordinator checkpoint is required before explicit rotation")
    if isinstance(operation, dict) and operation.get("checkpoint") == checkpoint.get("id") and operation.get("phase") == "complete":
        resolved = resolve_coordinator(stream, rows)
        if resolved is None or resolved.row.session != operation.get("target"):
            raise StreamsError("completed rotation does not match the designated successor")
        start = _start_record(stream)
        if start is not None:
            if start.session != operation["target"] or start.phase != "accepted" or start.operation != operation["owner"]:
                raise StreamsError("completed rotation has a conflicting saved opening")
            _save_start(stream, None)
        return operation["target"]
    recovering = isinstance(operation, dict) and operation.get("checkpoint") == checkpoint.get("id")
    if not recovering:
        resolved = resolve_coordinator(stream, rows)
        if resolved is None:
            raise StreamsError("no designated coordinator for a new explicit replacement")
        _idle(resolved)
        if checkpoint.get("session") != resolved.row.session or checkpoint.get("cwd") != str(stream):
            raise StreamsError("checkpoint does not belong to the designated coordinator")
        _validate_checkpoint_inputs(stream, checkpoint, project)
        native_path = resolved.native.info.get("path")
        if not isinstance(native_path, str) or not Path(native_path).is_absolute():
            raise StreamsError("checkpoint native evidence path is unavailable")
        ack = _native_ack(Path(native_path), resolved.row.session, checkpoint["id"])
        if resolved.native.status["rotationSafety"].get("entryId") != ack["entry"]:
            raise StreamsError("checkpoint is not the current logical native entry")
        control, _allowed = piweb.automatic_admission(resolved.native.status, resolved.row.session, str(stream), "wake")
        if control["generation"] != checkpoint.get("generation"):
            raise StreamsError("checkpoint was superseded by newer input or stop")
        cache = stream / "log/rotation-evidence" / f"{checkpoint['id']}.jsonl"
        if cache.is_symlink() or any(parent.is_symlink() for parent in (cache.parent, cache.parent.parent)):
            raise StreamsError("checkpoint evidence cache must stay in the owned stream")
        if cache.exists():
            with _regular_reader(cache) as handle:
                if handle.read() != ack["raw"]:
                    raise StreamsError("checkpoint evidence cache collision")
        _write(cache, ack["raw"].decode("utf-8"))
        if cache.read_bytes() != ack["raw"]:
            raise StreamsError("checkpoint evidence cache did not retain exact native bytes")
        operation = {"checkpoint": checkpoint["id"], "source": resolved.row.session, "owner": f"rotation:{checkpoint['id']}", "phase": "archiving", "state": checkpoint["state"], "prompt": _pickup(stream), "entry": ack["entry"], "sha256": ack["sha256"], "generation": control["generation"]}
        _save(stream, "coordinator_rotation", operation)
    if not isinstance(operation, dict):
        raise StreamsError("rotation operation is malformed")
    if operation.get("state") != _digest(stream / "STATE.md"):
        raise StreamsError("checkpoint STATE changed during replacement; explicit reconciliation required")
    if operation.get("phase") == "archiving":
        listing = piweb.list_sessions(str(stream))
        matches = [item for item in listing if item.get("id") == operation["source"]]
        if len(matches) != 1 or Path(str(matches[0].get("cwd", ""))).resolve() != stream:
            raise StreamsError("rotation original identity is unavailable")
        retired = matches[0].get("archived") is True
        _validate_checkpoint_inputs(stream, checkpoint, project, retired=retired, owner=operation["owner"])
        if not retired:
            resolved = resolve_coordinator(stream, rows)
            if resolved is None or resolved.row.session != operation["source"]:
                raise StreamsError("rotation original designation changed")
            _idle(resolved)
            piweb.archive(operation["source"], expected_idle={"sessionId": operation["source"], "cwd": str(stream), "entryId": operation["entry"], "generation": operation["generation"]})
        for row in rows:
            if row.session == operation["source"] and row.status is Status.active:
                transition(row, Status.archived)
        save_threads(stream / "threads.tsv", rows)
        operation["phase"] = "archived"
        _save(stream, "coordinator_rotation", operation)
    if operation.get("phase") != "archived":
        raise StreamsError("unknown rotation operation phase")
    _validate_checkpoint_inputs(stream, checkpoint, project, retired=True, owner=operation["owner"])
    target = ensure_coordinator(project, stream, opening_prompt=operation["prompt"], operation=operation["owner"])
    start = _start_record(stream)
    if start is None or start.session != target or start.phase != "accepted" or start.operation != operation["owner"]:
        raise StreamsError("rotation successor has no exact accepted opening identity")
    operation.update({"phase": "complete", "target": target})
    data = artifacts._read_tick_data(stream)
    data["coordinator_rotation"] = operation
    data["rotating"] = False
    artifacts._save_tick_data(stream, data)
    _save_start(stream, None)
    return target

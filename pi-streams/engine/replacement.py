from __future__ import annotations

import base64
import hashlib
import json
import os
import stat
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field, replace
from pathlib import Path

from engine import StreamsError, artifacts, clock, delivery, failure, failure_recovery, piweb, sessionlog
from engine.project import Project, _sync_directory, _write, commit_repo, git, require_stream
from engine.threads import Coordinator, Status, _canonical_stream, _native_session, _save_start, _start_record, _validated_handover, designated_coordinator, dump_threads, ensure_coordinator, load_threads, resolve_coordinator, save_threads, transition


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


def prepare_checkpoint_locked(stream: Path, session: str, *, source: dict | None = None) -> dict:
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
        **({"source": source} if source is not None else {}),
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
    if not isinstance(safety, dict) or safety.get("callbackInventory") != "native-and-extension-v1":
        raise StreamsError("complete native and extension callback inventory is unavailable; checkpoint rotation capability required")
    if safety.get("callbacksKnown") is not True:
        reasons = safety.get("unprovenCallbacks")
        detail = "; ".join(item for item in reasons if isinstance(item, str)) if isinstance(reasons, list) else "unproved callback mechanism"
        raise StreamsError(f"native callback inventory has unknown ownership: {detail}")
    children = safety.get("nativeChildCallbacks")
    if not isinstance(children, list) or children:
        raise StreamsError("native child callback ownership still needs the original coordinator")
    if resolved.native.info.get("childSessionsElsewhere", 0):
        raise StreamsError("native child references still need the original coordinator")


def _pickup(stream: Path) -> str:
    state = artifacts._read_stream_state_locked(stream)
    return (
        f"You are the new coordinator for stream {stream.name}. "
        f"Read {stream}/AGENTS.md and {stream}/STATE.md before acting. "
        "Use Goals' current objective, falling back to North Star. Current Goals and Rules take precedence. "
        "Open history/, context/, checks/, and handover/ only on demand. "
        f"Goal at pickup:\n{artifacts.resolve_current_goal(state)}"
    )


def _healthy_source(resolved) -> dict:
    _idle(resolved)
    sid, cwd, status = resolved.row.session, resolved.row.worktree, resolved.native.status
    _token, allowed = piweb.automatic_admission(status, sid, cwd, "wake")
    if not allowed:
        raise StreamsError("Newer stop or disabled admission preserves this coordinator")
    path = Path(resolved.native.info["path"])
    leaf = status["rotationSafety"]["entryId"]
    branch = sessionlog.branch_records(path, sid, cwd, leaf)
    if sessionlog.failure_observation(path, sid, cwd, leaf) is not None:
        raise StreamsError("Failed coordinator must use owned last-good recovery")
    terminal = next(((entry, raw) for entry, raw in reversed(branch) if entry.get("type") == "message"), None)
    if terminal is None:
        raise StreamsError("No complete native good checkpoint is available for rotation")
    entry, raw = terminal
    proof = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest()}
    sessionlog.verify_good_checkpoint(path, sid, cwd, leaf, proof, "")
    at = next(index for index, (item, _) in enumerate(branch) if item["id"] == entry["id"])
    if any(item.get("customType") != "pi-web.stream-failure" or item.get("data") != status.get("failureBoundary") or item["data"].get("state") != "watching" for item, _ in branch[at+1:]):
        raise StreamsError("Newer native input superseded the rotation good checkpoint")
    return {"entryId": leaf, "sha256": hashlib.sha256(branch[-1][1]).hexdigest(), "checkpoint": proof}


def rotate_locked(index: Path, project: Project, stream_id: str) -> str:
    stream = require_stream(index, project.info.name, stream_id)
    artifacts._read_stream_state_locked(stream)
    data = artifacts._read_tick_data(stream)
    checkpoint = data.get("coordinator_checkpoint")
    operation = data.get("coordinator_rotation")
    rows = load_threads(stream / "threads.tsv")
    if not any(row.role == "coordinator" for row in rows):
        raise StreamsError(f"stream {stream_id} has no coordinator; run pi-streams new {stream_id}")
    if not isinstance(checkpoint, dict):
        for row in rows:
            if row.role != "coordinator":
                continue
            episode = failure.load(stream, row.session)
            operation = failure_recovery.load(stream, row.session)
            if episode is not None and episode.state == "parked" and (operation is None or operation.phase != "complete"):
                result = failure_recovery.advance_locked(stream, episode.session, episode.id, clock.stamp(clock.now()), index=index, project=project)
                if not result.get("fork"):
                    raise StreamsError("Last-good rotation has no verified returned fork yet")
                return result["fork"]
        operation = data.get("coordinator_rotation")
        resolved = resolve_coordinator(stream, rows)
        if resolved is None:
            raise StreamsError("No designated coordinator or saved rotation owns this stream")
        source = _healthy_source(resolved)
        prepare_checkpoint_locked(stream, resolved.row.session, source=source)
        data = artifacts._read_tick_data(stream)
        checkpoint = data["coordinator_checkpoint"]
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
        piweb.require_settings(resolved.native.status, resolved.row.model, resolved.row.thinking)
        if checkpoint.get("session") != resolved.row.session or checkpoint.get("cwd") != str(stream):
            raise StreamsError("checkpoint does not belong to the designated coordinator")
        _validate_checkpoint_inputs(stream, checkpoint, project)
        native_path = resolved.native.info.get("path")
        if not isinstance(native_path, str) or not Path(native_path).is_absolute():
            raise StreamsError("checkpoint native evidence path is unavailable")
        source = checkpoint.get("source")
        if source is None:
            ack = _native_ack(Path(native_path), resolved.row.session, checkpoint["id"])
        else:
            if _healthy_source(resolved) != source:
                raise StreamsError("Rotation good checkpoint was superseded")
            raw = sessionlog.read_record(Path(native_path), resolved.row.session, source["entryId"], source["sha256"]).raw
            ack = {"entry": source["entryId"], "sha256": source["sha256"], "raw": raw}
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
        operation = {"checkpoint": checkpoint["id"], "source": resolved.row.session, "owner": f"rotation:{checkpoint['id']}", "phase": "archiving", "state": checkpoint["state"], "prompt": _pickup(stream) + f"\nRead the retained coordinator handover {stream / checkpoint['handover']} before task effects.", "entry": ack["entry"], "sha256": ack["sha256"], "generation": control["generation"], "model": resolved.row.model, "thinking": resolved.row.thinking}
        _save(stream, "coordinator_rotation", operation)
    if not isinstance(operation, dict):
        raise StreamsError("rotation operation is malformed")
    source = next((row for row in rows if row.session == operation.get("source") and row.role == "coordinator"), None)
    if source is None or operation.get("model", source.model) != source.model or operation.get("thinking", source.thinking) != source.thinking:
        raise StreamsError("Rotation source model/thinking changed beyond its frozen registry intent")
    project = replace(project, coordinator=replace(project.coordinator, model=source.model, thinking=source.thinking))
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


@dataclass
class ReplacementIntent:
    id: str
    source: str
    target: str
    mode: str
    registry: str
    state: str
    references: list[dict]
    records: dict
    original: dict
    successor: dict = field(default_factory=dict)
    outcome: dict = field(default_factory=dict)
    phase: str = "prepared"
    published: str = ""
    archive: dict = field(default_factory=dict)
    handoff: dict = field(default_factory=dict)
    registry_sha256: str = ""
    load: dict = field(default_factory=dict)
    version: int = 1


def replacement_intent(stream: Path) -> ReplacementIntent | None:
    raw = artifacts._read_tick_data(stream).get("coordinator_replacement")
    if raw is None:
        return None
    try:
        intent = ReplacementIntent(**raw)
        if (type(intent.version) is not int or intent.version != 1
            or not all(isinstance(value, str) for value in (intent.id, intent.source, intent.target, intent.registry, intent.state, intent.published))
            or not intent.id or not intent.source or intent.mode not in {"adopt", "capacity"}
            or not isinstance(intent.original, dict) or not isinstance(intent.successor, dict) or not isinstance(intent.archive, dict)
            or not isinstance(intent.load, dict) or not isinstance(intent.references, list) or not isinstance(intent.records, dict) or not isinstance(intent.outcome, dict) or not isinstance(intent.handoff, dict)
            or intent.registry_sha256 != hashlib.sha256(intent.registry.encode()).hexdigest()
            or intent.original.get("sessionId") != intent.source or not isinstance(intent.original.get("cwd"), str) or not Path(intent.original["cwd"]).is_absolute()
            or type(intent.original.get("allowed")) is not bool
            or not all(isinstance(intent.original.get(key), str) and intent.original[key] for key in ("generation", "entryId", "path", "sha256", "leafSha256", "model", "thinking"))
            or intent.phase not in {"prepared", "spawning", "created", "archiving", "archived", "complete"}
            or (intent.mode == "adopt" or intent.phase == "complete") and not intent.target):
            raise ValueError("invalid replacement identity or phase")
        return intent
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid saved coordinator replacement: {exc}") from exc


def _save_replacement(stream: Path, intent: ReplacementIntent) -> None:
    _save(stream, "coordinator_replacement", asdict(intent))


def _replacement_records(stream: Path) -> dict:
    data = artifacts._read_tick_data(stream)
    return {key: data[key] for key in ("drive", "deliveries", "tick_delivery", "dcr_operations", "dcr_dumps", "dcr_historical_recoveries", "failures", "failure_recoveries", "session_start", "state_log") if key in data}


def _replacement_inputs(stream: Path, sid: str) -> None:
    if _start_record(stream) is not None:
        raise StreamsError("saved opening ownership must settle before replacement")
    rotation = artifacts._read_tick_data(stream).get("coordinator_rotation")
    if isinstance(rotation, dict) and rotation.get("phase") != "complete":
        raise StreamsError("another coordinator rotation owns this stream")
    for receipt in delivery.receipts(stream):
        if receipt["session"] == sid and (receipt["state"] in {"sending", "uncertain"} or (receipt.get("control") or {}).get("state") in {"sending", "uncertain"}):
            raise StreamsError("unsettled old coordinator delivery must be retained before replacement")
    from engine import dcr
    op = dcr.load(stream, sid)
    fallback = op is not None and op.phase == "rotation-pending" and op.capacity is not None
    if op is not None and op.phase in {"sync-sending", "compact-sending", "resume-sending", "resuming", "compacting"}:
        raise StreamsError("unsettled old coordinator maintenance must be reconciled before replacement")
    for owner in artifacts._read_tick_data(stream).get("failure_recoveries", {}):
        recovery = failure_recovery.load(stream, owner)
        if recovery is not None and recovery.phase not in {"complete", "rotated"} and sid in {recovery.session, recovery.fork} and not (fallback and recovery.fork == sid and recovery.id == op.id and op.recovery_original == recovery.session):
            raise StreamsError("owned failure recovery must settle before replacement")


def _replacement_native(stream: Path, row, listing: list[dict]) -> tuple[Coordinator, dict]:
    resolved = Coordinator(row, _native_session(row.session, Path(row.worktree), listing))
    _idle(resolved)
    piweb.require_settings(resolved.native.status, row.model, row.thinking)
    automatic, allowed = piweb.automatic_admission(resolved.native.status, row.session, row.worktree, "wake")
    leaf = resolved.native.status["rotationSafety"].get("entryId")
    path = resolved.native.info.get("path")
    if not isinstance(leaf, str) or not leaf or not isinstance(path, str) or not Path(path).is_absolute():
        raise StreamsError("replacement requires the exact persisted old native leaf and path")
    with sessionlog.regular_reader(Path(path)) as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
    branch = sessionlog.branch_records(Path(path), row.session, row.worktree, leaf)
    return resolved, {"sessionId": row.session, "cwd": row.worktree, "entryId": leaf, "generation": automatic["generation"], "allowed": allowed, "path": path, "sha256": digest, "leafSha256": hashlib.sha256(branch[-1][1]).hexdigest(), "model": row.model, "thinking": row.thinking, "rotationSafety": resolved.native.status["rotationSafety"], "thread": asdict(row) | {"status": row.status.value}}


def _replacement_target(stream: Path, sid: str, model: str, thinking: str, listing: list[dict]) -> dict:
    native = _native_session(sid, stream, listing)
    piweb.require_settings(native.status, model, thinking)
    automatic, allowed = piweb.automatic_admission(native.status, sid, str(stream), "wake")
    return {"sessionId": sid, "cwd": str(stream), "path": native.info.get("path"), "entryId": (native.status.get("rotationSafety") or {}).get("entryId"), "generation": automatic["generation"], "allowed": allowed, "model": model, "thinking": thinking}


def _validate_replacement(stream: Path, intent: ReplacementIntent) -> None:
    if (intent.state != _digest(stream / "STATE.md") or intent.references != _workers(stream)
        or intent.records != _replacement_records(stream)):
        raise StreamsError("replacement STATE, worker references or input/drive ownership changed")
    current = (stream / "threads.tsv").read_bytes().decode("utf-8")
    if current != intent.registry and (not intent.published or current != intent.published):
        raise StreamsError("replacement registry changed beyond its frozen publication")


def _archive_proof(stream: Path, intent: ReplacementIntent, listing: list[dict]) -> dict | None:
    matches = [item for item in listing if item.get("id") == intent.source]
    if len(matches) != 1 or matches[0].get("cwd") != intent.original["cwd"]:
        raise StreamsError("replacement old exact native identity is unavailable")
    info = matches[0]
    if info.get("archived") is not True:
        return None
    path = info.get("archivePath")
    if not isinstance(path, str) or not Path(path).is_absolute() or not isinstance(info.get("archivedAt"), str):
        raise StreamsError("replacement has no positive durable archive evidence")
    with sessionlog.regular_reader(Path(path)) as handle:
        digest = hashlib.file_digest(handle, "sha256").hexdigest()
        os.fsync(handle.fileno())
    descriptor = os.open(Path(path).parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    if digest != intent.original["sha256"]:
        raise StreamsError("replacement archive does not retain the exact old native history")
    sessionlog.read_record(Path(path), intent.source, intent.original["entryId"], intent.original["leafSha256"], archived=True)
    return {"sessionId": intent.source, "cwd": intent.original["cwd"], "archivePath": path, "archivedAt": info["archivedAt"], "sha256": digest}


def _publish_handoff(path: Path, text: str) -> None:
    directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        descriptor = os.open(path.name, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=directory)
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(text.encode("utf-8"))
            handle.flush()
            os.fsync(handle.fileno())
        os.fsync(directory)
    except OSError as exc:
        raise StreamsError(f"capacity handoff publication held: {exc}") from exc
    finally:
        os.close(directory)


def _capacity_handoff(stream: Path, intent: ReplacementIntent) -> None:
    if intent.mode != "capacity":
        return
    if not intent.handoff or not (stream / intent.handoff["path"]).exists():
        op = intent.records["dcr_operations"][intent.source]
        dump = (intent.records["dcr_historical_recoveries"][intent.source]["dump"]
                if intent.outcome.get("kind") == "historical-dump-v1" else op)
        synced = base64.b64decode(dump["ready_source"], validate=True)
        if hashlib.sha256(synced).hexdigest() != dump["ready_revision"]:
            raise StreamsError("capacity handoff lost its frozen SYNC STATE")
        proof = intent.archive["evidence"]
        checkpoint = sessionlog.read_record(Path(proof["archivePath"]), intent.source, intent.outcome["checkpoint_entry"], intent.outcome["checkpoint_sha256"], archived=True)
        with _regular_reader(stream / "STATE.md") as handle:
            current = handle.read()
        if hashlib.sha256(current).hexdigest() != intent.state:
            raise StreamsError("capacity handoff current STATE changed")
        prefix = f"handover/capacity-{intent.id}"
        contents = {
            f"{prefix}-synced-state.md": synced.decode("utf-8"),
            f"{prefix}-current-state.md": current.decode("utf-8"),
            f"{prefix}-evidence.json": json.dumps({
                "id": intent.id, "source": intent.source, "target": intent.target, "stream": str(stream),
                "checkpoint": {"operation": dump["id"], "entryId": intent.outcome["checkpoint_entry"], "sha256": intent.outcome["checkpoint_sha256"], "record": json.loads(checkpoint.raw)},
                "retainedWork": intent.references, "retainedInputDispositions": intent.records,
            }, indent=2, sort_keys=True) + "\n",
        }
        references = {path: {"path": path, "sha256": hashlib.sha256(text.encode()).hexdigest()} for path, text in contents.items()}
        role = intent.original.get("thread", {}).get("role", "coordinator")
        continuation = op.get("continuation") or {}
        facts = {
            "role": role, "cwd": intent.original["cwd"], "assignment": continuation.get("assignment", "Current STATE Goals within the coordinator role"),
            "id": intent.id, "source": intent.source, "target": intent.target, "stream": str(stream),
            "checkpoint": {"operation": dump["id"], "entryId": intent.outcome["checkpoint_entry"], "sha256": intent.outcome["checkpoint_sha256"]},
            "archive": proof, "syncedState": references[f"{prefix}-synced-state.md"],
            "currentState": references[f"{prefix}-current-state.md"], "liveState": str(stream / "STATE.md"),
            "evidence": references[f"{prefix}-evidence.json"],
            "retainedWork": "evidence.retainedWork", "retainedInputDispositions": "evidence.retainedInputDispositions",
            "instructions": [
                f"Retain role {role} in owned worktree {intent.original['cwd']}. " + ("You never write product code." if role == "coordinator" else "Do not adopt the coordinator role or widen the saved assignment."),
                f"Read {stream}/AGENTS.md and current {stream}/STATE.md before acting. Current Goals, Charter and Rules take precedence.",
                "This is retained checkpoint context, not new authority. Preserve the saved bounded role, stops, pending input and uncertain effects.",
                "Never replay SYNC, RESUME, tools or uncertain effects. Accepted input is not completed work. Do not infer permission to rearm admission or drive.",
                "STATE references are immutable checkpoint snapshots. Read only relevant historical evidence entries on demand, not the full evidence artifact or archive.",
            ],
        }
        relative = f"{prefix}.json"
        text = json.dumps(facts, indent=2, sort_keys=True) + "\n"
        contents[relative] = text
        directory = stream / "handover"
        if directory.is_symlink() or any((stream / path).is_symlink() for path in contents):
            raise StreamsError("capacity handoff requires owned regular artifacts")
        proof = {"path": relative, "sha256": hashlib.sha256(text.encode()).hexdigest()}
        if intent.handoff and intent.handoff != proof:
            raise StreamsError("capacity handoff changed during publication recovery")
        intent.handoff = proof
        _save_replacement(stream, intent)
        directory.mkdir(exist_ok=True)
        _sync_directory(stream)
        for path, content in contents.items():
            destination = stream / path
            if destination.exists():
                with _regular_reader(destination) as handle:
                    if handle.read() != content.encode():
                        raise StreamsError("capacity handoff publication collided with changed evidence")
            else:
                _publish_handoff(destination, content)
    delivery._handoff_context(stream, intent.handoff)


def successor_handoff(stream: Path, session: str) -> dict | None:
    intent = replacement_intent(stream)
    if intent is None or intent.target != session:
        raw = next((item for item in artifacts._read_tick_data(stream).get("coordinator_replacement_history", []) if item.get("target") == session), None)
        intent = ReplacementIntent(**raw) if raw is not None else None
    if intent is None or intent.mode != "capacity" or intent.target != session:
        return None
    if intent.phase != "complete" or not intent.handoff:
        raise StreamsError("capacity successor has no published checkpoint handoff")
    _capacity_handoff(stream, intent)
    return dict(intent.handoff)


def _begin_replacement(stream: Path, source, target: str, *, outcome: dict | None = None) -> ReplacementIntent:
    _replacement_inputs(stream, source.session)
    listing = piweb.list_sessions(source.worktree)
    _resolved, original = _replacement_native(stream, source, listing)
    if outcome is not None and {key: original[key] for key in ("entryId", "generation", "allowed")} != outcome.get("retirement"):
        raise StreamsError("capacity source changed after its bound SYNC/receipt observation")
    if outcome is not None and outcome.get("kind") == "historical-dump-v1" and original["sha256"] != outcome.get("native_sha256"):
        raise StreamsError("historical recovery source bytes changed after dump selection")
    rows = load_threads(stream / "threads.tsv")
    if (source not in rows or source.status not in {Status.active, Status.waiting_quota}
        or source.role == "coordinator" and (designated_coordinator(rows) != source or Path(source.worktree).resolve() != stream)
        or outcome is None and source.role != "coordinator"):
        raise StreamsError("replacement old designation changed")
    if target == source.session or any(row.session == target for row in rows):
        raise StreamsError("replacement target must be the exact approved unregistered session")
    successor = _replacement_target(Path(source.worktree), target, source.model, source.thinking, listing) if target else {}
    intent = ReplacementIntent(uuid.uuid4().hex, source.session, target, "capacity" if outcome else "adopt", (stream / "threads.tsv").read_bytes().decode("utf-8"), _digest(stream / "STATE.md"), _workers(stream), _replacement_records(stream), original, successor, outcome or {})
    intent.registry_sha256 = hashlib.sha256(intent.registry.encode()).hexdigest()
    previous = replacement_intent(stream)
    if previous is not None:
        if previous.phase != "complete":
            raise StreamsError("another exact replacement intent owns this stream")
        data = artifacts._read_tick_data(stream)
        data.setdefault("coordinator_replacement_history", []).append(asdict(previous))
        artifacts._save_tick_data(stream, data)
    _save_replacement(stream, intent)
    return intent


def checkpoint_load_pending(stream: Path, session: str, *, delivery_id: str = "") -> bool:
    data = artifacts._read_tick_data(stream)
    candidates = [data.get("coordinator_replacement"), *data.get("coordinator_replacement_history", [])]
    return any(isinstance(item, dict) and item.get("mode") == "capacity" and item.get("target") == session
               and item.get("load", {}).get("state") != "observed"
               and delivery_id != f"capacity:{item['id']}:load" for item in candidates)


def _load_checkpoint(stream: Path, intent: ReplacementIntent) -> None:
    if intent.mode != "capacity" or intent.load.get("state") in {"observed", "blocked", "stopped", "superseded"}:
        return
    identity = f"capacity:{intent.id}:load"
    acknowledgement = f"Dump checkpoint loaded: {intent.id}"
    if identity not in artifacts._read_tick_data(stream).get("deliveries", {}):
        role = intent.original.get("thread", {}).get("role", "coordinator")
        goal = (f"Load the retained dump into this successor. Retain role {role} and owned worktree {intent.original['cwd']}. "
                "Read the handoff, saved synced STATE, current STATE and the exact saved assignment. Reconcile stops, newer input and uncertain effects. "
                "Do not perform task effects or replay commands during this load. Finish with the exact acknowledgement on its own line.\n" + acknowledgement)
        automatic = {"sessionId": intent.target, "cwd": intent.original["cwd"], "generation": intent.successor["generation"], "kind": "recovery"}
        delivery.prepare_control_locked(stream, identity, intent.target, goal, hashlib.sha256(goal.encode()).hexdigest(), f"dump-load:{intent.id}", 1, automatic)
        intent.load = {"delivery": identity, "state": "pending"}
        _save_replacement(stream, intent)
    record = delivery._get(stream, identity)
    if record.state == "prepared":
        delivery.send_locked(stream, identity)
    elif record.state == "transport_accepted":
        delivery.observe_control_locked(stream, identity)
    record = delivery._get(stream, identity)
    if record.state == "blocked":
        intent.load = {"delivery": identity, "state": "stopped", "detail": record.detail}
        _save_replacement(stream, intent)
        return
    if record.control is not None and record.control.state == "superseded":
        intent.load = {"delivery": identity, "state": "superseded", "detail": record.detail}
        _save_replacement(stream, intent)
        return
    if record.control is None or record.control.state != "ended":
        return
    native = _native_session(intent.target, Path(intent.original["cwd"]))
    token, allowed = piweb.automatic_admission(native.status, intent.target, intent.original["cwd"], "recovery")
    if not allowed or token != record.automatic:
        intent.load = {"delivery": identity, "state": "stopped" if not allowed else "superseded", "detail": "Newer receiving control superseded checkpoint load; no replay."}
        _save_replacement(stream, intent)
        return
    if any(native.status.get(key) for key in ("isStreaming", "isCompacting", "isBashRunning", "pendingMessageCount", "queuedMessages", "pendingAsk", "pendingDialogs")):
        return
    branch = sessionlog.branch_records(Path(native.info["path"]), intent.target, intent.original["cwd"], native.status.get("rotationSafety", {}).get("entryId"))
    prefix = delivery._handoff_context(stream, intent.handoff)
    users = []
    for at, (entry, raw) in enumerate(branch):
        message = entry.get("message", {})
        content = message.get("content", [])
        text = content if isinstance(content, str) else "\n".join(part.get("text", "") for part in content if isinstance(part, dict) and part.get("type") == "text")
        if message.get("role") == "user" and text.startswith(prefix + '<skill name="poteto-mode"') and text.endswith('</skill>\n\n' + record.control.goal):
            users.append((at, entry, raw))
    if len(users) != 1:
        return
    at, user, user_raw = users[0]
    tail = branch[at + 1:]
    assistants = [(entry, raw) for entry, raw in tail if entry.get("message", {}).get("role") == "assistant"]
    if any(entry.get("message", {}).get("role") == "user" for entry, _ in tail) or not assistants:
        return
    entry, raw = assistants[-1]
    message = entry["message"]
    if message.get("stopReason") not in {"stop", "error", "aborted", "length"}:
        return
    text = "\n".join(part.get("text", "") for part in message.get("content", []) if isinstance(part, dict) and part.get("type") == "text")
    acknowledged = (acknowledgement in text.splitlines() and message.get("stopReason") == "stop"
                    and not any(item.get("message", {}).get("stopReason") in {"error", "aborted", "length"} for item, _ in assistants))
    intent.load = {"delivery": identity, "state": "observed" if acknowledged else "blocked", "userEntryId": user["id"], "userSha256": hashlib.sha256(user_raw).hexdigest(), "assistantEntryId": entry["id"], "assistantSha256": hashlib.sha256(raw).hexdigest(), "generation": token["generation"]}
    if not acknowledged:
        intent.load["detail"] = "Terminal checkpoint load has no valid exact acknowledgement; successor task admission remains fenced. No replay."
    _save_replacement(stream, intent)


def advance_replacement_locked(stream: Path, intent: ReplacementIntent) -> str:
    if intent.phase == "complete":
        rows = load_threads(stream / "threads.tsv")
        row = next((row for row in rows if row.session == intent.target), None)
        if row is None or row.status is not Status.active or (row.role == "coordinator" and designated_coordinator(rows) != row):
            raise StreamsError("completed replacement no longer designates its exact target")
        _capacity_handoff(stream, intent)
        _load_checkpoint(stream, intent)
        return intent.target
    _validate_replacement(stream, intent)
    cwd = Path(intent.original["cwd"])
    if intent.mode == "capacity" and intent.phase == "prepared" and not intent.target:
        listing = piweb.list_sessions(str(cwd))
        known = {row.session for row in load_threads(stream / "threads.tsv")}
        if any(item.get("archived") is not True and item.get("id") not in known for item in listing):
            raise StreamsError("capacity rotation never chooses an unregistered candidate")
        intent.phase = "spawning"
        _save_replacement(stream, intent)
        intent.target = piweb.spawn(str(cwd))
        intent.phase = "created"
        _save_replacement(stream, intent)
    elif intent.phase == "spawning":
        raise StreamsError("replacement spawn identity is uncertain; no retry or candidate selection")
    if intent.mode == "capacity" and intent.phase == "created":
        status = piweb.session_status(intent.target)
        piweb.require_identity(status, intent.target)
        if status.get("messageCount") != 0 or any(status.get(key) for key in ("isStreaming", "isCompacting", "isBashRunning", "pendingMessageCount", "pendingAsk", "pendingDialogs")):
            raise StreamsError("capacity successor changed before its no-input registration")
        if any(status.get(key) != value for key, value in {
            "potetoInvocationSupport": "exact-goal-v1", "controlGoalSupport": "preserve-ask-v1",
            "recoveryControlSupport": "question-safe-v1", "conditionalAdmissionSupport": "generation-cas-v1",
        }.items()):
            raise StreamsError("capacity successor lacks supported checkpoint-bearing goal control")
        token, allowed = piweb.automatic_admission(status, intent.target, str(cwd), "wake")
        if allowed != intent.original["allowed"]:
            if not allowed:
                raise StreamsError("capacity successor received a newer stop; refusing to rearm it")
            piweb.set_automatic_admission(intent.target, False, expected_generation=token["generation"])
        configured = piweb.configure_session(intent.target, intent.original["model"], intent.original["thinking"])
        role = intent.original.get("thread", {}).get("role", "coordinator")
        op = intent.records["dcr_operations"][intent.source]
        assignment = (op.get("continuation") or {}).get("assignment") or _pickup(stream)
        piweb.register_stream_failure(intent.target, str(cwd), stream, configured, starting=True, role=role, assignment=assignment)
        intent.successor = _replacement_target(cwd, intent.target, intent.original["model"], intent.original["thinking"], piweb.list_sessions(str(cwd)))
        intent.phase = "prepared"
        _save_replacement(stream, intent)
    successor = _replacement_target(cwd, intent.target, intent.original["model"], intent.original["thinking"], piweb.list_sessions(str(cwd)))
    if any(successor[key] != intent.successor[key] for key in ("path", "generation", "allowed", "model", "thinking")):
        raise StreamsError("replacement target settings or receiving generation changed")
    if intent.phase == "prepared" and _archive_proof(stream, intent, piweb.list_sessions(str(cwd))) is None:
        rows = load_threads(stream / "threads.tsv")
        row = next((row for row in rows if row.session == intent.source), None)
        if row is None or row.status not in {Status.active, Status.waiting_quota} or (row.role == "coordinator" and designated_coordinator(rows) != row):
            raise StreamsError("replacement old designation changed before retirement")
        _replacement_inputs(stream, intent.source)
        _resolved, current = _replacement_native(stream, row, piweb.list_sessions(str(cwd)))
        if any(current[key] != intent.original[key] for key in ("entryId", "generation", "allowed", "path", "sha256", "model", "thinking")):
            raise StreamsError("replacement old checkpoint or receiving generation changed; no retirement replay")
        _validate_replacement(stream, intent)
        intent.phase = "archiving"
        _save_replacement(stream, intent)
        expected = {key: intent.original[key] for key in ("sessionId", "cwd", "entryId", "generation")}
        receipt = piweb.archive(intent.source, expected_idle=expected)
        intent.archive = {"receipt": receipt}
        _save_replacement(stream, intent)
    if intent.phase in {"prepared", "archiving"}:
        proof = _archive_proof(stream, intent, piweb.list_sessions(str(cwd)))
        if proof is None:
            raise StreamsError("replacement archive outcome is uncertain; no source reopen or request replay")
        intent.archive["evidence"] = proof
        intent.phase = "archived"
        _save_replacement(stream, intent)
    if intent.phase != "archived":
        raise StreamsError("replacement has an unknown publication phase")
    if _archive_proof(stream, intent, piweb.list_sessions(str(cwd))) != intent.archive.get("evidence"):
        raise StreamsError("replacement old archive evidence changed before publication")
    _validate_replacement(stream, intent)
    _capacity_handoff(stream, intent)
    if not intent.published:
        lines = []
        for number, line in enumerate(intent.registry.splitlines(keepends=True)):
            cells = line.rstrip("\r\n").split("\t")
            if number and cells[0] == intent.source:
                cells[8] = "archived"
                line = "\t".join(cells) + ("\r\n" if line.endswith("\r\n") else "\n")
            lines.append(line)
        registry = "".join(lines)
        source_row = next(row for row in load_threads(stream / "threads.tsv") if row.session == intent.source)
        intent.published = registry + ("" if registry.endswith("\n") else "\n") + dump_threads([replace(source_row, session=intent.target, status=Status.active)]).split("\n", 1)[1]
        _save_replacement(stream, intent)
    _validate_replacement(stream, intent)
    current_target = _replacement_target(cwd, intent.target, intent.original["model"], intent.original["thinking"], piweb.list_sessions(str(cwd)))
    if any(current_target[key] != intent.successor[key] for key in ("path", "generation", "allowed", "model", "thinking")):
        raise StreamsError("replacement target received newer control before publication")
    _capacity_handoff(stream, intent)
    _write(stream / "threads.tsv", intent.published)
    intent.phase = "complete"
    _save_replacement(stream, intent)
    _load_checkpoint(stream, intent)
    return intent.target


def replace_locked(index: Path, project: Project, stream_id: str, target: str, *, source: str | None = None) -> str:
    stream = require_stream(index, project.info.name, stream_id).resolve()
    if not _canonical_stream(stream):
        raise StreamsError("explicit replacement requires canonical STATE without migration or healing")
    data = artifacts._read_tick_data(stream)
    book = data.get("state_log")
    if book is not None and book.get("pending") is not None:
        raise StreamsError("pending artifact publication must settle before replacement")
    with sessionlog.regular_reader(stream / "STATE.md") as handle:
        artifacts._checked_state(handle.read(), artifacts._book(book) if book is not None else artifacts.LogBook())
    intent = replacement_intent(stream)
    if intent is not None and intent.target == target and intent.mode == "adopt":
        if source is not None and source != intent.source:
            raise StreamsError("replacement --from disagrees with its saved old designation")
        return advance_replacement_locked(stream, intent)
    row = designated_coordinator(load_threads(stream / "threads.tsv"))
    if row is None or source is not None and row.session != source:
        raise StreamsError("replacement requires the exact current old coordinator designation")
    intent = _begin_replacement(stream, row, target)
    return advance_replacement_locked(stream, intent)

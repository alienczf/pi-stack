from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine import StreamsError, artifacts, clock, piweb, sessionlog

STATES = {"prepared", "sending", "transport_accepted", "consumed", "applied", "blocked", "uncertain"}


@dataclass
class GoalControl:
    run_id: str
    sequence: int
    goal: str
    revision: str
    state: str = "prepared"
    checkpoint: dict | None = None


@dataclass
class Delivery:
    id: str
    session: str
    body: str
    origin: str = "steer"
    behavior: str | None = None
    automatic: dict[str, str] | None = None
    state: str = "prepared"
    detail: str = ""
    events: list[dict] = field(default_factory=list)
    evidence: dict[str, str] | None = None
    control: GoalControl | None = None
    handoff: dict[str, str] | None = None

    def public(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _records(data: dict) -> dict[str, Delivery]:
    raw = data.get("deliveries", {})
    if not isinstance(raw, dict):
        raise StreamsError("invalid delivery records")
    records = {}
    try:
        for identity, value in raw.items():
            value = dict(value)
            if value.get("control") is not None:
                value["control"] = GoalControl(**value["control"])
            record = Delivery(**value)
            if record.id != identity or record.state not in STATES or record.origin not in ("steer", "tick", "drive") or record.behavior not in (None, "steer", "follow-up"):
                raise ValueError("invalid delivery identity or state")
            if not all(isinstance(item, str) and item.strip() for item in (record.id, record.session, record.body)):
                raise ValueError("missing delivery intent")
            if not isinstance(record.events, list) or not all(isinstance(item, dict) for item in record.events):
                raise ValueError("invalid delivery events")
            if record.automatic is not None and (
                record.origin not in ("tick", "drive") or not isinstance(record.automatic, dict)
                or set(record.automatic) != {"sessionId", "cwd", "generation", "kind"}
                or not all(isinstance(value, str) and value for value in record.automatic.values())
                or record.automatic["kind"] not in ("wake", "recovery", "resume")
            ):
                raise ValueError("invalid automatic admission snapshot")
            if record.handoff is not None and (not isinstance(record.handoff, dict) or set(record.handoff) != {"path", "sha256"} or not all(isinstance(value, str) and value for value in record.handoff.values()) or re.fullmatch(r"[0-9a-f]{64}", record.handoff["sha256"]) is None):
                raise ValueError("invalid capacity handoff evidence")
            if record.origin == "drive":
                control = record.control
                if control is None or not all(isinstance(item, str) and item for item in (control.run_id, control.goal, control.revision)) or type(control.sequence) is not int or control.sequence < 1 or control.state not in ("prepared", "queued", "sending", "ended", "uncertain", "superseded") or record.automatic is None:
                    raise ValueError("invalid current-goal control intent")
                invocation = "/poteto-mode " + control.goal
                if (record.handoff is None and (record.body != invocation or record.automatic["kind"] != "wake")
                    or record.handoff is not None and (not record.body.endswith("\n" + invocation) or record.body.startswith("/") or record.automatic["kind"] != "recovery")):
                    raise ValueError("invalid checkpoint-bearing current-goal invocation")
                checkpoint = control.checkpoint
                if checkpoint is not None and (not isinstance(checkpoint, dict) or set(checkpoint) != {'path', 'entryId', 'sha256', 'lines'} or not all(isinstance(checkpoint[key], str) and checkpoint[key] for key in ('path', 'entryId', 'sha256')) or re.fullmatch(r'[0-9a-f]{64}', checkpoint['sha256']) is None or type(checkpoint['lines']) is not int or checkpoint['lines'] < 2):
                    raise ValueError("invalid current-goal native checkpoint")
            elif record.control is not None:
                raise ValueError("control facts belong only to an automatic drive delivery")
            if not isinstance(record.detail, str) or (record.origin == "tick" and not record.events):
                raise ValueError("invalid delivery description or empty tick batch")
            if record.state == "applied" and (
                not isinstance(record.evidence, dict) or set(record.evidence) != {"path", "sha256"}
                or not all(isinstance(item, str) and item for item in record.evidence.values())
                or re.fullmatch(r"[0-9a-f]{64}", record.evidence["sha256"]) is None
            ):
                raise ValueError("applied delivery has no concrete evidence")
            records[identity] = record
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid delivery record: {exc}") from exc
    return records


def _save(stream_dir: Path, record: Delivery, *, tick: bool = False) -> dict:
    data = artifacts._read_tick_data(stream_dir)
    records = _records(data)
    records[record.id] = record
    data["deliveries"] = {identity: item.public() for identity, item in records.items()}
    if tick:
        current = data.get("tick_delivery")
        if current is not None and current != record.id:
            raise StreamsError("another tick delivery is pending")
        data["tick_delivery"] = record.id
    artifacts._save_tick_data(stream_dir, data)
    return record.public()


def _get(stream_dir: Path, identity: str) -> Delivery:
    records = _records(artifacts._read_tick_data(stream_dir))
    if identity not in records:
        raise StreamsError(f"delivery {identity} is unavailable")
    return records[identity]


def receipts(stream_dir: Path) -> list[dict]:
    return [record.public() for record in _records(artifacts._read_tick_data(stream_dir)).values()]


def _handoff_context(stream_dir: Path, proof: dict) -> str:
    if _evidence(stream_dir, proof["path"]) != proof:
        raise StreamsError("capacity continuation handoff changed; no dispatch")
    path = stream_dir / proof["path"]
    with sessionlog.regular_reader(path) as handle:
        raw = handle.read()
        if hashlib.sha256(raw).hexdigest() != proof["sha256"]:
            raise StreamsError("capacity continuation handoff changed while reading")
        os.fsync(handle.fileno())
    directories = {path.parent}
    try:
        public = json.loads(raw)
        for key in ("evidence", "syncedState", "currentState"):
            reference = public[key]
            if _evidence(stream_dir, reference["path"]) != reference:
                raise StreamsError("capacity continuation referenced evidence changed; no dispatch")
            path = stream_dir / reference["path"]
            with sessionlog.regular_reader(path) as handle:
                if hashlib.file_digest(handle, "sha256").hexdigest() != reference["sha256"]:
                    raise StreamsError("capacity continuation referenced evidence changed while reading")
                os.fsync(handle.fileno())
            directories.add(path.parent)
        archive = public["archive"]
        with sessionlog.regular_reader(Path(archive["archivePath"])) as handle:
            if hashlib.file_digest(handle, "sha256").hexdigest() != archive["sha256"]:
                raise StreamsError("capacity continuation archived history changed; no dispatch")
        checkpoint = public["checkpoint"]
        sessionlog.read_record(Path(archive["archivePath"]), public["source"], checkpoint["entryId"], checkpoint["sha256"], archived=True)
        for directory in directories:
            descriptor = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            try:
                os.fsync(descriptor)
            finally:
                os.close(descriptor)
    except (KeyError, TypeError, ValueError, OSError) as exc:
        raise StreamsError(f"capacity continuation evidence unavailable; no dispatch: {exc}") from exc
    return f"Retained dump recovery handoff {stream_dir / proof['path']}\nSHA-256 {proof['sha256']}\n{raw.decode('utf-8')}\n"


def _attach_handoff(stream_dir: Path, record: Delivery) -> None:
    from engine.replacement import successor_handoff

    proof = successor_handoff(stream_dir, record.session)
    if proof is None:
        return
    previous = [item for item in _records(artifacts._read_tick_data(stream_dir)).values() if item.session == record.session and item.handoff is not None]
    if any(item.state in {"prepared", "sending", "uncertain"} or item.control is not None and item.control.state in {"sending", "uncertain"} for item in previous):
        raise StreamsError("first capacity handoff delivery must settle before another continuation")
    if any(item.state in {"consumed", "applied"} or item.control is not None and item.control.state == "ended" for item in previous):
        return
    record.handoff = proof
    record.body = _handoff_context(stream_dir, proof) + record.body
    if record.control is not None:
        record.automatic = {**record.automatic, "kind": "recovery"}


def _verify_handoff(stream_dir: Path, record: Delivery) -> None:
    if record.handoff is not None:
        context = _handoff_context(stream_dir, record.handoff)
        if not record.body.startswith(context) or record.control is not None and record.body != context + "/poteto-mode " + record.control.goal:
            raise StreamsError("saved capacity continuation changed its exact handoff context")


def prepare_locked(stream_dir: Path, identity: str, session: str, body: str, *, events: list[dict] | None = None, behavior: str | None = None, automatic_kind: str = "wake") -> dict:
    if not identity.strip() or not session.strip() or not body.strip():
        raise StreamsError("delivery identity, destination and body are required")
    record = Delivery(identity, session, body, origin="steer" if events is None else "tick", behavior=behavior, events=events or [])
    records = _records(artifacts._read_tick_data(stream_dir))
    if identity in records:
        old = records[identity]
        if old.handoff is not None:
            record.handoff = old.handoff
            record.body = _handoff_context(stream_dir, old.handoff) + record.body
        if (old.session, old.body, old.origin, old.events, old.behavior) != (record.session, record.body, record.origin, record.events, record.behavior) or (old.automatic is not None and old.automatic["kind"] != automatic_kind):
            raise StreamsError(f"delivery {identity} has changed intent")
        return old.public()
    if events is not None:
        status = _require_destination(stream_dir, record, session)
        record.automatic, _allowed = piweb.automatic_admission(status, session, str(stream_dir), automatic_kind)
    _attach_handoff(stream_dir, record)
    if events is None:
        artifacts.append_log_locked(stream_dir, clock.stamp(clock.now()), f"Steer {identity}", f"Destination session: {session}\n{body}", request_id=f"delivery:{identity}")
    return _save(stream_dir, record, tick=events is not None)


def prepare_control_locked(stream_dir: Path, identity: str, session: str, goal: str, revision: str, run_id: str, sequence: int, automatic: dict[str, str]) -> dict:
    record = Delivery(identity, session, "/poteto-mode " + goal, origin="drive", automatic=automatic, control=GoalControl(run_id, sequence, goal, revision))
    if identity in _records(artifacts._read_tick_data(stream_dir)):
        raise StreamsError("current-goal delivery identity already exists; reconcile it instead")
    _attach_handoff(stream_dir, record)
    return _save(stream_dir, record)


def observe_control_locked(stream_dir: Path, identity: str, *, state: str | None = None) -> dict:
    record = _get(stream_dir, identity)
    if record.control is None or record.automatic is None:
        raise StreamsError("delivery is not a saved current-goal control intent")
    if state is None:
        native = piweb.control_goal_status(record.session, record.automatic["cwd"], identity)
        _control_receipt(record, native)
        state = native["state"]
    record.control.state = state
    if state == "uncertain":
        if record.state != "blocked":
            record.state = "uncertain"
            record.detail = "Native control admission is uncertain; do not replay the saved task."
    elif state == "superseded":
        record.detail = "Unadmitted automatic goal was superseded; original delivery intent is retained."
    elif record.state in ("sending", "uncertain"):
        record.state = "transport_accepted"
    return _save(stream_dir, record)


def reconcile_queued_control_locked(stream_dir: Path, identity: str) -> dict:
    record = _get(stream_dir, identity)
    if record.control is None or record.control.state != "queued" or record.automatic is None:
        raise StreamsError("only a proven unadmitted queued goal can be explicitly reconciled")
    _verify_handoff(stream_dir, record)
    response = piweb.control_goal(record.session, identity, record.control.run_id, record.control.sequence, record.body, record.control.goal, record.automatic)
    _control_receipt(record, response)
    record.control.state = response["state"]
    return _save(stream_dir, record)


def _control_receipt(record: Delivery, native: dict) -> None:
    control = record.control
    if control is None or native.get("id") != record.id or native.get("sessionId") != record.session or native.get("text") != record.body or native.get("potetoGoal") != control.goal or native.get("runId") != control.run_id or native.get("sequence") != control.sequence or native.get("automaticAdmission") != record.automatic:
        raise StreamsError("current-goal receiver changed the exact saved intent")


def _require_destination(stream_dir: Path, record: Delivery, session: str) -> dict[str, object]:
    from engine.threads import Status, _native_session, designated_coordinator, load_threads, resolve_coordinator
    from engine.replacement import successor_handoff

    rows = load_threads(stream_dir / "threads.tsv")
    if record.handoff is not None and record.handoff == successor_handoff(stream_dir, session):
        target = next((row for row in rows if row.session == session and row.status is Status.active), None)
        if target is not None and target.role != "coordinator" and session == record.session:
            return _native_session(session, Path(target.worktree)).status
    row = designated_coordinator(rows)
    if session != record.session or row is None or row.session != session:
        raise StreamsError(f"delivery {record.id} destination is stale or does not match")
    resolved = resolve_coordinator(stream_dir)
    if resolved is None or resolved.row.session != session:
        raise StreamsError(f"delivery {record.id} destination changed before dispatch")
    return resolved.native.status


def send_locked(stream_dir: Path, identity: str) -> dict:
    from engine.threads import require_ratified

    record = _get(stream_dir, identity)
    if record.state == "sending":
        record.state = "uncertain"
        record.detail = "Interrupted send; inspect the transcript and affected artifacts before any replay."
        return _save(stream_dir, record)
    if record.state != "prepared":
        return record.public()
    status = _require_destination(stream_dir, record, record.session)
    if record.origin in ("tick", "drive"):
        require_ratified(stream_dir)
        if record.automatic is None:
            record.state = "blocked"
            record.detail = "No saved automatic admission generation; reconcile the old request without renewing it."
            return _save(stream_dir, record)
        current, allowed = piweb.automatic_admission(status, record.session, record.automatic["cwd"], record.automatic["kind"])
        if not allowed or current != record.automatic:
            record.state = "blocked"
            record.detail = "Automatic admission was disabled or superseded; the saved generation is not renewed."
            return _save(stream_dir, record)
    from engine import blocked_goals
    if not blocked_goals.permit(stream_dir, record.control.goal if record.control else record.body):
        record.state, record.detail = "blocked", "Blocked-goal escalation suppresses identical prompts. Select a different authorized unit."
        return _save(stream_dir, record)
    if record.control is not None:
        record.control.checkpoint = None
        leaf = status.get('rotationSafety', {}).get('entryId')
        if isinstance(leaf, str) and leaf:
            sources = [item for item in piweb.list_sessions(record.automatic['cwd']) if item.get('id') == record.session]
            if len(sources) == 1 and isinstance(sources[0].get('path'), str):
                try:
                    record.control.checkpoint = sessionlog.control_checkpoint(Path(sources[0]['path']), record.session, record.automatic['cwd'], leaf)
                except (StreamsError, OSError, ValueError):
                    pass
    _verify_handoff(stream_dir, record)
    record.state = "sending"
    _save(stream_dir, record)
    try:
        if record.control is not None:
            response = piweb.control_goal(record.session, identity, record.control.run_id, record.control.sequence, record.body, record.control.goal, record.automatic)
            _control_receipt(record, response)
            record.control.state = response["state"]
            if response["state"] == "uncertain":
                record.state = "uncertain"
                record.detail = "Receiver retained an uncertain goal admission; no replay is authorized."
                return _save(stream_dir, record)
        else:
            response = piweb.prompt(record.session, record.body, record.behavior, delivery_id=identity, automatic=record.automatic)
            if response.get("transportAccepted") is not True:
                raise StreamsError("delivery transport acceptance is unconfirmed")
    except StreamsError as exc:
        record.state = "blocked" if isinstance(exc, piweb.PromptRejected) else "uncertain"
        record.detail = str(exc)
        _save(stream_dir, record)
        raise
    record.state = "transport_accepted"
    return _save(stream_dir, record)


def _evidence(stream_dir: Path, relative: str | None) -> dict[str, str]:
    if relative is None:
        raise StreamsError("an applied receipt requires concrete owned-artifact evidence")
    path = Path(relative)
    if path.is_absolute() or not path.parts or ".." in path.parts:
        raise StreamsError("receipt evidence must stay in the owned stream")
    if path.parts[0] not in ("STATE.md", "context", "checks", "handover", "history"):
        raise StreamsError("receipt evidence must be an owned agent-facing artifact")
    digest = hashlib.sha256()
    try:
        directory = os.open(stream_dir, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            for part in path.parts[:-1]:
                child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=directory)
                os.close(directory)
                directory = child
            name = path.parts[-1]
            if not stat.S_ISREG(os.stat(name, dir_fd=directory, follow_symlinks=False).st_mode):
                raise StreamsError("receipt evidence must be a regular file, not a symlink or special file")
            descriptor = os.open(name, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK, dir_fd=directory)
            try:
                before = os.fstat(descriptor)
                if not stat.S_ISREG(before.st_mode):
                    raise StreamsError("receipt evidence must be a regular file")
                if before.st_size == 0:
                    raise StreamsError("receipt evidence is empty")
                with os.fdopen(descriptor, "rb", closefd=False) as handle:
                    remaining = before.st_size
                    while remaining:
                        chunk = handle.read(min(65536, remaining))
                        if not chunk:
                            raise StreamsError("receipt evidence changed while hashing")
                        digest.update(chunk)
                        remaining -= len(chunk)
                after = os.fstat(descriptor)
                if (before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_size, after.st_mtime_ns, after.st_ctime_ns):
                    raise StreamsError("receipt evidence changed while hashing")
            finally:
                os.close(descriptor)
        finally:
            os.close(directory)
    except OSError as exc:
        raise StreamsError(f"receipt evidence unavailable: {exc}") from exc
    return {"path": path.as_posix(), "sha256": digest.hexdigest()}


def acknowledge_locked(stream_dir: Path, identity: str, session: str, state: str, detail: str, *, evidence: str | None = None) -> dict:
    record = _get(stream_dir, identity)
    _require_destination(stream_dir, record, session)
    if state not in ("consumed", "applied", "blocked") or not detail.strip():
        raise StreamsError("receipt requires consumed, applied or blocked and a concrete description")
    if record.state == "applied":
        proof = _evidence(stream_dir, evidence) if state == "applied" else None
        if state == record.state and detail == record.detail and proof == record.evidence:
            return record.public()
        raise StreamsError("an applied receipt cannot be rewritten")
    if state == "applied":
        if record.state != "consumed":
            raise StreamsError("an instruction must be consumed before an applied receipt")
        record.evidence = _evidence(stream_dir, evidence)
    elif state == "consumed" and record.state not in ("transport_accepted", "sending", "uncertain", "consumed"):
        raise StreamsError("only an admitted instruction can be consumed")
    if state == "blocked":
        from engine import blocked_goals
        blocked_goals.receive(stream_dir, record.control.goal if record.control else record.body, "delivery:" + identity, sent=identity if record.state in {"transport_accepted", "consumed", "sending", "uncertain"} else "")
    elif state == "applied":
        from engine import blocked_goals
        blocked_goals.progress(stream_dir, record.control.goal if record.control else record.body, identity)
    record.state = state
    record.detail = detail
    return _save(stream_dir, record)


def current_tick(stream_dir: Path) -> dict | None:
    data = artifacts._read_tick_data(stream_dir)
    identity = data.get("tick_delivery")
    if identity is None:
        return None
    record = _get(stream_dir, identity)
    if record.origin != "tick":
        raise StreamsError("tick delivery points to a non-tick instruction")
    return record.public()


def finish_tick_locked(stream_dir: Path, pending: list[dict]) -> list[dict]:
    data = artifacts._read_tick_data(stream_dir)
    identity = data.get("tick_delivery")
    if identity is None:
        return pending
    record = _get(stream_dir, identity)
    if record.origin != "tick":
        raise StreamsError("tick delivery points to a non-tick instruction")
    if record.state != "applied":
        return pending
    if pending[:len(record.events)] != record.events:
        raise StreamsError("applied delivery does not match the original pending event prefix")
    data["pending"] = pending[len(record.events):]
    data.pop("tick_delivery")
    artifacts._save_tick_data(stream_dir, data)
    return data["pending"]


def new_identity() -> str:
    return uuid.uuid4().hex

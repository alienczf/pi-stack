from __future__ import annotations

import hashlib
import os
import re
import stat
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine import StreamsError, artifacts, clock, piweb

STATES = {"prepared", "sending", "transport_accepted", "consumed", "applied", "blocked", "uncertain"}


@dataclass
class Delivery:
    id: str
    session: str
    body: str
    origin: str = "steer"
    behavior: str | None = None
    state: str = "prepared"
    detail: str = ""
    events: list[dict] = field(default_factory=list)
    evidence: dict[str, str] | None = None

    def public(self) -> dict:
        return {key: value for key, value in asdict(self).items() if value is not None}


def _records(data: dict) -> dict[str, Delivery]:
    raw = data.get("deliveries", {})
    if not isinstance(raw, dict):
        raise StreamsError("invalid delivery records")
    records = {}
    try:
        for identity, value in raw.items():
            record = Delivery(**value)
            if record.id != identity or record.state not in STATES or record.origin not in ("steer", "tick") or record.behavior not in (None, "steer", "follow-up"):
                raise ValueError("invalid delivery identity or state")
            if not all(isinstance(item, str) and item.strip() for item in (record.id, record.session, record.body)):
                raise ValueError("missing delivery intent")
            if not isinstance(record.events, list) or not all(isinstance(item, dict) for item in record.events):
                raise ValueError("invalid delivery events")
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


def prepare_locked(stream_dir: Path, identity: str, session: str, body: str, *, events: list[dict] | None = None, behavior: str | None = None) -> dict:
    if not identity.strip() or not session.strip() or not body.strip():
        raise StreamsError("delivery identity, destination and body are required")
    record = Delivery(identity, session, body, origin="steer" if events is None else "tick", behavior=behavior, events=events or [])
    records = _records(artifacts._read_tick_data(stream_dir))
    if identity in records:
        old = records[identity]
        if (old.session, old.body, old.origin, old.events, old.behavior) != (record.session, record.body, record.origin, record.events, record.behavior):
            raise StreamsError(f"delivery {identity} has changed intent")
        return old.public()
    if events is None:
        artifacts.append_log_locked(stream_dir, clock.stamp(clock.now()), f"Steer {identity}", f"Destination session: {session}\n{body}", request_id=f"delivery:{identity}")
    return _save(stream_dir, record, tick=events is not None)


def _require_destination(stream_dir: Path, record: Delivery, session: str) -> None:
    from engine.threads import designated_coordinator, load_threads, resolve_coordinator

    row = designated_coordinator(load_threads(stream_dir / "threads.tsv"))
    if session != record.session or row is None or row.session != session:
        raise StreamsError(f"delivery {record.id} destination is stale or does not match")
    resolved = resolve_coordinator(stream_dir)
    if resolved is None or resolved.row.session != session:
        raise StreamsError(f"delivery {record.id} destination changed before dispatch")


def send_locked(stream_dir: Path, identity: str) -> dict:
    from engine.threads import require_ratified

    record = _get(stream_dir, identity)
    if record.state == "sending":
        record.state = "uncertain"
        record.detail = "Interrupted send; inspect the transcript and affected artifacts before any replay."
        return _save(stream_dir, record)
    if record.state != "prepared":
        return record.public()
    _require_destination(stream_dir, record, record.session)
    if record.origin == "tick":
        require_ratified(stream_dir)
    record.state = "sending"
    _save(stream_dir, record)
    try:
        response = piweb.prompt(record.session, record.body, record.behavior, delivery_id=identity)
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

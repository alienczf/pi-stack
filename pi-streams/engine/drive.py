from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from engine import StreamsError, artifacts, delivery, piweb
from engine.threads import Coordinator, require_ratified


@dataclass
class Drive:
    enabled: bool = False
    run_id: str = ""
    sequence: int = 0
    current_delivery: str = ""
    desired: dict[str, str] | None = None
    remote_state: str = "not-requested"
    remote_generation: str = ""


def load(stream_dir: Path) -> Drive:
    value = artifacts._read_tick_data(stream_dir).get("drive")
    if value is None:
        return Drive()
    try:
        record = Drive(**value)
        if type(record.enabled) is not bool or not isinstance(record.run_id, str) or not isinstance(record.current_delivery, str) or type(record.sequence) is not int or record.sequence < 0 or record.enabled and not record.run_id:
            raise ValueError("invalid explicit switch or transport identity")
        if record.remote_state not in ("not-requested", "on-unconfirmed", "on-confirmed", "off-unconfirmed", "off-confirmed") or not isinstance(record.remote_generation, str):
            raise ValueError("invalid remote drive confirmation")
        if record.desired is not None and (not isinstance(record.desired, dict) or set(record.desired) != {"goal", "body", "revision"} or not all(isinstance(item, str) for item in record.desired.values())):
            raise ValueError("invalid desired goal snapshot")
        return record
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid drive control: {exc}") from exc


def save(stream_dir: Path, record: Drive) -> dict:
    data = artifacts._read_tick_data(stream_dir)
    data["drive"] = asdict(record)
    artifacts._save_tick_data(stream_dir, data)
    return asdict(record)


def public(stream_dir: Path) -> dict:
    return asdict(load(stream_dir))


def is_paused(stream_dir: Path) -> bool:
    return "drive" in artifacts._read_tick_data(stream_dir) and not load(stream_dir).enabled


def enable(stream_dir: Path, resolved: Coordinator) -> dict:
    artifacts._read_stream_state_locked(stream_dir)
    require_ratified(stream_dir)
    piweb.require_control_goal(resolved.row.session)
    record = Drive(run_id=uuid.uuid4().hex, remote_state="on-unconfirmed")
    save(stream_dir, record)
    remote = piweb.set_automatic_admission(resolved.row.session, True)
    record.enabled, record.remote_state, record.remote_generation = True, "on-confirmed", str(remote["generation"])
    return save(stream_dir, record)


def pause_local(stream_dir: Path) -> dict:
    record = load(stream_dir)
    record.enabled, record.remote_state, record.remote_generation = False, "off-unconfirmed", ""
    return save(stream_dir, record)


def confirm_pause(stream_dir: Path, resolved: Coordinator) -> dict:
    record = load(stream_dir)
    if record.enabled or record.remote_state != "off-unconfirmed":
        raise StreamsError("local off intent must precede native stop publication")
    remote = piweb.set_automatic_admission(resolved.row.session, False)
    record.remote_state, record.remote_generation = "off-confirmed", str(remote["generation"])
    return save(stream_dir, record)


def is_stalled(status: dict[str, object]) -> bool:
    activity = status.get("activity")
    indicated = isinstance(activity, dict) and activity.get("phase") in ("waiting", "error", "idle")
    return bool(status.get("pendingAsk") or status.get("pendingExtensionDialogs")) or indicated or not any(status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning"))


def step(stream_dir: Path, resolved: Coordinator | None, stalled: bool, *, maintenance: bool = False) -> bool:
    record = load(stream_dir)
    if not record.enabled or resolved is None:
        return False
    if not stalled:
        return True
    state = artifacts._read_stream_state_locked(stream_dir)
    require_ratified(stream_dir)
    goal = artifacts.resolve_current_goal(state)
    revision = hashlib.sha256(goal.encode("utf-8")).hexdigest()
    record.desired = {"goal": goal, "body": "/poteto-mode " + goal, "revision": revision}
    save(stream_dir, record)
    piweb.require_settings(resolved.native.status, resolved.row.model, resolved.row.thinking)
    token, allowed = piweb.automatic_admission(resolved.native.status, resolved.row.session, resolved.row.worktree, "wake")
    previous = None
    if record.current_delivery:
        previous = delivery._get(stream_dir, record.current_delivery)
        if previous.control is None:
            raise StreamsError("drive delivery points to a non-control instruction")
        if previous.session == resolved.row.session and previous.state not in ("prepared", "blocked") and previous.control.state != "superseded":
            try:
                delivery.observe_control_locked(stream_dir, previous.id)
                previous = delivery._get(stream_dir, previous.id)
            except StreamsError as exc:
                previous.state, previous.detail = "uncertain", str(exc)
                previous.control.state = "uncertain"
                delivery._save(stream_dir, previous)
                return True
        if previous.control.state in ("sending", "uncertain") or previous.state in ("sending", "uncertain"):
            return True
        same = previous.session == resolved.row.session and previous.control.revision == revision and previous.automatic == token
        if previous.control.state == "queued" and same:
            if allowed and not maintenance:
                delivery.reconcile_queued_control_locked(stream_dir, previous.id)
            return True
        if previous.state == "prepared" and same:
            if not maintenance:
                delivery.send_locked(stream_dir, previous.id)
            return True
        if previous.state == "blocked" and same:
            if allowed and not maintenance and previous.control.state == "prepared":
                previous.state, previous.detail = "prepared", ""
                delivery._save(stream_dir, previous)
                try:
                    delivery.send_locked(stream_dir, previous.id)
                except piweb.PromptRejected:
                    pass
            return True
        if not allowed:
            return True
    record.sequence += 1
    identity = delivery.new_identity()
    delivery.prepare_control_locked(stream_dir, identity, resolved.row.session, goal, revision, record.run_id, record.sequence, token)
    record.current_delivery = identity
    save(stream_dir, record)
    if not maintenance:
        try:
            delivery.send_locked(stream_dir, identity)
        except piweb.PromptRejected:
            return True
        current = delivery._get(stream_dir, identity)
        if previous is not None and previous.control is not None and previous.control.state == "queued" and current.state == "transport_accepted":
            delivery.observe_control_locked(stream_dir, previous.id, state="superseded")
    return True

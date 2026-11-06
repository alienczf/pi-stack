from __future__ import annotations

import hashlib
import uuid
from dataclasses import asdict, dataclass
from enum import Enum
from pathlib import Path

from engine import StreamsError, artifacts, delivery, piweb
from engine.threads import Coordinator, Status, _native_session, designated_coordinator, load_threads, resolve_coordinator


class StopIntent(str, Enum):
    OPERATOR_OFF = "operator-off"


@dataclass(frozen=True)
class LegacyResume:
    run_id: str
    session: str
    cwd: str
    generation: str
    recovery_id: str = ""


@dataclass
class Drive:
    enabled: bool = False
    run_id: str = ""
    sequence: int = 0
    current_delivery: str = ""
    desired: dict[str, str] | None = None
    remote_state: str = "not-requested"
    remote_generation: str = ""
    resume_original: str = ""
    stop_intent: StopIntent | None = None


def load(stream_dir: Path) -> Drive:
    value = artifacts._read_tick_data(stream_dir).get("drive")
    if value is None:
        return Drive()
    try:
        record = Drive(**value)
        if type(record.enabled) is not bool or not isinstance(record.run_id, str) or not isinstance(record.current_delivery, str) or type(record.sequence) is not int or record.sequence < 0 or record.enabled and not record.run_id:
            raise ValueError("invalid explicit switch or transport identity")
        if record.remote_state not in ("not-requested", "on-unconfirmed", "on-confirmed", "off-unconfirmed", "off-confirmed") or not isinstance(record.remote_generation, str) or not isinstance(record.resume_original, str):
            raise ValueError("invalid remote drive confirmation")
        if record.stop_intent is not None:
            record.stop_intent = StopIntent(record.stop_intent)
            if record.enabled or record.remote_state not in ("off-unconfirmed", "off-confirmed"):
                raise ValueError("operator off contradicts drive confirmation")
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
    raw = resolved.native.status.get("automaticAdmission")
    initial = (
        isinstance(raw, dict) and raw.get("generation") == "unarmed"
        and raw.get("durable") is False and raw.get("allowed") is False
        and raw.get("sessionId") == resolved.row.session
        and raw.get("cwd") == str(Path(resolved.row.worktree).resolve())
    )
    generation = None if initial else piweb.automatic_admission(resolved.native.status, resolved.row.session, resolved.row.worktree, "wake")[0]["generation"]
    piweb.require_control_goal(resolved.row.session)
    record = Drive(run_id=uuid.uuid4().hex, remote_state="on-unconfirmed")
    save(stream_dir, record)
    remote = piweb.set_automatic_admission(resolved.row.session, True, expected_generation=generation, initialize_if_absent=initial)
    piweb.automatic_admission({"automaticAdmission": remote}, resolved.row.session, resolved.row.worktree, "wake")
    record.enabled, record.remote_state, record.remote_generation = True, "on-confirmed", str(remote["generation"])
    return save(stream_dir, record)


def _legacy_candidate(record: Drive) -> bool:
    return not record.enabled and record.stop_intent is None and record.remote_state == "off-confirmed" and bool(record.run_id and record.remote_generation) and not record.resume_original


def reconcile_locked(stream_dir: Path) -> LegacyResume | None:
    record = load(stream_dir)
    if not _legacy_candidate(record):
        return None
    from engine import dcr, failure, failure_recovery, replacement, sessionlog, terminal_sessions
    rows = load_threads(stream_dir / "threads.tsv")
    live = [row for row in rows if row.status in {Status.active, Status.waiting_quota, Status.parked} and terminal_sessions.load(stream_dir, row.session, row.worktree) is None]
    if not live:
        return None
    state = artifacts._read_stream_state_locked(stream_dir)
    goal = artifacts.resolve_current_goal(state)
    if not goal.strip() or failure.policy_blocks_goal(stream_dir, goal):
        return None
    intent = replacement.replacement_intent(stream_dir)
    data = artifacts._read_tick_data(stream_dir)
    if intent is not None and intent.phase != "complete":
        raise StreamsError("Existing replacement owns admission; no legacy rearm")
    designated = designated_coordinator(rows)
    if designated not in live:
        return None
    pending = [failure_recovery.load(stream_dir, sid) for sid in data.get("failure_recoveries", {})]
    pending = [op for op in pending if op.phase != "complete" and any(row.session == op.session and row.role == "coordinator" for row in rows)]
    if pending:
        owned = [(op, row) for op in pending for row in rows if row.session == op.session and row.role == "coordinator" and op.result is not None and op.result.get("state") == "forked" and op.result.get("generation") == record.remote_generation]
        if len(owned) != 1:
            raise StreamsError("Existing recovery has no exact legacy continuation generation")
        op, row = owned[0]
        if designated.session not in {op.session, op.result["forkSessionId"]}:
            raise StreamsError("Existing recovery no longer owns the designated coordinator")
        if op.phase not in {"retiring", "retired", "clearing"}:
            if row not in live:
                raise StreamsError("Terminal original preserves legacy recovery parking")
            native = _native_session(row.session, Path(row.worktree))
            token, allowed = piweb.automatic_admission(native.status, row.session, row.worktree, "recovery")
            if allowed or token["generation"] != record.remote_generation:
                raise StreamsError("Newer original stop/input superseded legacy recovery continuation")
            piweb.require_settings(native.status, row.model, row.thinking)
        return LegacyResume(record.run_id, row.session, row.worktree, record.remote_generation, op.id)
    operation = dcr.load(stream_dir, designated.session)
    if operation is not None and operation.phase not in {"complete", "superseded", "rotated"}:
        raise StreamsError("Existing DCR owns admission; no legacy rearm")
    resolved = resolve_coordinator(stream_dir, rows)
    if resolved is None:
        return None
    sid, cwd, status = resolved.row.session, resolved.row.worktree, resolved.native.status
    token, allowed = piweb.automatic_admission(status, sid, cwd, "recovery")
    if allowed or token["generation"] != record.remote_generation:
        raise StreamsError("Newer receiving stop/input superseded legacy drive healing")
    piweb.require_settings(status, resolved.row.model, resolved.row.thinking)
    piweb.require_control_goal(sid)
    piweb.register_stream_failure(sid, cwd, stream_dir, status)
    boundary = status.get("failureBoundary")
    episode = failure.load(stream_dir, sid)
    if episode is not None and (episode.cancelled or episode.uncertain_jobs or episode.kind == "content-policy"):
        raise StreamsError("Cancellation, policy or uncertain effects preserve legacy parking")
    if isinstance(boundary, dict) and boundary.get("state") == "parked":
        return LegacyResume(record.run_id, sid, cwd, record.remote_generation)
    if isinstance(boundary, dict) and boundary.get("state") != "watching" or episode is not None and episode.state != "recovered":
        raise StreamsError("Unresolved failure owns legacy admission")
    if any(item["state"] in {"sending", "uncertain"} or item.get("control", {}).get("state") in {"sending", "uncertain"} for item in delivery.receipts(stream_dir)) or any(value.get("replay") for value in data.get("sessions", {}).values()):
        raise StreamsError("Uncertain delivery/replay preserves legacy admission")
    if status.get("controlGoal", {}).get("state") in {"sending", "uncertain"}:
        raise StreamsError("Uncertain native control owns legacy admission")
    native_file = resolved.native.info.get("path")
    if not isinstance(native_file, str) or sessionlog.failure_observation(Path(native_file), sid, cwd, status.get("rotationSafety", {}).get("entryId")) is not None:
        raise StreamsError("Unclassified failure preserves legacy admission")
    remote = piweb.set_automatic_admission(sid, True, expected_generation=record.remote_generation)
    piweb.automatic_admission({"automaticAdmission": remote}, sid, cwd, "wake")
    record.enabled, record.remote_state, record.remote_generation = True, "on-confirmed", str(remote["generation"])
    save(stream_dir, record)
    return None


def request_resume(stream_dir: Path, original: str, *, legacy: LegacyResume | None = None) -> dict:
    artifacts._read_stream_state_locked(stream_dir)
    if legacy is None:
        record = Drive(enabled=True, run_id=uuid.uuid4().hex, remote_state="on-unconfirmed", resume_original=original)
    else:
        record = load(stream_dir)
        if not _legacy_candidate(record) or record.run_id != legacy.run_id or record.remote_generation != legacy.generation or original != legacy.session:
            raise StreamsError("Legacy resume no longer owns exact local drive intent")
        record.enabled, record.remote_state, record.resume_original = True, "on-unconfirmed", original
    return save(stream_dir, record)


def confirm_resume(stream_dir: Path, original: str, sid: str, cwd: str, generation: str) -> None:
    record = load(stream_dir)
    if not record.enabled or record.resume_original != original:
        return
    token, allowed = piweb.automatic_admission(piweb.session_status(sid), sid, cwd, "wake")
    if not allowed or token["generation"] != generation:
        raise StreamsError("Newer receiving stop/input superseded drive resume confirmation")
    record.remote_state, record.remote_generation, record.resume_original = "on-confirmed", generation, ""
    save(stream_dir, record)


def pause_local(stream_dir: Path) -> dict:
    record = load(stream_dir)
    record.enabled, record.remote_state, record.remote_generation, record.resume_original = False, "off-unconfirmed", "", ""
    record.stop_intent = StopIntent.OPERATOR_OFF
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
    return bool(status.get("pendingAsk") or status.get("pendingDialogs")) or indicated or not any(status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning"))


def step(stream_dir: Path, resolved: Coordinator | None, stalled: bool, *, maintenance: bool = False) -> bool:
    record = load(stream_dir)
    if not record.enabled or resolved is None:
        return False
    if not stalled:
        return True
    state = artifacts._read_stream_state_locked(stream_dir)
    goal = artifacts.resolve_current_goal(state)
    from engine.failure import policy_blocks_goal
    if policy_blocks_goal(stream_dir, goal):
        return True
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
        if previous.session == resolved.row.session and previous.control.state != "superseded" and (previous.state not in ("prepared", "blocked") or previous.control.state in ("sending", "uncertain")):
            try:
                delivery.observe_control_locked(stream_dir, previous.id)
                previous = delivery._get(stream_dir, previous.id)
            except StreamsError as exc:
                if previous.state != "blocked":
                    previous.state, previous.detail = "uncertain", str(exc)
                previous.control.state = "uncertain"
                delivery._save(stream_dir, previous)
                return True
        if previous.control.state in ("sending", "uncertain") or previous.state in ("sending", "uncertain"):
            return True
        same = previous.session == resolved.row.session and previous.control.revision == revision and previous.automatic == {**token, "kind": "recovery" if previous.handoff is not None else "wake"}
        if previous.control.state == "queued" and same:
            if allowed and not maintenance:
                delivery.reconcile_queued_control_locked(stream_dir, previous.id)
            return True
        if previous.state == "prepared" and same:
            if not maintenance:
                delivery.send_locked(stream_dir, previous.id)
            return True
        if previous.state == "blocked" and same and previous.control.state != "ended":
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
    from engine import blocked_goals
    native_file = resolved.native.info.get("path")
    if isinstance(native_file, str) and previous is not None and previous.control.revision == revision and previous.control.state == "ended":
        blocked_goals.observe(stream_dir, goal, resolved.row.session, native_file, dispatch=previous.id, leaf=resolved.native.status.get('rotationSafety', {}).get('entryId'))
    if not blocked_goals.permit(stream_dir, goal):
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

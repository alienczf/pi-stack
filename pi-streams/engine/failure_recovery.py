from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace
from enum import Enum
from pathlib import Path

from engine import StreamsError, artifacts, dcr, delivery, drive, failure, piweb, sessionlog, terminal_sessions
from engine.project import _write
from engine.threads import Coordinator, Status, _native_session, designated_coordinator, dump_threads, load_threads


@dataclass
class Recovery:
    id: str
    session: str
    episode: str
    cwd: str
    request: dict
    phase: str = "fork-sending"
    result: dict | None = None
    receipt: dict | None = None
    fork: str = ""
    fork_file: str = ""
    registry_before: str = ""
    registry_after: str = ""
    detail: str = ""
    generation: str = ""
    observation: dict | None = None
    retirement_request: dict | None = None
    retirement: dict | None = None
    source_sha256: str = ""
    source_leaf: str = ""
    cleanup_before: str = ""
    cleanup_after: str = ""


def load(stream: Path, sid: str) -> Recovery | None:
    data = artifacts._read_tick_data(stream).get("failure_recoveries", {})
    if not isinstance(data, dict):
        raise StreamsError("Recovery records are malformed")
    value = data.get(sid)
    if value is None:
        return None
    try:
        op = Recovery(**value)
        if op.session != sid or not op.id or not Path(op.cwd).is_absolute() or op.phase not in {"fork-refused", "fork-sending", "forked", "binding", "bound", "preparing", "dcr", "observed", "retiring", "retired", "clearing", "complete", "cancelled", "uncertain"} or not isinstance(op.request, dict):
            raise ValueError("Recovery identity/phase changed")
        return op
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"Invalid recovery record: {exc}") from exc


def save(stream: Path, op: Recovery) -> None:
    data = artifacts._read_tick_data(stream)
    records = data.setdefault("failure_recoveries", {})
    if not isinstance(records, dict):
        raise StreamsError("Recovery records are malformed")
    records[op.session] = asdict(op)
    artifacts._save_tick_data(stream, data)


def _hash(value: object) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()


def _branch(native, sid: str, cwd: str):
    return sessionlog.branch_records(Path(native.info["path"]), sid, cwd, native.status.get("rotationSafety", {}).get("entryId"))


def _result(stream: Path, op: Recovery, episode: failure.Episode, native) -> dict | None:
    matches = [(entry, raw) for entry, raw in _branch(native, op.session, op.cwd) if entry.get("customType") == "pi-web.failure-recovery" and isinstance(entry.get("data"), dict) and entry["data"].get("id") == op.id]
    if not matches:
        return None
    entry, raw = matches[-1]
    result = entry["data"]
    authorization = {"authority": op.request["authority"]}
    expected = {"version": 1, "id": op.id, "episode": op.episode, "originalSessionId": op.session, "cwd": op.cwd, "root": str(stream.resolve()), "stream": stream.name, "checkpoint": op.request["expected"]["checkpoint"], "failure": op.request["expected"]["failure"], "intentSha256": _hash(op.request), **authorization}
    if any(result.get(key) != value for key, value in expected.items()) or result.get("state") not in {"fork-sending", "forked", "cancelled", "uncertain"} or not isinstance(result.get("generation"), str):
        raise StreamsError("Native fork result changed exact request/target evidence")
    op.receipt = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest()}
    return result


def _verify_fork(op: Recovery, original):
    result = op.result
    sid, file = result.get("forkSessionId"), result.get("forkFile")
    if not isinstance(sid, str) or not sid or sid == op.session or not isinstance(file, str) or not Path(file).is_absolute():
        raise StreamsError("Returned fork SID/file is unconfirmed")
    native = _native_session(sid, Path(op.cwd))
    if native.info.get("path") != file:
        raise StreamsError("Returned fork is not its exact native file")
    with sessionlog.regular_reader(Path(file)) as source:
        header = json.loads(source.readline())
    if header.get("parentSession") != original.info["path"]:
        raise StreamsError("Returned fork parent file changed")
    held = native.status.get("failureBoundary")
    if not isinstance(held, dict) or held.get("state") != "recovering" or held.get("sessionId") != sid or held.get("cwd") != op.cwd or held.get("root") != result["root"] or held.get("stream") != result["stream"] or held.get("recovery") != {"id": op.id, "originalSessionId": op.session}:
        raise StreamsError("Returned fork has no exact receiving recovery hold")
    prefix = []
    for entry, raw in _branch(original, op.session, op.cwd):
        if entry.get("type") != "label":
            prefix.append(entry)
        if entry["id"] == result["checkpoint"]["entryId"]:
            if hashlib.sha256(raw).hexdigest() != result["checkpoint"]["sha256"]:
                raise StreamsError("Original good-prefix hash changed")
            break
    else:
        raise StreamsError("Original good checkpoint is not on the native branch")
    actual = [entry for entry, _ in _branch(native, sid, op.cwd) if entry.get("type") != "label"]
    parent = None
    for index, expected in enumerate(prefix):
        if index >= len(actual) or {**expected, "parentId": parent} != actual[index]:
            raise StreamsError("Returned fork changed the inclusive logical good prefix")
        parent = expected["id"]
    if any(entry.get("type") != "custom" or entry.get("customType") != "pi-web.stream-failure" or entry.get("data") != held for entry in actual[len(prefix):]):
        raise StreamsError("Returned fork has unowned task descendants")
    return native


class ResumeIntent(Enum):
    CONTINUE_OWNED = "continue-owned"
    OPERATOR = "operator"


def resume_parked_locked(stream: Path, at: str, *, index: Path, project, intent: ResumeIntent | drive.LegacyResume = ResumeIntent.CONTINUE_OWNED) -> list[dict]:
    artifacts._read_stream_state_locked(stream)
    explicit = intent is ResumeIntent.OPERATOR
    legacy = intent if isinstance(intent, drive.LegacyResume) else None
    if intent is not ResumeIntent.CONTINUE_OWNED and not explicit and legacy is None:
        raise StreamsError("Unknown parked resume authority")
    if drive.is_paused(stream) and not explicit and legacy is None:
        return [{"stream": stream.name, "state": "stopped", "detail": "Explicit local off remains authoritative"}]
    if legacy is not None and legacy.recovery_id:
        try:
            op, episode = load(stream, legacy.session), failure.load(stream, legacy.session)
            if op is None or op.id != legacy.recovery_id or op.cwd != legacy.cwd or op.result is None or op.result.get("generation") != legacy.generation or episode is None or episode.id != op.episode or episode.recovery_id != op.id:
                raise StreamsError("Legacy continuation lost its exact recovery journal")
            if episode.cancelled or episode.uncertain_jobs or episode.kind in {"usage-limit", "content-policy"} or not isinstance(episode.authority, dict) or not isinstance(episode.checkpoint, dict):
                raise StreamsError("Cancellation, policy, uncertain effects or lost authority preserve owned maintenance")
            retiring = op.phase in {"retiring", "retired", "clearing"}
            original = None if retiring else _native_session(op.session, Path(op.cwd))
            if original is not None:
                token, allowed = piweb.automatic_admission(original.status, op.session, op.cwd, "recovery")
                if allowed or token["generation"] != legacy.generation:
                    raise StreamsError("Newer original stop/input superseded legacy continuation")
            if op.fork:
                rows = load_threads(stream / "threads.tsv")
                originals = [row for row in rows if row.session == op.session]
                forks = [row for row in rows if row.session == op.fork]
                if len(originals) != 1 or len(forks) != 1 or forks[0] != replace(originals[0], session=op.fork, status=Status.active) or terminal_sessions.load(stream, op.fork, op.cwd) is not None:
                    raise StreamsError("Legacy continuation lost its exact registry fork")
                fork = _native_session(op.fork, Path(op.cwd))
                if fork.info.get("path") != op.fork_file or fork.status.get("failureBoundary", {}).get("recovery") != {"id": op.id, "originalSessionId": op.session}:
                    raise StreamsError("Legacy continuation lost its native fork owner")
            else:
                fork = _verify_fork(op, original)
            piweb.require_settings(fork.status, episode.authorized_model, episode.authorized_thinking)
            generation = op.generation or op.result["forkGeneration"]
            enabled = bool(op.generation)
            if op.phase == "preparing":
                latest = _result(stream, op, episode, original)
                maintenance = (latest or {}).get("maintenance", {})
                if maintenance.get("phase") != "ready" or maintenance.get("expectedGeneration") != op.result["forkGeneration"]:
                    raise StreamsError("Owned maintenance preparation remains unconfirmed")
                generation, enabled = maintenance.get("generation"), True
            token, allowed = piweb.automatic_admission(fork.status, op.result["forkSessionId"], op.cwd, "recovery")
            if token["generation"] != generation or allowed != enabled:
                raise StreamsError("Newer fork stop/input superseded legacy continuation")
            drive.request_resume(stream, op.session, legacy=legacy)
            return [advance_locked(stream, op.session, op.episode, at, index=index, project=project)]
        except (StreamsError, OSError) as exc:
            return [{"session": legacy.session, "state": "pending", "detail": str(exc)}]
    results = []
    processed = set()
    rows = sorted(load_threads(stream / "threads.tsv"), key=lambda row: row.role != "coordinator")
    data = artifacts._read_tick_data(stream)
    operations = [load(stream, sid) for sid in data.get("failure_recoveries", {})]
    if not explicit and legacy is None:
        for sid in dict.fromkeys([*data.get("failure_recoveries", {}), *data.get("failures", {})]):
            row = next((row for row in rows if row.session == sid), None)
            op, episode = load(stream, sid), failure.load(stream, sid)
            retiring = op is not None and op.phase in {"retiring", "retired", "clearing"}
            if row is None or not retiring and (row.status in {Status.done, Status.archived} or terminal_sessions.load(stream, sid, row.worktree) is not None):
                continue
            if op is not None and op.phase == "complete" or episode is None or episode.state != "parked" or episode.kind in {"usage-limit", "content-policy"} or episode.checkpoint is None or episode.authority is None and op is None:
                continue
            processed.add(sid)
            try:
                results.append(advance_locked(stream, sid, episode.id, at, index=index, project=project))
            except (StreamsError, OSError) as exc:
                results.append({"session": sid, "state": "pending", "detail": str(exc)})
    if not explicit and legacy is None and not drive.load(stream).enabled:
        return results
    for row in rows:
        if row.session in processed or row.status not in {Status.active, Status.waiting_quota, Status.parked} or legacy is not None and (row.session != legacy.session or row.worktree != legacy.cwd):
            continue
        if any(op is not None and op.fork == row.session and op.phase != "complete" for op in operations):
            continue
        try:
            terminal = terminal_sessions.load(stream, row.session, row.worktree)
            if terminal is not None:
                results.append({"session": row.session, "state": "terminal-preserved", "detail": terminal["state"]})
                continue
            if row.role == "coordinator" and load(stream, row.session) is None and designated_coordinator(load_threads(stream / "threads.tsv")) != row:
                raise StreamsError(f"{'Explicit' if explicit else 'Automatic'} resume preserves the designated coordinator")
            native = _native_session(row.session, Path(row.worktree))
            if legacy is not None:
                record = drive.load(stream)
                token, allowed = piweb.automatic_admission(native.status, row.session, row.worktree, "recovery")
                if record.enabled or record.stop_intent is not None or record.remote_state != "off-confirmed" or record.run_id != legacy.run_id or record.remote_generation != legacy.generation or allowed or token["generation"] != legacy.generation:
                    raise StreamsError("Newer stop/input superseded exact legacy resume proof")
                piweb.require_settings(native.status, row.model, row.thinking)
            piweb.register_stream_failure(row.session, row.worktree, stream, native.status)
            episode = failure.observe(stream, row.session, row.worktree, native.info, native.status, at, row.model, row.thinking)
            if episode is not None and episode.kind == "content-policy":
                results.append({"session": row.session, "state": "policy-blocked", "detail": failure.POLICY_BLOCKER})
                continue
            if episode is None or episode.state != "parked":
                if explicit and not drive.load(stream).enabled and row.role == "coordinator":
                    piweb.require_settings(native.status, row.model, row.thinking)
                    drive.enable(stream, Coordinator(row, native))
                continue
            if explicit or legacy is not None:
                branch = _branch(native, row.session, row.worktree)
                failed = next((i for i, (entry, _) in enumerate(branch) if entry["id"] == episode.failure_entry), None)
                if failed is None or any(entry.get("message", {}).get("role") == "user" for entry, _ in branch[failed+1:]) or episode.uncertain_jobs or legacy is not None and episode.cancelled:
                    raise StreamsError("Parked resume preserves newer input, cancellation and unresolved external effects")
                operation = load(stream, row.session)
                if operation is None:
                    token, allowed = piweb.automatic_admission(native.status, row.session, row.worktree, "recovery")
                    if allowed or legacy is not None and token["generation"] != legacy.generation:
                        raise StreamsError("Parked resume requires the exact disabled original admission")
                    if episode.kind != "usage-limit" and native.status.get("failureBoundary", {}).get("parking") != {"generation": token["generation"], "owned": True}:
                        piweb.require_settings(native.status, row.model, row.thinking)
                        piweb.resume_failure(row.session, row.worktree, {**native.status["failureBoundary"], "generation": token["generation"]})
                        native = _native_session(row.session, Path(row.worktree))
                        episode.authority, episode.continuation = None, None
                    if explicit:
                        episode.cancelled = False
                    if episode.kind == "usage-limit":
                        episode.pause_owned, episode.pause_generation = True, token["generation"]
                    failure.save(stream, episode)
                    episode = failure.observe(stream, row.session, row.worktree, native.info, native.status, at, row.model, row.thinking)
                    if episode.kind != "usage-limit" and episode.authority is None:
                        raise StreamsError("Parked resume has no native good-prefix recovery ownership")
                if row.role == "coordinator" or not drive.load(stream).enabled:
                    drive.request_resume(stream, row.session, legacy=legacy)
            if episode.kind == "usage-limit":
                failure.step(stream, episode, native.status, at, native.info)
                results.append({"session": row.session, "state": episode.state, "phase": episode.retry_state})
            else:
                results.append(advance_locked(stream, row.session, episode.id, at, index=index, project=project))
        except (StreamsError, OSError) as exc:
            results.append({"session": row.session, "state": "pending", "detail": str(exc)})
    return results


def advance_locked(stream: Path, sid: str, episode_id: str, at: str, *, index: Path | None = None, project=None) -> dict:
    artifacts._read_stream_state_locked(stream)
    episode = failure.load(stream, sid)
    if episode is not None and episode.kind == "content-policy":
        raise StreamsError(failure.POLICY_BLOCKER)
    saved = load(stream, sid)
    if saved is not None and saved.phase in {"retiring", "retired", "clearing", "complete"}:
        episode = failure.load(stream, sid)
        if saved.episode != episode_id or episode is None or episode.id != episode_id or episode.recovery_id != saved.id:
            raise StreamsError("Retirement does not own this exact episode")
        if saved.phase != "complete":
            if not isinstance(episode.checkpoint, dict) or not isinstance(episode.authority, dict) or episode.state not in {"parked", "recovered"}:
                raise StreamsError("Retirement proof is unavailable; original and marker remain owned")
            _retire(stream, saved, episode)
        return asdict(saved)
    if drive.is_paused(stream):
        raise StreamsError("Local off preserves recovery parking")
    episode = failure.load(stream, sid)
    rows = load_threads(stream / "threads.tsv")
    originals = [row for row in rows if row.session == sid]
    if episode is None or episode.id != episode_id or episode.kind == "usage-limit" or episode.state != "parked" or episode.checkpoint is None or len(originals) != 1:
        raise StreamsError("Recovery needs the exact parked episode, good checkpoint and registry original")
    row = originals[0]
    native = _native_session(sid, Path(episode.cwd))
    piweb.require_settings(native.status, episode.authorized_model, episode.authorized_thinking)
    failure.observe(stream, sid, episode.cwd, native.info, native.status, at, row.model, row.thinking)
    episode = failure.load(stream, sid)
    if episode.kind == "content-policy":
        raise StreamsError(failure.POLICY_BLOCKER)
    if not episode.recovery_id or episode.authority is None or native.status.get("failureForkSupport") != "engine-prefix-v1" or native.status.get("engineFailureRecoverySupport") != "enrolled-prefix-v1":
        raise StreamsError("Exact native recovery ownership is unavailable; original remains parked")
    if not piweb.recovery_readiness(sid, episode.cwd, native.status, episode.kind):
        raise StreamsError("Native same-provider readiness is not yet restored; keep this owned recovery pending")
    if episode.uncertain_jobs or episode.cancelled:
        raise StreamsError("Uncertain jobs/cancellation still own the original; no replay or replacement")
    with sessionlog.regular_reader(stream / "failures" / (sid + ".lastgood")) as marker:
        if marker.read() != (episode.checkpoint["entryId"] + "\n").encode():
            raise StreamsError("Exact good-prefix marker changed")
    entries = _branch(native, sid, episode.cwd)
    failure_at = next((i for i, (entry, _) in enumerate(entries) if entry["id"] == episode.failure_entry), None)
    if failure_at is None or any(entry.get("message", {}).get("role") == "user" for entry, _ in entries[failure_at+1:]):
        raise StreamsError("Later accepted input must be reconciled; preserve the original")
    enrolled = failure.enrolled_authority(stream, sid, episode.cwd, Path(native.info["path"]), native.status["rotationSafety"]["entryId"], native.status.get("failureBoundary"), native.status, episode.pause_generation)
    expected_continuation = None if enrolled is None else failure.policy_continuation(stream, episode, row.role) if episode.kind == "content-policy" else enrolled[1]
    if enrolled is None or enrolled[0] != episode.authority or enrolled[1]["role"] != row.role or not episode.pause_owned or episode.continuation is None or any(expected_continuation[key] != episode.continuation.get(key) for key in expected_continuation if key != "stateSha256"):
        raise StreamsError("Saved engine recovery authority or bounded assignment changed")
    op = load(stream, sid)
    starting_phase = None if op is None else op.phase
    token, allowed = piweb.automatic_admission(native.status, sid, episode.cwd, "recovery")
    expected_generation = episode.pause_generation if op is None or op.result is None else op.result["generation"]
    if op is not None and op.result is None:
        result = _result(stream, op, episode, native)
        if result is not None:
            op.result = result
            save(stream, op)
            expected_generation = result["generation"]
    if allowed or token["generation"] != expected_generation:
        raise StreamsError("Newer original stop/input superseded recovery")
    if op is None or op.phase == "fork-refused":
        from engine.replacement import _idle
        _idle(Coordinator(row, native))
        if row.status not in (Status.active, Status.waiting_quota, Status.parked):
            raise StreamsError("Original registry is not available for scoped recovery")
        if row.role == "coordinator" and designated_coordinator(rows) != row:
            raise StreamsError("Recovery preserves the designated coordinator; no second active coordinator")
        authorization = {"authority": episode.authority, "continuation": episode.continuation}
        request = {"cwd": episode.cwd, "id": episode.recovery_id, "episode": episode.id, "expected": {**native.status["failureBoundary"], "generation": token["generation"]}, **authorization}
        if op is not None and op.request != request:
            raise StreamsError("Refused recovery intent was superseded; preserve its exact journal")
        op = op or Recovery(episode.recovery_id, sid, episode.id, episode.cwd, request)
        op.phase = "fork-sending"
        save(stream, op)
        try:
            response = piweb.fork_failure(sid, op.cwd, op.request)
        except piweb.RecoveryRefused as exc:
            if exc.receipt != {"state": "refused-before-effect", "id": op.id, "intentSha256": _hash(op.request)}:
                raise StreamsError("Recovery refusal changed exact admission identity") from exc
            op.phase, op.detail = "fork-refused", str(exc)
            save(stream, op)
            raise
        native = _native_session(sid, Path(op.cwd))
        op.result = _result(stream, op, episode, native)
        if op.result != response:
            raise StreamsError("Fork response lacks its exact persisted native result")
        save(stream, op)
    if op.id != episode.recovery_id or op.episode != episode.id or op.cwd != episode.cwd:
        raise StreamsError("Recovery operation changed owning episode")
    if op.result is None:
        raise StreamsError("Fork outcome is unknown; never issue a second fork")
    if op.result["state"] != "forked":
        op.phase = "cancelled" if op.result["state"] == "cancelled" else "uncertain"
        save(stream, op)
        raise StreamsError("Native fork is cancelled or uncertain; preserve originals and markers")
    if op.phase == "fork-sending":
        op.phase = "forked"
        save(stream, op)
    if op.phase in {"forked", "binding", "bound"}:
        from engine.replacement import _idle
        _idle(Coordinator(row, native))
        fork = _verify_fork(op, native)
        piweb.require_settings(fork.status, episode.authorized_model, episode.authorized_thinking)
        _held, enabled = piweb.automatic_admission(fork.status, op.result["forkSessionId"], op.cwd, "recovery")
        if enabled:
            raise StreamsError("Returned fork is no longer held disabled")
        fresh, live = piweb.automatic_admission(piweb.session_status(sid), sid, op.cwd, "recovery")
        if live or fresh["generation"] != op.result["generation"]:
            raise StreamsError("Newer stop/input superseded verified fork binding")
    if op.phase == "forked":
        if row.role == "coordinator" and designated_coordinator(rows) != row:
            raise StreamsError("Recovery binding preserves the designated coordinator")
        op.fork, op.fork_file = op.result["forkSessionId"], op.result["forkFile"]
        if any(item.session == op.fork for item in rows):
            raise StreamsError("Returned SID already has a registry owner")
        op.registry_before = dump_threads(rows)
        op.registry_after = dump_threads([replace(item, status=Status.parked) if item.session == sid else item for item in rows] + [replace(row, session=op.fork, status=Status.active)])
        op.phase = "binding"
        save(stream, op)
    if op.phase == "binding":
        with sessionlog.regular_reader(stream / "threads.tsv") as source:
            current = source.read().decode()
        if current not in (op.registry_before, op.registry_after):
            raise StreamsError("Registry changed during recovery binding; preserve foreign rows")
        if current != op.registry_after:
            _write(stream / "threads.tsv", op.registry_after)
        op.phase = "bound"
        save(stream, op)
    if op.phase in {"preparing", "dcr", "observed"} or op.phase == "bound" and starting_phase == "bound":
        if index is None or project is None:
            raise StreamsError("Recovery DCR requires its exact registered project/index")
        _advance_dcr(stream, op, episode, row, native, index, project)
    if op.phase == "observed" and starting_phase == "observed":
        if native.status.get("failureRetirementSupport") != "singular-original-v1":
            raise StreamsError("Verified singular-original retirement capability is unavailable")
        _unresolved(stream, op, episode)
        with sessionlog.regular_reader(Path(native.info["path"])) as source:
            op.source_sha256 = hashlib.sha256(source.read()).hexdigest()
        op.source_leaf = native.status["rotationSafety"]["entryId"]
        op.retirement_request = {"id": op.id, "forkSessionId": op.fork}
        op.phase = "retiring"
        save(stream, op)
        _retire(stream, op, episode)
    return asdict(op)


def _past_control_owner(stream: Path, op: Recovery, episode: failure.Episode, item: dict) -> bool:
    automatic, control = item.get("automatic", {}), item.get("control", {})
    if (item.get("origin") != "drive" or item.get("state") != "transport_accepted" or control.get("state") != "sending"
            or automatic.get("sessionId") != op.session or automatic.get("cwd") != op.cwd or op.result is None):
        return False
    data = artifacts._read_tick_data(stream)
    proofs = data.get("recovery_control_ownership", {})
    if not isinstance(proofs, dict) or not isinstance(proofs.get(op.id, {}), dict):
        raise StreamsError("Recovery control ownership evidence is malformed")
    proof = proofs.get(op.id, {}).get(item["id"])
    generation = op.result["generation"]
    if isinstance(proof, dict) and op.source_sha256 and proof.get("original_sha256") == op.source_sha256 and proof.get("generation") == generation and proof.get("old_automatic") == automatic:
        receiver = proof.get("receiver", {})
        if isinstance(receiver, dict) and receiver.get("state") == "ended" and receiver.get("id") != item["id"] and receiver.get("automaticAdmission", {}).get("generation") != automatic.get("generation"):
            delivery._control_receipt(delivery._get(stream, receiver["id"]), receiver)
            return True
    native = _native_session(op.session, Path(op.cwd))
    status, safety = native.status, native.status.get("rotationSafety", {})
    token, allowed = piweb.automatic_admission(status, op.session, op.cwd, "recovery")
    piweb.require_settings(status, episode.authorized_model, episode.authorized_thinking)
    if (allowed or token["generation"] != generation or automatic.get("generation") == generation
            or any(status.get(key) for key in ("isStreaming", "isCompacting", "isBashRunning", "pendingMessageCount", "pendingAsk", "pendingDialogs"))
            or not safety.get("callbacksKnown") or safety.get("nativeChildCallbacks") or safety.get("unprovenCallbacks")
            or any(owner.get("kind") not in {"none", "safe-to-drop"} or owner.get("owners") for owner in safety.get("callbackOwners", []))):
        return False
    candidates = [row for row in delivery.receipts(stream) if row["session"] == op.session and row.get("origin") == "drive" and row.get("control", {}).get("state") == "ended"]
    candidates.sort(key=lambda row: row["control"]["sequence"], reverse=True)
    for candidate in candidates:
        try:
            receiver = piweb.control_goal_status(op.session, op.cwd, candidate["id"])
            delivery._control_receipt(delivery._get(stream, candidate["id"]), receiver)
        except (StreamsError, OSError):
            continue
        if receiver.get("state") != "ended" or receiver.get("id") == item["id"] or receiver.get("automaticAdmission", {}).get("generation") == automatic.get("generation"):
            continue
        with sessionlog.regular_reader(Path(native.info["path"])) as source:
            original_sha256 = hashlib.sha256(source.read()).hexdigest()
        proof = {"version": 1, "generation": generation, "old_automatic": automatic, "receiver": receiver,
                 "original_sha256": original_sha256, "original_leaf": safety.get("entryId"),
                 "scope": "Historical control no longer owns input; application outcome and original delivery are unchanged."}
        data.setdefault("recovery_control_ownership", {}).setdefault(op.id, {})[item["id"]] = proof
        artifacts._save_tick_data(stream, data)
        return True
    return False


def _unresolved(stream: Path, op: Recovery, episode: failure.Episode) -> None:
    if drive.is_paused(stream) or episode.cancelled or episode.uncertain_jobs:
        raise StreamsError("Newer local stop, cancellation or uncertain jobs preserve the failure marker")
    for item in delivery.receipts(stream):
        if item["session"] != op.session or item["state"] != "prepared" or item.get("origin") != "drive" or item.get("control", {}).get("state") != "prepared" or item.get("automatic", {}).get("cwd") != op.cwd or item["automatic"].get("sessionId") != op.session:
            continue
        unsent = delivery._get(stream, item["id"])
        unsent.state, unsent.control.state = "blocked", "superseded"
        unsent.detail = f"Prepared original drive intent was never admitted; superseded by verified recovery {op.id}. Exact original body is retained without transport."
        delivery._save(stream, unsent)
    for item in delivery.receipts(stream):
        if item["session"] != op.session or item["state"] in {"applied", "blocked"}:
            continue
        automatic, control = item.get("automatic", {}), item.get("control", {})
        terminal = (item.get("origin") == "drive" and item["state"] in {"transport_accepted", "consumed"}
                    and control.get("state") in {"ended", "superseded"}
                    and automatic.get("sessionId") == op.session and automatic.get("cwd") == op.cwd)
        if not terminal and not _past_control_owner(stream, op, episode, item):
            raise StreamsError("An unresolved original delivery still owns its evidence/input")
    rows = load_threads(stream / "threads.tsv")
    old = [row for row in rows if row.session == op.session]
    forks = [row for row in rows if row.session == op.fork]
    if len(old) != 1 or len(forks) != 1 or old[0].status not in {Status.parked, Status.archived} or forks[0] != replace(old[0], session=op.fork, status=Status.active):
        raise StreamsError("Retirement registry no longer names the exact original and returned fork")
    expected = [line for line in op.registry_after.splitlines()[1:] if line.split("\t")[0] in {op.session, op.fork}]
    actual = dump_threads([replace(old[0], status=Status.parked), forks[0]]).splitlines()[1:]
    if actual != expected:
        raise StreamsError("Retirement original/fork registry fields changed")


def _owned_deletion(op: Recovery, receipt: dict, digest: str) -> bool:
    archive, deleted = receipt.get("archive"), receipt.get("deleted")
    if not isinstance(archive, dict) or archive.get("sessionId") != op.session or archive.get("cwd") != op.cwd or archive.get("originalPath") != receipt["originalFile"] or not isinstance(deleted, dict):
        return False
    expected = {"sessionId": op.session, "archivePath": archive.get("archivePath"), "sourceSha256": digest}
    if deleted == expected:
        return True
    identity = hashlib.sha256(json.dumps([op.cwd, op.session, op.fork, op.id], ensure_ascii=False, separators=(",", ":")).encode()).hexdigest()
    journal = deleted.get("journalFile")
    if not isinstance(journal, str) or not Path(journal).is_absolute() or not Path(journal).name.endswith(f".recovery-{identity}.json") or not isinstance(archive.get("archivePath"), str):
        return False
    extended = {**expected, "protocol": "intent-quarantine-v1", "completionId": identity, "journalFile": journal,
                "originalQuarantine": str(Path(receipt["originalFile"]).parent / f".recovery-{identity}.original-retired"),
                "archiveQuarantine": f"{archive['archivePath']}.recovery-{identity}.deleted"}
    return deleted == extended


def _retirement_cache(op: Recovery, episode: failure.Episode, receipt: dict) -> dict:
    if receipt.get("version") != 1 or receipt.get("id") != op.id or receipt.get("state") != "released" or receipt.get("originalSessionId") != op.session or receipt.get("forkSessionId") != op.fork or receipt.get("cwd") != op.cwd or receipt.get("originalFile") != episode.checkpoint["nativeFile"] or receipt.get("originalLeaf") != op.source_leaf or receipt.get("observation") != op.observation:
        raise StreamsError("Retirement receipt changed its exact target or RESUME proof")
    operation = receipt.get("operation")
    if not isinstance(operation, dict) or {key: value for key, value in operation.items() if key != "maintenance"} != op.result or not isinstance(operation.get("maintenance"), dict) or operation["maintenance"].get("generation") != op.generation:
        raise StreamsError("Retirement receipt changed its frozen native fork/epoch")
    cache_file = receipt.get("cacheFile")
    if not isinstance(cache_file, str) or not Path(cache_file).is_absolute():
        raise StreamsError("Retirement lacks its exact retained native evidence cache")
    try:
        with sessionlog.regular_reader(Path(cache_file)) as source:
            cache = json.load(source)
    except (ValueError, UnicodeError) as exc:
        raise StreamsError("Retained native evidence cache is malformed") from exc
    if not isinstance(cache, dict) or cache.get("version") != 1 or cache.get("sessionId") != op.fork or cache.get("cwd") != op.cwd or not isinstance(cache.get("operations"), dict):
        raise StreamsError("Retained native evidence cache owner changed")
    native = cache["operations"].get(op.id)
    kept = native.get("retirement") if isinstance(native, dict) else None
    if not isinstance(kept, dict) or {key: value for key, value in kept.items() if key != "sourceBase64"} != receipt:
        raise StreamsError("Retirement lacks its exact independently read durable receipt")
    try:
        raw = base64.b64decode(kept["sourceBase64"], validate=True)
        digest = hashlib.sha256(raw).hexdigest()
        lines = raw.splitlines(keepends=True)
        header = json.loads(lines[0])
        if not isinstance(header, dict):
            raise ValueError("invalid cached native header")
        records = {}
        for line in lines[1:]:
            if not line.strip():
                continue
            entry = json.loads(line)
            if not isinstance(entry, dict) or not isinstance(entry.get("id"), str) or entry["id"] in records:
                raise ValueError("ambiguous cached native entries")
            records[entry["id"]] = hashlib.sha256(line).hexdigest()
    except (ValueError, KeyError, TypeError, IndexError) as exc:
        raise StreamsError(f"Retained native source is malformed: {exc}") from exc
    if digest != op.source_sha256 or digest != receipt.get("sourceSha256") or header.get("type") != "session" or header.get("id") != op.session or header.get("cwd") != op.cwd:
        raise StreamsError("Retained original source hash or identity changed")
    evidence = [(episode.failure_entry, episode.failure_sha256), (episode.checkpoint["entryId"], episode.checkpoint["sha256"])]
    if episode.authority is not None and receipt["operation"].get("authority") != episode.authority:
        raise StreamsError("Retained engine recovery authority changed")
    if op.receipt is not None:
        evidence.append((op.receipt["entryId"], op.receipt["sha256"]))
    if any(records.get(identity) != digest for identity, digest in evidence):
        raise StreamsError("Required original entry/hash evidence is not retained exactly")
    if not _owned_deletion(op, receipt, digest):
        raise StreamsError("No exact owned singular-original deletion receipt")
    return native


def _released(stream: Path, op: Recovery, episode: failure.Episode, native: dict) -> None:
    fork = _native_session(op.fork, Path(op.cwd))
    if fork.info.get("path") != op.fork_file:
        raise StreamsError("Released fork file identity changed")
    piweb.require_settings(fork.status, episode.authorized_model, episode.authorized_thinking)
    token, allowed = piweb.automatic_admission(fork.status, op.fork, op.cwd, "wake")
    if not allowed or token["generation"] != op.generation:
        raise StreamsError("Newer fork stop/input preserves the marker after native retirement")
    boundary = fork.status.get("failureBoundary")
    if not isinstance(boundary, dict) or boundary.get("state") != "watching" or boundary.get("recovery") != {"id": op.id, "originalSessionId": op.session}:
        raise StreamsError("Returned fork has no verified durable release")
    release = op.retirement.get("release")
    if not isinstance(release, dict):
        raise StreamsError("Retirement has no exact native release entry/hash")
    record = json.loads(sessionlog.read_record(Path(op.fork_file), op.fork, release["entryId"], release["sha256"]).raw)
    expected = {"version": 1, "sessionId": op.fork, "cwd": op.cwd, "root": str(stream.resolve()), "stream": stream.name, "state": "watching", "recovery": {"id": op.id, "originalSessionId": op.session}}
    if record.get("customType") != "pi-web.stream-failure" or any(record.get("data", {}).get(key) != value for key, value in expected.items()) or not any(entry["id"] == release["entryId"] for entry, _raw in _branch(fork, op.fork, op.cwd)):
        raise StreamsError("Native release proof is not on the exact current fork branch")
    current = dcr.load(stream, op.fork)
    if current is None or current.id != op.id or current.phase != "complete" or current.recovery_original != op.session:
        raise StreamsError("Retirement no longer owns its completed shared DCR")
    observed = sessionlog.resume_observation(Path(op.fork_file), op.fork, op.cwd, fork.status.get("rotationSafety", {}).get("entryId"), op.id, op.generation, current.compaction_entry, current.compaction_sha256, current.resume_text, current.resume_goal, native)
    if observed != op.observation:
        raise StreamsError("Retirement's completed RESUME evidence changed")
    from engine.replacement import _idle
    _idle(Coordinator(next(row for row in load_threads(stream / "threads.tsv") if row.session == op.fork), fork))


def _retire(stream: Path, op: Recovery, episode: failure.Episode) -> None:
    _unresolved(stream, op, episode)
    if op.retirement is None:
        if op.phase != "retiring" or op.retirement_request != {"id": op.id, "forkSessionId": op.fork}:
            raise StreamsError("Retirement has no immutable saved native request")
        receipt = piweb.retire_failure(op.session, op.cwd, op.retirement_request)
        _retirement_cache(op, episode, receipt)
        op.retirement, op.phase = receipt, "retired"
        save(stream, op)
    native = _retirement_cache(op, episode, op.retirement)
    _released(stream, op, episode, native)
    artifacts.append_log_locked(stream, episode.observed_at, "Verified original retirement", f"Retired only original {op.session} after completed same-fork DCR on {op.fork}. Exact native evidence remains cached with SHA-256 {op.retirement['sourceSha256']}. No worker or worktree was deleted.", request_id=f"failure-retired:{op.id}")
    if op.phase == "retired":
        with sessionlog.regular_reader(stream / "threads.tsv") as source:
            before = source.read().decode()
        lines = before.splitlines(keepends=True)
        changed = []
        for line in lines:
            cells = line.split("\t")
            if cells[0] == op.session:
                if len(cells) != 10 or cells[8] not in {"parked", "archived"}:
                    raise StreamsError("Original registry disposition changed")
                cells[8] = "archived"
                line = "\t".join(cells)
            changed.append(line)
        op.cleanup_before, op.cleanup_after, op.phase = before, "".join(changed), "clearing"
        save(stream, op)
    with sessionlog.regular_reader(stream / "threads.tsv") as source:
        current = source.read().decode()
    if current not in {op.cleanup_before, op.cleanup_after}:
        raise StreamsError("Registry changed during exact retirement cleanup; foreign rows preserved")
    if current != op.cleanup_after:
        _write(stream / "threads.tsv", op.cleanup_after)
    directory = stream / "failures"
    if directory.is_symlink() or not directory.is_dir():
        raise StreamsError("Failure marker directory is no longer owned")
    marker = directory / (op.session + ".lastgood")
    try:
        marker.lstat()
    except FileNotFoundError:
        pass
    else:
        expected_marker = (episode.checkpoint["entryId"] + "\n").encode()
        with sessionlog.regular_reader(marker) as source:
            if source.read() != expected_marker:
                raise StreamsError("Foreign/changed failure marker was preserved")
            owned_marker = os.fstat(source.fileno())
        owned_directory = directory.lstat()
        _unresolved(stream, op, failure.load(stream, op.session))
        token, allowed = piweb.automatic_admission(piweb.session_status(op.fork), op.fork, op.cwd, "wake")
        if not allowed or token["generation"] != op.generation:
            raise StreamsError("Newer fork stop/input superseded marker cleanup")
        current_directory = directory.lstat()
        if directory.is_symlink() or not directory.is_dir() or current_directory.st_dev != owned_directory.st_dev or current_directory.st_ino != owned_directory.st_ino:
            raise StreamsError("Failure marker directory changed during final receiving check")
        with sessionlog.regular_reader(marker) as source:
            current_marker = os.fstat(source.fileno())
            if any(getattr(current_marker, key) != getattr(owned_marker, key) for key in ("st_dev", "st_ino", "st_mode", "st_size", "st_mtime_ns", "st_ctime_ns")) or source.read() != expected_marker:
                raise StreamsError("Changed marker identity/bytes after final receiving check were preserved")
        marker.unlink()
        fd = os.open(directory, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(fd)
        finally:
            os.close(fd)
    op.phase, episode.state = "complete", "recovered"
    data = artifacts._read_tick_data(stream)
    data["failure_recoveries"][op.session] = asdict(op)
    data["failures"][op.session] = episode.public()
    artifacts._save_tick_data(stream, data)
    drive.confirm_resume(stream, op.session, op.fork, op.cwd, op.generation)


def resolve_fork(stream: Path, op: Recovery) -> Coordinator:
    rows = [row for row in load_threads(stream / "threads.tsv") if row.session == op.fork]
    original = [row for row in load_threads(stream / "threads.tsv") if row.session == op.session]
    if len(rows) != 1 or len(original) != 1 or rows[0] != replace(original[0], session=op.fork, status=Status.active):
        raise StreamsError("Recovery fork registry identity changed")
    native = _native_session(op.fork, Path(op.cwd))
    if native.info.get("path") != op.fork_file:
        raise StreamsError("Recovery fork native file changed")
    boundary = native.status.get("failureBoundary")
    if not isinstance(boundary, dict) or boundary.get("state") != "recovering" or boundary.get("recovery") != {"id": op.id, "originalSessionId": op.session}:
        raise StreamsError("Recovery fork runtime is no longer held by this operation")
    return Coordinator(rows[0], native)


def _advance_dcr(stream: Path, op: Recovery, episode: failure.Episode, row, original, index, project) -> None:
    from engine.replacement import _idle
    _idle(Coordinator(row, original))
    fork = resolve_fork(stream, op)
    piweb.require_settings(fork.native.status, episode.authorized_model, episode.authorized_thinking)
    if original.status.get("failureMaintenanceSupport") != "operation-scoped-v1":
        raise StreamsError("Operation-scoped recovery maintenance capability is unavailable")
    if op.phase == "bound":
        if not isinstance(op.result.get("forkGeneration"), str):
            raise StreamsError("Historical fork has no receiving-owned held generation; preserve parking")
        token, allowed = piweb.automatic_admission(fork.native.status, op.fork, op.cwd, "wake")
        if allowed or token["generation"] != op.result["forkGeneration"]:
            raise StreamsError("Newer fork stop/input superseded initial preparation")
        op.phase = "preparing"
        save(stream, op)
        piweb.failure_maintenance(op.session, op.cwd, {"id": op.id, "action": "prepare", "expectedForkGeneration": op.result["forkGeneration"]})
    latest = _result(stream, op, episode, _native_session(op.session, Path(op.cwd)))
    if latest is None or {key: value for key, value in latest.items() if key != "maintenance"} != op.result:
        raise StreamsError("Native maintenance changed its frozen exact fork result")
    maintenance = latest.get("maintenance")
    if not isinstance(maintenance, dict) or maintenance.get("id") != op.id or maintenance.get("phase") != "ready" or maintenance.get("expectedGeneration") != op.result["forkGeneration"] or not isinstance(maintenance.get("generation"), str):
        raise StreamsError("Held-fork preparation remains uncertain; do not rearm or resend")
    fork = resolve_fork(stream, op)
    token, allowed = piweb.automatic_admission(fork.native.status, op.fork, op.cwd, "wake")
    if not allowed or token["generation"] != maintenance["generation"]:
        raise StreamsError("Newer fork stop/input superseded DCR")
    if op.phase == "preparing":
        op.generation, op.phase = token["generation"], "dcr"
        save(stream, op)
    if op.generation != token["generation"]:
        raise StreamsError("Saved recovery DCR generation changed")
    continuation = episode.continuation
    if continuation is None and row.role != "coordinator":
        continuation = {"role": row.role, "assignment": f"Retain this worker's bounded role. The exact saved input is {episode.saved_entry} SHA-256 {episode.saved_sha256} in original {op.session}. Read that evidence and existing handovers before task effects. If assignment scope cannot be established, park for coordinator reassignment."}
    current = dcr.prepare(index, stream.name, stream, fork, op.id, token, original=op.session, continuation=continuation)
    if op.phase == "dcr":
        dcr.step(index, project, stream.name, stream, fork)
        current = dcr.load(stream, op.fork)
        if current.phase == "complete" and current.observation is not None:
            op.observation, op.phase = current.observation, "observed"
            save(stream, op)

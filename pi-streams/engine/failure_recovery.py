from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from engine import StreamsError, artifacts, dcr, drive, failure, piweb, sessionlog
from engine.project import _write
from engine.threads import Coordinator, Status, _native_session, dump_threads, load_threads, require_ratified


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


def load(stream: Path, sid: str) -> Recovery | None:
    data = artifacts._read_tick_data(stream).get("failure_recoveries", {})
    if not isinstance(data, dict):
        raise StreamsError("Recovery records are malformed")
    value = data.get(sid)
    if value is None:
        return None
    try:
        op = Recovery(**value)
        if op.session != sid or not op.id or not Path(op.cwd).is_absolute() or op.phase not in {"fork-sending", "forked", "binding", "bound", "preparing", "dcr", "observed", "cancelled", "uncertain"} or not isinstance(op.request, dict):
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
    notice = episode.ratification
    expected = {"version": 1, "id": op.id, "episode": op.episode, "originalSessionId": op.session, "cwd": op.cwd, "root": str(stream.resolve()), "stream": stream.name, "checkpoint": op.request["expected"]["checkpoint"], "failure": op.request["expected"]["failure"], "intentSha256": _hash(op.request), "noticeId": notice["noticeId"], "provenance": notice["provenance"], "instructions": notice["instructions"]}
    if any(result.get(key) != value for key, value in expected.items()) or result.get("state") not in {"fork-sending", "forked", "cancelled", "uncertain"} or not isinstance(result.get("generation"), str):
        raise StreamsError("Native fork result changed exact request/notice/target evidence")
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


def advance_locked(stream: Path, sid: str, episode_id: str, at: str, *, index: Path | None = None, project=None) -> dict:
    require_ratified(stream)
    if drive.is_paused(stream):
        raise StreamsError("Local off preserves recovery parking")
    episode = failure.load(stream, sid)
    rows = load_threads(stream / "threads.tsv")
    originals = [row for row in rows if row.session == sid]
    if episode is None or episode.id != episode_id or episode.kind == "usage-limit" or episode.state != "parked" or episode.ratification is None or episode.checkpoint is None or len(originals) != 1 or not episode.recovery_id:
        raise StreamsError("Recovery needs the exact ratified parked episode and registry original")
    row = originals[0]
    native = _native_session(sid, Path(episode.cwd))
    piweb.require_settings(native.status, episode.authorized_model, episode.authorized_thinking)
    if native.status.get("failureRatificationConfigured") is not True or native.status.get("failureForkSupport") != "ratified-prefix-v1":
        raise StreamsError("Authenticated exact fork intake is unavailable; original remains parked")
    failure.observe(stream, sid, episode.cwd, native.info, native.status, at, row.model, row.thinking)
    episode = failure.load(stream, sid)
    if episode.uncertain_jobs or episode.cancelled:
        raise StreamsError("Uncertain jobs/cancellation still own the original; no replay or replacement")
    with sessionlog.regular_reader(stream / "failures" / (sid + ".lastgood")) as marker:
        if marker.read() != (episode.checkpoint["entryId"] + "\n").encode():
            raise StreamsError("Exact good-prefix marker changed")
    entries = _branch(native, sid, episode.cwd)
    failure_at = next((i for i, (entry, _) in enumerate(entries) if entry["id"] == episode.failure_entry), None)
    if failure_at is None or any(entry.get("message", {}).get("role") == "user" for entry, _ in entries[failure_at+1:]):
        raise StreamsError("Later accepted input must be reconciled; preserve the original")
    proof = episode.ratification
    record = json.loads(sessionlog.read_record(Path(native.info["path"]), sid, proof["entryId"], proof["sha256"]).raw)
    if record.get("customType") != "pi-web.failure-ratification" or any(record.get("data", {}).get(key) != proof[key] for key in ("version", "id", "noticeId", "provenance", "instructions", "generation", "target")) or not any(entry["id"] == proof["entryId"] for entry, _ in entries):
        raise StreamsError("Ratification receipt is not on the current original branch")
    op = load(stream, sid)
    starting_phase = None if op is None else op.phase
    token, allowed = piweb.automatic_admission(native.status, sid, episode.cwd, "recovery")
    expected_generation = proof["generation"] if op is None or op.result is None else op.result["generation"]
    if op is not None and op.result is None:
        result = _result(stream, op, episode, native)
        if result is not None:
            op.result = result
            save(stream, op)
            expected_generation = result["generation"]
    if allowed or token["generation"] != expected_generation:
        raise StreamsError("Newer original stop/input superseded recovery")
    if op is None:
        from engine.replacement import _idle
        _idle(Coordinator(row, native))
        if row.status not in (Status.active, Status.waiting_quota):
            raise StreamsError("Original registry is not available for scoped recovery")
        op = Recovery(episode.recovery_id, sid, episode.id, episode.cwd, {"cwd": episode.cwd, "id": episode.recovery_id, "episode": episode.id, "expected": {**native.status["failureBoundary"], "generation": token["generation"]}, "ratification": {key: proof[key] for key in ("entryId", "sha256")}})
        save(stream, op)
        response = piweb.fork_failure(sid, op.cwd, op.request)
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
    return asdict(op)


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
    current = dcr.prepare(index, stream.name, stream, fork, op.id, token, original=op.session, instructions=op.result["instructions"])
    if op.phase == "dcr":
        dcr.step(index, project, stream.name, stream, fork)
        current = dcr.load(stream, op.fork)
        if current.phase == "complete" and current.observation is not None:
            op.observation, op.phase = current.observation, "observed"
            save(stream, op)

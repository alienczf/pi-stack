from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from engine import StreamsError, artifacts, dcr, delivery, drive, failure, piweb, sessionlog
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
        if op.session != sid or not op.id or not Path(op.cwd).is_absolute() or op.phase not in {"fork-sending", "forked", "binding", "bound", "preparing", "dcr", "observed", "retiring", "retired", "clearing", "complete", "cancelled", "uncertain"} or not isinstance(op.request, dict):
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
    saved = load(stream, sid)
    if saved is not None and saved.phase in {"retiring", "retired", "clearing", "complete"}:
        episode = failure.load(stream, sid)
        if saved.episode != episode_id or episode is None or episode.id != episode_id or episode.recovery_id != saved.id:
            raise StreamsError("Retirement does not own this exact episode")
        if saved.phase != "complete":
            if not isinstance(episode.checkpoint, dict) or not isinstance(episode.ratification, dict) or episode.state not in {"parked", "recovered"}:
                raise StreamsError("Retirement proof is unavailable; original and marker remain owned")
            _retire(stream, saved, episode)
        return asdict(saved)
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


def _unresolved(stream: Path, op: Recovery, episode: failure.Episode) -> None:
    if drive.is_paused(stream) or episode.cancelled or episode.uncertain_jobs:
        raise StreamsError("Newer local stop, cancellation or uncertain jobs preserve the failure marker")
    if any(item["session"] == op.session and item["state"] not in {"applied", "blocked"} for item in delivery.receipts(stream)):
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
    evidence = [(episode.failure_entry, episode.failure_sha256), (episode.checkpoint["entryId"], episode.checkpoint["sha256"]), (episode.ratification["entryId"], episode.ratification["sha256"])]
    if op.receipt is not None:
        evidence.append((op.receipt["entryId"], op.receipt["sha256"]))
    if any(records.get(identity) != digest for identity, digest in evidence):
        raise StreamsError("Required original entry/hash evidence is not retained exactly")
    archive, deleted = receipt.get("archive"), receipt.get("deleted")
    if not isinstance(archive, dict) or archive.get("sessionId") != op.session or archive.get("cwd") != op.cwd or archive.get("originalPath") != receipt["originalFile"] or not isinstance(deleted, dict) or deleted != {"sessionId": op.session, "archivePath": archive.get("archivePath"), "sourceSha256": digest}:
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
        with sessionlog.regular_reader(marker) as source:
            if source.read() != (episode.checkpoint["entryId"] + "\n").encode():
                raise StreamsError("Foreign/changed failure marker was preserved")
        _unresolved(stream, op, failure.load(stream, op.session))
        token, allowed = piweb.automatic_admission(piweb.session_status(op.fork), op.fork, op.cwd, "wake")
        if not allowed or token["generation"] != op.generation:
            raise StreamsError("Newer fork stop/input superseded marker cleanup")
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

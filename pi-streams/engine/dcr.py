from __future__ import annotations

import base64
import hashlib
import json
import shlex
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine import StreamsError, artifacts, piweb, sessionlog
from engine.project import Project, STATE_SCHEMA, load_stream_config
from engine.threads import Coordinator, require_ratified

THRESHOLD = 150000
COMPACT_INSTRUCTIONS = (
    "Preserve the synced STATE Goals, active Rules, exact artifact references, completed work and failures. "
    "Retain pending ordered human input and uncertain external jobs without retrying them. "
    "Do not invent a RESUME prompt, continuation budget, task ledger or environment remedy."
)
TERMINAL = frozenset({"complete", "superseded", "blocked"})
PHASES = TERMINAL | {"sync-prepared", "sync-sending", "sync-admitted", "compact-sending", "compacting", "resume-sending", "resuming"}


@dataclass
class Operation:
    id: str
    session: str
    cwd: str
    automatic: dict[str, str]
    sync_text: str
    compact_instructions: str = COMPACT_INSTRUCTIONS
    phase: str = "sync-prepared"
    ready_revision: str = ""
    ready_source: str = ""
    ready_entries: list[dict] = field(default_factory=list)
    checkpoint_entry: str = ""
    checkpoint_sha256: str = ""
    compaction_entry: str = ""
    compaction_sha256: str = ""
    resume_text: str = ""
    resume_goal: str = ""
    completed_leaf: str = ""
    detail: str = ""
    recovery_original: str = ""
    recovery_instructions: str = ""
    observation: dict | None = None


def load(stream_dir: Path, sid: str) -> Operation | None:
    records = artifacts._read_tick_data(stream_dir).get("dcr_operations", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid saved DCR operations")
    value = records.get(sid)
    if value is None:
        return None
    try:
        op = Operation(**value)
        if op.session != sid or op.phase not in PHASES or not op.id or not Path(op.cwd).is_absolute() or op.automatic.get("sessionId") != sid or op.automatic.get("cwd") != op.cwd or op.automatic.get("kind") != "wake":
            raise ValueError("mismatched DCR owner or phase")
        return op
    except (TypeError, ValueError, AttributeError) as exc:
        raise StreamsError(f"invalid saved DCR operation: {exc}") from exc


def save(stream_dir: Path, op: Operation) -> None:
    data = artifacts._read_tick_data(stream_dir)
    records = data.setdefault("dcr_operations", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid saved DCR operations")
    records[op.session] = asdict(op)
    artifacts._save_tick_data(stream_dir, data)


def receipts(stream_dir: Path) -> list[dict]:
    records = artifacts._read_tick_data(stream_dir).get("dcr_operations", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid saved DCR operations")
    result = []
    for sid in records:
        op = load(stream_dir, sid)
        result.append({"id": op.id, "session": op.session, "phase": op.phase, "detail": op.detail, "compactionEntry": op.compaction_entry})
    return result


def resume_text(stream_dir: Path, goal: str) -> str:
    return (
        "Read the current stream artifacts before acting:\n"
        f"- {stream_dir}/AGENTS.md\n"
        f"- {stream_dir}/STATE.md\n"
        "Resolve the current objective in STATE Goals, falling back to its North Star.\n"
        "Open history/, context/ and its README index, checks/, or handover/ only on demand.\n"
        "Historical entries do not override current Goals or Rules.\n"
        "Do not self-remedy environment/auth/resource failures or write new rules, skills,\n"
        "or memory because of them. Park and append a Log entry via the engine;\n"
        "the human repairs them.\n"
        f"/poteto-mode {goal}"
    )


def ready(stream_dir: Path, index: Path, stream: str, resolved: Coordinator, identity: str) -> dict:
    op = load(stream_dir, resolved.row.session)
    if op is None or op.id != identity or op.phase not in {"sync-sending", "sync-admitted"}:
        raise StreamsError("SYNC ready does not match the current owned DCR operation")
    token, allowed = piweb.automatic_admission(resolved.native.status, op.session, op.cwd, "wake")
    if not allowed or token != op.automatic:
        raise StreamsError("SYNC was superseded by newer input or stop")
    state = artifacts._read_stream_state_locked(stream_dir)
    require_ratified(stream_dir)
    revision = hashlib.sha256(state.source).hexdigest()
    if op.ready_revision and op.ready_revision != revision:
        raise StreamsError("SYNC ready STATE revision changed")
    op.ready_revision = revision
    op.ready_source = base64.b64encode(state.source).decode("ascii")
    book = artifacts._read_tick_data(stream_dir).get("state_log")
    op.ready_entries = [] if book is None else [asdict(entry) for entry in artifacts._book(book).entries]
    save(stream_dir, op)
    piweb.watch_dcr_events(op.session, op.cwd, op.id, index, stream, token["generation"], original=op.recovery_original)
    return {"id": op.id, "sessionId": op.session, "stateRevision": revision, "acknowledgement": f"DCR SYNC ready: {op.id} {revision}"}


def synced_state(stream_dir: Path, op: Operation) -> bool:
    before = artifacts.parse_state(base64.b64decode(op.ready_source, validate=True))
    current = artifacts._read_stream_state_locked(stream_dir)
    if before.source[:before.log.body.start] != current.source[:current.log.body.start]:
        return False
    old, new = before.source[before.log.body.start:], current.source[current.log.body.start:]
    if old == new:
        return True
    retired: list[tuple[artifacts.LogEntry, bytes]] = []
    for value in op.ready_entries:
        entry = artifacts.LogEntry(**value)
        raw = old[entry.start:entry.end]
        retired.append((entry, raw))
        if old[entry.end:] == new:
            return all((stream_dir / "history" / artifacts._history_name(item, "entry", content)).read_bytes() == content for item, content in retired)
    return False


def native_branch(resolved: Coordinator) -> list[tuple[dict, bytes]]:
    safety = resolved.native.status.get("rotationSafety")
    leaf = safety.get("entryId") if isinstance(safety, dict) else None
    path = resolved.native.info.get("path")
    if not isinstance(leaf, str) or not leaf or not isinstance(path, str):
        raise StreamsError("DCR requires the exact persisted native leaf")
    entries: dict[str, tuple[dict, bytes]] = {}
    with sessionlog.regular_reader(Path(path)) as handle:
        header = json.loads(handle.readline())
        if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != resolved.row.session or not isinstance(header.get("cwd"), str) or Path(header["cwd"]).resolve() != Path(resolved.row.worktree).resolve():
            raise StreamsError("DCR native evidence identity/cwd changed")
        for raw in handle:
            try:
                entry = json.loads(raw)
            except ValueError:
                continue
            if isinstance(entry, dict) and isinstance(entry.get("id"), str):
                if entry["id"] in entries:
                    raise StreamsError("DCR native entry identity is ambiguous")
                entries[entry["id"]] = entry, raw
    branch: list[tuple[dict, bytes]] = []
    seen: set[str] = set()
    while leaf is not None:
        if leaf in seen or leaf not in entries:
            raise StreamsError("DCR native branch is absent or cyclic")
        seen.add(leaf)
        entry, raw = entries[leaf]
        branch.append((entry, raw))
        leaf = entry.get("parentId")
        if leaf is not None and not isinstance(leaf, str):
            raise StreamsError("DCR native branch has an invalid parent identity")
    return branch


def terminal_checkpoint(resolved: Coordinator, acknowledgement: str) -> tuple[str, str] | None:
    status = resolved.native.status
    if any(status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning")) or status.get("pendingMessageCount", 0) or status.get("pendingAsk") or status.get("pendingExtensionDialogs"):
        return None
    entry, raw = native_branch(resolved)[0]
    message = entry.get("message", {})
    text = "\n".join(block.get("text", "") for block in message.get("content", []) if isinstance(block, dict) and block.get("type") == "text")
    if entry.get("type") != "message" or message.get("role") != "assistant" or message.get("stopReason") != "stop" or acknowledgement not in text.splitlines():
        raise StreamsError("DCR has no complete native SYNC acknowledgement at its exact idle leaf")
    return entry["id"], hashlib.sha256(raw).hexdigest()


def completion_after(resolved: Coordinator, compaction: str) -> str | None:
    completed = None
    for entry, _ in native_branch(resolved):
        if entry["id"] == compaction:
            return completed
        message = entry.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            if message.get("stopReason") == "error":
                raise StreamsError("Native RESUME contains an assistant error")
            if completed is None and message.get("stopReason") == "stop":
                completed = entry["id"]
    raise StreamsError("Native RESUME branch does not contain its owned compaction")


def close_events(stream_dir: Path, op: Operation) -> None:
    receipt = piweb.close_dcr_events(op.session, op.cwd, op.id, original=op.recovery_original)
    op.completed_leaf = receipt.get("entryId") or op.completed_leaf
    save(stream_dir, op)


def prepare(index: Path, stream: str, stream_dir: Path, resolved: Coordinator, identity: str, token: dict, *, original: str = "", instructions: str = "") -> Operation:
    previous = load(stream_dir, resolved.row.session)
    if previous is not None and (original or previous.phase not in {"complete", "superseded"}):
        if previous.id != identity or previous.recovery_original != original or previous.automatic != token or previous.recovery_instructions != instructions:
            raise StreamsError("Another DCR operation owns the returned fork")
        return previous
    command = shlex.join([str(Path(__file__).resolve().parents[2] / "bin/pi-streams"), "dcr", "ready", stream, "--home", str(index), "--session", resolved.row.session, "--operation", identity])
    text = (
        f"SYNC/DUMP for same-session DCR {identity}. At the next safe boundary, finish or record ongoing work. "
        f"Read {stream_dir}/AGENTS.md and {stream_dir}/STATE.md before syncing any inherited context. Synchronize Current Objective, active Rules, "
        "completed work, failures and exact artifact references through the canonical artifact commands. "
        "Do not prune or rotate Log, abort active tools, author RESUME, or retry uncertain external jobs. "
        f"Then run {command}. Make no artifact writes afterward. Finish the turn with the exact acknowledgement returned by that command."
    )
    op = Operation(identity, resolved.row.session, resolved.row.worktree, token, text, recovery_original=original, recovery_instructions=instructions)
    save(stream_dir, op)
    return op


def step(index: Path, project: Project, stream: str, stream_dir: Path, resolved: Coordinator | None) -> bool:
    if resolved is None or load_stream_config(stream_dir / "stream.toml").state_schema != STATE_SCHEMA:
        return False
    from engine.drive import is_paused

    if is_paused(stream_dir):
        return True
    sid, status = resolved.row.session, resolved.native.status
    op = load(stream_dir, sid)
    token, allowed = piweb.automatic_admission(status, sid, resolved.row.worktree, "wake")
    if op is not None and op.phase == "blocked":
        return True
    if op is not None and op.phase not in TERMINAL and (not allowed or token != op.automatic):
        if op.phase in {"compact-sending", "compacting", "resume-sending", "resuming"}:
            native = piweb.maintenance_status(op.cwd, sid, op.id, original=op.recovery_original)
            if native.get("generation") != op.automatic["generation"] or native.get("entryId") != op.checkpoint_entry:
                raise StreamsError("Changed-control DCR disposition has no matching saved checkpoint/generation")
            if native["state"] in {"failed", "uncertain"} and native.get("cancelledByStop") is not True:
                op.phase, op.detail = "blocked", f"Native DCR {native['state']}: {native.get('detail', 'unconfirmed failure')}"
                save(stream_dir, op)
                close_events(stream_dir, op)
                return True
        op.phase, op.detail = "superseded", "Newer native input or stop superseded this maintenance generation."
        save(stream_dir, op)
        close_events(stream_dir, op)
        return False
    if op is None or op.phase in {"complete", "superseded"}:
        usage = status.get("contextUsage")
        tokens = usage.get("tokens") if isinstance(usage, dict) else None
        safety = status.get("rotationSafety")
        leaf = safety.get("entryId") if isinstance(safety, dict) else None
        if not allowed or type(tokens) is not int or tokens < THRESHOLD:
            return False
        if status.get("isCompacting") is True or status.get("isBashRunning") is True or status.get("pendingAsk") or status.get("pendingExtensionDialogs"):
            return True
        if op is not None and op.completed_leaf == leaf:
            return False
        require_ratified(stream_dir)
        identity = uuid.uuid4().hex
        op = prepare(index, stream, stream_dir, resolved, identity, token)
    try:
        piweb.require_settings(status, resolved.row.model if op.recovery_original else project.coordinator.model, resolved.row.thinking if op.recovery_original else project.coordinator.thinking)
        if status.get("maintenanceSupport") != "checkpoint-input-v1" or status.get("potetoInvocationSupport") != "exact-goal-v1" or status.get("dcrEventSupport") != "phase-v1":
            op.phase, op.detail = "blocked", "Native checkpoint, exact mode and idle-event capabilities are required."
            save(stream_dir, op)
            return True
        if op.phase == "sync-prepared":
            if status.get("isCompacting") is True or status.get("isBashRunning") is True or status.get("pendingAsk") or status.get("pendingExtensionDialogs"):
                return True
            op.phase = "sync-sending"
            save(stream_dir, op)
            if op.recovery_original:
                receipt = piweb.failure_maintenance(op.recovery_original, op.cwd, {"id": op.id, "action": "sync", "deliveryId": f"{op.id}:sync", "text": op.sync_text})
                sync = receipt["operation"].get("maintenance", {}).get("sync")
                if not isinstance(sync, dict) or sync.get("text") != op.sync_text or sync.get("deliveryId") != f"{op.id}:sync" or sync.get("state") not in {"sending", "ended"}:
                    raise StreamsError("Recovery SYNC admission identity/body is unconfirmed")
            else:
                piweb.prompt(sid, op.sync_text, "steer" if status.get("isStreaming") is True else None, delivery_id=f"{op.id}:sync", automatic=op.automatic)
            op.phase = "sync-admitted"
            save(stream_dir, op)
            return True
        if op.phase in {"sync-sending", "sync-admitted"}:
            if not op.ready_revision:
                return True
            checkpoint = terminal_checkpoint(resolved, f"DCR SYNC ready: {op.id} {op.ready_revision}")
            if checkpoint is None:
                return True
            if not synced_state(stream_dir, op):
                op.phase, op.detail = "superseded", "STATE changed after SYNC; no stale checkpoint was compacted."
                save(stream_dir, op)
                close_events(stream_dir, op)
                return False
            op.checkpoint_entry, op.checkpoint_sha256 = checkpoint
            op.phase = "compact-sending"
            save(stream_dir, op)
            piweb.compact_at_checkpoint(sid, op.id, {"sessionId": sid, "cwd": op.cwd, "entryId": op.checkpoint_entry, "generation": token["generation"]}, op.compact_instructions, original=op.recovery_original)
            op.phase = "compacting"
            save(stream_dir, op)
            return True
        if op.phase in {"compact-sending", "compacting", "resume-sending", "resuming"}:
            native = piweb.maintenance_status(op.cwd, sid, op.id, original=op.recovery_original)
            if native.get("generation") != op.automatic["generation"] or native.get("entryId") != op.checkpoint_entry:
                raise StreamsError("Native DCR receipt changed its saved checkpoint/generation")
            if native["state"] in {"failed", "uncertain"}:
                raise StreamsError(f"Native DCR {native['state']}: {native.get('detail', '')}")
            if native["state"] == "superseded" or native["inputSequence"]:
                op.phase, op.detail = "superseded", "Accepted newer maintenance input is retained by the native inbox; old RESUME is invalid."
                save(stream_dir, op)
                close_events(stream_dir, op)
                return False
            if native["state"] in {"prepared", "compacting"}:
                return True
            if op.phase == "resume-sending":
                receipt = native.get("resume")
                if not isinstance(receipt, dict) or receipt.get("deliveryId") != f"{op.id}:resume" or receipt.get("text") != op.resume_text or receipt.get("potetoGoal") != op.resume_goal:
                    return True
                op.phase = "resuming"
                save(stream_dir, op)
            if op.phase == "resuming":
                if native["state"] != "resumed":
                    return True
                if op.recovery_original:
                    op.observation = sessionlog.resume_observation(Path(resolved.native.info["path"]), sid, op.cwd, status.get("rotationSafety", {}).get("entryId"), op.id, op.automatic["generation"], op.compaction_entry, op.compaction_sha256, op.resume_text, op.resume_goal, native)
                    if op.observation is None:
                        return True
                    completed = op.observation["assistantEntryId"]
                else:
                    completed = completion_after(resolved, op.compaction_entry)
                    if completed is None:
                        return True
                op.completed_leaf = completed
                op.phase = "complete"
                save(stream_dir, op)
                close_events(stream_dir, op)
                return False
            if native.get("resume") is not None:
                raise StreamsError("Native RESUME exists without this driver's saved admission intent")
            proof = piweb.compaction_result(op.cwd, sid, op.id, original=op.recovery_original)
            if proof is None:
                return True
            artifacts._rotate_log_locked(stream_dir)
            state = artifacts._read_stream_state_locked(stream_dir)
            require_ratified(stream_dir)
            op.compaction_entry, op.compaction_sha256 = proof["entryId"], proof["sha256"]
            op.resume_goal = artifacts.resolve_current_goal(state)
            op.resume_text = ("Explicitly ratified exceptional instructions:\n" + op.recovery_instructions + "\n" if op.recovery_instructions else "") + resume_text(stream_dir, op.resume_goal)
            op.phase = "resume-sending"
            save(stream_dir, op)
            piweb.resume_maintenance(sid, op.id, op.compaction_entry, 0, {**op.automatic, "kind": "resume"}, f"{op.id}:resume", op.resume_text, poteto_goal=op.resume_goal, original=op.recovery_original)
            op.phase = "resuming"
            save(stream_dir, op)
    except piweb.PromptRejected as exc:
        op.phase, op.detail = "superseded", str(exc)
        save(stream_dir, op)
        close_events(stream_dir, op)
    except (StreamsError, OSError, ValueError) as exc:
        op.detail = str(exc)
        if op.phase not in {"sync-sending", "compact-sending", "resume-sending"}:
            op.phase = "blocked"
        save(stream_dir, op)
    return op.phase not in {"complete", "superseded"}

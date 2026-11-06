from __future__ import annotations

import base64
import hashlib
import json
import re
import shlex
import uuid
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine import StreamsError, artifacts, piweb, sessionlog
from engine.project import Project, STATE_SCHEMA, load_stream_config
from engine.threads import Coordinator, NativeSession

THRESHOLD = 150000
COMPACT_INSTRUCTIONS = (
    "Preserve the synced STATE Goals, active Rules, exact artifact references, completed work and failures. "
    "Retain pending ordered human input and uncertain external jobs without retrying them. "
    "Do not invent a RESUME prompt, continuation budget, task ledger or environment remedy."
)
TERMINAL = frozenset({"complete", "superseded", "blocked", "rotated"})
PHASES = TERMINAL | {"sync-prepared", "sync-sending", "sync-admitted", "compact-sending", "compacting", "resume-sending", "resuming", "rotation-pending"}


class CapacityExceeded(StreamsError):
    pass


@dataclass(frozen=True)
class CapacityOutcome:
    operation: str
    checkpoint_entry: str
    checkpoint_sha256: str
    generation: str
    receipt: dict
    retirement: dict = field(default_factory=dict)
    kind: str = "known-capacity-v1"


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
    observation: dict | None = None
    continuation: dict | None = None
    rebuilt_tokens: int = 0
    capacity: dict | None = None


def safe_context(native: dict, status: dict) -> int:
    tokens, target = native.get("tokensAfter"), native.get("targetTokens")
    model = status.get("model", {})
    capacity = model.get("contextWindow")
    if type(capacity) is not int or capacity <= 0 or type(tokens) is not int or tokens < 0 or type(target) is not int or target <= 0:
        raise StreamsError("Native compaction has unknown same-model context capacity")
    budget = {"provider": model.get("provider"), "model": model.get("id"), "contextWindow": capacity, "targetTokens": int(capacity * 0.8)}
    if not (target == THRESHOLD and native.get("contextBudget") is None) and (native.get("contextBudget") != budget or target != budget["targetTokens"]):
        raise StreamsError("Native compaction changed the same-model safe context capacity")
    if tokens >= min(THRESHOLD, target, budget["targetTokens"]):
        raise CapacityExceeded("Native compaction did not reduce rebuilt context below 150000 tokens")
    return tokens


def load(stream_dir: Path, sid: str) -> Operation | None:
    records = artifacts._read_tick_data(stream_dir).get("dcr_operations", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid saved DCR operations")
    value = records.get(sid)
    if value is None:
        return None
    try:
        op = Operation(**{key: item for key, item in value.items() if key != "recovery_instructions"})
        if op.session != sid or op.phase not in PHASES or not op.id or not Path(op.cwd).is_absolute() or op.automatic.get("sessionId") != sid or op.automatic.get("cwd") != op.cwd or op.automatic.get("kind") != "wake" or type(op.rebuilt_tokens) is not int or op.rebuilt_tokens < 0:
            raise ValueError("mismatched DCR owner or phase")
        if op.capacity is not None:
            outcome = CapacityOutcome(**op.capacity)
            if (outcome.kind != "known-capacity-v1" or outcome.operation != op.id
                or outcome.checkpoint_entry != op.checkpoint_entry or outcome.checkpoint_sha256 != op.checkpoint_sha256
                or outcome.generation != op.automatic["generation"] or not isinstance(outcome.receipt, dict)):
                raise ValueError("invalid saved capacity outcome")
        return op
    except (TypeError, ValueError, AttributeError, KeyError) as exc:
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
        "Runtime failures use engine-owned recovery under the standing charter. Preserve stops,\n"
        "newer input, unknown effects and bounded role. Never read tokens, repair credentials,\n"
        "switch provider/model or replay rejected content. Record failures through the Log.\n"
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
    if any(status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning")) or status.get("pendingMessageCount", 0) or status.get("pendingAsk") or status.get("pendingDialogs"):
        return None
    branch = native_branch(resolved)
    suffix = []
    for entry, raw in branch:
        if entry.get("type") != "custom" or entry.get("customType") != "pi-web.stream-failure":
            break
        suffix.append(entry)
    else:
        raise StreamsError("DCR has no native assistant behind its checkpoint metadata")
    message = entry.get("message")
    content = message.get("content") if isinstance(message, dict) else None
    if (entry.get("type") != "message" or not isinstance(content, list)
        or message.get("role") != "assistant" or message.get("stopReason") != "stop"
        or any(not isinstance(block, dict) or block.get("type") not in ("text", "thinking")
               or not isinstance(block.get(block["type"]), str) for block in content)):
        raise StreamsError("DCR has no complete native SYNC acknowledgement at its exact idle leaf")
    text = "\n".join(block["text"] for block in content if block.get("type") == "text")
    if acknowledgement not in text.splitlines():
        raise StreamsError("DCR has no complete native SYNC acknowledgement at its exact idle leaf")
    if suffix:
        boundary = status.get("failureBoundary")
        proof = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest()}
        if (not isinstance(boundary, dict) or type(boundary.get("version")) is not int or boundary["version"] != 1
            or boundary.get("sessionId") != resolved.row.session or boundary.get("cwd") != resolved.row.worktree
            or boundary.get("state") != "watching" or boundary.get("failure") is not None
            or not isinstance(boundary.get("root"), str) or not Path(boundary["root"]).is_absolute()
            or not isinstance(boundary.get("stream"), str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", boundary["stream"])
            or boundary.get("checkpoint") != proof
            or any(not isinstance(child.get("data"), dict) or type(child["data"].get("version")) is not int
                   or child["data"] != boundary for child in suffix)):
            raise StreamsError("DCR checkpoint metadata does not bind its own complete native SYNC acknowledgement")
    leaf, leaf_raw = branch[0]
    return leaf["id"], hashlib.sha256(leaf_raw).hexdigest()


def completion_after(resolved: Coordinator, compaction: str) -> str | None:
    completed = None
    branch = native_branch(resolved)
    retries = sessionlog.retry_dispositions(list(reversed(branch)), resolved.row.session, resolved.row.worktree)
    for entry, _ in branch:
        if entry["id"] == compaction:
            return completed
        message = entry.get("message")
        if isinstance(message, dict) and message.get("role") == "assistant":
            if message.get("stopReason") == "error" and retries.get(entry["id"], {}).get("state") != "resolved":
                raise StreamsError("Native RESUME contains an assistant error")
            if completed is None and message.get("stopReason") == "stop":
                completed = entry["id"]
    raise StreamsError("Native RESUME branch does not contain its owned compaction")


def close_events(stream_dir: Path, op: Operation) -> None:
    receipt = piweb.close_dcr_events(op.session, op.cwd, op.id, original=op.recovery_original)
    op.completed_leaf = receipt.get("entryId") or op.completed_leaf
    save(stream_dir, op)


def continuation_text(op: Operation, stream_dir: Path) -> str:
    context = op.continuation
    if context is None:
        return ""
    if context.get("mode") == "permitted-analysis-v1":
        raise StreamsError("Content-policy blocker. A clean model context and resource view is not proven")
    role = context.get("role")
    assignment = context.get("assignment")
    if not isinstance(role, str) or re.fullmatch(r"[a-z][a-z0-9_-]*", role) is None or not isinstance(assignment, str) or not assignment:
        raise StreamsError("Recovery has no exact bounded continuation assignment")
    return (f"Recovery retains role {role} in owned worktree {op.cwd}. Current session is {op.session}. "
            + ("Do not adopt the coordinator role or widen the assignment. " if role != "coordinator" else "")
            + f"Original assignment evidence follows. Its old session and handover identity are historical. Use {stream_dir}/handover/{role}/{op.session}.md for this session's handover with first line session: {op.session}. "
            "Reconcile omitted input and effects from the original evidence; never replay its last command.\n"
            f"Original native input/effect evidence: {context.get('nativeFile', 'retained original evidence')}. Saved input {json.dumps(context.get('savedInput', {}), sort_keys=True)}. Existing original handovers {json.dumps(context.get('handovers', []), sort_keys=True)}.\n"
            f"<original-assignment>\n{assignment}\n</original-assignment>\n")


def prepare(index: Path, stream: str, stream_dir: Path, resolved: Coordinator, identity: str, token: dict, *, original: str = "", continuation: dict | None = None) -> Operation:
    if (continuation or {}).get("mode") == "permitted-analysis-v1":
        raise StreamsError("Content-policy blocker. A clean model context and resource view is not proven; do not prepare recovery SYNC")
    previous = load(stream_dir, resolved.row.session)
    if previous is not None and (original or previous.phase not in {"complete", "superseded"}):
        if previous.id != identity or previous.recovery_original != original or previous.automatic != token or previous.continuation != continuation:
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
    op = Operation(identity, resolved.row.session, resolved.row.worktree, token, text, recovery_original=original, continuation=continuation)
    op.sync_text = continuation_text(op, stream_dir) + op.sync_text
    save(stream_dir, op)
    return op


def _capacity_detail(detail: str) -> int | None:
    if not isinstance(detail, str):
        return None
    if detail == "Legacy native compaction has no verified rebuilt context below 150000 tokens":
        return THRESHOLD
    for prefix in ("Native DCR failed: ", "maintenance failed: ", "Dead empty maintenance ownership released without replay. Prior failed: "):
        if detail.startswith(prefix):
            detail = detail[len(prefix):]
            break
    match = re.fullmatch(r"Native compaction did not reduce rebuilt context below ([0-9]+) tokens", detail)
    return int(match[1]) if match else None


def capacity_outcome(op: Operation, native: dict, status: dict) -> CapacityOutcome | None:
    if (op.recovery_original or not op.ready_revision or not op.ready_source or not op.checkpoint_entry or not op.checkpoint_sha256
        or op.resume_text or op.resume_goal or native.get("resume") is not None or native.get("inputs") != []
        or native.get("inputSequence") != 0 or native.get("cancelledByStop") is True
        or native.get("generation") != op.automatic["generation"] or native.get("entryId") != op.checkpoint_entry
        or native.get("id") != op.id or native.get("sessionId") != op.session or native.get("cwd") != op.cwd
        or native.get("instructions") != op.compact_instructions):
        return None
    if native.get("state") not in {"failed", "superseded", "complete"}:
        return None
    target = native.get("targetTokens")
    model = status.get("model", {})
    capacity = model.get("contextWindow")
    if type(capacity) is not int or capacity <= 0 or type(target) is not int or target <= 0:
        return None
    budget = {"provider": model.get("provider"), "model": model.get("id"), "contextWindow": capacity, "targetTokens": int(capacity * 0.8)}
    if not (target == THRESHOLD and native.get("contextBudget") is None) and (native.get("contextBudget") != budget or target != budget["targetTokens"]):
        return None
    known = _capacity_detail(native.get("detail", "")) == target
    legacy = (native.get("state") == "superseded"
              and native.get("detail") == "Dead empty maintenance ownership released without replay. Prior uncertain: Interrupted maintenance has no proven completed native compaction; do not replay"
              and (_capacity_detail(op.detail) in {THRESHOLD, target} or op.capacity is not None and _capacity_detail(op.capacity["receipt"].get("detail", "")) in {THRESHOLD, target}))
    if native.get("state") == "complete":
        known = False
        if (not isinstance(native.get("compactionEntryId"), str) or not native["compactionEntryId"]
            or not isinstance(native.get("compactionSha256"), str) or re.fullmatch(r"[a-f0-9]{64}", native["compactionSha256"]) is None):
            return None
        try:
            safe_context(native, status)
        except CapacityExceeded:
            known = True
        except StreamsError:
            return None
    if not known and not legacy:
        return None
    return CapacityOutcome(op.id, op.checkpoint_entry, op.checkpoint_sha256, op.automatic["generation"], native)


def _capacity_checkpoint(stream_dir: Path, op: Operation, resolved: Coordinator, outcome: CapacityOutcome) -> None:
    if not synced_state(stream_dir, op):
        raise StreamsError("Capacity rotation retains changed STATE; no stale checkpoint replacement")
    from engine import replacement
    replacement._idle(resolved)
    path = Path(resolved.native.info["path"])
    branch = sessionlog.branch_records(path, op.session, op.cwd, resolved.native.status["rotationSafety"]["entryId"])
    at = next((i for i, (entry, _) in enumerate(branch) if entry["id"] == op.checkpoint_entry), None)
    if at is None or hashlib.sha256(branch[at][1]).hexdigest() != op.checkpoint_sha256:
        raise StreamsError("Capacity rotation has no exact saved SYNC checkpoint")
    checkpoint_status = {**resolved.native.status, "rotationSafety": {**resolved.native.status["rotationSafety"], "entryId": op.checkpoint_entry}}
    checkpoint = Coordinator(resolved.row, NativeSession(resolved.native.info, checkpoint_status))
    if terminal_checkpoint(checkpoint, f"DCR SYNC ready: {op.id} {op.ready_revision}") != (op.checkpoint_entry, op.checkpoint_sha256):
        raise StreamsError("Capacity rotation lost its terminal SYNC acknowledgement")
    marker = None
    compactions = []
    for entry, raw in branch[at + 1:]:
        data = entry.get("data", {})
        if not isinstance(data, dict):
            raise StreamsError("Capacity rotation has malformed native metadata")
        if entry.get("type") == "custom" and entry.get("customType") == "pi-web.maintenance":
            if marker is not None or entry.get("parentId") != op.checkpoint_entry or data != {"id": op.id, "sessionId": op.session, "cwd": op.cwd, "entryId": op.checkpoint_entry, "generation": op.automatic["generation"]}:
                raise StreamsError("Capacity rotation has a changed maintenance marker")
            marker = entry["id"]
        elif entry.get("type") == "compaction" and marker is not None:
            digest = hashlib.sha256(raw).hexdigest()
            sessionlog.compaction_record(sessionlog.read_record(path, op.session, entry["id"], digest))
            compactions.append((entry["id"], digest))
        elif entry.get("type") == "custom" and entry.get("customType") == "pi-web.stream-failure" and data == resolved.native.status.get("failureBoundary") and data.get("state") == "watching" and data.get("failure") is None:
            continue
        elif (entry.get("type") == "custom" and entry.get("customType") == "pi-web.streams-dcr"
              and data.get("id") == op.id and data.get("sessionId") == op.session and data.get("cwd") == op.cwd
              and data.get("generation") == op.automatic["generation"] and data.get("state") in {"active", "closed"}):
            continue
        else:
            raise StreamsError("Capacity rotation retains newer native input or unknown compaction effects")
    if marker is None or len(compactions) > 1 or outcome.receipt.get("markerEntryId", marker) != marker:
        raise StreamsError("Capacity rotation has no unique persisted maintenance attempt")
    if outcome.receipt.get("compactionEntryId") is not None and (outcome.receipt.get("compactionEntryId"), outcome.receipt.get("compactionSha256")) not in compactions:
        raise StreamsError("Capacity rotation compaction receipt changed")


def rotate_capacity_locked(stream_dir: Path, resolved: Coordinator, op: Operation, outcome: CapacityOutcome) -> str:
    from engine import replacement
    op.capacity = asdict(outcome)
    save(stream_dir, op)
    _capacity_checkpoint(stream_dir, op, resolved, outcome)
    token, allowed = piweb.automatic_admission(resolved.native.status, op.session, op.cwd, "wake")
    if allowed and token != op.automatic:
        raise StreamsError("Newer receiving input superseded capacity rotation")
    outcome = CapacityOutcome(outcome.operation, outcome.checkpoint_entry, outcome.checkpoint_sha256, outcome.generation, outcome.receipt,
                              {"entryId": resolved.native.status["rotationSafety"]["entryId"], "generation": token["generation"], "allowed": allowed})
    op.capacity = asdict(outcome)
    op.phase = "rotation-pending"
    save(stream_dir, op)
    intent = replacement.replacement_intent(stream_dir)
    if intent is None or intent.phase == "complete":
        intent = replacement._begin_replacement(stream_dir, resolved.row, "", outcome=op.capacity)
    elif intent.mode != "capacity" or intent.source != op.session or intent.outcome != op.capacity:
        raise StreamsError("Another replacement intent owns this capacity outcome")
    target = replacement.advance_replacement_locked(stream_dir, intent)
    op.phase, op.detail = "rotated", f"Known capacity failure rotated from saved SYNC checkpoint to {target}; original input receipts retained."
    save(stream_dir, op)
    return target


def advance_capacity_replacement_locked(stream_dir: Path, *, session: str | None = None, operation: str | None = None) -> bool:
    from engine import replacement
    intent = replacement.replacement_intent(stream_dir)
    if intent is None or intent.mode != "capacity" or session is not None and intent.source != session:
        return False
    op = load(stream_dir, intent.source)
    if op is None or operation is not None and op.id != operation:
        return False
    if intent.phase == "complete" and op.phase == "rotated":
        return operation is not None
    if op.phase != "rotation-pending" or op.capacity != intent.outcome:
        raise StreamsError("Capacity replacement lost its exact DCR owner/receipt")
    target = replacement.advance_replacement_locked(stream_dir, intent)
    op.phase, op.detail = "rotated", f"Known capacity failure rotated from saved SYNC checkpoint to {target}; original input receipts retained."
    save(stream_dir, op)
    return True


def step(index: Path, project: Project, stream: str, stream_dir: Path, resolved: Coordinator | None) -> bool:
    if resolved is None or load_stream_config(stream_dir / "stream.toml").state_schema != STATE_SCHEMA:
        return False
    from engine.drive import is_paused

    if is_paused(stream_dir):
        return True
    sid, status = resolved.row.session, resolved.native.status
    op = load(stream_dir, sid)
    if op is not None and (op.continuation or {}).get("mode") == "permitted-analysis-v1":
        op.phase, op.detail = "blocked", "Content-policy blocker. Persisted restricted DCR has no proven clean context/resource view. No inference, compaction, or RESUME is admitted."
        save(stream_dir, op)
        return True
    token, allowed = piweb.automatic_admission(status, sid, resolved.row.worktree, "wake")
    if op is not None and op.phase == "rotated":
        return True
    if op is not None and op.phase in {"blocked", "compact-sending", "compacting", "rotation-pending"} and op.checkpoint_entry and not op.recovery_original:
        try:
            native = piweb.maintenance_status(op.cwd, sid, op.id)
            outcome = capacity_outcome(op, native, status)
            if outcome is not None:
                rotate_capacity_locked(stream_dir, resolved, op, outcome)
                return True
            if op.phase == "rotation-pending":
                return True
        except (StreamsError, OSError, ValueError) as exc:
            from engine import replacement
            intent = replacement.replacement_intent(stream_dir)
            if intent is not None and intent.phase != "complete":
                replacement._save(stream_dir, "coordinator_replacement_error", {"replacement": intent.id, "detail": str(exc)})
            else:
                op.detail = str(exc)
                save(stream_dir, op)
            return True
    if op is not None and op.phase == "blocked" and op.detail == "Native RESUME contains an assistant error":
        native = piweb.maintenance_status(op.cwd, sid, op.id, original=op.recovery_original)
        resume = native.get("resume")
        if (native.get("state") != "resumed" or native.get("generation") != op.automatic["generation"]
            or native.get("entryId") != op.checkpoint_entry or native.get("compactionEntryId") != op.compaction_entry
            or native.get("compactionSha256") != op.compaction_sha256 or native.get("inputs") or native.get("inputSequence")
            or not isinstance(resume, dict) or resume.get("state") != "admitted"
            or resume.get("deliveryId") != f"{op.id}:resume" or resume.get("text") != op.resume_text
            or resume.get("potetoGoal") != op.resume_goal):
            return True
        op.phase, op.detail = "resuming", "Reconciled exact admitted RESUME; no redispatch."
        save(stream_dir, op)
    if op is not None and op.phase == "blocked":
        legacy_gate = "below 150000 tokens" in op.detail and not op.resume_text and op.checkpoint_entry
        if not legacy_gate:
            return True
        native = piweb.maintenance_status(op.cwd, sid, op.id, original=op.recovery_original)
        if native.get("generation") != op.automatic["generation"] or native.get("entryId") != op.checkpoint_entry:
            raise StreamsError("Legacy DCR reconciliation changed its exact checkpoint/generation")
        if native.get("resume") is not None or native.get("inputs") or native.get("inputSequence"):
            return True
        if native.get("state") == "superseded":
            op.phase, op.detail = "superseded", "Dead legacy context-gate ownership was reconciled without replay; current admission remains authoritative."
            save(stream_dir, op)
            close_events(stream_dir, op)
            return False
        if native.get("state") != "complete" or not allowed or token != op.automatic:
            return True
        safe_context(native, status)
        if piweb.compaction_result(op.cwd, sid, op.id, original=op.recovery_original) is None:
            return True
        op.phase, op.detail = "compacting", "Reconciled exact completed compaction after the legacy context gate."
        save(stream_dir, op)
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
        trigger = max(THRESHOLD, op.rebuilt_tokens + max(20000, op.rebuilt_tokens // 10)) if op is not None and op.rebuilt_tokens else THRESHOLD
        if not allowed or type(tokens) is not int or tokens < trigger:
            return False
        if status.get("isCompacting") is True or status.get("isBashRunning") is True or status.get("pendingAsk") or status.get("pendingDialogs"):
            return True
        if op is not None and op.completed_leaf == leaf:
            return False
        artifacts._read_stream_state_locked(stream_dir)
        identity = uuid.uuid4().hex
        op = prepare(index, stream, stream_dir, resolved, identity, token)
    try:
        piweb.require_settings(status, resolved.row.model, resolved.row.thinking)
        if status.get("maintenanceSupport") != "checkpoint-input-v1" or status.get("potetoInvocationSupport") != "exact-goal-v1" or status.get("dcrEventSupport") != "phase-v1":
            op.phase, op.detail = "blocked", "Native checkpoint, exact mode and idle-event capabilities are required."
            save(stream_dir, op)
            return True
        if op.phase == "sync-prepared":
            if status.get("isCompacting") is True or status.get("isBashRunning") is True or status.get("pendingAsk") or status.get("pendingDialogs"):
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
                if op.recovery_original and status.get("failureSyncContinuationSupport") == "entry-bound-v1" and not any(status.get(key) for key in ("isStreaming", "isCompacting", "isBashRunning", "pendingMessageCount", "pendingAsk", "pendingDialogs")):
                    branch = native_branch(resolved)
                    entry, raw = branch[0]
                    if entry.get("message", {}).get("role") == "assistant" and entry["message"].get("stopReason") == "aborted":
                        expected = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest()}
                        model = status.get("model", {})
                        identity = {"provider": model.get("provider"), "model": model.get("id"), "thinking": resolved.row.thinking}
                        try:
                            receipt = piweb.failure_maintenance(op.recovery_original, op.cwd, {"id": op.id, "action": "continue-sync", "expected": expected, "identity": identity})
                            sync = receipt["operation"].get("maintenance", {}).get("sync", {})
                            if sync.get("text") != op.sync_text or sync.get("deliveryId") != f"{op.id}:sync":
                                raise StreamsError("Recovery continuation changed the accepted SYNC intent")
                            for continued in sync.get("continuations", []):
                                if continued.get("checkpoint") == expected and (continued.get("operationId") != op.id or continued.get("originalSessionId") != op.recovery_original or continued.get("sessionId") != sid or continued.get("identity") != identity or continued.get("generation") != op.automatic["generation"] or continued.get("originalGeneration") != receipt["operation"].get("generation") or continued.get("state") not in {"sending", "ended", "uncertain"}):
                                    raise StreamsError("Recovery continuation changed its frozen checkpoint/identity/generations")
                            op.detail = "Recovery SYNC continuation is uncertain; no redispatch" if any(item.get("state") == "uncertain" for item in sync.get("continuations", [])) else ""
                        except (StreamsError, OSError) as exc:
                            op.detail = str(exc)
                        save(stream_dir, op)
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
            op.rebuilt_tokens = safe_context(native, status)
            artifacts._rotate_log_locked(stream_dir)
            state = artifacts._read_stream_state_locked(stream_dir)
            op.compaction_entry, op.compaction_sha256 = proof["entryId"], proof["sha256"]
            op.resume_goal = artifacts.resolve_current_goal(state)
            op.resume_text = continuation_text(op, stream_dir) + resume_text(stream_dir, op.resume_goal)
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

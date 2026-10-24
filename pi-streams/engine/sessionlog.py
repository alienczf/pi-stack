from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from engine import StreamsError

CHUNK = 65536


@contextmanager
def regular_reader(path: Path) -> Iterator[BinaryIO]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise StreamsError(f"native source must be a regular owned file: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(descriptor)
        def identity(value: os.stat_result) -> tuple[int, ...]:
            return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise StreamsError(f"native source changed before read: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            yield handle
        if identity(os.fstat(descriptor)) != identity(opened) or identity(path.lstat()) != identity(opened):
            raise StreamsError(f"native source changed during read: {path}")
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class EvidenceRecord:
    session_id: str
    entry_id: str
    sha256: str
    raw: bytes
    line_number: int
    path: str
    archived: bool


def read_record(path: Path, session_id: str, entry_id: str, expected_sha256: str, *, archived: bool = False) -> EvidenceRecord:
    if not session_id or not entry_id or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise StreamsError("evidence requires exact session/entry identity and a SHA-256 hash")
    found: tuple[int, bytes] | None = None
    try:
        with regular_reader(path) as handle:
            try:
                header = json.loads(handle.readline())
            except ValueError as exc:
                raise StreamsError("evidence source has invalid session identity") from exc
            if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != session_id:
                raise StreamsError("evidence source session identity does not match")
            for number, raw in enumerate(handle, start=2):
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("id") == entry_id:
                    if found is not None:
                        raise StreamsError(f"ambiguous evidence entry {entry_id}")
                    found = number, raw
    except OSError as exc:
        raise StreamsError(f"evidence source unavailable at {path}: {exc}") from exc
    if found is None:
        raise StreamsError(f"evidence entry {entry_id} unavailable")
    number, raw = found
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise StreamsError(f"evidence hash mismatch for {session_id}/{entry_id}: expected {expected_sha256}, got {digest}")
    return EvidenceRecord(session_id, entry_id, digest, raw, number, str(path), archived)


def compaction_record(evidence: EvidenceRecord) -> dict:
    try:
        entry = json.loads(evidence.raw)
    except ValueError as exc:
        raise StreamsError("native compaction evidence is not valid JSON") from exc
    if not isinstance(entry, dict) or entry.get("type") != "compaction" or entry.get("id") != evidence.entry_id or not isinstance(entry.get("summary"), str) or not entry["summary"].strip() or not isinstance(entry.get("firstKeptEntryId"), str) or not entry["firstKeptEntryId"] or type(entry.get("tokensBefore")) is not int or entry["tokensBefore"] < 0:
        raise StreamsError("evidence is not a successful persisted native compaction entry")
    return {"sessionId": evidence.session_id, "entryId": evidence.entry_id, "sha256": evidence.sha256, "tokensBefore": entry["tokensBefore"], "summary": entry["summary"]}


def branch_records(path: Path, sid: str, cwd: str, leaf: object) -> list[tuple[dict, bytes]]:
    entries: dict[str, tuple[dict, bytes]] = {}
    with regular_reader(path) as handle:
        header = json.loads(handle.readline())
        if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != sid or not isinstance(header.get("cwd"), str) or Path(header["cwd"]).resolve() != Path(cwd).resolve():
            raise StreamsError("failure evidence does not match the exact native session/cwd")
        for raw in handle:
            try:
                value = json.loads(raw)
            except ValueError:
                continue
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                if value["id"] in entries:
                    raise StreamsError("failure evidence contains ambiguous native entry IDs")
                entries[value["id"]] = value, raw
    if not isinstance(leaf, str) or leaf not in entries:
        raise StreamsError("failure boundary cannot prove the exact current native branch")
    branch = []
    seen = set()
    while leaf is not None:
        if not isinstance(leaf, str) or leaf in seen or leaf not in entries:
            raise StreamsError("failure evidence has an incomplete or cyclic branch")
        seen.add(leaf)
        value, raw = entries[leaf]
        branch.append((value, raw))
        leaf = value.get("parentId")
    branch.reverse()
    return branch


def verify_good_checkpoint(path: Path, sid: str, cwd: str, leaf: object, checkpoint: dict, failure_entry: str) -> dict:
    if not isinstance(checkpoint.get("entryId"), str) or not isinstance(checkpoint.get("sha256"), str) or re.fullmatch(r"[a-f0-9]{64}", checkpoint["sha256"]) is None:
        raise StreamsError("native good-turn checkpoint identity/hash is invalid")
    pending: set[str] = set()
    healthy = True
    for entry, raw in branch_records(path, sid, cwd, leaf):
        if entry["id"] == failure_entry:
            break
        message = entry.get("message", {})
        if message.get("role") == "assistant":
            healthy = not pending
            calls = message.get("content", [])
            if isinstance(calls, list):
                for call in calls:
                    if isinstance(call, dict) and call.get("type") == "toolCall":
                        identity = call.get("id")
                        if not isinstance(identity, str) or not identity or identity in pending:
                            raise StreamsError("ambiguous tool-call identity in good-turn checkpoint")
                        pending.add(identity)
            if message.get("stopReason") in ("error", "aborted", "length"):
                healthy = False
        elif message.get("role") == "toolResult":
            identity = message.get("toolCallId")
            if not isinstance(identity, str) or identity not in pending:
                raise StreamsError("good-turn checkpoint has an unmatched tool result")
            pending.remove(identity)
            healthy = healthy and message.get("isError") is not True
        if entry["id"] == checkpoint["entryId"]:
            terminal = message.get("role") == "toolResult" or message.get("role") == "assistant" and message.get("stopReason") == "stop"
            if not terminal or pending or not healthy or hashlib.sha256(raw).hexdigest() != checkpoint["sha256"]:
                raise StreamsError("checkpoint is not the exact complete successful persisted turn")
            return {"entryId": checkpoint["entryId"], "sha256": checkpoint["sha256"], "nativeFile": str(path), "branchLeaf": leaf}
    raise StreamsError("good-turn checkpoint is absent or is not before the native failure")


def failure_observation(path: Path, sid: str, cwd: str, leaf: object, failure_entry: str | None = None) -> dict | None:
    branch = branch_records(path, sid, cwd, leaf)
    failed = None
    saved = ("", "")
    uncertain: dict[str, dict[str, str]] = {}
    for entry, raw in branch:
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user":
            saved = entry["id"], hashlib.sha256(raw).hexdigest()
        if message.get("role") == "toolResult":
            details = message.get("details")
            if isinstance(details, dict):
                job = details.get("jobId", details.get("job_id", details.get("externalJobId")))
                if isinstance(job, str) and job:
                    status = str(details.get("status", "unknown"))
                    if status in ("completed", "succeeded", "failed", "cancelled"):
                        uncertain.pop(job, None)
                    else:
                        uncertain[job] = {"id": job, "state": status}
        is_tool = message.get("role") == "toolResult" and message.get("isError") is True
        is_model = message.get("role") == "assistant" and message.get("stopReason") == "error"
        if not is_tool and not is_model or failure_entry is not None and entry["id"] != failure_entry:
            continue
        body = message.get("errorMessage", "")
        if is_tool:
            content = message.get("content", [])
            body = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
            if failure_entry is None and not re.search(r"ENOSPC|no space left|resource exhausted|out of memory|login expired|unauthorized|token expired|authentication expired", body, re.I):
                continue
        failed = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest(), "provider": "tool" if is_tool else str(message.get("provider", "unknown")), "message": body if isinstance(body, str) else "", "toolError": is_tool, "savedEntryId": saved[0], "savedSha256": saved[1], "uncertainJobs": []}
    if failed is not None:
        failed["uncertainJobs"] = list(uncertain.values())
    return failed


def successful_control_completion(path: Path, sid: str, cwd: str, leaf: object, prefix: str, goal: str) -> bool:
    active = False
    completed = False
    for entry, _raw in branch_records(path, sid, cwd, leaf):
        message = entry.get("message", {})
        content = message.get("content", [])
        text = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
        if message.get("role") == "user" and text.startswith(prefix) and text.endswith(goal) and '<skill name="poteto-mode"' in text:
            active, completed = True, False
        elif active and message.get("role") == "assistant":
            if message.get("stopReason") == "error":
                return False
            if message.get("stopReason") == "stop":
                completed = True
    return completed


def resume_observation(path: Path, sid: str, cwd: str, leaf: object, identity: str, generation: str, compaction: str, compaction_sha256: str, text: str, goal: str, native: dict) -> dict | None:
    receipt = native.get("resume")
    if not isinstance(receipt, dict) or receipt.get("observation") is None:
        return None
    observation = receipt["observation"]
    if not isinstance(observation, dict) or native.get("state") != "resumed" or native.get("inputSequence") != 0 or receipt.get("state") != "admitted" or receipt.get("deliveryId") != identity+":resume" or receipt.get("generation") != generation or receipt.get("inputSequence") != 0 or receipt.get("text") != text or receipt.get("potetoGoal") != goal:
        raise StreamsError("RESUME observation changed its saved admission/epoch")
    required = ("entryId", "sha256", "userEntryId", "assistantEntryId", "assistantSha256")
    if any(not isinstance(observation.get(key), str) or not observation[key] for key in required):
        raise StreamsError("RESUME observation lacks exact entry/hash identities")
    entries = branch_records(path, sid, cwd, leaf)
    positions = {entry["id"]: index for index, (entry, _raw) in enumerate(entries)}
    keys = (compaction, observation["userEntryId"], observation["assistantEntryId"], observation["entryId"])
    if any(key not in positions for key in keys) or not all(positions[a] < positions[b] for a, b in zip(keys, keys[1:])):
        raise StreamsError("RESUME observation is not on its ordered post-compaction branch")
    entry = json.loads(read_record(path, sid, observation["entryId"], observation["sha256"]).raw)
    expected = {"kind": "assistant-stop", "operationId": identity, "sessionId": sid, "cwd": cwd, "generation": generation, "deliveryId": identity+":resume", "compactionEntryId": compaction, "userEntryId": observation["userEntryId"], "assistantEntryId": observation["assistantEntryId"], "assistantSha256": observation["assistantSha256"]}
    if entry.get("type") != "custom" or entry.get("customType") != "pi-web.resume-observed" or entry.get("data") != expected or any(observation.get(key) != expected[key] for key in ("kind", "deliveryId", "compactionEntryId")):
        raise StreamsError("RESUME observation is not its exact native correlated receipt")
    compaction_record(read_record(path, sid, compaction, compaction_sha256))
    assistant = json.loads(read_record(path, sid, observation["assistantEntryId"], observation["assistantSha256"]).raw).get("message", {})
    if assistant.get("role") != "assistant" or assistant.get("stopReason") != "stop":
        raise StreamsError("RESUME observation has no actual non-error completed assistant")
    owned, owned_raw = entries[positions[observation["userEntryId"]]]
    message = owned.get("message", {})
    content = message.get("content", [])
    actual = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    invocation = "/poteto-mode " + goal
    prefix = text[:-len(invocation)] if text.endswith(invocation) else None
    if message.get("role") != "user" or prefix is None or not actual.startswith(prefix+'<skill name="poteto-mode"') or not actual.endswith("</skill>\n\n"+goal):
        raise StreamsError("RESUME observation user is not the actual expanded fixed mode/goal input")
    messages = [value.get("message", {}) for value, _raw in entries[positions[compaction]+1:positions[observation["entryId"]]] if value.get("type") == "message"]
    if sum(message.get("role") == "user" for message in messages) != 1 or any(message.get("stopReason") in {"error", "aborted"} for message in messages):
        raise StreamsError("New input or failed inference superseded the owned RESUME")
    return {**observation, "userSha256": hashlib.sha256(owned_raw).hexdigest()}


def last_assistant(path: Path) -> dict[str, object] | None:
    try:
        with regular_reader(path) as handle:
            return _scan_back(handle)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc


def _scan_back(handle: BinaryIO) -> dict[str, object] | None:
    end = handle.seek(0, os.SEEK_END)
    pieces: list[bytes] = []
    while end > 0:
        start = max(0, end - CHUNK)
        handle.seek(start)
        data = handle.read(end - start)
        end = start
        stop = len(data)
        cut = data.rfind(b"\n", 0, stop)
        while cut >= 0:
            pieces.append(data[cut + 1 : stop])
            message = _assistant(b"".join(reversed(pieces)))
            if message is not None:
                return message
            pieces = []
            stop = cut
            cut = data.rfind(b"\n", 0, stop)
        pieces.append(data[:stop])
    return _assistant(b"".join(reversed(pieces)))


def _assistant(line: bytes) -> dict[str, object] | None:
    # A line pi is still appending does not parse yet; the one before it counts.
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "message":
        return None
    message = entry.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        return message
    return None

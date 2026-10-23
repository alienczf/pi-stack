from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO

from engine import StreamsError

CHUNK = 65536


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
        with path.open("rb") as handle:
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


def last_assistant(path: Path) -> dict[str, object] | None:
    try:
        with open(path, "rb") as handle:
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

"""Authenticated transport adapters create relay approvals. Message bodies cannot."""
from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

from engine import StreamsError, artifacts
from engine.project import _write

_SEAL = object()


@dataclass(frozen=True)
class VerifiedRelay:
    principal: str
    message_id: str
    stream: str
    sha256: str
    body: str
    instruction_date: str
    quoted_words: str
    raw: bytes
    _seal: object = field(repr=False)


class TrustedRelayIntake:
    def __init__(self, authenticate: Callable[[object, bytes], str | None], trusted_principals: Mapping[str, str]):
        self.authenticate = authenticate
        self.trusted_principals = dict(trusted_principals)

    def accept(self, transport: object, raw: bytes, *, stream: str) -> VerifiedRelay:
        principal = self.authenticate(transport, raw)
        if principal is None or self.trusted_principals.get(principal) != "ZF":
            raise StreamsError("No authenticated trusted ZF relay principal")
        source = _source(raw, stream)
        return VerifiedRelay(principal, source["messageId"], stream, hashlib.sha256(raw).hexdigest(), source["body"], source.get("instructionDate", ""), source.get("quotedWords", ""), raw, _SEAL)


def _source(raw: bytes, stream: str) -> dict:
    try:
        source = json.loads(raw)
    except (ValueError, UnicodeError) as exc:
        raise StreamsError("Relay source is not UTF-8 JSON") from exc
    if not isinstance(source, dict) or source.get("stream") != stream or source.get("onBehalfOf") != "ZF" or source.get("onInstruction") is not True or source.get("scope") != "in-scope-reversible":
        raise StreamsError("Relay source does not authorize this stream's reversible scope")
    if any(not isinstance(source.get(key), str) or not source[key].strip() for key in ("messageId", "body")):
        raise StreamsError("Relay needs its exact source identity and words")
    dated, quoted = source.get("instructionDate", ""), source.get("quotedWords", "")
    if not isinstance(dated, str) or not isinstance(quoted, str) or not (dated or quoted):
        raise StreamsError("Relay needs ZF's dated standing rule or exact quoted words")
    if dated:
        try:
            if date.fromisoformat(dated).isoformat() != dated:
                raise ValueError("noncanonical date")
        except ValueError as exc:
            raise StreamsError("Relay standing-rule date must be YYYY-MM-DD") from exc
    if quoted and quoted not in source["body"]:
        raise StreamsError("Quoted ZF words are absent from the exact source")
    return source


def record_ruling(stream: Path, at: str, subject: str, source: VerifiedRelay, *, supersedes: str | None = None) -> int:
    if not isinstance(source, VerifiedRelay) or source._seal is not _SEAL or source.stream != stream.name:
        raise StreamsError("A verified exact-stream relay approval is required")
    provenance = (f"Trusted ZF relay principal {source.principal}. Source {source.message_id}, SHA-256 {source.sha256}. "
                  f"Instruction date {source.instruction_date or 'not supplied'}. Scope is in-scope reversible work only.\n")
    notice = "trusted-relay:" + hashlib.sha256(json.dumps([source.principal, source.message_id, source.stream]).encode()).hexdigest()
    retained = retain_source(stream, source.raw)
    return artifacts.record_ruling(stream, at, subject, provenance + f"Exact source record {retained}.\n" + source.body, notice_id=notice, supersedes=supersedes)


def source_provenance(raw: bytes, stream: str) -> dict:
    source = _source(raw, stream)
    return {'kind': 'recorded-source-provenance', 'stream': stream, 'messageId': source['messageId'],
            'instructionDate': source.get('instructionDate', ''), 'sha256': hashlib.sha256(raw).hexdigest(),
            'raw': base64.b64encode(raw).decode('ascii')}


def validate_provenance(value: dict, stream: str) -> bytes:
    try:
        raw = base64.b64decode(value['raw'], validate=True)
        if source_provenance(raw, stream) != value:
            raise ValueError('changed source metadata')
        return raw
    except (ValueError, KeyError, TypeError) as exc:
        raise StreamsError(f'Relay source provenance changed: {exc}') from exc


def retain_source(stream: Path, raw: bytes) -> str:
    relative = 'history/relay-' + hashlib.sha256(raw).hexdigest() + '.json'
    path = stream / relative
    if path.parent.is_symlink() or path.is_symlink():
        raise StreamsError('Relay source retention requires an owned regular history path')
    if path.exists() and path.read_bytes() != raw:
        raise StreamsError('Exact relay source retention changed')
    if not path.exists():
        _write(path, raw.decode('utf-8'))
    return relative


def record_sourced_ruling(stream: Path, at: str, subject: str, raw: bytes, *, supersedes: str | None = None) -> int:
    source = source_provenance(raw, stream.name)
    body = json.loads(raw)['body']
    retained = retain_source(stream, raw)
    provenance = (f"Recorded bot-relay source {source['messageId']}. Instruction date {source['instructionDate'] or 'not supplied'}. "
                  f"SHA-256 {source['sha256']}. Exact source {retained}. This is source provenance, not transport authentication. Scope remains in-scope reversible work under the existing Charter.\n")
    return artifacts.record_ruling(stream, at, subject, provenance + body, notice_id='relay-source:' + source['messageId'], supersedes=supersedes)

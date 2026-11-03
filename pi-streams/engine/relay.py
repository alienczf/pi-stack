"""Authenticated transport adapters create relay approvals. Message bodies cannot."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
import hashlib
import json
from pathlib import Path
from typing import Callable, Mapping

from engine import StreamsError, artifacts

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
    _seal: object = field(repr=False)


class TrustedRelayIntake:
    def __init__(self, authenticate: Callable[[object, bytes], str | None], trusted_principals: Mapping[str, str]):
        self.authenticate = authenticate
        self.trusted_principals = dict(trusted_principals)

    def accept(self, transport: object, raw: bytes, *, stream: str) -> VerifiedRelay:
        principal = self.authenticate(transport, raw)
        if principal is None or self.trusted_principals.get(principal) != "ZF":
            raise StreamsError("No authenticated trusted ZF relay principal")
        try:
            source = json.loads(raw)
        except (ValueError, UnicodeError) as exc:
            raise StreamsError("Authenticated relay source is not UTF-8 JSON") from exc
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
        return VerifiedRelay(principal, source["messageId"], stream, hashlib.sha256(raw).hexdigest(), source["body"], dated, quoted, _SEAL)


def record_ruling(stream: Path, at: str, subject: str, source: VerifiedRelay, *, supersedes: str | None = None) -> int:
    if not isinstance(source, VerifiedRelay) or source._seal is not _SEAL or source.stream != stream.name:
        raise StreamsError("A verified exact-stream relay approval is required")
    provenance = (f"Trusted ZF relay principal {source.principal}. Source {source.message_id}, SHA-256 {source.sha256}. "
                  f"Instruction date {source.instruction_date or 'not supplied'}. Scope is in-scope reversible work only.\n")
    notice = "trusted-relay:" + hashlib.sha256(json.dumps([source.principal, source.message_id, source.stream]).encode()).hexdigest()
    return artifacts.record_ruling(stream, at, subject, provenance + source.body, notice_id=notice, supersedes=supersedes)

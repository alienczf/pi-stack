from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from pathlib import Path
from typing import Literal, TypedDict

from engine import StreamsError
from engine.project import git, git_blob


class SourceBytes(TypedDict):
    path: str
    sha256: str
    bytes_base64: str


class GitSource(SourceBytes):
    source_kind: Literal["git-blob"]
    commit: str
    blob_oid: str


class RetainedFile(SourceBytes):
    source_kind: Literal["retained-file"]


class WitnessSpan(TypedDict):
    source: str
    start: int
    end: int
    sha256: str
    text: str


class LegacyAuthority(TypedDict):
    marker: WitnessSpan
    evidence: list[WitnessSpan]
    instruction_date: str | None


class RecoveryInput(TypedDict):
    version: Literal[1]
    supplemental_sources: dict[str, GitSource | RetainedFile]
    legacy_authority: LegacyAuthority


CURRENT = frozenset({"STREAM.md", "DECISIONS.md", "STATE.md"})
MARKER = re.compile(r"ratified: retained-source-v1 SHA256 ([0-9a-f]{64}) instruction-date (unknown|\d{4}-\d{2}-\d{2}); documentary provenance, not transport authentication or new work authority\n?")
REVOKED = re.compile(r"\b(?:ratif\w*[^\n]{0,100}(?:revok\w*|retract\w*|not true|never occurred)|(?:revok\w*|retract\w*)[^\n]{0,100}ratif\w*|ZF never (?:approved|authorized|ratified))\b", re.IGNORECASE)


def canonical(value: object) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def raw_source(record: dict, key: str = "bytes") -> bytes:
    try:
        raw = base64.b64decode(record[key], validate=True)
        raw.decode("utf-8")
        if b"\0" in raw or sha(raw) != record["sha256"]:
            raise ValueError("binary data or source hash mismatch")
        return raw
    except (KeyError, TypeError, ValueError) as exc:
        raise StreamsError(f"invalid retained source bytes: {exc}") from exc


def retained_path(root: Path, name: str) -> Path:
    if (not isinstance(name, str) or not re.fullmatch(r"context/(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+\.md", name)
            or any(part in {".", ".."} for part in Path(name).parts)):
        raise StreamsError("retained file must be a regular relative context Markdown path")
    return root / name


def retained_bytes(root: Path, name: str) -> bytes:
    retained_path(root, name)
    descriptors = []
    try:
        descriptors.append(os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW))
        parts = Path(name).parts
        for index, part in enumerate(parts):
            final = index == len(parts) - 1
            flags = os.O_RDONLY | os.O_NOFOLLOW | (os.O_NONBLOCK if final else os.O_DIRECTORY)
            descriptor = os.open(part, flags, dir_fd=descriptors[-1])
            descriptors.append(descriptor)
            before = os.fstat(descriptor)
            if before.st_uid != os.getuid() or (final and not stat.S_ISREG(before.st_mode)):
                raise StreamsError("retained file must have owned directories and a regular owned source")
        with os.fdopen(descriptors[-1], "rb", closefd=False) as handle:
            raw = handle.read()
        after = os.fstat(descriptors[-1])
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise StreamsError("retained file changed while reading")
        return raw
    except OSError as exc:
        raise StreamsError(f"retained file ownership, symlink or availability boundary failed: {exc}") from exc
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def validate_sources(root: Path, recovery: RecoveryInput, *, fresh: bool) -> dict[str, dict]:
    try:
        if not isinstance(recovery, dict) or set(recovery) != {"version", "supplemental_sources", "legacy_authority"} or type(recovery["version"]) is not int or recovery["version"] != 1:
            raise ValueError("expected recovery-sources version 1 with supplemental_sources and legacy_authority")
        result = {}
        for name, record in sorted(recovery["supplemental_sources"].items()):
            if not isinstance(name, str) or re.fullmatch(r"(git|retained):[a-z][a-z0-9-]{0,63}", name) is None:
                raise ValueError("invalid supplemental source name")
            kind = record["source_kind"]
            fields = {"source_kind", "path", "sha256", "bytes_base64"}
            if kind == "git-blob" and name.startswith("git:"):
                if set(record) != fields | {"commit", "blob_oid"} or record["path"] != "STREAM.md":
                    raise ValueError("Git source must bind an exact historical STREAM.md blob")
                for key in ("commit", "blob_oid"):
                    if not isinstance(record[key], str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", record[key]) is None:
                        raise ValueError("Git source requires full object identities")
                if git(root, "rev-parse", "--show-toplevel").strip() != str(root.resolve()) or git(root, "cat-file", "-t", record["commit"]).strip() != "commit":
                    raise ValueError("Git source requires a same-root commit object")
                git(root, "merge-base", "--is-ancestor", record["commit"], "HEAD")
                entry = git(root, "ls-tree", record["commit"], "--", "STREAM.md").strip()
                if entry != f"100644 blob {record['blob_oid']}\tSTREAM.md" and entry != f"100755 blob {record['blob_oid']}\tSTREAM.md":
                    raise ValueError("historical STREAM is not the bound regular Git blob")
                observed = git_blob(root, f"{record['commit']}:STREAM.md")
            elif kind == "retained-file" and name.startswith("retained:"):
                if set(record) != fields:
                    raise ValueError("unexpected retained-file fields")
                retained_path(root, record["path"])
                observed = retained_bytes(root, record["path"]) if fresh else None
            else:
                raise ValueError("unsupported supplemental source kind")
            raw = raw_source(record, "bytes_base64")
            if observed is not None and observed != raw:
                raise ValueError("supplemental source changed")
            result[name] = {"bytes": record["bytes_base64"], "sha256": record["sha256"]}
        return result
    except (KeyError, TypeError, ValueError, AttributeError, OSError) as exc:
        raise StreamsError(f"invalid recovery sources: {exc}") from exc


def literal_lines(raw: bytes, start: int, end: int) -> list[str]:
    if start and raw[start - 1:start] != b"\n" or end < len(raw) and raw[end - 1:end] != b"\n":
        raise ValueError("legacy witness must retain complete source lines")
    result = []
    offset = 0
    fence = b""
    for line in raw.splitlines(keepends=True):
        text = line.rstrip(b"\r\n")
        delimiter = re.fullmatch(rb" {0,3}(`{3,}|~{3,})(.*)", text)
        if fence:
            if delimiter and delimiter[1][:1] == fence[:1] and len(delimiter[1]) >= len(fence) and not delimiter[2].strip():
                fence = b""
        elif delimiter:
            fence = delimiter[1]
        elif start <= offset and offset + len(line) <= end and not text.lstrip().startswith(b">"):
            result.append(text.decode("utf-8"))
        offset += len(line)
    return result


def ratification_dates(line: str) -> list[str | None]:
    if any(char in line for char in '?`"') or re.search(r"\b(?:not|never|false|revok\w*|question\w*|example\w*|counterexample\w*|unratified|denied)\b", line, re.IGNORECASE):
        return []
    dated = re.fullmatch(r"Ratified by ZF on (\d{4}-\d{2}-\d{2})(?:[ \t]+[^?\r\n]+)?\.", line)
    if dated is not None:
        return [dated[1]]
    if re.fullmatch(r"ZF (?:subsequently )?ratified STREAM\.md(?:\.|, accepted [^?\r\n]+\.)", line):
        return [None]
    return []


def validate_authority(sources: dict[str, dict], recovery: RecoveryInput) -> tuple[dict, bytes, str | None]:
    from engine import artifacts

    try:
        authority = recovery["legacy_authority"]
        if not isinstance(authority, dict) or set(authority) != {"marker", "evidence", "instruction_date"}:
            raise ValueError("legacy authority requires exact marker, evidence and instruction_date fields")
        current = raw_source(sources["STREAM.md"])
        if not current:
            raise ValueError("current STREAM authority is empty")
        current_lines = literal_lines(current, 0, len(current))
        if REVOKED.search("\n".join(current_lines)):
            raise ValueError("current STREAM explicitly revokes ratification")
        current_markers = [line for line in current_lines if line.startswith("ratified:")]
        if any(line.strip().lower() not in {"ratified: yes", "ratified: true"} and not artifacts.has_ratified_authority_line(line) for line in current_markers):
            raise ValueError("current STREAM authority is negative or unratified; an ancestor cannot override it")
        def span(item: dict) -> bytes:
            if set(item) != {"source", "start", "end", "sha256", "text"} or item["source"] == "STATE.md":
                raise ValueError("STATE cannot supply legacy authority or corroboration")
            raw = raw_source(sources[item["source"]])
            start, end = item["start"], item["end"]
            if type(start) is not int or type(end) is not int or not 0 <= start < end <= len(raw):
                raise ValueError("invalid legacy witness span")
            part = raw[start:end]
            if part.decode("utf-8") != item["text"] or sha(part) != item["sha256"]:
                raise ValueError("legacy witness span or hash changed")
            literal_lines(raw, start, end)
            context = part.decode("utf-8")
            if REVOKED.search(context):
                raise ValueError("retained source contradicts or revokes ratification")
            return part
        marker_span = authority["marker"]
        source = marker_span["source"]
        if source != "STREAM.md" and source not in {name for name, record in recovery["supplemental_sources"].items() if record["source_kind"] == "git-blob"}:
            raise ValueError("legacy marker must come from current or ancestor Git STREAM")
        marker = span(marker_span)
        original = raw_source(sources[source])
        if (len(marker.splitlines()) != 1 or (marker_span["start"] and original[marker_span["start"] - 1:marker_span["start"]] != b"\n")
                or (marker_span["end"] < len(original) and not marker.endswith(b"\n"))):
            raise ValueError("legacy marker must be an exact complete source line")
        if marker.decode("utf-8").rstrip("\r\n") not in literal_lines(original, marker_span["start"], marker_span["end"]):
            raise ValueError("legacy marker is quoted or fenced, not an active source line")
        dated = artifacts.has_ratified_authority_line(marker.decode("utf-8"))
        if not dated and marker.strip().lower() not in {b"ratified: yes", b"ratified: true"}:
            raise ValueError("legacy authority cannot promote an unratified source")
        if not current_markers and (source == "STREAM.md" or re.match(rb"ratified:[ \t]+\d{4}-\d{2}-\d{2}(?:[.T \t])", marker) is None):
            raise ValueError("a missing current marker requires the exact dated ancestor STREAM authority")
        if not isinstance(authority["evidence"], list) or not authority["evidence"]:
            raise ValueError("legacy authority requires corroborating source spans")
        proofs = []
        for item in authority["evidence"]:
            span(item)
            raw = raw_source(sources[item["source"]])
            proofs.extend(date for line in literal_lines(raw, item["start"], item["end"]) for date in ratification_dates(line))
        if not dated and not proofs:
            raise ValueError("bare legacy authority requires a complete affirmative, unquoted ratification statement")
        dates = {date for date in proofs if date is not None}
        for line in (marker, *(line.encode() for line in current_markers)):
            match = re.match(rb"ratified:[ \t]+(\d{4}-\d{2}-\d{2})(?:[.T \t])", line)
            if match is not None:
                dates.add(match[1].decode())
        from datetime import date as Date
        for date in dates:
            Date.fromisoformat(date)
        if len(dates) > 1:
            raise ValueError("ratification statements disagree on the instruction date")
        date = next(iter(dates), None)
        declared = authority["instruction_date"]
        if declared is not None and (not isinstance(declared, str) or declared != date):
            raise ValueError("instruction date must derive from the actual ratification statement or marker")
        return marker_span, marker, date
    except (KeyError, TypeError, ValueError, AttributeError) as exc:
        raise StreamsError(f"invalid legacy authority: {exc}") from exc


def witness(root: Path, sources: dict, recovery: RecoveryInput) -> tuple[str, bytes, str]:
    _, _, date = validate_authority({**sources, **validate_sources(root, recovery, fresh=False)}, recovery)
    raw = canonical({"version": 1, "root": str(root), "sources": sources, "recovery_sources": recovery})
    identity = sha(raw)
    line = f"ratified: retained-source-v1 SHA256 {identity} instruction-date {date or 'unknown'}; documentary provenance, not transport authentication or new work authority\n"
    return f"history/recovery-{identity}.json", raw, line


def has_authority(root: Path, line: str) -> bool:
    from engine.migration import regular_bytes

    match = MARKER.fullmatch(line)
    if match is None:
        return False
    try:
        if (root / "history").is_symlink():
            return False
        raw = regular_bytes(root / f"history/recovery-{match[1]}.json")
        if sha(raw) != match[1]:
            return False
        document = json.loads(raw)
        if set(document) != {"version", "root", "sources", "recovery_sources"} or document["version"] != 1 or document["root"] != str(root.resolve()):
            return False
        sources = document["sources"]
        if not {"STREAM.md", "STATE.md"} <= set(sources) <= CURRENT:
            return False
        for record in sources.values():
            raw_source(record)
        validate_sources(root, document["recovery_sources"], fresh=True)
        operation = json.loads(regular_bytes(root / "log/migration.json"))
        plan = operation.get("plan", {})
        commit = operation.get("commit")
        if (operation.get("version") != 1 or operation.get("root") != str(root.resolve()) or operation.get("phase") != "complete"
                or plan.get("sources") != sources or plan.get("recovery_sources") != document["recovery_sources"]
                or not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None):
            return False
        git(root, "merge-base", "--is-ancestor", commit, "HEAD")
        if git_blob(root, f"{commit}:history/recovery-{match[1]}.json") != raw:
            return False
        installed = git_blob(root, f"{commit}:STATE.md").splitlines(keepends=True)
        if len(installed) < 2 or installed[1].decode("utf-8") != line:
            return False
        return witness(root, sources, document["recovery_sources"])[2] == line
    except (StreamsError, OSError, ValueError, KeyError, TypeError, AttributeError):
        return False

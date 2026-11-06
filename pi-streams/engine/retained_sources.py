from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from datetime import datetime
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


class RecoveryInput(TypedDict):
    version: Literal[2]
    supplemental_sources: dict[str, GitSource | RetainedFile]


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
        if (not isinstance(recovery, dict) or set(recovery) != {"version", "supplemental_sources"}
                or type(recovery["version"]) is not int or recovery["version"] != 2
                or not isinstance(recovery["supplemental_sources"], dict)):
            raise ValueError("expected documentary recovery-sources version 2; authority, dates and caller trust labels are not accepted")
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
                if entry not in {f"100644 blob {record['blob_oid']}\tSTREAM.md", f"100755 blob {record['blob_oid']}\tSTREAM.md"}:
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
        raise StreamsError(f"invalid documentary recovery sources: {exc}") from exc


def legacy_authority_line(line: str) -> bool:
    if len(line.splitlines()) != 1:
        return False
    match = re.fullmatch(r"ratified:[ \t]+(\S+)[ \t]+(.+)", line.rstrip("\r\n"))
    if match is None:
        return False
    reference, provenance = match.groups()
    if reference.casefold() == "zf":
        return re.fullmatch(r"notice[ \t]+\S.*", provenance, re.IGNORECASE) is not None
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}\.", reference):
        reference = reference[:-1]
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}(?:T\S+)?", reference) is None:
        return False
    try:
        stamp = datetime.fromisoformat(reference)
    except ValueError:
        return False
    return bool(provenance.strip()) and ("T" not in reference or stamp.tzinfo is not None)


def current_authority(sources: dict[str, dict]) -> dict:
    source = "STREAM.md"
    raw = raw_source(sources[source])
    line = raw.splitlines(keepends=True)[0] if raw else b""
    validated = legacy_authority_line(line.decode("utf-8"))
    after = line if validated or line.strip().lower() == b"ratified: no" else b"ratified: no\n"
    if not after.endswith(b"\n"):
        after += b"\n"
    return {"source": source, "source_sha256": sources[source]["sha256"],
            "before": base64.b64encode(line).decode(), "before_sha256": sha(line),
            "validated": validated, "after": base64.b64encode(after).decode(), "after_sha256": sha(after)}


def repair_policy(root: Path, sources: dict, recovery: RecoveryInput, identity: str, mapping: tuple, state: bytes | None) -> dict:
    authority = current_authority(sources)
    contracts = {"STREAM.md": sources["STREAM.md"]["sha256"], **{name: record["sha256"] for name, record in recovery["supplemental_sources"].items()}}
    return {"version": 1, "policy": "preserve-current-authority-no-prose-ratification-v1", "root": str(root),
            "plan_id": identity, "current_authority": authority, "original_contract_hashes": contracts,
            "mapping_sha256": sha(canonical(mapping)), "target_sha256": sha(state) if state is not None else None,
            "scope": "Source-preserving structural repair only; documentary prose supplies no execution authority or instruction date."}


def repair_record(root: Path, sources: dict, recovery: RecoveryInput, identity: str, mapping: tuple, state: bytes) -> tuple[str, bytes]:
    policy = repair_policy(root, sources, recovery, identity, mapping, state)
    raw = canonical({"version": 2, "root": str(root), "sources": sources, "recovery_sources": recovery, "repair_policy": policy})
    return f"history/recovery-{sha(raw)}.json", raw

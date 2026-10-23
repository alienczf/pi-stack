from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
from dataclasses import asdict, dataclass
from pathlib import Path

from engine import StreamsError, artifacts, clock
from engine.project import git, git_blob, load_stream_config

SOURCES = ("STREAM.md", "DECISIONS.md", "STATE.md")
TARGETS = frozenset({"ratified", "north_star", "current_objective", "charter", "rules", "history"})


def encoded(data: bytes) -> str:
    return base64.b64encode(data).decode("ascii")


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def regular_bytes(path: Path) -> bytes:
    descriptor = None
    try:
        if not stat.S_ISREG(path.lstat().st_mode):
            raise StreamsError(f"migration source must be a regular file, not a symlink: {path}")
        descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
        before = os.fstat(descriptor)
        if not stat.S_ISREG(before.st_mode):
            raise StreamsError(f"migration source is not regular: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            data = handle.read()
        after = os.fstat(descriptor)
        if (before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns) != (after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns):
            raise StreamsError(f"migration source changed while reading: {path}")
        return data
    except OSError as exc:
        raise StreamsError(f"migration source unavailable: {path}: {exc}") from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)


@dataclass(frozen=True)
class MigrationPlan:
    id: str
    root: str
    started_at: str
    sources: dict[str, dict]
    config: dict
    mapping: tuple[dict, ...]
    history: tuple[dict, ...]
    unresolved: tuple[dict, ...]
    state: str | None

    @property
    def ready(self) -> bool:
        return not self.unresolved and self.state is not None

    def public(self) -> dict:
        return {"version": 1, **asdict(self), "ready": self.ready}


def state_parts(data: bytes) -> list[tuple[int, int]]:
    starts = [0]
    offset = 0
    fence = b""
    for line in data.splitlines(keepends=True):
        text = line.rstrip(b"\r\n")
        marker = re.fullmatch(rb" {0,3}(`{3,}|~{3,})(.*)", text)
        if fence:
            if marker and marker[1][:1] == fence[:1] and len(marker[1]) >= len(fence) and not marker[2].strip():
                fence = b""
        elif marker and not (marker[1][:1] == b"`" and b"`" in marker[2]):
            fence = marker[1]
        elif re.fullmatch(rb" {0,3}##(?:[ \t].*)?", text) and offset:
            starts.append(offset)
        offset += len(line)
    return list(zip(starts, [*starts[1:], len(data)]))


def _versions(root: Path, name: str) -> list[tuple[str, bytes, str]]:
    try:
        commits = git(root, "log", "--reverse", "--format=%H", "--", name).splitlines()
    except StreamsError:
        return []
    result = []
    for commit in commits:
        try:
            data = git_blob(root, f"{commit}:{name}")
            at = clock.parse(git(root, "show", "-s", "--format=%cI", commit).strip())
            if at is not None:
                result.append((commit, data, clock.stamp(at)))
        except StreamsError:
            continue
    return result


def _history(root: Path, sources: dict[str, dict], at: str) -> tuple[dict, ...]:
    result = []
    for name, source in sources.items():
        raw = base64.b64decode(source["bytes"])
        spans = state_parts(raw) if name == "STATE.md" else [(0, len(raw))]
        versions = _versions(root, name)
        for occurrence, (start, end) in enumerate(spans, 1):
            part = raw[start:end]
            introduced = None
            if sum(raw[a:b] == part for a, b in spans) == 1:
                for commit, old, timestamp in versions:
                    old_parts = state_parts(old) if name == "STATE.md" else [(0, len(old))]
                    if sum(old[a:b] == part for a, b in old_parts) == 1:
                        introduced = (commit, timestamp)
                        break
            timestamp = introduced[1] if introduced else at
            slug = timestamp.replace(":", "").replace("-", "")
            path = f"history/{slug}-legacy-{name[:-3].lower()}-{occurrence:04d}-{digest(part)[:16]}.md"
            destination = root / path
            if destination.exists() or destination.is_symlink():
                if regular_bytes(destination) != part:
                    raise StreamsError(f"migration history collision: {path}")
            result.append({"source": name, "start": start, "end": end, "occurrence": occurrence, "path": path, "bytes": encoded(part), "sha256": digest(part), "at": timestamp, "time_source": "git-exact-entry-introduction" if introduced else "migration-start-fallback", "git_commit": introduced[0] if introduced else None})
    return tuple(result)


def _mapping(sources: dict[str, dict], mapping: list[dict] | None) -> tuple[tuple[dict, ...], list[dict]]:
    rows = []
    for item in mapping or []:
        if not isinstance(item, dict) or set(item) != {"source", "start", "end", "target"}:
            raise StreamsError("migration mapping requires exact source/start/end/target fields")
        name, start, end, target = (item[key] for key in ("source", "start", "end", "target"))
        if not isinstance(name, str) or not isinstance(target, str) or name not in sources or name == "STATE.md" or target not in TARGETS:
            raise StreamsError("migration mapping has an unsupported source or target")
        size = len(base64.b64decode(sources[name]["bytes"]))
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= size:
            raise StreamsError("migration mapping has an invalid source byte span")
        rows.append(dict(item))
    unresolved = []
    for name, source in sources.items():
        if name == "STATE.md":
            continue
        offset = 0
        for item in sorted((row for row in rows if row["source"] == name), key=lambda row: row["start"]):
            if item["start"] < offset:
                raise StreamsError(f"migration mapping overlaps in {name}")
            if item["start"] > offset:
                unresolved.append({"source": name, "start": offset, "end": item["start"], "target": "unresolved", "reason": "explicit authority/history classification required"})
            offset = item["end"]
        size = len(base64.b64decode(source["bytes"]))
        if offset < size:
            unresolved.append({"source": name, "start": offset, "end": size, "target": "unresolved", "reason": "explicit authority/history classification required"})
    return tuple(rows), unresolved


def _state(sources: dict[str, dict], mapping: tuple[dict, ...], identity: str, at: str, count: int) -> bytes:
    def fragments(target: str) -> list[bytes]:
        return [base64.b64decode(sources[row["source"]]["bytes"])[row["start"]:row["end"]] for row in mapping if row["target"] == target]

    authority = [row for row in mapping if row["target"] == "ratified"]
    stars, objectives = fragments("north_star"), fragments("current_objective")
    if len(authority) != 1 or authority[0]["source"] != "STREAM.md" or authority[0]["start"] != 0 or len(stars) != 1 or len(objectives) > 1:
        raise StreamsError("migration requires one first-line STREAM authority, one North Star and at most one current objective")
    marker = fragments("ratified")[0]
    if len(marker.splitlines()) != 1 or not marker.startswith(b"ratified: ") or marker.rstrip().lower() in (b"ratified: yes", b"ratified: true", b"ratified: 1"):
        raise StreamsError("migration authority must retain an unambiguous source-bearing ratified marker or no")
    def body(parts: list[bytes]) -> bytes:
        return b"".join(part if part.endswith(b"\n") else part + b"\n" for part in parts)
    state = (b"## Goals\n" + body([marker]) + b"\n### North Star\n" + body(stars) + b"\n### Current objective\n" + body(objectives)
             + b"\n### Charter\n" + body(fragments("charter")) + b"\n## Rules\n" + body(fragments("rules"))
             + f"\n## Log\n### {at} Stream artifact migration\nMigration {identity}. Retained exact legacy sources and {count} ordered STATE occurrences. Provenance is retained by the engine; history snapshots remain available on demand.\n".encode())
    artifacts.parse_state(state)
    return state


def plan_migration(stream: Path, mapping: list[dict] | None = None, *, started_at: str | None = None) -> MigrationPlan:
    if stream.is_symlink() or not stream.is_dir():
        raise StreamsError("migration requires a real selected stream root, not a symlink")
    root = stream.resolve()
    for name in ("history", "failures"):
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise StreamsError(f"migration {name} must be an owned directory")
    for name in ("GOAL.md", "ACTIONS.md"):
        if (root / name).exists() or (root / name).is_symlink():
            raise StreamsError(f"unknown intermediate authority {name}; explicit source-backed rollout decision required")
    config_bytes = regular_bytes(root / "stream.toml")
    config = {"bytes": encoded(config_bytes), "sha256": digest(config_bytes)}
    if load_stream_config(root / "stream.toml").state_schema != 0:
        raise StreamsError("migration planning requires an unmigrated legacy stream")
    timestamp = clock.parse(started_at) if started_at is not None else clock.now()
    if timestamp is None:
        raise StreamsError("invalid migration start timestamp")
    at = clock.stamp(timestamp)
    try:
        head = git(root, "rev-parse", "--verify", "HEAD").strip()
    except StreamsError:
        head = ""
    sources = {}
    for name in SOURCES:
        path = root / name
        if name == "DECISIONS.md" and not path.exists() and not path.is_symlink():
            continue
        raw = regular_bytes(path)
        try:
            raw.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StreamsError(f"legacy {name} is not UTF-8; no lossy migration is permitted") from exc
        if b"\0" in raw:
            raise StreamsError(f"legacy {name} contains binary data; no lossy migration is permitted")
        sources[name] = {"bytes": encoded(raw), "sha256": digest(raw), "git_head": head}
    rows, unresolved = _mapping(sources, mapping)
    seed = {"root": str(root), "started_at": at, "sources": sources, "config": config, "mapping": rows}
    identity = digest(json.dumps(seed, sort_keys=True, separators=(",", ":")).encode())
    history = _history(root, sources, at)
    state = None
    if not unresolved:
        try:
            state = encoded(_state(sources, rows, identity, at, sum(part["source"] == "STATE.md" for part in history)))
        except StreamsError as exc:
            unresolved.append({"source": "STREAM.md", "start": 0, "end": len(base64.b64decode(sources["STREAM.md"]["bytes"])), "target": "unresolved", "reason": str(exc)})
    return MigrationPlan(identity, str(root), at, sources, config, rows, history, tuple(unresolved), state)

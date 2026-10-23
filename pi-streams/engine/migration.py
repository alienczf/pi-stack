from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import stat
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path

from engine import StreamsError, artifacts, clock
from engine.project import _sync_directory, _write, commit_repo, git, git_blob, load_stream_config, templates_dir

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
    if marker.rstrip().lower() != b"ratified: no" and not artifacts.has_ratified_authority_line(marker.decode("utf-8")):
        raise StreamsError("migration authority must retain dated source provenance or an explicit ZF notice reference, or remain ratified: no")
    def body(parts: list[bytes]) -> bytes:
        return b"".join(part if part.endswith(b"\n") else part + b"\n" for part in parts)
    state = (b"## Goals\n" + body([marker]) + b"\n### North Star\n" + body(stars) + b"\n### Current objective\n" + body(objectives)
             + b"\n### Charter\n" + body(fragments("charter")) + b"\n## Rules\n" + body(fragments("rules"))
             + f"\n## Log\n### {artifacts._timestamp(at)} Stream artifact migration\nMigration {identity}. Retained exact legacy sources and {count} ordered STATE occurrences. Provenance is retained by the engine; history snapshots remain available on demand.\n".encode())
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


def _json(value: object) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def _restore_plan(root: Path, document: dict) -> MigrationPlan:
    try:
        if document["version"] != 1 or document["root"] != str(root) or not document["ready"] or document["unresolved"]:
            raise ValueError("wrong root, version or unresolved authority")
        sources, config = document["sources"], document["config"]
        if not {"STREAM.md", "STATE.md"} <= set(sources) <= set(SOURCES):
            raise ValueError("unexpected legacy source")
        for record in [*sources.values(), config]:
            raw = artifacts._decode_bytes(record["bytes"])
            if digest(raw) != record["sha256"]:
                raise ValueError("source hash mismatch")
        rows, unresolved = _mapping(sources, document["mapping"])
        if unresolved:
            raise ValueError("unresolved mapping")
        at = clock.stamp(clock.parse(document["started_at"]))
        seed = {"root": str(root), "started_at": at, "sources": sources, "config": config, "mapping": rows}
        identity = digest(_json(seed).encode())
        history = []
        for name in SOURCES:
            if name not in sources:
                continue
            source = sources[name]
            raw = artifacts._decode_bytes(source["bytes"])
            spans = state_parts(raw) if name == "STATE.md" else [(0, len(raw))]
            for occurrence, (start, end) in enumerate(spans, 1):
                part = document["history"][len(history)]
                content = raw[start:end]
                timestamp = part["at"]
                expected = {"source": name, "start": start, "end": end, "occurrence": occurrence, "bytes": encoded(content), "sha256": digest(content)}
                if any(part[key] != value for key, value in expected.items()):
                    raise ValueError("history does not reconstruct exact ordered sources")
                slug = timestamp.replace(":", "").replace("-", "")
                if part["path"] != f"history/{slug}-legacy-{name[:-3].lower()}-{occurrence:04d}-{digest(content)[:16]}.md":
                    raise ValueError("unsafe history destination")
                if part["time_source"] == "migration-start-fallback":
                    if timestamp != at or part["git_commit"] is not None:
                        raise ValueError("invalid fallback time")
                elif part["time_source"] == "git-exact-entry-introduction":
                    commit = part["git_commit"]
                    if not isinstance(commit, str) or re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", commit) is None:
                        raise ValueError("invalid Git provenance")
                    old = git_blob(root, f"{commit}:{name}")
                    old_spans = state_parts(old) if name == "STATE.md" else [(0, len(old))]
                    if sum(old[a:b] == content for a, b in old_spans) != 1 or clock.stamp(clock.parse(git(root, "show", "-s", "--format=%cI", commit).strip())) != timestamp:
                        raise ValueError("Git introduction provenance changed")
                else:
                    raise ValueError("unknown history time provenance")
                history.append(part)
        state = encoded(_state(sources, rows, identity, at, sum(item["source"] == "STATE.md" for item in history)))
        restored = MigrationPlan(identity, str(root), at, sources, config, rows, tuple(history), (), state)
        if _json(restored.public()) != _json(document):
            raise ValueError("plan changed or has unsupported fields")
        return restored
    except (KeyError, TypeError, ValueError, IndexError, AttributeError) as exc:
        raise StreamsError(f"invalid migration plan: {exc}") from exc


def _new_config(raw: bytes, identity: str) -> bytes:
    parsed = tomllib.loads(raw.decode())
    if "migration_id" in parsed:
        raise StreamsError("stream already declares a migration identity")
    body = raw
    if "state_schema" in parsed:
        matches = list(re.finditer(rb"(?m)^state_schema[ \t]*=[ \t]*0[ \t]*(?:#[^\n]*)?\r?\n?", raw))
        if len(matches) != 1 or any(token in raw[:matches[0].start()] for token in (b"[", b'"""', b"'''")):
            raise StreamsError("complex legacy schema field requires explicit rollout reconciliation")
        body = raw[:matches[0].start()] + raw[matches[0].end():]
    after = f'state_schema = 1\nmigration_id = "{identity}"\n'.encode() + body
    if tomllib.loads(after.decode()) != {**parsed, "state_schema": 1, "migration_id": identity}:
        raise StreamsError("migration schema update would change unrelated configuration")
    return after


def _ignore_after(before: bytes | None) -> bytes:
    raw = before or b""
    if raw.endswith(b"log/\n"):
        return raw
    return raw + (b"\n" if raw and not raw.endswith(b"\n") else b"") + b"log/\n"


def _set_phase(root: Path, operation: dict, phase: str) -> None:
    operation["phase"] = phase
    _write(root / "log/migration.json", json.dumps(operation, sort_keys=True, indent=2) + "\n")


def _scope(plan: MigrationPlan) -> tuple[str, ...]:
    return tuple(sorted({*plan.sources, "stream.toml", ".gitignore", "failures/.gitkeep", *(part["path"] for part in plan.history)}))


def _seed_book(plan: MigrationPlan) -> dict:
    state = artifacts.parse_state(artifacts._decode_bytes(plan.state))
    raw = state.source[state.log.body.start:]
    book = artifacts.LogBook(next_occurrence=2, entries=[artifacts.LogEntry(1, 0, len(raw), digest(raw), artifacts._timestamp(plan.started_at), "Stream artifact migration")], receipts={"migration:" + plan.id: {"intent": digest(raw), "occurrence": 1}})
    artifacts._checked_state(state.source, book)
    return asdict(book)


def _expected(plan: MigrationPlan, operation: dict) -> dict[str, bytes | None]:
    extras = operation["extras"]
    if set(extras) != {".gitignore", "failures/.gitkeep"}:
        raise StreamsError("unexpected migration extra path")
    ignore_before = artifacts._decode_bytes(extras[".gitignore"]["before"]) if extras[".gitignore"]["before"] is not None else None
    if artifacts._decode_bytes(extras[".gitignore"]["after"]) != _ignore_after(ignore_before):
        raise StreamsError("migration ignore snapshot changed")
    marker = extras["failures/.gitkeep"]
    marker_before = artifacts._decode_bytes(marker["before"]) if marker["before"] is not None else None
    if artifacts._decode_bytes(marker["after"]) != (marker_before if marker_before is not None else (templates_dir() / "stream/failures/.gitkeep").read_bytes()):
        raise StreamsError("migration layout marker changed")
    return {**{name: None for name in plan.sources if name != "STATE.md"}, "STATE.md": artifacts._decode_bytes(plan.state), "stream.toml": _new_config(artifacts._decode_bytes(plan.config["bytes"]), plan.id), **{part["path"]: artifacts._decode_bytes(part["bytes"]) for part in plan.history}, **{name: artifacts._decode_bytes(record["after"]) for name, record in extras.items()}}


def _actual(path: Path) -> bytes | None:
    return regular_bytes(path) if path.exists() or path.is_symlink() else None


def _validate_current(root: Path, plan: MigrationPlan, operation: dict, expected: dict) -> None:
    phase = operation["phase"]
    if phase not in ("history", "state", "retire", "commit"):
        raise StreamsError("unknown migration phase")
    for name in ("log", "history", "failures"):
        path = root / name
        if path.is_symlink() or (path.exists() and not path.is_dir()):
            raise StreamsError(f"migration {name} is not an owned directory")
    for name, record in plan.sources.items():
        before = artifacts._decode_bytes(record["bytes"])
        allowed = [before]
        if name == "STATE.md" and phase != "history":
            allowed = [before, expected[name]] if phase == "state" else [expected[name]]
        elif name != "STATE.md" and phase in ("retire", "commit"):
            allowed = [before, None] if phase == "retire" else [None]
        if _actual(root / name) not in allowed:
            raise StreamsError(f"migration source changed unexpectedly: {name}")
    config_before = artifacts._decode_bytes(plan.config["bytes"])
    configs = [config_before, expected["stream.toml"]] if phase == "retire" else [expected["stream.toml"]] if phase == "commit" else [config_before]
    if _actual(root / "stream.toml") not in configs:
        raise StreamsError("migration configuration changed unexpectedly")
    for name, record in operation["extras"].items():
        before = artifacts._decode_bytes(record["before"]) if record["before"] is not None else None
        allowed = (before, expected[name]) if phase == "history" else (expected[name],)
        if _actual(root / name) not in allowed:
            raise StreamsError(f"migration owned layout changed: {name}")
    book = artifacts._read_tick_data(root).get("state_log")
    seed = _seed_book(plan)
    allowed_books = (None,) if phase == "history" else (None, seed) if phase == "state" else (seed,)
    if book not in allowed_books or (book == seed and _actual(root / "STATE.md") != expected["STATE.md"]):
        raise StreamsError("migration Log ownership changed unexpectedly")
    for part in plan.history:
        actual = _actual(root / part["path"])
        if actual != expected[part["path"]] and (actual is not None or phase != "history"):
            raise StreamsError("migration retained history changed or disappeared")


def _own_commit(root: Path, operation: dict, expected: dict, commit: str) -> bool:
    parents = git(root, "rev-list", "--parents", "-n", "1", commit).split()
    if parents[1:] != ([operation["base_head"]] if operation["base_head"] else []):
        return False
    if git(root, "show", "-s", "--format=%s", commit).strip() != operation["message"]:
        return False
    changed = set(git(root, "diff-tree", "--root", "--no-commit-id", "--no-renames", "--name-only", "-r", commit).splitlines())
    if not changed <= set(expected):
        return False
    for name, raw in expected.items():
        tracked = git(root, "ls-tree", "--name-only", commit, "--", name).strip()
        if raw is None:
            if tracked:
                return False
        elif not tracked or git_blob(root, f"{commit}:{name}") != raw:
            return False
    return True


def apply_migration_locked(stream: Path, document: dict | None = None) -> dict:
    if stream.is_symlink() or not (stream / ".git").is_dir() or (stream / ".git").is_symlink():
        raise StreamsError("migration requires its own real stream repository")
    root = stream.resolve()
    journal = root / "log/migration.json"
    if journal.parent.is_symlink():
        raise StreamsError("migration journal directory is symlinked")
    operation = json.loads(regular_bytes(journal)) if journal.exists() or journal.is_symlink() else None
    if operation is None:
        if document is None:
            raise StreamsError("no migration to resume; supply an explicitly reviewed --apply plan")
        plan = _restore_plan(root, document)
        fresh = plan_migration(root, list(plan.mapping), started_at=plan.started_at)
        if _json(fresh.public()) != _json(plan.public()):
            raise StreamsError("migration sources or plan changed before application")
        if artifacts._read_tick_data(root).get("state_log") is not None:
            raise StreamsError("legacy root already has canonical Log ownership; reconcile explicitly")
        staged = set(git(root, "diff", "--cached", "--no-renames", "--name-only").splitlines())
        if staged.intersection(_scope(plan)):
            raise StreamsError("migration overlaps foreign staged edits")
        heads = {source["git_head"] for source in plan.sources.values()}
        if len(heads) != 1:
            raise StreamsError("migration source Git identities disagree")
        extras = {}
        for name in (".gitignore", "failures/.gitkeep"):
            before = _actual(root / name)
            after = _ignore_after(before) if name == ".gitignore" else before if before is not None else (templates_dir() / "stream/failures/.gitkeep").read_bytes()
            after.decode("utf-8")
            if b"\0" in after:
                raise StreamsError("migration layout contains binary data")
            extras[name] = {"before": encoded(before) if before is not None else None, "after": encoded(after)}
        operation = {"version": 1, "root": str(root), "plan": plan.public(), "base_head": next(iter(heads)), "extras": extras, "message": f"pi-streams migrate {root.name} {plan.id}"}
        _expected(plan, operation)
        _set_phase(root, operation, "history")
    else:
        if not isinstance(operation, dict) or operation.get("version") != 1 or operation.get("root") != str(root):
            raise StreamsError("invalid migration journal identity")
        plan = _restore_plan(root, operation["plan"])
        if document is not None and _json(document) != _json(plan.public()):
            raise StreamsError("a different migration is already recorded")
    expected = _expected(plan, operation)
    if operation["phase"] == "complete":
        current_config = tomllib.loads(regular_bytes(root / "stream.toml").decode())
        if current_config.get("state_schema") != 1 or current_config.get("migration_id") != plan.id:
            raise StreamsError("completed migration schema identity changed")
        if not _own_commit(root, operation, expected, operation["commit"]):
            raise StreamsError("migration completion receipt no longer proves its scoped commit")
        return {"id": plan.id, "commit": operation["commit"], "changed": False}
    _validate_current(root, plan, operation, expected)
    try:
        head = git(root, "rev-parse", "--verify", "HEAD").strip()
    except StreamsError:
        head = ""
    if head != operation["base_head"]:
        if operation["phase"] != "commit" or not _own_commit(root, operation, expected, head):
            raise StreamsError("migration Git parent changed beyond its own recorded transition")
        staged_scope = set(git(root, "diff", "--cached", "--name-only").splitlines()).intersection(_scope(plan))
        if (root / ".git/index.lock").exists() or staged_scope:
            raise StreamsError("migration commit exists but scoped index publication is unconfirmed; reconcile without deleting unknown locks")
        operation["commit"] = head
        _set_phase(root, operation, "complete")
        return {"id": plan.id, "commit": head, "changed": False}
    if operation["phase"] == "history":
        for name in (".gitignore", "failures/.gitkeep"):
            _write(root / name, expected[name].decode())
        for part in plan.history:
            _write(root / part["path"], expected[part["path"]].decode())
        if b"".join(regular_bytes(root / p["path"]) for p in plan.history if p["source"] == "STATE.md") != artifacts._decode_bytes(plan.sources["STATE.md"]["bytes"]):
            raise StreamsError("retained STATE reconstruction does not match its source")
        _sync_directory(root / "history")
        _set_phase(root, operation, "state")
    if operation["phase"] == "state":
        _write(root / "STATE.md", expected["STATE.md"].decode())
        data = artifacts._read_tick_data(root)
        book = _seed_book(plan)
        if data.get("state_log") not in (None, book):
            raise StreamsError("migration Log ownership changed before publication")
        data["state_log"] = book
        artifacts._save_tick_data(root, data)
        _set_phase(root, operation, "retire")
    if operation["phase"] == "retire":
        for name, record in plan.sources.items():
            if name != "STATE.md" and (root / name).exists():
                if regular_bytes(root / name) != artifacts._decode_bytes(record["bytes"]):
                    raise StreamsError(f"migration legacy source changed before retirement: {name}")
                (root / name).unlink()
        _write(root / "stream.toml", expected["stream.toml"].decode())
        _sync_directory(root)
        _set_phase(root, operation, "commit")
    _validate_current(root, plan, operation, expected)
    commit_repo(root, operation["message"], paths=_scope(plan), scope_only=True)
    committed = git(root, "rev-parse", "HEAD").strip()
    if not _own_commit(root, operation, expected, committed):
        raise StreamsError("migration commit publication is unconfirmed")
    operation["commit"] = committed
    _set_phase(root, operation, "complete")
    return {"id": plan.id, "commit": committed, "changed": True}

#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import socket
import stat
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

SCHEMA_VERSION = 2
MANIFEST_PATH = ".pi/jig/manifest.json"
PROFILE_PATH = ".pi/jig/profile.json"
LOCK_PATH = ".pi/jig/init.lock"
STAGING_PATH = ".pi/jig/principles/staging.json"
CANDIDATE_PATH = ".pi/jig/principles/candidate.md"
ANSWERS_PATH = ".pi/jig/principles/answers.input.json"
PRINCIPLE_PATH = ".cursor/skills/principle-repository/SKILL.md"
PI_SETTINGS_PATH = ".pi/settings.json"
PI_CURSOR_SKILLS_PATH = "../.cursor/skills"
PSTACK_CREATE_SKILL = "pstack/skills/create-verification-skill/SKILL.md"
PSTACK_MAINTAIN_SKILL = "pstack/skills/maintain-verification-skill/SKILL.md"
MAX_INPUT_BYTES = 256 * 1024
MAX_TEXT = 4000
MAX_OS_PID = (1 << 31) - 1
STATES = {
    "surveying",
    "awaiting-principles",
    "verification-building",
    "configured",
    "failed-surveying",
    "failed-awaiting-principles",
    "failed-verification-building",
}
ACTIVE_STATES = {"surveying", "awaiting-principles", "verification-building"}
STATE_EDGES = {
    ("absent", "surveying"),
    ("surveying", "awaiting-principles"),
    ("awaiting-principles", "verification-building"),
    ("verification-building", "configured"),
}
VERIFICATION_PATH = re.compile(r"^\.cursor/skills/verify-[a-z0-9][a-z0-9-]{0,55}/SKILL\.md$")
SKILL_NAME = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
REVISION = re.compile(r"^[0-9a-f]{40,64}$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")


class JigError(Exception):
    pass


class ValidationError(JigError):
    pass


def now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def read_json_bytes(raw: bytes, label: str) -> Any:
    if not raw or len(raw) > MAX_INPUT_BYTES:
        raise ValidationError(f"{label} is empty or too large")
    try:
        value = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{label} is not valid UTF-8 JSON") from error
    return value


def resolve_git_root() -> Path:
    try:
        output = subprocess.check_output(
            ["git", "rev-parse", "--show-toplevel"],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise JigError("jig init must run inside one Git repository") from error
    root = Path(output).resolve()
    if not root.is_dir():
        raise JigError("the resolved Git root is not a directory")
    return root


def git_output(root: Path, *arguments: str) -> str:
    try:
        return subprocess.check_output(
            ["git", "-C", str(root), *arguments],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError) as error:
        raise JigError(f"git {' '.join(arguments)} failed") from error


def source_record(root: Path) -> Dict[str, Any]:
    revision = git_output(root, "rev-parse", "HEAD")
    if not REVISION.fullmatch(revision):
        raise JigError("the repository has no valid HEAD revision")
    status = subprocess.run(
        [
            "git",
            "-C",
            str(root),
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude).pi/jig",
            f":(exclude){PI_SETTINGS_PATH}",
            f":(exclude){PRINCIPLE_PATH}",
            ":(exclude,glob).cursor/skills/verify-*/**",
        ],
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    if status.returncode != 0:
        raise JigError("git status failed")
    lines = sorted(line for line in status.stdout.splitlines() if line)
    return {"revision": revision, "dirty": bool(lines), "statusSummary": lines}


def repository_identity(root: Path) -> str:
    git_dir = Path(git_output(root, "rev-parse", "--absolute-git-dir"))
    common_value = Path(git_output(root, "rev-parse", "--git-common-dir"))
    common_dir = common_value if common_value.is_absolute() else root / common_value
    material = f"{git_dir.resolve()}\0{common_dir.resolve()}".encode("utf-8")
    return sha256_bytes(material)


def process_start(pid: int) -> Optional[str]:
    path = Path("/proc") / str(pid) / "stat"
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError:
        return None
    close = raw.rfind(")")
    fields = raw[close + 2 :].split() if close >= 0 else []
    return fields[19] if len(fields) > 19 else None


def safe_relative_path(
    root: Path,
    value: str,
    *,
    must_exist: bool = False,
    create_parent: bool = False,
    allow_owned_symlink: bool = False,
) -> Path:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValidationError("artifact path is invalid")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValidationError(f"artifact path is not a contained relative path: {value}")
    current = root
    parts = list(candidate.parts)
    for index, part in enumerate(parts):
        current = current / part
        if current.exists() or current.is_symlink():
            mode = current.lstat().st_mode
            final = index == len(parts) - 1
            if stat.S_ISLNK(mode) and not (final and allow_owned_symlink):
                raise ValidationError(f"artifact path crosses a symlink: {value}")
            if not final and not stat.S_ISDIR(mode):
                raise ValidationError(f"artifact path has a non-directory ancestor: {value}")
        elif create_parent and index < len(parts) - 1:
            continue
    resolved = current.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValidationError(f"artifact path escapes the Git root: {value}") from error
    if must_exist and not current.exists():
        raise ValidationError(f"artifact path is missing: {value}")
    return current


def read_contained_bytes(root: Path, value: str, label: str) -> bytes:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValidationError(f"{label} path is not contained")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValidationError(f"{label} path is not contained")
    descriptors = []
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(root, os.O_RDONLY | directory | nofollow)
        descriptors.append(descriptor)
        for part in candidate.parts[:-1]:
            descriptor = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=descriptor)
            descriptors.append(descriptor)
        descriptor = os.open(
            candidate.parts[-1],
            os.O_RDONLY | os.O_NONBLOCK | nofollow,
            dir_fd=descriptor,
        )
        descriptors.append(descriptor)
        metadata = os.fstat(descriptor)
        if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > MAX_INPUT_BYTES:
            raise ValidationError(f"{label} is not a bounded regular file")
        chunks = []
        total = 0
        while True:
            chunk = os.read(descriptor, min(65536, MAX_INPUT_BYTES + 1 - total))
            if not chunk:
                break
            chunks.append(chunk)
            total += len(chunk)
            if total > MAX_INPUT_BYTES:
                raise ValidationError(f"{label} exceeds {MAX_INPUT_BYTES} bytes")
        return b"".join(chunks)
    except ValidationError:
        raise
    except OSError as error:
        raise ValidationError(f"{label} is not a contained regular file") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def read_contained_json(root: Path, value: str, label: str) -> Any:
    return read_json_bytes(read_contained_bytes(root, value, label), label)


def unlink_contained(root: Path, value: str, *, missing_ok: bool = False) -> None:
    candidate = Path(value)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValidationError("unlink path is not contained")
    descriptors = []
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    try:
        descriptor = os.open(root, os.O_RDONLY | directory | nofollow)
        descriptors.append(descriptor)
        for part in candidate.parts[:-1]:
            descriptor = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=descriptor)
            descriptors.append(descriptor)
        os.unlink(candidate.parts[-1], dir_fd=descriptor)
        os.fsync(descriptor)
    except FileNotFoundError:
        if not missing_ok:
            raise ValidationError(f"contained path is missing: {value}")
    except OSError as error:
        raise JigError(f"unlink path is unsafe: {value}") from error
    finally:
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def open_contained_directory(root: Path, value: str) -> int:
    candidate = Path(value)
    if candidate.is_absolute() or not candidate.parts or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValidationError("controller directory path is not contained")
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    current = None
    try:
        current = os.open(root, os.O_RDONLY | directory | nofollow)
        for part in candidate.parts:
            try:
                child = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=current)
            except FileNotFoundError:
                os.mkdir(part, mode=0o755, dir_fd=current)
                os.fsync(current)
                child = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=current)
            os.close(current)
            current = child
        result = current
        current = None
        return result
    except ValidationError:
        raise
    except OSError as error:
        raise JigError(f"controller directory is unsafe: {value}") from error
    finally:
        if current is not None:
            os.close(current)


def atomic_write(root: Path, value: str, raw: bytes, mode: int = 0o644) -> None:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise ValidationError("atomic-write path is not contained")
    candidate = Path(value)
    if candidate.is_absolute() or any(part in {"", ".", ".."} for part in candidate.parts):
        raise ValidationError("atomic-write path is not contained")
    descriptors = []
    temporary = f".jigctl.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    nofollow = getattr(os, "O_NOFOLLOW", 0)
    directory = getattr(os, "O_DIRECTORY", 0)
    parent_descriptor = None
    try:
        parent_descriptor = os.open(root, os.O_RDONLY | directory | nofollow)
        descriptors.append(parent_descriptor)
        for part in candidate.parts[:-1]:
            try:
                child = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=parent_descriptor)
            except FileNotFoundError:
                os.mkdir(part, mode=0o755, dir_fd=parent_descriptor)
                os.fsync(parent_descriptor)
                child = os.open(part, os.O_RDONLY | directory | nofollow, dir_fd=parent_descriptor)
            descriptors.append(child)
            parent_descriptor = child
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            mode,
            dir_fd=parent_descriptor,
        )
        try:
            offset = 0
            while offset < len(raw):
                offset += os.write(descriptor, raw[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        os.replace(
            temporary,
            candidate.parts[-1],
            src_dir_fd=parent_descriptor,
            dst_dir_fd=parent_descriptor,
        )
        os.fsync(parent_descriptor)
    except ValidationError:
        raise
    except OSError as error:
        raise JigError(f"atomic-write path is unsafe: {value}") from error
    finally:
        if parent_descriptor is not None:
            try:
                os.unlink(temporary, dir_fd=parent_descriptor)
            except FileNotFoundError:
                pass
        for descriptor in reversed(descriptors):
            os.close(descriptor)


def atomic_json(root: Path, value: str, document: Any) -> str:
    raw = canonical_json(document)
    atomic_write(root, value, raw)
    return sha256_bytes(raw)


class RepositoryLock:
    FIELDS = {"schemaVersion", "pid", "host", "processStart", "token", "acquiredAt"}
    LOCK_NAME = "init.lock"

    def __init__(self, root: Path):
        self.root = root
        self.directory_descriptor: Optional[int] = None
        self.token = uuid.uuid4().hex
        self.owner = {
            "schemaVersion": 1,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "processStart": process_start(os.getpid()),
            "token": self.token,
            "acquiredAt": now(),
        }

    def _directory(self) -> int:
        if self.directory_descriptor is None:
            raise JigError("the init lock directory is not open")
        return self.directory_descriptor

    def _publish_owner(self) -> None:
        directory = self._directory()
        temporary = f".init.lock.{self.token}.tmp"
        nofollow = getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(
            temporary,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | nofollow,
            0o600,
            dir_fd=directory,
        )
        try:
            raw = canonical_json(self.owner)
            offset = 0
            while offset < len(raw):
                offset += os.write(descriptor, raw[offset:])
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        try:
            os.link(
                temporary,
                self.LOCK_NAME,
                src_dir_fd=directory,
                dst_dir_fd=directory,
                follow_symlinks=False,
            )
            os.fsync(directory)
        finally:
            try:
                os.unlink(temporary, dir_fd=directory)
            except FileNotFoundError:
                pass

    def _snapshot_at(self, directory: int, name: str, label: str) -> Tuple[bytes, Tuple[int, int]]:
        flags = os.O_RDONLY | os.O_NONBLOCK | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(name, flags, dir_fd=directory)
        except OSError as error:
            raise JigError(f"{label} is not a contained regular file") from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise JigError(f"{label} is not a contained regular file")
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, min(65536, MAX_INPUT_BYTES + 1 - total))
                if not chunk:
                    break
                total += len(chunk)
                if total > MAX_INPUT_BYTES:
                    raise JigError(f"{label} exceeds {MAX_INPUT_BYTES} bytes")
                chunks.append(chunk)
            return b"".join(chunks), (metadata.st_dev, metadata.st_ino)
        finally:
            os.close(descriptor)

    def _validate_holder(self, value: Any) -> Mapping[str, Any]:
        if not isinstance(value, dict) or set(value) != self.FIELDS:
            raise JigError("the init lock record has an invalid shape")
        pid = value.get("pid")
        host = value.get("host")
        started = value.get("processStart")
        token = value.get("token")
        acquired = value.get("acquiredAt")
        if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1:
            raise JigError("the init lock record has an unsupported version")
        if type(pid) is not int or pid <= 0 or pid > MAX_OS_PID:
            raise JigError("the init lock record has an invalid PID")
        if not isinstance(host, str) or not host or len(host) > 255:
            raise JigError("the init lock record has an invalid host")
        if started is not None and (not isinstance(started, str) or not started.isdigit()):
            raise JigError("the init lock record has an invalid process start")
        if not isinstance(token, str) or not re.fullmatch(r"[0-9a-f]{32}", token):
            raise JigError("the init lock record has an invalid token")
        try:
            parsed = datetime.fromisoformat(acquired.replace("Z", "+00:00"))
        except (AttributeError, ValueError) as error:
            raise JigError("the init lock record has an invalid acquisition time") from error
        if parsed.tzinfo is None:
            raise JigError("the init lock record has an invalid acquisition time")
        return value

    def _stale(self, value: Mapping[str, Any]) -> bool:
        if value["host"] != socket.gethostname():
            return False
        pid = value["pid"]
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except (PermissionError, OSError):
            return False
        current = process_start(pid)
        expected = value["processStart"]
        return current is not None and expected is not None and current != expected

    def _unlink_snapshot(self, raw: bytes, identity: Tuple[int, int]) -> None:
        directory = self._directory()
        current, current_identity = self._snapshot_at(directory, self.LOCK_NAME, "init lock")
        if current != raw or current_identity != identity:
            raise JigError("the init lock changed during stale-owner reconciliation")
        os.unlink(self.LOCK_NAME, dir_fd=directory)
        os.fsync(directory)

    def _preserve_stale(self, raw: bytes, identity: Tuple[int, int]) -> None:
        directory = self._directory()
        receipts = open_contained_directory(self.root, ".pi/jig/receipts")
        evidence = f"lock-reclaimed-{sha256_bytes(raw)[:16]}.json"
        try:
            try:
                os.link(
                    self.LOCK_NAME,
                    evidence,
                    src_dir_fd=directory,
                    dst_dir_fd=receipts,
                    follow_symlinks=False,
                )
                os.fsync(receipts)
            except FileExistsError:
                existing, _ = self._snapshot_at(receipts, evidence, "stale-lock evidence")
                if existing != raw:
                    raise JigError("stale-lock evidence collides with a different file")
        finally:
            os.close(receipts)
        self._unlink_snapshot(raw, identity)

    def __enter__(self) -> "RepositoryLock":
        self.directory_descriptor = open_contained_directory(self.root, ".pi/jig")
        try:
            try:
                self._publish_owner()
                return self
            except FileExistsError:
                pass
            raw, identity = self._snapshot_at(self._directory(), self.LOCK_NAME, "init lock")
            try:
                holder = self._validate_holder(read_json_bytes(raw, "init lock"))
            except (ValidationError, JigError) as error:
                raise JigError(
                    "the init lock owner is uncertain; preserve .pi/jig/init.lock and inspect it"
                ) from error
            if not self._stale(holder):
                raise JigError("the init lock has a live or uncertain owner; wait for it to finish")
            self._preserve_stale(raw, identity)
            try:
                self._publish_owner()
            except FileExistsError as error:
                raise JigError("another init acquired the lock during stale-owner reconciliation") from error
            return self
        except BaseException:
            os.close(self._directory())
            self.directory_descriptor = None
            raise

    def __exit__(self, exc_type: Any, exc: Any, traceback: Any) -> None:
        try:
            directory = self._directory()
            raw, identity = self._snapshot_at(directory, self.LOCK_NAME, "init lock")
            holder = self._validate_holder(read_json_bytes(raw, "init lock"))
            if holder["token"] == self.token:
                self._unlink_snapshot(raw, identity)
        except (ValidationError, JigError, OSError):
            pass
        finally:
            if self.directory_descriptor is not None:
                os.close(self.directory_descriptor)
                self.directory_descriptor = None


def validate_source(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict) or set(value) != {"revision", "dirty", "statusSummary"}:
        raise ValidationError("manifest source has the wrong shape")
    revision = value["revision"]
    status = value["statusSummary"]
    if not isinstance(revision, str) or not REVISION.fullmatch(revision):
        raise ValidationError("manifest source revision is invalid")
    if not isinstance(value["dirty"], bool) or not isinstance(status, list):
        raise ValidationError("manifest source status is invalid")
    if any(not isinstance(item, str) or not item for item in status) or status != sorted(set(status)):
        raise ValidationError("manifest source status summary is invalid")
    return dict(value)


def valid_state_edge(source: str, target: str) -> bool:
    if (source, target) in STATE_EDGES:
        return True
    if source in ACTIVE_STATES and target == f"failed-{source}":
        return True
    return source.startswith("failed-") and target == source.removeprefix("failed-")


def validate_manifest(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        raise ValidationError("manifest is not an object")
    schema = value.get("schemaVersion")
    if schema == 1:
        raise ValidationError(
            "unsupported legacy Jig v1 campaign; preserve .pi/jig and its worktrees, "
            "then archive or migrate it explicitly before running Jig v2"
        )
    required = {
        "schemaVersion",
        "repository",
        "source",
        "principle",
        "verification",
        "currentState",
        "resourceIsolation",
        "transitions",
        "artifacts",
        "tools",
        "createdAt",
        "updatedAt",
    }
    if schema != SCHEMA_VERSION or set(value) != required:
        raise ValidationError("manifest has the wrong v2 shape")
    repository = value["repository"]
    if repository != {"root": ".", "scope": "repository", "identity": repository.get("identity") if isinstance(repository, dict) else None}:
        raise ValidationError("manifest repository record is invalid")
    if not isinstance(repository.get("identity"), str) or not SHA256.fullmatch(repository["identity"]):
        raise ValidationError("manifest repository identity is invalid")
    validate_source(value["source"])
    principle = value["principle"]
    if not isinstance(principle, dict) or set(principle) != {"path", "sha256", "version", "ratifiedAt"}:
        raise ValidationError("manifest principle record is invalid")
    if principle["path"] != PRINCIPLE_PATH:
        raise ValidationError("manifest principle path is invalid")
    verification = value["verification"]
    if verification is not None:
        if not isinstance(verification, dict) or set(verification) != {
            "skillPath", "sha256", "createdBy", "maintainedBy", "completedAt"
        }:
            raise ValidationError("manifest verification record is invalid")
        if not VERIFICATION_PATH.fullmatch(verification["skillPath"]):
            raise ValidationError("manifest verification skill path is invalid")
        if not SHA256.fullmatch(verification["sha256"]):
            raise ValidationError("manifest verification hash is invalid")
        if verification["createdBy"] != PSTACK_CREATE_SKILL or verification["maintainedBy"] != PSTACK_MAINTAIN_SKILL:
            raise ValidationError("manifest verification ownership is invalid")
    state = value["currentState"]
    if state not in STATES:
        raise ValidationError("manifest state is invalid")
    if value["resourceIsolation"] not in {"isolated-shell", "inherited-session"}:
        raise ValidationError("manifest isolation is invalid")
    if not isinstance(value["transitions"], list) or not isinstance(value["artifacts"], list):
        raise ValidationError("manifest transition or artifact list is invalid")
    previous = None
    for index, item in enumerate(value["transitions"]):
        if not isinstance(item, dict) or set(item) != {
            "from", "to", "at", "receiptPath", "receiptSha256"
        }:
            raise ValidationError("manifest transition has the wrong shape")
        if item["from"] not in STATES | {"absent"} or item["to"] not in STATES:
            raise ValidationError("manifest transition names an invalid state")
        if not valid_state_edge(item["from"], item["to"]):
            raise ValidationError("manifest transition is outside the v2 state graph")
        if index == 0 and item["from"] != "absent":
            raise ValidationError("manifest transition history does not start at absent")
        if previous is not None and item["from"] != previous:
            raise ValidationError("manifest transition history is not contiguous")
        if (
            not isinstance(item["receiptPath"], str)
            or not item["receiptPath"].startswith(".pi/jig/receipts/")
            or not isinstance(item["receiptSha256"], str)
            or not SHA256.fullmatch(item["receiptSha256"])
            or not isinstance(item["at"], str)
            or not item["at"]
        ):
            raise ValidationError("manifest transition receipt is invalid")
        previous = item["to"]
    if previous is not None and previous != state:
        raise ValidationError("manifest state differs from its transition history")
    artifact_paths = []
    for item in value["artifacts"]:
        if (
            not isinstance(item, dict)
            or set(item) != {"path", "owner", "sha256"}
            or not isinstance(item["path"], str)
            or not item["path"]
            or item["owner"] not in {"human", "controller", "jig-skill", "repository"}
            or not isinstance(item["sha256"], str)
            or not SHA256.fullmatch(item["sha256"])
        ):
            raise ValidationError("manifest artifact record is invalid")
        artifact_paths.append(item["path"])
    if artifact_paths != sorted(set(artifact_paths)):
        raise ValidationError("manifest artifact paths are duplicated or unsorted")
    artifacts_by_path = {item["path"]: item for item in value["artifacts"]}
    receipt_paths = []
    for transition_item in value["transitions"]:
        receipt_path = transition_item["receiptPath"]
        receipt_paths.append(receipt_path)
        artifact = artifacts_by_path.get(receipt_path)
        if (
            artifact is None
            or artifact["owner"] != "controller"
            or artifact["sha256"] != transition_item["receiptSha256"]
        ):
            raise ValidationError("manifest transition receipt is not linked to its controller artifact")
    if len(receipt_paths) != len(set(receipt_paths)):
        raise ValidationError("manifest transition receipt paths are duplicated")
    if (
        not isinstance(value["tools"], dict)
        or set(value["tools"]) != {"jig", "pi", "python"}
        or any(not isinstance(item, str) or not item for item in value["tools"].values())
        or not isinstance(value["createdAt"], str)
        or not isinstance(value["updatedAt"], str)
    ):
        raise ValidationError("manifest tool or timestamp metadata is invalid")
    if state in {"verification-building", "configured", "failed-verification-building"}:
        if not isinstance(principle["sha256"], str) or not SHA256.fullmatch(principle["sha256"]):
            raise ValidationError("ratified state lacks a principle hash")
        if not isinstance(principle["version"], int) or principle["version"] < 1 or not principle["ratifiedAt"]:
            raise ValidationError("ratified state lacks principle metadata")
    else:
        if any(principle[key] is not None for key in ("sha256", "version", "ratifiedAt")):
            raise ValidationError("unratified state contains principle metadata")
    if state == "configured" and verification is None:
        raise ValidationError("configured state lacks a verification skill")
    if state != "configured" and verification is not None:
        raise ValidationError("non-configured state contains a verification skill")
    return dict(value)


def load_manifest(root: Path) -> Dict[str, Any]:
    manifest = validate_manifest(read_contained_json(root, MANIFEST_PATH, "Jig manifest"))
    if manifest["repository"]["identity"] != repository_identity(root):
        raise ValidationError("Jig manifest belongs to a different Git repository")
    if manifest["source"] != source_record(root):
        raise ValidationError("repository source revision or dirty summary changed after surveying")
    for artifact in manifest["artifacts"]:
        if artifact["owner"] not in {"controller", "human", "jig-skill"}:
            continue
        artifact_raw = read_contained_bytes(root, artifact["path"], f"manifest artifact {artifact['path']}")
        if sha256_bytes(artifact_raw) != artifact["sha256"]:
            raise ValidationError(f"manifest artifact changed: {artifact['path']}")
    return manifest


def write_manifest(root: Path, manifest: Dict[str, Any]) -> None:
    manifest["updatedAt"] = now()
    validate_manifest(manifest)
    atomic_json(root, MANIFEST_PATH, manifest)


def new_manifest(root: Path, isolation: str) -> Dict[str, Any]:
    created = now()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "repository": {"root": ".", "identity": repository_identity(root), "scope": "repository"},
        "source": source_record(root),
        "principle": {"path": PRINCIPLE_PATH, "sha256": None, "version": None, "ratifiedAt": None},
        "verification": None,
        "currentState": "surveying",
        "resourceIsolation": isolation,
        "transitions": [],
        "artifacts": [],
        "tools": {
            "jig": "2",
            "pi": os.environ.get("JIG_PI_VERSION", "unknown"),
            "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        },
        "createdAt": created,
        "updatedAt": created,
    }


def upsert_artifact(manifest: Dict[str, Any], path: str, owner: str, digest: str) -> None:
    record = {"path": path, "owner": owner, "sha256": digest}
    matches = [item for item in manifest["artifacts"] if item["path"] == path]
    if matches:
        manifest["artifacts"][manifest["artifacts"].index(matches[0])] = record
    else:
        manifest["artifacts"].append(record)
    manifest["artifacts"].sort(key=lambda item: item["path"])


def transition(root: Path, manifest: Dict[str, Any], target: str, kind: str, details: Mapping[str, Any]) -> None:
    source = manifest["currentState"]
    if not valid_state_edge(source, target):
        raise ValidationError(f"invalid Jig transition {source} -> {target}")
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": kind,
        "from": source,
        "to": target,
        "at": now(),
        "details": dict(details),
    }
    index = len(manifest["transitions"]) + 1
    receipt_path = f".pi/jig/receipts/{index:04d}-{kind}.json"
    safe_relative_path(root, receipt_path, create_parent=True)
    digest = atomic_json(root, receipt_path, receipt)
    manifest["transitions"].append(
        {"from": source, "to": target, "at": receipt["at"], "receiptPath": receipt_path, "receiptSha256": digest}
    )
    upsert_artifact(manifest, receipt_path, "controller", digest)
    manifest["currentState"] = target


def require_isolation(manifest: Mapping[str, Any], isolation: str) -> None:
    if manifest["resourceIsolation"] != isolation:
        expected = manifest["resourceIsolation"]
        recovery = "jig init" if expected == "isolated-shell" else "/skill:jig init or /jig init"
        raise ValidationError(f"route mismatch: campaign is {expected}; resume with {recovery}")


def recover_failed(root: Path, manifest: Dict[str, Any]) -> Dict[str, Any]:
    state = manifest["currentState"]
    if not state.startswith("failed-"):
        return manifest
    target = state.removeprefix("failed-")
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "failed-state-retried",
        "from": state,
        "to": target,
        "at": now(),
        "details": {},
    }
    index = len(manifest["transitions"]) + 1
    receipt_path = f".pi/jig/receipts/{index:04d}-failed-state-retried.json"
    safe_relative_path(root, receipt_path, create_parent=True)
    digest = atomic_json(root, receipt_path, receipt)
    manifest["transitions"].append(
        {"from": state, "to": target, "at": receipt["at"], "receiptPath": receipt_path, "receiptSha256": digest}
    )
    upsert_artifact(manifest, receipt_path, "controller", digest)
    manifest["currentState"] = target
    write_manifest(root, manifest)
    return manifest


def start(root: Path, isolation: str) -> Dict[str, Any]:
    path = root / MANIFEST_PATH
    if path.exists() or path.is_symlink():
        manifest = load_manifest(root)
        require_isolation(manifest, isolation)
        manifest = recover_failed(root, manifest)
        if manifest["currentState"] == "configured":
            validate_configured(root, manifest)
        return manifest
    manifest = new_manifest(root, isolation)
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "campaign-started",
        "from": "absent",
        "to": "surveying",
        "at": now(),
        "details": {"resourceIsolation": isolation, "sourceRevision": manifest["source"]["revision"]},
    }
    receipt_path = ".pi/jig/receipts/0001-campaign-started.json"
    safe_relative_path(root, receipt_path, create_parent=True)
    digest = atomic_json(root, receipt_path, receipt)
    manifest["transitions"].append(
        {"from": "absent", "to": "surveying", "at": receipt["at"], "receiptPath": receipt_path, "receiptSha256": digest}
    )
    upsert_artifact(manifest, receipt_path, "controller", digest)
    write_manifest(root, manifest)
    return manifest


def evidence_paths(profile: Mapping[str, Any]) -> Iterable[str]:
    for key in ("productType", "entryPoints", "existingPolicies"):
        value = profile.get(key)
        items = value if isinstance(value, list) else [value]
        for item in items:
            if isinstance(item, dict):
                for evidence in item.get("evidence", []):
                    if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                        yield evidence["path"]


def validate_profile(root: Path, value: Any, revision: str) -> Dict[str, Any]:
    required = {"schemaVersion", "repositoryRevision", "productType", "entryPoints", "existingPolicies", "unknowns"}
    if not isinstance(value, dict) or set(value) != required or value["schemaVersion"] != SCHEMA_VERSION:
        raise ValidationError("repository profile has the wrong v2 shape")
    if value["repositoryRevision"] != revision:
        raise ValidationError("repository profile revision differs from the campaign source")
    if not isinstance(value["productType"], dict) or not isinstance(value["entryPoints"], list):
        raise ValidationError("repository profile observations are invalid")
    if not isinstance(value["existingPolicies"], list) or not isinstance(value["unknowns"], list):
        raise ValidationError("repository profile policy observations are invalid")
    observations = [value["productType"], *value["entryPoints"], *value["existingPolicies"]]
    for observation in observations:
        if (
            not isinstance(observation, dict)
            or set(observation) != {"value", "evidence"}
            or not isinstance(observation["evidence"], list)
            or not observation["evidence"]
        ):
            raise ValidationError("repository profile observation has the wrong shape")
        bounded_text(observation["value"], "profile observation", limit=2000)
        for evidence in observation["evidence"]:
            if (
                not isinstance(evidence, dict)
                or set(evidence) != {"path", "line", "note"}
                or not isinstance(evidence["line"], int)
                or isinstance(evidence["line"], bool)
                or evidence["line"] < 1
            ):
                raise ValidationError("repository profile evidence has the wrong shape")
            bounded_text(evidence["path"], "profile evidence path", limit=1000)
            bounded_text(evidence["note"], "profile evidence note", limit=2000)
    for unknown in value["unknowns"]:
        if not isinstance(unknown, dict) or set(unknown) != {"question", "reason"}:
            raise ValidationError("repository profile unknown has the wrong shape")
        bounded_text(unknown["question"], "profile unknown question", limit=2000)
        bounded_text(unknown["reason"], "profile unknown reason", limit=2000)
    for relative in evidence_paths(value):
        path = safe_relative_path(root, relative, must_exist=True)
        if not path.is_file() or path.is_symlink():
            raise ValidationError(f"profile evidence is not a regular file: {relative}")
    return dict(value)


def commit_profile(root: Path, isolation: str, raw: bytes) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] == "awaiting-principles":
        return manifest
    if manifest["currentState"] != "surveying":
        raise ValidationError("profile can only be committed while surveying")
    profile = validate_profile(root, read_json_bytes(raw, "repository profile"), manifest["source"]["revision"])
    safe_relative_path(root, PROFILE_PATH, create_parent=True)
    digest = atomic_json(root, PROFILE_PATH, profile)
    upsert_artifact(manifest, PROFILE_PATH, "jig-skill", digest)
    transition(root, manifest, "awaiting-principles", "profile-committed", {"profileSha256": digest})
    write_manifest(root, manifest)
    return manifest


def bounded_text(value: Any, label: str, *, allow_empty: bool = False, limit: int = MAX_TEXT) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    if not allow_empty and not value.strip():
        raise ValidationError(f"{label} is empty")
    if len(value) > limit or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValidationError(f"{label} is too large or contains control characters")
    return value


def text_list(value: Any, label: str, *, minimum: int = 1) -> List[str]:
    if not isinstance(value, list) or len(value) < minimum:
        raise ValidationError(f"{label} must contain at least {minimum} item")
    result = [bounded_text(item, label, limit=1000) for item in value]
    if len(result) != len(set(result)):
        raise ValidationError(f"{label} contains duplicates")
    return result


def validate_answers(value: Any) -> Dict[str, Any]:
    required = {
        "schemaVersion",
        "protectedUserPaths",
        "forbiddenOutcomes",
        "compatibilityPolicy",
        "priorityTradeoffs",
        "authority",
        "freeTextAmendments",
    }
    if not isinstance(value, dict) or set(value) != required or value["schemaVersion"] != SCHEMA_VERSION:
        raise ValidationError("repository principle answers have the wrong v2 shape")
    protected = value["protectedUserPaths"]
    if not isinstance(protected, list) or not protected:
        raise ValidationError("protectedUserPaths must contain at least one path")
    normalized_paths = []
    for item in protected:
        if not isinstance(item, dict) or set(item) != {"name", "action", "visibleResult", "thresholds"}:
            raise ValidationError("a protected user path has the wrong shape")
        normalized_paths.append({key: bounded_text(item[key], f"protectedUserPaths.{key}", limit=2000) for key in item})
    authority = value["authority"]
    if not isinstance(authority, dict) or set(authority) != {
        "owner", "exceptions", "amendmentPolicy", "ratificationMarker"
    }:
        raise ValidationError("authority has the wrong shape")
    normalized_authority = {
        "owner": bounded_text(authority["owner"], "authority.owner", limit=500),
        "exceptions": text_list(authority["exceptions"], "authority.exceptions"),
        "amendmentPolicy": bounded_text(authority["amendmentPolicy"], "authority.amendmentPolicy", limit=2000),
        "ratificationMarker": bounded_text(authority["ratificationMarker"], "authority.ratificationMarker", limit=300),
    }
    return {
        "schemaVersion": SCHEMA_VERSION,
        "protectedUserPaths": normalized_paths,
        "forbiddenOutcomes": text_list(value["forbiddenOutcomes"], "forbiddenOutcomes"),
        "compatibilityPolicy": bounded_text(value["compatibilityPolicy"], "compatibilityPolicy"),
        "priorityTradeoffs": text_list(value["priorityTradeoffs"], "priorityTradeoffs"),
        "authority": normalized_authority,
        "freeTextAmendments": bounded_text(value["freeTextAmendments"], "freeTextAmendments", allow_empty=True),
    }


def bullet(value: str) -> str:
    return value.replace("\r", "").replace("\n", " ").strip()


def render_principle(answers: Mapping[str, Any], ratified_at: str, version: int) -> bytes:
    owner = bullet(answers["authority"]["owner"])
    lines = [
        "---",
        "name: principle-repository",
        "description: Repository-specific priorities, protected paths, and constraints. Use for every nontrivial task in this repository after poteto-mode Principles.",
        "disable-model-invocation: false",
        "---",
        "",
        "# Repository Principles",
        "",
        "Status: RATIFIED",
        f"Owner: {owner}",
        f"Ratified at: {ratified_at}",
        f"Version: {version}",
        "",
        "This skill is human-owned. Agents may propose amendments under `.pi/jig/principles/proposals/`. They may not edit this file.",
        "",
        "## Protected user paths",
        "",
    ]
    for index, item in enumerate(answers["protectedUserPaths"], 1):
        lines.extend(
            [
                f"### RP-{100 + index:03d}. {bullet(item['name'])}",
                "",
                f"Action: {bullet(item['action'])}",
                "",
                f"Visible result: {bullet(item['visibleResult'])}",
                "",
                f"Thresholds: {bullet(item['thresholds'])}",
                "",
            ]
        )
    lines.extend(["## Forbidden outcomes", ""])
    for item in answers["forbiddenOutcomes"]:
        lines.append(f"- {bullet(item)}")
    lines.extend(["", "## Compatibility policy", "", answers["compatibilityPolicy"].strip(), "", "## Priority tradeoffs", ""])
    for index, item in enumerate(answers["priorityTradeoffs"], 1):
        lines.append(f"{index}. {bullet(item)}")
    lines.extend(["", "## Authority and exceptions", "", f"Owner: {owner}", "", "Exceptions:"])
    for item in answers["authority"]["exceptions"]:
        lines.append(f"- {bullet(item)}")
    lines.extend(
        [
            "",
            f"Amendment policy: {answers['authority']['amendmentPolicy'].strip()}",
            "",
            "## Interview amendments",
            "",
            answers["freeTextAmendments"].strip() or "None.",
            "",
            "## Ratification",
            "",
            f"Human marker: {bullet(answers['authority']['ratificationMarker'])}",
            "",
        ]
    )
    return "\n".join(lines).encode("utf-8")


def parse_frontmatter(raw: bytes, expected_name: Optional[str] = None) -> Tuple[str, str]:
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError("skill is not UTF-8") from error
    if not text.startswith("---\n") or "\n---\n" not in text[4:]:
        raise ValidationError("skill lacks valid frontmatter")
    frontmatter = text.split("\n---\n", 1)[0].removeprefix("---\n")
    values = {}
    for line in frontmatter.splitlines():
        key, separator, value = line.partition(":")
        if separator:
            values[key.strip()] = value.strip().strip('"')
    name = values.get("name", "")
    description = values.get("description", "")
    if not SKILL_NAME.fullmatch(name) or not description:
        raise ValidationError("skill frontmatter name or description is invalid")
    if expected_name and name != expected_name:
        raise ValidationError(f"skill name must be {expected_name}")
    return name, description


def parse_principle_metadata(raw: bytes) -> Tuple[str, int, str]:
    text = raw.decode("utf-8")
    if not re.search(r"^Status: RATIFIED$", text, re.MULTILINE):
        raise ValidationError("existing repository Principle is not ratified")
    owner = re.search(r"^Owner: (.+)$", text, re.MULTILINE)
    version = re.search(r"^Version: ([1-9][0-9]*)$", text, re.MULTILINE)
    ratified = re.search(r"^Ratified at: (.+)$", text, re.MULTILINE)
    if not owner or not version or not ratified:
        raise ValidationError("existing repository Principle lacks ratification metadata")
    try:
        datetime.fromisoformat(ratified.group(1).replace("Z", "+00:00"))
    except ValueError as error:
        raise ValidationError("existing repository Principle has an invalid ratification time") from error
    return owner.group(1), int(version.group(1)), ratified.group(1)


def present_principles(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] != "awaiting-principles":
        raise ValidationError("principles interview is not available in the current state")
    profile = read_contained_json(root, PROFILE_PATH, "repository profile")
    return {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "repository-principles-interview",
        "observedFacts": profile,
        "questions": [
            {"answerKey": "protectedUserPaths", "prompt": "Which user paths, visible results, and local thresholds must agents protect?"},
            {"answerKey": "forbiddenOutcomes", "prompt": "Which repository-specific outcomes must agents never cause?"},
            {"answerKey": "compatibilityPolicy", "prompt": "Which compatibility breaks are acceptable in this repository?"},
            {"answerKey": "priorityTradeoffs", "prompt": "How should this repository rank its own competing product goals?"},
            {"answerKey": "authority", "prompt": "Who owns exceptions, amendments, and the ratification marker?"},
        ],
        "freeTextAmendments": {"required": False},
        "answersPath": ANSWERS_PATH,
        "existingPrinciple": (root / PRINCIPLE_PATH).is_file(),
    }


def stage_principles(root: Path, isolation: str, raw: bytes, adopt_existing: bool) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] != "awaiting-principles":
        raise ValidationError("principles can only be staged while awaiting principles")
    answers = validate_answers(read_json_bytes(raw, "repository principle answers"))
    answers_raw = canonical_json(answers)
    input_digest = sha256_bytes(answers_raw)
    staging_file = safe_relative_path(root, STAGING_PATH, create_parent=True)
    recorded_paths = {item["path"] for item in manifest["artifacts"]}
    if staging_file.exists() or staging_file.is_symlink():
        if STAGING_PATH not in recorded_paths:
            for relative in (STAGING_PATH, CANDIDATE_PATH, ANSWERS_PATH):
                unlink_contained(root, relative, missing_ok=True)
        else:
            staging = read_contained_json(root, STAGING_PATH, "principle staging record")
            if staging.get("answersSha256") != input_digest or bool(staging.get("adoptedExisting")) != adopt_existing:
                raise ValidationError("different principle answers are already staged; record amend or defer first")
            candidate_raw = read_contained_bytes(root, staging["candidatePath"], "staged principle candidate")
            staged_answers_raw = read_contained_bytes(root, ANSWERS_PATH, "staged principle answers")
            if sha256_bytes(candidate_raw) != staging["candidateSha256"]:
                raise ValidationError("staged principle candidate changed")
            if sha256_bytes(staged_answers_raw) != input_digest:
                raise ValidationError("staged principle answers changed")
            return manifest, staging
    existing = root / PRINCIPLE_PATH
    if adopt_existing:
        if not existing.exists() and not existing.is_symlink():
            raise ValidationError("there is no safe existing repository Principle to adopt")
        candidate_raw = read_contained_bytes(root, PRINCIPLE_PATH, "existing repository Principle")
        parse_frontmatter(candidate_raw, "principle-repository")
        owner, version, ratified_at = parse_principle_metadata(candidate_raw)
    else:
        if existing.exists() or existing.is_symlink():
            raise ValidationError("an existing repository Principle is preserved; use --adopt-existing")
        owner = answers["authority"]["owner"]
        version = 1
        ratified_at = now()
        candidate_raw = render_principle(answers, ratified_at, version)
    safe_relative_path(root, ANSWERS_PATH, create_parent=True)
    atomic_write(root, ANSWERS_PATH, answers_raw)
    safe_relative_path(root, CANDIDATE_PATH, create_parent=True)
    atomic_write(root, CANDIDATE_PATH, candidate_raw)
    candidate_digest = sha256_bytes(candidate_raw)
    staging = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "repository-principle-staging",
        "candidatePath": CANDIDATE_PATH,
        "candidateSha256": candidate_digest,
        "answersSha256": input_digest,
        "intendedMarker": answers["authority"]["ratificationMarker"],
        "owner": owner,
        "version": version,
        "ratifiedAt": ratified_at,
        "adoptedExisting": adopt_existing,
        "stagedAt": now(),
    }
    staging_digest = atomic_json(root, STAGING_PATH, staging)
    upsert_artifact(manifest, ANSWERS_PATH, "human", input_digest)
    upsert_artifact(manifest, CANDIDATE_PATH, "controller", candidate_digest)
    upsert_artifact(manifest, STAGING_PATH, "controller", staging_digest)
    write_manifest(root, manifest)
    return manifest, staging


def record_principles_decision(
    root: Path,
    isolation: str,
    decision: str,
    candidate_sha: str,
    marker: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] != "awaiting-principles":
        raise ValidationError("principle decision is unavailable in the current state")
    staging = read_contained_json(root, STAGING_PATH, "principle staging record")
    if staging["candidateSha256"] != candidate_sha:
        raise ValidationError("principle decision digest differs from the staged candidate")
    marker = bounded_text(marker, "operator marker", limit=300)
    decision_record = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "repository-principle-decision",
        "decision": decision,
        "candidateSha256": candidate_sha,
        "operatorMarker": marker,
        "recordedAt": now(),
    }
    path_value = f".pi/jig/principles/decisions/{time.time_ns()}-{decision}.json"
    safe_relative_path(root, path_value, create_parent=True)
    decision_digest = atomic_json(root, path_value, decision_record)
    upsert_artifact(manifest, path_value, "human", decision_digest)
    if decision == "amend":
        staged_paths = {STAGING_PATH, CANDIDATE_PATH, ANSWERS_PATH}
        manifest["artifacts"] = [item for item in manifest["artifacts"] if item["path"] not in staged_paths]
        write_manifest(root, manifest)
        try:
            for relative in staged_paths:
                unlink_contained(root, relative, missing_ok=True)
        except OSError as error:
            raise JigError("amended principle staging files could not be removed") from error
    else:
        write_manifest(root, manifest)
    return manifest, decision_record


def ratify_principles(root: Path, isolation: str, candidate_sha: str, marker: str) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] in {"verification-building", "configured"}:
        staging = read_contained_json(root, STAGING_PATH, "principle staging record")
        if (
            manifest["principle"]["sha256"] != candidate_sha
            or staging["intendedMarker"] != marker
        ):
            raise ValidationError("repeated ratification differs from the approved digest or marker")
        return manifest
    if manifest["currentState"] != "awaiting-principles":
        raise ValidationError("principles cannot be ratified in the current state")
    staging = read_contained_json(root, STAGING_PATH, "principle staging record")
    if staging["candidateSha256"] != candidate_sha or staging["intendedMarker"] != marker:
        raise ValidationError("ratification does not approve the exact staged digest and marker")
    raw = read_contained_bytes(root, CANDIDATE_PATH, "staged principle candidate")
    if sha256_bytes(raw) != candidate_sha:
        raise ValidationError("staged principle candidate changed")
    parse_frontmatter(raw, "principle-repository")
    target = safe_relative_path(root, PRINCIPLE_PATH, create_parent=True)
    if staging["adoptedExisting"]:
        target_raw = read_contained_bytes(root, PRINCIPLE_PATH, "existing repository Principle")
        if sha256_bytes(target_raw) != candidate_sha:
            raise ValidationError("existing repository Principle changed before ratification")
    else:
        if target.exists() or target.is_symlink():
            target_raw = read_contained_bytes(root, PRINCIPLE_PATH, "repository Principle")
            if sha256_bytes(target_raw) != candidate_sha:
                raise ValidationError("repository Principle appeared or changed after staging")
        else:
            atomic_write(root, PRINCIPLE_PATH, raw)
    upsert_artifact(manifest, PRINCIPLE_PATH, "human", candidate_sha)
    manifest["principle"] = {
        "path": PRINCIPLE_PATH,
        "sha256": candidate_sha,
        "version": staging["version"],
        "ratifiedAt": staging["ratifiedAt"],
    }
    transition(
        root,
        manifest,
        "verification-building",
        "principle-ratified",
        {"principlePath": PRINCIPLE_PATH, "principleSha256": candidate_sha},
    )
    write_manifest(root, manifest)
    return manifest


def merge_pi_settings(root: Path) -> Tuple[str, str]:
    path = safe_relative_path(root, PI_SETTINGS_PATH, create_parent=True)
    if path.exists() or path.is_symlink():
        before_raw = read_contained_bytes(root, PI_SETTINGS_PATH, "Pi project settings")
        value = read_json_bytes(before_raw, "Pi project settings")
        if not isinstance(value, dict):
            raise ValidationError("Pi project settings must be an object")
    else:
        before_raw = b""
        value = {}
    skills = value.get("skills")
    if skills is None:
        skills = []
    if not isinstance(skills, list) or any(not isinstance(item, str) for item in skills):
        raise ValidationError("Pi project settings skills must be a list of paths")
    if PI_CURSOR_SKILLS_PATH not in skills:
        skills.append(PI_CURSOR_SKILLS_PATH)
    value["skills"] = skills
    before = sha256_bytes(before_raw) if before_raw else ""
    raw = (json.dumps(value, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
    if before_raw != raw:
        atomic_write(root, PI_SETTINGS_PATH, raw)
    return before, sha256_bytes(raw)


def verification_skill_paths(root: Path) -> List[str]:
    skills_root = safe_relative_path(root, ".cursor/skills", must_exist=True)
    if skills_root.is_symlink() or not skills_root.is_dir():
        raise ValidationError(".cursor/skills must be a contained directory")
    paths = []
    for child in skills_root.iterdir():
        relative = f".cursor/skills/{child.name}/SKILL.md"
        if VERIFICATION_PATH.fullmatch(relative):
            skill_file = child / "SKILL.md"
            if skill_file.exists() or skill_file.is_symlink():
                paths.append(relative)
    return sorted(paths)


def validate_verification_skill(root: Path, relative: str) -> Tuple[Path, str]:
    if not isinstance(relative, str) or not VERIFICATION_PATH.fullmatch(relative):
        raise ValidationError("verification skill must be .cursor/skills/verify-*/SKILL.md")
    if verification_skill_paths(root) != [relative]:
        raise ValidationError("configuration requires exactly one .cursor/skills/verify-*/SKILL.md")
    path = root / relative
    raw = read_contained_bytes(root, relative, "verification skill")
    name, _ = parse_frontmatter(raw)
    if not name.startswith("verify-"):
        raise ValidationError("verification skill name must start with verify-")
    return path, sha256_bytes(raw)


def complete_configuration(root: Path, isolation: str, raw: bytes) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    value = read_json_bytes(raw, "configuration completion")
    if (
        not isinstance(value, dict)
        or set(value) != {"schemaVersion", "verificationSkillPath"}
        or value["schemaVersion"] != SCHEMA_VERSION
    ):
        raise ValidationError("configuration completion has the wrong v2 shape")
    if manifest["currentState"] == "configured":
        if value["verificationSkillPath"] != manifest["verification"]["skillPath"]:
            raise ValidationError("repeated configuration names a different verification skill")
        _, digest = validate_verification_skill(root, value["verificationSkillPath"])
        merge_pi_settings(root)
        if digest != manifest["verification"]["sha256"]:
            manifest["verification"]["sha256"] = digest
            manifest["verification"]["completedAt"] = now()
            upsert_artifact(manifest, value["verificationSkillPath"], "repository", digest)
            write_manifest(root, manifest)
        validate_configured(root, manifest)
        return manifest
    if manifest["currentState"] != "verification-building":
        raise ValidationError("configuration can only complete after principle ratification")
    _, digest = validate_verification_skill(root, value["verificationSkillPath"])
    merge_pi_settings(root)
    upsert_artifact(manifest, value["verificationSkillPath"], "repository", digest)
    manifest["verification"] = {
        "skillPath": value["verificationSkillPath"],
        "sha256": digest,
        "createdBy": PSTACK_CREATE_SKILL,
        "maintainedBy": PSTACK_MAINTAIN_SKILL,
        "completedAt": now(),
    }
    transition(
        root,
        manifest,
        "configured",
        "repository-configured",
        {
            "principlePath": PRINCIPLE_PATH,
            "verificationSkillPath": value["verificationSkillPath"],
            "piSettingsPath": PI_SETTINGS_PATH,
        },
    )
    write_manifest(root, manifest)
    return manifest


def validate_configured(root: Path, manifest: Dict[str, Any]) -> None:
    principle_raw = read_contained_bytes(root, PRINCIPLE_PATH, "ratified repository Principle")
    if sha256_bytes(principle_raw) != manifest["principle"]["sha256"]:
        raise ValidationError("ratified repository Principle changed")
    parse_frontmatter(principle_raw, "principle-repository")
    verification = manifest["verification"]
    _, digest = validate_verification_skill(root, verification["skillPath"])
    if digest != verification["sha256"]:
        raise ValidationError("configured verification skill changed; run the pstack maintenance skill and reconfigure")
    settings = read_contained_json(root, PI_SETTINGS_PATH, "Pi project settings")
    skills = settings.get("skills") if isinstance(settings, dict) else None
    if (
        not isinstance(skills, list)
        or any(not isinstance(item, str) for item in skills)
        or PI_CURSOR_SKILLS_PATH not in skills
    ):
        raise ValidationError("Pi project settings no longer load .cursor/skills")


def validate_configuration(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] != "configured":
        raise ValidationError("repository is not configured")
    validate_configured(root, manifest)
    return manifest


def record_failure(root: Path, isolation: str, state: str, reason: str) -> Dict[str, Any]:
    manifest = load_manifest(root)
    require_isolation(manifest, isolation)
    if manifest["currentState"] != state or state not in ACTIVE_STATES:
        raise ValidationError("failure state differs from the current active state")
    reason = bounded_text(reason, "failure reason", limit=2000)
    target = f"failed-{state}"
    receipt = {
        "schemaVersion": SCHEMA_VERSION,
        "kind": "phase-failed",
        "from": state,
        "to": target,
        "at": now(),
        "details": {"reason": reason},
    }
    path_value = f".pi/jig/receipts/{len(manifest['transitions']) + 1:04d}-phase-failed.json"
    safe_relative_path(root, path_value, create_parent=True)
    digest = atomic_json(root, path_value, receipt)
    manifest["transitions"].append(
        {"from": state, "to": target, "at": receipt["at"], "receiptPath": path_value, "receiptSha256": digest}
    )
    upsert_artifact(manifest, path_value, "controller", digest)
    manifest["currentState"] = target
    write_manifest(root, manifest)
    return manifest


def render_result(manifest: Mapping[str, Any]) -> None:
    result: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "state": manifest["currentState"],
        "resourceIsolation": manifest["resourceIsolation"],
        "principlePath": PRINCIPLE_PATH,
    }
    if manifest["currentState"] == "awaiting-principles":
        result["next"] = "present-principles"
        result["answersPath"] = ANSWERS_PATH
    elif manifest["currentState"] == "verification-building":
        result["next"] = "run-create-verification-skill"
        result["pstackSkill"] = PSTACK_CREATE_SKILL
    elif manifest["currentState"] == "configured":
        result["outcome"] = "configured"
        result["verification"] = manifest["verification"]
        result["maintenance"] = f"/skill:maintain-verification-skill {manifest['verification']['skillPath']}"
    print(json.dumps(result, sort_keys=True))


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="jigctl.py")
    subparsers = result.add_subparsers(dest="command", required=True)
    commands = {}
    for name in (
        "start",
        "commit-profile",
        "present-principles",
        "stage-principles",
        "record-principles-decision",
        "ratify-principles",
        "complete-configuration",
        "validate-configuration",
        "record-failure",
    ):
        command = subparsers.add_parser(name)
        command.add_argument("--resource-isolation", required=True, choices=("isolated-shell", "inherited-session"))
        commands[name] = command
    commands["stage-principles"].add_argument("--adopt-existing", action="store_true")
    commands["record-principles-decision"].add_argument("--decision", required=True, choices=("amend", "defer"))
    commands["record-principles-decision"].add_argument("--candidate-sha", required=True)
    commands["record-principles-decision"].add_argument("--operator-marker", required=True)
    commands["ratify-principles"].add_argument("--candidate-sha", required=True)
    commands["ratify-principles"].add_argument("--operator-marker", required=True)
    commands["record-failure"].add_argument("--state", required=True, choices=tuple(sorted(ACTIVE_STATES)))
    commands["record-failure"].add_argument("--reason", required=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    root = resolve_git_root()
    output: Optional[Mapping[str, Any]] = None
    with RepositoryLock(root):
        if arguments.command == "start":
            manifest = start(root, arguments.resource_isolation)
        elif arguments.command == "commit-profile":
            manifest = commit_profile(root, arguments.resource_isolation, sys.stdin.buffer.read(MAX_INPUT_BYTES + 1))
        elif arguments.command == "present-principles":
            output = present_principles(root, arguments.resource_isolation)
            manifest = load_manifest(root)
        elif arguments.command == "stage-principles":
            manifest, staging = stage_principles(
                root,
                arguments.resource_isolation,
                sys.stdin.buffer.read(MAX_INPUT_BYTES + 1),
                arguments.adopt_existing,
            )
            output = {"state": manifest["currentState"], **staging}
        elif arguments.command == "record-principles-decision":
            manifest, output = record_principles_decision(
                root,
                arguments.resource_isolation,
                arguments.decision,
                arguments.candidate_sha,
                arguments.operator_marker,
            )
        elif arguments.command == "ratify-principles":
            manifest = ratify_principles(
                root,
                arguments.resource_isolation,
                arguments.candidate_sha,
                arguments.operator_marker,
            )
        elif arguments.command == "complete-configuration":
            manifest = complete_configuration(
                root,
                arguments.resource_isolation,
                sys.stdin.buffer.read(MAX_INPUT_BYTES + 1),
            )
        elif arguments.command == "validate-configuration":
            manifest = validate_configuration(root, arguments.resource_isolation)
        else:
            manifest = record_failure(
                root,
                arguments.resource_isolation,
                arguments.state,
                arguments.reason,
            )
    if output is None:
        render_result(manifest)
    else:
        print(json.dumps(output, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JigError as error:
        print(f"jigctl: {error}", file=sys.stderr)
        print(
            "Recovery: preserve .pi/jig and .cursor/skills, correct the named boundary, and rerun the owning Jig route.",
            file=sys.stderr,
        )
        raise SystemExit(1)

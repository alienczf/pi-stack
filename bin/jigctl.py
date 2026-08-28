#!/usr/bin/env python3
"""Deterministic state controller for Jig init."""

from __future__ import annotations

import argparse
import datetime as dt
import errno
import hashlib
import json
import os
import platform
import re
import socket
import stat
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path, PurePosixPath
from typing import Any, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

JIG_VERSION = "1.0.0"
SCHEMA_VERSION = 1
MAX_INPUT_BYTES = 1024 * 1024
IMPLEMENTED_STATES = {
    "surveying",
    "awaiting-commandments",
    "failed-surveying",
    "failed-awaiting-commandments",
}
SENSITIVE_NAMES = {
    ".env",
    "auth.json",
    "private_key.pem",
    "public_key.pem",
    "id_rsa",
    "id_ed25519",
}


class JigError(Exception):
    """A bounded operator-facing failure."""


class ValidationError(JigError):
    """A schema or semantic validation failure."""


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "null":
        return value is None
    raise ValidationError("schema uses an unsupported type")


def resolve_ref(root_schema: Mapping[str, Any], reference: str) -> Mapping[str, Any]:
    if not reference.startswith("#/"):
        raise ValidationError("schema uses a non-local reference")
    value: Any = root_schema
    for raw_part in reference[2:].split("/"):
        part = raw_part.replace("~1", "/").replace("~0", "~")
        if not isinstance(value, dict) or part not in value:
            raise ValidationError("schema contains an unresolved reference")
        value = value[part]
    if not isinstance(value, dict):
        raise ValidationError("schema reference does not name an object")
    return value


def valid_datetime(value: str) -> bool:
    match = re.fullmatch(
        r"(\d{4})-(\d{2})-(\d{2})[Tt](\d{2}):(\d{2}):(\d{2})"
        r"(?:\.\d+)?(?:[Zz]|([+-])(\d{2}):(\d{2}))",
        value,
    )
    if match is None:
        return False
    year, month, day, hour, minute, second = map(int, match.groups()[:6])
    offset_hour = int(match.group(8) or 0)
    offset_minute = int(match.group(9) or 0)
    try:
        dt.date(year, month, day)
    except ValueError:
        return False
    return (
        hour <= 23
        and minute <= 59
        and second <= 59
        and offset_hour <= 23
        and offset_minute <= 59
    )


def validate_instance(
    instance: Any,
    schema: Mapping[str, Any],
    root_schema: Optional[Mapping[str, Any]] = None,
    location: str = "$",
) -> None:
    root = schema if root_schema is None else root_schema
    if "$ref" in schema:
        validate_instance(instance, resolve_ref(root, schema["$ref"]), root, location)

    if "type" in schema:
        expected = schema["type"]
        accepted = [expected] if isinstance(expected, str) else expected
        if not isinstance(accepted, list) or not all(isinstance(item, str) for item in accepted):
            raise ValidationError("schema has an invalid type rule")
        if not any(type_matches(instance, item) for item in accepted):
            raise ValidationError(f"{location} has the wrong type")

    if "const" in schema and instance != schema["const"]:
        raise ValidationError(f"{location} does not match its required value")
    if "enum" in schema and instance not in schema["enum"]:
        raise ValidationError(f"{location} is not an allowed value")

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if not isinstance(required, list):
            raise ValidationError("schema has an invalid required rule")
        missing = [name for name in required if name not in instance]
        if missing:
            raise ValidationError(f"{location} is missing {missing[0]}")
        properties = schema.get("properties", {})
        if not isinstance(properties, dict):
            raise ValidationError("schema has an invalid properties rule")
        for name, subschema in properties.items():
            if name in instance:
                validate_instance(instance[name], subschema, root, f"{location}.{name}")
        if schema.get("additionalProperties") is False:
            extras = sorted(set(instance) - set(properties))
            if extras:
                raise ValidationError(f"{location} has unexpected property {extras[0]}")

    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            raise ValidationError(f"{location} has too few items")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            raise ValidationError(f"{location} has too many items")
        if schema.get("uniqueItems") is True:
            encoded = [json.dumps(item, sort_keys=True, separators=(",", ":")) for item in instance]
            if len(encoded) != len(set(encoded)):
                raise ValidationError(f"{location} has duplicate items")
        items = schema.get("items")
        if isinstance(items, dict):
            for index, item in enumerate(instance):
                validate_instance(item, items, root, f"{location}[{index}]")
        if "contains" in schema:
            matches = 0
            for item in instance:
                try:
                    validate_instance(item, schema["contains"], root, location)
                    matches += 1
                except ValidationError:
                    pass
            minimum = schema.get("minContains", 1)
            maximum = schema.get("maxContains")
            if matches < minimum or (maximum is not None and matches > maximum):
                raise ValidationError(f"{location} does not satisfy contains")

    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            raise ValidationError(f"{location} is too short")
        if "maxLength" in schema and len(instance) > schema["maxLength"]:
            raise ValidationError(f"{location} is too long")
        if "pattern" in schema and re.search(schema["pattern"], instance) is None:
            raise ValidationError(f"{location} does not match its pattern")
        if schema.get("format") == "date-time" and not valid_datetime(instance):
            raise ValidationError(f"{location} is not a date-time")

    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            raise ValidationError(f"{location} is below its minimum")
        if "maximum" in schema and instance > schema["maximum"]:
            raise ValidationError(f"{location} is above its maximum")

    for subschema in schema.get("allOf", []):
        validate_instance(instance, subschema, root, location)
    if "anyOf" in schema:
        matches = 0
        for subschema in schema["anyOf"]:
            try:
                validate_instance(instance, subschema, root, location)
                matches += 1
            except ValidationError:
                pass
        if matches == 0:
            raise ValidationError(f"{location} does not satisfy any allowed shape")
    if "if" in schema:
        try:
            validate_instance(instance, schema["if"], root, location)
            matched = True
        except ValidationError:
            matched = False
        branch = schema.get("then") if matched else schema.get("else")
        if isinstance(branch, dict):
            validate_instance(instance, branch, root, location)


def read_json_bytes(raw: bytes, label: str) -> Any:
    if not raw:
        raise ValidationError(f"{label} is empty")
    if len(raw) > MAX_INPUT_BYTES:
        raise ValidationError(f"{label} exceeds {MAX_INPUT_BYTES} bytes")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValidationError(f"{label} is not valid UTF-8 JSON") from error


def read_json(path: Path, label: str) -> Any:
    try:
        return read_json_bytes(path.read_bytes(), label)
    except FileNotFoundError as error:
        raise ValidationError(f"{label} is missing") from error
    except OSError as error:
        raise ValidationError(f"{label} cannot be read") from error


def canonical_json(value: Any) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as error:
        raise ValidationError(f"owned artifact {path.name} cannot be hashed") from error


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def run_git(root: Path, arguments: Sequence[str]) -> str:
    result = subprocess.run(
        ["git", "-C", str(root), *arguments],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if result.returncode != 0:
        raise JigError("Git could not inspect the repository")
    return result.stdout.rstrip("\n")


def resolve_git_root() -> Path:
    result = subprocess.run(
        ["git", "rev-parse", "--show-toplevel"],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        raise JigError("cwd is not inside a Git repository")
    root = Path(result.stdout.strip()).resolve()
    if not root.is_dir():
        raise JigError("Git returned an invalid repository root")
    return root


def source_record(root: Path) -> Dict[str, Any]:
    revision = run_git(root, ["rev-parse", "HEAD"])
    if re.fullmatch(r"[0-9a-f]{40,64}", revision) is None:
        raise JigError("the repository has no valid HEAD revision")
    raw_status = run_git(
        root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).pi/jig"],
    )
    summary = [] if not raw_status else raw_status.splitlines()
    return {"revision": revision, "dirty": bool(summary), "statusSummary": summary}


def repository_identity(root: Path) -> str:
    git_dir = Path(run_git(root, ["rev-parse", "--absolute-git-dir"]))
    common_value = Path(run_git(root, ["rev-parse", "--git-common-dir"]))
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


def ensure_owned_directory(root: Path, relative: str) -> Path:
    current = root
    for part in relative.split("/"):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            current.mkdir()
            mode = current.lstat().st_mode
            fsync_directory(current.parent)
        if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
            raise JigError(f"controller directory is unsafe: {relative}")
        try:
            current.resolve().relative_to(root)
        except ValueError as error:
            raise JigError(f"controller directory escapes the Git root: {relative}") from error
    return current


class RepositoryLock:
    FIELDS = {"schemaVersion", "pid", "host", "processStart", "token", "acquiredAt"}

    def __init__(self, root: Path) -> None:
        self.root = root
        self.directory = root / ".pi" / "jig"
        self.path = self.directory / "init.lock"
        self.token = uuid.uuid4().hex
        self.owner = {
            "schemaVersion": 1,
            "pid": os.getpid(),
            "host": socket.gethostname(),
            "processStart": process_start(os.getpid()),
            "token": self.token,
            "acquiredAt": now(),
        }
        self.reclaimed: List[Path] = []

    def _write_owner(self) -> None:
        descriptor = os.open(self.path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            os.write(descriptor, canonical_json(self.owner))
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
        fsync_directory(self.directory)

    def _snapshot(self, path: Path, label: str) -> Tuple[bytes, Tuple[int, int]]:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            descriptor = os.open(path, flags)
        except OSError as error:
            raise JigError(f"{label} is not a contained regular file") from error
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise JigError(f"{label} is not a contained regular file")
            chunks = []
            total = 0
            while True:
                chunk = os.read(descriptor, 65536)
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
        process_start_value = value.get("processStart")
        token = value.get("token")
        acquired_at = value.get("acquiredAt")
        if value.get("schemaVersion") != 1:
            raise JigError("the init lock record has an unsupported version")
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise JigError("the init lock record has an invalid PID")
        if (
            not isinstance(host, str)
            or not host
            or len(host) > 255
            or any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in host)
        ):
            raise JigError("the init lock record has an invalid host")
        if not (
            process_start_value is None
            or (
                isinstance(process_start_value, str)
                and re.fullmatch(r"[0-9]+", process_start_value) is not None
            )
        ):
            raise JigError("the init lock record has an invalid process start")
        if not isinstance(token, str) or re.fullmatch(r"[0-9a-f]{32}", token) is None:
            raise JigError("the init lock record has an invalid token")
        if not isinstance(acquired_at, str) or not valid_datetime(acquired_at):
            raise JigError("the init lock record has an invalid acquisition time")
        return value

    def _stale(self, value: Mapping[str, Any]) -> bool:
        if value["host"] != socket.gethostname():
            return False
        pid = value["pid"]
        expected_start = value["processStart"]
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        except PermissionError:
            return False
        except OSError as error:
            return error.errno == errno.ESRCH
        current_start = process_start(pid)
        return (
            current_start is not None
            and expected_start is not None
            and current_start != expected_start
        )

    def _evidence_matches(self, evidence: Path, raw: bytes) -> bool:
        try:
            existing, _identity = self._snapshot(evidence, "stale-lock evidence")
        except JigError:
            return False
        return existing == raw

    def _unlink_snapshot(self, raw: bytes, identity: Tuple[int, int]) -> None:
        current, current_identity = self._snapshot(self.path, "init lock")
        if current != raw or current_identity != identity:
            raise JigError("the init lock changed during stale-owner reconciliation")
        try:
            self.path.unlink()
        except FileNotFoundError as error:
            raise JigError("the init lock changed during stale-owner reconciliation") from error
        fsync_directory(self.directory)

    def _preserve_stale(self, raw: bytes, identity: Tuple[int, int], evidence: Path) -> None:
        created = False
        try:
            os.link(self.path, evidence, follow_symlinks=False)
            created = True
            fsync_directory(evidence.parent)
        except FileExistsError:
            if not self._evidence_matches(evidence, raw):
                raise JigError(
                    "stale-lock evidence collides with an existing different file; both were preserved"
                )
        except FileNotFoundError as error:
            raise JigError("the init lock changed during stale-owner reconciliation") from error
        if created:
            evidence_raw, evidence_identity = self._snapshot(evidence, "stale-lock evidence")
            if evidence_raw != raw or evidence_identity != identity:
                try:
                    evidence.unlink()
                except OSError:
                    pass
                raise JigError("the init lock changed during stale-owner reconciliation")
        self._unlink_snapshot(raw, identity)

    def acquire(self) -> "RepositoryLock":
        ensure_owned_directory(self.root, ".pi/jig")
        try:
            self._write_owner()
            return self
        except FileExistsError:
            pass
        try:
            raw, identity = self._snapshot(self.path, "init lock")
            holder = self._validate_holder(read_json_bytes(raw, "init lock"))
        except (OSError, ValidationError, JigError) as error:
            raise JigError(
                "the init lock owner is uncertain; preserve .pi/jig/init.lock and inspect it"
            ) from error
        if not self._stale(holder):
            raise JigError("the init lock has a live or uncertain owner; wait for that owner to finish")
        receipts = ensure_owned_directory(self.root, ".pi/jig/receipts")
        evidence = receipts / f"lock-reclaimed-{sha256_bytes(raw)[:16]}.json"
        self._preserve_stale(raw, identity, evidence)
        self.reclaimed.append(evidence)
        try:
            self._write_owner()
        except FileExistsError as error:
            raise JigError("another init acquired the lock during stale-owner reconciliation") from error
        return self

    def release(self) -> None:
        try:
            current = read_json(self.path, "init lock")
            if isinstance(current, dict) and current.get("token") == self.token:
                self.path.unlink()
                fsync_directory(self.directory)
        except (OSError, ValidationError):
            pass

    def __enter__(self) -> "RepositoryLock":
        return self.acquire()

    def __exit__(self, _kind: Any, _value: Any, _traceback: Any) -> None:
        self.release()


def fsync_directory(path: Path) -> None:
    try:
        descriptor = os.open(path, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)


def atomic_write(path: Path, data: bytes) -> None:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise JigError(f"atomic-write parent is unsafe: {path.parent.name}")
    temporary = path.parent / f".jigctl-{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
    finally:
        os.close(descriptor)
    os.replace(temporary, path)
    fsync_directory(path.parent)


def atomic_write_json(path: Path, value: Any, schema: Optional[Mapping[str, Any]] = None) -> None:
    if schema is not None:
        validate_instance(value, schema)
    atomic_write(path, canonical_json(value))


def schema_root() -> Path:
    return Path(__file__).resolve().parent.parent / "skills" / "jig" / "references" / "schemas" / "v1"


def load_schema(name: str) -> Mapping[str, Any]:
    allowed = {"manifest", "profile", "proposal", "result", "selection"}
    if name not in allowed:
        raise ValidationError("schema name is not supported")
    value = read_json(schema_root() / f"{name}.schema.json", f"{name} schema")
    if not isinstance(value, dict):
        raise ValidationError(f"{name} schema is not an object")
    return value


def safe_relative_path(root: Path, value: str, must_exist: bool = False) -> Path:
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or "//" in value
        or any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value)
    ):
        raise ValidationError("artifact path is not a portable repository-relative path")
    raw_parts = value.split("/")
    pure = PurePosixPath(value)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in raw_parts):
        raise ValidationError("artifact path is not a contained repository-relative path")
    if any(part.lower() in SENSITIVE_NAMES for part in pure.parts):
        raise ValidationError("artifact path names protected key material")
    current = root
    for index, part in enumerate(pure.parts):
        current = current / part
        try:
            mode = current.lstat().st_mode
        except FileNotFoundError:
            if must_exist or index < len(pure.parts) - 1:
                raise ValidationError(f"artifact path does not exist: {value}")
            break
        except OSError as error:
            raise ValidationError(f"artifact path cannot be inspected: {value}") from error
        if stat.S_ISLNK(mode):
            raise ValidationError(f"artifact path traverses a symlink: {value}")
        if index < len(pure.parts) - 1 and not stat.S_ISDIR(mode):
            raise ValidationError(f"artifact path has a non-directory ancestor: {value}")
    resolved = current.resolve(strict=False)
    try:
        resolved.relative_to(root)
    except ValueError as error:
        raise ValidationError(f"artifact path escapes the Git root: {value}") from error
    return current


def profile_evidence_paths(profile: Mapping[str, Any]) -> Iterable[str]:
    observations: List[Any] = [profile.get("productType")]
    for key in ("languages", "frameworks", "buildTools", "ci", "entryPoints", "topology"):
        value = profile.get(key, [])
        if isinstance(value, list):
            observations.extend(value)
    for observation in observations:
        if isinstance(observation, dict):
            for evidence in observation.get("evidence", []):
                if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                    yield evidence["path"]
    for failure in profile.get("failureModes", []):
        if isinstance(failure, dict):
            for evidence in failure.get("evidence", []):
                if isinstance(evidence, dict) and isinstance(evidence.get("path"), str):
                    yield evidence["path"]


def validate_profile_semantics(root: Path, profile: Mapping[str, Any], revision: str) -> None:
    if profile.get("repositoryRevision") != revision:
        raise ValidationError("profile repositoryRevision does not match the recorded source revision")
    for path in profile_evidence_paths(profile):
        evidence = safe_relative_path(root, path, must_exist=True)
        try:
            mode = evidence.lstat().st_mode
        except OSError as error:
            raise ValidationError(f"profile evidence cannot be inspected: {path}") from error
        if not stat.S_ISREG(mode):
            raise ValidationError(f"profile evidence is not a regular file: {path}")


def upsert_artifact(manifest: Dict[str, Any], path: str, owner: str, digest: str) -> None:
    artifacts = manifest["artifacts"]
    replacement = {"path": path, "owner": owner, "sha256": digest}
    for index, artifact in enumerate(artifacts):
        if artifact.get("path") == path:
            artifacts[index] = replacement
            return
    artifacts.append(replacement)


def relative_to_root(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def known_receipt_artifacts(root: Path) -> List[Tuple[str, str]]:
    receipts = root / ".pi" / "jig" / "receipts"
    if not receipts.is_dir() or receipts.is_symlink():
        return []
    result = []
    patterns = ("lock-reclaimed-*.json", "interrupted-write-*.bin", "interrupted-transition-*.json")
    for pattern in patterns:
        for path in sorted(receipts.glob(pattern)):
            if path.is_file() and not path.is_symlink():
                result.append((relative_to_root(root, path), sha256_file(path)))
    return result


def reconcile_orphan_transitions(root: Path, manifest: Optional[Mapping[str, Any]]) -> List[Tuple[str, str]]:
    receipts = ensure_owned_directory(root, ".pi/jig/receipts")
    referenced = set() if manifest is None else {item["receiptPath"] for item in manifest["transitions"]}
    recovered = []
    for path in sorted(receipts.glob("transition-*.json")):
        relative = relative_to_root(root, path)
        if relative in referenced or not path.is_file() or path.is_symlink():
            continue
        digest = sha256_file(path)
        destination = receipts / f"interrupted-transition-{digest}.json"
        if destination.exists():
            if sha256_file(destination) != digest:
                raise JigError("interrupted-transition evidence collides with an existing unknown file")
            path.unlink()
        else:
            os.rename(path, destination)
        recovered.append((relative_to_root(root, destination), digest))
    return recovered


def reconcile_temporary_files(root: Path) -> List[Tuple[str, str]]:
    jig_dir = root / ".pi" / "jig"
    if not jig_dir.exists() or jig_dir.is_symlink():
        return []
    receipts = ensure_owned_directory(root, ".pi/jig/receipts")
    reserved = (
        (jig_dir, re.compile(r"\.jigctl-(?:manifest|profile)\.json\.\d+\.[0-9a-f]{32}\.tmp")),
        (receipts, re.compile(r"\.jigctl-transition-\d{4}-[a-z-]+\.json\.\d+\.[0-9a-f]{32}\.tmp")),
    )
    recovered: List[Tuple[str, str]] = []
    for parent, name_pattern in reserved:
        try:
            candidates = sorted(parent.iterdir())
        except OSError as error:
            raise JigError("controller temporary files cannot be inspected") from error
        for path in candidates:
            if name_pattern.fullmatch(path.name) is None:
                continue
            try:
                mode = path.lstat().st_mode
            except OSError as error:
                raise JigError("controller temporary file cannot be inspected") from error
            if not stat.S_ISREG(mode):
                raise JigError("controller temporary file is not a regular file")
            digest = sha256_file(path)
            destination = receipts / f"interrupted-write-{digest}.bin"
            if destination.exists():
                if destination.is_symlink() or not destination.is_file() or sha256_file(destination) != digest:
                    raise JigError("interrupted-write evidence collides with an existing unknown file")
                path.unlink()
            else:
                os.rename(path, destination)
            recovered.append((relative_to_root(root, destination), digest))
    return recovered


def validate_manifest_semantics(root: Path, manifest: Mapping[str, Any], schema: Mapping[str, Any]) -> None:
    validate_instance(manifest, schema)
    state = manifest["currentState"]
    if state not in IMPLEMENTED_STATES:
        raise ValidationError(f"manifest state {state} is outside this controller unit")
    if manifest["repository"]["identity"] != repository_identity(root):
        raise ValidationError("manifest repository identity does not match this Git repository")
    artifacts = manifest["artifacts"]
    artifact_paths = [artifact["path"] for artifact in artifacts]
    if len(artifact_paths) != len(set(artifact_paths)):
        raise ValidationError("manifest has duplicate artifact paths")
    allowed_artifact = re.compile(
        r"^\.pi/jig/(?:profile\.json|receipts/(?:transition-\d{4}-[a-z-]+\.json|"
        r"lock-reclaimed-[0-9a-f]{16}\.json|interrupted-write-[0-9a-f]{64}\.bin|"
        r"interrupted-transition-[0-9a-f]{64}\.json))$"
    )
    for artifact in artifacts:
        artifact_path = artifact["path"]
        if allowed_artifact.fullmatch(artifact_path) is None:
            raise ValidationError(f"manifest names an unknown owned artifact: {artifact_path}")
        expected_owner = "jig-skill" if artifact_path == ".pi/jig/profile.json" else "controller"
        if artifact["owner"] != expected_owner:
            raise ValidationError(f"owned artifact has the wrong owner: {artifact_path}")
        path = safe_relative_path(root, artifact_path, must_exist=True)
        if sha256_file(path) != artifact["sha256"]:
            raise ValidationError(f"owned artifact hash mismatch: {artifact_path}")
    transitions = manifest["transitions"]
    if not transitions or transitions[0]["from"] != "absent":
        raise ValidationError("manifest transition history does not start at absent")
    allowed_edges = {
        ("absent", "surveying"),
        ("surveying", "awaiting-commandments"),
        ("surveying", "failed-surveying"),
        ("awaiting-commandments", "failed-awaiting-commandments"),
        ("failed-surveying", "surveying"),
        ("failed-awaiting-commandments", "awaiting-commandments"),
    }
    previous = "absent"
    receipt_kind = {
        ("absent", "surveying"): "init-started",
        ("surveying", "awaiting-commandments"): "profile-committed",
        ("surveying", "failed-surveying"): "phase-failed",
        ("awaiting-commandments", "failed-awaiting-commandments"): "phase-failed",
        ("failed-surveying", "surveying"): "failed-state-reconciled",
        ("failed-awaiting-commandments", "awaiting-commandments"): "failed-state-reconciled",
    }
    source_status_sha256 = sha256_bytes(canonical_json(manifest["source"]["statusSummary"]))
    for index, transition in enumerate(transitions, start=1):
        edge = (transition["from"], transition["to"])
        if transition["from"] != previous or edge not in allowed_edges:
            raise ValidationError("manifest transition history has an invalid edge")
        expected_path = f".pi/jig/receipts/transition-{index:04d}-{edge[1]}.json"
        if transition["receiptPath"] != expected_path:
            raise ValidationError("transition receipt path does not match the implemented transition")
        receipt_artifact = next(
            (item for item in artifacts if item["path"] == expected_path), None
        )
        if (
            receipt_artifact is None
            or receipt_artifact["owner"] != "controller"
            or receipt_artifact["sha256"] != transition["receiptSha256"]
        ):
            raise ValidationError("transition receipt artifact does not match the manifest")
        receipt = safe_relative_path(root, expected_path, must_exist=True)
        if sha256_file(receipt) != transition["receiptSha256"]:
            raise ValidationError("transition receipt hash mismatch")
        receipt_data = read_json(receipt, "transition receipt")
        kind = receipt_kind[edge]
        expected_values = {
            "schemaVersion": 1,
            "kind": kind,
            "from": edge[0],
            "to": edge[1],
            "at": transition["at"],
            "sourceRevision": manifest["source"]["revision"],
            "sourceDirty": manifest["source"]["dirty"],
            "sourceStatusSha256": source_status_sha256,
        }
        expected_fields = set(expected_values)
        if kind == "profile-committed":
            expected_fields.update({"profilePath", "profileSha256", "commandmentsGenerated"})
        elif kind == "phase-failed":
            expected_fields.add("failureReason")
        if not isinstance(receipt_data, dict) or set(receipt_data) != expected_fields:
            raise ValidationError("transition receipt has an invalid implemented shape")
        if any(receipt_data.get(key) != value for key, value in expected_values.items()):
            raise ValidationError("transition receipt does not match the manifest")
        if kind == "profile-committed":
            profile_artifact = next(
                (item for item in artifacts if item["path"] == ".pi/jig/profile.json"), None
            )
            if (
                receipt_data["profilePath"] != ".pi/jig/profile.json"
                or receipt_data["commandmentsGenerated"] is not False
                or profile_artifact is None
                or receipt_data["profileSha256"] != profile_artifact["sha256"]
            ):
                raise ValidationError("profile transition receipt is inconsistent")
        elif kind == "phase-failed":
            reason = receipt_data["failureReason"]
            if (
                not isinstance(reason, str)
                or not reason.strip()
                or len(reason) > 500
                or "\n" in reason
                or "\r" in reason
            ):
                raise ValidationError("failure transition receipt has an invalid reason")
        previous = transition["to"]
    if previous != state:
        raise ValidationError("manifest currentState does not match its last transition")
    if state in {"awaiting-commandments", "failed-awaiting-commandments"}:
        profile_artifact = next(
            (item for item in artifacts if item["path"] == ".pi/jig/profile.json"),
            None,
        )
        if profile_artifact is None:
            raise ValidationError("awaiting-commandments has no committed profile artifact")
        profile = read_json(root / ".pi" / "jig" / "profile.json", "profile")
        validate_instance(profile, load_schema("profile"))
        validate_profile_semantics(root, profile, manifest["source"]["revision"])


def receipt_value(kind: str, from_state: str, to_state: str, source: Mapping[str, Any], **extra: Any) -> Dict[str, Any]:
    value: Dict[str, Any] = {
        "schemaVersion": 1,
        "kind": kind,
        "from": from_state,
        "to": to_state,
        "at": now(),
        "sourceRevision": source["revision"],
        "sourceDirty": source["dirty"],
        "sourceStatusSha256": sha256_bytes(canonical_json(source["statusSummary"])),
    }
    value.update(extra)
    return value


def append_transition(
    root: Path,
    manifest: Dict[str, Any],
    from_state: str,
    to_state: str,
    kind: str,
    **extra: Any,
) -> None:
    index = len(manifest["transitions"]) + 1
    relative = f".pi/jig/receipts/transition-{index:04d}-{to_state}.json"
    path = safe_relative_path(root, relative)
    receipt = receipt_value(kind, from_state, to_state, manifest["source"], **extra)
    if path.exists():
        raise JigError(f"owned receipt path already exists: {relative}")
    atomic_write_json(path, receipt)
    digest = sha256_file(path)
    manifest["transitions"].append(
        {"from": from_state, "to": to_state, "at": receipt["at"], "receiptPath": relative, "receiptSha256": digest}
    )
    upsert_artifact(manifest, relative, "controller", digest)
    manifest["currentState"] = to_state
    manifest["updatedAt"] = receipt["at"]


def detect_pi_version() -> str:
    override = os.environ.get("JIG_PI_VERSION")
    if override:
        return override
    executable = os.environ.get("PI", "pi")
    try:
        result = subprocess.run(
            [executable, "--version"],
            check=False,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.TimeoutExpired):
        return "unknown"
    return result.stdout.strip().splitlines()[0] if result.returncode == 0 and result.stdout.strip() else "unknown"


def new_manifest(root: Path, isolation: str) -> Dict[str, Any]:
    timestamp = now()
    source = source_record(root)
    manifest: Dict[str, Any] = {
        "schemaVersion": SCHEMA_VERSION,
        "repository": {"root": ".", "identity": repository_identity(root), "scope": "repository"},
        "source": source,
        "commandments": {"path": "COMMANDMENTS.md", "sha256": None, "version": None, "ratifiedAt": None},
        "currentState": "surveying",
        "resourceIsolation": isolation,
        "transitions": [],
        "artifacts": [],
        "verification": [],
        "firstStep": {
            "selectionPath": ".pi/jig/steps/0001/selection.json",
            "selectedCandidateId": None,
            "proposalPath": None,
            "resultPath": None,
            "outcome": "pending",
        },
        "evaluation": {"required": False, "status": "not-required", "verdictPath": None},
        "tools": {"jig": JIG_VERSION, "pi": detect_pi_version(), "python": platform.python_version()},
        "createdAt": timestamp,
        "updatedAt": timestamp,
    }
    append_transition(root, manifest, "absent", "surveying", "init-started")
    return manifest


def load_existing_manifest(root: Path) -> Dict[str, Any]:
    path = root / ".pi" / "jig" / "manifest.json"
    value = read_json(path, "manifest")
    if not isinstance(value, dict):
        raise ValidationError("manifest is not an object")
    validate_manifest_semantics(root, value, load_schema("manifest"))
    return value


def validate_current_source(root: Path, manifest: Mapping[str, Any]) -> None:
    if source_record(root) != manifest["source"]:
        raise ValidationError(
            "repository source revision or dirty summary changed after the recorded boundary"
        )


def attach_recovery_artifacts(manifest: Dict[str, Any], artifacts: Iterable[Tuple[str, str]]) -> bool:
    before = canonical_json(manifest["artifacts"])
    for path, digest in artifacts:
        upsert_artifact(manifest, path, "controller", digest)
    return before != canonical_json(manifest["artifacts"])


def write_manifest(root: Path, manifest: Dict[str, Any]) -> None:
    schema = load_schema("manifest")
    validate_instance(manifest, schema)
    atomic_write_json(root / ".pi" / "jig" / "manifest.json", manifest, schema)


def start(root: Path, isolation: str, lock: RepositoryLock) -> Dict[str, Any]:
    manifest_path = root / ".pi" / "jig" / "manifest.json"
    if manifest_path.exists():
        if manifest_path.is_symlink():
            raise ValidationError("manifest path is a symlink")
        manifest = load_existing_manifest(root)
        if manifest["resourceIsolation"] != isolation:
            raise JigError("the existing manifest uses a different resourceIsolation route")
        validate_current_source(root, manifest)
        recovered = (
            reconcile_temporary_files(root)
            + reconcile_orphan_transitions(root, manifest)
            + known_receipt_artifacts(root)
        )
        changed = attach_recovery_artifacts(manifest, recovered)
        reconciled = False
        state = manifest["currentState"]
        if state == "failed-surveying":
            append_transition(root, manifest, state, "surveying", "failed-state-reconciled")
            changed = True
            reconciled = True
        elif state == "failed-awaiting-commandments":
            append_transition(
                root, manifest, state, "awaiting-commandments", "failed-state-reconciled"
            )
            changed = True
            reconciled = True
        if changed:
            if not reconciled:
                manifest["updatedAt"] = now()
            write_manifest(root, manifest)
        return manifest
    recovered = (
        reconcile_temporary_files(root)
        + reconcile_orphan_transitions(root, None)
        + known_receipt_artifacts(root)
    )
    manifest = new_manifest(root, isolation)
    attach_recovery_artifacts(manifest, recovered)
    write_manifest(root, manifest)
    return manifest


def record_failure(root: Path, isolation: str, expected_state: str, reason: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] != expected_state:
        raise ValidationError(
            f"failure expected {expected_state}, found {manifest['currentState']}"
        )
    clean_reason = reason.strip()
    if not clean_reason or len(clean_reason) > 500 or "\n" in clean_reason or "\r" in clean_reason:
        raise ValidationError("failure reason must be one line of 1 to 500 characters")
    failed_state = f"failed-{expected_state}"
    append_transition(
        root,
        manifest,
        expected_state,
        failed_state,
        "phase-failed",
        failureReason=clean_reason,
    )
    write_manifest(root, manifest)
    return manifest


def commit_profile(root: Path, isolation: str, lock: RepositoryLock, raw: bytes) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    recovered = reconcile_orphan_transitions(root, manifest) + known_receipt_artifacts(root)
    if attach_recovery_artifacts(manifest, recovered):
        manifest["updatedAt"] = now()
        write_manifest(root, manifest)
    state = manifest["currentState"]
    if state == "failed-surveying":
        append_transition(root, manifest, state, "surveying", "failed-state-reconciled")
        write_manifest(root, manifest)
        state = "surveying"
    profile = read_json_bytes(raw, "profile input")
    if not isinstance(profile, dict):
        raise ValidationError("profile input is not an object")
    validate_instance(profile, load_schema("profile"))
    current_source = source_record(root)
    if current_source != manifest["source"]:
        raise ValidationError("repository source or dirty summary changed after surveying")
    validate_profile_semantics(root, profile, manifest["source"]["revision"])
    profile_path = root / ".pi" / "jig" / "profile.json"
    wanted = canonical_json(profile)
    if state in {"awaiting-commandments", "failed-awaiting-commandments"}:
        if not profile_path.is_file() or profile_path.is_symlink() or profile_path.read_bytes() != wanted:
            raise ValidationError("the committed profile differs from the supplied profile")
        if state == "failed-awaiting-commandments":
            append_transition(root, manifest, state, "awaiting-commandments", "failed-state-reconciled")
            write_manifest(root, manifest)
        return manifest
    if state != "surveying":
        raise ValidationError(f"profile cannot be committed from state {state}")
    if profile_path.exists():
        if profile_path.is_symlink() or not profile_path.is_file():
            raise ValidationError("existing profile path is not a regular file")
        if profile_path.read_bytes() != wanted:
            raise ValidationError("an uncommitted profile exists with different content")
    else:
        atomic_write(profile_path, wanted)
    profile_digest = sha256_file(profile_path)
    upsert_artifact(manifest, ".pi/jig/profile.json", "jig-skill", profile_digest)
    append_transition(
        root,
        manifest,
        "surveying",
        "awaiting-commandments",
        "profile-committed",
        profilePath=".pi/jig/profile.json",
        profileSha256=profile_digest,
        commandmentsGenerated=False,
    )
    write_manifest(root, manifest)
    return manifest


def render_result(manifest: Mapping[str, Any]) -> None:
    print(json.dumps({"root": ".", "state": manifest["currentState"], "resourceIsolation": manifest["resourceIsolation"]}, sort_keys=True))


def command_validate_schema(arguments: argparse.Namespace) -> int:
    schema = load_schema(arguments.schema)
    document = read_json(Path(arguments.document), "document")
    validate_instance(document, schema)
    print(f"valid {arguments.schema}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="jigctl.py")
    subparsers = result.add_subparsers(dest="command", required=True)
    for name in ("start", "commit-profile", "record-failure"):
        command = subparsers.add_parser(name)
        command.add_argument(
            "--resource-isolation",
            required=True,
            choices=("isolated-shell", "inherited-session"),
        )
        if name == "record-failure":
            command.add_argument(
                "--state", required=True, choices=("surveying", "awaiting-commandments")
            )
            command.add_argument("--reason", required=True)
    validate = subparsers.add_parser("validate-schema")
    validate.add_argument("--schema", required=True)
    validate.add_argument("--document", required=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command == "validate-schema":
        return command_validate_schema(arguments)
    root = resolve_git_root()
    with RepositoryLock(root) as lock:
        if arguments.command == "start":
            manifest = start(root, arguments.resource_isolation, lock)
        elif arguments.command == "record-failure":
            manifest = record_failure(
                root,
                arguments.resource_isolation,
                arguments.state,
                arguments.reason,
            )
        else:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest = commit_profile(root, arguments.resource_isolation, lock, raw)
    render_result(manifest)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except JigError as error:
        print(f"jigctl: {error}", file=sys.stderr)
        print(
            "Recovery: preserve .pi/jig, inspect the named state or lock, correct only that problem, and rerun jig init.",
            file=sys.stderr,
        )
        raise SystemExit(1)

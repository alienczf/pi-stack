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
MAX_OS_PID = (1 << 31) - 1
IMPLEMENTED_STATES = {
    "surveying",
    "awaiting-commandments",
    "commandments-ratified",
    "failed-surveying",
    "failed-awaiting-commandments",
    "failed-commandments-ratified",
}
TRANSITION_KIND_BY_EDGE = {
    ("absent", "surveying"): "init-started",
    ("surveying", "awaiting-commandments"): "profile-committed",
    ("awaiting-commandments", "commandments-ratified"): "commandments-ratified",
    ("surveying", "failed-surveying"): "phase-failed",
    ("awaiting-commandments", "failed-awaiting-commandments"): "phase-failed",
    ("commandments-ratified", "failed-commandments-ratified"): "phase-failed",
    ("failed-surveying", "surveying"): "failed-state-reconciled",
    ("failed-awaiting-commandments", "awaiting-commandments"): "failed-state-reconciled",
    ("failed-commandments-ratified", "commandments-ratified"): "failed-state-reconciled",
}
TRANSITION_RECEIPT_PATTERN = re.compile(
    r"transition-([0-9]{4})-("
    + "|".join(sorted(re.escape(state) for state in IMPLEMENTED_STATES))
    + r")\.json"
)
SENSITIVE_NAMES = {
    ".env",
    "auth.json",
    "private_key.pem",
    "public_key.pem",
    "id_rsa",
    "id_ed25519",
}

COMMANDMENTS_TEMPLATE = "skills/jig/references/COMMANDMENTS.template.md"
COMMANDMENTS_INTERVIEW_PATH = ".pi/jig/commandments/interview.json"
COMMANDMENTS_STAGING_PATH = ".pi/jig/commandments/staging.json"
COMMANDMENTS_ROOT_PATH = "COMMANDMENTS.md"
COMMANDMENTS_ANSWER_KEYS = (
    "requiredInitOutcome",
    "hardForbiddenOutcomes",
    "protectedUserPath",
    "proofPolicy",
    "compatibilityPolicy",
    "autonomyPolicy",
    "tradeoffOrder",
    "authority",
)
COMMANDMENTS_DEFAULTS: Dict[str, Any] = {
    "requiredInitOutcome": "Jig init records human-ratified COMMANDMENTS, crash-safe state, real verification, a feature map, and one evidence-backed first-step outcome before it reports success.",
    "hardForbiddenOutcomes": [
        "Do not invent human intent.",
        "Do not report completion after an interruption.",
        "Do not write outside the Git root.",
        "Do not load untrusted project resources during shell init.",
        "Do not store an absolute dependency on the operator's pstack checkout.",
        "Do not weaken verification to pass.",
        "Do not merge automatically.",
    ],
    "protectedUserPath": {
        "action": "Run the repository's primary documented user command.",
        "visibleResult": "The command completes its documented user-visible result.",
        "evidence": "Capture runtime output or persisted state that proves the visible result.",
        "cleanup": "Stop owned processes and restore the repository to its pre-run state.",
        "thresholds": "No additional threshold.",
    },
    "proofPolicy": {
        "baselineRequirement": "Reproduce the current behavior before the change.",
        "targetedVerification": "Prove the changed behavior before and after the change.",
        "productRegressionFloor": "Run the repository's full product regression check.",
        "seededGuardProof": "Seed and detect a negative case for every deterministic guard.",
        "independentReview": "Require independent review for high-blast-radius changes.",
        "behavioralEval": "Use blinded pstack Eval for agent-behavior claims.",
    },
    "compatibilityPolicy": "Do not introduce a user-visible compatibility break in the first improvement.",
    "autonomyPolicy": [
        "Agents may edit and test in isolated worktrees.",
        "Agents may open pull requests and drive them to merge-ready.",
        "Agents may revert failed attempts.",
        "Agents may run bounded evaluations after ratification.",
        "Agents may not merge, deploy, or amend COMMANDMENTS automatically.",
    ],
    "tradeoffOrder": [
        "Correctness and safety",
        "User-visible reliability",
        "Agent determinism",
        "Maintainability",
        "Performance",
        "Compatibility",
        "Implementation cost",
    ],
    "authority": {
        "owner": "Repository operator",
        "exceptions": "No exceptions without operator approval.",
        "amendmentPolicy": "Agents may propose amendments. The repository operator approves and ratifies them.",
        "ratificationMarker": "I ratify these exact repository COMMANDMENTS.",
    },
}


class JigError(Exception):
    """A bounded operator-facing failure."""


class ValidationError(JigError):
    """A schema or semantic validation failure."""


def is_object(value: Any) -> bool:
    return isinstance(value, dict)


def is_json_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def json_equal(left: Any, right: Any) -> bool:
    if is_json_number(left) and is_json_number(right):
        return left == right
    if type(left) is not type(right):
        return False
    if isinstance(left, list):
        return len(left) == len(right) and all(
            json_equal(left_item, right_item)
            for left_item, right_item in zip(left, right)
        )
    if isinstance(left, dict):
        return set(left) == set(right) and all(
            json_equal(left[key], right[key]) for key in left
        )
    return left == right


def type_matches(value: Any, expected: str) -> bool:
    if expected == "object":
        return isinstance(value, dict)
    if expected == "array":
        return isinstance(value, list)
    if expected == "string":
        return isinstance(value, str)
    if expected == "integer":
        if isinstance(value, bool):
            return False
        return isinstance(value, int) or (
            isinstance(value, float) and value.is_integer()
        )
    if expected == "number":
        return is_json_number(value)
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
        r"([0-9]{4})-([0-9]{2})-([0-9]{2})[Tt]([0-9]{2}):([0-9]{2}):([0-9]{2})"
        r"(?:\.[0-9]+)?(?:[Zz]|([+-])([0-9]{2}):([0-9]{2}))",
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

    if "const" in schema and not json_equal(instance, schema["const"]):
        raise ValidationError(f"{location} does not match its required value")
    if "enum" in schema and not any(json_equal(instance, item) for item in schema["enum"]):
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
            for index, item in enumerate(instance):
                if any(json_equal(item, other) for other in instance[index + 1 :]):
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

    def reject_constant(_value: str) -> Any:
        raise ValueError("non-standard JSON constant")

    def reject_duplicate_keys(pairs: List[Tuple[str, Any]]) -> Dict[str, Any]:
        value: Dict[str, Any] = {}
        for key, item in pairs:
            if key in value:
                raise ValueError("duplicate JSON object key")
            value[key] = item
        return value

    try:
        return json.loads(
            raw.decode("utf-8"),
            parse_constant=reject_constant,
            object_pairs_hook=reject_duplicate_keys,
        )
    except (UnicodeDecodeError, ValueError) as error:
        raise ValidationError(f"{label} is not valid UTF-8 JSON") from error


def read_json(path: Path, label: str) -> Any:
    try:
        return read_json_bytes(path.read_bytes(), label)
    except FileNotFoundError as error:
        raise ValidationError(f"{label} is missing") from error
    except OSError as error:
        raise ValidationError(f"{label} cannot be read") from error


def canonical_json(value: Any) -> bytes:
    try:
        rendered = json.dumps(value, allow_nan=False, indent=2, sort_keys=True)
    except (TypeError, ValueError) as error:
        raise ValidationError("value cannot be encoded as canonical JSON") from error
    return (rendered + "\n").encode("utf-8")


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
        [
            "status",
            "--porcelain=v1",
            "--untracked-files=all",
            "--",
            ".",
            ":(exclude).pi/jig",
            ":(exclude)COMMANDMENTS.md",
        ],
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
        if type(value.get("schemaVersion")) is not int or value["schemaVersion"] != 1:
            raise JigError("the init lock record has an unsupported version")
        if type(pid) is not int or pid <= 0 or pid > MAX_OS_PID:
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
        except OverflowError:
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
        except OSError as error:
            raise JigError("the init lock could not be removed during stale-owner reconciliation") from error
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
        except OSError as error:
            raise JigError("stale-lock evidence could not be preserved safely") from error
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
    reserved = (
        (re.compile(r"lock-reclaimed-([0-9a-f]{16})\.json"), True),
        (re.compile(r"interrupted-write-([0-9a-f]{64})\.bin"), False),
        (re.compile(r"interrupted-transition-([0-9a-f]{64})\.json"), False),
    )
    result = []
    for path in sorted(receipts.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        for pattern, prefix_digest in reserved:
            match = pattern.fullmatch(path.name)
            if match is None:
                continue
            digest = sha256_file(path)
            expected = match.group(1)
            digest_matches = digest.startswith(expected) if prefix_digest else digest == expected
            if digest_matches:
                result.append((relative_to_root(root, path), digest))
            break
    return result


def validate_transition_receipt(
    root: Path,
    receipt: Any,
    edge: Tuple[str, str],
    source: Mapping[str, Any],
    expected_at: Optional[str] = None,
) -> str:
    kind = TRANSITION_KIND_BY_EDGE.get(edge)
    if kind is None:
        raise ValidationError("transition receipt has an unimplemented edge")
    expected_values = {
        "schemaVersion": 1,
        "kind": kind,
        "from": edge[0],
        "to": edge[1],
        "sourceRevision": source["revision"],
        "sourceDirty": source["dirty"],
        "sourceStatusSha256": sha256_bytes(canonical_json(source["statusSummary"])),
    }
    expected_fields = set(expected_values) | {"at"}
    if kind == "profile-committed":
        expected_fields.update({"profilePath", "profileSha256", "commandmentsGenerated"})
    elif kind == "commandments-ratified":
        expected_fields.update(
            {
                "recordedAt",
                "resourceIsolation",
                "interviewPath",
                "interviewSha256",
                "answersPath",
                "answersSha256",
                "candidatePath",
                "commandmentsPath",
                "commandmentsSha256",
                "version",
                "operatorMarker",
                "approvalDigest",
            }
        )
    elif kind == "phase-failed":
        expected_fields.add("failureReason")
    if not isinstance(receipt, dict) or set(receipt) != expected_fields:
        raise ValidationError("transition receipt has an invalid implemented shape")
    if type(receipt["schemaVersion"]) is not int:
        raise ValidationError("transition receipt has an invalid schema version")
    if type(receipt["sourceDirty"]) is not bool:
        raise ValidationError("transition receipt has an invalid source dirty flag")
    if any(receipt.get(key) != value for key, value in expected_values.items()):
        raise ValidationError("transition receipt does not match its boundary")
    if not isinstance(receipt["at"], str) or not valid_datetime(receipt["at"]):
        raise ValidationError("transition receipt has an invalid timestamp")
    if expected_at is not None and receipt["at"] != expected_at:
        raise ValidationError("transition receipt does not match its transition timestamp")
    if kind == "profile-committed":
        if (
            receipt["profilePath"] != ".pi/jig/profile.json"
            or receipt["commandmentsGenerated"] is not False
            or not isinstance(receipt["profileSha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", receipt["profileSha256"]) is None
        ):
            raise ValidationError("profile transition receipt is inconsistent")
        profile_path = safe_relative_path(root, receipt["profilePath"], must_exist=True)
        try:
            mode = profile_path.lstat().st_mode
        except OSError as error:
            raise ValidationError("committed profile cannot be inspected") from error
        if not stat.S_ISREG(mode) or sha256_file(profile_path) != receipt["profileSha256"]:
            raise ValidationError("profile transition receipt hash is inconsistent")
    elif kind == "commandments-ratified":
        marker = receipt["operatorMarker"]
        digest = receipt["commandmentsSha256"]
        approval = sha256_bytes(
            canonical_json({"candidateSha256": digest, "operatorMarker": marker})
        )
        fixed = {
            "interviewPath": COMMANDMENTS_INTERVIEW_PATH,
            "commandmentsPath": COMMANDMENTS_ROOT_PATH,
        }
        if any(receipt.get(key) != value for key, value in fixed.items()):
            raise ValidationError("COMMANDMENTS transition receipt has inconsistent paths")
        if receipt["resourceIsolation"] not in {"isolated-shell", "inherited-session"}:
            raise ValidationError("COMMANDMENTS transition receipt has invalid isolation")
        if (
            not isinstance(marker, str)
            or not marker.strip()
            or len(marker) > 200
            or "\n" in marker
            or "\r" in marker
            or receipt["approvalDigest"] != approval
            or type(receipt["version"]) is not int
            or receipt["version"] < 1
            or not isinstance(receipt["recordedAt"], str)
            or not valid_datetime(receipt["recordedAt"])
        ):
            raise ValidationError("COMMANDMENTS transition receipt has invalid approval evidence")
        for digest_key in ("interviewSha256", "answersSha256", "commandmentsSha256"):
            digest_value = receipt[digest_key]
            if (
                not isinstance(digest_value, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest_value) is None
            ):
                raise ValidationError("COMMANDMENTS transition receipt has an invalid digest")
        expected_paths = {
            "answersPath": (
                f".pi/jig/commandments/answers/{receipt['answersSha256']}.json"
            ),
            "candidatePath": (
                f".pi/jig/commandments/candidates/{digest}.md"
            ),
        }
        if any(receipt.get(key) != value for key, value in expected_paths.items()):
            raise ValidationError("COMMANDMENTS transition receipt has invalid content addresses")
        for path_key, digest_key in (
            ("interviewPath", "interviewSha256"),
            ("answersPath", "answersSha256"),
            ("candidatePath", "commandmentsSha256"),
            ("commandmentsPath", "commandmentsSha256"),
        ):
            path_value = receipt[path_key]
            digest_value = receipt[digest_key]
            if (
                not isinstance(path_value, str)
                or not isinstance(digest_value, str)
                or re.fullmatch(r"[0-9a-f]{64}", digest_value) is None
            ):
                raise ValidationError("COMMANDMENTS transition receipt has invalid artifact evidence")
            artifact_path = safe_relative_path(root, path_value, must_exist=True)
            if not artifact_path.is_file() or artifact_path.is_symlink() or sha256_file(artifact_path) != digest_value:
                raise ValidationError("COMMANDMENTS transition receipt artifact hash is inconsistent")
        candidate = safe_relative_path(root, receipt["candidatePath"], must_exist=True).read_bytes()
        metadata = validate_commandments_bytes(candidate)
        if (
            metadata["version"] != receipt["version"]
            or metadata["ratifiedAt"] != receipt["at"]
            or metadata["marker"] != marker
        ):
            raise ValidationError("COMMANDMENTS transition receipt does not match the exact candidate")
    elif kind == "phase-failed":
        reason = receipt["failureReason"]
        if (
            not isinstance(reason, str)
            or not reason.strip()
            or len(reason) > 500
            or "\n" in reason
            or "\r" in reason
        ):
            raise ValidationError("failure transition receipt has an invalid reason")
    return kind


def reconcile_orphan_transitions(root: Path, manifest: Optional[Mapping[str, Any]]) -> List[Tuple[str, str]]:
    receipts = ensure_owned_directory(root, ".pi/jig/receipts")
    referenced = set() if manifest is None else {item["receiptPath"] for item in manifest["transitions"]}
    expected_index = 1 if manifest is None else len(manifest["transitions"]) + 1
    boundary = "absent" if manifest is None else manifest["currentState"]
    source = source_record(root) if manifest is None else manifest["source"]
    recovered = []
    for path in sorted(receipts.iterdir()):
        match = TRANSITION_RECEIPT_PATTERN.fullmatch(path.name)
        if match is None or int(match.group(1)) != expected_index:
            continue
        relative = relative_to_root(root, path)
        if relative in referenced or path.is_symlink() or not path.is_file():
            continue
        edge = (boundary, match.group(2))
        try:
            receipt = read_json(path, "orphan transition receipt")
            kind = validate_transition_receipt(root, receipt, edge, source)
        except JigError:
            continue
        if kind == "commandments-ratified":
            continue
        digest = sha256_file(path)
        destination = receipts / f"interrupted-transition-{digest}.json"
        try:
            if destination.exists() or destination.is_symlink():
                if (
                    destination.is_symlink()
                    or not destination.is_file()
                    or sha256_file(destination) != digest
                ):
                    raise JigError(
                        "interrupted-transition evidence collides with an existing unknown file"
                    )
                path.unlink()
            else:
                os.rename(path, destination)
        except OSError as error:
            raise JigError("orphan transition receipt could not be preserved safely") from error
        recovered.append((relative_to_root(root, destination), digest))
    return recovered


def reconcile_temporary_files(root: Path) -> List[Tuple[str, str]]:
    jig_dir = root / ".pi" / "jig"
    if not jig_dir.exists() or jig_dir.is_symlink():
        return []
    receipts = ensure_owned_directory(root, ".pi/jig/receipts")
    reserved = (
        (jig_dir, re.compile(r"\.jigctl-(?:manifest|profile)\.json\.[0-9]+\.[0-9a-f]{32}\.tmp")),
        (receipts, re.compile(r"\.jigctl-transition-[0-9]{4}-[a-z-]+\.json\.[0-9]+\.[0-9a-f]{32}\.tmp")),
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
    implemented_state = "|".join(sorted(re.escape(item) for item in IMPLEMENTED_STATES))
    allowed_artifact = re.compile(
        r"^(?:COMMANDMENTS\.md|\.pi/jig/(?:profile\.json|commandments/(?:interview\.json|"
        r"staging\.json|answers/[0-9a-f]{64}\.json|candidates/[0-9a-f]{64}\.md|"
        r"decisions/[0-9a-f]{64}\.json|proposals/[0-9a-f]{64}\.md)|"
        r"receipts/(?:transition-[0-9]{4}-(?:"
        + implemented_state
        + r")\.json|lock-reclaimed-[0-9a-f]{16}\.json|"
        + r"interrupted-write-[0-9a-f]{64}\.bin|interrupted-transition-[0-9a-f]{64}\.json)))$"
    )
    for artifact in artifacts:
        artifact_path = artifact["path"]
        if allowed_artifact.fullmatch(artifact_path) is None:
            raise ValidationError(f"manifest names an unknown owned artifact: {artifact_path}")
        if artifact_path == COMMANDMENTS_ROOT_PATH or "/answers/" in artifact_path:
            expected_owner = "human"
        elif artifact_path == ".pi/jig/profile.json" or "/proposals/" in artifact_path:
            expected_owner = "jig-skill"
        else:
            expected_owner = "controller"
        if artifact["owner"] != expected_owner:
            raise ValidationError(f"owned artifact has the wrong owner: {artifact_path}")
        path = safe_relative_path(root, artifact_path, must_exist=True)
        if sha256_file(path) != artifact["sha256"]:
            if artifact_path == COMMANDMENTS_ROOT_PATH:
                raise ValidationError(
                    "ratified COMMANDMENTS changed; preserve it and use the amendment and re-ratification flow"
                )
            raise ValidationError(f"owned artifact hash mismatch: {artifact_path}")
        receipt_name = Path(artifact_path).name
        digest_name = re.fullmatch(r"lock-reclaimed-([0-9a-f]{16})\.json", receipt_name)
        if digest_name is not None and not artifact["sha256"].startswith(digest_name.group(1)):
            raise ValidationError(f"recovery artifact name does not match its digest: {artifact_path}")
        digest_name = re.fullmatch(
            r"interrupted-(?:write|transition)-([0-9a-f]{64})\.(?:bin|json)",
            receipt_name,
        )
        if digest_name is not None and artifact["sha256"] != digest_name.group(1):
            raise ValidationError(f"recovery artifact name does not match its digest: {artifact_path}")
        content_name = re.fullmatch(
            r"(?:answers|candidates|decisions|proposals)/([0-9a-f]{64})\.(?:json|md)",
            "/".join(Path(artifact_path).parts[-2:]),
        )
        if content_name is not None and artifact["sha256"] != content_name.group(1):
            raise ValidationError(f"content-addressed artifact name does not match its digest: {artifact_path}")
    transitions = manifest["transitions"]
    if not transitions or transitions[0]["from"] != "absent":
        raise ValidationError("manifest transition history does not start at absent")
    expected_transition_artifacts = set()
    previous = "absent"
    for index, transition in enumerate(transitions, start=1):
        edge = (transition["from"], transition["to"])
        if transition["from"] != previous or edge not in TRANSITION_KIND_BY_EDGE:
            raise ValidationError("manifest transition history has an invalid edge")
        expected_path = f".pi/jig/receipts/transition-{index:04d}-{edge[1]}.json"
        if transition["receiptPath"] != expected_path:
            raise ValidationError("transition receipt path does not match the implemented transition")
        expected_transition_artifacts.add(expected_path)
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
        kind = validate_transition_receipt(
            root,
            receipt_data,
            edge,
            manifest["source"],
            expected_at=transition["at"],
        )
        if kind == "profile-committed":
            profile_artifact = next(
                (item for item in artifacts if item["path"] == ".pi/jig/profile.json"), None
            )
            if (
                profile_artifact is None
                or receipt_data["profileSha256"] != profile_artifact["sha256"]
            ):
                raise ValidationError("profile transition receipt is inconsistent")
        elif kind == "commandments-ratified":
            if (
                receipt_data["resourceIsolation"] != manifest["resourceIsolation"]
                or receipt_data["commandmentsSha256"] != manifest["commandments"]["sha256"]
                or receipt_data["version"] != manifest["commandments"]["version"]
                or receipt_data["at"] != manifest["commandments"]["ratifiedAt"]
            ):
                raise ValidationError("COMMANDMENTS transition receipt is inconsistent with the manifest")
        previous = transition["to"]
    transition_artifacts = {
        path
        for path in artifact_paths
        if re.fullmatch(
            r"\.pi/jig/receipts/transition-[0-9]{4}-(?:" + implemented_state + r")\.json",
            path,
        )
    }
    if transition_artifacts != expected_transition_artifacts:
        raise ValidationError("transition receipt artifacts do not match transition history")
    if previous != state:
        raise ValidationError("manifest currentState does not match its last transition")
    if state in {
        "awaiting-commandments",
        "failed-awaiting-commandments",
        "commandments-ratified",
        "failed-commandments-ratified",
    }:
        profile_artifact = next(
            (item for item in artifacts if item["path"] == ".pi/jig/profile.json"),
            None,
        )
        if profile_artifact is None:
            raise ValidationError("COMMANDMENTS boundary has no committed profile artifact")
        profile = read_json(root / ".pi" / "jig" / "profile.json", "profile")
        validate_instance(profile, load_schema("profile"))
        validate_profile_semantics(root, profile, manifest["source"]["revision"])
    if state in {"commandments-ratified", "failed-commandments-ratified"}:
        root_path = safe_relative_path(root, COMMANDMENTS_ROOT_PATH, must_exist=True)
        if not root_path.is_file() or root_path.is_symlink():
            raise ValidationError("ratified COMMANDMENTS path is not a regular file")
        digest = sha256_file(root_path)
        metadata = validate_commandments_bytes(root_path.read_bytes())
        commandment_record = manifest["commandments"]
        if (
            commandment_record["sha256"] != digest
            or commandment_record["version"] != metadata["version"]
            or commandment_record["ratifiedAt"] != metadata["ratifiedAt"]
        ):
            raise ValidationError(
                "ratified COMMANDMENTS changed; preserve it and use the amendment and re-ratification flow"
            )
        artifact = next((item for item in artifacts if item["path"] == COMMANDMENTS_ROOT_PATH), None)
        if artifact != {"path": COMMANDMENTS_ROOT_PATH, "owner": "human", "sha256": digest}:
            raise ValidationError("ratified COMMANDMENTS artifact ownership is inconsistent")


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
    validate_manifest_semantics(root, manifest, schema)
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
        elif state == "failed-commandments-ratified":
            append_transition(
                root, manifest, state, "commandments-ratified", "failed-state-reconciled"
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
    recovered = reconcile_orphan_transitions(root, manifest) + known_receipt_artifacts(root)
    if attach_recovery_artifacts(manifest, recovered):
        manifest["updatedAt"] = now()
        write_manifest(root, manifest)
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

def require_commandments_boundary(
    root: Path, isolation: str, allowed_states: Sequence[str]
) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] not in allowed_states:
        raise ValidationError(
            f"COMMANDMENTS command cannot run from state {manifest['currentState']}"
        )
    return manifest


def bounded_text(value: Any, label: str, maximum: int = 2000, allow_empty: bool = False) -> str:
    if not isinstance(value, str):
        raise ValidationError(f"{label} must be text")
    if value != value.strip():
        raise ValidationError(f"{label} must not have leading or trailing whitespace")
    if not allow_empty and not value:
        raise ValidationError(f"{label} must not be empty")
    if len(value.encode("utf-8")) > maximum:
        raise ValidationError(f"{label} is too long")
    if any(ord(character) < 32 or 127 <= ord(character) <= 159 for character in value):
        raise ValidationError(f"{label} contains a control character")
    if "{{" in value or "}}" in value or "TEMPLATE, NOT RATIFIED" in value:
        raise ValidationError(f"{label} contains a template marker")
    return value


def string_list(value: Any, label: str) -> List[str]:
    if not isinstance(value, list) or not value or len(value) > 20:
        raise ValidationError(f"{label} must be a non-empty list with at most 20 items")
    result = [bounded_text(item, f"{label} item", 500) for item in value]
    if len(result) != len(set(result)):
        raise ValidationError(f"{label} contains duplicate items")
    return result


def exact_text_object(
    value: Any, label: str, fields: Sequence[str]
) -> Dict[str, str]:
    if not isinstance(value, dict) or set(value) != set(fields):
        raise ValidationError(f"{label} must contain exactly {', '.join(fields)}")
    return {field: bounded_text(value[field], f"{label}.{field}", 1000) for field in fields}


def copy_json_value(value: Any) -> Any:
    return json.loads(json.dumps(value, allow_nan=False))


def validate_commandments_answers(value: Any) -> Tuple[Dict[str, Any], Dict[str, str]]:
    expected = set(COMMANDMENTS_ANSWER_KEYS) | {"schemaVersion", "freeTextAmendments"}
    if not isinstance(value, dict) or set(value) != expected:
        raise ValidationError("COMMANDMENTS answers are incomplete or contain unknown keys")
    if type(value["schemaVersion"]) is not int or value["schemaVersion"] != 1:
        raise ValidationError("COMMANDMENTS answers use an unsupported schema version")
    validators = {
        "requiredInitOutcome": lambda item: bounded_text(item, "requiredInitOutcome", 2000),
        "hardForbiddenOutcomes": lambda item: string_list(item, "hardForbiddenOutcomes"),
        "protectedUserPath": lambda item: exact_text_object(
            item,
            "protectedUserPath",
            ("action", "visibleResult", "evidence", "cleanup", "thresholds"),
        ),
        "proofPolicy": lambda item: exact_text_object(
            item,
            "proofPolicy",
            (
                "baselineRequirement",
                "targetedVerification",
                "productRegressionFloor",
                "seededGuardProof",
                "independentReview",
                "behavioralEval",
            ),
        ),
        "compatibilityPolicy": lambda item: bounded_text(item, "compatibilityPolicy", 2000),
        "autonomyPolicy": lambda item: string_list(item, "autonomyPolicy"),
        "tradeoffOrder": lambda item: string_list(item, "tradeoffOrder"),
        "authority": lambda item: exact_text_object(
            item,
            "authority",
            ("owner", "exceptions", "amendmentPolicy", "ratificationMarker"),
        ),
    }
    resolved: Dict[str, Any] = {}
    modes: Dict[str, str] = {}
    for key in COMMANDMENTS_ANSWER_KEYS:
        choice = value[key]
        if not isinstance(choice, dict) or choice.get("selection") not in {"default", "custom"}:
            raise ValidationError(f"{key} must explicitly select default or custom")
        selection = choice["selection"]
        if selection == "default":
            if set(choice) != {"selection"}:
                raise ValidationError(f"{key} default selection must not contain a value")
            selected = copy_json_value(COMMANDMENTS_DEFAULTS[key])
        else:
            if set(choice) != {"selection", "value"}:
                raise ValidationError(f"{key} custom selection must contain exactly one value")
            selected = choice["value"]
        resolved[key] = validators[key](selected)
        modes[key] = selection
    resolved["freeTextAmendments"] = bounded_text(
        value["freeTextAmendments"],
        "freeTextAmendments",
        4000,
        allow_empty=True,
    )
    return resolved, modes


def commandments_template_bytes() -> bytes:
    path = Path(__file__).resolve().parent.parent / COMMANDMENTS_TEMPLATE
    try:
        return path.read_bytes()
    except OSError as error:
        raise ValidationError("the checked-in COMMANDMENTS template cannot be read") from error


def render_commandments_candidate(
    resolved: Mapping[str, Any], ratified_at: str, version: int = 1
) -> bytes:
    if not valid_datetime(ratified_at):
        raise ValidationError("prospective ratification timestamp is invalid")
    protected = resolved["protectedUserPath"]
    proof = resolved["proofPolicy"]
    authority = resolved["authority"]
    replacements = {
        "{{OWNER}}": authority["owner"],
        "{{RATIFIED_AT}}": ratified_at,
        "{{VERSION}}": str(version),
        "{{REQUIRED_OUTCOME}}": resolved["requiredInitOutcome"],
        "{{REQUIRED_OUTCOME_PROOF}}": (
            proof["targetedVerification"] + " " + proof["productRegressionFloor"]
        ),
        "{{EXCEPTIONS}}": authority["exceptions"],
        "{{FORBIDDEN_OUTCOMES}}": " ".join(resolved["hardForbiddenOutcomes"]),
        "{{PROTECTED_ACTION}}": protected["action"],
        "{{PROTECTED_RESULT}}": protected["visibleResult"],
        "{{PROTECTED_EVIDENCE}}": protected["evidence"],
        "{{PROTECTED_CLEANUP}}": protected["cleanup"],
        "{{PROTECTED_THRESHOLDS}}": protected["thresholds"],
        "{{PROOF_BASELINE}}": proof["baselineRequirement"],
        "{{PROOF_TARGETED}}": proof["targetedVerification"],
        "{{PROOF_REGRESSION}}": proof["productRegressionFloor"],
        "{{PROOF_SEEDED}}": proof["seededGuardProof"],
        "{{PROOF_REVIEW}}": proof["independentReview"],
        "{{PROOF_BEHAVIORAL}}": proof["behavioralEval"],
        "{{COMPATIBILITY}}": resolved["compatibilityPolicy"],
        "{{AUTONOMY}}": "\n".join(
            f"- {item}" for item in resolved["autonomyPolicy"]
        ),
        "{{TRADEOFF_ORDER}}": "\n".join(
            f"{index}. {item}"
            for index, item in enumerate(resolved["tradeoffOrder"], start=1)
        ),
        "{{AMENDMENT_POLICY}}": authority["amendmentPolicy"],
        "{{FREE_TEXT_AMENDMENTS}}": resolved["freeTextAmendments"] or "None.",
        "{{RATIFICATION_MARKER}}": authority["ratificationMarker"],
    }
    text = commandments_template_bytes().decode("utf-8")
    for marker, replacement in replacements.items():
        text = text.replace(marker, replacement)
    raw = text.encode("utf-8")
    validate_commandments_bytes(raw)
    return raw


def validate_commandments_bytes(raw: bytes) -> Dict[str, Any]:
    if not raw or len(raw) > 256 * 1024:
        raise ValidationError("COMMANDMENTS bytes are empty or too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError("COMMANDMENTS bytes are not UTF-8") from error
    if not text.endswith("\n") or "{{" in text or "}}" in text or "TEMPLATE, NOT RATIFIED" in text:
        raise ValidationError("COMMANDMENTS contains a template marker or lacks its final newline")
    required_sections = (
        "# Repository COMMANDMENTS",
        "## Hard commandments",
        "## Directional commandments",
        "## Protected user path",
        "## Proof policy",
        "## Compatibility policy",
        "## Autonomy policy",
        "## Tradeoff order",
        "## Amendment policy",
        "## Ratification",
    )
    if any(text.count(section) != 1 for section in required_sections):
        raise ValidationError("COMMANDMENTS does not match the checked-in section structure")
    ids = re.findall(r"^### (CMD-[0-9]{3})\. ", text, flags=re.MULTILINE)
    if ids != ["CMD-001", "CMD-002", "CMD-101", "CMD-102"]:
        raise ValidationError("COMMANDMENTS has missing, duplicate, or unstable commandment IDs")
    for label, count in (
        ("**Statement.** ", 4),
        ("**Scope.** ", 4),
        ("**Priority.** ", 4),
        ("**Proof.** ", 4),
        ("**Exceptions.** ", 4),
        ("**Owner.** ", 4),
    ):
        if text.count(label) != count:
            raise ValidationError("COMMANDMENTS commandment entries are incomplete")
    status = re.search(r"^Status: (.+)$", text, flags=re.MULTILINE)
    owner = re.search(r"^Owner: (.+)$", text, flags=re.MULTILINE)
    timestamp = re.search(r"^Ratified at: (.+)$", text, flags=re.MULTILINE)
    version = re.search(r"^Version: ([0-9]+)$", text, flags=re.MULTILINE)
    marker = re.search(r"^Human note: (.+)$", text, flags=re.MULTILINE)
    if not all((status, owner, timestamp, version, marker)) or status.group(1) != "RATIFIED":
        raise ValidationError("COMMANDMENTS ratification metadata is incomplete")
    if not valid_datetime(timestamp.group(1)):
        raise ValidationError("COMMANDMENTS ratification timestamp is invalid")
    parsed_version = int(version.group(1))
    if parsed_version < 1:
        raise ValidationError("COMMANDMENTS version is invalid")
    bounded_text(owner.group(1), "COMMANDMENTS owner", 1000)
    bounded_text(marker.group(1), "COMMANDMENTS ratification marker", 200)
    if "Human decision: ratified" not in text:
        raise ValidationError("COMMANDMENTS lacks the prospective ratification decision")
    return {
        "owner": owner.group(1),
        "ratifiedAt": timestamp.group(1),
        "version": parsed_version,
        "marker": marker.group(1),
    }


def fixed_artifact_path(root: Path, relative: str, create_parent: bool = True) -> Path:
    pure = PurePosixPath(relative)
    if create_parent and len(pure.parts) > 1:
        ensure_owned_directory(root, "/".join(pure.parts[:-1]))
    path = safe_relative_path(root, relative)
    if path.exists() or path.is_symlink():
        try:
            mode = path.lstat().st_mode
        except OSError as error:
            raise ValidationError(f"artifact path cannot be inspected: {relative}") from error
        if stat.S_ISLNK(mode) or not stat.S_ISREG(mode):
            raise ValidationError(f"artifact path is not a regular file: {relative}")
    return path


def write_exact_artifact(root: Path, relative: str, raw: bytes) -> str:
    path = fixed_artifact_path(root, relative)
    if path.exists():
        if path.read_bytes() != raw:
            raise ValidationError(f"content-addressed artifact collision: {relative}")
    else:
        atomic_write(path, raw)
    return sha256_bytes(raw)


def content_addressed_artifact(
    root: Path, directory: str, suffix: str, raw: bytes
) -> Tuple[str, str]:
    digest = sha256_bytes(raw)
    relative = f".pi/jig/commandments/{directory}/{digest}.{suffix}"
    write_exact_artifact(root, relative, raw)
    return relative, digest


def interview_value(
    profile: Mapping[str, Any], profile_digest: str, isolation: str
) -> Dict[str, Any]:
    observed = {
        "repositoryRevision": profile["repositoryRevision"],
        "profilePath": ".pi/jig/profile.json",
        "profileSha256": profile_digest,
        "productType": profile["productType"],
        "languages": profile["languages"],
        "frameworks": profile["frameworks"],
        "buildTools": profile["buildTools"],
        "ci": profile["ci"],
        "entryPoints": profile["entryPoints"],
        "topology": profile["topology"],
        "unknowns": profile["unknowns"],
    }
    prompts = {
        "requiredInitOutcome": "Which result must jig init guarantee before success?",
        "hardForbiddenOutcomes": "Which outcomes must init never permit?",
        "protectedUserPath": "Which user path and visible result must init protect?",
        "proofPolicy": "Which evidence is required before the first improvement is kept?",
        "compatibilityPolicy": "Which compatibility breaks are acceptable?",
        "autonomyPolicy": "What may the coordinator do without another question?",
        "tradeoffOrder": "How should init rank goals when they conflict?",
        "authority": "Who owns exceptions, amendments, and the ratification marker?",
    }
    questions = [
        {
            "answerKey": key,
            "prompt": prompts[key],
            "recommendedDefault": copy_json_value(COMMANDMENTS_DEFAULTS[key]),
            "answerRule": "Select default explicitly or supply a custom value.",
        }
        for key in COMMANDMENTS_ANSWER_KEYS
    ]
    return {
        "schemaVersion": 1,
        "kind": "commandments-interview",
        "round": 1,
        "resourceIsolation": isolation,
        "routeNotice": (
            "This current session has inherited project resources that cannot be unloaded."
            if isolation == "inherited-session"
            else "The shell-started session disabled discovered project resources."
        ),
        "observedFacts": observed,
        "questions": questions,
        "freeTextAmendments": {
            "prompt": "Name any amendment not captured above.",
            "required": False,
            "default": "",
        },
        "candidateInputPath": ".pi/jig/commandments/answers.input.json",
        "rules": [
            "Recommended defaults are not answers unless the operator selects them.",
            "Missing or partial answers remain unresolved.",
            "Do not start a second interview round.",
        ],
    }


def present_commandments(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = require_commandments_boundary(
        root,
        isolation,
        ("awaiting-commandments", "commandments-ratified"),
    )
    if manifest["currentState"] == "commandments-ratified":
        return {
            "state": "commandments-ratified",
            "alreadyRatified": True,
            "sha256": manifest["commandments"]["sha256"],
        }
    profile_path = root / ".pi" / "jig" / "profile.json"
    profile = read_json(profile_path, "profile")
    raw = canonical_json(
        interview_value(profile, sha256_file(profile_path), isolation)
    )
    path = fixed_artifact_path(root, COMMANDMENTS_INTERVIEW_PATH)
    if path.exists() and path.read_bytes() != raw:
        raise ValidationError("the durable COMMANDMENTS interview differs from the repository profile")
    if not path.exists():
        atomic_write(path, raw)
    digest = sha256_bytes(raw)
    artifact = next(
        (item for item in manifest["artifacts"] if item["path"] == COMMANDMENTS_INTERVIEW_PATH),
        None,
    )
    if artifact != {"path": COMMANDMENTS_INTERVIEW_PATH, "owner": "controller", "sha256": digest}:
        upsert_artifact(manifest, COMMANDMENTS_INTERVIEW_PATH, "controller", digest)
        manifest["updatedAt"] = now()
        write_manifest(root, manifest)
    return read_json_bytes(raw, "COMMANDMENTS interview")


def load_staging(root: Path) -> Optional[Dict[str, Any]]:
    path = root / COMMANDMENTS_STAGING_PATH
    if not path.exists() and not path.is_symlink():
        return None
    fixed_artifact_path(root, COMMANDMENTS_STAGING_PATH)
    value = read_json(path, "COMMANDMENTS staging record")
    expected = {
        "schemaVersion",
        "kind",
        "answersPath",
        "answersSha256",
        "choiceModes",
        "candidatePath",
        "candidateSha256",
        "version",
        "prospectiveRatifiedAt",
        "intendedMarker",
        "sourceRevision",
        "interviewSha256",
        "adoptedExisting",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise ValidationError("COMMANDMENTS staging record has an invalid shape")
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "commandments-staged"
        or type(value["version"]) is not int
        or value["version"] < 1
        or type(value["adoptedExisting"]) is not bool
        or not isinstance(value["sourceRevision"], str)
        or re.fullmatch(r"[0-9a-f]{40,64}", value["sourceRevision"]) is None
        or not isinstance(value["interviewSha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", value["interviewSha256"]) is None
        or not isinstance(value["choiceModes"], dict)
        or set(value["choiceModes"]) != set(COMMANDMENTS_ANSWER_KEYS)
        or any(mode not in {"default", "custom"} for mode in value["choiceModes"].values())
    ):
        raise ValidationError("COMMANDMENTS staging record has invalid metadata")
    bounded_text(value["intendedMarker"], "staged ratification marker", 200)
    if not isinstance(value["prospectiveRatifiedAt"], str) or not valid_datetime(
        value["prospectiveRatifiedAt"]
    ):
        raise ValidationError("COMMANDMENTS staging record has an invalid timestamp")
    for directory, path_key, digest_key, suffix in (
        ("answers", "answersPath", "answersSha256", "json"),
        ("candidates", "candidatePath", "candidateSha256", "md"),
    ):
        digest = value[digest_key]
        expected_path = f".pi/jig/commandments/{directory}/{digest}.{suffix}"
        if (
            not isinstance(digest, str)
            or re.fullmatch(r"[0-9a-f]{64}", digest) is None
            or value[path_key] != expected_path
        ):
            raise ValidationError("COMMANDMENTS staging record has an invalid content address")
        artifact_path = safe_relative_path(root, expected_path, must_exist=True)
        if artifact_path.is_symlink() or not artifact_path.is_file() or sha256_file(artifact_path) != digest:
            raise ValidationError("COMMANDMENTS staging artifact hash changed")
    answers = read_json(root / value["answersPath"], "staged COMMANDMENTS answers")
    _resolved, modes = validate_commandments_answers(answers)
    if modes != value["choiceModes"]:
        raise ValidationError("COMMANDMENTS staging choice evidence is inconsistent")
    metadata = validate_commandments_bytes((root / value["candidatePath"]).read_bytes())
    if (
        metadata["version"] != value["version"]
        or metadata["ratifiedAt"] != value["prospectiveRatifiedAt"]
        or metadata["marker"] != value["intendedMarker"]
    ):
        raise ValidationError("COMMANDMENTS staging candidate metadata is inconsistent")
    return value


def amendment_decision_exists(
    root: Path,
    manifest: Mapping[str, Any],
    candidate_digest: str,
    isolation: str,
) -> bool:
    directory = root / ".pi" / "jig" / "commandments" / "decisions"
    if not directory.exists():
        return False
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("COMMANDMENTS decision directory is unsafe")
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    expected_fields = {
        "schemaVersion",
        "kind",
        "decision",
        "candidateSha256",
        "operatorMarker",
        "at",
        "sourceRevision",
        "resourceIsolation",
    }
    for path in directory.iterdir():
        if path.is_symlink() or not path.is_file():
            continue
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        relative = relative_to_root(root, path)
        artifact = artifacts.get(relative)
        if (
            path.name != f"{digest}.json"
            or artifact != {"path": relative, "owner": "controller", "sha256": digest}
        ):
            continue
        try:
            value = read_json_bytes(raw, "COMMANDMENTS decision")
            if not isinstance(value, dict) or set(value) != expected_fields:
                continue
            marker = bounded_text(
                value["operatorMarker"], "decision operator marker", 200
            )
        except ValidationError:
            continue
        if (
            type(value["schemaVersion"]) is int
            and value["schemaVersion"] == 1
            and value["kind"] == "commandments-decision"
            and value["decision"] == "amend"
            and value["candidateSha256"] == candidate_digest
            and value["sourceRevision"] == manifest["source"]["revision"]
            and value["resourceIsolation"] == isolation
            and isinstance(value["at"], str)
            and valid_datetime(value["at"])
            and marker == value["operatorMarker"]
        ):
            return True
    return False


def stage_commandments(
    root: Path,
    isolation: str,
    raw: bytes,
    amend_candidate_sha: Optional[str],
    adopt_existing: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(root, isolation, ("awaiting-commandments",))
    interview_artifact = next(
        (item for item in manifest["artifacts"] if item["path"] == COMMANDMENTS_INTERVIEW_PATH),
        None,
    )
    if interview_artifact is None:
        raise ValidationError("present the one COMMANDMENTS interview before staging answers")
    answers = read_json_bytes(raw, "COMMANDMENTS answers")
    resolved, modes = validate_commandments_answers(answers)
    answers_raw = canonical_json(answers)
    answers_path, answers_digest = content_addressed_artifact(
        root, "answers", "json", answers_raw
    )
    current = load_staging(root)
    if (
        current is not None
        and current["answersSha256"] == answers_digest
        and current["adoptedExisting"] == adopt_existing
    ):
        candidate_path = safe_relative_path(root, current["candidatePath"], must_exist=True)
        candidate_raw = candidate_path.read_bytes()
        if sha256_bytes(candidate_raw) != current["candidateSha256"]:
            raise ValidationError("staged COMMANDMENTS candidate hash changed")
        staging_raw = canonical_json(current)
        wanted = (
            (answers_path, "human", answers_digest),
            (current["candidatePath"], "controller", current["candidateSha256"]),
            (COMMANDMENTS_STAGING_PATH, "controller", sha256_bytes(staging_raw)),
        )
        before = canonical_json(manifest["artifacts"])
        for path_value, owner, digest in wanted:
            upsert_artifact(manifest, path_value, owner, digest)
        if before != canonical_json(manifest["artifacts"]):
            manifest["updatedAt"] = now()
            write_manifest(root, manifest)
        return manifest, current
    if current is not None:
        prior = current["candidateSha256"]
        if (
            amend_candidate_sha != prior
            or not amendment_decision_exists(root, manifest, prior, isolation)
        ):
            raise ValidationError(
                "changed answers require a recorded amend decision for the current candidate digest"
            )
    elif amend_candidate_sha is not None:
        raise ValidationError("there is no staged candidate to amend")
    root_path = fixed_artifact_path(root, COMMANDMENTS_ROOT_PATH, create_parent=False)
    if adopt_existing:
        if not root_path.exists():
            raise ValidationError("there is no existing root COMMANDMENTS.md to adopt")
        candidate_raw = root_path.read_bytes()
        metadata = validate_commandments_bytes(candidate_raw)
        if metadata["marker"] != resolved["authority"]["ratificationMarker"]:
            raise ValidationError("existing COMMANDMENTS marker differs from the explicit answer")
    else:
        metadata = {"ratifiedAt": now(), "version": 1}
        candidate_raw = render_commandments_candidate(
            resolved, metadata["ratifiedAt"], metadata["version"]
        )
        metadata = validate_commandments_bytes(candidate_raw)
    candidate_path, candidate_digest = content_addressed_artifact(
        root, "candidates", "md", candidate_raw
    )
    staging = {
        "schemaVersion": 1,
        "kind": "commandments-staged",
        "answersPath": answers_path,
        "answersSha256": answers_digest,
        "choiceModes": modes,
        "candidatePath": candidate_path,
        "candidateSha256": candidate_digest,
        "version": metadata["version"],
        "prospectiveRatifiedAt": metadata["ratifiedAt"],
        "intendedMarker": resolved["authority"]["ratificationMarker"],
        "sourceRevision": manifest["source"]["revision"],
        "interviewSha256": interview_artifact["sha256"],
        "adoptedExisting": adopt_existing,
    }
    staging_raw = canonical_json(staging)
    staging_path = fixed_artifact_path(root, COMMANDMENTS_STAGING_PATH)
    atomic_write(staging_path, staging_raw)
    upsert_artifact(manifest, answers_path, "human", answers_digest)
    upsert_artifact(manifest, candidate_path, "controller", candidate_digest)
    upsert_artifact(
        manifest,
        COMMANDMENTS_STAGING_PATH,
        "controller",
        sha256_bytes(staging_raw),
    )
    manifest["updatedAt"] = now()
    write_manifest(root, manifest)
    return manifest, staging


def record_commandments_decision(
    root: Path,
    isolation: str,
    decision: str,
    candidate_sha: Optional[str],
    operator_marker: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(root, isolation, ("awaiting-commandments",))
    marker = bounded_text(operator_marker, "operator marker", 200)
    current = load_staging(root)
    if decision == "amend":
        if current is None or candidate_sha != current["candidateSha256"]:
            raise ValidationError("amend must name the current exact candidate digest")
    elif decision == "defer":
        if candidate_sha is not None and (
            current is None or candidate_sha != current["candidateSha256"]
        ):
            raise ValidationError("defer names a stale or unknown candidate digest")
    else:
        raise ValidationError("decision must be amend or defer")
    receipt = {
        "schemaVersion": 1,
        "kind": "commandments-decision",
        "decision": decision,
        "candidateSha256": candidate_sha,
        "operatorMarker": marker,
        "at": now(),
        "sourceRevision": manifest["source"]["revision"],
        "resourceIsolation": isolation,
    }
    raw = canonical_json(receipt)
    path, digest = content_addressed_artifact(root, "decisions", "json", raw)
    upsert_artifact(manifest, path, "controller", digest)
    manifest["updatedAt"] = receipt["at"]
    write_manifest(root, manifest)
    return manifest, {**receipt, "path": path, "sha256": digest}


def ratify_commandments(
    root: Path, isolation: str, candidate_sha: str, operator_marker: str
) -> Dict[str, Any]:
    manifest = require_commandments_boundary(
        root,
        isolation,
        ("awaiting-commandments", "commandments-ratified"),
    )
    marker = bounded_text(operator_marker, "operator marker", 200)
    if re.fullmatch(r"[0-9a-f]{64}", candidate_sha) is None:
        raise ValidationError("candidate digest must be a lowercase SHA-256 value")
    if manifest["currentState"] == "commandments-ratified":
        if manifest["commandments"]["sha256"] != candidate_sha:
            raise ValidationError("ratified COMMANDMENTS digest differs from the requested digest")
        metadata = validate_commandments_bytes((root / COMMANDMENTS_ROOT_PATH).read_bytes())
        if metadata["marker"] != marker:
            raise ValidationError("operator marker differs from the ratified exact bytes")
        return manifest
    staging = load_staging(root)
    if staging is None or staging["candidateSha256"] != candidate_sha:
        raise ValidationError("ratification must name the current exact candidate digest")
    candidate_path = safe_relative_path(root, staging["candidatePath"], must_exist=True)
    candidate_raw = candidate_path.read_bytes()
    if sha256_bytes(candidate_raw) != candidate_sha:
        raise ValidationError("staged COMMANDMENTS candidate hash changed")
    metadata = validate_commandments_bytes(candidate_raw)
    if metadata["marker"] != marker or staging["intendedMarker"] != marker:
        raise ValidationError("ratification marker differs from the exact staged candidate")
    root_path = fixed_artifact_path(root, COMMANDMENTS_ROOT_PATH, create_parent=False)
    if root_path.exists():
        if root_path.read_bytes() != candidate_raw:
            raise ValidationError(
                "pre-existing COMMANDMENTS.md differs from the staged digest; preserve it and stage exact adoption"
            )
    else:
        atomic_write(root_path, candidate_raw)
    interview_artifact = next(
        item for item in manifest["artifacts"] if item["path"] == COMMANDMENTS_INTERVIEW_PATH
    )
    approval_digest = sha256_bytes(
        canonical_json({"candidateSha256": candidate_sha, "operatorMarker": marker})
    )
    index = len(manifest["transitions"]) + 1
    receipt_relative = (
        f".pi/jig/receipts/transition-{index:04d}-commandments-ratified.json"
    )
    receipt_path = fixed_artifact_path(root, receipt_relative)
    if receipt_path.exists():
        receipt = read_json(receipt_path, "COMMANDMENTS ratification receipt")
        validate_transition_receipt(
            root,
            receipt,
            ("awaiting-commandments", "commandments-ratified"),
            manifest["source"],
        )
        expected_receipt = {
            "resourceIsolation": isolation,
            "interviewPath": COMMANDMENTS_INTERVIEW_PATH,
            "interviewSha256": interview_artifact["sha256"],
            "answersPath": staging["answersPath"],
            "answersSha256": staging["answersSha256"],
            "candidatePath": staging["candidatePath"],
            "commandmentsPath": COMMANDMENTS_ROOT_PATH,
            "commandmentsSha256": candidate_sha,
            "version": metadata["version"],
            "operatorMarker": marker,
            "approvalDigest": approval_digest,
            "at": metadata["ratifiedAt"],
        }
        if any(receipt.get(key) != value for key, value in expected_receipt.items()):
            raise ValidationError("existing ratification receipt differs from this approval")
        receipt_raw = receipt_path.read_bytes()
    else:
        receipt = receipt_value(
            "commandments-ratified",
            "awaiting-commandments",
            "commandments-ratified",
            manifest["source"],
            recordedAt=now(),
            resourceIsolation=isolation,
            interviewPath=COMMANDMENTS_INTERVIEW_PATH,
            interviewSha256=interview_artifact["sha256"],
            answersPath=staging["answersPath"],
            answersSha256=staging["answersSha256"],
            candidatePath=staging["candidatePath"],
            commandmentsPath=COMMANDMENTS_ROOT_PATH,
            commandmentsSha256=candidate_sha,
            version=metadata["version"],
            operatorMarker=marker,
            approvalDigest=approval_digest,
        )
        receipt["at"] = metadata["ratifiedAt"]
        receipt_raw = canonical_json(receipt)
        atomic_write(receipt_path, receipt_raw)
    receipt_digest = sha256_bytes(receipt_raw)
    manifest["transitions"].append(
        {
            "from": "awaiting-commandments",
            "to": "commandments-ratified",
            "at": receipt["at"],
            "receiptPath": receipt_relative,
            "receiptSha256": receipt_digest,
        }
    )
    upsert_artifact(manifest, receipt_relative, "controller", receipt_digest)
    upsert_artifact(manifest, COMMANDMENTS_ROOT_PATH, "human", candidate_sha)
    manifest["commandments"] = {
        "path": COMMANDMENTS_ROOT_PATH,
        "sha256": candidate_sha,
        "version": metadata["version"],
        "ratifiedAt": metadata["ratifiedAt"],
    }
    manifest["currentState"] = "commandments-ratified"
    manifest["updatedAt"] = receipt["at"]
    write_manifest(root, manifest)
    return manifest


def validate_commandments(root: Path, isolation: str) -> Dict[str, Any]:
    return require_commandments_boundary(root, isolation, ("commandments-ratified",))


def propose_commandments_amendment(
    root: Path, isolation: str, raw: bytes
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(root, isolation, ("commandments-ratified",))
    if not raw or len(raw) > 64 * 1024:
        raise ValidationError("COMMANDMENTS amendment proposal is empty or too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError("COMMANDMENTS amendment proposal is not UTF-8") from error
    if not text.strip() or "Human decision: ratified" in text:
        raise ValidationError("COMMANDMENTS amendment proposal is empty or claims ratification")
    proposal_raw = raw if raw.endswith(b"\n") else raw + b"\n"
    path, digest = content_addressed_artifact(
        root, "proposals", "md", proposal_raw
    )
    expected = {"path": path, "owner": "jig-skill", "sha256": digest}
    artifact = next((item for item in manifest["artifacts"] if item["path"] == path), None)
    if artifact != expected:
        upsert_artifact(manifest, path, "jig-skill", digest)
        manifest["updatedAt"] = now()
        write_manifest(root, manifest)
    return manifest, {"path": path, "sha256": digest}


def render_result(manifest: Mapping[str, Any]) -> None:
    result = {
        "root": ".",
        "state": manifest["currentState"],
        "resourceIsolation": manifest["resourceIsolation"],
    }
    if manifest["currentState"] == "awaiting-commandments":
        result["resume"] = (
            "Write the complete one-round response to "
            ".pi/jig/commandments/answers.input.json, then rerun jig init through the same route."
        )
    print(json.dumps(result, sort_keys=True))


def command_validate_schema(arguments: argparse.Namespace) -> int:
    schema = load_schema(arguments.schema)
    document = read_json(Path(arguments.document), "document")
    validate_instance(document, schema)
    print(f"valid {arguments.schema}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(prog="jigctl.py")
    subparsers = result.add_subparsers(dest="command", required=True)
    mutating = (
        "start",
        "commit-profile",
        "record-failure",
        "present-commandments",
        "stage-commandments",
        "record-commandments-decision",
        "ratify-commandments",
        "validate-commandments",
        "propose-commandments-amendment",
    )
    commands = {}
    for name in mutating:
        command = subparsers.add_parser(name)
        command.add_argument(
            "--resource-isolation",
            required=True,
            choices=("isolated-shell", "inherited-session"),
        )
        commands[name] = command
    commands["record-failure"].add_argument(
        "--state",
        required=True,
        choices=("surveying", "awaiting-commandments", "commandments-ratified"),
    )
    commands["record-failure"].add_argument("--reason", required=True)
    commands["stage-commandments"].add_argument("--amend-candidate-sha")
    commands["stage-commandments"].add_argument("--adopt-existing", action="store_true")
    commands["record-commandments-decision"].add_argument(
        "--decision", required=True, choices=("amend", "defer")
    )
    commands["record-commandments-decision"].add_argument("--candidate-sha")
    commands["record-commandments-decision"].add_argument(
        "--operator-marker", required=True
    )
    commands["ratify-commandments"].add_argument("--candidate-sha", required=True)
    commands["ratify-commandments"].add_argument("--operator-marker", required=True)
    validate = subparsers.add_parser("validate-schema")
    validate.add_argument("--schema", required=True)
    validate.add_argument("--document", required=True)
    return result


def main(argv: Optional[Sequence[str]] = None) -> int:
    arguments = parser().parse_args(argv)
    if arguments.command == "validate-schema":
        return command_validate_schema(arguments)
    root = resolve_git_root()
    output: Optional[Mapping[str, Any]] = None
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
        elif arguments.command == "commit-profile":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest = commit_profile(root, arguments.resource_isolation, lock, raw)
        elif arguments.command == "present-commandments":
            output = present_commandments(root, arguments.resource_isolation)
            manifest = load_existing_manifest(root)
        elif arguments.command == "stage-commandments":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest, staging = stage_commandments(
                root,
                arguments.resource_isolation,
                raw,
                arguments.amend_candidate_sha,
                arguments.adopt_existing,
            )
            output = {"state": manifest["currentState"], **staging}
        elif arguments.command == "record-commandments-decision":
            manifest, output = record_commandments_decision(
                root,
                arguments.resource_isolation,
                arguments.decision,
                arguments.candidate_sha,
                arguments.operator_marker,
            )
        elif arguments.command == "ratify-commandments":
            manifest = ratify_commandments(
                root,
                arguments.resource_isolation,
                arguments.candidate_sha,
                arguments.operator_marker,
            )
        elif arguments.command == "validate-commandments":
            manifest = validate_commandments(root, arguments.resource_isolation)
        else:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest, output = propose_commandments_amendment(
                root, arguments.resource_isolation, raw
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
            "Recovery: preserve .pi/jig, inspect the named state or lock, correct only that problem, and rerun jig init.",
            file=sys.stderr,
        )
        raise SystemExit(1)

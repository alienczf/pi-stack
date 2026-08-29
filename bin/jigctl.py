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
import resource
import signal
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
    "surveying", "awaiting-commandments", "commandments-ratified",
    "verification-building", "verification-ready", "step-selecting", "step-running",
    "initialized", "failed-surveying", "failed-awaiting-commandments",
    "failed-commandments-ratified", "failed-verification-building",
    "failed-verification-ready", "failed-step-selecting", "failed-step-running",
}
TRANSITION_KIND_BY_EDGE = {
    ("absent", "surveying"): "init-started",
    ("surveying", "awaiting-commandments"): "profile-committed",
    ("awaiting-commandments", "commandments-ratified"): "commandments-ratified",
    ("commandments-ratified", "verification-building"): "verification-started",
    ("verification-building", "verification-ready"): "verification-ready",
    ("verification-ready", "step-selecting"): "step-selection-started",
    ("step-selecting", "step-running"): "step-worker-activated",
    ("step-selecting", "initialized"): "no-candidate-finalized",
    **{(state, f"failed-{state}"): "phase-failed" for state in (
        "surveying", "awaiting-commandments", "commandments-ratified",
        "verification-building", "verification-ready", "step-selecting", "step-running",
    )},
    **{(f"failed-{state}", state): "failed-state-reconciled" for state in (
        "surveying", "awaiting-commandments", "commandments-ratified",
        "verification-building", "verification-ready", "step-selecting", "step-running",
    )},
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
COMMANDMENTS_ROOT_TEMP_PATTERN = re.compile(
    r"\.jigctl-COMMANDMENTS\.md\.([0-9a-f]{64})\.([0-9]+)\.([0-9a-f]{32})\.tmp"
)
VERIFICATION_PLAN_PATH = ".pi/jig/verification/plan.json"
VERIFICATION_SKILL_PATH = ".pi/skills/jig-verification/SKILL.md"
VERIFICATION_FEATURE_INDEX_PATH = ".pi/skills/jig-verification/references/features/index.md"
VERIFICATION_OUTPUT_LIMIT = 256 * 1024
VERIFICATION_ID = re.compile(r"[a-z0-9][a-z0-9-]{0,63}")
SELECTION_PATH = ".pi/jig/steps/0001/selection.json"
PROPOSAL_PATH = ".pi/jig/steps/0001/proposal.json"
RESULT_PATH = ".pi/jig/steps/0001/result.json"
BEFORE_PATH = ".pi/jig/steps/0001/before.json"
STEP_WORKTREE = ".pi/jig/worktrees/0001"
WORKER_PATH = ".pi/jig/steps/0001/worker.json"
WORKER_DRAFT_FIELDS = {"schemaVersion", "stepId", "workerSessionId", "allowedPaths"}
WORKER_PROTECTED_PATHS = [".git", ".pi", "COMMANDMENTS.md", "eval", "evals"]
BASELINE_OUTPUT_LIMIT = 256 * 1024
BASELINE_TIMEOUT_SECONDS = 120
SELECTION_DRAFT_FIELDS = {
    "schemaVersion", "stepId", "repositoryRevision", "commandmentsSha256",
    "candidates", "selectedCandidateId", "rankingSummary",
}
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


def source_record(root: Path, excluded_paths: Sequence[str] = ()) -> Dict[str, Any]:
    revision = run_git(root, ["rev-parse", "HEAD"])
    if re.fullmatch(r"[0-9a-f]{40,64}", revision) is None:
        raise JigError("the repository has no valid HEAD revision")
    pathspecs = [".", ":(exclude).pi/jig", ":(exclude)COMMANDMENTS.md"]
    for value in excluded_paths:
        pure = PurePosixPath(value)
        if (
            not isinstance(value, str)
            or pure.is_absolute()
            or any(part in {"", ".", ".."} for part in pure.parts)
            or "\\" in value
        ):
            raise ValidationError("source exclusion is not a contained relative path")
        pathspecs.append(f":(exclude){value}")
    raw_status = run_git(
        root,
        ["status", "--porcelain=v1", "--untracked-files=all", "--", *pathspecs],
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


def atomic_write(path: Path, data: bytes, ownership_token: Optional[str] = None) -> None:
    if not path.parent.is_dir() or path.parent.is_symlink():
        raise JigError(f"atomic-write parent is unsafe: {path.parent.name}")
    token = f".{ownership_token}" if ownership_token is not None else ""
    temporary = (
        path.parent
        / f".jigctl-{path.name}{token}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    )
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
    elif kind == "verification-started":
        expected_fields.update(
            {
                "resourceIsolation",
                "planPath",
                "planSha256",
                "commandmentsSha256",
                "protectedFeatureId",
            }
        )
    elif kind == "verification-ready":
        expected_fields.update(
            {
                "resourceIsolation",
                "planPath",
                "planSha256",
                "commandmentsSha256",
                "protectedFeatureId",
                "skillPath",
                "skillSha256",
                "featureIndexPath",
                "featureIndexSha256",
                "runtimeReceiptPath",
                "runtimeReceiptSha256",
            }
        )
    elif kind == "step-selection-started":
        expected_fields.update(
            {
                "resourceIsolation",
                "commandmentsSha256",
                "runtimeReceiptPath",
                "runtimeReceiptSha256",
            }
        )
    elif kind == "step-worker-activated":
        expected_fields.update({
            "resourceIsolation", "commandmentsSha256", "selectionSha256",
            "proposalSha256", "beforeSha256", "workerSha256",
            "inputRevision", "branch", "worktree",
        })
    elif kind == "no-candidate-finalized":
        expected_fields.update(
            {
                "resourceIsolation", "commandmentsSha256", "selectionPath",
                "selectionSha256", "resultPath", "resultSha256",
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
    elif kind in {"verification-started", "verification-ready"}:
        if (
            not isinstance(receipt["resourceIsolation"], str)
            or receipt["resourceIsolation"] not in {"isolated-shell", "inherited-session"}
            or receipt["planPath"] != VERIFICATION_PLAN_PATH
            or not isinstance(receipt["planSha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", receipt["planSha256"]) is None
            or not isinstance(receipt["commandmentsSha256"], str)
            or re.fullmatch(r"[0-9a-f]{64}", receipt["commandmentsSha256"]) is None
            or not isinstance(receipt["protectedFeatureId"], str)
            or VERIFICATION_ID.fullmatch(receipt["protectedFeatureId"]) is None
        ):
            raise ValidationError("verification transition receipt is inconsistent")
        paths = [(receipt["planPath"], receipt["planSha256"])]
        if kind == "verification-ready":
            if (
                receipt["skillPath"] != VERIFICATION_SKILL_PATH
                or receipt["featureIndexPath"] != VERIFICATION_FEATURE_INDEX_PATH
                or re.fullmatch(r"[0-9a-f]{64}", receipt["skillSha256"]) is None
                or re.fullmatch(r"[0-9a-f]{64}", receipt["featureIndexSha256"]) is None
                or re.fullmatch(r"[0-9a-f]{64}", receipt["runtimeReceiptSha256"]) is None
            ):
                raise ValidationError("verification-ready receipt has invalid artifacts")
            paths.extend(
                [
                    (receipt["skillPath"], receipt["skillSha256"]),
                    (receipt["featureIndexPath"], receipt["featureIndexSha256"]),
                    (receipt["runtimeReceiptPath"], receipt["runtimeReceiptSha256"]),
                ]
            )
        for path_value, digest in paths:
            path = safe_relative_path(root, path_value, must_exist=True)
            if path.is_symlink() or not path.is_file() or sha256_file(path) != digest:
                raise ValidationError("verification transition artifact hash is inconsistent")
    elif kind == "step-selection-started":
        if (
            receipt["resourceIsolation"] not in {"isolated-shell", "inherited-session"}
            or re.fullmatch(r"[0-9a-f]{64}", receipt["commandmentsSha256"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", receipt["runtimeReceiptSha256"]) is None
        ):
            raise ValidationError("step-selection transition receipt is inconsistent")
        runtime_path = safe_relative_path(root, receipt["runtimeReceiptPath"], must_exist=True)
        if runtime_path.is_symlink() or not runtime_path.is_file() or sha256_file(runtime_path) != receipt["runtimeReceiptSha256"]:
            raise ValidationError("step-selection runtime receipt hash is inconsistent")
    elif kind == "no-candidate-finalized":
        fixed = {
            "selectionPath": SELECTION_PATH,
            "resultPath": RESULT_PATH,
        }
        if (
            receipt["resourceIsolation"] not in {"isolated-shell", "inherited-session"}
            or receipt["selectionPath"] != fixed["selectionPath"]
            or receipt["resultPath"] != fixed["resultPath"]
            or re.fullmatch(r"[0-9a-f]{64}", receipt["commandmentsSha256"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", receipt["selectionSha256"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", receipt["resultSha256"]) is None
        ):
            raise ValidationError("no-candidate transition receipt is inconsistent")
        for path_key, digest_key in (("selectionPath", "selectionSha256"), ("resultPath", "resultSha256")):
            path = safe_relative_path(root, receipt[path_key], must_exist=True)
            if path.is_symlink() or not path.is_file() or sha256_file(path) != receipt[digest_key]:
                raise ValidationError("no-candidate transition artifact hash is inconsistent")
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
        r"steps/0001/(?:(?:selection|proposal|result|before|worker)\.json|commands/baseline-[0-9]{2}\.json)|"
        r"verification/(?:plan\.json|receipts/runtime-[0-9a-f]{64}\.json|"
        r"evidence/[a-z0-9][a-z0-9._-]{0,127}\.json)|receipts/(?:transition-[0-9]{4}-(?:"
        + implemented_state
        + r")\.json|lock-reclaimed-[0-9a-f]{16}\.json|"
        + r"interrupted-write-[0-9a-f]{64}\.bin|interrupted-transition-[0-9a-f]{64}\.json))|"
        + r"\.pi/skills/jig-verification/(?:SKILL\.md|helpers/[a-z0-9][a-z0-9-]{0,63}\.py|"
        + r"references/features/(?:index|[a-z0-9][a-z0-9-]{0,63})\.md))$"
    )
    for artifact in artifacts:
        artifact_path = artifact["path"]
        if allowed_artifact.fullmatch(artifact_path) is None:
            raise ValidationError(f"manifest names an unknown owned artifact: {artifact_path}")
        if artifact_path == COMMANDMENTS_ROOT_PATH or "/answers/" in artifact_path:
            expected_owner = "human"
        elif (
            artifact_path == ".pi/jig/profile.json"
            or artifact_path == VERIFICATION_PLAN_PATH
            or artifact_path.startswith(".pi/skills/jig-verification/")
            or "/proposals/" in artifact_path
        ):
            expected_owner = "jig-skill"
        elif "/verification/evidence/" in artifact_path:
            expected_owner = "repository"
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
        if artifact_path == SELECTION_PATH:
            validate_committed_selection(root, manifest, read_json(path, "selection"))
    proposal_artifact = next((item for item in artifacts if item["path"] == PROPOSAL_PATH), None)
    if proposal_artifact is not None:
        proposal_path = safe_relative_path(root, PROPOSAL_PATH, must_exist=True)
        validate_committed_proposal(root, manifest, read_json(proposal_path, "proposal"))
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
        elif kind in {"verification-started", "verification-ready"}:
            plan_artifact = next(
                (item for item in artifacts if item["path"] == VERIFICATION_PLAN_PATH),
                None,
            )
            plan = read_json(root / VERIFICATION_PLAN_PATH, "verification plan")
            if (
                receipt_data["resourceIsolation"] != manifest["resourceIsolation"]
                or receipt_data["commandmentsSha256"] != manifest["commandments"]["sha256"]
                or plan_artifact is None
                or receipt_data["planSha256"] != plan_artifact["sha256"]
                or receipt_data["protectedFeatureId"] != plan.get("protectedFeatureId")
            ):
                raise ValidationError("verification transition receipt is inconsistent with the manifest")
            if kind == "verification-ready":
                if (
                    len(manifest["verification"]) != 1
                    or receipt_data["runtimeReceiptPath"] != manifest["verification"][0]["receiptPath"]
                ):
                    raise ValidationError("verification-ready receipt differs from the runtime record")
        elif kind == "step-selection-started":
            record = manifest["verification"][0] if len(manifest["verification"]) == 1 else None
            if (
                receipt_data["resourceIsolation"] != manifest["resourceIsolation"]
                or receipt_data["commandmentsSha256"] != manifest["commandments"]["sha256"]
                or record is None
                or receipt_data["runtimeReceiptPath"] != record["receiptPath"]
                or receipt_data["runtimeReceiptSha256"] != next(
                    (item["sha256"] for item in artifacts if item["path"] == record["receiptPath"]),
                    None,
                )
            ):
                raise ValidationError("step-selection transition differs from its verified boundary")
        elif kind == "step-worker-activated":
            worker_artifact = next((item for item in artifacts if item["path"] == WORKER_PATH), None)
            worker = read_json(root / WORKER_PATH, "worker receipt")
            fixed = {
                "resourceIsolation": manifest["resourceIsolation"],
                "commandmentsSha256": manifest["commandments"]["sha256"],
                "selectionSha256": worker["selectionSha256"],
                "proposalSha256": worker["proposalSha256"],
                "beforeSha256": worker["beforeSha256"],
                "workerSha256": worker_artifact["sha256"] if worker_artifact else None,
                "inputRevision": worker["inputRevision"], "branch": worker["branch"],
                "worktree": worker["worktree"],
            }
            if any(receipt_data.get(key) != value for key, value in fixed.items()):
                raise ValidationError("worker activation transition differs from its authorization")
        elif kind == "no-candidate-finalized":
            selection_artifact = next((item for item in artifacts if item["path"] == SELECTION_PATH), None)
            result_artifact = next((item for item in artifacts if item["path"] == RESULT_PATH), None)
            if (
                receipt_data["resourceIsolation"] != manifest["resourceIsolation"]
                or receipt_data["commandmentsSha256"] != manifest["commandments"]["sha256"]
                or selection_artifact is None
                or receipt_data["selectionSha256"] != selection_artifact["sha256"]
                or result_artifact is None
                or receipt_data["resultSha256"] != result_artifact["sha256"]
            ):
                raise ValidationError("no-candidate transition differs from its committed boundary")
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
        "verification-building",
        "failed-verification-building",
        "verification-ready", "failed-verification-ready",
        "step-selecting", "failed-step-selecting", "step-running",
        "failed-step-running", "initialized",
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
    if state in {
        "commandments-ratified",
        "failed-commandments-ratified",
        "verification-building",
        "failed-verification-building",
        "verification-ready", "failed-verification-ready",
        "step-selecting", "failed-step-selecting", "step-running",
        "failed-step-running", "initialized",
    }:
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
    if state in {
        "verification-ready", "failed-verification-ready",
        "step-selecting", "failed-step-selecting", "step-running",
        "failed-step-running", "initialized",
    }:
        validate_verification_ready(root, manifest)
    if state in {"step-running", "failed-step-running"}:
        validate_step_worker(root, manifest)
    if state == "initialized":
        validate_no_candidate_result(root, manifest)


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
            "selectionPath": SELECTION_PATH,
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


def verification_reserved_paths(root: Path, manifest: Mapping[str, Any]) -> List[str]:
    if manifest["currentState"] not in {
        "verification-building",
        "failed-verification-building",
        "verification-ready",
        "failed-verification-ready",
        "step-selecting", "failed-step-selecting", "step-running",
        "failed-step-running", "initialized",
    }:
        return []
    plan = read_json(root / VERIFICATION_PLAN_PATH, "verification plan")
    paths = plan.get("reservedPaths") if isinstance(plan, dict) else None
    if not isinstance(paths, list) or any(not isinstance(item, str) for item in paths):
        raise ValidationError("verification plan has invalid reserved paths")
    return list(paths)


def validate_current_source(root: Path, manifest: Mapping[str, Any]) -> None:
    if source_record(root, verification_reserved_paths(root, manifest)) != manifest["source"]:
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


def reconcile_commandments_root_temporaries(
    root: Path, manifest: Mapping[str, Any]
) -> List[Tuple[str, str]]:
    if manifest["currentState"] != "awaiting-commandments":
        return []
    staging = load_staging(root, manifest)
    if staging is None or not staging_artifacts_registered(manifest, staging):
        return []
    candidate = safe_relative_path(
        root, staging["candidatePath"], must_exist=True
    ).read_bytes()
    candidate_digest = staging["candidateSha256"]
    receipts = ensure_owned_directory(root, ".pi/jig/receipts")
    recovered: List[Tuple[str, str]] = []
    for path in sorted(root.iterdir()):
        match = COMMANDMENTS_ROOT_TEMP_PATTERN.fullmatch(path.name)
        if match is None:
            continue
        try:
            details = path.lstat()
        except OSError as error:
            raise JigError("COMMANDMENTS temporary cannot be inspected") from error
        if not stat.S_ISREG(details.st_mode) or details.st_size > len(candidate):
            continue
        raw = path.read_bytes()
        token = match.group(1)
        owned = (
            token == candidate_digest
            and bool(raw)
            and candidate.startswith(raw)
        )
        if not owned:
            continue
        digest = sha256_bytes(raw)
        destination = receipts / f"interrupted-write-{digest}.bin"
        if destination.exists() or destination.is_symlink():
            if (
                destination.is_symlink()
                or not destination.is_file()
                or sha256_file(destination) != digest
            ):
                raise JigError(
                    "interrupted-write evidence collides with an existing unknown file"
                )
            path.unlink()
        else:
            os.rename(path, destination)
        recovered.append((relative_to_root(root, destination), digest))
    return recovered


def start(root: Path, isolation: str, lock: RepositoryLock) -> Dict[str, Any]:
    manifest_path = root / ".pi" / "jig" / "manifest.json"
    if manifest_path.exists():
        if manifest_path.is_symlink():
            raise ValidationError("manifest path is a symlink")
        manifest = load_existing_manifest(root)
        if manifest["resourceIsolation"] != isolation:
            raise JigError("the existing manifest uses a different resourceIsolation route")
        root_recovery = reconcile_commandments_root_temporaries(root, manifest)
        validate_current_source(root, manifest)
        recovered = (
            root_recovery
            + reconcile_temporary_files(root)
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
        elif state == "failed-verification-building":
            append_transition(
                root, manifest, state, "verification-building", "failed-state-reconciled"
            )
            changed = True
            reconciled = True
        elif state == "failed-verification-ready":
            append_transition(
                root, manifest, state, "verification-ready", "failed-state-reconciled"
            )
            changed = True
            reconciled = True
        elif state == "failed-step-selecting":
            append_transition(
                root, manifest, state, "step-selecting", "failed-state-reconciled"
            )
            changed = True
            reconciled = True
        elif state == "failed-step-running":
            validate_step_worker(root, manifest)
            append_transition(
                root, manifest, state, "step-running", "failed-state-reconciled"
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
    if (
        not text.endswith("\n")
        or "{{" in text
        or "}}" in text
        or "TEMPLATE, NOT RATIFIED" in text
    ):
        raise ValidationError(
            "COMMANDMENTS contains a template marker or lacks its final newline"
        )
    if any(
        (ord(character) < 32 and character != "\n")
        or 127 <= ord(character) <= 159
        for character in text
    ):
        raise ValidationError("COMMANDMENTS contains a control character")
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
    section_positions = []
    for section in required_sections:
        matches = list(
            re.finditer(rf"^{re.escape(section)}$", text, flags=re.MULTILINE)
        )
        if len(matches) != 1:
            raise ValidationError(
                "COMMANDMENTS does not match the checked-in section structure"
            )
        section_positions.append(matches[0].start())
    if section_positions != sorted(section_positions):
        raise ValidationError("COMMANDMENTS sections are out of order")
    id_matches = list(
        re.finditer(r"^### (CMD-[0-9]{3})\. .+$", text, flags=re.MULTILINE)
    )
    ids = [match.group(1) for match in id_matches]
    if ids != ["CMD-001", "CMD-002", "CMD-101", "CMD-102"]:
        raise ValidationError(
            "COMMANDMENTS has missing, duplicate, or unstable commandment IDs"
        )
    hard_start = section_positions[1]
    directional_start = section_positions[2]
    protected_start = section_positions[3]
    if not (
        hard_start < id_matches[0].start() < id_matches[1].start() < directional_start
        < id_matches[2].start() < id_matches[3].start() < protected_start
    ):
        raise ValidationError(
            "COMMANDMENTS hard and directional entries are misplaced"
        )
    block_ends = (
        id_matches[1].start(),
        directional_start,
        id_matches[3].start(),
        protected_start,
    )
    labels = ("Statement", "Scope", "Priority", "Proof", "Exceptions", "Owner")
    for match, end in zip(id_matches, block_ends):
        block = text[match.start():end]
        for label in labels:
            values = re.findall(
                rf"^\*\*{label}\.\*\* (.+)$", block, flags=re.MULTILINE
            )
            if len(values) != 1:
                raise ValidationError(
                    f"COMMANDMENTS {match.group(1)} has an invalid {label} field"
                )
            bounded_text(
                values[0], f"COMMANDMENTS {match.group(1)} {label}", 4000
            )

    def section_lines(index: int) -> List[str]:
        start = text.index("\n", section_positions[index]) + 1
        end = (
            section_positions[index + 1]
            if index + 1 < len(section_positions)
            else len(text)
        )
        return [line for line in text[start:end].splitlines() if line]

    def ordered_values(
        index: int, labels: Sequence[str], pattern: str, kind: str
    ) -> List[str]:
        lines = section_lines(index)
        values = []
        positions = []
        for label in labels:
            matches = [
                (line_index, match.group(1))
                for line_index, line in enumerate(lines)
                for match in [re.fullmatch(pattern.format(label=re.escape(label)), line)]
                if match is not None
            ]
            if len(matches) != 1:
                raise ValidationError(
                    f"COMMANDMENTS {kind} has an invalid {label} field"
                )
            positions.append(matches[0][0])
            values.append(
                bounded_text(
                    matches[0][1], f"COMMANDMENTS {kind} {label}", 4000
                )
            )
        if positions != sorted(positions) or len(lines) != len(labels):
            raise ValidationError(f"COMMANDMENTS {kind} fields are misplaced")
        return values

    ordered_values(
        3,
        ("Action", "Visible result", "Evidence", "Cleanup", "Thresholds"),
        r"\*\*{label}\.\*\* (.+)",
        "protected user path",
    )
    ordered_values(
        4,
        (
            "Baseline requirement",
            "Targeted verification",
            "Product regression floor",
            "Seeded guard proof",
            "Independent review",
            "Behavioral eval",
        ),
        r"- {label}: (.+)",
        "proof policy",
    )
    compatibility = section_lines(5)
    if not compatibility:
        raise ValidationError("COMMANDMENTS compatibility policy is empty")
    for line in compatibility:
        bounded_text(line, "COMMANDMENTS compatibility policy", 4000)
    autonomy_lines = section_lines(6)
    autonomy = []
    for line in autonomy_lines:
        match = re.fullmatch(r"- (.+)", line)
        if match is None:
            raise ValidationError("COMMANDMENTS autonomy policy is malformed")
        autonomy.append(
            bounded_text(match.group(1), "COMMANDMENTS autonomy policy", 1000)
        )
    if not autonomy or len(autonomy) != len(set(autonomy)):
        raise ValidationError("COMMANDMENTS autonomy policy is empty or duplicated")
    tradeoff_lines = section_lines(7)
    tradeoffs = []
    numbers = []
    for line in tradeoff_lines:
        match = re.fullmatch(r"([1-9][0-9]*)\. (.+)", line)
        if match is None:
            raise ValidationError("COMMANDMENTS tradeoff order is malformed")
        numbers.append(int(match.group(1)))
        tradeoffs.append(
            bounded_text(match.group(2), "COMMANDMENTS tradeoff entry", 1000)
        )
    if (
        not tradeoffs
        or numbers != list(range(1, len(numbers) + 1))
        or len(tradeoffs) != len(set(tradeoffs))
    ):
        raise ValidationError("COMMANDMENTS tradeoff order is empty or ambiguous")
    amendment_lines = section_lines(8)
    amendment_prefix = "Free-text amendments from the interview: "
    if (
        len(amendment_lines) < 2
        or not amendment_lines[-1].startswith(amendment_prefix)
        or sum(line.startswith(amendment_prefix) for line in amendment_lines) != 1
    ):
        raise ValidationError("COMMANDMENTS amendment policy is incomplete")
    for line in amendment_lines[:-1]:
        bounded_text(line, "COMMANDMENTS amendment policy", 4000)
    bounded_text(
        amendment_lines[-1][len(amendment_prefix):],
        "COMMANDMENTS free-text amendments",
        4000,
    )

    def unique_line(label: str, pattern: str) -> re.Match[str]:
        matches = list(re.finditer(pattern, text, flags=re.MULTILINE))
        if len(matches) != 1:
            raise ValidationError(f"COMMANDMENTS {label} metadata is invalid")
        return matches[0]
    status = unique_line("status", r"^Status: (.+)$")
    owner = unique_line("owner", r"^Owner: (.+)$")
    timestamp = unique_line("timestamp", r"^Ratified at: (.+)$")
    version = unique_line("version", r"^Version: ([0-9]+)$")
    scope = unique_line("scope", r"^Scope: (.+)$")
    marker = unique_line("ratification marker", r"^Human note: (.+)$")
    decision = unique_line("decision", r"^Human decision: (.+)$")
    if (
        status.group(1) != "RATIFIED"
        or decision.group(1) != "ratified"
        or not (
            section_positions[0] == 0
            and section_positions[0] < status.start() < owner.start()
            < timestamp.start() < version.start() < scope.start() < hard_start
            and section_positions[-1] < decision.start() < marker.start()
        )
    ):
        raise ValidationError("COMMANDMENTS ratification metadata is incomplete")
    if not valid_datetime(timestamp.group(1)):
        raise ValidationError("COMMANDMENTS ratification timestamp is invalid")
    parsed_version = int(version.group(1))
    if parsed_version < 1:
        raise ValidationError("COMMANDMENTS version is invalid")
    bounded_text(owner.group(1), "COMMANDMENTS owner", 1000)
    bounded_text(scope.group(1), "COMMANDMENTS scope", 2000)
    bounded_text(marker.group(1), "COMMANDMENTS ratification marker", 200)
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


def load_staging(
    root: Path, manifest: Optional[Mapping[str, Any]] = None
) -> Optional[Dict[str, Any]]:
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
        "previousCandidateSha256",
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
        or (
            value["previousCandidateSha256"] is not None
            and (
                not isinstance(value["previousCandidateSha256"], str)
                or re.fullmatch(
                    r"[0-9a-f]{64}", value["previousCandidateSha256"]
                )
                is None
            )
        )
        or not isinstance(value["sourceRevision"], str)
        or re.fullmatch(r"[0-9a-f]{40,64}", value["sourceRevision"]) is None
        or not isinstance(value["interviewSha256"], str)
        or re.fullmatch(r"[0-9a-f]{64}", value["interviewSha256"]) is None
        or not isinstance(value["choiceModes"], dict)
        or set(value["choiceModes"]) != set(COMMANDMENTS_ANSWER_KEYS)
        or any(
            mode not in {"default", "custom"}
            for mode in value["choiceModes"].values()
        )
    ):
        raise ValidationError("COMMANDMENTS staging record has invalid metadata")
    if manifest is not None:
        interview = next(
            (
                item
                for item in manifest["artifacts"]
                if item["path"] == COMMANDMENTS_INTERVIEW_PATH
            ),
            None,
        )
        if (
            value["sourceRevision"] != manifest["source"]["revision"]
            or interview is None
            or value["interviewSha256"] != interview["sha256"]
        ):
            raise ValidationError(
                "COMMANDMENTS staging record differs from its manifest boundary"
            )
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
            raise ValidationError(
                "COMMANDMENTS staging record has an invalid content address"
            )
        artifact_path = safe_relative_path(root, expected_path, must_exist=True)
        if (
            artifact_path.is_symlink()
            or not artifact_path.is_file()
            or sha256_file(artifact_path) != digest
        ):
            raise ValidationError("COMMANDMENTS staging artifact hash changed")
    answers = read_json(
        root / value["answersPath"], "staged COMMANDMENTS answers"
    )
    resolved, modes = validate_commandments_answers(answers)
    if modes != value["choiceModes"]:
        raise ValidationError(
            "COMMANDMENTS staging choice evidence is inconsistent"
        )
    candidate_raw = (root / value["candidatePath"]).read_bytes()
    metadata = validate_commandments_bytes(candidate_raw)
    if (
        metadata["version"] != value["version"]
        or metadata["ratifiedAt"] != value["prospectiveRatifiedAt"]
    ):
        raise ValidationError(
            "COMMANDMENTS staging candidate metadata is inconsistent"
        )
    if not (
        resolved["authority"]["ratificationMarker"]
        == value["intendedMarker"]
        == metadata["marker"]
    ):
        raise ValidationError(
            "COMMANDMENTS staging answer and candidate markers are inconsistent"
        )
    if value["adoptedExisting"]:
        root_path = fixed_artifact_path(
            root, COMMANDMENTS_ROOT_PATH, create_parent=False
        )
        if not root_path.exists() or root_path.read_bytes() != candidate_raw:
            raise ValidationError(
                "adopted COMMANDMENTS staging no longer matches the root file"
            )
    else:
        expected_candidate = render_commandments_candidate(
            resolved,
            value["prospectiveRatifiedAt"],
            value["version"],
        )
        if (
            expected_candidate != candidate_raw
            or sha256_bytes(expected_candidate) != value["candidateSha256"]
        ):
            raise ValidationError(
                "generated COMMANDMENTS staging differs from its exact answers"
            )
    return value


def staging_artifacts_registered(
    manifest: Mapping[str, Any], staging: Mapping[str, Any]
) -> bool:
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    return (
        artifacts.get(staging["answersPath"])
        == {
            "path": staging["answersPath"],
            "owner": "human",
            "sha256": staging["answersSha256"],
        }
        and artifacts.get(staging["candidatePath"])
        == {
            "path": staging["candidatePath"],
            "owner": "controller",
            "sha256": staging["candidateSha256"],
        }
    )


def parse_commandments_decision(raw: bytes) -> Optional[Dict[str, Any]]:
    expected = {
        "schemaVersion",
        "kind",
        "decision",
        "candidateSha256",
        "operatorMarker",
        "at",
        "sourceRevision",
        "resourceIsolation",
    }
    try:
        value = read_json_bytes(raw, "COMMANDMENTS decision")
        if not isinstance(value, dict) or set(value) != expected:
            return None
        bounded_text(value["operatorMarker"], "decision operator marker", 200)
    except ValidationError:
        return None
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "commandments-decision"
        or value["decision"] not in {"amend", "defer"}
        or (
            value["candidateSha256"] is not None
            and (
                not isinstance(value["candidateSha256"], str)
                or re.fullmatch(r"[0-9a-f]{64}", value["candidateSha256"])
                is None
            )
        )
        or (
            value["decision"] == "amend"
            and value["candidateSha256"] is None
        )
        or not isinstance(value["at"], str)
        or not valid_datetime(value["at"])
        or value["resourceIsolation"] not in {"isolated-shell", "inherited-session"}
        or not isinstance(value["sourceRevision"], str)
    ):
        return None
    return value


def decision_matches(
    value: Mapping[str, Any],
    manifest: Mapping[str, Any],
    decision: str,
    candidate_sha: Optional[str],
    operator_marker: str,
    isolation: str,
) -> bool:
    return (
        value["decision"] == decision
        and value["candidateSha256"] == candidate_sha
        and value["operatorMarker"] == operator_marker
        and value["sourceRevision"] == manifest["source"]["revision"]
        and value["resourceIsolation"] == isolation
    )


def amendment_decision_exists(
    root: Path,
    manifest: Mapping[str, Any],
    candidate_digest: str,
    isolation: str,
) -> bool:
    for artifact in manifest["artifacts"]:
        relative = artifact["path"]
        if "/decisions/" not in relative:
            continue
        path = safe_relative_path(root, relative, must_exist=True)
        value = parse_commandments_decision(path.read_bytes())
        if value is not None and decision_matches(
            value,
            manifest,
            "amend",
            candidate_digest,
            value["operatorMarker"],
            isolation,
        ):
            return True
    return False


def matching_orphan_decision(
    root: Path,
    manifest: Mapping[str, Any],
    decision: str,
    candidate_sha: Optional[str],
    operator_marker: str,
    isolation: str,
) -> Optional[Tuple[Dict[str, Any], str, str]]:
    directory = root / ".pi" / "jig" / "commandments" / "decisions"
    if not directory.exists():
        return None
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("COMMANDMENTS decision directory is unsafe")
    registered = {item["path"] for item in manifest["artifacts"]}
    matches = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            continue
        relative = relative_to_root(root, path)
        if relative in registered or path.stat().st_size > 4096:
            continue
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        if path.name != f"{digest}.json":
            continue
        value = parse_commandments_decision(raw)
        if value is not None and decision_matches(
            value,
            manifest,
            decision,
            candidate_sha,
            operator_marker,
            isolation,
        ):
            matches.append((value, relative, digest))
    if len(matches) > 1:
        raise ValidationError(
            "multiple matching orphan COMMANDMENTS decisions require inspection"
        )
    return matches[0] if matches else None


def stage_commandments(
    root: Path,
    isolation: str,
    raw: bytes,
    amend_candidate_sha: Optional[str],
    adopt_existing: bool,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(
        root, isolation, ("awaiting-commandments",)
    )
    interview_artifact = next(
        (
            item
            for item in manifest["artifacts"]
            if item["path"] == COMMANDMENTS_INTERVIEW_PATH
        ),
        None,
    )
    if interview_artifact is None:
        raise ValidationError(
            "present the one COMMANDMENTS interview before staging answers"
        )
    answers = read_json_bytes(raw, "COMMANDMENTS answers")
    resolved, modes = validate_commandments_answers(answers)
    answers_raw = canonical_json(answers)
    answers_digest = sha256_bytes(answers_raw)
    answers_path = (
        f".pi/jig/commandments/answers/{answers_digest}.json"
    )
    current = load_staging(root, manifest)
    if (
        current is not None
        and current["answersSha256"] == answers_digest
        and current["adoptedExisting"] == adopt_existing
    ):
        if not staging_artifacts_registered(manifest, current):
            previous = current["previousCandidateSha256"]
            if previous is not None and (
                amend_candidate_sha != previous
                or not amendment_decision_exists(
                    root, manifest, previous, isolation
                )
            ):
                raise ValidationError(
                    "staging recovery requires the recorded amend decision"
                )
            if previous is None and amend_candidate_sha is not None:
                raise ValidationError("there is no staged candidate to amend")
            upsert_artifact(
                manifest, current["answersPath"], "human", current["answersSha256"]
            )
            upsert_artifact(
                manifest,
                current["candidatePath"],
                "controller",
                current["candidateSha256"],
            )
            manifest["updatedAt"] = max(manifest["updatedAt"], now())
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
    root_path = fixed_artifact_path(
        root, COMMANDMENTS_ROOT_PATH, create_parent=False
    )
    if adopt_existing:
        if not root_path.exists():
            raise ValidationError(
                "there is no existing root COMMANDMENTS.md to adopt"
            )
        candidate_raw = root_path.read_bytes()
        metadata = validate_commandments_bytes(candidate_raw)
        if metadata["marker"] != resolved["authority"]["ratificationMarker"]:
            raise ValidationError(
                "existing COMMANDMENTS marker differs from the explicit answer"
            )
    else:
        metadata = {"ratifiedAt": now(), "version": 1}
        candidate_raw = render_commandments_candidate(
            resolved, metadata["ratifiedAt"], metadata["version"]
        )
        metadata = validate_commandments_bytes(candidate_raw)
    candidate_digest = sha256_bytes(candidate_raw)
    candidate_path = (
        f".pi/jig/commandments/candidates/{candidate_digest}.md"
    )
    for relative, expected_raw in (
        (answers_path, answers_raw),
        (candidate_path, candidate_raw),
    ):
        path = root / relative
        parent = path.parent
        if parent.exists() or parent.is_symlink():
            if parent.is_symlink() or not parent.is_dir():
                raise ValidationError(
                    f"artifact directory is unsafe: {relative}"
                )
            if path.exists() or path.is_symlink():
                fixed_artifact_path(root, relative)
                if path.read_bytes() != expected_raw:
                    raise ValidationError(
                        f"content-addressed artifact collision: {relative}"
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
        "previousCandidateSha256": (
            current["candidateSha256"] if current is not None else None
        ),
        "adoptedExisting": adopt_existing,
    }
    staging_raw = canonical_json(staging)
    staging_path = fixed_artifact_path(root, COMMANDMENTS_STAGING_PATH)
    content_addressed_artifact(root, "answers", "json", answers_raw)
    content_addressed_artifact(root, "candidates", "md", candidate_raw)
    atomic_write(staging_path, staging_raw)
    upsert_artifact(manifest, answers_path, "human", answers_digest)
    upsert_artifact(manifest, candidate_path, "controller", candidate_digest)
    manifest["updatedAt"] = max(manifest["updatedAt"], now())
    write_manifest(root, manifest)
    return manifest, staging


def record_commandments_decision(
    root: Path,
    isolation: str,
    decision: str,
    candidate_sha: Optional[str],
    operator_marker: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(
        root, isolation, ("awaiting-commandments",)
    )
    marker = bounded_text(operator_marker, "operator marker", 200)
    current = load_staging(root, manifest)
    if current is not None and not staging_artifacts_registered(manifest, current):
        raise ValidationError(
            "resume staging before recording a COMMANDMENTS decision"
        )
    if decision == "amend":
        if current is None or candidate_sha != current["candidateSha256"]:
            raise ValidationError(
                "amend must name the current exact candidate digest"
            )
    elif decision == "defer":
        if candidate_sha is not None and (
            current is None or candidate_sha != current["candidateSha256"]
        ):
            raise ValidationError("defer names a stale or unknown candidate digest")
    else:
        raise ValidationError("decision must be amend or defer")
    orphan = matching_orphan_decision(
        root,
        manifest,
        decision,
        candidate_sha,
        marker,
        isolation,
    )
    if orphan is not None:
        receipt, path, digest = orphan
        upsert_artifact(manifest, path, "controller", digest)
        manifest["updatedAt"] = max(manifest["updatedAt"], receipt["at"])
        write_manifest(root, manifest)
        return manifest, {**receipt, "path": path, "sha256": digest}
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
    path, digest = content_addressed_artifact(
        root, "decisions", "json", raw
    )
    upsert_artifact(manifest, path, "controller", digest)
    manifest["updatedAt"] = max(manifest["updatedAt"], receipt["at"])
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
        raise ValidationError(
            "candidate digest must be a lowercase SHA-256 value"
        )
    if manifest["currentState"] == "commandments-ratified":
        if manifest["commandments"]["sha256"] != candidate_sha:
            raise ValidationError(
                "ratified COMMANDMENTS digest differs from the requested digest"
            )
        metadata = validate_commandments_bytes(
            (root / COMMANDMENTS_ROOT_PATH).read_bytes()
        )
        if metadata["marker"] != marker:
            raise ValidationError(
                "operator marker differs from the ratified exact bytes"
            )
        return manifest
    staging = load_staging(root, manifest)
    if staging is None or staging["candidateSha256"] != candidate_sha:
        raise ValidationError(
            "ratification must name the current exact candidate digest"
        )
    if not staging_artifacts_registered(manifest, staging):
        raise ValidationError("resume staging before ratification")
    candidate_path = safe_relative_path(
        root, staging["candidatePath"], must_exist=True
    )
    candidate_raw = candidate_path.read_bytes()
    if sha256_bytes(candidate_raw) != candidate_sha:
        raise ValidationError("staged COMMANDMENTS candidate hash changed")
    metadata = validate_commandments_bytes(candidate_raw)
    if metadata["marker"] != marker or staging["intendedMarker"] != marker:
        raise ValidationError(
            "ratification marker differs from the exact staged candidate"
        )
    interview_artifact = next(
        item
        for item in manifest["artifacts"]
        if item["path"] == COMMANDMENTS_INTERVIEW_PATH
    )
    approval_digest = sha256_bytes(
        canonical_json(
            {"candidateSha256": candidate_sha, "operatorMarker": marker}
        )
    )
    index = len(manifest["transitions"]) + 1
    receipt_relative = (
        f".pi/jig/receipts/transition-{index:04d}-commandments-ratified.json"
    )
    receipt_path = fixed_artifact_path(root, receipt_relative)
    root_path = fixed_artifact_path(
        root, COMMANDMENTS_ROOT_PATH, create_parent=False
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
    if receipt_path.exists():
        if not root_path.exists():
            raise ValidationError(
                "ratification receipt exists before root publication"
            )
        if root_path.read_bytes() != candidate_raw:
            raise ValidationError(
                "existing ratification receipt has different root bytes"
            )
        receipt = read_json(
            receipt_path, "COMMANDMENTS ratification receipt"
        )
        validate_transition_receipt(
            root,
            receipt,
            ("awaiting-commandments", "commandments-ratified"),
            manifest["source"],
        )
        if any(
            receipt.get(key) != value
            for key, value in expected_receipt.items()
        ):
            raise ValidationError(
                "existing ratification receipt differs from this approval"
            )
        receipt_raw = receipt_path.read_bytes()
    else:
        if root_path.exists() and root_path.read_bytes() != candidate_raw:
            raise ValidationError(
                "pre-existing COMMANDMENTS.md differs from the staged digest; "
                "preserve it and stage exact adoption"
            )
        if not root_path.exists():
            atomic_write(
                root_path, candidate_raw, ownership_token=candidate_sha
            )
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
    upsert_artifact(
        manifest, receipt_relative, "controller", receipt_digest
    )
    upsert_artifact(
        manifest, COMMANDMENTS_ROOT_PATH, "human", candidate_sha
    )
    manifest["commandments"] = {
        "path": COMMANDMENTS_ROOT_PATH,
        "sha256": candidate_sha,
        "version": metadata["version"],
        "ratifiedAt": metadata["ratifiedAt"],
    }
    manifest["currentState"] = "commandments-ratified"
    manifest["updatedAt"] = max(
        manifest["updatedAt"], receipt["recordedAt"]
    )
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


def protected_user_path(root: Path) -> Dict[str, str]:
    text = (root / COMMANDMENTS_ROOT_PATH).read_text(encoding="utf-8")
    labels = ("Action", "Visible result", "Evidence", "Cleanup", "Thresholds")
    result = {}
    for label in labels:
        matches = re.findall(rf"^\*\*{re.escape(label)}\.\*\* (.+)$", text, re.MULTILINE)
        if len(matches) != 1:
            raise ValidationError(f"COMMANDMENTS protected path has invalid {label}")
        key = {"Visible result": "visibleResult"}.get(label, label.lower())
        result[key] = bounded_text(matches[0], f"protected path {label}", 4000)
    return result


def validate_verification_plan(
    root: Path, manifest: Mapping[str, Any], value: Any
) -> Dict[str, Any]:
    fields = {
        "schemaVersion",
        "kind",
        "sourceRevision",
        "commandmentsSha256",
        "protectedUserPath",
        "protectedFeatureId",
        "skillPath",
        "featureIndexPath",
        "featureIds",
        "featurePaths",
        "helperPaths",
        "selfTestCommand",
        "timeoutSeconds",
        "cleanupOwner",
        "reservedPaths",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError("verification plan has an invalid shape")
    if (
        type(value["schemaVersion"]) is not int
        or value["schemaVersion"] != 1
        or value["kind"] != "verification-plan"
        or value["sourceRevision"] != manifest["source"]["revision"]
        or value["commandmentsSha256"] != manifest["commandments"]["sha256"]
        or value["skillPath"] != VERIFICATION_SKILL_PATH
        or value["featureIndexPath"] != VERIFICATION_FEATURE_INDEX_PATH
        or type(value["timeoutSeconds"]) is not int
        or not 2 <= value["timeoutSeconds"] <= 120
        or not isinstance(value["cleanupOwner"], str)
    ):
        raise ValidationError("verification plan metadata is inconsistent")
    bounded_text(value["cleanupOwner"], "verification cleanup owner", 500)
    if value["protectedUserPath"] != protected_user_path(root):
        raise ValidationError("verification plan changes the ratified protected path")
    protected_id = value["protectedFeatureId"]
    if not isinstance(protected_id, str) or VERIFICATION_ID.fullmatch(protected_id) is None:
        raise ValidationError("verification plan has an invalid protected feature ID")
    feature_ids = value["featureIds"]
    if (
        not isinstance(feature_ids, list)
        or not 3 <= len(feature_ids) <= 5
        or len(feature_ids) != len(set(feature_ids))
        or any(not isinstance(item, str) or VERIFICATION_ID.fullmatch(item) is None for item in feature_ids)
        or protected_id not in feature_ids
    ):
        raise ValidationError("verification plan must name three to five unique features")
    expected_features = [
        f".pi/skills/jig-verification/references/features/{item}.md"
        for item in feature_ids
    ]
    if value["featurePaths"] != expected_features:
        raise ValidationError("verification feature paths do not match their IDs")
    helpers = value["helperPaths"]
    if (
        not isinstance(helpers, list)
        or not 1 <= len(helpers) <= 5
        or len(helpers) != len(set(helpers))
        or any(
            not isinstance(item, str)
            or re.fullmatch(r"\.pi/skills/jig-verification/helpers/[a-z0-9][a-z0-9-]{0,63}\.py", item) is None
            for item in helpers
        )
    ):
        raise ValidationError("verification plan has invalid helper paths")
    command = value["selfTestCommand"]
    if (
        not isinstance(command, list)
        or command != ["python3", helpers[0], "self-test"]
        or any(len(item.encode("utf-8")) > 512 for item in command)
    ):
        raise ValidationError("verification self-test command is not the fixed argv protocol")
    reserved = [VERIFICATION_SKILL_PATH, VERIFICATION_FEATURE_INDEX_PATH, *expected_features, *helpers]
    if value["reservedPaths"] != reserved or len(reserved) != len(set(reserved)):
        raise ValidationError("verification reserved paths are inconsistent")
    return value


def load_verification_plan(root: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    path = safe_relative_path(root, VERIFICATION_PLAN_PATH, must_exist=True)
    if path.is_symlink() or not path.is_file():
        raise ValidationError("verification plan path is unsafe")
    return validate_verification_plan(root, manifest, read_json(path, "verification plan"))


def portable_verification_text(raw: bytes, label: str) -> str:
    if not raw or len(raw) > 128 * 1024:
        raise ValidationError(f"{label} is empty or too large")
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError as error:
        raise ValidationError(f"{label} is not UTF-8") from error
    banned = ("{{", "}}", ".cursor/", "/ho" + "me/", "TEMPLATE", "TODO")
    if any(item in text for item in banned):
        raise ValidationError(f"{label} contains a placeholder or nonportable path")
    return text


def validate_generated_verification(
    root: Path, manifest: Mapping[str, Any], plan: Mapping[str, Any]
) -> List[Tuple[str, str]]:
    reserved = set(plan["reservedPaths"])
    skill_root = root / ".pi/skills/jig-verification"
    if not skill_root.is_dir() or skill_root.is_symlink():
        raise ValidationError("verification skill directory is missing or unsafe")
    actual = {
        path.relative_to(root).as_posix()
        for path in skill_root.rglob("*")
        if not path.is_dir() or path.is_symlink()
    }
    if actual != reserved:
        raise ValidationError("verification skill files differ from the reserved plan")
    results = []
    for relative in plan["reservedPaths"]:
        path = safe_relative_path(root, relative, must_exist=True)
        if path.is_symlink() or not path.is_file():
            raise ValidationError(f"verification artifact is unsafe: {relative}")
        raw = path.read_bytes()
        text = portable_verification_text(raw, relative)
        if relative in plan["helperPaths"]:
            if not os.access(path, os.X_OK):
                raise ValidationError(f"verification helper is not executable: {relative}")
        elif relative == VERIFICATION_SKILL_PATH:
            if (
                not text.startswith("---\nname: jig-verification\n")
                or "\ndescription:" not in text.split("---", 2)[1]
                or any(f"\n## {heading}\n" not in text for heading in ("Launch", "Doctor", "Drive", "Evidence", "Cleanup", "Helpers"))
                or any(helper not in text for helper in plan["helperPaths"])
            ):
                raise ValidationError("verification SKILL.md is incomplete")
        elif relative == VERIFICATION_FEATURE_INDEX_PATH:
            if (
                f"Protected feature: `{plan['protectedFeatureId']}`" not in text
                or any(f"./{item}.md" not in text for item in plan["featureIds"])
                or text.count(".md)") != len(plan["featureIds"])
            ):
                raise ValidationError("verification feature index is incomplete")
        else:
            feature_id = Path(relative).stem
            headings = re.findall(r"^## (.+)$", text, re.MULTILINE)
            expected_headings = [
                "Sub-features",
                "How to get to it (user POV)",
                "Driving it with fixture-control",
                "Gotchas",
            ]
            metadata = ("Feature ID", "Owner", "Public entry point", "Allowed dependencies", "Evidence", "Last result")
            if (
                headings != expected_headings
                or f"Feature ID: `{feature_id}`" not in text
                or any(len(re.findall(rf"^{re.escape(label)}: .+$", text, re.MULTILINE)) != 1 for label in metadata)
            ):
                raise ValidationError(f"verification feature map is incomplete: {feature_id}")
            if feature_id == plan["protectedFeatureId"]:
                for value in plan["protectedUserPath"].values():
                    if value not in text:
                        raise ValidationError("protected feature differs from COMMANDMENTS")
        results.append((relative, sha256_bytes(raw)))
    return results


def parse_runtime_result(
    root: Path, manifest: Mapping[str, Any], plan: Mapping[str, Any], raw: bytes
) -> Tuple[Dict[str, Any], List[Tuple[str, str]]]:
    value = read_json_bytes(raw, "verification runtime result")
    fields = {"schemaVersion", "kind", "sourceRevision", "protectedFeatureId", "phases", "process", "evidence"}
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError("verification runtime result has an invalid shape")
    phases = value["phases"]
    process = value["process"]
    if (
        value["schemaVersion"] != 1
        or value["kind"] != "verification-self-test"
        or value["sourceRevision"] != manifest["source"]["revision"]
        or value["protectedFeatureId"] != plan["protectedFeatureId"]
        or not isinstance(phases, dict)
        or set(phases) != {"launch", "doctor", "drive", "evidence", "cleanup"}
        or any(item is not True for item in phases.values())
        or not isinstance(process, dict)
        or set(process) != {"pid", "processStart", "cleaned"}
        or type(process["pid"]) is not int
        or process["pid"] < 1
        or not isinstance(process["processStart"], str)
        or not process["processStart"]
        or process["cleaned"] is not True
        or process_start(process["pid"]) == process["processStart"]
    ):
        raise ValidationError("verification runtime phases or cleanup are unproved")
    evidence = value["evidence"]
    if not isinstance(evidence, list) or len(evidence) < 2:
        raise ValidationError("verification runtime evidence is incomplete")
    artifacts = []
    seen = set()
    documents = {}
    for item in evidence:
        if not isinstance(item, dict) or set(item) != {"path", "sha256"}:
            raise ValidationError("verification evidence record has an invalid shape")
        relative = item["path"]
        if (
            not isinstance(relative, str)
            or re.fullmatch(r"\.pi/jig/verification/evidence/[a-z0-9][a-z0-9._-]{0,127}\.json", relative) is None
            or relative in seen
            or re.fullmatch(r"[0-9a-f]{64}", item["sha256"]) is None
        ):
            raise ValidationError("verification evidence path or digest is invalid")
        path = safe_relative_path(root, relative, must_exist=True)
        if path.is_symlink() or not path.is_file() or path.stat().st_size > 128 * 1024 or sha256_file(path) != item["sha256"]:
            raise ValidationError("verification evidence bytes are inconsistent")
        documents[Path(relative).name] = read_json(path, "verification evidence")
        seen.add(relative)
        artifacts.append((relative, item["sha256"]))
    if set(documents) != {"protected-action.json", "protected-result.json"}:
        raise ValidationError("verification evidence must contain the protected action and result")
    action = documents["protected-action.json"]
    result = documents["protected-result.json"]
    protected = plan["protectedUserPath"]
    if (
        not isinstance(action, dict)
        or set(action) != {"kind", "action", "command"}
        or action["kind"] != "protected-action"
        or action["action"] != protected["action"]
        or not isinstance(action["command"], list)
        or not action["command"]
        or not isinstance(result, dict)
        or set(result) != {"kind", "visibleResult", "evidence", "thresholds", "observed", "persisted"}
        or result["kind"] != "protected-result"
        or result["visibleResult"] != protected["visibleResult"]
        or result["evidence"] != protected["evidence"]
        or result["thresholds"] != protected["thresholds"]
        or not result["observed"]
        or result["observed"] != result["persisted"]
    ):
        raise ValidationError("verification evidence does not prove the ratified protected path")
    evidence_directory = root / ".pi/jig/verification/evidence"
    actual_evidence = {
        path.relative_to(root).as_posix()
        for path in evidence_directory.iterdir()
    }
    if actual_evidence != seen:
        raise ValidationError("verification evidence directory contains unknown or missing files")
    return value, artifacts


def run_verification_command(
    root: Path, plan: Mapping[str, Any]
) -> Tuple[bytes, bytes, str]:
    ensure_owned_directory(root, ".pi/jig/verification")
    stdout_file = tempfile.TemporaryFile()
    stderr_file = tempfile.TemporaryFile()
    started = now()

    def child_limits() -> None:
        resource.setrlimit(
            resource.RLIMIT_FSIZE,
            (VERIFICATION_OUTPUT_LIMIT, VERIFICATION_OUTPUT_LIMIT),
        )

    def stop_group(pid: int) -> None:
        try:
            os.killpg(pid, signal.SIGTERM)
        except ProcessLookupError:
            return
        try:
            process.wait(timeout=2)
        except subprocess.TimeoutExpired:
            try:
                os.killpg(pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
            process.wait()

    process = subprocess.Popen(
        plan["selfTestCommand"],
        cwd=root,
        stdin=subprocess.DEVNULL,
        stdout=stdout_file,
        stderr=stderr_file,
        start_new_session=True,
        preexec_fn=child_limits,
    )
    try:
        process.wait(timeout=plan["timeoutSeconds"])
    except subprocess.TimeoutExpired as error:
        stop_group(process.pid)
        stdout_file.close()
        stderr_file.close()
        raise ValidationError(
            "verification self-test timed out and its process group was stopped"
        ) from error
    stdout_file.seek(0)
    stderr_file.seek(0)
    stdout = stdout_file.read(VERIFICATION_OUTPUT_LIMIT + 1)
    stderr = stderr_file.read(VERIFICATION_OUTPUT_LIMIT + 1)
    stdout_file.close()
    stderr_file.close()
    if len(stdout) > VERIFICATION_OUTPUT_LIMIT or len(stderr) > VERIFICATION_OUTPUT_LIMIT:
        stop_group(process.pid)
        raise ValidationError("verification self-test output is too large")
    if process.returncode != 0:
        stop_group(process.pid)
        detail = stderr.decode("utf-8", errors="replace")[:500]
        raise ValidationError(
            f"verification self-test failed with {process.returncode}: {detail}"
        )
    try:
        os.killpg(process.pid, 0)
    except ProcessLookupError:
        pass
    else:
        stop_group(process.pid)
        raise ValidationError("verification self-test left a process alive")
    return stdout, stderr, started


def begin_verification(
    root: Path, isolation: str, raw: bytes
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    manifest = require_commandments_boundary(root, isolation, ("commandments-ratified", "verification-building"))
    value = read_json_bytes(raw, "verification plan input")
    plan = validate_verification_plan(root, manifest, value)
    wanted = canonical_json(plan)
    skill_root = root / ".pi/skills/jig-verification"
    if (
        manifest["currentState"] != "verification-building"
        and (skill_root.exists() or skill_root.is_symlink())
    ):
        raise ValidationError(
            "pre-existing verification skill is preserved and blocks generation"
        )
    plan_path = fixed_artifact_path(root, VERIFICATION_PLAN_PATH)
    if manifest["currentState"] == "verification-building":
        if not plan_path.exists() or plan_path.read_bytes() != wanted:
            raise ValidationError("verification-building uses a different plan")
        return manifest, plan
    if plan_path.exists() and plan_path.read_bytes() != wanted:
        raise ValidationError("uncommitted verification plan differs from the supplied plan")
    if not plan_path.exists():
        atomic_write(plan_path, wanted)
    plan_digest = sha256_bytes(wanted)
    upsert_artifact(manifest, VERIFICATION_PLAN_PATH, "jig-skill", plan_digest)
    append_transition(
        root,
        manifest,
        "commandments-ratified",
        "verification-building",
        "verification-started",
        resourceIsolation=isolation,
        planPath=VERIFICATION_PLAN_PATH,
        planSha256=plan_digest,
        commandmentsSha256=manifest["commandments"]["sha256"],
        protectedFeatureId=plan["protectedFeatureId"],
    )
    write_manifest(root, manifest)
    return manifest, plan


def known_runtime_receipts(
    root: Path, manifest: Mapping[str, Any], plan: Mapping[str, Any]
) -> List[Tuple[str, str]]:
    directory = root / ".pi/jig/verification/receipts"
    if not directory.exists():
        return []
    if directory.is_symlink() or not directory.is_dir():
        raise ValidationError("verification receipt directory is unsafe")
    expected = {
        "schemaVersion",
        "kind",
        "command",
        "sourceRevision",
        "commandmentsSha256",
        "protectedFeatureId",
        "startedAt",
        "finishedAt",
        "exitCode",
        "stdoutSha256",
        "stderrSha256",
        "result",
    }
    receipts = []
    for path in sorted(directory.iterdir()):
        if path.is_symlink() or not path.is_file():
            raise ValidationError("verification receipt directory contains an unknown path")
        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        if path.name != f"runtime-{digest}.json":
            raise ValidationError("verification receipt name does not prove ownership")
        value = read_json_bytes(raw, "verification runtime receipt")
        if (
            not isinstance(value, dict)
            or set(value) != expected
            or value["schemaVersion"] != 1
            or value["kind"] != "verification-runtime-receipt"
            or value["command"] != plan["selfTestCommand"]
            or value["sourceRevision"] != manifest["source"]["revision"]
            or value["commandmentsSha256"] != manifest["commandments"]["sha256"]
            or value["protectedFeatureId"] != plan["protectedFeatureId"]
            or value["exitCode"] != 0
            or not valid_datetime(value["startedAt"])
            or not valid_datetime(value["finishedAt"])
            or re.fullmatch(r"[0-9a-f]{64}", value["stdoutSha256"]) is None
            or re.fullmatch(r"[0-9a-f]{64}", value["stderrSha256"]) is None
        ):
            raise ValidationError("verification runtime receipt is inconsistent")
        receipts.append((relative_to_root(root, path), digest))
    return receipts


def complete_verification(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] == "verification-ready":
        validate_verification_ready(root, manifest)
        return manifest
    if manifest["currentState"] != "verification-building":
        raise ValidationError("verification cannot complete from the current state")
    plan = load_verification_plan(root, manifest)
    generated = validate_generated_verification(root, manifest, plan)
    stdout, stderr, started = run_verification_command(root, plan)
    result, evidence = parse_runtime_result(root, manifest, plan, stdout)
    finished = now()
    runtime = {
        "schemaVersion": 1,
        "kind": "verification-runtime-receipt",
        "command": plan["selfTestCommand"],
        "sourceRevision": manifest["source"]["revision"],
        "commandmentsSha256": manifest["commandments"]["sha256"],
        "protectedFeatureId": plan["protectedFeatureId"],
        "startedAt": started,
        "finishedAt": finished,
        "exitCode": 0,
        "stdoutSha256": sha256_bytes(stdout),
        "stderrSha256": sha256_bytes(stderr),
        "result": result,
    }
    runtime_raw = canonical_json(runtime)
    runtime_digest = sha256_bytes(runtime_raw)
    runtime_relative = f".pi/jig/verification/receipts/runtime-{runtime_digest}.json"
    write_exact_artifact(root, runtime_relative, runtime_raw)
    for relative, digest in generated:
        upsert_artifact(manifest, relative, "jig-skill", digest)
    for relative, digest in evidence:
        upsert_artifact(manifest, relative, "repository", digest)
    for relative, digest in known_runtime_receipts(root, manifest, plan):
        upsert_artifact(manifest, relative, "controller", digest)
    manifest["verification"].append(
        {
            "kind": "runtime",
            "command": " ".join(plan["selfTestCommand"]),
            "exitCode": 0,
            "receiptPath": runtime_relative,
            "outputSha256": sha256_bytes(stdout),
            "revision": manifest["source"]["revision"],
            "finishedAt": finished,
        }
    )
    hashes = dict(generated)
    append_transition(
        root,
        manifest,
        "verification-building",
        "verification-ready",
        "verification-ready",
        resourceIsolation=isolation,
        planPath=VERIFICATION_PLAN_PATH,
        planSha256=sha256_file(root / VERIFICATION_PLAN_PATH),
        commandmentsSha256=manifest["commandments"]["sha256"],
        protectedFeatureId=plan["protectedFeatureId"],
        skillPath=VERIFICATION_SKILL_PATH,
        skillSha256=hashes[VERIFICATION_SKILL_PATH],
        featureIndexPath=VERIFICATION_FEATURE_INDEX_PATH,
        featureIndexSha256=hashes[VERIFICATION_FEATURE_INDEX_PATH],
        runtimeReceiptPath=runtime_relative,
        runtimeReceiptSha256=runtime_digest,
    )
    manifest["updatedAt"] = max(manifest["updatedAt"], finished)
    write_manifest(root, manifest)
    return manifest


def validate_verification_ready(root: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    plan = load_verification_plan(root, manifest)
    generated = dict(validate_generated_verification(root, manifest, plan))
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    for relative, digest in known_runtime_receipts(root, manifest, plan):
        if artifacts.get(relative) != {"path": relative, "owner": "controller", "sha256": digest}:
            raise ValidationError("runtime receipt ownership is inconsistent")
    for relative, digest in generated.items():
        if artifacts.get(relative) != {"path": relative, "owner": "jig-skill", "sha256": digest}:
            raise ValidationError("ready verification artifact registration is inconsistent")
    if len(manifest["verification"]) != 1:
        raise ValidationError("verification-ready requires one runtime verification")
    record = manifest["verification"][0]
    path = safe_relative_path(root, record["receiptPath"], must_exist=True)
    if (
        artifacts.get(record["receiptPath"]) != {
            "path": record["receiptPath"],
            "owner": "controller",
            "sha256": sha256_file(path),
        }
        or record["exitCode"] != 0
        or record["kind"] != "runtime"
    ):
        raise ValidationError("runtime verification receipt registration is inconsistent")
    runtime = read_json(path, "runtime verification receipt")
    if (
        runtime["command"] != plan["selfTestCommand"]
        or runtime["sourceRevision"] != record["revision"]
        or runtime["finishedAt"] != record["finishedAt"]
        or runtime["stdoutSha256"] != record["outputSha256"]
        or record["command"] != " ".join(plan["selfTestCommand"])
    ):
        raise ValidationError("runtime verification record differs from its receipt")
    result_raw = canonical_json(runtime["result"])
    _result, evidence = parse_runtime_result(root, manifest, plan, result_raw)
    for relative, digest in evidence:
        if artifacts.get(relative) != {"path": relative, "owner": "repository", "sha256": digest}:
            raise ValidationError("verification evidence registration is inconsistent")
    return plan


def validate_verification(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] != "verification-ready":
        raise ValidationError("verification is not ready")
    validate_verification_ready(root, manifest)
    return manifest


def begin_step_selection(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] == "step-selecting":
        validate_verification_ready(root, manifest)
        return manifest
    if manifest["currentState"] != "verification-ready":
        raise ValidationError("step selection requires verification-ready")
    validate_verification_ready(root, manifest)
    record = manifest["verification"][0]
    runtime_path = safe_relative_path(root, record["receiptPath"], must_exist=True)
    append_transition(
        root,
        manifest,
        "verification-ready",
        "step-selecting",
        "step-selection-started",
        resourceIsolation=isolation,
        commandmentsSha256=manifest["commandments"]["sha256"],
        runtimeReceiptPath=record["receiptPath"],
        runtimeReceiptSha256=sha256_file(runtime_path),
    )
    write_manifest(root, manifest)
    return manifest


def validate_committed_selection(
    root: Path, manifest: Mapping[str, Any], selection: Any, draft: Optional[Mapping[str, Any]] = None
) -> None:
    validate_instance(selection, load_schema("selection"))
    if not isinstance(selection, dict):
        raise ValidationError("selection is not an object")
    semantic = {key: selection[key] for key in SELECTION_DRAFT_FIELDS}
    if draft is not None and not json_equal(semantic, draft):
        raise ValidationError("existing selection differs from the submitted draft")
    if (
        selection["repositoryRevision"] != manifest["source"]["revision"]
        or selection["commandmentsSha256"] != manifest["commandments"]["sha256"]
    ):
        raise ValidationError("selection differs from the current source or COMMANDMENTS boundary")
    registered = any(item["path"] == SELECTION_PATH for item in manifest["artifacts"])
    if registered and manifest["firstStep"]["selectedCandidateId"] != selection["selectedCandidateId"]:
        raise ValidationError("manifest selected candidate differs from the committed selection")
    candidates = selection["candidates"]
    if len(candidates) > 20:
        raise ValidationError("selection has more than 20 candidates")
    ids = [candidate["id"] for candidate in candidates]
    if len(ids) != len(set(ids)):
        raise ValidationError("selection has duplicate candidate IDs")
    selected_id = selection["selectedCandidateId"]
    commandments = (root / COMMANDMENTS_ROOT_PATH).read_text(encoding="utf-8")
    known_ids = set(re.findall(r"^### (CMD-[0-9]{3})\. ", commandments, re.MULTILINE))
    for candidate in candidates:
        eligibility = candidate["eligibility"]
        if selected_id is None and (eligibility["eligible"] or not eligibility["rejectionReasons"]):
            raise ValidationError("no-selection candidates must be ineligible with rejection reasons")
        if candidate["responseLayer"] == "behavioral-eval" and candidate["behavioralEval"] != "required":
            raise ValidationError("behavioral-eval candidates must require behavioral evaluation")
        if not set(candidate["commandmentIds"]).issubset(known_ids):
            raise ValidationError("selection cites an unknown COMMANDMENT ID")
        for evidence in candidate["evidence"]:
            relative = evidence["path"]
            if relative == COMMANDMENTS_ROOT_PATH or relative.startswith(".pi/"):
                raise ValidationError("selection evidence is not a source file")
            path = safe_relative_path(root, relative, must_exist=True)
            flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
            try:
                descriptor = os.open(path, flags)
                with os.fdopen(descriptor, encoding="utf-8") as source:
                    if not stat.S_ISREG(os.fstat(source.fileno()).st_mode):
                        raise ValidationError("selection evidence is not a regular source file")
                    if not any(number == evidence["line"] for number, _line in enumerate(source, 1)):
                        raise ValidationError("selection evidence line does not exist")
            except (OSError, UnicodeError) as error:
                raise ValidationError("selection evidence is not a readable source file") from error
    if selected_id is not None:
        matches = [candidate for candidate in candidates if candidate["id"] == selected_id]
        if len(matches) != 1:
            raise ValidationError("selected candidate ID must match exactly one candidate")
        eligibility = matches[0]["eligibility"]
        if not eligibility["eligible"] or eligibility["rejectionReasons"]:
            raise ValidationError("selected candidate must be eligible with no rejection reasons")


def validate_command_set(command_set: Mapping[str, Any], label: str) -> None:
    commands = command_set["commands"]
    if len(commands) > 4:
        raise ValidationError(f"{label} has more than four commands")
    for command in commands:
        if not command.strip() or "\n" in command or "\r" in command or len(command) > 1000:
            raise ValidationError(f"{label} commands must be nonempty single lines of at most 1000 characters")


def validate_committed_proposal(
    root: Path, manifest: Mapping[str, Any], proposal: Any, draft: Optional[Mapping[str, Any]] = None
) -> None:
    validate_instance(proposal, load_schema("proposal"))
    if not isinstance(proposal, dict):
        raise ValidationError("proposal is not an object")
    if draft is not None and not json_equal(proposal, draft):
        raise ValidationError("existing proposal differs from the submitted draft")
    selection_artifact = next((item for item in manifest["artifacts"] if item["path"] == SELECTION_PATH), None)
    if selection_artifact is None or selection_artifact["owner"] != "controller":
        raise ValidationError("proposal requires a registered controller selection")
    selection_path = safe_relative_path(root, SELECTION_PATH, must_exist=True)
    selection_digest = sha256_file(selection_path)
    if selection_artifact["sha256"] != selection_digest:
        raise ValidationError("registered selection differs from the committed file")
    selection = read_json(selection_path, "selection")
    validate_committed_selection(root, manifest, selection)
    selected_id = selection["selectedCandidateId"]
    candidates = [item for item in selection["candidates"] if item["id"] == selected_id]
    if selected_id is None or len(candidates) != 1:
        raise ValidationError("proposal requires one selected candidate")
    candidate = candidates[0]
    expected = {
        "candidateId": selected_id,
        "repositoryRevision": manifest["source"]["revision"],
        "commandmentsSha256": manifest["commandments"]["sha256"],
        "selectionSha256": selection_digest,
        "commandmentIds": candidate["commandmentIds"],
        "evidence": candidate["evidence"],
        "responseLayer": candidate["responseLayer"],
        "blastRadius": candidate["riskCost"]["blastRadius"],
        "uncertainty": candidate["riskCost"]["uncertainty"],
        "potetoPlaybook": candidate["potetoPlaybook"],
    }
    if any(not json_equal(proposal[key], value) for key, value in expected.items()):
        raise ValidationError("proposal differs from its selected candidate boundary")
    if proposal["evalDecision"]["status"] != candidate["behavioralEval"]:
        raise ValidationError("proposal eval decision differs from its selected candidate")
    if candidate["behavioralEval"] == "required" and not proposal["proof"]["independentReview"]:
        raise ValidationError("behavioral evaluation requires independent review")
    command_sets = [("baseline", proposal["baseline"])]
    command_sets.extend((f"proof.{key}", value) for key, value in proposal["proof"].items() if isinstance(value, dict))
    command_sets.append(("rollback", {"commands": proposal["rollback"]["commands"]}))
    for label, command_set in command_sets:
        validate_command_set(command_set, label)
    first_step = manifest["firstStep"]
    registered = any(item["path"] == PROPOSAL_PATH for item in manifest["artifacts"])
    expected_proposal_path = PROPOSAL_PATH if registered else None
    if (
        manifest["currentState"] not in {"step-selecting", "step-running", "failed-step-running"}
        or first_step["selectionPath"] != SELECTION_PATH
        or first_step["selectedCandidateId"] != selected_id
        or first_step["proposalPath"] != expected_proposal_path
        or first_step["resultPath"] is not None
        or first_step["outcome"] != "pending"
    ):
        raise ValidationError("proposal links do not match the pending first step")


def validate_no_candidate_result(root: Path, manifest: Mapping[str, Any]) -> None:
    first_step = manifest["firstStep"]
    if first_step != {
        "selectionPath": SELECTION_PATH,
        "selectedCandidateId": None,
        "proposalPath": None,
        "resultPath": RESULT_PATH,
        "outcome": "no-eligible-candidate",
    }:
        raise ValidationError("initialized no-candidate manifest has an invalid first-step shape")
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    selection_path = safe_relative_path(root, SELECTION_PATH, must_exist=True)
    result_path = safe_relative_path(root, RESULT_PATH, must_exist=True)
    selection_digest = sha256_file(selection_path)
    result_digest = sha256_file(result_path)
    if artifacts.get(SELECTION_PATH) != {"path": SELECTION_PATH, "owner": "controller", "sha256": selection_digest}:
        raise ValidationError("initialized selection ownership is inconsistent")
    if artifacts.get(RESULT_PATH) != {"path": RESULT_PATH, "owner": "controller", "sha256": result_digest}:
        raise ValidationError("initialized result ownership is inconsistent")
    selection = read_json(selection_path, "selection")
    validate_committed_selection(root, manifest, selection)
    if selection["selectedCandidateId"] is not None:
        raise ValidationError("no-candidate result requires a null selection")
    result = read_json(result_path, "result")
    validate_instance(result, load_schema("result"))
    expected = {
        "schemaVersion": 1, "stepId": "0001", "outcome": "no-eligible-candidate",
        "selectionPath": SELECTION_PATH, "selectionSha256": selection_digest,
        "proposalPath": None, "proposalSha256": None, "inputRevision": None,
        "outputRevision": None, "branch": None, "worktree": None, "commands": [],
        "diffSha256": None, "independentVerdict": None,
    }
    if not isinstance(result, dict) or any(result.get(key) != value for key, value in expected.items()):
        raise ValidationError("no-candidate result differs from its selection boundary")
    step_dir = result_path.parent
    if {item.name for item in step_dir.iterdir()} != {"selection.json", "result.json"}:
        raise ValidationError("initialized step directory contains an unknown artifact")


def atomic_create(path: Path, data: bytes) -> None:
    temporary = path.parent / f".jigctl-{path.name}.{os.getpid()}.{uuid.uuid4().hex}.tmp"
    descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    try:
        offset = 0
        while offset < len(data):
            offset += os.write(descriptor, data[offset:])
        os.fsync(descriptor)
        os.link(temporary, path, follow_symlinks=False)
        fsync_directory(path.parent)
    except FileExistsError as error:
        raise JigError(f"owned artifact path already exists: {relative_to_root(path.parents[4], path)}") from error
    finally:
        os.close(descriptor)
        temporary.unlink(missing_ok=True)


def commit_step_selection(root: Path, isolation: str, raw: bytes) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] != "step-selecting":
        raise ValidationError("selection commitment requires step-selecting")
    validate_verification_ready(root, manifest)
    draft = read_json_bytes(raw, "selection draft")
    if not isinstance(draft, dict) or set(draft) != SELECTION_DRAFT_FIELDS:
        raise ValidationError("selection draft must contain every semantic selection field exactly")
    input_digest = sha256_bytes(canonical_json(draft))
    path = fixed_artifact_path(root, SELECTION_PATH)
    existing = path.exists() or path.is_symlink()
    if existing:
        if path.is_symlink() or not path.is_file():
            raise JigError("existing selection collision is not a regular file")
        selection = read_json(path, "selection")
        validate_committed_selection(root, manifest, selection, draft)
        if selection["controllerReceipt"]["inputSha256"] != input_digest:
            raise ValidationError("existing selection input digest differs from the submitted draft")
    else:
        selection = dict(draft)
        selection["controllerReceipt"] = {"recordedAt": now(), "inputSha256": input_digest}
        validate_committed_selection(root, manifest, selection, draft)
        atomic_create(path, canonical_json(selection))
    digest = sha256_file(path)
    registered = next((item for item in manifest["artifacts"] if item["path"] == SELECTION_PATH), None)
    expected = {"path": SELECTION_PATH, "owner": "controller", "sha256": digest}
    if registered is not None:
        if registered != expected:
            raise ValidationError("registered selection differs from the committed file")
        return manifest
    upsert_artifact(manifest, SELECTION_PATH, "controller", digest)
    manifest["firstStep"]["selectedCandidateId"] = selection["selectedCandidateId"]
    manifest["updatedAt"] = selection["controllerReceipt"]["recordedAt"]
    write_manifest(root, manifest)
    return manifest


def commit_step_proposal(root: Path, isolation: str, raw: bytes) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] != "step-selecting":
        raise ValidationError("proposal commitment requires step-selecting")
    validate_verification_ready(root, manifest)
    draft = read_json_bytes(raw, "proposal draft")
    validate_committed_proposal(root, manifest, draft, draft)
    path = fixed_artifact_path(root, PROPOSAL_PATH)
    names = {item.name for item in path.parent.iterdir()}
    if names - {"selection.json", "proposal.json"}:
        raise JigError("step directory contains an unknown artifact")
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_file():
            raise JigError("existing proposal collision is not a regular file")
        proposal = read_json(path, "proposal")
        if canonical_json(proposal) != path.read_bytes():
            raise ValidationError("existing proposal is not the exact recoverable proposal")
        validate_committed_proposal(root, manifest, proposal, draft)
    else:
        atomic_create(path, canonical_json(draft))
    digest = sha256_file(path)
    registered = next((item for item in manifest["artifacts"] if item["path"] == PROPOSAL_PATH), None)
    expected = {"path": PROPOSAL_PATH, "owner": "controller", "sha256": digest}
    if registered is not None:
        if registered != expected:
            raise ValidationError("registered proposal differs from the committed file")
        return manifest
    upsert_artifact(manifest, PROPOSAL_PATH, "controller", digest)
    manifest["firstStep"]["proposalPath"] = PROPOSAL_PATH
    manifest["updatedAt"] = now()
    write_manifest(root, manifest)
    return manifest


def worktree_entries(root: Path) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    for block in run_git(root, ["worktree", "list", "--porcelain"]).split("\n\n"):
        entry: Dict[str, str] = {}
        for line in block.splitlines():
            key, _, value = line.partition(" ")
            entry[key] = value
        if entry:
            entries.append(entry)
    return entries


def branch_revision(root: Path, branch: str) -> Optional[str]:
    result = subprocess.run(
        ["git", "-C", str(root), "show-ref", "--verify", "--quiet", f"refs/heads/{branch}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False,
    )
    if result.returncode == 1:
        return None
    if result.returncode != 0:
        raise JigError("Git could not inspect the reserved step branch")
    return run_git(root, ["rev-parse", f"refs/heads/{branch}"])


def ensure_step_worktree(root: Path, branch: str, revision: str) -> Path:
    parent = ensure_owned_directory(root, ".pi/jig/worktrees")
    path = parent / "0001"
    entries = worktree_entries(root)
    branch_ref = f"refs/heads/{branch}"
    branch_head = branch_revision(root, branch)
    matches = [item for item in entries if item.get("worktree") == str(path)]
    users = [item for item in entries if item.get("branch") == branch_ref]
    if path.exists() or path.is_symlink():
        if path.is_symlink() or not path.is_dir() or len(matches) != 1:
            raise JigError("reserved step worktree path has an unknown identity")
    elif matches:
        raise JigError("reserved step worktree has a stale Git administrative entry")
    if users and users != matches:
        raise JigError("reserved step branch is registered to a different worktree")
    if branch_head is not None and branch_head != revision:
        raise JigError("reserved step branch has the wrong revision")
    if not matches:
        arguments = ["worktree", "add", "--quiet"]
        if branch_head is None:
            arguments.extend(["-b", branch, str(path), revision])
        else:
            arguments.extend([str(path), branch])
        result = subprocess.run(
            ["git", "-C", str(root), *arguments], check=False,
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        if result.returncode != 0:
            raise JigError("Git could not create the reserved step worktree")
        matches = [item for item in worktree_entries(root) if item.get("worktree") == str(path)]
    if (len(matches) != 1 or matches[0].get("branch") != branch_ref
            or matches[0].get("HEAD") != revision or branch_revision(root, branch) != revision):
        raise JigError("reserved step worktree identity does not match the proposal")
    return path


def clean_step_worktree(path: Path, revision: str) -> None:
    if run_git(path, ["rev-parse", "HEAD"]) != revision:
        raise ValidationError("baseline changed the isolated worktree revision")
    if run_git(path, ["status", "--porcelain=v1", "--untracked-files=all"]):
        raise ValidationError("baseline changed the isolated worktree source")


def validate_baseline_receipt(value: Any, expected: Mapping[str, Any]) -> None:
    fields = set(expected) | {
        "exitCode", "timedOut", "finishedAt", "stdout", "stdoutSha256",
        "stdoutTruncated", "stderr", "stderrSha256", "stderrTruncated",
    }
    if not isinstance(value, dict) or set(value) != fields:
        raise ValidationError("baseline command receipt has an invalid shape")
    if any(value.get(key) != item for key, item in expected.items()):
        raise ValidationError("baseline command receipt differs from the proposal boundary")
    if (type(value["exitCode"]) is not int or type(value["timedOut"]) is not bool
            or not isinstance(value["finishedAt"], str) or not valid_datetime(value["finishedAt"])):
        raise ValidationError("baseline command receipt has invalid completion evidence")
    for stream in ("stdout", "stderr"):
        output = value[stream]
        if (not isinstance(output, str) or len(output.encode("utf-8")) > BASELINE_OUTPUT_LIMIT
                or value[f"{stream}Sha256"] != sha256_bytes(output.encode("utf-8"))
                or type(value[f"{stream}Truncated"]) is not bool):
            raise ValidationError("baseline command receipt has invalid bounded output")


def run_baseline_command(path: Path, command: str) -> Dict[str, Any]:
    environment = dict(os.environ)
    environment["PYTHONDONTWRITEBYTECODE"] = "1"
    with tempfile.TemporaryFile() as stdout_file, tempfile.TemporaryFile() as stderr_file:
        process = subprocess.Popen(
            ["sh", "-c", command], cwd=path, env=environment,
            stdout=stdout_file, stderr=stderr_file, start_new_session=True,
        )
        timed_out = False
        try:
            process.wait(timeout=BASELINE_TIMEOUT_SECONDS)
        except subprocess.TimeoutExpired:
            timed_out = True
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
        outputs = []
        truncated = []
        for stream in (stdout_file, stderr_file):
            stream.seek(0, os.SEEK_END)
            truncated.append(stream.tell() > BASELINE_OUTPUT_LIMIT)
            stream.seek(0)
            outputs.append(stream.read(BASELINE_OUTPUT_LIMIT).decode("utf-8", errors="replace"))
    code = 124 if timed_out else (process.returncode if process.returncode >= 0 else 128 - process.returncode)
    return {
        "exitCode": code, "timedOut": timed_out, "finishedAt": now(),
        "stdout": outputs[0], "stdoutSha256": sha256_bytes(outputs[0].encode()),
        "stdoutTruncated": truncated[0], "stderr": outputs[1],
        "stderrSha256": sha256_bytes(outputs[1].encode()), "stderrTruncated": truncated[1],
    }


def prepare_step_worktree(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] != "step-selecting" or manifest["firstStep"]["resultPath"] is not None:
        raise ValidationError("baseline preparation requires a pending step-selecting proposal")
    validate_verification_ready(root, manifest)
    proposal_path = safe_relative_path(root, PROPOSAL_PATH, must_exist=True)
    proposal = read_json(proposal_path, "proposal")
    validate_committed_proposal(root, manifest, proposal)
    proposal_digest = sha256_file(proposal_path)
    proposal_artifact = next((item for item in manifest["artifacts"] if item["path"] == PROPOSAL_PATH), None)
    if proposal_artifact != {"path": PROPOSAL_PATH, "owner": "controller", "sha256": proposal_digest}:
        raise ValidationError("registered proposal differs from the committed file")
    selection_digest = sha256_file(root / SELECTION_PATH)
    branch = f"jig/init-step-0001-{selection_digest[:12]}"
    revision = proposal["repositoryRevision"]
    worktree = ensure_step_worktree(root, branch, revision)
    clean_step_worktree(worktree, revision)
    commands = proposal["baseline"]["commands"]
    command_dir = ensure_owned_directory(root, ".pi/jig/steps/0001/commands")
    allowed = {f"baseline-{index:02d}.json" for index in range(1, len(commands) + 1)}
    if {item.name for item in command_dir.iterdir()} - allowed:
        raise JigError("baseline command directory contains an unknown artifact")
    summaries = []
    artifacts = []
    for index, command in enumerate(commands, 1):
        relative = f".pi/jig/steps/0001/commands/baseline-{index:02d}.json"
        receipt_path = root / relative
        expected = {
            "schemaVersion": 1, "kind": "step-command", "phase": "baseline",
            "index": index, "command": command, "worktree": STEP_WORKTREE,
            "branch": branch, "revision": revision,
        }
        if receipt_path.exists() or receipt_path.is_symlink():
            if receipt_path.is_symlink() or not receipt_path.is_file():
                raise JigError("baseline command receipt has an unknown identity")
            receipt = read_json(receipt_path, "baseline command receipt")
            validate_baseline_receipt(receipt, expected)
            if canonical_json(receipt) != receipt_path.read_bytes():
                raise ValidationError("baseline command receipt has unknown bytes")
        else:
            receipt = {**expected, **run_baseline_command(worktree, command)}
            validate_baseline_receipt(receipt, expected)
            atomic_create(receipt_path, canonical_json(receipt))
        clean_step_worktree(worktree, revision)
        if receipt["exitCode"] != 0 or receipt["timedOut"]:
            raise ValidationError("baseline command did not pass")
        digest = sha256_file(receipt_path)
        artifacts.append((relative, digest))
        summaries.append({
            "phase": "baseline", "index": index, "command": command,
            "receiptPath": relative, "receiptSha256": digest,
            "exitCode": receipt["exitCode"], "finishedAt": receipt["finishedAt"],
        })
    before_static = {
        "schemaVersion": 1, "kind": "step-before", "stepId": "0001",
        "proposalPath": PROPOSAL_PATH, "proposalSha256": proposal_digest,
        "inputRevision": revision, "branch": branch, "worktree": STEP_WORKTREE,
        "commands": summaries,
    }
    before_path = root / BEFORE_PATH
    if before_path.exists() or before_path.is_symlink():
        if before_path.is_symlink() or not before_path.is_file():
            raise JigError("before receipt has an unknown identity")
        before = read_json(before_path, "before receipt")
        if (not isinstance(before, dict) or set(before) != set(before_static) | {"recordedAt"}
                or any(before.get(key) != value for key, value in before_static.items())
                or not isinstance(before["recordedAt"], str) or not valid_datetime(before["recordedAt"])
                or canonical_json(before) != before_path.read_bytes()):
            raise ValidationError("before receipt is not the exact recoverable baseline pin")
    else:
        before = {**before_static, "recordedAt": now()}
        atomic_create(before_path, canonical_json(before))
    artifacts.append((BEFORE_PATH, sha256_file(before_path)))
    validate_current_source(root, manifest)
    registered = {item["path"]: item for item in manifest["artifacts"]}
    expected_artifacts = {path: {"path": path, "owner": "controller", "sha256": digest} for path, digest in artifacts}
    if all(registered.get(path) == value for path, value in expected_artifacts.items()):
        return manifest
    if any(path in registered and registered[path] != value for path, value in expected_artifacts.items()):
        raise ValidationError("registered baseline evidence differs from the exact receipts")
    for path, digest in artifacts:
        upsert_artifact(manifest, path, "controller", digest)
    manifest["updatedAt"] = before["recordedAt"]
    write_manifest(root, manifest)
    return manifest


def validate_step_worker(root: Path, manifest: Mapping[str, Any]) -> Dict[str, Any]:
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    required = (SELECTION_PATH, PROPOSAL_PATH, BEFORE_PATH, WORKER_PATH)
    paths = {name: safe_relative_path(root, name, must_exist=True) for name in required}
    if any(artifacts.get(name) != {"path": name, "owner": "controller", "sha256": sha256_file(paths[name])} for name in required):
        raise ValidationError("worker authorization artifacts do not match the manifest")
    proposal = read_json(paths[PROPOSAL_PATH], "proposal")
    validate_committed_proposal(root, manifest, proposal)
    before = read_json(paths[BEFORE_PATH], "before receipt")
    commands = proposal["baseline"]["commands"]
    if (not isinstance(before, dict) or set(before) != {
            "schemaVersion", "kind", "stepId", "proposalPath", "proposalSha256",
            "inputRevision", "branch", "worktree", "commands", "recordedAt"}
            or before["schemaVersion"] != 1 or before["kind"] != "step-before"
            or before["stepId"] != "0001" or before["proposalPath"] != PROPOSAL_PATH
            or before["proposalSha256"] != sha256_file(paths[PROPOSAL_PATH])
            or before["inputRevision"] != proposal["repositoryRevision"]
            or before["worktree"] != STEP_WORKTREE or len(before["commands"]) != len(commands)
            or not valid_datetime(before["recordedAt"]) or canonical_json(before) != paths[BEFORE_PATH].read_bytes()):
        raise ValidationError("worker authorization has an invalid before receipt")
    for index, command in enumerate(commands, 1):
        relative = f".pi/jig/steps/0001/commands/baseline-{index:02d}.json"
        receipt_path = safe_relative_path(root, relative, must_exist=True)
        expected = {"schemaVersion": 1, "kind": "step-command", "phase": "baseline",
            "index": index, "command": command, "worktree": STEP_WORKTREE,
            "branch": before["branch"], "revision": before["inputRevision"]}
        receipt = read_json(receipt_path, "baseline command receipt")
        validate_baseline_receipt(receipt, expected)
        summary = before["commands"][index - 1]
        if (canonical_json(receipt) != receipt_path.read_bytes() or receipt["exitCode"] != 0
                or receipt["timedOut"] or summary != {
                    "phase": "baseline", "index": index, "command": command,
                    "receiptPath": relative, "receiptSha256": sha256_file(receipt_path),
                    "exitCode": 0, "finishedAt": receipt["finishedAt"]}):
            raise ValidationError("worker authorization baseline did not pass exactly")
    worker_path = paths[WORKER_PATH]
    worker = read_json(worker_path, "worker receipt")
    expected = {
        "schemaVersion": 1, "kind": "step-worker", "stepId": "0001",
        "selectedCandidateId": proposal["candidateId"],
        "selectionSha256": sha256_file(paths[SELECTION_PATH]),
        "proposalSha256": sha256_file(paths[PROPOSAL_PATH]),
        "beforeSha256": sha256_file(paths[BEFORE_PATH]),
        "inputRevision": before["inputRevision"], "branch": before["branch"],
        "worktree": STEP_WORKTREE, "protectedPaths": WORKER_PROTECTED_PATHS,
    }
    if (not isinstance(worker, dict) or set(worker) != set(expected) | {
            "workerSessionId", "allowedPaths", "worktreeGitIdentity", "recordedAt"}
            or any(worker.get(key) != value for key, value in expected.items())
            or canonical_json(worker) != worker_path.read_bytes()):
        raise ValidationError("worker receipt differs from its activation boundary")
    session, allowed = worker["workerSessionId"], worker["allowedPaths"]
    protected = WORKER_PROTECTED_PATHS + verification_reserved_paths(root, manifest)
    if (not isinstance(session, str) or not session.strip() or len(session) > 200
            or any(ord(char) < 32 for char in session)
            or not isinstance(allowed, list) or not 1 <= len(allowed) <= 5
            or len(allowed) != len(set(allowed)) or any(not isinstance(item, str) for item in allowed)
            or not isinstance(worker["recordedAt"], str) or not valid_datetime(worker["recordedAt"])):
        raise ValidationError("worker receipt has an invalid session or scope")
    for relative in allowed:
        path = safe_relative_path(root / STEP_WORKTREE, relative)
        if (any(part in WORKER_PROTECTED_PATHS for part in PurePosixPath(relative).parts)
                or any(relative == item or relative.startswith(item + "/") for item in protected)
                or path.exists() and (path.is_symlink() or not path.is_file())):
            raise ValidationError("worker receipt contains a protected or invalid path")
    worktree = safe_relative_path(root, STEP_WORKTREE, must_exist=True)
    entries = [item for item in worktree_entries(root) if item.get("worktree") == str(worktree)]
    head = run_git(worktree, ["rev-parse", "HEAD"])
    if (len(entries) != 1 or entries[0].get("branch") != f"refs/heads/{before['branch']}"
            or entries[0].get("HEAD") != head or branch_revision(root, before["branch"]) != head
            or worker["worktreeGitIdentity"] != repository_identity(worktree)
            or subprocess.run(["git", "-C", str(worktree), "merge-base", "--is-ancestor",
                before["inputRevision"], head]).returncode != 0):
        raise ValidationError("worker worktree identity or ancestry changed")
    changed = set(filter(None, run_git(worktree, ["diff", "--name-only", "-z", before["inputRevision"], head]).split("\0")))
    status = run_git(worktree, ["status", "--porcelain=v1", "--untracked-files=all", "--", ".", ":(exclude).pi"])
    changed.update(line[3:].split(" -> ")[-1] for line in status.splitlines() if len(line) > 3)
    if changed - set(worker["allowedPaths"]):
        raise ValidationError("worker changed source outside its authorized paths")
    return worker


def activate_step_worker(root: Path, isolation: str, raw: bytes) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] == "step-running":
        worker = validate_step_worker(root, manifest)
        draft = read_json_bytes(raw, "worker draft")
        if {key: worker[key] for key in WORKER_DRAFT_FIELDS} != draft:
            raise ValidationError("worker activation retry differs from its authorization")
        return manifest
    if manifest["currentState"] != "step-selecting":
        raise ValidationError("worker activation requires step-selecting")
    manifest = prepare_step_worktree(root, isolation)
    draft = read_json_bytes(raw, "worker draft")
    if not isinstance(draft, dict) or set(draft) != WORKER_DRAFT_FIELDS:
        raise ValidationError("worker draft has an invalid shape")
    session = draft.get("workerSessionId")
    allowed = draft.get("allowedPaths")
    if (draft.get("schemaVersion") != 1 or draft.get("stepId") != "0001"
            or not isinstance(session, str) or not session.strip() or len(session) > 200
            or any(ord(char) < 32 for char in session)
            or not isinstance(allowed, list) or not 1 <= len(allowed) <= 5
            or len(allowed) != len(set(allowed)) or any(not isinstance(item, str) for item in allowed)):
        raise ValidationError("worker draft is not one bounded authorization")
    protected = WORKER_PROTECTED_PATHS + verification_reserved_paths(root, manifest)
    for relative in allowed:
        path = safe_relative_path(root / STEP_WORKTREE, relative)
        if (any(part in WORKER_PROTECTED_PATHS for part in PurePosixPath(relative).parts)
                or any(relative == item or relative.startswith(item + "/") for item in protected)):
            raise ValidationError("worker allowed path targets protected state")
        if path.exists() and (path.is_symlink() or not path.is_file()):
            raise ValidationError("worker allowed path is not a regular file target")
    artifacts = {item["path"]: item for item in manifest["artifacts"]}
    for name in (SELECTION_PATH, PROPOSAL_PATH, BEFORE_PATH):
        path = safe_relative_path(root, name, must_exist=True)
        if artifacts.get(name) != {"path": name, "owner": "controller", "sha256": sha256_file(path)}:
            raise ValidationError("worker activation requires exact registered step inputs")
    before = read_json(root / BEFORE_PATH, "before receipt")
    worktree = safe_relative_path(root, STEP_WORKTREE, must_exist=True)
    worker_static = {
        "schemaVersion": 1, "kind": "step-worker", "stepId": "0001",
        "workerSessionId": session, "selectedCandidateId": manifest["firstStep"]["selectedCandidateId"],
        "selectionSha256": sha256_file(root / SELECTION_PATH),
        "proposalSha256": sha256_file(root / PROPOSAL_PATH),
        "beforeSha256": sha256_file(root / BEFORE_PATH), "inputRevision": before["inputRevision"],
        "branch": before["branch"], "worktree": STEP_WORKTREE, "allowedPaths": allowed,
        "protectedPaths": WORKER_PROTECTED_PATHS, "worktreeGitIdentity": repository_identity(worktree),
    }
    worker_path = fixed_artifact_path(root, WORKER_PATH)
    if worker_path.exists() or worker_path.is_symlink():
        if worker_path.is_symlink() or not worker_path.is_file():
            raise JigError("worker receipt has an unknown identity")
        worker = read_json(worker_path, "worker receipt")
        if (not isinstance(worker, dict) or set(worker) != set(worker_static) | {"recordedAt"}
                or any(worker.get(key) != value for key, value in worker_static.items())
                or canonical_json(worker) != worker_path.read_bytes()):
            raise ValidationError("existing worker receipt differs from this authorization")
    else:
        worker = {**worker_static, "recordedAt": now()}
        atomic_create(worker_path, canonical_json(worker))
    worker_digest = sha256_file(worker_path)
    upsert_artifact(manifest, WORKER_PATH, "controller", worker_digest)
    extra = {
        "resourceIsolation": isolation, "commandmentsSha256": manifest["commandments"]["sha256"],
        "selectionSha256": worker["selectionSha256"], "proposalSha256": worker["proposalSha256"],
        "beforeSha256": worker["beforeSha256"], "workerSha256": worker_digest,
        "inputRevision": worker["inputRevision"], "branch": worker["branch"], "worktree": STEP_WORKTREE,
    }
    index = len(manifest["transitions"]) + 1
    receipt_path = root / f".pi/jig/receipts/transition-{index:04d}-step-running.json"
    if receipt_path.exists() or receipt_path.is_symlink():
        receipt = read_json(receipt_path, "worker activation transition")
        validate_transition_receipt(root, receipt, ("step-selecting", "step-running"), manifest["source"])
        if any(receipt.get(key) != value for key, value in extra.items()):
            raise ValidationError("worker activation transition differs from this authorization")
        digest = sha256_file(receipt_path)
        manifest["transitions"].append({"from": "step-selecting", "to": "step-running",
            "at": receipt["at"], "receiptPath": relative_to_root(root, receipt_path), "receiptSha256": digest})
        upsert_artifact(manifest, relative_to_root(root, receipt_path), "controller", digest)
        manifest["currentState"], manifest["updatedAt"] = "step-running", receipt["at"]
    else:
        append_transition(root, manifest, "step-selecting", "step-running", "step-worker-activated", **extra)
    validate_step_worker(root, manifest)
    write_manifest(root, manifest)
    return manifest


def finalize_no_candidate(root: Path, isolation: str) -> Dict[str, Any]:
    manifest = load_existing_manifest(root)
    if manifest["resourceIsolation"] != isolation:
        raise JigError("the existing manifest uses a different resourceIsolation route")
    validate_current_source(root, manifest)
    if manifest["currentState"] == "initialized":
        return manifest
    if manifest["currentState"] != "step-selecting":
        raise ValidationError("no-candidate finalization requires step-selecting")
    validate_verification_ready(root, manifest)
    selection_artifact = next((item for item in manifest["artifacts"] if item["path"] == SELECTION_PATH), None)
    if selection_artifact is None or selection_artifact["owner"] != "controller":
        raise ValidationError("no-candidate finalization requires a registered controller selection")
    selection_path = safe_relative_path(root, SELECTION_PATH, must_exist=True)
    selection = read_json(selection_path, "selection")
    validate_committed_selection(root, manifest, selection)
    if selection["selectedCandidateId"] is not None:
        raise ValidationError("no-candidate finalization requires a null selection")
    selection_digest = sha256_file(selection_path)
    if selection_artifact["sha256"] != selection_digest:
        raise ValidationError("registered selection differs from the committed file")
    result_path = fixed_artifact_path(root, RESULT_PATH)
    names = {item.name for item in result_path.parent.iterdir()}
    if names - {"selection.json", "result.json"}:
        raise JigError("step directory contains an unknown artifact")
    result_static = {
        "schemaVersion": 1, "stepId": "0001", "outcome": "no-eligible-candidate",
        "selectionPath": SELECTION_PATH, "selectionSha256": selection_digest,
        "proposalPath": None, "proposalSha256": None, "inputRevision": None,
        "outputRevision": None, "branch": None, "worktree": None, "commands": [],
        "diffSha256": None, "independentVerdict": None,
    }
    if result_path.exists() or result_path.is_symlink():
        if result_path.is_symlink() or not result_path.is_file():
            raise JigError("existing result collision is not a regular file")
        result = read_json(result_path, "result")
        validate_instance(result, load_schema("result"))
        if (not isinstance(result, dict) or canonical_json(result) != result_path.read_bytes()
                or any(result.get(key) != value for key, value in result_static.items())):
            raise ValidationError("existing result is not the exact recoverable no-candidate result")
    else:
        result = {**result_static, "recordedAt": now()}
        atomic_create(result_path, canonical_json(result))
    result_digest = sha256_file(result_path)
    upsert_artifact(manifest, RESULT_PATH, "controller", result_digest)
    extra = {
        "resourceIsolation": isolation,
        "commandmentsSha256": manifest["commandments"]["sha256"],
        "selectionPath": SELECTION_PATH, "selectionSha256": selection_digest,
        "resultPath": RESULT_PATH, "resultSha256": result_digest,
    }
    index = len(manifest["transitions"]) + 1
    receipt_relative = f".pi/jig/receipts/transition-{index:04d}-initialized.json"
    receipt_path = safe_relative_path(root, receipt_relative)
    if receipt_path.exists() or receipt_path.is_symlink():
        if receipt_path.is_symlink() or not receipt_path.is_file():
            raise JigError("initialized transition collision is not a regular file")
        receipt = read_json(receipt_path, "initialized transition receipt")
        validate_transition_receipt(root, receipt, ("step-selecting", "initialized"), manifest["source"])
        if any(receipt.get(key) != value for key, value in extra.items()):
            raise ValidationError("initialized transition differs from the recoverable result")
        receipt_digest = sha256_file(receipt_path)
        manifest["transitions"].append({
            "from": "step-selecting", "to": "initialized", "at": receipt["at"],
            "receiptPath": receipt_relative, "receiptSha256": receipt_digest,
        })
        upsert_artifact(manifest, receipt_relative, "controller", receipt_digest)
        manifest["currentState"] = "initialized"
        manifest["updatedAt"] = receipt["at"]
    else:
        append_transition(root, manifest, "step-selecting", "initialized", "no-candidate-finalized", **extra)
    manifest["firstStep"] = {
        "selectionPath": SELECTION_PATH, "selectedCandidateId": None,
        "proposalPath": None, "resultPath": RESULT_PATH, "outcome": "no-eligible-candidate",
    }
    write_manifest(root, manifest)
    return manifest


def render_result(root: Path, manifest: Mapping[str, Any]) -> None:
    result: Dict[str, Any] = {
        "root": ".",
        "state": manifest["currentState"],
        "resourceIsolation": manifest["resourceIsolation"],
    }
    if manifest["currentState"] == "awaiting-commandments":
        isolation = manifest["resourceIsolation"]
        operations = []
        interview = next(
            (
                item
                for item in manifest["artifacts"]
                if item["path"] == COMMANDMENTS_INTERVIEW_PATH
            ),
            None,
        )
        if interview is None:
            operations.append(
                {
                    "name": "present",
                    "command": [
                        "present-commandments",
                        "--resource-isolation",
                        isolation,
                    ],
                }
            )
        staging = load_staging(root, manifest)
        if staging is None or not staging_artifacts_registered(manifest, staging):
            stage_command = [
                "stage-commandments",
                "--resource-isolation",
                isolation,
            ]
            if (
                staging is not None
                and staging["previousCandidateSha256"] is not None
            ):
                stage_command.extend(
                    [
                        "--amend-candidate-sha",
                        staging["previousCandidateSha256"],
                    ]
                )
            if staging is not None and staging["adoptedExisting"]:
                stage_command.append("--adopt-existing")
            operations.append(
                {
                    "name": "stage",
                    "command": stage_command,
                    "stdin": ".pi/jig/commandments/answers.input.json",
                }
            )
        else:
            digest = staging["candidateSha256"]
            marker = staging["intendedMarker"]
            result["candidate"] = {
                "path": staging["candidatePath"],
                "sha256": digest,
                "intendedMarker": marker,
            }
            operations.extend(
                [
                    {
                        "name": "ratify",
                        "command": [
                            "ratify-commandments",
                            "--candidate-sha",
                            digest,
                            "--operator-marker",
                            marker,
                            "--resource-isolation",
                            isolation,
                        ],
                    },
                    {
                        "name": "amend",
                        "command": [
                            "record-commandments-decision",
                            "--decision",
                            "amend",
                            "--candidate-sha",
                            digest,
                            "--operator-marker",
                            "<operator-written marker>",
                            "--resource-isolation",
                            isolation,
                        ],
                        "followUp": {
                            "command": [
                                "stage-commandments",
                                "--amend-candidate-sha",
                                digest,
                                "--resource-isolation",
                                isolation,
                            ],
                            "stdin": ".pi/jig/commandments/answers.input.json",
                        },
                    },
                    {
                        "name": "defer",
                        "command": [
                            "record-commandments-decision",
                            "--decision",
                            "defer",
                            "--candidate-sha",
                            digest,
                            "--operator-marker",
                            "<operator-written marker>",
                            "--resource-isolation",
                            isolation,
                        ],
                    },
                ]
            )
        result["resume"] = {
            "controller": "jigctl.py",
            "operations": operations,
            "note": (
                "Run the named trusted-controller operation directly. "
                "This launcher version does not consume response files on rerun."
            ),
        }
    elif manifest["currentState"] == "commandments-ratified":
        result["resume"] = {
            "controller": "jigctl.py",
            "operations": [
                {
                    "name": "begin-verification",
                    "command": ["begin-verification", "--resource-isolation", manifest["resourceIsolation"]],
                    "stdin": ".pi/jig/verification/plan.input.json",
                }
            ],
        }
    elif manifest["currentState"] == "verification-building":
        plan = load_verification_plan(root, manifest)
        result["verification"] = {
            "planPath": VERIFICATION_PLAN_PATH,
            "reservedPaths": plan["reservedPaths"],
            "protectedFeatureId": plan["protectedFeatureId"],
        }
        result["resume"] = {
            "controller": "jigctl.py",
            "operations": [
                {
                    "name": "complete-verification",
                    "command": ["complete-verification", "--resource-isolation", manifest["resourceIsolation"]],
                }
            ],
        }
    elif manifest["currentState"] == "verification-ready":
        plan = load_verification_plan(root, manifest)
        result["verification"] = {
            "skillPath": VERIFICATION_SKILL_PATH,
            "featureIndexPath": VERIFICATION_FEATURE_INDEX_PATH,
            "protectedFeatureId": plan["protectedFeatureId"],
        }
    elif manifest["currentState"] in {"step-running", "failed-step-running"}:
        worker = validate_step_worker(root, manifest)
        proposal = read_json(root / PROPOSAL_PATH, "proposal")
        result["workerHandoff"] = {
            "worktree": worker["worktree"], "workerSessionId": worker["workerSessionId"],
            "selectedCandidateId": worker["selectedCandidateId"], "proposalPath": PROPOSAL_PATH,
            "potetoPlaybook": proposal["potetoPlaybook"],
            "allowedPaths": worker["allowedPaths"], "protectedPaths": worker["protectedPaths"],
        }
    elif manifest["currentState"] == "step-selecting":
        selection = next(
            (item for item in manifest["artifacts"] if item["path"] == SELECTION_PATH), None
        )
        if selection is not None:
            result["selection"] = {"path": SELECTION_PATH, "sha256": selection["sha256"]}
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
        "begin-verification",
        "complete-verification",
        "validate-verification",
        "begin-step-selection",
        "commit-step-selection",
        "commit-step-proposal",
        "prepare-step-worktree",
        "finalize-no-candidate",
        "activate-step-worker",
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
        choices=(
            "surveying",
            "awaiting-commandments",
            "commandments-ratified",
            "verification-building",
            "verification-ready",
            "step-selecting",
            "step-running",
        ),
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
        elif arguments.command == "begin-verification":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest, output = begin_verification(
                root, arguments.resource_isolation, raw
            )
            output = {"state": manifest["currentState"], **output}
        elif arguments.command == "complete-verification":
            manifest = complete_verification(root, arguments.resource_isolation)
        elif arguments.command == "validate-verification":
            manifest = validate_verification(root, arguments.resource_isolation)
        elif arguments.command == "begin-step-selection":
            manifest = begin_step_selection(root, arguments.resource_isolation)
        elif arguments.command == "commit-step-selection":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest = commit_step_selection(root, arguments.resource_isolation, raw)
        elif arguments.command == "commit-step-proposal":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest = commit_step_proposal(root, arguments.resource_isolation, raw)
        elif arguments.command == "prepare-step-worktree":
            manifest = prepare_step_worktree(root, arguments.resource_isolation)
        elif arguments.command == "activate-step-worker":
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest = activate_step_worker(root, arguments.resource_isolation, raw)
        elif arguments.command == "finalize-no-candidate":
            manifest = finalize_no_candidate(root, arguments.resource_isolation)
        else:
            raw = sys.stdin.buffer.read(MAX_INPUT_BYTES + 1)
            manifest, output = propose_commandments_amendment(
                root, arguments.resource_isolation, raw
            )
    if output is None:
        render_result(root, manifest)
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

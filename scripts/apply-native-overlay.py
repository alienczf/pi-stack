#!/usr/bin/env python3
"""Apply the pinned pi-web source overlay without loading a daemon or user data."""
from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import stat
import tempfile

MANIFEST = Path(__file__).resolve().parents[1] / "native/pi-web/manifest.json"
JOURNAL = ".pi-stack-overlay.pending"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def journal_bytes(manifest: dict) -> bytes:
    return (json.dumps({"id": manifest["id"], "manifestSha256": digest(json.dumps(manifest, sort_keys=True, separators=(",", ":")).encode())}, sort_keys=True) + "\n").encode()


def owned_path(root: Path, name: str) -> Path:
    relative = Path(name)
    if relative.is_absolute() or not relative.parts or any(part in {"..", "."} for part in relative.parts):
        raise ValueError(f"unsafe overlay path {name}")
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise ValueError(f"symlink in overlay target {name}")
    return current


def read_regular(path: Path) -> bytes:
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        if not stat.S_ISREG(os.fstat(fd).st_mode):
            raise ValueError(f"not a regular overlay file {path}")
        with os.fdopen(fd, "rb", closefd=False) as source:
            return source.read()
    finally:
        os.close(fd)


def publish(path: Path, data: bytes, mode: int = 0o644) -> None:
    fd, temporary = tempfile.mkstemp(prefix=".pi-stack-overlay-", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as target:
            target.write(data)
            target.flush()
            os.fchmod(target.fileno(), mode)
            os.fsync(target.fileno())
        os.replace(temporary, path)
        directory = os.open(path.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def apply(root: Path, manifest: dict, *, check: bool = False) -> str:
    root = root.absolute()
    if root.is_symlink() or root.resolve() != root or not root.is_dir():
        raise ValueError("overlay root must be a canonical nonsymlink package directory")
    fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX)
        return apply_locked(root, manifest, check=check)
    finally:
        os.close(fd)


def apply_locked(root: Path, manifest: dict, *, check: bool) -> str:
    for name, expected in manifest["packages"].items():
        raw = read_regular(owned_path(root, name))
        package = json.loads(raw)
        if any(package.get(key) != expected[key] for key in ("name", "version")) or expected.get("sha256", digest(raw)) != digest(raw):
            raise ValueError(f"unsupported package version or bytes {name}")
    journal = owned_path(root, JOURNAL)
    expected_journal = journal_bytes(manifest)
    if journal.exists() and read_regular(journal) != expected_journal:
        raise ValueError("overlay journal belongs to a different manifest")
    states, updates = [], []
    actuals = {}
    seen = set()
    for item in manifest["files"]:
        path = owned_path(root, item["path"])
        if path in seen or not path.parent.is_dir():
            raise ValueError("ambiguous overlay file or missing parent directory")
        seen.add(path)
        raw = read_regular(path) if path.exists() else None
        actual = None if raw is None else digest(raw)
        actuals[item["path"]] = actual
        if actual == item["after"]:
            states.append("after")
            continue
        if actual not in [item["before"], *(tree.get(item["path"]) for tree in manifest.get("inputs", []))]:
            raise ValueError(f"unexpected source hash {item['path']}")
        states.append("before")
        if "contentFile" in item:
            patched = read_regular(owned_path(MANIFEST.parents[1], item["contentFile"]))
        elif "content" in item:
            patched = item["content"].encode()
        else:
            patched = raw.decode("utf-8")
            for edit in item["edits"]:
                if patched.count(edit["old"]) != 1:
                    raise ValueError(f"nonunique patch preimage {item['path']}")
                patched = patched.replace(edit["old"], edit["new"], 1)
            patched = patched.encode()
        if digest(patched) != item["after"]:
            raise ValueError(f"overlay postimage hash mismatch {item['path']}")
        updates.append((path, patched, stat.S_IMODE(path.stat().st_mode) if path.exists() else 0o644))
    pristine = {item["path"]: item["before"] for item in manifest["files"]}
    postimage = {item["path"]: item["after"] for item in manifest["files"]}
    if not journal.exists() and actuals not in [pristine, postimage, *manifest.get("inputs", [])]:
        raise ValueError("unowned mixed original/patched tree")
    if check:
        return "already-applied" if not updates else "ready"
    if updates:
        if not journal.exists():
            publish(journal, expected_journal, 0o600)
        for path, patched, mode in updates:
            publish(path, patched, mode)
    if journal.exists():
        journal.unlink()
        directory = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    return "applied" if updates else "already-applied"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path, help="canonical disposable or authorized pi-web package root")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--extension", choices=("pi-subagents", "pi-web-access", "pi-prompt-template-model", "pi-cursor-sdk", "pi-jupyter"))
    args = parser.parse_args()
    manifest = MANIFEST if args.extension is None else MANIFEST.parents[1] / "extensions" / (args.extension + ".json")
    try:
        result = apply(args.root, json.loads(manifest.read_text()), check=args.check)
    except (OSError, ValueError, KeyError) as exc:
        parser.exit(1, f"Native overlay refused. {exc}\n")
    print(f"pi-stack native overlay {result}. No daemon was started or restarted.")


if __name__ == "__main__":
    main()

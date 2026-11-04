#!/usr/bin/env python3
"""Copy only static npm package material into a fresh owned native test fixture."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import shutil
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXTENSIONS = ("pi-subagents", "pi-web-access", "pi-prompt-template-model", "pi-cursor-sdk", "pi-jupyter")


def ignore_runtime(directory, names):
    return [name for name in names if name in {"auth.json", ".git", ".cache", ".pi"} or name.endswith(".jsonl")]


def dependency(source: Path, name: str) -> Path | None:
    for parent in (source, *source.parents):
        candidate = parent / "node_modules" / name
        if (candidate / "package.json").is_file():
            return candidate.resolve()
    return None


def copy_dependencies(source: Path, destination: Path, seen: set[Path] | None = None) -> None:
    seen = set() if seen is None else set(seen)
    seen.add(source.resolve())
    package = json.loads((source / "package.json").read_text())
    optional = package.get("optionalDependencies", {})
    for name in package.get("dependencies", {}) | optional:
        if name.startswith(("@earendil-works/", "@mariozechner/")):
            continue
        resolved = dependency(source, name)
        if resolved is None:
            if name in optional:
                continue
            raise ValueError(f"static dependency {name} is unavailable at {source}")
        target = destination / "node_modules" / name
        if resolved in seen:
            continue
        if not target.exists():
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copytree(resolved, target, symlinks=True, ignore=ignore_runtime)
        elif (target / "package.json").read_bytes() != (resolved / "package.json").read_bytes():
            raise ValueError(f"mixed static dependency version at {target}")
        copy_dependencies(resolved, target, seen)


def prepare(source: Path, extensions: Path, destination: Path) -> None:
    owned = (ROOT / ".harness-heal").resolve()
    if not destination.resolve().is_relative_to(owned) or destination.exists():
        raise ValueError("native fixture needs a fresh destination under this worktree's .harness-heal directory")
    destination.mkdir(parents=True)
    native = destination / "native"
    native.mkdir()
    for name in ("package.json", "dist", "node_modules"):
        if (source / name).is_dir():
            shutil.copytree(source / name, native / name, symlinks=True, ignore=ignore_runtime)
        else:
            shutil.copyfile(source / name, native / name)
    ext_root = destination / "extensions"
    for name in EXTENSIONS:
        package = extensions / name
        target = ext_root / name
        for path in package.rglob("*"):
            relative = path.relative_to(package)
            if "node_modules" in relative.parts or relative.parts[0] in {"docs", "skills", "examples", "agents", "prompts"}:
                continue
            if path.is_file() and not path.is_symlink() and (path.suffix in {".ts", ".mjs"} or relative == Path("package.json")):
                (target / relative).parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(path, target / relative)
        copy_dependencies(package, target)
    (ext_root / "node_modules").symlink_to("../native/node_modules")
    targets = [(native, []), *[(ext_root / name, ["--extension", name]) for name in EXTENSIONS]]
    for target, flags in targets:
        subprocess.run(["python3", str(ROOT / "scripts/apply-native-overlay.py"), str(target), *flags, "--check"], check=True)
    for target, flags in targets:
        subprocess.run(["python3", str(ROOT / "scripts/apply-native-overlay.py"), str(target), *flags], check=True)
    print(native)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("extensions", type=Path)
    parser.add_argument("destination", type=Path)
    args = parser.parse_args()
    prepare(args.source.resolve(), args.extensions.resolve(), args.destination.absolute())

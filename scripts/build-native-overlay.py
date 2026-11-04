#!/usr/bin/env python3
"""Regenerate a source-only overlay from explicit pristine and edited package roots."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path
import subprocess

EXTENSIONS = {"pi-subagents": "0.58.0", "pi-web-access": "0.26.0", "pi-prompt-template-model": "0.12.2", "pi-cursor-sdk": "0.1.5", "pi-jupyter": "0.1.0"}
PACKAGES = {"package.json": ("@jmfederico/pi-web", "1.202607.3"), **{f"node_modules/@earendil-works/{name}/package.json": (f"@earendil-works/{name}", "0.82.1") for name in ("pi-coding-agent", "pi-ai", "pi-agent-core")}, "node_modules/@earendil-works/pi-coding-agent/node_modules/@earendil-works/pi-ai/package.json": ("@earendil-works/pi-ai", "0.82.1")}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(pristine, edited, paths, *, postimages=None):
    result = {"id": "harness-heal-v1", "packages": {}, "files": []}
    for path, (name, version) in PACKAGES.items():
        raw = (pristine / path).read_bytes()
        value = json.loads(raw)
        if (value["name"], value["version"]) != (name, version) or (edited / path).read_bytes() != raw:
            raise ValueError(f"unsupported package {path}")
        result["packages"][path] = {"name": name, "version": version, "sha256": digest(raw)}
    for path in sorted(set(paths)):
        old = (pristine / path).read_bytes() if (pristine / path).exists() else None
        new = (edited / path).read_bytes()
        if old == new:
            continue
        item = {"path": path, "before": None if old is None else digest(old), "after": digest(new)}
        if postimages is not None:
            destination = postimages / path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(new)
            item["contentFile"] = str(destination.relative_to(Path(__file__).resolve().parents[1] / "native"))
        elif old is None:
            item["content"] = new.decode()
        else:
            before, after = old.decode().splitlines(keepends=True), new.decode().splitlines(keepends=True)
            edits = []
            for group in difflib.SequenceMatcher(a=before, b=after, autojunk=False).get_grouped_opcodes(3):
                original = "".join(before[group[0][1]:group[-1][2]])
                replacement = "".join(after[group[0][3]:group[-1][4]])
                if old.decode().count(original) != 1:
                    raise ValueError(f"nonunique patch group {path}")
                edits.append({"old": original, "new": replacement})
            item["edits"] = edits
        result["files"].append(item)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pristine", type=Path)
    parser.add_argument("edited", type=Path)
    parser.add_argument("paths", nargs="+")
    parser.add_argument("--extension", choices=EXTENSIONS)
    parser.add_argument("--postimages", type=Path, help="write auditable full postimage sources below native/")
    parser.add_argument("--accept-revision", action="append", default=[], help="accept a complete known overlay tree from this git revision")
    args = parser.parse_args()
    if args.extension:
        PACKAGES = {"package.json": (args.extension, EXTENSIONS[args.extension])}
    result = build(args.pristine, args.edited, args.paths, postimages=args.postimages)
    if args.postimages:
        result["id"] = "continuous-recovery-v2"
    if args.accept_revision:
        result["inputs"] = []
        for revision in args.accept_revision:
            previous = json.loads(subprocess.check_output(["git", "show", f"{revision}:native/pi-web/manifest.json"], text=True))
            known = {item["path"]: item["after"] for item in previous["files"]}
            tree = {item["path"]: known.get(item["path"], item["before"]) for item in result["files"]}
            if tree not in result["inputs"]:
                result["inputs"].append(tree)
    print(json.dumps(result, indent=2, ensure_ascii=False))

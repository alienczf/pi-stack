#!/usr/bin/env python3
"""Regenerate a source-only overlay from explicit pristine and edited package roots."""
from __future__ import annotations

import argparse
import difflib
import hashlib
import json
from pathlib import Path

PACKAGES = {"package.json": ("@jmfederico/pi-web", "1.202607.3"), **{f"node_modules/@earendil-works/{name}/package.json": (f"@earendil-works/{name}", "0.82.1") for name in ("pi-coding-agent", "pi-ai", "pi-agent-core")}}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def build(pristine, edited, paths):
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
        if old is None:
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
    args = parser.parse_args()
    print(json.dumps(build(args.pristine, args.edited, args.paths), indent=2, ensure_ascii=False))

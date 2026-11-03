#!/usr/bin/env python3
"""List charter authority uses and reject the removed runtime human protocol."""
from pathlib import Path
import re
import sys

ROOT = Path(__file__).resolve().parents[1]
PATHS = ("pi-streams/engine", "pi-streams/templates", "skills/stream", "skills/stream-kickoff", "prompts/stream.md", "overlay/AGENTS.md", "native")
FORBIDDEN = re.compile(r"failure.?ratif|ratif.{0,20}failure|ratified-prefix|verified-notice|verified-zf-dm|verifyFailureNotice|ZF-only|human repairs", re.IGNORECASE)
failed = False
for name in PATHS:
    selected = ROOT / name
    for path in sorted(selected.rglob("*") if selected.is_dir() else [selected]):
        if not path.is_file() or path.suffix not in {".py", ".js", ".ts", ".md", ".json"} or "__pycache__" in path.parts:
            continue
        for number, line in enumerate(path.read_text().splitlines(), 1):
            if FORBIDDEN.search(line):
                print(f"FORBIDDEN {path.relative_to(ROOT)}:{number}:{line}")
                failed = True
            elif re.search("ratif", line, re.IGNORECASE):
                print(f"CHARTER {path.relative_to(ROOT)}:{number}:{line}")
raise SystemExit(1 if failed else 0)

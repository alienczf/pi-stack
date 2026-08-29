#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
START = "<!-- readme-checks:start -->"
END = "<!-- readme-checks:end -->"


def commands() -> list[str]:
    text = README.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit("README must contain one check command marker pair")
    block = text.split(START, 1)[1].split(END, 1)[0]
    match = re.fullmatch(r"\s*```bash\n(.+?)\n```\s*", block, re.DOTALL)
    if match is None:
        raise SystemExit("README check command block is malformed")
    result = [line.strip() for line in match.group(1).splitlines() if line.strip()]
    if any(line.startswith("#") or "<" in line or ">" in line for line in result):
        raise SystemExit("README check commands must be directly executable")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    extracted = commands()
    for command in extracted:
        if arguments.execute:
            completed = subprocess.run(command, cwd=ROOT, shell=True)
            if completed.returncode != 0:
                raise SystemExit(completed.returncode)
            print(f"README command passed: {command}")
        else:
            print(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

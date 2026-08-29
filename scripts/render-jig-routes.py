#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MATRIX = ROOT / "skills/jig/references/public-routes.json"
TARGETS = (ROOT / "README.md", ROOT / "skills/jig/references/init-contract.md")
START = "<!-- public-routes:start -->"
END = "<!-- public-routes:end -->"


def table() -> str:
    document = json.loads(MATRIX.read_text(encoding="utf-8"))
    routes = document["routes"]
    lines = [
        "| Command | Resource loading | Receipt | Controller | Pause and resume | Terminal state |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for route in routes:
        cells = [
            f"`{route['userCommand']}`",
            route["trustResourceLoading"],
            f"`{route['resourceIsolation']}`",
            f"`{route['controllerLocation']}`",
            route["pauseResumeBehavior"] + " " + route["routeMismatchRecovery"],
            f"`{route['terminalState']}`",
        ]
        lines.append("| " + " | ".join(cell.replace("|", "\\|") for cell in cells) + " |")
    return "\n".join(lines)


def render(path: Path, replacement: str) -> bool:
    text = path.read_text(encoding="utf-8")
    if text.count(START) != 1 or text.count(END) != 1:
        raise SystemExit(f"{path.relative_to(ROOT)} must contain one public route marker pair")
    before, remainder = text.split(START, 1)
    _, after = remainder.split(END, 1)
    wanted = before + START + "\n" + replacement + "\n" + END + after
    if text == wanted:
        return False
    path.write_text(wanted, encoding="utf-8")
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    replacement = table()
    changed = []
    for target in TARGETS:
        if arguments.check:
            original = target.read_text(encoding="utf-8")
            start = original.index(START) + len(START)
            end = original.index(END)
            if original[start:end].strip() != replacement:
                changed.append(target.relative_to(ROOT).as_posix())
        elif render(target, replacement):
            changed.append(target.relative_to(ROOT).as_posix())
    if arguments.check and changed:
        raise SystemExit("stale public route table: " + ", ".join(changed))
    print("public route matrix ok" if arguments.check else "public route tables rendered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

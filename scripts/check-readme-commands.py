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


def check_merged_commands() -> None:
    text = README.read_text(encoding="utf-8")
    section = text.split("## Isolated stock Prime merged PoC\n", 1)[1].split("## Verify the repository", 1)[0]
    blocks = re.findall(r"```bash\n(.*?)\n```", section, re.DOTALL)
    if len(blocks) != 4:
        raise SystemExit("merged PoC must document selection, prerequisites, install/init/doctor and verify")
    required = (
        "git clone --branch feat/merged-poc --single-branch https://github.com/alienczf/pi-stack.git pi-stack-merged-poc",
        '--coordinator-model "$POC_MODEL" --coordinator-thinking "$POC_THINKING"',
        '--compaction-percent "$POC_PERCENT"',
        '"$POC_ROOT/bin/pi-streams" poc init --root "$POC_ROOT" --stream weekend-poc',
        '"$POC_ROOT/bin/pi-streams" poc doctor --root "$POC_ROOT" --stream weekend-poc',
        '"$POC_ROOT/bin/pi-streams" poc verify --root "$POC_ROOT" --stream weekend-poc',
        'export CARGO_HOME="$POC_ROOT/build/cargo"',
        'export RUSTUP_HOME="$POC_ROOT/build/rustup"',
    )
    if any(command not in section for command in required):
        raise SystemExit("merged PoC commands do not match the explicit isolated contract")
    for block in blocks:
        subprocess.run(["bash", "-n"], input=block, text=True, check=True)
    for verb in ("init", "doctor", "verify"):
        subprocess.run([str(ROOT / "bin/pi-streams"), "poc", verb, "--help"], stdout=subprocess.DEVNULL, check=True)
    subprocess.run([str(ROOT / "install.sh"), "--merged-poc", "--help"], stdout=subprocess.DEVNULL, check=True)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--execute", action="store_true")
    arguments = parser.parse_args()
    extracted = commands()
    check_merged_commands()
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

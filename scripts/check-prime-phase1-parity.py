#!/usr/bin/env python3
from __future__ import annotations

import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile

ROOT = Path(__file__).resolve().parents[1]
REGRESSIONS = "test_phase1_parity"
SUITES = [REGRESSIONS, "test_drive", "test_dcr", "test_thread_spawn", "test_failure_dcr", "test_resume_admission", "test_observation_admission"]


def check(root: Path, suites: list[str]) -> int:
    with tempfile.TemporaryDirectory(prefix="prime-parity-env-") as temporary:
        env = {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "HOME": temporary,
            "XDG_CONFIG_HOME": temporary,
            "XDG_DATA_HOME": temporary,
            "XDG_STATE_HOME": temporary,
            "XDG_CACHE_HOME": temporary,
            "TMPDIR": temporary,
            "PYTHONDONTWRITEBYTECODE": "1",
            "PYTHONPATH": str(root / "pi-streams/tests"),
            "PI_OFFLINE": "1",
        }
        return subprocess.run(["python3", "-m", "unittest", "-v", *suites], cwd=root, env=env).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="Check shared Pi adapter parity without a provider or production state. This does not prove native Prime support.")
    parser.add_argument("--compare", metavar="REF", help="also run the new regressions against a disposable Git snapshot, expecting failure")
    args = parser.parse_args()
    if args.compare:
        revision = subprocess.check_output(["git", "rev-parse", "--verify", args.compare + "^{commit}"], cwd=ROOT, text=True).strip()
        with tempfile.TemporaryDirectory(prefix="prime-parity-baseline-") as temporary:
            snapshot = Path(temporary)
            archive = snapshot / "baseline.tar"
            subprocess.run(["git", "archive", "--output", str(archive), revision], cwd=ROOT, check=True)
            subprocess.run(["tar", "-xf", str(archive), "-C", temporary], check=True)
            subprocess.run(["git", "init", "--quiet", temporary], check=True)
            subprocess.run(["git", "-C", temporary, "-c", "user.name=Test", "-c", "user.email=test@example.com", "-c", "core.hooksPath=/dev/null", "commit", "--quiet", "--allow-empty", "-m", "Disposable parity snapshot"], check=True)
            shutil.copyfile(ROOT / "pi-streams/tests/test_phase1_parity.py", snapshot / "pi-streams/tests/test_phase1_parity.py")
            print(f"Baseline {revision}. New regression failures are expected.", flush=True)
            if check(snapshot, [REGRESSIONS]) == 0:
                print("Baseline unexpectedly passed the new regressions.", flush=True)
                return 1
    print("Current shared Pi adapter acceptance. Native Prime is not exercised.", flush=True)
    return check(ROOT, SUITES)


if __name__ == "__main__":
    raise SystemExit(main())

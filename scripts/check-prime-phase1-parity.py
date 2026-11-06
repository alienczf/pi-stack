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
BASELINE_CASES = [
    REGRESSIONS + ".SpawnParityTests.test_spawn_without_ratification",
    REGRESSIONS + ".DriveParityTests.test_tick_heals_exact_silent_off_once",
    REGRESSIONS + ".DumpParityTests.test_validated_dump_survives_compaction_failure",
]
FAILURE_MARKERS = ("PHASE1_SPAWN_RATIFICATION", "PHASE1_DRIVE_SILENT_OFF", "PHASE1_VALIDATED_DUMP")
REGRESSION_SUITES = [REGRESSIONS, "test_phase1_native", "test_phase1_acceptance"]
SUITES = [*REGRESSION_SUITES, "test_drive", "test_dcr", "test_thread_spawn", "test_failure_dcr", "test_observation_admission"]


def expected_baseline_failures(result: subprocess.CompletedProcess[str]) -> bool:
    output = result.stdout + result.stderr
    return (result.returncode == 1 and "FAILED (failures=3)" in output
            and "Ran 3 tests" in output and "ERROR:" not in output
            and all(marker in output for marker in FAILURE_MARKERS))


def check(root: Path, suites: list[str], *, capture: bool = False) -> subprocess.CompletedProcess[str]:
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
        if os.environ.get("PI_STACK_NATIVE_TEST_ROOT"):
            env["PI_STACK_NATIVE_TEST_ROOT"] = os.environ["PI_STACK_NATIVE_TEST_ROOT"]
        return subprocess.run(["python3", "-m", "unittest", "-v", *suites], cwd=root, env=env, capture_output=capture, text=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="Check shared Pi adapter parity without a provider or production state. This does not prove native Prime support.")
    parser.add_argument("--compare", metavar="REF", help="also run the new regressions against a disposable Git snapshot, expecting failure")
    parser.add_argument("--regressions-only", action="store_true", help="run only the task-specific regression suites")
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
            baseline = check(snapshot, BASELINE_CASES, capture=True)
            output = baseline.stdout + baseline.stderr
            print(output, flush=True)
            if not expected_baseline_failures(baseline):
                print("Baseline must fail all three behavioral checks without fixture errors.", flush=True)
                return 1
    print("Current shared Pi adapter acceptance. Native Prime is not exercised.", flush=True)
    return check(ROOT, REGRESSION_SUITES if args.regressions_only else SUITES).returncode


if __name__ == "__main__":
    raise SystemExit(main())

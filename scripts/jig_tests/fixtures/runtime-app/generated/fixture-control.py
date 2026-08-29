#!/usr/bin/env python3
import hashlib
import json
import os
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

os.environ["PYTHONDONTWRITEBYTECODE"] = "1"
ROOT = Path.cwd()
RUNTIME = ROOT / ".pi/jig/verification/runtime"
STATE = RUNTIME / "state.json"
DRIVE_RESULT = RUNTIME / "drive-result.json"
EVIDENCE = ROOT / ".pi/jig/verification/evidence"
OWNED_PROCESS = None


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def process_start(pid):
    try:
        raw = (Path("/proc") / str(pid) / "stat").read_text(encoding="utf-8")
    except OSError:
        return None
    close = raw.rfind(")")
    fields = raw[close + 2:].split() if close >= 0 else []
    return fields[19] if len(fields) > 19 else None


def state_value():
    return json.loads(STATE.read_text(encoding="utf-8"))


def run_client(*arguments):
    state = state_value()
    result = subprocess.run(
        [sys.executable, "client.py", "--endpoint-file", state["endpointFile"], *arguments],
        cwd=ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=5,
    )
    return json.loads(result.stdout)


def cleanup():
    global OWNED_PROCESS
    if not STATE.exists():
        return
    state = state_value()
    pid = state["pid"]
    if process_start(pid) == state["processStart"]:
        os.kill(pid, signal.SIGTERM)
        if OWNED_PROCESS is not None and OWNED_PROCESS.pid == pid:
            try:
                OWNED_PROCESS.wait(timeout=2.5)
            except subprocess.TimeoutExpired:
                os.kill(pid, signal.SIGKILL)
                OWNED_PROCESS.wait(timeout=2)
        else:
            for _ in range(50):
                if process_start(pid) != state["processStart"]:
                    break
                time.sleep(0.05)
            else:
                os.kill(pid, signal.SIGKILL)
    OWNED_PROCESS = None
    shutil.rmtree(RUNTIME, ignore_errors=True)


def launch():
    global OWNED_PROCESS
    if STATE.exists():
        old = state_value()
        if process_start(old["pid"]) == old["processStart"]:
            raise RuntimeError("verification fixture is already running")
        shutil.rmtree(RUNTIME, ignore_errors=True)
    data = RUNTIME / "data"
    endpoint = RUNTIME / "endpoint.json"
    RUNTIME.mkdir(parents=True)
    process = subprocess.Popen(
        [sys.executable, "app.py", "--port", "0", "--data-dir", str(data), "--endpoint-file", str(endpoint)],
        cwd=ROOT,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    OWNED_PROCESS = process
    started = process_start(process.pid)
    if started is None:
        raise RuntimeError("fixture process identity is unavailable")
    STATE.write_bytes(canonical({"pid": process.pid, "processStart": started, "endpointFile": str(endpoint), "dataDir": str(data)}))
    for _ in range(100):
        if endpoint.exists():
            try:
                run_client("doctor")
                return state_value()
            except Exception:
                pass
        if process.poll() is not None:
            raise RuntimeError("fixture process exited before readiness")
        time.sleep(0.05)
    raise RuntimeError("fixture readiness timed out")


def doctor():
    state = state_value()
    value = run_client("doctor")
    if value["build"] != "fixture-v1" or value["dataDir"] != str(Path(state["dataDir"]).resolve()):
        raise RuntimeError("doctor found the wrong fixture instance")
    if value["pid"] != state["pid"] or process_start(state["pid"]) != state["processStart"]:
        raise RuntimeError("doctor found the wrong process owner")
    return value


def drive():
    action = run_client("add", "--title", "Release", "--body", "Ship it")
    listed = run_client("list")
    searched = run_client("search", "Release")
    persisted = json.loads((Path(state_value()["dataDir"]) / "notes.json").read_text(encoding="utf-8"))
    if action["title"] != "Release" or listed != persisted or searched != [action]:
        raise RuntimeError("public drive did not prove persisted visible state")
    result = {"action": action, "listed": listed, "searched": searched, "persisted": persisted}
    DRIVE_RESULT.write_bytes(canonical(result))
    return result


def evidence():
    value = json.loads(DRIVE_RESULT.read_text(encoding="utf-8"))
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    action_path = EVIDENCE / "protected-action.json"
    result_path = EVIDENCE / "protected-result.json"
    action_path.write_bytes(
        canonical(
            {
                "kind": "protected-action",
                "action": "Run python3 client.py add --title \"Release\" --body \"Ship it\" using the launched fixture.",
                "command": ["python3", "client.py", "add", "--title", "Release", "--body", "Ship it"],
            }
        )
    )
    result_path.write_bytes(
        canonical(
            {
                "kind": "protected-result",
                "visibleResult": "The public list command returns the saved Release note.",
                "evidence": "Capture the add command, list output, and persisted notes.json bytes.",
                "thresholds": "Complete within five seconds.",
                "observed": value["listed"],
                "persisted": value["persisted"],
            }
        )
    )
    return [
        {"path": action_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(action_path.read_bytes()).hexdigest()},
        {"path": result_path.relative_to(ROOT).as_posix(), "sha256": hashlib.sha256(result_path.read_bytes()).hexdigest()},
    ]


def self_test():
    state = launch()
    try:
        doctor()
        drive()
        artifacts = evidence()
    finally:
        cleanup()
    if process_start(state["pid"]) == state["processStart"]:
        raise RuntimeError("cleanup left the owned fixture process alive")
    revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, check=True, text=True, stdout=subprocess.PIPE).stdout.strip()
    return {
        "schemaVersion": 1,
        "kind": "verification-self-test",
        "sourceRevision": revision,
        "protectedFeatureId": "create-note",
        "phases": {"launch": True, "doctor": True, "drive": True, "evidence": True, "cleanup": True},
        "process": {"pid": state["pid"], "processStart": state["processStart"], "cleaned": True},
        "evidence": artifacts,
    }


def main():
    command = sys.argv[1] if len(sys.argv) == 2 else ""
    if command == "launch":
        print(json.dumps(launch(), sort_keys=True))
    elif command == "doctor":
        print(json.dumps(doctor(), sort_keys=True))
    elif command == "drive":
        print(json.dumps(drive(), sort_keys=True))
    elif command == "evidence":
        print(json.dumps(evidence(), sort_keys=True))
    elif command == "cleanup":
        cleanup()
    elif command == "self-test":
        print(json.dumps(self_test(), sort_keys=True))
    else:
        raise SystemExit("usage: fixture-control.py launch|doctor|drive|evidence|cleanup|self-test")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        cleanup()
        print(f"fixture-control: {error}", file=sys.stderr)
        raise SystemExit(1)

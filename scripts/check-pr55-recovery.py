#!/usr/bin/env python3
"""Verify PR 55 recovery through an isolated native service with no provider traffic."""
from __future__ import annotations

import argparse
import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("chaos", ROOT / "scripts/check-streams-chaos.py")
chaos = importlib.util.module_from_spec(spec)
spec.loader.exec_module(chaos)


class Sandbox(chaos.Sandbox):
    def __init__(self, *args, engine_root, acknowledge, **kwargs):
        super().__init__(*args, **kwargs)
        self.engine_root = engine_root
        self.env["PI_STREAMS_BIN"] = str(engine_root / "bin/pi-streams")
        self.env["CHAOS_LOAD_ACK"] = "1" if acknowledge else "0"

    def cli(self, *args, **kwargs):
        return self.command(self.engine_root / "bin/pi-streams", *args, "--home", self.index, **kwargs)


def historical(sandbox, worker, acknowledge):
    name, stream, coordinator = sandbox.new()
    sid = sandbox.worker(name) if worker else coordinator
    sandbox.control("history", {"session": sid})
    sandbox.tick()
    for _ in range(12):
        sandbox.wait_idle(sid)
        sandbox.tick()
        data = sandbox.state(stream)
        if data.get("dcr_operations", {}).get(sid, {}).get("phase") == "complete":
            break
    else:
        raise AssertionError("real first SYNC, compaction and RESUME did not complete")
    sandbox.wait_idle(sid)
    dump = sandbox.state(stream)["dcr_dumps"][sid]
    sandbox.prompt(sid, "Finish this bounded later work without external effects.")
    sandbox.objective(name, "Verify the newer objective without replaying old commands.")
    sandbox.control("history", {"session": sid})
    sandbox.plan(sid, {"ready": False, "text": "Finished the later SYNC turn without calling ready."})
    sandbox.tick()
    sandbox.wait_idle(sid)
    stalled = sandbox.state(stream)["dcr_operations"][sid]
    chaos.check(stalled["id"] != dump["id"] and stalled["phase"] == "sync-admitted" and not stalled["ready_revision"], "later SYNC trigger was not reached")
    current = (stream / "STATE.md").read_bytes()
    source = next(item for item in sandbox.control("snapshot")["evidence"] if item["session"] == sid)
    original = Path(source["file"]).read_bytes()
    for _ in range(6):
        sandbox.tick()
        intent = sandbox.state(stream).get("coordinator_replacement", {})
        if intent.get("phase") == "complete":
            sandbox.wait_idle(intent["target"])
            sandbox.tick()
            intent = sandbox.state(stream)["coordinator_replacement"]
            if intent.get("load", {}).get("state") in {"observed", "blocked"}:
                break
    data = sandbox.state(stream)
    intent = data.get("coordinator_replacement", {})
    chaos.check(intent.get("phase") == "complete", "P1 later idle SYNC did not recover from its retained validated dump")
    recovery = data["dcr_historical_recoveries"][sid]
    chaos.check(recovery["dump"] == dump and recovery["stalled_operation"] == stalled["id"], "selected dump impersonated the stalled operation")
    chaos.check(data["dcr_operations"][sid] == stalled and data["dcr_dumps"][sid] == dump, "immutable DCR evidence changed")
    handoff = json.loads((stream / intent["handoff"]["path"]).read_text())
    chaos.check((stream / handoff["syncedState"]["path"]).read_bytes() == base64.b64decode(dump["ready_source"]), "synced snapshot changed")
    chaos.check((stream / handoff["currentState"]["path"]).read_bytes() == current, "current snapshot changed")
    chaos.check(Path(handoff["archive"]["archivePath"]).read_bytes() == original, "native archive lost exact original bytes")
    chaos.check((stream / "STATE.md").read_bytes() == current, "recovery rewrote current STATE")
    expected = "observed" if acknowledge else "blocked"
    chaos.check(intent["load"]["state"] == expected, "terminal load did not get its exact acknowledgement disposition")
    if not acknowledge:
        load = intent["load"]
        before = sandbox.control("snapshot")
        for _ in range(3):
            sandbox.tick()
        after = sandbox.control("snapshot")
        reads = [item for item in after["requests"][len(before["requests"]):] if item["url"].split("?")[0] == f"/api/sessions/{coordinator}/status"]
        chaos.check(len(reads) >= 3, "P2 unloaded worker starved healthy coordinator observation")
        chaos.check(sandbox.state(stream)["coordinator_replacement"]["load"] == load, "blocked disposition changed or load replayed")
        new_calls = after["calls"][len(before["calls"]):]
        chaos.check(not any(item["session"] == intent["target"] for item in new_calls), "unloaded successor received task or command replay")
    sandbox.snapshot()
    return {"result": "PASS", "source": sid, "target": intent["target"], "role": handoff["role"], "load": intent["load"],
            "dump": dump["id"], "stalledOperation": stalled["id"], "archiveSha256": hashlib.sha256(original).hexdigest()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-tar", type=Path, required=True)
    parser.add_argument("--logs", type=Path, required=True)
    parser.add_argument("--engine-root", type=Path, default=ROOT)
    parser.add_argument("--cases", default="coordinator,worker,worker-no-ack")
    args = parser.parse_args()
    run = args.logs.resolve() / ("run-" + uuid.uuid4().hex)
    run.mkdir(parents=True)
    fixture = ROOT / ".harness-heal" / ("pr55-" + uuid.uuid4().hex)
    native = fixture / "native"
    native.mkdir(parents=True)
    results = []
    try:
        chaos.copy_native_archive(args.source_tar, native)
        subprocess.run([sys.executable, str(ROOT / "scripts/apply-native-overlay.py"), str(native)], check=True)
        for case in args.cases.split(","):
            chaos.check(case in {"coordinator", "worker", "worker-no-ack"}, "unknown recovery case")
            sandbox = Sandbox(run, case, native, shutil.which("node"), engine_root=args.engine_root.resolve(), acknowledge=case != "worker-no-ack")
            result = {"case": case, "result": "FAIL"}
            try:
                sandbox.start()
                result.update(historical(sandbox, case != "coordinator", case != "worker-no-ack"))
            except Exception as error:
                result["error"] = str(error)
                if sandbox.url:
                    sandbox.snapshot()
            finally:
                result["cleanup"] = sandbox.cleanup()
                results.append(result)
                chaos.save(run / "results.json", results)
            print(json.dumps(result), flush=True)
    finally:
        shutil.rmtree(fixture)
        chaos.save(run / "fixture-cleanup.json", {"path": str(fixture), "removed": not fixture.exists()})
    print(run)
    return 0 if all(item["result"] == "PASS" and item["cleanup"]["processStopped"] and item["cleanup"]["pathRemoved"] for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

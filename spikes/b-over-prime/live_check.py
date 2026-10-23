"""Control-only probe for a separately launched, private track-4 Prime daemon."""
import argparse
import json
import os
from pathlib import Path
import stat

from probe import Intake, Journal, Wire, dispatch


OWNER = "01a166e0-220d-7dbc-8b1c-719e872dad2d"


def check(root: Path, timeout: float, *, restart_only: bool = False):
    root = root.resolve()
    if root.parent != Path("/tmp") or not root.name.startswith("prime-t4."):
        raise ValueError("expected a private /tmp/prime-t4.* root")
    if root.stat().st_uid != os.getuid() or (root / "track4-owned").read_text().strip() != OWNER:
        raise ValueError("root owner marker mismatch")
    socket = root / "daemon.sock"
    identity = socket.stat()
    if not stat.S_ISSOCK(identity.st_mode) or identity.st_uid != os.getuid():
        raise ValueError("expected owned supervisor socket")
    settings = json.loads((root / "agent/settings.json").read_text())
    if settings != {"allowedModels": ["openai-codex/gpt-6.1-sol"], "retry": {
            "enabled": False, "failover": {"enabled": False}, "provider": {
                "waitForUsage": {"enabled": False, "pauseUntilReset": False}}}}:
        raise ValueError("retry, failover and quota parking must be disabled")
    report = {"root": str(root), "inference": "not attempted", "checks": []}
    sid = None

    def ok(wire, command, **fields):
        response = wire.request(command, **fields)
        if not response["success"]:
            raise AssertionError(response)
        return response.get("data")

    try:
        with Wire(str(socket), timeout=timeout) as wire, Journal(root / "intake.sqlite3") as journal:
            report["hello"] = {key: wire.hello[key] for key in (
                "type", "protocol", "schemaId", "schemaRevision", "appVersion",
                "supervisorGeneration", "supervisorPid", "serverCapabilities")}
            existing = ok(wire, "list", cwd=str(root / "work"), all=True)
            if restart_only:
                previous = json.loads((root / "live-check.json").read_text())
                rows = [row for row in existing["sessions"] if row["sessionId"] == previous["sessionId"]]
                assert len(rows) == 1 and rows[0]["messageCount"] == 1, rows
                assert rows[0]["lifecycle"] == "archived", rows
                durable = journal.lookup(Intake(previous["sessionId"], "user", "t4-preflight-1",
                                               "prompt_and_wait", "Track 4 preflight fixture. Do not perform any action."))
                assert durable["state"] == "rejected", durable
                report["checks"].append("archived session, one native user row, and shim rejection survive supervisor restart")
                report["result"] = "PASS"
                return report
            assert existing["sessions"] == [], existing
            created = ok(wire, "create", lifecycle="resident", telemetryDisabled=True, config={
                "cwd": str(root / "work"), "provider": "openai-codex", "model": "gpt-6.1-sol", "thinking": "xhigh"})
            sid = created["sessionId"]
            report["sessionId"] = sid
            state = ok(wire, "get_connection_state", activeSessionId=sid)
            assert state["cwd"] == str(root / "work"), state
            assert (state["model"]["provider"], state["model"]["id"]) == ("openai-codex", "gpt-6.1-sol"), state
            report["effectiveThinking"] = state.get("thinkingLevel")
            attached = ok(wire, "attach", activeSessionId=sid, capabilities=["attach_snapshot", "event_sequence"])
            report["attach"] = attached
            pause = ok(wire, "acquire_session_input_pause", activeSessionId=sid, leaseKey="prime-t4-control")
            report["pause"] = pause
            ask = Intake(sid, "user", "t4-message-1", "follow_up", "Track 4 control fixture. Never execute.")
            try:
                first = dispatch(journal, ask, wire.request)
                second = dispatch(journal, ask, lambda *a, **k: (_ for _ in ()).throw(AssertionError("duplicate dispatched")))
                assert first == second and first["state"] == "admitted", (first, second)
                queue = ok(wire, "get_queue", activeSessionId=sid)
                assert queue == {"steering": [], "followUp": [ask.body]}, queue
                report["checks"].append("typed source row persisted and duplicate suppressed; native paused queue has one input")
                report["intake"] = first
            finally:
                ok(wire, "clear_queue", activeSessionId=sid)
            assert ok(wire, "get_queue", activeSessionId=sid) == {"steering": [], "followUp": []}
            ok(wire, "release_session_input_pause", activeSessionId=sid, pauseId=pause["pauseId"])
            refusal = dispatch(journal, Intake(sid, "user", "t4-preflight-1", "prompt_and_wait",
                                               "Track 4 preflight fixture. Do not perform any action."), wire.request)
            assert refusal["state"] == "rejected", refusal
            assert "No API key found for openai-codex" in refusal["reply"].get("error", ""), refusal
            report["preflight"] = refusal
            report["checks"].append("missing-provider-credential refusal retained without model inference")
            messages = ok(wire, "get_messages", activeSessionId=sid)
            report["messages"] = messages
            rows = messages["messages"]
            assert any(row.get("role") == "user" for row in rows), rows
            assert not any(row.get("role") == "assistant" for row in rows), rows
            report["checks"].append("preflight has a user row but no assistant row")
            replay = ok(wire, "attach", activeSessionId=sid, capabilities=["attach_snapshot", "event_sequence"],
                        resumeCursor={"sequence": 0})
            assert replay["replay"]["status"] == "unavailable", replay
            assert replay["replay"]["reason"] == "event_replay_not_available", replay
            assert any(frame.get("event", {}).get("type") == "turn_end"
                       and "No API key found for openai-codex" in frame["event"].get("error", "")
                       for frame in wire.events), wire.events
            report["resumeAttach"] = replay
            report["events"] = wire.events
            report["checks"].append("turn_end error observed; offset-zero replay explicitly unavailable")
            report["result"] = "PASS"
    except BaseException as exc:
        report["result"] = "FAIL"
        report["failure"] = f"{type(exc).__name__}: {exc}"
        raise
    finally:
        current = socket.stat()
        if (current.st_dev, current.st_ino) != (identity.st_dev, identity.st_ino):
            raise RuntimeError("owned socket identity changed; refusing cleanup")
        with Wire(str(socket), timeout=timeout) as cleanup:
            if sid:
                report["abort"] = cleanup.request("abort_and_clear_queue", activeSessionId=sid)
                report["archive"] = cleanup.request("kill", activeSessionId=sid)
            report["shutdown"] = cleanup.request("shutdown", force=True)
        output = "restart-check.json" if restart_only else "live-check.json"
        (root / output).write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--timeout", type=float, required=True)
    parser.add_argument("--restart-only", action="store_true")
    args = parser.parse_args()
    report = check(args.root, args.timeout, restart_only=args.restart_only)
    output = "restart-check.json" if args.restart_only else "live-check.json"
    print(json.dumps({"result": report["result"], "checks": report["checks"],
                      "report": str(args.root / output)}))

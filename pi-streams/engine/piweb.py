from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

from engine import StreamsError, repo_root, sessionlog
from engine.project import default_pi_web_url


def _run(args: list[str], stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    # project.toml's pi_web_url is the address a browser opens, which may be a
    # tunnel. The engine runs beside pi-web, so it follows pi-web's own config.
    env = os.environ.copy()
    env.setdefault("PI_WEB_URL", default_pi_web_url())
    try:
        return subprocess.run(
            [sys.executable, os.fspath(repo_root() / "bin" / "pi-web-cli"), *args],
            input=stdin,
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=env,
            check=False,
            timeout=30,
        )
    except subprocess.TimeoutExpired as exc:
        raise StreamsError(f"pi-web receiving boundary timed out for {args[0]}") from exc


class PromptRejected(StreamsError):
    pass


def call(args: list[str], stdin: str | None = None) -> dict[str, object]:
    proc = _run(args, stdin)
    try:
        data = json.loads(proc.stdout) if proc.stdout.strip() else {}
    except json.JSONDecodeError as exc:
        detail = proc.stderr.strip() or proc.stdout.strip()
        raise StreamsError(f"pi-web-cli {' '.join(args)}: {detail}") from exc
    if not isinstance(data, dict):
        raise StreamsError(f"pi-web-cli {' '.join(args)} returned {type(data).__name__}")
    if proc.returncode != 0 or data.get("ok") is False:
        detail = proc.stderr.strip() or proc.stdout.strip()
        error = PromptRejected if args[0] in ("prompt", "compact", "maintenance-resume", "control-goal") and data.get("status") in (400, 404, 409, 422) else StreamsError
        raise error(f"pi-web-cli {' '.join(args)} failed: {detail}")
    return data


def list_sessions(cwd: str) -> list[dict[str, object]]:
    data = call(["list", "--cwd", cwd])
    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        raise StreamsError("pi-web-cli list returned no session list")
    return [item for item in sessions if isinstance(item, dict)]


def read_evidence(cwd: str, session_id: str, entry_id: str, expected_sha256: str, *, line_hint: int | None = None) -> sessionlog.EvidenceRecord:
    if line_hint is not None and (type(line_hint) is not int or line_hint < 1):
        raise StreamsError("evidence line hint must be a positive integer")
    matches = [item for item in list_sessions(cwd) if item.get("id") == session_id]
    if not matches:
        raise StreamsError(f"evidence session {session_id} unavailable")
    if len(matches) != 1:
        raise StreamsError(f"ambiguous evidence session {session_id}")
    info = matches[0]
    native_cwd = info.get("cwd")
    if not isinstance(native_cwd, str) or Path(native_cwd).resolve() != Path(cwd).resolve():
        raise StreamsError("evidence session identity has the wrong cwd")
    archived = info.get("archived") is True
    raw_path = info.get("archivePath" if archived else "path")
    if not isinstance(raw_path, str) or not raw_path or not Path(raw_path).is_absolute():
        kind = "archive" if archived else "live"
        raise StreamsError(f"{kind} evidence path unavailable for {session_id}")
    return sessionlog.read_record(Path(raw_path), session_id, entry_id, expected_sha256, archived=archived)


def spawn(cwd: str) -> str:
    data = call(["spawn", cwd])
    session = data.get("session")
    if not isinstance(session, dict) or not isinstance(session.get("id"), str) or not session["id"]:
        raise StreamsError("pi-web-cli spawn returned no session id")
    returned_cwd = session.get("cwd")
    if not isinstance(returned_cwd, str) or Path(returned_cwd).resolve() != Path(cwd).resolve():
        raise StreamsError("spawn identity has no matching native cwd")
    return str(session["id"])


def set_model(sid: str, model: str) -> None:
    call(["model", sid, model])


def set_thinking(sid: str, level: str) -> None:
    call(["thinking-level", sid, level])


def session_status(sid: str) -> dict[str, object]:
    data = call(["status", sid])
    session = data.get("session")
    if not isinstance(session, dict):
        raise StreamsError("pi-web-cli status returned no session")
    return session


def automatic_admission(session: dict[str, object], sid: str, cwd: str, kind: str) -> tuple[dict[str, str], bool]:
    raw = session.get("automaticAdmission")
    if not isinstance(raw, dict) or raw.get("durable") is not True:
        raise StreamsError("durable automatic admission capability is unavailable")
    native_cwd = raw.get("cwd")
    generation = raw.get("generation")
    if raw.get("sessionId") != sid or not isinstance(native_cwd, str) or Path(native_cwd).resolve() != Path(cwd).resolve():
        raise StreamsError("automatic admission capability has a mismatched native identity")
    if not isinstance(generation, str) or not generation or type(raw.get("allowed")) is not bool or kind not in ("wake", "recovery", "resume"):
        raise StreamsError("automatic admission capability is malformed")
    return {"sessionId": sid, "cwd": native_cwd, "generation": generation, "kind": kind}, raw["allowed"]


def set_automatic_admission(sid: str, allowed: bool, *, expected_generation: str | None = None) -> dict[str, object]:
    flags = [] if expected_generation is None else ["--expected-generation", expected_generation]
    data = call(["automatic-admission", sid, "on" if allowed else "off", *flags])
    result = data.get("result")
    if not isinstance(result, dict) or result.get("sessionId") != sid or result.get("durable") is not True or result.get("allowed") is not allowed or not isinstance(result.get("generation"), str) or not result["generation"]:
        raise StreamsError("automatic admission control publication is unconfirmed")
    return result


def prompt(sid: str, text: str, behavior: str | None = None, *, delivery_id: str | None = None, automatic: dict[str, str] | None = None, poteto_goal: str | None = None) -> dict[str, object]:
    # On argv, a text that starts with a dash would parse as a flag.
    flags = [] if behavior is None else [f"--{behavior}"]
    if delivery_id is not None:
        flags += ["--delivery-id", delivery_id]
    if automatic is not None:
        flags += ["--automatic-admission", json.dumps(automatic, ensure_ascii=False)]
    payload = text
    if poteto_goal is not None:
        require_poteto(sid)
        payload = _poteto_payload(text, poteto_goal)
        flags.append("--poteto")
    return call(["prompt", sid, *flags], stdin=payload)


def command_run(sid: str, text: str) -> dict:
    data = call(["command-run", sid], stdin=text)
    result = data.get("result")
    if data.get("commandAccepted") is not True or not isinstance(result, dict):
        raise StreamsError("native command acceptance is unconfirmed")
    return result


def maintenance_capabilities() -> bool:
    data = call(["runtime"])
    runtime = data.get("runtime")
    return isinstance(runtime, dict) and runtime.get("component") == "sessiond" and isinstance(runtime.get("capabilities"), list) and all(capability in runtime["capabilities"] for capability in ("sessions.maintenanceCheckpoint", "prompt.potetoArguments", "sessions.streamsDcrEvents", "prompt.controlGoal", "sessions.conditionalAdmission", "prompt.recoveryControl"))


def require_maintenance(sid: str) -> dict[str, object]:
    status = session_status(sid)
    require_identity(status, sid)
    if status.get("maintenanceSupport") != "checkpoint-input-v1":
        raise StreamsError("receiving maintenance capability is unavailable; automatic DCR is disabled")
    return status


def require_poteto(sid: str) -> dict[str, object]:
    status = session_status(sid)
    require_identity(status, sid)
    if status.get("potetoInvocationSupport") != "exact-goal-v1":
        raise StreamsError("recipient-loaded exact poteto invocation capability is unavailable")
    return status


def _poteto_payload(text: str, goal: str) -> str:
    invocation = "/poteto-mode " + goal
    if not goal.strip() or not text.endswith(invocation):
        raise StreamsError("poteto invocation body does not match its exact goal")
    prefix = text[:-len(invocation)]
    if prefix and not prefix.endswith("\n") or prefix.lstrip().startswith("/"):
        raise StreamsError("poteto invocation prefix is not a separate non-command prefix")
    return json.dumps({"text": text, "goal": goal}, ensure_ascii=False)


def _maintenance_result(data: dict, sid: str, identity: str, cwd: str) -> dict:
    result = data.get("result")
    if not isinstance(result, dict) or type(result.get("version")) is not int or result["version"] != 1 or result.get("id") != identity or result.get("sessionId") != sid:
        raise StreamsError("maintenance receiver returned a mismatched operation/session identity")
    native_cwd = result.get("cwd")
    if not isinstance(native_cwd, str) or Path(native_cwd).resolve() != Path(cwd).resolve():
        raise StreamsError("maintenance receiver returned a mismatched native cwd")
    if result.get("state") not in ("prepared", "compacting", "complete", "failed", "uncertain", "superseded", "resuming", "resumed") or type(result.get("inputSequence")) is not int or result["inputSequence"] < 0 or not isinstance(result.get("inputs"), list) or len(result["inputs"]) != result["inputSequence"]:
        raise StreamsError("maintenance receiver returned malformed phase/input state")
    return result


def register_stream_failure(sid: str, cwd: str, stream_dir: Path, status: dict, *, starting: bool = False) -> None:
    if status.get("failureBoundarySupport") != "persisted-turn-v1":
        return
    result = status.get("failureBoundary")
    if result is None:
        result = call(["failure-boundary", sid, "--cwd", cwd, "--stream", stream_dir.name, "--root", str(stream_dir.resolve())]).get("result")
    if not isinstance(result, dict) or type(result.get("version")) is not int or result["version"] != 1 or result.get("sessionId") != sid or result.get("cwd") != cwd or result.get("root") != str(stream_dir.resolve()) or result.get("stream") != stream_dir.name or result.get("state") not in ("watching", "parked", "uncertain"):
        raise StreamsError("native failure registration identity/state is unconfirmed")
    status["failureBoundary"] = result
    if starting and result["state"] != "watching":
        raise StreamsError("Native failure registration is parked or unconfirmed; no opening task was sent")


def ratify_failure(sid: str, cwd: str, request: dict) -> dict:
    data = call(["failure-ratify", sid, "--cwd", cwd], stdin=json.dumps(request, ensure_ascii=False))
    result = data.get("result")
    if not isinstance(result, dict) or type(result.get("version")) is not int or result["version"] != 1 or not isinstance(result.get("target"), dict) or result["target"].get("sessionId") != sid or result["target"].get("cwd") != cwd or not all(isinstance(result.get(key), str) for key in ("noticeId", "provenance", "instructions", "generation", "entryId", "sha256")):
        raise StreamsError("Native authenticated ratification receipt is unconfirmed")
    return result


def fork_failure(sid: str, cwd: str, request: dict) -> dict:
    result = call(["failure-fork", sid, "--cwd", cwd], stdin=json.dumps(request, ensure_ascii=False)).get("result")
    if not isinstance(result, dict) or result.get("version") != 1 or result.get("originalSessionId") != sid or result.get("cwd") != cwd or result.get("id") != request.get("id"):
        raise StreamsError("Native recovery returned an unconfirmed exact fork identity")
    return result


def failure_maintenance(sid: str, cwd: str, request: dict) -> dict:
    result = call(["failure-maintenance", sid, "--cwd", cwd], stdin=json.dumps(request, ensure_ascii=False)).get("result")
    if not isinstance(result, dict) or not isinstance(result.get("operation"), dict) or result["operation"].get("id") != request.get("id") or result["operation"].get("originalSessionId") != sid or result["operation"].get("cwd") != cwd:
        raise StreamsError("Native recovery maintenance owner is unconfirmed")
    return result


def require_control_goal(sid: str) -> dict[str, object]:
    status = require_poteto(sid)
    if status.get("controlGoalSupport") != "preserve-ask-v1":
        raise StreamsError("receiving question-preserving goal control is unavailable")
    return status


def _control_goal_result(data: dict, sid: str, cwd: str, identity: str) -> dict:
    result = data.get("result")
    if not isinstance(result, dict) or type(result.get("version")) is not int or result["version"] != 1 or result.get("id") != identity or result.get("sessionId") != sid or result.get("cwd") != cwd or result.get("state") not in ("queued", "sending", "ended", "uncertain", "superseded"):
        raise StreamsError("current-goal receiver returned unconfirmed identity/phase")
    return result


def control_goal(sid: str, identity: str, run_id: str, sequence: int, text: str, goal: str, automatic: dict[str, str] | None) -> dict:
    if automatic is None or automatic.get("kind") not in ("wake", "recovery") or automatic.get("sessionId") != sid:
        raise StreamsError("current-goal control requires its saved receiving generation")
    status = require_control_goal(sid)
    if automatic["kind"] == "recovery" and (status.get("recoveryControlSupport") != "question-safe-v1" or status.get("conditionalAdmissionSupport") != "generation-cas-v1"):
        raise StreamsError("question-safe conditional recovery control is unavailable")
    data = call(["control-goal", sid, identity, "--run-id", run_id, "--sequence", str(sequence), "--automatic-admission", json.dumps(automatic)], stdin=_poteto_payload(text, goal))
    return _control_goal_result(data, sid, automatic["cwd"], identity)


def control_goal_status(sid: str, cwd: str, identity: str) -> dict:
    return _control_goal_result(call(["control-goal", sid, identity, "--cwd", cwd, "--status"]), sid, cwd, identity)


def watch_dcr_events(sid: str, cwd: str, identity: str, index: Path, stream: str, generation: str) -> dict:
    data = call(["maintenance-events", sid, identity, "--cwd", cwd, "--index", str(index), "--stream", stream, "--generation", generation])
    result = data.get("result")
    if not isinstance(result, dict) or result.get("id") != identity or not isinstance(result.get("entryId"), str) or not result["entryId"]:
        raise StreamsError("native DCR event registration is unconfirmed")
    return result


def close_dcr_events(sid: str, cwd: str, identity: str) -> dict:
    data = call(["maintenance-events", sid, identity, "--cwd", cwd, "--close"])
    result = data.get("result")
    if not isinstance(result, dict) or result.get("id") != identity or result.get("closed") is not True:
        raise StreamsError("native DCR event close is unconfirmed")
    return result


def compact_at_checkpoint(sid: str, identity: str, expected: dict[str, str], instructions: str) -> dict:
    if set(expected) != {"sessionId", "cwd", "entryId", "generation"} or expected["sessionId"] != sid or not all(isinstance(value, str) and value for value in expected.values()):
        raise StreamsError("compaction requires the exact saved native checkpoint")
    status = require_maintenance(sid)
    automatic, allowed = automatic_admission(status, sid, expected["cwd"], "wake")
    safety = status.get("rotationSafety")
    if not allowed or automatic["generation"] != expected["generation"] or not isinstance(safety, dict) or safety.get("entryId") != expected["entryId"]:
        raise PromptRejected("saved maintenance checkpoint/generation was superseded")
    data = call(["compact", sid, identity, "--expected-idle", json.dumps(expected)], stdin=instructions)
    result = _maintenance_result(data, sid, identity, expected["cwd"])
    if result.get("entryId") != expected["entryId"] or result.get("generation") != expected["generation"] or result.get("instructions") != instructions:
        raise StreamsError("maintenance receiver changed the saved compaction intent")
    return result


def maintenance_status(cwd: str, sid: str, identity: str) -> dict:
    data = call(["maintenance", sid, identity, "--cwd", cwd])
    return _maintenance_result(data, sid, identity, cwd)


def reconcile_maintenance(cwd: str, sid: str, identity: str) -> dict:
    data = call(["maintenance", sid, identity, "--cwd", cwd, "--reconcile"])
    return _maintenance_result(data, sid, identity, cwd)


def resume_maintenance(sid: str, identity: str, compaction_entry: str, input_sequence: int, automatic: dict[str, str], delivery_id: str, text: str, *, poteto_goal: str | None = None) -> dict:
    if automatic.get("sessionId") != sid or automatic.get("kind") != "resume" or type(input_sequence) is not int or input_sequence < 0:
        raise StreamsError("RESUME requires its saved exact session/generation/input sequence")
    flags = ["maintenance-resume", sid, identity, "--compaction-entry", compaction_entry, "--input-sequence", str(input_sequence), "--delivery-id", delivery_id, "--automatic-admission", json.dumps(automatic)]
    payload = text
    if poteto_goal is not None:
        require_poteto(sid)
        flags.append("--poteto")
        payload = _poteto_payload(text, poteto_goal)
    data = call(flags, stdin=payload)
    result = _maintenance_result(data, sid, identity, automatic["cwd"])
    receipt = result.get("resume")
    if not isinstance(receipt, dict) or receipt.get("deliveryId") != delivery_id or receipt.get("text") != text or receipt.get("generation") != automatic.get("generation") or receipt.get("inputSequence") != input_sequence or receipt.get("potetoGoal") != poteto_goal:
        raise StreamsError("RESUME admission intent is unconfirmed or changed")
    return result


def compaction_result(cwd: str, sid: str, identity: str) -> dict | None:
    operation = maintenance_status(cwd, sid, identity)
    if operation["state"] in ("prepared", "compacting") or operation["state"] == "superseded" and operation.get("compactionEntryId") is None:
        return None
    if operation["state"] in ("failed", "uncertain"):
        raise StreamsError(f"maintenance {operation['state']}: {operation.get('detail', 'no proven completion')}")
    entry, digest = operation.get("compactionEntryId"), operation.get("compactionSha256")
    if not isinstance(entry, str) or not entry or not isinstance(digest, str) or re.fullmatch(r"[0-9a-f]{64}", digest) is None or not isinstance(operation.get("markerEntryId"), str) or not operation["markerEntryId"]:
        raise StreamsError("maintenance has no exact persisted compaction receipt")
    evidence = read_evidence(cwd, sid, entry, digest)
    return sessionlog.compaction_record(evidence)


def queue_clear(sid: str) -> None:
    call(["queue-clear", sid])


def archive(sid: str, *, expected_idle: dict[str, str] | None = None) -> dict[str, object]:
    flags = [] if expected_idle is None else ["--expected-idle", json.dumps(expected_idle, ensure_ascii=False)]
    data = call(["archive", sid, *flags])
    result = data.get("result")
    if not isinstance(result, dict) or (expected_idle is not None and result.get("archived") is not True):
        raise StreamsError("archive publication is unconfirmed")
    if expected_idle is not None:
        frozen = result.get("automaticAdmission")
        if not isinstance(frozen, dict) or frozen.get("sessionId") != sid or frozen.get("durable") is not True or frozen.get("allowed") is not False:
            raise StreamsError("replacement retirement barrier is unconfirmed")
    return result


def prompt_help() -> str:
    proc = _run(["prompt", "--help"])
    return proc.stdout + proc.stderr


def split_model(model: str) -> tuple[str, str]:
    provider, slash, model_id = model.partition("/")
    if slash == "" or provider == "" or model_id == "":
        raise StreamsError("model must be provider/id")
    return provider, model_id


def require_identity(session: dict[str, object], session_id: str) -> None:
    if session.get("sessionId") != session_id:
        raise StreamsError(f"native status identity does not match exact session {session_id}")


def require_settings(session: dict[str, object], model: str, thinking: str) -> None:
    provider, model_id = split_model(model)
    raw = session.get("model")
    if not isinstance(raw, dict):
        raise StreamsError("status has no model provider/id")
    got_provider = raw.get("provider")
    got_id = raw.get("id")
    if got_provider != provider or got_id != model_id:
        raise StreamsError(f"model is {got_provider}/{got_id}, expected {provider}/{model_id}")
    got_thinking = session.get("thinkingLevel")
    if got_thinking != thinking:
        raise StreamsError(f"thinkingLevel is {got_thinking}, expected {thinking}")


def configure_session(sid: str, model: str, thinking: str) -> dict[str, object]:
    require_identity(session_status(sid), sid)
    set_model(sid, model)
    set_thinking(sid, thinking)
    session = session_status(sid)
    require_identity(session, sid)
    require_settings(session, model, thinking)
    return session

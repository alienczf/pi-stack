from __future__ import annotations

import json
import os
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
    return subprocess.run(
        [sys.executable, os.fspath(repo_root() / "bin" / "pi-web-cli"), *args],
        input=stdin,
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=env,
        check=False,
    )


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
        error = PromptRejected if args[0] == "prompt" and data.get("status") in (400, 404, 409, 422) else StreamsError
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


def set_automatic_admission(sid: str, allowed: bool) -> dict[str, object]:
    data = call(["automatic-admission", sid, "on" if allowed else "off"])
    result = data.get("result")
    if not isinstance(result, dict) or result.get("sessionId") != sid or result.get("durable") is not True or result.get("allowed") is not allowed:
        raise StreamsError("automatic admission control publication is unconfirmed")
    return result


def prompt(sid: str, text: str, behavior: str | None = None, *, delivery_id: str | None = None, automatic: dict[str, str] | None = None) -> dict[str, object]:
    # On argv, a text that starts with a dash would parse as a flag.
    flags = [] if behavior is None else [f"--{behavior}"]
    if delivery_id is not None:
        flags += ["--delivery-id", delivery_id]
    if automatic is not None:
        flags += ["--automatic-admission", json.dumps(automatic, ensure_ascii=False)]
    return call(["prompt", sid, *flags], stdin=text)


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

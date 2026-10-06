from __future__ import annotations

import json
import os
import subprocess
import sys

from engine import StreamsError, repo_root
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
        raise StreamsError(f"pi-web-cli {' '.join(args)} failed: {detail}")
    return data


def list_sessions(cwd: str) -> list[dict[str, object]]:
    data = call(["list", "--cwd", cwd])
    sessions = data.get("sessions")
    if not isinstance(sessions, list):
        raise StreamsError("pi-web-cli list returned no session list")
    return [item for item in sessions if isinstance(item, dict)]


def spawn(cwd: str) -> str:
    data = call(["spawn", cwd])
    session = data.get("session")
    if not isinstance(session, dict) or not isinstance(session.get("id"), str):
        raise StreamsError("pi-web-cli spawn returned no session id")
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


def prompt(sid: str, text: str, behavior: str | None = None) -> None:
    # On argv, a text that starts with a dash would parse as a flag.
    flags = [] if behavior is None else [f"--{behavior}"]
    call(["prompt", sid, *flags], stdin=text)


def queue_clear(sid: str) -> None:
    call(["queue-clear", sid])


def archive(sid: str) -> None:
    call(["archive", sid])


def prompt_help() -> str:
    proc = _run(["prompt", "--help"])
    return proc.stdout + proc.stderr


def split_model(model: str) -> tuple[str, str]:
    provider, slash, model_id = model.partition("/")
    if slash == "" or provider == "" or model_id == "":
        raise StreamsError("model must be provider/id")
    return provider, model_id


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
    set_model(sid, model)
    set_thinking(sid, thinking)
    session = session_status(sid)
    require_settings(session, model, thinking)
    return session

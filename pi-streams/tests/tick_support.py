"""A home with streams for tick tests, with pi-web bodies in the shapes of @jmfederico/pi-web 1.202607.3.

status() is a SessionStatus and info() a SessionInfo from apiTypes.d.ts. write_log() writes
a session .jsonl in the entry shapes of pi-coding-agent's docs/session-format.md.
"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
from pathlib import Path

from support import EngineCase

HEADER = "session\trole\trepo\tworktree\tbranch\tbase\tmodel\tthinking\tstatus\tstarted\n"
SUBSCRIPTIONS = "id\tsource\ttarget\twhen\taction\n"
STARTED = "2026-10-06T00:00:00Z"
PROMPTS = ("POST", r"/api/sessions/[^/]+/prompt", 200, {"accepted": True})
OPENED = "2026-10-06T09:00:00.000Z"
OPENED_MS = 1791277200000
USAGE = {
    "input": 1200,
    "output": 300,
    "cacheRead": 0,
    "cacheWrite": 0,
    "totalTokens": 1500,
    "cost": {"input": 0.012, "output": 0.015, "cacheRead": 0, "cacheWrite": 0, "total": 0.027},
}


def user(text: str) -> dict[str, object]:
    return {"role": "user", "content": text, "timestamp": OPENED_MS}


def reply(text: str) -> dict[str, object]:
    return {
        "role": "assistant",
        "content": [{"type": "text", "text": text}],
        "api": "openai-codex-responses",
        "provider": "openai-codex",
        "model": "gpt-6-astra",
        "usage": USAGE,
        "stopReason": "stop",
        "timestamp": OPENED_MS,
    }


def failure(error: str) -> dict[str, object]:
    return {**reply(""), "content": [], "stopReason": "error", "errorMessage": error}


def thinking_change() -> dict[str, object]:
    return {"type": "thinking_level_change", "thinkingLevel": "xhigh"}


def row(
    sid: str,
    role: str,
    worktree: str,
    status: str = "active",
    repo: str = "alpha",
    branch: str = "",
) -> str:
    if role == "coordinator":
        repo = ""
    return f"{sid}\t{role}\t{repo}\t{worktree}\t{branch}\t\topenai-codex/gpt-6-astra\txhigh\t{status}\t{STARTED}\n"


def status(
    sid: str,
    *,
    streaming: bool = False,
    queued: tuple[tuple[str, str], ...] = (),
    tokens: int | None = 1000,
    ask: dict[str, object] | None = None,
) -> dict[str, object]:
    body: dict[str, object] = {
        "sessionId": sid,
        "persisted": True,
        "model": {
            "provider": "openai-codex",
            "id": "gpt-6-astra",
            "name": "GPT-6 Astra",
            "contextWindow": 400000,
            "reasoning": True,
        },
        "thinkingLevel": "xhigh",
        "isStreaming": streaming,
        "isCompacting": False,
        "isBashRunning": False,
        "pendingMessageCount": len(queued),
        "queuedMessages": [{"kind": kind, "text": text} for kind, text in queued],
        "messageCount": 12,
        "tokens": {"input": 1200, "output": 300, "cacheRead": 0, "cacheWrite": 0, "total": 1500},
        "cost": 0.5,
        "contextUsage": {
            "tokens": tokens,
            "contextWindow": 400000,
            "percent": None if tokens is None else tokens / 4000,
        },
    }
    if ask is not None:
        body["pendingAsk"] = ask
    return body


def info(sid: str, cwd: str, path: str, modified: str = "2026-10-06T11:00:00.000Z") -> dict[str, object]:
    return {
        "id": sid,
        "path": path,
        "persisted": True,
        "cwd": cwd,
        "created": "2026-10-06T09:00:00.000Z",
        "modified": modified,
        "messageCount": 12,
        "firstMessage": "",
    }


def got_status(sid: str) -> tuple[str, str, str, object]:
    return ("GET", f"/api/sessions/{sid}/status", "", None)


def got_list(cwd: str) -> tuple[str, str, str, object]:
    return ("GET", "/api/sessions", urllib.parse.urlencode({"cwd": cwd}), None)


def got_prompt(sid: str, text: str, behavior: str | None = None) -> tuple[str, str, str, object]:
    body: dict[str, object] = {"text": text}
    if behavior is not None:
        body["streamingBehavior"] = behavior
    return ("POST", f"/api/sessions/{sid}/prompt", "", body)


def got_post(sid: str, verb: str, body: object = None) -> tuple[str, str, str, object]:
    return ("POST", f"/api/sessions/{sid}/{verb}", "", {} if body is None else body)


def rotation(stream: str) -> str:
    return (
        f"You are the new coordinator for stream {stream}. "
        "Your memory is the files in this folder. Read STATE.md, then continue."
    )


class TickCase(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.logs = self.tmp / "sessions"
        self.logs.mkdir()
        self.stub.requests.clear()

    def make_stream(self, home: Path, name: str, rows: str) -> Path:
        stream_dir = (home / name).resolve()
        stream_dir.mkdir()
        (stream_dir / "STREAM.md").write_text("ratified: 2026-10-06\n", encoding="utf-8")
        (stream_dir / "threads.tsv").write_text(HEADER + rows, encoding="utf-8")
        (stream_dir / "subscriptions.tsv").write_text(SUBSCRIPTIONS, encoding="utf-8")
        return stream_dir

    def subscribe(self, stream_dir: Path, *rows: str) -> None:
        text = SUBSCRIPTIONS + "".join(f"{line}\n" for line in rows)
        (stream_dir / "subscriptions.tsv").write_text(text, encoding="utf-8")

    def log_path(self, sid: str) -> str:
        return str(self.logs / f"{sid}.jsonl")

    def write_log(self, sid: str, cwd: str, *items: dict[str, object]) -> None:
        entries: list[dict[str, object]] = [
            {"type": "session", "version": 3, "id": sid, "timestamp": OPENED, "cwd": cwd},
        ]
        for index, item in enumerate(items, start=1):
            head = {"id": f"e{index}", "parentId": f"e{index - 1}" if index > 1 else None, "timestamp": OPENED}
            if "role" in item:
                entries.append({"type": "message", **head, "message": item})
            else:
                entries.append({"type": item["type"], **head, **item})
        text = "".join(json.dumps(entry, separators=(",", ":")) + "\n" for entry in entries)
        Path(self.log_path(sid)).write_text(text, encoding="utf-8")

    def alerts(self) -> str:
        return (self.home / "ALERTS").read_text(encoding="utf-8")

    def tick(self, at: str, *args: str) -> subprocess.CompletedProcess[str]:
        self.stub.requests.clear()
        self.env["PI_STREAMS_NOW"] = at
        return self.run_streams("tick", *args)

    def events(self, stream_dir: Path) -> str:
        return (stream_dir / "log" / "events.jsonl").read_text(encoding="utf-8")

    def state(self, stream_dir: Path) -> object:
        return json.loads((stream_dir / "log" / "tick-state.json").read_text(encoding="utf-8"))

    def rows(self, stream_dir: Path) -> str:
        return (stream_dir / "threads.tsv").read_text(encoding="utf-8")

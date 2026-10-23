"""A home with streams for tick tests, with pi-web bodies in the shapes of @jmfederico/pi-web 1.202607.3.

status() is a SessionStatus and info() a SessionInfo from apiTypes.d.ts. write_log() writes
a session .jsonl in the entry shapes of pi-coding-agent's docs/session-format.md.
"""
from __future__ import annotations

import json
import subprocess
import urllib.parse
from pathlib import Path

from support import EngineCase, ROOT, git, pi_stack_revision

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


def rotation(stream: str, path: Path) -> str:
    return (
        f"You are the new coordinator for stream {stream}. "
        f"Read {path}/AGENTS.md and {path}/STATE.md before acting. "
        "Use Goals' current objective, falling back to North Star. Current Goals and Rules take precedence. "
        "Open history/, context/, checks/, and handover/ only on demand. "
        "Goal at pickup:\n<the single human-authorized outcome>"
    )


class TickCase(EngineCase):
    def setUp(self) -> None:
        super().setUp()
        proc = self.run_streams("init", str(self.root), "-y")
        self.assertEqual(proc.returncode, 0, proc.stderr)
        self.stub.reflect_delivery_ids = True
        self.stub.simulate_session_lifecycle = True
        self.fixture_streams: list[Path] = []
        self.logs = self.tmp / "sessions"
        self.logs.mkdir()
        self.stub.requests.clear()

    def make_stream(
        self,
        home: Path,
        name: str,
        rows: str,
        index: Path | None = None,
        project: str | None = None,
    ) -> Path:
        project_name = self.root.name if project is None else project
        stream_dir = self.register_stream(name, (home / name).resolve(), index, project_name)
        self.fixture_streams.append(stream_dir)
        state = (ROOT / "pi-streams/templates/stream/STATE.md").read_text()
        (stream_dir / "STATE.md").write_text(state.replace("ratified: no", "ratified: 2026-10-23 fixture human confirmation", 1))
        (stream_dir / "threads.tsv").write_text(HEADER + rows, encoding="utf-8")
        (stream_dir / "subscriptions.tsv").write_text(SUBSCRIPTIONS, encoding="utf-8")
        (stream_dir / ".gitignore").write_text("log/\n", encoding="utf-8")
        (stream_dir / "stream.toml").write_text(
            f'project = "{project_name}"\npi_stack_revision = "{pi_stack_revision()}"\nstate_schema = 1\n',
            encoding="utf-8",
        )
        if not (stream_dir / ".git").exists():
            git(stream_dir, self.env, "init", "--quiet")
        git(stream_dir, self.env, "add", "-A")
        if git(stream_dir, self.env, "status", "--porcelain").strip() != "":
            git(stream_dir, self.env, "commit", "-m", "fixture")
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
        return (self.index / "ALERTS").read_text(encoding="utf-8")

    def tick(self, at: str, *args: str) -> subprocess.CompletedProcess[str]:
        routes = list(self.stub.routes)
        native = []
        for stream in self.fixture_streams:
            table = stream / "threads.tsv"
            for line in table.read_text().splitlines()[1:]:
                cells = line.split("\t")
                if len(cells) != 10:
                    continue
                sid, role, _, cwd = cells[:4]
                native.append(info(sid, cwd, self.log_path(sid)))
                if role == "coordinator" and not any(method == "GET" and path == f"/api/sessions/{sid}/status" for method, path, _, _ in routes):
                    routes.append(("GET", f"/api/sessions/{sid}/status", 200, status(sid)))
        if not any(method == "GET" and path == "/api/sessions" for method, path, _, _ in routes):
            routes.append(("GET", "/api/sessions", 200, native))
        self.stub.set_routes(routes)
        self.stub.requests.clear()
        self.env["PI_STREAMS_NOW"] = at
        return self.run_streams("tick", *args)

    def apply_tick_delivery(self, stream_dir: Path) -> None:
        data = self.state(stream_dir)
        identity = data["tick_delivery"]
        record = data["deliveries"][identity]
        proof = Path("context") / f"fixture-plan-{identity}.md"
        (stream_dir / proof).parent.mkdir(exist_ok=True)
        (stream_dir / proof).write_text(f"Fixture coordinator incorporated this event batch in its active plan.\n{record['body']}\n")
        for phase, detail, extra in (
            ("consumed", "Read the exact fixture event batch.", []),
            ("applied", "Incorporated the batch in the fixture active plan.", ["--evidence", str(proof)]),
        ):
            result = self.run_streams("delivery", "ack", stream_dir.name, identity, "--session", record["session"], "--state", phase, "--detail", detail, *extra)
            self.assertEqual(result.returncode, 0, result.stderr)
        git(stream_dir, self.env, "add", "--", str(proof))
        git(stream_dir, self.env, "commit", "-m", "fixture applied tick batch")

    def tick_facts(self, stream_dir: Path) -> dict:
        return {key: value for key, value in self.state(stream_dir).items() if key not in ("deliveries", "tick_delivery")}

    def events(self, stream_dir: Path) -> str:
        return (stream_dir / "log" / "events.jsonl").read_text(encoding="utf-8")

    def state(self, stream_dir: Path) -> object:
        return json.loads((stream_dir / "log" / "tick-state.json").read_text(encoding="utf-8"))

    def rows(self, stream_dir: Path) -> str:
        return (stream_dir / "threads.tsv").read_text(encoding="utf-8")

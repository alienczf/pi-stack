from __future__ import annotations

import json
import os
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engine import StreamsError, clock, piweb
from engine.project import Project, commit_home, home_lock, load_project, stream_dirs
from engine.threads import Status, Thread, load_threads, rotate_coordinator, save_threads

WAKE_KINDS = frozenset({"idle", "ask", "context", "stale-steer"})
QUEUE_FLAGS = {"steer": "steer", "followUp": "follow-up"}


@dataclass
class Event:
    at: str
    kind: str
    session: str
    role: str
    detail: str

    def line(self) -> str:
        detail = " / ".join(self.detail.splitlines())
        return " ".join(part for part in (self.kind, self.session, self.role, detail) if part)


@dataclass
class Seen:
    busy: bool = False
    asks: list[str] = field(default_factory=list)
    context: bool = False
    queued: dict[str, str] = field(default_factory=dict)


@dataclass
class TickState:
    sessions: dict[str, Seen] = field(default_factory=dict)
    pending: list[Event] = field(default_factory=list)


def write_atomic(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_state(path: Path) -> TickState:
    if not path.exists():
        return TickState()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return TickState(
            sessions={str(sid): Seen(**seen) for sid, seen in data["sessions"].items()},
            pending=[Event(**item) for item in data["pending"]],
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc


def save_state(path: Path, state: TickState) -> None:
    data = {
        "sessions": {sid: asdict(seen) for sid, seen in state.sessions.items()},
        "pending": [asdict(event) for event in state.pending],
    }
    write_atomic(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


def _count(value: object) -> int:
    return value if isinstance(value, int) and not isinstance(value, bool) else 0


def _tokens(status: dict[str, object]) -> int | None:
    usage = status.get("contextUsage")
    tokens = usage.get("tokens") if isinstance(usage, dict) else None
    if isinstance(tokens, bool) or not isinstance(tokens, (int, float)):
        return None
    return int(tokens)


def _questions(ask: dict[str, object]) -> str:
    questions = ask.get("questions")
    if not isinstance(questions, list):
        return ""
    return "\n".join(
        item["question"] for item in questions if isinstance(item, dict) and isinstance(item.get("question"), str)
    )


def _queued(status: dict[str, object]) -> dict[str, str]:
    items = status.get("queuedMessages")
    found: dict[str, str] = {}
    for item in items if isinstance(items, list) else []:
        if isinstance(item, dict) and item.get("kind") in QUEUE_FLAGS and isinstance(item.get("text"), str):
            found.setdefault(item["text"], item["kind"])
    return found


class StreamTick:
    def __init__(self, project: Project, stream_dir: Path, now: datetime) -> None:
        self.project = project
        self.caps = project.caps
        self.stream_dir = stream_dir
        self.stream = stream_dir.name
        self.now = now
        self.at = clock.stamp(now)
        self.state_path = stream_dir / "log" / "tick-state.json"
        self.events_path = stream_dir / "log" / "events.jsonl"
        self.rows_path = stream_dir / "threads.tsv"
        self.state = TickState()
        self.rows: list[Thread] = []
        self.rows_dirty = False
        self.events: list[Event] = []
        self.logged = 0
        self.listings: dict[str, dict[str, dict[str, object]]] = {}

    def run(self) -> None:
        self.state = load_state(self.state_path)
        self.rows = load_threads(self.rows_path)
        self.observe()
        self.flush()
        self.wake()
        self.flush()

    def emit(self, kind: str, row: Thread | None = None, detail: str = "") -> None:
        event = Event(self.at, kind, row.session if row else "", row.role if row else "", detail)
        self.events.append(event)
        if kind in WAKE_KINDS:
            self.state.pending.append(event)

    def flush(self) -> None:
        if self.rows_dirty:
            save_threads(self.rows_path, self.rows)
            self.rows_dirty = False
        if self.logged < len(self.events):
            self.events_path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.events_path, "a", encoding="utf-8", newline="\n") as handle:
                for event in self.events[self.logged :]:
                    handle.write(json.dumps(asdict(event), ensure_ascii=False) + "\n")
            self.logged = len(self.events)
        save_state(self.state_path, self.state)

    def listing(self, cwd: str) -> dict[str, dict[str, object]]:
        if cwd not in self.listings:
            self.listings[cwd] = {
                item["id"]: item for item in piweb.list_sessions(cwd) if isinstance(item.get("id"), str)
            }
        return self.listings[cwd]

    def coordinator(self) -> Thread | None:
        for row in self.rows:
            if row.role == "coordinator" and row.status is Status.active:
                return row
        return None

    def observe(self) -> None:
        observed: set[str] = set()
        for row in self.rows:
            if row.role != "coordinator" and row.status in (Status.active, Status.waiting_quota):
                self.observe_thread(row)
                observed.add(row.session)
        self.state.sessions = {sid: seen for sid, seen in self.state.sessions.items() if sid in observed}

    def observe_thread(self, row: Thread) -> None:
        status = piweb.session_status(row.session)
        old = self.state.sessions.get(row.session, Seen())
        new = Seen(
            busy=status.get("isStreaming") is True or _count(status.get("pendingMessageCount")) > 0,
            context=old.context,
        )
        self.state.sessions[row.session] = new
        if old.busy and not new.busy:
            self.emit("idle", row)
        ask = status.get("pendingAsk")
        if isinstance(ask, dict) and isinstance(ask.get("askId"), str):
            new.asks = [ask["askId"]]
            if ask["askId"] not in old.asks:
                self.emit("ask", row, _questions(ask))
        tokens = _tokens(status)
        if not old.context and tokens is not None and tokens >= self.caps.thread_handover_tokens:
            new.context = True
            self.emit("context", row, f"{tokens} tokens")
        self.resend_stale(row, status, old, new)

    def resend_stale(self, row: Thread, status: dict[str, object], old: Seen, new: Seen) -> None:
        queued = _queued(status)
        new.queued = {text: old.queued.get(text, self.at) for text in queued}
        limit = timedelta(minutes=self.caps.steer_queue_minutes)
        stale = [text for text, seen in new.queued.items() if self.since(seen) >= limit]
        if not stale:
            return
        for text in stale:
            self.emit("stale-steer", row, text)
        # queue/clear drops every queued message, not only the stale ones.
        piweb.queue_clear(row.session)
        for text, kind in queued.items():
            piweb.prompt(row.session, text, "steer" if text in stale else QUEUE_FLAGS[kind])
        for text in stale:
            new.queued[text] = self.at

    def since(self, stamp: str) -> timedelta:
        seen = clock.parse(stamp)
        return timedelta(0) if seen is None else self.now - seen

    def wake(self) -> None:
        coord = self.coordinator()
        if not self.state.pending or coord is None:
            return
        text = "\n".join([f"pi-streams tick {self.at}:", *(event.line() for event in self.state.pending)])
        status = piweb.session_status(coord.session)
        if status.get("isStreaming") is True:
            piweb.prompt(coord.session, text, "follow-up")
        elif self.warm(coord, status):
            piweb.prompt(coord.session, text)
        else:
            self.flush()
            sid = rotate_coordinator(self.project, self.stream)
            self.rows = load_threads(self.rows_path)
            piweb.prompt(sid, text, "follow-up")
        self.state.pending = []

    def warm(self, coord: Thread, status: dict[str, object]) -> bool:
        tokens = _tokens(status)
        if tokens is not None and tokens >= self.caps.warm_context_tokens:
            return False
        info = self.listing(str(self.stream_dir)).get(coord.session)
        modified = clock.parse(info.get("modified")) if info is not None else None
        return modified is not None and self.now - modified < timedelta(hours=self.caps.warm_idle_hours)


def tick_home(home: Path, now: datetime) -> list[str]:
    lines: list[str] = []
    with home_lock(home):
        project = load_project(home)
        for stream_dir in stream_dirs(home):
            run = StreamTick(project, stream_dir, now)
            run.run()
            counts = Counter(event.kind for event in run.events)
            if counts:
                lines.append(f"{stream_dir}\t" + "\t".join(f"{kind}={counts[kind]}" for kind in sorted(counts)))
        commit_home(home, "pi-streams tick")
    return lines


def run_tick(homes: list[Path]) -> int:
    now = clock.now()
    for home in homes:
        for line in tick_home(home, now):
            print(line)
    return 0

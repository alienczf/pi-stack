from __future__ import annotations

import json
import os
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engine import StreamsError, clock, piweb, sessionlog
from engine.project import Project, commit_home, home_lock, load_project, push_home, stream_dirs
from engine.subscriptions import SOURCES, Subscription, load_subscriptions
from engine.threads import Status, Thread, load_threads, rotate_coordinator, save_threads, transition

WAKE_KINDS = frozenset({"idle", "ask", "context", "stale-steer", "outage", "recovered", "subscription", "claim"})
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
class Mark:
    watch: list[str]
    fingerprint: str


@dataclass
class Claim:
    key: str
    alert: str
    row: Thread
    detail: str


@dataclass
class TickState:
    sessions: dict[str, Seen] = field(default_factory=dict)
    pending: list[Event] = field(default_factory=list)
    outages: list[str] = field(default_factory=list)
    rotating: bool = False
    subscriptions: dict[str, Mark] = field(default_factory=dict)
    claims: list[str] = field(default_factory=list)


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
            sessions={str(sid): Seen(**seen) for sid, seen in data.get("sessions", {}).items()},
            pending=[Event(**item) for item in data.get("pending", [])],
            outages=[str(sid) for sid in data.get("outages", [])],
            rotating=data.get("rotating", False) is True,
            subscriptions={str(sub): Mark(**mark) for sub, mark in data.get("subscriptions", {}).items()},
            claims=[str(key) for key in data.get("claims", [])],
        )
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc


def save_state(path: Path, state: TickState) -> None:
    data = {
        "sessions": {sid: asdict(seen) for sid, seen in state.sessions.items()},
        "pending": [asdict(event) for event in state.pending],
        "outages": state.outages,
        "rotating": state.rotating,
        "subscriptions": {sub: asdict(mark) for sub, mark in state.subscriptions.items()},
        "claims": state.claims,
    }
    write_atomic(path, json.dumps(data, indent=2, sort_keys=True) + "\n")


class Alerts:
    def __init__(self, path: Path) -> None:
        self.path = path
        try:
            self.lines = path.read_text(encoding="utf-8").splitlines() if path.is_file() else []
        except OSError as exc:
            raise StreamsError(f"could not read {path}: {exc}") from exc
        self.changed = False

    def add(self, line: str) -> None:
        if all(_alert_key(item) != _alert_key(line) for item in self.lines):
            self.lines.append(line)
            self.changed = True

    def clear(self, *key: str) -> None:
        kept = [item for item in self.lines if _alert_key(item) != key]
        if len(kept) < len(self.lines):
            self.lines = kept
            self.changed = True

    def save(self) -> None:
        if self.changed:
            write_atomic(self.path, "".join(f"{line}\n" for line in self.lines))
            self.changed = False


def _alert_key(line: str) -> tuple[str, ...]:
    return tuple(line.split(" ")[1:3])


def _summary(error: object) -> str:
    return " ".join(error[:200].splitlines()) if isinstance(error, str) else ""


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


def _working(status: dict[str, object]) -> bool:
    # pi-web refuses to archive a session in any of these states, not only while it streams.
    busy = any(status.get(name) is True for name in ("isStreaming", "isCompacting", "isBashRunning"))
    return busy or _count(status.get("pendingMessageCount")) > 0


def _queued(status: dict[str, object]) -> list[tuple[str, str]]:
    items = status.get("queuedMessages")
    return [
        (item["text"], item["kind"])
        for item in (items if isinstance(items, list) else [])
        if isinstance(item, dict) and item.get("kind") in QUEUE_FLAGS and isinstance(item.get("text"), str)
    ]


class StreamTick:
    def __init__(
        self,
        project: Project,
        stream_dir: Path,
        now: datetime,
        alerts: Alerts,
        claims: list[Claim] | None,
    ) -> None:
        self.project = project
        self.caps = project.caps
        self.stream_dir = stream_dir
        self.stream = stream_dir.name
        self.now = now
        self.at = clock.stamp(now)
        self.alerts = alerts
        self.claims = claims
        self.state_path = stream_dir / "log" / "tick-state.json"
        self.events_path = stream_dir / "log" / "events.jsonl"
        self.rows_path = stream_dir / "threads.tsv"
        self.state = TickState()
        self.rows: list[Thread] = []
        self.rows_dirty = False
        self.events: list[Event] = []
        self.logged = 0
        self.listings: dict[str, dict[str, dict[str, object]]] = {}
        self.loaded = False
        self.errors: list[str] = []

    def run(self) -> None:
        try:
            self.state = load_state(self.state_path)
            self.loaded = True
            self.rows = load_threads(self.rows_path)
            self.check_claims()
            self.observe()
            self.check_subscriptions()
            self.flush()
            self.wake()
            self.archive_done()
        except StreamsError as exc:
            self.fail(str(exc))
        self.flush()

    def emit(self, kind: str, row: Thread | None = None, detail: str = "") -> None:
        event = Event(self.at, kind, row.session if row else "", row.role if row else "", detail)
        self.events.append(event)
        if kind in WAKE_KINDS:
            self.state.pending.append(event)

    def fail(self, detail: str) -> None:
        self.errors.append(detail)
        self.emit("tick-error", detail=detail)

    def check_claims(self) -> None:
        if self.claims is None:
            return
        for claim in self.claims:
            self.alerts.add(f"{self.at} {claim.alert}")
            if claim.key not in self.state.claims:
                self.emit("claim", claim.row, claim.detail)
        held = [claim.key for claim in self.claims]
        for key in self.state.claims:
            if key not in held:
                self.alerts.clear("claim", key)
        self.state.claims = held

    def check_subscriptions(self) -> None:
        if self.coordinator() is None and not self.state.rotating:
            return
        try:
            subs = load_subscriptions(self.stream_dir / "subscriptions.tsv")
        except StreamsError as exc:
            self.fail(str(exc))
            return
        marks: dict[str, Mark] = {}
        for sub in subs:
            old = self.state.subscriptions.get(sub.id)
            mark = self.check_subscription(sub, old)
            if mark is not None:
                marks[sub.id] = mark
        self.state.subscriptions = marks

    def check_subscription(self, sub: Subscription, old: Mark | None) -> Mark | None:
        source = SOURCES.get(sub.source)
        if source is None:
            self.fail(f"subscription {sub.id}: unknown source {sub.source}")
            return None
        try:
            reading = source(sub, self.stream_dir, self.now)
        except StreamsError as exc:
            self.fail(f"subscription {sub.id}: {exc}")
            return old
        if old is not None and old.watch == sub.watch() and old.fingerprint != reading.fingerprint:
            head = f"{sub.id}: {sub.action}" if sub.action else sub.id
            self.emit("subscription", detail="\n".join([head, *reading.detail]))
        return Mark(sub.watch(), reading.fingerprint)

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
        # A state file that does not parse is left for a person to read.
        if self.loaded:
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
        coord = self.coordinator()
        self.state.outages = [sid for sid in self.state.outages if coord is not None and sid == coord.session]
        if coord is not None:
            self.check_outage(coord)
        for row in self.rows:
            if not self.out(row):
                self.alerts.clear(self.stream, row.session)

    def out(self, row: Thread) -> bool:
        # The coordinator stays active during its outage, so that pi-streams new
        # does not start a second one; the tick state remembers it instead.
        if row.role == "coordinator":
            return row.session in self.state.outages
        return row.status is Status.waiting_quota

    def check_outage(self, row: Thread) -> None:
        info = self.listing(row.worktree).get(row.session)
        if info is None or not isinstance(info.get("path"), str):
            return
        message = sessionlog.last_assistant(Path(info["path"]))
        if message is not None and message.get("stopReason") == "error":
            summary = _summary(message.get("errorMessage"))
            self.alerts.add(" ".join(part for part in (self.at, self.stream, row.session, row.role, summary) if part))
            if not self.out(row):
                self.set_out(row, True)
                self.emit("outage", row, summary)
        elif self.out(row):
            self.set_out(row, False)
            self.alerts.clear(self.stream, row.session)
            self.emit("recovered", row)

    def set_out(self, row: Thread, out: bool) -> None:
        if row.role == "coordinator":
            self.state.outages = [row.session] if out else []
            return
        transition(row, Status.waiting_quota if out else Status.active)
        self.rows_dirty = True

    def observe_thread(self, row: Thread) -> None:
        status = piweb.session_status(row.session)
        # A spawned thread starts on a prompt, so one first seen idle has finished it,
        # even when it did so between two ticks. An adopted thread that is already
        # idle reports idle once too, which tells its coordinator that it waits.
        old = self.state.sessions.get(row.session, Seen(busy=True))
        new = Seen(
            busy=status.get("isStreaming") is True or _count(status.get("pendingMessageCount")) > 0,
            context=old.context,
        )
        self.state.sessions[row.session] = new
        if old.busy and not new.busy:
            self.emit("idle", row)
        self.check_outage(row)
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
        new.queued = {text: old.queued.get(text, self.at) for text, _kind in queued}
        limit = timedelta(minutes=self.caps.steer_queue_minutes)
        # A steer that still waits cannot be sent any harder, so only follow-ups go stale.
        stale = list(dict.fromkeys(
            text for text, kind in queued if kind == "followUp" and self.since(new.queued[text]) >= limit
        ))
        if not stale:
            return
        for text in stale:
            self.emit("stale-steer", row, text)
        # queue/clear drops every queued message, not only the stale ones.
        piweb.queue_clear(row.session)
        for text, kind in queued:
            piweb.prompt(row.session, text, "steer" if text in stale else QUEUE_FLAGS[kind])
        for text in stale:
            new.queued[text] = self.at

    def since(self, stamp: str) -> timedelta:
        seen = clock.parse(stamp)
        return timedelta(0) if seen is None else self.now - seen

    def wake(self) -> None:
        coord = self.coordinator()
        if not self.state.pending or (coord is None and not self.state.rotating):
            return
        if coord is not None and self.out(coord):
            return
        text = "\n".join([f"pi-streams tick {self.at}:", *(event.line() for event in self.state.pending)])
        sid, behavior = self.wake_target(coord)
        piweb.prompt(sid, text, behavior)
        self.state.pending = []
        self.state.rotating = False

    def wake_target(self, coord: Thread | None) -> tuple[str, str | None]:
        if coord is not None:
            status = piweb.session_status(coord.session)
            if status.get("isStreaming") is True:
                return coord.session, "follow-up"
            if self.warm(coord, status):
                return coord.session, None
        # A rotation that fails after its archive leaves no active coordinator.
        # The flag lets the next tick finish it instead of waiting for pi-streams rotate.
        self.state.rotating = True
        self.flush()
        sid = rotate_coordinator(self.project, self.stream)
        self.rows = load_threads(self.rows_path)
        return sid, "follow-up"

    def archive_done(self) -> None:
        for row in self.rows:
            if row.role != "coordinator" or row.status is not Status.done:
                continue
            if _working(piweb.session_status(row.session)):
                continue
            piweb.archive(row.session)
            transition(row, Status.archived)
            self.rows_dirty = True
            self.emit("archived", row)

    def warm(self, coord: Thread, status: dict[str, object]) -> bool:
        tokens = _tokens(status)
        if tokens is not None and tokens >= self.caps.warm_context_tokens:
            return False
        info = self.listing(coord.worktree).get(coord.session)
        modified = clock.parse(info.get("modified")) if info is not None else None
        return modified is not None and self.now - modified < timedelta(hours=self.caps.warm_idle_hours)


def find_claims(dirs: list[Path]) -> dict[str, list[Claim]] | None:
    held: list[tuple[str, Thread]] = []
    for stream_dir in dirs:
        try:
            rows = load_threads(stream_dir / "threads.tsv")
        except StreamsError:
            # Without every stream's rows, a claim that is not found may still hold.
            return None
        held += [(stream_dir.name, row) for row in rows if row.status is not Status.archived]
    found: dict[str, list[Claim]] = {}
    for index, (a_stream, a) in enumerate(held):
        for b_stream, b in held[index + 1 :]:
            what = _shared(a, b) if a_stream != b_stream else ""
            if what == "":
                continue
            key = f"{a_stream}/{a.session},{b_stream}/{b.session}"
            alert = f"claim {key} {a.role} and {b.role} share {what}"
            for stream, row, other_stream, other in ((a_stream, a, b_stream, b), (b_stream, b, a_stream, a)):
                detail = f"shares {what} with {other_stream} {other.role} {other.session}"
                found.setdefault(stream, []).append(Claim(key, alert, row, detail))
    return found


def _shared(a: Thread, b: Thread) -> str:
    if a.worktree != "" and a.worktree == b.worktree:
        return f"worktree {a.worktree}"
    if a.repo != "" and a.branch != "" and (a.repo, a.branch) == (b.repo, b.branch):
        return f"{a.repo} branch {a.branch}"
    return ""


def tick_home(home: Path, now: datetime) -> bool:
    ok = True
    with home_lock(home):
        project = load_project(home)
        alerts = Alerts(home / "ALERTS")
        dirs = stream_dirs(home)
        claims = find_claims(dirs)
        for stream_dir in dirs:
            mine = None if claims is None else claims.get(stream_dir.name, [])
            run = StreamTick(project, stream_dir, now, alerts, mine)
            run.run()
            for error in run.errors:
                ok = False
                print(f"{stream_dir}: {error}", file=sys.stderr, flush=True)
            counts = Counter(event.kind for event in run.events)
            if counts:
                counted = "\t".join(f"{kind}={counts[kind]}" for kind in sorted(counts))
                print(f"{stream_dir}\t{counted}", flush=True)
        alerts.save()
        commit_home(home, "pi-streams tick")
        push_home(home, project.info.remote)
    return ok


def run_tick(homes: list[Path]) -> int:
    now = clock.now()
    ok = True
    for home in homes:
        try:
            ok = tick_home(home, now) and ok
        except (StreamsError, OSError) as exc:
            ok = False
            print(f"{home}: {exc}", file=sys.stderr, flush=True)
    return 0 if ok else 1

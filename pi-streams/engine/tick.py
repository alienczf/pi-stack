from __future__ import annotations

import json
import sys
from collections import Counter
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engine import StreamsError, artifacts, clock, dcr, delivery, drive, piweb, sessionlog
from engine.project import (
    Project,
    StreamRow,
    _write as write_atomic,
    commit_repo,
    index_lock,
    load_projects,
    load_stream_config,
    load_stream_rows,
    push_repo,
    stream_locks,
)
from engine.subscriptions import SOURCES, Subscription, load_subscriptions
from engine.threads import Coordinator, Status, Thread, _native_session, load_threads, require_ratified, resolve_coordinator, save_threads, transition

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
    replay: list[list[str]] = field(default_factory=list)


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
    try:
        data = json.loads(path.read_bytes()) if path.exists() else {}
        if not isinstance(data, dict):
            raise ValueError("expected tick-state object")
    except (OSError, ValueError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc
    data.update({
        "sessions": {sid: asdict(seen) for sid, seen in state.sessions.items()},
        "pending": [asdict(event) for event in state.pending],
        "outages": state.outages,
        "rotating": state.rotating,
        "subscriptions": {sub: asdict(mark) for sub, mark in state.subscriptions.items()},
        "claims": state.claims,
    })
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
        index: Path,
        project: Project,
        stream_id: str,
        stream_dir: Path,
        now: datetime,
        alerts: Alerts,
        claims: list[Claim] | None,
    ) -> None:
        self.index = index
        self.project = project
        self.caps = project.caps
        self.stream_dir = stream_dir
        self.stream = stream_id
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
        self.coordinator_resolution: Coordinator | None = None
        self.dcr_owned = False
        self.drive_owned = False
        self.drive_enabled = False
        self.automatic_paused = False
        self.stalled = False

    def run(self) -> None:
        try:
            self.state = load_state(self.state_path)
            self.loaded = True
            self.drive_enabled = drive.load(self.stream_dir).enabled
            self.automatic_paused = drive.is_paused(self.stream_dir)
            self.rows = load_threads(self.rows_path)
            self.coordinator_resolution = resolve_coordinator(self.stream_dir, self.rows)
            if self.coordinator_resolution is not None:
                resolved = self.coordinator_resolution
                self.listings[resolved.row.worktree] = {resolved.row.session: resolved.native.info}
                self.stalled = drive.is_stalled(resolved.native.status)
            if not self.automatic_paused:
                self.dcr_owned = dcr.step(self.index, self.project, self.stream, self.stream_dir, self.coordinator_resolution)
            self.check_claims()
            self.observe()
            self.drive_owned = drive.step(self.stream_dir, self.coordinator_resolution, self.stalled, maintenance=self.dcr_owned)
            self.check_subscriptions()
            self.flush()
            self.wake()
            self.archive_done()
        except (StreamsError, OSError) as exc:
            self.fail(str(exc))
        try:
            self.flush()
        except (StreamsError, OSError) as exc:
            if str(exc) not in self.errors:
                self.errors.append(str(exc))

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
        if self.coordinator() is None:
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
        resolved = self.coordinator_resolution
        return resolved.row if resolved is not None and resolved.row.status is Status.active else None

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
        elif message is not None and self.out(row):
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
        piweb.require_identity(status, row.session)
        # A spawned thread starts on a prompt, so one first seen idle has finished it,
        # even when it did so between two ticks. An adopted thread that is already
        # idle reports idle once too, which tells its coordinator that it waits.
        old = self.state.sessions.get(row.session, Seen(busy=True))
        # The last resend stopped after queue/clear, so what is not queued now was dropped.
        # A replayed prompt starts the thread again, whatever the status said before it.
        self.stalled = self.stalled or drive.is_stalled(status)
        sent = False if self.drive_enabled or self.automatic_paused else self.replay(row, old, Counter(text for text, _kind in _queued(status)))
        new = Seen(
            busy=sent or status.get("isStreaming") is True or _count(status.get("pendingMessageCount")) > 0,
            context=old.context,
            replay=list(old.replay) if self.drive_enabled or self.automatic_paused else [],
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
        if not self.drive_enabled and not self.automatic_paused:
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
        require_ratified(self.stream_dir)
        for text in stale:
            self.emit("stale-steer", row, text)
        new.replay = [[text, "steer" if text in stale else QUEUE_FLAGS[kind]] for text, kind in queued]
        self.flush()
        # queue/clear drops every queued message, not only the stale ones.
        piweb.queue_clear(row.session)
        self.replay(row, new, Counter())
        for text in stale:
            new.queued[text] = self.at

    def replay(self, row: Thread, seen: Seen, waiting: Counter[str]) -> bool:
        if seen.replay:
            require_ratified(self.stream_dir)
        sent = False
        while seen.replay:
            text, behavior = seen.replay[0]
            if waiting[text] > 0:
                waiting[text] -= 1
            else:
                piweb.prompt(row.session, text, behavior)
                sent = True
            del seen.replay[0]
            self.flush()
        return sent

    def since(self, stamp: str) -> timedelta:
        seen = clock.parse(stamp)
        return timedelta(0) if seen is None else self.now - seen

    def wake(self) -> None:
        if self.automatic_paused or self.dcr_owned or self.drive_owned:
            return
        current = delivery.current_tick(self.stream_dir)
        if current is not None:
            if current["state"] == "applied":
                remaining = delivery.finish_tick_locked(self.stream_dir, [asdict(event) for event in self.state.pending])
                self.state.pending = [Event(**event) for event in remaining]
            else:
                if current["state"] in ("prepared", "sending"):
                    delivery.send_locked(self.stream_dir, current["id"])
                return
        coord = self.coordinator()
        if not self.state.pending or (coord is None and not self.state.rotating):
            return
        if coord is not None and self.out(coord):
            return
        require_ratified(self.stream_dir)
        text = "\n".join([f"pi-streams tick {self.at}:", *(event.line() for event in self.state.pending)])
        sid, behavior = self.wake_target(coord)
        identity = delivery.new_identity()
        delivery.prepare_locked(self.stream_dir, identity, sid, text, events=[asdict(event) for event in self.state.pending], behavior=behavior)
        delivery.send_locked(self.stream_dir, identity)
        self.state.rotating = False

    def wake_target(self, coord: Thread | None) -> tuple[str, str | None]:
        if coord is not None:
            resolved = resolve_coordinator(self.stream_dir, self.rows)
            if resolved is None or resolved.row.session != coord.session:
                raise StreamsError("coordinator designation changed before dispatch")
            status = resolved.native.status
            _automatic, allowed = piweb.automatic_admission(status, coord.session, coord.worktree, "wake")
            if not allowed:
                return coord.session, None
            if status.get("isStreaming") is True or status.get("isCompacting") is True:
                return coord.session, "follow-up"
            return coord.session, None
        raise StreamsError("no designated coordinator; explicit new/adoption or rotation recovery is required")

    def archive_done(self) -> None:
        for row in self.rows:
            if row.role != "coordinator" or row.status is not Status.done:
                continue
            listing = self.listing(row.worktree)
            info = listing.get(row.session)
            if info is not None and info.get("archived") is True:
                transition(row, Status.archived)
                self.rows_dirty = True
                continue
            status = _native_session(row.session, Path(row.worktree), list(listing.values())).status
            if _working(status):
                continue
            require_ratified(self.stream_dir)
            piweb.archive(row.session)
            transition(row, Status.archived)
            self.rows_dirty = True
            self.emit("archived", row)


def find_claims(streams: list[tuple[str, Path]]) -> dict[str, list[Claim]] | None:
    held: list[tuple[str, Thread]] = []
    for stream_id, stream_dir in streams:
        try:
            rows = load_threads(stream_dir / "threads.tsv")
        except StreamsError:
            # Without every stream's rows, a claim that is not found may still hold.
            return None
        held += [(stream_id, row) for row in rows if row.status is not Status.archived]
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


def _claims_for(group: list[StreamRow]) -> dict[str, list[Claim] | None]:
    found = find_claims([(row.id, Path(row.path)) for row in group])
    if found is None:
        return {row.id: None for row in group}
    return {row.id: found.get(row.id, []) for row in group}


def tick_index(index: Path, now: datetime) -> bool:
    ok = True
    with index_lock(index):
        projects = {project.info.name: project for project in load_projects(index)}
        rows = load_stream_rows(index)
        ordered = sorted(rows, key=lambda row: str(Path(row.path).resolve()))
        with stream_locks([Path(row.path) for row in ordered]):
            alerts = Alerts(index / "ALERTS")
            grouped: dict[str, list[StreamRow]] = {}
            for row in ordered:
                grouped.setdefault(row.project, []).append(row)
            claims = {stream_id: mine for group in grouped.values() for stream_id, mine in _claims_for(group).items()}
            runs: list[tuple[StreamRow, StreamTick]] = []
            history_paths: dict[str, list[str]] = {}
            for row in ordered:
                try:
                    history_paths[row.path] = artifacts._rotate_log_locked(Path(row.path))
                except (StreamsError, OSError) as exc:
                    ok = False
                    print(f"{row.path}: {exc}", file=sys.stderr, flush=True)
                    continue
                project = projects.get(row.project)
                if project is None:
                    ok = False
                    print(f"{row.path}: stream {row.id} names missing project {row.project}", file=sys.stderr, flush=True)
                    continue
                run = StreamTick(index, project, row.id, Path(row.path), now, alerts, claims.get(row.id))
                run.run()
                runs.append((row, run))
                for error in run.errors:
                    ok = False
                    print(f"{row.path}: {error}", file=sys.stderr, flush=True)
                counts = Counter(event.kind for event in run.events)
                if counts:
                    counted = "\t".join(f"{kind}={counts[kind]}" for kind in sorted(counts))
                    print(f"{row.path}\t{counted}", flush=True)
            for row, _run in runs:
                repo = Path(row.path)
                try:
                    commit_repo(repo, "pi-streams tick", paths=tuple(history_paths[row.path]))
                    if history_paths[row.path]:
                        artifacts._acknowledge_history_locked(repo)
                except (StreamsError, OSError) as exc:
                    ok = False
                    print(f"{row.path}: {exc}", file=sys.stderr, flush=True)
            alerts.save()
            for row, _run in runs:
                repo = Path(row.path)
                try:
                    push_repo(repo, load_stream_config(repo / "stream.toml").remote)
                except StreamsError as exc:
                    ok = False
                    print(f"{row.path}: {exc}", file=sys.stderr, flush=True)
    return ok


def run_tick(indexes: list[Path]) -> int:
    now = clock.now()
    ok = True
    for index in indexes:
        try:
            ok = tick_index(index, now) and ok
        except (StreamsError, OSError) as exc:
            ok = False
            print(f"{index}: {exc}", file=sys.stderr, flush=True)
    return 0 if ok else 1

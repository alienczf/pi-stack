from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from engine import StreamsError
from engine import piweb
from engine.project import Project, stream_dirs


class Status(enum.Enum):
    active = "active"
    waiting_quota = "waiting_quota"
    done = "done"
    archived = "archived"


# The only legal status changes.
TRANSITIONS: dict[Status, frozenset[Status]] = {
    Status.active: frozenset({Status.waiting_quota, Status.done, Status.archived}),
    Status.waiting_quota: frozenset({Status.active, Status.archived}),
    Status.done: frozenset({Status.archived}),
    Status.archived: frozenset(),
}

THREAD_COLUMNS = (
    "session",
    "role",
    "repo",
    "worktree",
    "branch",
    "base",
    "model",
    "thinking",
    "status",
    "started",
)

KICKOFF = "/skill:stream-kickoff"


@dataclass
class Thread:
    session: str
    role: str
    repo: str
    worktree: str
    branch: str
    base: str
    model: str
    thinking: str
    status: Status
    started: str


def utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def transition(row: Thread, new: Status) -> None:
    if new not in TRANSITIONS[row.status]:
        raise ValueError(f"{row.status.value} -> {new.value} is not allowed")
    row.status = new


def load_threads(path: Path) -> list[Thread]:
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc
    lines = text.splitlines()
    if not lines or tuple(lines[0].split("\t")) != THREAD_COLUMNS:
        raise StreamsError(f"{path} has an unexpected header")
    rows: list[Thread] = []
    for index, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        parts = line.split("\t")
        if len(parts) != len(THREAD_COLUMNS):
            raise StreamsError(f"{path}:{index} has {len(parts)} fields")
        try:
            status = Status(parts[8])
        except ValueError as exc:
            raise StreamsError(f"{path}:{index} has status {parts[8]}") from exc
        rows.append(
            Thread(
                session=parts[0],
                role=parts[1],
                repo=parts[2],
                worktree=parts[3],
                branch=parts[4],
                base=parts[5],
                model=parts[6],
                thinking=parts[7],
                status=status,
                started=parts[9],
            )
        )
    return rows


def save_threads(path: Path, rows: list[Thread]) -> None:
    lines = ["\t".join(THREAD_COLUMNS)]
    for row in rows:
        fields = (
            row.session,
            row.role,
            row.repo,
            row.worktree,
            row.branch,
            row.base,
            row.model,
            row.thinking,
            row.status.value,
            row.started,
        )
        for field in fields:
            if "\t" in field or "\n" in field or "\r" in field:
                raise StreamsError("a thread field contains a tab or newline")
        lines.append("\t".join(fields))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def is_ratified(text: str) -> bool:
    marker = "ratified: "
    for line in text.splitlines():
        at = line.find(marker)
        if at < 0:
            continue
        rest = line[at + len(marker) :].strip()
        value = rest.split(" ", 1)[0] if rest else ""
        return value != "" and value != "no"
    return False


def _unrecorded(cwd: Path, rows: list[Thread]) -> list[dict[str, object]]:
    known = {row.session for row in rows}
    return [
        item
        for item in piweb.list_sessions(str(cwd))
        if isinstance(item.get("id"), str) and item["id"] not in known and item.get("archived") is not True
    ]


def _resume_or_spawn(cwd: Path, rows: list[Thread]) -> tuple[str, bool]:
    # A crash after spawn leaves a listed session with no row. It needs its
    # opening prompt only if it never received one.
    found = _unrecorded(cwd, rows)
    if found:
        return str(found[0]["id"]), found[0].get("messageCount") == 0
    return piweb.spawn(str(cwd)), True


def ensure_coordinator(project: Project, stream_dir: Path, *, opening_prompt: str | None = None) -> str:
    stream_dir = stream_dir.resolve()
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    for row in rows:
        if row.role == "coordinator" and row.status is Status.active:
            return row.session
    sid, needs_opening = _resume_or_spawn(stream_dir, rows)
    piweb.configure_session(sid, project.coordinator.model, project.coordinator.thinking)
    if needs_opening:
        piweb.prompt(sid, KICKOFF if opening_prompt is None else opening_prompt)
    rows.append(
        Thread(
            session=sid,
            role="coordinator",
            repo="",
            worktree=str(stream_dir),
            branch="",
            base="",
            model=project.coordinator.model,
            thinking=project.coordinator.thinking,
            status=Status.active,
            started=utc_now(),
        )
    )
    save_threads(path, rows)
    return sid


def _as_cost(value: object) -> int | float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StreamsError("status has no cost")
    return value


def _coordinator_state(session_id: str, session: dict[str, object]) -> dict[str, object]:
    # pi reports null tokens after a compaction until the next reply.
    usage = session.get("contextUsage")
    tokens = usage.get("tokens") if isinstance(usage, dict) else None
    model = session.get("model")
    if not isinstance(model, dict) or "id" not in model:
        raise StreamsError("status has no model id")
    if "isStreaming" not in session or "thinkingLevel" not in session or "cost" not in session:
        raise StreamsError("status is missing a coordinator field")
    return {
        "session": session_id,
        "isStreaming": session["isStreaming"],
        "contextUsage": {"tokens": tokens},
        "model": model["id"],
        "thinkingLevel": session["thinkingLevel"],
        "cost": _as_cost(session["cost"]),
    }


def _one_stream(stream_dir: Path) -> dict[str, object]:
    text = (stream_dir / "STREAM.md").read_text(encoding="utf-8")
    rows = load_threads(stream_dir / "threads.tsv")
    counts = {name: 0 for name in ("active", "waiting_quota", "done", "archived")}
    coord: Thread | None = None
    threads: list[Thread] = []
    for row in rows:
        if row.role == "coordinator":
            if coord is None and row.status is Status.active:
                coord = row
            continue
        counts[row.status.value] += 1
        threads.append(row)
    coord_cost: int | float = 0
    coord_state: dict[str, object] | None = None
    if coord is not None:
        session = piweb.session_status(coord.session)
        coord_state = _coordinator_state(coord.session, session)
        coord_cost = _as_cost(session["cost"])
    # pi-web opens a runtime to answer status for an idle session, so finished
    # threads are counted but not queried.
    thread_cost: int | float = 0
    for row in threads:
        if row.status not in (Status.active, Status.waiting_quota):
            continue
        session = piweb.session_status(row.session)
        thread_cost += _as_cost(session.get("cost"))
    share = None if thread_cost == 0 else coord_cost / thread_cost
    return {
        "id": stream_dir.name,
        "ratified": is_ratified(text),
        "coordinator": coord_state,
        "threads": counts,
        "coordinatorCostShare": share,
    }


def status_report(project: Project, stream_id: str | None) -> dict[str, object]:
    dirs = stream_dirs(Path(project.info.home))
    if stream_id is not None:
        dirs = [path for path in dirs if path.name == stream_id]
        if not dirs:
            raise StreamsError(f"no stream {stream_id}")
    return {"streams": [_one_stream(path) for path in dirs]}


def format_status(report: dict[str, object]) -> str:
    streams = report["streams"]
    if not isinstance(streams, list) or not streams:
        return "no streams\n"
    lines: list[str] = []
    for stream in streams:
        if not isinstance(stream, dict):
            continue
        counts = stream["threads"]
        if not isinstance(counts, dict):
            continue
        counted = ",".join(f"{name}={counts[name]}" for name in ("active", "waiting_quota", "done", "archived"))
        share = stream["coordinatorCostShare"]
        share_text = "-" if share is None else str(share)
        ratified = "yes" if stream["ratified"] else "no"
        coord = stream["coordinator"]
        if not isinstance(coord, dict):
            lines.append(f"{stream['id']}\tratified={ratified}\t-\tthreads={counted}\tshare={share_text}")
            continue
        usage = coord["contextUsage"]
        tokens = usage.get("tokens") if isinstance(usage, dict) else None
        if tokens is None:
            tokens = "-"
        streaming = "yes" if coord["isStreaming"] else "no"
        lines.append(
            f"{stream['id']}\tratified={ratified}\t{coord['session']}\tstreaming={streaming}\t"
            f"tokens={tokens}\tmodel={coord['model']}\tthinking={coord['thinkingLevel']}\t"
            f"cost={coord['cost']}\tthreads={counted}\tshare={share_text}"
        )
    return "\n".join(lines) + "\n"

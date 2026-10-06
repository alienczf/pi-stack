from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path

from engine import StreamsError, clock, repo_root
from engine import piweb
from engine.project import STREAM_ID, Project, Repo, git, stream_dirs

_ROLE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class Status(enum.Enum):
    active = "active"
    waiting_quota = "waiting_quota"
    done = "done"
    archived = "archived"


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
    return clock.stamp(clock.now())


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


def render_brief(
    *,
    stream: str,
    stream_dir: str,
    role: str,
    repo: str,
    worktree: str,
    branch: str,
    base: str,
    note: str,
) -> str:
    text = (repo_root() / "pi-streams" / "templates" / "thread-brief.md").read_text(encoding="utf-8")
    values = {
        "stream": stream,
        "stream_dir": stream_dir,
        "role": role,
        "repo": repo,
        "worktree": worktree,
        "branch": branch,
        "base": base,
        "note": note,
    }
    for key, value in values.items():
        text = text.replace("{" + key + "}", value)
    return text


def _common_dir(path: Path) -> Path:
    raw = git(path, "rev-parse", "--git-common-dir").strip()
    common = Path(raw)
    if not common.is_absolute():
        common = (path / common).resolve()
    return common.resolve()


def ensure_stream_exclude(worktree: Path) -> None:
    exclude = _common_dir(worktree) / "info" / "exclude"
    exclude.parent.mkdir(parents=True, exist_ok=True)
    line = "/.stream"
    existing = exclude.read_text(encoding="utf-8") if exclude.is_file() else ""
    if line in existing.splitlines():
        return
    if existing and not existing.endswith("\n"):
        existing += "\n"
    exclude.write_text(existing + line + "\n", encoding="utf-8", newline="\n")


def write_stream_pointer(worktree: Path, stream_dir: Path) -> None:
    (worktree / ".stream").write_text(str(stream_dir.resolve()) + "\n", encoding="utf-8", newline="\n")


def _repo_named(project: Project, name: str) -> Repo:
    for repo in project.repos:
        if repo.name == name:
            return repo
    raise StreamsError(f"no repo {name}")


def repo_for_worktree(project: Project, worktree: Path) -> Repo:
    common = _common_dir(worktree)
    for repo in project.repos:
        if _common_dir(Path(repo.path)) == common:
            return repo
    raise StreamsError(f"no repo matches {worktree}")


def _outside_repos(path: Path, project: Project) -> None:
    resolved = path.resolve()
    for repo in project.repos:
        parents = [Path(repo.path), *[Path(item.path) for item in repo.worktrees]]
        for parent in parents:
            parent_resolved = parent.resolve()
            if resolved == parent_resolved or parent_resolved in resolved.parents:
                raise StreamsError(f"worktree {resolved} is inside {repo.name}")


def _require_role(role: str) -> None:
    if _ROLE.fullmatch(role) is None:
        raise StreamsError(f"invalid role: {role}")


def _require_stream(project: Project, stream_id: str) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    stream_dir = (Path(project.info.home) / stream_id).resolve()
    if not (stream_dir / "threads.tsv").is_file():
        raise StreamsError(f"no stream {stream_id}")
    return stream_dir


def _append_thread(path: Path, row: Thread) -> None:
    rows = load_threads(path)
    if any(item.session == row.session for item in rows):
        raise StreamsError(f"session {row.session} is already recorded")
    rows.append(row)
    save_threads(path, rows)


def spawn_thread(
    project: Project,
    stream_id: str,
    repo_name: str,
    role: str,
    *,
    base: str | None,
    branch: str | None,
    model: str | None,
    thinking: str | None,
    note: str,
) -> str:
    _require_role(role)
    stream_dir = _require_stream(project, stream_id)
    repo = _repo_named(project, repo_name)
    repo_path = Path(repo.path)
    base_ref = "HEAD" if base is None else base
    sha = git(repo_path, "rev-parse", "--verify", f"{base_ref}^{{commit}}").strip()
    branch_name = f"stream/{stream_id}/{role}" if branch is None else branch
    model_name = project.threads.model if model is None else model
    thinking_level = project.threads.thinking if thinking is None else thinking
    piweb.split_model(model_name)
    worktree = (Path(project.info.worktrees_dir) / repo.name / f"{stream_id}-{role}").resolve()
    _outside_repos(worktree, project)
    rows_path = stream_dir / "threads.tsv"
    rows = load_threads(rows_path)
    if worktree.exists():
        pointer = worktree / ".stream"
        marker = pointer.read_text(encoding="utf-8").strip() if pointer.is_file() else ""
        if marker != str(stream_dir):
            raise StreamsError(f"worktree {worktree} is not stream {stream_id}")
        ensure_stream_exclude(worktree)
        earlier = [row for row in rows if row.worktree == str(worktree)]
        for row in earlier:
            if row.status is not Status.archived:
                return row.session
        branch_name = git(worktree, "branch", "--show-current").strip()
        if earlier:
            sha = earlier[-1].base
    else:
        worktree.parent.mkdir(parents=True, exist_ok=True)
        git(repo_path, "worktree", "add", "-b", branch_name, str(worktree), sha)
        write_stream_pointer(worktree, stream_dir)
        ensure_stream_exclude(worktree)
    sid, needs_brief = _resume_or_spawn(worktree, rows)
    piweb.configure_session(sid, model_name, thinking_level)
    if needs_brief:
        piweb.prompt(
            sid,
            render_brief(
                stream=stream_id,
                stream_dir=str(stream_dir),
                role=role,
                repo=repo.name,
                worktree=str(worktree),
                branch=branch_name,
                base=sha,
                note=note,
            ),
        )
    _append_thread(
        rows_path,
        _thread_row(sid, role, repo.name, worktree, branch_name, sha, model_name, thinking_level),
    )
    return sid


def rotate_coordinator(project: Project, stream_id: str) -> str:
    stream_dir = _require_stream(project, stream_id)
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    coordinators = [row for row in rows if row.role == "coordinator"]
    if not coordinators:
        raise StreamsError(f"stream {stream_id} has no coordinator; run pi-streams new {stream_id}")
    active = [row for row in coordinators if row.status is Status.active]
    for row in active:
        piweb.archive(row.session)
        transition(row, Status.archived)
    save_threads(path, rows)
    prompt = (
        f"You are the new coordinator for stream {stream_id}. "
        "Your memory is the files in this folder. Read STATE.md, then continue."
    )
    return ensure_coordinator(project, stream_dir, opening_prompt=prompt)


def _has_handover(stream_dir: Path, role: str) -> bool:
    path = stream_dir / "handover" / f"{role}.md"
    return path.is_file() and path.read_text(encoding="utf-8").strip() != ""


def close_stream(project: Project, stream_id: str) -> list[str]:
    stream_dir = _require_stream(project, stream_id)
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    open_threads = [row for row in rows if row.role != "coordinator" and row.status is not Status.archived]
    missing = [f"handover/{row.role}.md" for row in open_threads if not _has_handover(stream_dir, row.role)]
    if missing:
        raise StreamsError(f"stream {stream_id} has no " + ", ".join(missing))
    report: list[str] = []
    for row in open_threads:
        piweb.archive(row.session)
        transition(row, Status.archived)
        save_threads(path, rows)
        report.append(f"archived {row.session} {row.role}")
    # pi-web refuses to archive a session that is still working, and the
    # coordinator is usually the one running close.
    for row in rows:
        if row.role == "coordinator" and row.status is Status.active:
            transition(row, Status.done)
            report.append(f"done {row.session} coordinator")
    save_threads(path, rows)
    return report


def adopt_thread(
    project: Project,
    stream_id: str,
    session_id: str,
    worktree: Path,
    role: str,
) -> str:
    _require_role(role)
    stream_dir = _require_stream(project, stream_id)
    worktree = worktree.expanduser().resolve()
    if not worktree.is_dir():
        raise StreamsError(f"worktree is not a directory: {worktree}")
    listed = [item for item in piweb.list_sessions(str(worktree)) if item.get("id") == session_id]
    if not listed:
        raise StreamsError(f"session {session_id} is not in {worktree}")
    if listed[0].get("archived") is True:
        raise StreamsError(f"session {session_id} is archived")
    branch = git(worktree, "branch", "--show-current").strip()
    if branch == "":
        raise StreamsError(f"{worktree} has no branch")
    repo = repo_for_worktree(project, worktree)
    session = piweb.session_status(session_id)
    raw = session.get("model")
    thinking = session.get("thinkingLevel")
    if not isinstance(raw, dict) or not isinstance(raw.get("provider"), str) or not isinstance(raw.get("id"), str):
        raise StreamsError("status has no model provider/id")
    if not isinstance(thinking, str) or thinking == "":
        raise StreamsError("status has no thinkingLevel")
    model = f"{raw['provider']}/{raw['id']}"
    sha = git(worktree, "rev-parse", "HEAD").strip()
    write_stream_pointer(worktree, stream_dir)
    ensure_stream_exclude(worktree)
    _append_thread(
        stream_dir / "threads.tsv",
        _thread_row(session_id, role, repo.name, worktree, branch, sha, model, thinking),
    )
    return session_id


def _thread_row(
    sid: str,
    role: str,
    repo: str,
    worktree: Path,
    branch: str,
    base: str,
    model: str,
    thinking: str,
) -> Thread:
    return Thread(
        session=sid,
        role=role,
        repo=repo,
        worktree=str(worktree),
        branch=branch,
        base=base,
        model=model,
        thinking=thinking,
        status=Status.active,
        started=utc_now(),
    )

from __future__ import annotations

import enum
import hashlib
import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path

from engine import StreamsError, clock, repo_root
from engine import artifacts, piweb
from engine.project import STATE_SCHEMA, Project, Repo, _write, git, load_stream_config, require_stream, stream_rows

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


@dataclass(frozen=True)
class CloseResult:
    report: tuple[str, ...]
    handovers: tuple[str, ...]


@dataclass(frozen=True)
class NativeSession:
    info: dict[str, object]
    status: dict[str, object]


@dataclass(frozen=True)
class Coordinator:
    row: Thread
    native: NativeSession


@dataclass
class SessionStart:
    session: str
    cwd: str
    role: str
    intent: str
    phase: str = "created"


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
    if len({row.session for row in rows}) != len(rows):
        raise StreamsError(f"{path} has duplicate session IDs")
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
    _write(path, "\n".join(lines) + "\n")


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


def designated_coordinator(rows: list[Thread]) -> Thread | None:
    active = [row for row in rows if row.role == "coordinator" and row.status is Status.active]
    if len(active) > 1:
        raise StreamsError("multiple active coordinator designations; explicit reconciliation required")
    return active[0] if active else None


def _native_session(session_id: str, cwd: Path, listing: list[dict[str, object]] | None = None) -> NativeSession:
    items = piweb.list_sessions(str(cwd)) if listing is None else listing
    matches = [item for item in items if item.get("id") == session_id]
    if len(matches) != 1:
        raise StreamsError(f"session {session_id} has no unique exact native identity for cwd {cwd}")
    info = matches[0]
    native_cwd = info.get("cwd")
    if not isinstance(native_cwd, str) or Path(native_cwd).resolve() != cwd.resolve():
        raise StreamsError(f"session {session_id} native cwd does not match {cwd}")
    if info.get("archived") is True:
        raise StreamsError(f"session {session_id} is archived; refusing to reopen it through status")
    status = piweb.session_status(session_id)
    piweb.require_identity(status, session_id)
    return NativeSession(info, status)


def resolve_coordinator(stream_dir: Path, rows: list[Thread] | None = None) -> Coordinator | None:
    rows = load_threads(stream_dir / "threads.tsv") if rows is None else rows
    row = designated_coordinator(rows)
    if row is None:
        return None
    if Path(row.worktree).resolve() != stream_dir.resolve():
        raise StreamsError(f"coordinator {row.session} registry cwd does not match {stream_dir}")
    listing = piweb.list_sessions(str(stream_dir))
    retired = {item.session for item in rows if item.role == "coordinator" and item.status is Status.archived}
    for item in listing:
        if item.get("id") in retired and item.get("archived") is not True:
            raise StreamsError(f"archived coordinator {item['id']} is still live in the native listing")
    known = {item.session for item in rows if item.role == "coordinator"}
    unregistered = [
        item for item in listing
        if item.get("archived") is not True and item.get("id") not in known
        and (not isinstance(item.get("cwd"), str) or Path(item["cwd"]).resolve() == stream_dir.resolve())
    ]
    if unregistered:
        raise StreamsError("unregistered coordinator candidate; explicit adoption or reconciliation required")
    return Coordinator(row, _native_session(row.session, stream_dir, listing))


def _start_record(stream_dir: Path) -> SessionStart | None:
    raw = artifacts._read_tick_data(stream_dir).get("session_start")
    if raw is None:
        return None
    try:
        start = SessionStart(**raw)
        if not all(isinstance(value, str) and value for value in asdict(start).values()):
            raise ValueError("empty or non-string start field")
        if start.phase not in ("created", "sending", "accepted"):
            raise ValueError("unknown start phase")
        return start
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid saved session start: {exc}") from exc


def _save_start(stream_dir: Path, start: SessionStart | None) -> None:
    data = artifacts._read_tick_data(stream_dir)
    if start is None:
        data.pop("session_start", None)
    else:
        data["session_start"] = asdict(start)
    artifacts._save_tick_data(stream_dir, data)


def _send_start(stream_dir: Path, session_id: str, prompt: str) -> None:
    start = _start_record(stream_dir)
    if start is None or start.session != session_id or start.phase != "created":
        raise StreamsError("saved session start is not ready for opening")
    start.phase = "sending"
    _save_start(stream_dir, start)
    try:
        piweb.prompt(session_id, prompt)
    except piweb.PromptRejected:
        start.phase = "created"
        _save_start(stream_dir, start)
        raise
    _accept_start(stream_dir, session_id)


def _accept_start(stream_dir: Path, session_id: str) -> None:
    start = _start_record(stream_dir)
    if start is None or start.session != session_id:
        raise StreamsError("saved session start identity changed")
    start.phase = "accepted"
    _save_start(stream_dir, start)


def _resume_or_spawn(cwd: Path, rows: list[Thread], stream_dir: Path, role: str, intent: list[str]) -> tuple[str, bool]:
    digest = hashlib.sha256(json.dumps(intent, ensure_ascii=False).encode()).hexdigest()
    start = _start_record(stream_dir)
    if start is not None:
        if (start.cwd, start.role, start.intent) != (str(cwd), role, digest):
            raise StreamsError("another or changed session start is pending; refusing uncertain adoption")
        if start.phase == "sending":
            raise StreamsError(f"opening acceptance for {start.session} is uncertain; refusing replay")
        native = _native_session(start.session, cwd)
        if start.phase == "accepted":
            return start.session, False
        busy = any(native.status.get(key) is True for key in ("isStreaming", "isCompacting", "isBashRunning"))
        if native.info.get("messageCount") != 0 or busy or native.status.get("pendingMessageCount", 0) != 0:
            raise StreamsError(f"opening acceptance for {start.session} is uncertain; refusing replay")
        return start.session, True
    listing = piweb.list_sessions(str(cwd))
    known = {row.session for row in rows}
    if any(item.get("archived") is not True and item.get("id") not in known for item in listing):
        raise StreamsError("unregistered native session; use explicit adoption, not directory-based recovery")
    sid = piweb.spawn(str(cwd))
    _save_start(stream_dir, SessionStart(sid, str(cwd), role, digest))
    return sid, True


def _adopt_coordinator(project: Project, stream_dir: Path, rows: list[Thread], session_id: str) -> str:
    if _start_record(stream_dir) is not None:
        raise StreamsError("a saved session start is pending; reconcile it before explicit adoption")
    listing = piweb.list_sessions(str(stream_dir))
    selected = _native_session(session_id, stream_dir, listing)
    piweb.require_settings(selected.status, project.coordinator.model, project.coordinator.thinking)
    known = {row.session for row in rows if row.role == "coordinator"} | {session_id}
    if any(item.get("archived") is not True and item.get("id") not in known for item in listing):
        raise StreamsError("unregistered coordinator candidates remain ambiguous")
    for row in rows:
        if row.session == session_id:
            if row.role == "coordinator" and row.status is Status.active:
                return resolve_coordinator(stream_dir, rows).row.session
            raise StreamsError("selected session is already recorded with an inactive or different role")
        if row.role == "coordinator" and row.status is Status.active:
            matches = [item for item in listing if item.get("id") == row.session]
            if len(matches) != 1 or matches[0].get("archived") is not True:
                raise StreamsError("existing coordinator is not proven retired; use explicit safe replacement")
            transition(row, Status.archived)
    rows.append(_thread_row(session_id, "coordinator", "", stream_dir, "", "", project.coordinator.model, project.coordinator.thinking))
    save_threads(stream_dir / "threads.tsv", rows)
    return session_id


def ensure_coordinator(project: Project, stream_dir: Path, *, opening_prompt: str | None = None, coordinator_session: str | None = None) -> str:
    stream_dir = stream_dir.resolve()
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    if coordinator_session is not None:
        return _adopt_coordinator(project, stream_dir, rows, coordinator_session)
    if designated_coordinator(rows) is not None:
        resolved = resolve_coordinator(stream_dir, rows)
        start = _start_record(stream_dir)
        if start is not None:
            if start.session != resolved.row.session or start.phase != "accepted":
                raise StreamsError("registry and saved session start disagree")
            _save_start(stream_dir, None)
        return resolved.row.session
    prompt = KICKOFF if opening_prompt is None else opening_prompt
    sid, needs_opening = _resume_or_spawn(stream_dir, rows, stream_dir, "coordinator", [project.coordinator.model, project.coordinator.thinking, prompt])
    if needs_opening:
        piweb.configure_session(sid, project.coordinator.model, project.coordinator.thinking)
        _send_start(stream_dir, sid, prompt)
    rows.append(_thread_row(sid, "coordinator", "", stream_dir, "", "", project.coordinator.model, project.coordinator.thinking))
    save_threads(path, rows)
    _save_start(stream_dir, None)
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


def _canonical_stream(stream_dir: Path) -> bool:
    path = stream_dir / "stream.toml"
    return path.is_file() and load_stream_config(path).state_schema == STATE_SCHEMA


def _one_stream(stream_id: str, stream_dir: Path) -> dict[str, object]:
    canonical = _canonical_stream(stream_dir)
    if canonical:
        state = artifacts.read_stream_state(stream_dir)
        ratified = _has_ratified_authority(state)
    else:
        ratified = is_ratified((stream_dir / "STREAM.md").read_text(encoding="utf-8"))
    rows = load_threads(stream_dir / "threads.tsv")
    counts = {name: 0 for name in ("active", "waiting_quota", "done", "archived")}
    coordinator = resolve_coordinator(stream_dir, rows)
    if coordinator is None:
        raise StreamsError(f"stream {stream_id} has no designated active coordinator")
    threads: list[Thread] = []
    for row in rows:
        if row.role == "coordinator":
            continue
        counts[row.status.value] += 1
        threads.append(row)
    session = coordinator.native.status
    coord_state = _coordinator_state(coordinator.row.session, session)
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
    result = {
        "id": stream_id,
        "ratified": ratified,
        "coordinator": coord_state,
        "threads": counts,
        "coordinatorCostShare": share,
    }
    if canonical:
        result["path"] = str(stream_dir)
        result["threadSessions"] = [
            {"session": row.session, "role": row.role, "worktree": row.worktree, "status": row.status.value}
            for row in threads
        ]
    return result


def status_report(index: Path, stream_id: str | None) -> dict[str, object]:
    rows = stream_rows(index, stream_id)
    return {"streams": [_one_stream(row.id, Path(row.path)) for row in rows]}


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


def handover_path(role: str, session_id: str) -> Path:
    _require_role(role)
    if _ROLE.fullmatch(session_id) is None:
        raise StreamsError(f"invalid handover session: {session_id}")
    return Path("handover") / role / f"{session_id}.md"


def render_brief(
    *,
    session_id: str,
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
        "session_id": session_id,
        "handover": str(Path(stream_dir) / handover_path(role, session_id)),
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


def _require_worker_role(role: str) -> None:
    _require_role(role)
    if role == "coordinator":
        raise StreamsError("coordinator is a reserved worker role")


def _has_ratified_authority(state: artifacts.StreamState) -> bool:
    authority = state.source[state.authority.start:state.authority.end].decode("utf-8")
    words = authority.partition(":")[2].split()
    normalized = [word.lower() for word in words]
    return bool(normalized) and normalized[0] not in ("no", "false", "unratified") and normalized not in (["yes"], ["true"])


def require_ratified(stream_dir: Path) -> None:
    state = artifacts._read_stream_state_locked(stream_dir)
    if not _has_ratified_authority(state):
        raise StreamsError("STATE Goals is unratified or has no source-backed authority; no worker or automatic dispatch is authorized")


def _require_stream(index: Path, project: Project, stream_id: str) -> Path:
    return require_stream(index, project.info.name, stream_id)


def _append_thread(path: Path, row: Thread) -> None:
    rows = load_threads(path)
    if any(item.session == row.session for item in rows):
        raise StreamsError(f"session {row.session} is already recorded")
    rows.append(row)
    save_threads(path, rows)


def spawn_thread(
    index: Path,
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
    _require_worker_role(role)
    stream_dir = _require_stream(index, project, stream_id)
    require_ratified(stream_dir)
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
                start = _start_record(stream_dir)
                if start is not None:
                    if start.session != row.session or start.phase != "accepted":
                        raise StreamsError("worker registry and saved session start disagree")
                    _save_start(stream_dir, None)
                return row.session
        branch_name = git(worktree, "branch", "--show-current").strip()
        if earlier:
            sha = earlier[-1].base
    else:
        worktree.parent.mkdir(parents=True, exist_ok=True)
        git(repo_path, "worktree", "add", "-b", branch_name, str(worktree), sha)
        write_stream_pointer(worktree, stream_dir)
        ensure_stream_exclude(worktree)
    sid, needs_brief = _resume_or_spawn(worktree, rows, stream_dir, role, [repo.name, branch_name, sha, model_name, thinking_level, note])
    if needs_brief:
        piweb.configure_session(sid, model_name, thinking_level)
        _send_start(
            stream_dir,
            sid,
            render_brief(
                session_id=sid,
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
    _save_start(stream_dir, None)
    return sid


def rotate_coordinator(index: Path, project: Project, stream_id: str) -> str:
    stream_dir = _require_stream(index, project, stream_id)
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    coordinators = [row for row in rows if row.role == "coordinator"]
    if not coordinators:
        raise StreamsError(f"stream {stream_id} has no coordinator; run pi-streams new {stream_id}")
    prompt = (
        f"You are the new coordinator for stream {stream_id}. "
        "Your memory is the files in this folder. Read STATE.md, then continue."
    )
    if _canonical_stream(stream_dir):
        state = artifacts._read_stream_state_locked(stream_dir)
        goal = artifacts.resolve_current_goal(state)
        prompt = (
            f"You are the new coordinator for stream {stream_id}. "
            f"Read {stream_dir}/AGENTS.md and {stream_dir}/STATE.md before acting. "
            "Use Goals' current objective, falling back to North Star. Current Goals and Rules take precedence. "
            "Open history/, context/, checks/, and handover/ only on demand. "
            f"Goal at pickup:\n{goal}"
        )
    resolved = resolve_coordinator(stream_dir, rows)
    active = [resolved.row] if resolved is not None else []
    for row in active:
        piweb.archive(row.session)
        transition(row, Status.archived)
    save_threads(path, rows)
    return ensure_coordinator(project, stream_dir, opening_prompt=prompt)


def _validated_handover(stream_dir: Path, row: Thread) -> str:
    canonical = handover_path(row.role, row.session)
    for relative in (canonical, Path("handover") / f"{row.role}.md"):
        path = stream_dir
        for part in relative.parts:
            path = path / part
            if path.is_symlink():
                raise StreamsError(f"refusing handover symlink: {relative}")
        if not path.exists():
            continue
        if not path.is_file():
            raise StreamsError(f"handover is not a regular file: {relative}")
        try:
            data = path.read_bytes()
            lines = data.decode("utf-8").splitlines()
        except (OSError, UnicodeError) as exc:
            raise StreamsError(f"could not read handover {relative}: {exc}") from exc
        if (b"\x00" in data or not lines or lines[0] != f"session: {row.session}"
                or not any(line.strip() for line in lines[1:])):
            raise StreamsError(
                f"handover {relative} must start with 'session: {row.session}' and contain a nonempty UTF-8 body"
            )
        return relative.as_posix()
    raise StreamsError(f"missing handover for session {row.session}: {canonical}")


def close_stream(index: Path, project: Project, stream_id: str) -> CloseResult:
    stream_dir = _require_stream(index, project, stream_id)
    path = stream_dir / "threads.tsv"
    rows = load_threads(path)
    open_threads = [row for row in rows if row.role != "coordinator" and row.status is not Status.archived]
    handovers: list[str] = []
    for row in rows:
        if row.role == "coordinator":
            continue
        try:
            relative = _validated_handover(stream_dir, row)
        except StreamsError:
            if row.status is not Status.archived:
                raise
            continue
        # A busy close may already have archived this worker without committing its evidence.
        handovers.append(relative)
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
    return CloseResult(tuple(report), tuple(handovers))


def adopt_thread(
    index: Path,
    project: Project,
    stream_id: str,
    session_id: str,
    worktree: Path,
    role: str,
) -> str:
    _require_worker_role(role)
    stream_dir = _require_stream(index, project, stream_id)
    require_ratified(stream_dir)
    worktree = worktree.expanduser().resolve()
    if not worktree.is_dir():
        raise StreamsError(f"worktree is not a directory: {worktree}")
    native = _native_session(session_id, worktree)
    branch = git(worktree, "branch", "--show-current").strip()
    if branch == "":
        raise StreamsError(f"{worktree} has no branch")
    repo = repo_for_worktree(project, worktree)
    session = native.status
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

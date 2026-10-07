from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from collections.abc import Iterator
from dataclasses import dataclass, field
from pathlib import Path

from engine import StreamsError, repo_root

DEFAULT_MODEL = "openai-codex/gpt-6-astra"
DEFAULT_THINKING = "xhigh"
DEFAULT_PI_WEB_URL = "http://127.0.0.1:8504"
STREAM_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
PROJECT_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")
STREAM_COLUMNS = ("id", "path", "project")
PROTECTED_STREAM_FILES = frozenset({"STREAM.md", "STATE.md", "DECISIONS.md", "threads.tsv"})


@dataclass
class Worktree:
    path: str
    branch: str


@dataclass
class Repo:
    name: str
    path: str
    worktrees: list[Worktree] = field(default_factory=list)


@dataclass
class ProjectSection:
    name: str
    root: str
    pi_web_url: str
    worktrees_dir: str
    pi_stack_revision: str


@dataclass
class ModelSettings:
    model: str
    thinking: str


@dataclass
class Caps:
    warm_context_tokens: int = 60000
    warm_idle_hours: int = 6
    thread_handover_tokens: int = 150000
    steer_queue_minutes: int = 10


@dataclass
class Project:
    info: ProjectSection
    coordinator: ModelSettings
    threads: ModelSettings
    caps: Caps
    repos: list[Repo]


@dataclass
class StreamRow:
    id: str
    path: str
    project: str


@dataclass
class StreamConfig:
    project: str
    pi_stack_revision: str
    remote: str = ""


def _q(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def dump_project(project: Project) -> str:
    info = project.info
    caps = project.caps
    lines = [
        "[project]",
        f"name = {_q(info.name)}",
        f"root = {_q(info.root)}",
        f"pi_web_url = {_q(info.pi_web_url)}",
        f"worktrees_dir = {_q(info.worktrees_dir)}",
        f"pi_stack_revision = {_q(info.pi_stack_revision)}",
        "",
        "[coordinator]",
        f"model = {_q(project.coordinator.model)}",
        f"thinking = {_q(project.coordinator.thinking)}",
        "",
        "[threads]",
        f"model = {_q(project.threads.model)}",
        f"thinking = {_q(project.threads.thinking)}",
        "",
        "[caps]",
        f"warm_context_tokens = {caps.warm_context_tokens}",
        f"warm_idle_hours = {caps.warm_idle_hours}",
        f"thread_handover_tokens = {caps.thread_handover_tokens}",
        f"steer_queue_minutes = {caps.steer_queue_minutes}",
        "",
    ]
    for repo in project.repos:
        lines.append("[[repos]]")
        lines.append(f"name = {_q(repo.name)}")
        lines.append(f"path = {_q(repo.path)}")
        lines.append("worktrees = [")
        for item in repo.worktrees:
            lines.append(f"  {{ path = {_q(item.path)}, branch = {_q(item.branch)} }},")
        lines.append("]")
        lines.append("")
    return "\n".join(lines)


def dump_stream_config(config: StreamConfig) -> str:
    lines = [
        f"project = {_q(config.project)}",
        f"pi_stack_revision = {_q(config.pi_stack_revision)}",
    ]
    if config.remote != "":
        lines.append(f"remote = {_q(config.remote)}")
    return "\n".join(lines) + "\n"


def _repo_from_toml(item: object) -> Repo:
    if not isinstance(item, dict):
        raise StreamsError("project file repo entry is not a table")
    worktrees: list[Worktree] = []
    for raw in item["worktrees"]:
        if not isinstance(raw, dict):
            raise StreamsError("project file worktree entry is not a table")
        worktrees.append(Worktree(path=str(raw["path"]), branch=str(raw["branch"])))
    return Repo(name=str(item["name"]), path=str(item["path"]), worktrees=worktrees)


def load_project(path: Path) -> Project:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise StreamsError(f"{path.name}: {exc}") from exc
    try:
        info = data["project"]
        coordinator = data["coordinator"]
        threads = data["threads"]
        caps = data["caps"]
        name = str(info["name"])
        project = Project(
            info=ProjectSection(
                name=name,
                root=str(info["root"]),
                pi_web_url=str(info["pi_web_url"]),
                worktrees_dir=str(info["worktrees_dir"]),
                pi_stack_revision=str(info["pi_stack_revision"]),
            ),
            coordinator=ModelSettings(str(coordinator["model"]), str(coordinator["thinking"])),
            threads=ModelSettings(str(threads["model"]), str(threads["thinking"])),
            caps=Caps(
                warm_context_tokens=int(caps["warm_context_tokens"]),
                warm_idle_hours=int(caps["warm_idle_hours"]),
                thread_handover_tokens=int(caps["thread_handover_tokens"]),
                steer_queue_minutes=int(caps["steer_queue_minutes"]),
            ),
            repos=[_repo_from_toml(item) for item in data.get("repos", [])],
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StreamsError(f"{path.name}: {exc}") from exc
    if path.stem != name:
        raise StreamsError(f"{path.name}: name is {name}")
    return project


def project_file(index: Path, name: str) -> Path:
    return index / "projects" / f"{name}.toml"


def save_project(index: Path, project: Project) -> None:
    path = project_file(index, project.info.name)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(dump_project(project), encoding="utf-8", newline="\n")


def load_projects(index: Path) -> list[Project]:
    directory = index / "projects"
    if not directory.is_dir():
        return []
    return [load_project(path) for path in sorted(directory.glob("*.toml"))]


def load_stream_config(path: Path) -> StreamConfig:
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc
    try:
        remote = data.get("remote", "")
        config = StreamConfig(
            project=str(data["project"]),
            pi_stack_revision=str(data["pi_stack_revision"]),
            remote=str(remote),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc
    return config


def save_stream_config(repo: Path, config: StreamConfig) -> None:
    (repo / "stream.toml").write_text(dump_stream_config(config), encoding="utf-8", newline="\n")


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(f".{path.name}.tmp")
    try:
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp, path)
    finally:
        tmp.unlink(missing_ok=True)


def load_stream_rows(index: Path) -> list[StreamRow]:
    path = index / "streams.tsv"
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc
    if not lines:
        return []
    if tuple(lines[0].split("\t")) != STREAM_COLUMNS:
        raise StreamsError(f"{path} has an unexpected header")
    rows: list[StreamRow] = []
    for number, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        parts = line.split("\t")
        if len(parts) != len(STREAM_COLUMNS):
            raise StreamsError(f"{path}:{number} has {len(parts)} fields")
        rows.append(StreamRow(id=parts[0], path=parts[1], project=parts[2]))
    return rows


def save_stream_rows(index: Path, rows: list[StreamRow]) -> None:
    lines = ["\t".join(STREAM_COLUMNS)]
    for row in rows:
        for value in (row.id, row.path, row.project):
            if "\t" in value or "\n" in value or "\r" in value:
                raise StreamsError("a stream field contains a tab or newline")
        lines.append(f"{row.id}\t{row.path}\t{row.project}")
    _write(index / "streams.tsv", "\n".join(lines) + "\n")


def upsert_stream_row(index: Path, row: StreamRow) -> None:
    rows = [item for item in load_stream_rows(index) if not (item.id == row.id and item.project == row.project)]
    rows.append(row)
    rows.sort(key=lambda item: (item.project, item.id))
    save_stream_rows(index, rows)


def _git_env() -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    return env


def git(cwd: Path, *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", os.fspath(cwd), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_git_env(),
        check=False,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"git {args[0]} failed"
        raise StreamsError(detail)
    return proc.stdout


def pi_stack_revision() -> str:
    return git(repo_root(), "rev-parse", "HEAD").strip()


def _parse_worktrees(repo: Path, text: str) -> list[Worktree]:
    found: list[Worktree] = []
    current_path: str | None = None
    current_branch: str | None = None

    def flush() -> None:
        nonlocal current_path, current_branch
        if current_path is None:
            return
        path = Path(current_path).resolve()
        if path != repo.resolve():
            branch = current_branch or ""
            prefix = "refs/heads/"
            if branch.startswith(prefix):
                branch = branch[len(prefix) :]
            found.append(Worktree(path=str(path), branch=branch))
        current_path = None
        current_branch = None

    for line in text.splitlines():
        if line.startswith("worktree "):
            flush()
            current_path = line[len("worktree ") :]
        elif line.startswith("branch "):
            current_branch = line[len("branch ") :]
        elif line == "detached":
            current_branch = ""
    flush()
    found.sort(key=lambda item: item.path)
    return found


def discover_repos(root: Path) -> list[Repo]:
    repos: list[Repo] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or not (child / ".git").is_dir():
            continue
        worktrees = _parse_worktrees(child, git(child, "worktree", "list", "--porcelain"))
        repos.append(Repo(name=child.name, path=str(child.resolve()), worktrees=worktrees))
    return repos


def config_root() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "pi-streams"


def homes_path() -> Path:
    return config_root() / "homes"


def default_index() -> Path:
    return config_root()


def read_homes() -> list[Path]:
    path = homes_path()
    if not path.is_file():
        return []
    found: list[Path] = []
    seen: set[str] = set()
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if text == "" or text in seen:
            continue
        seen.add(text)
        found.append(Path(text))
    return found


def register_home(index: Path) -> None:
    path = homes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(index.resolve())
    current: list[str] = []
    seen: set[str] = set()
    if path.is_file():
        for line in path.read_text(encoding="utf-8").splitlines():
            text = line.strip()
            if text == "" or text in seen:
                continue
            seen.add(text)
            current.append(text)
    if resolved in seen:
        return
    current.append(resolved)
    path.write_text("".join(f"{line}\n" for line in current), encoding="utf-8", newline="\n")


def _inside(child: Path, parent: Path) -> bool:
    return child.resolve().is_relative_to(parent.resolve())


def _reject_index_inside_repo(index: Path, repos: list[Repo]) -> None:
    for repo in repos:
        if _inside(index, Path(repo.path)):
            raise StreamsError(f"index {index} is inside repo {repo.name}")
        for item in repo.worktrees:
            if _inside(index, Path(item.path)):
                raise StreamsError(f"index {index} is inside a worktree of {repo.name}")


def templates_dir() -> Path:
    return repo_root() / "pi-streams" / "templates"


def copy_missing(src: Path, dst: Path) -> None:
    for dirpath, _dirnames, filenames in os.walk(src):
        relative = Path(dirpath).relative_to(src)
        target_dir = dst / relative
        target_dir.mkdir(parents=True, exist_ok=True)
        for name in filenames:
            target = target_dir / name
            if not target.exists():
                shutil.copyfile(Path(dirpath) / name, target)


def seed_context(repo: Path, repos: list[Repo]) -> None:
    readme = repo / "context" / "README.md"
    if readme.is_file() and readme.read_text(encoding="utf-8") != "# Shared context\n":
        return
    lines = ["# Shared context", ""]
    for item in repos:
        agents = Path(item.path) / "AGENTS.md"
        if agents.is_file():
            lines.append(f"{item.name}\t{item.path}\t{agents}")
        else:
            lines.append(f"{item.name}\t{item.path}")
    readme.parent.mkdir(parents=True, exist_ok=True)
    readme.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


def default_pi_web_url() -> str:
    path = Path.home() / ".config" / "pi-web" / "config.json"
    if not path.is_file():
        return DEFAULT_PI_WEB_URL
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PI_WEB_URL
    if not isinstance(data, dict):
        return DEFAULT_PI_WEB_URL
    host = data.get("host")
    port = data.get("port")
    if isinstance(port, str) and port.isdigit():
        port = int(port)
    if not isinstance(host, str) or host == "" or isinstance(port, bool) or not isinstance(port, int):
        return DEFAULT_PI_WEB_URL
    return f"http://{host}:{port}"


def _validate_model(model: str) -> None:
    provider, slash, model_id = model.partition("/")
    if slash == "" or provider == "" or model_id == "":
        raise StreamsError("model must be provider/id")


def _choose(label: str, default: str, provided: str | None, assume_yes: bool) -> str:
    if provided is not None:
        return provided
    if assume_yes or not sys.stdin.isatty():
        print(f"{label}: {default}", file=sys.stderr)
        return default
    entered = input(f"{label} [{default}]: ").strip()
    return default if entered == "" else entered


def ensure_git(repo: Path) -> None:
    if (repo / ".git").exists():
        return
    repo.mkdir(parents=True, exist_ok=True)
    git(repo, "init")


def ensure_origin(repo: Path, remote: str) -> None:
    if remote == "":
        return
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo), "config", "--get", "remote.origin.url"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_git_env(),
        check=False,
    )
    if proc.returncode != 0:
        git(repo, "remote", "add", "origin", remote)
        return
    origin = proc.stdout.strip()
    if origin != remote:
        raise StreamsError(f"origin is {origin}, but stream.toml names remote {remote}")


@contextlib.contextmanager
def index_lock(index: Path) -> Iterator[None]:
    with open(index / ".pi-streams.lock", "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


@contextlib.contextmanager
def stream_lock(repo: Path) -> Iterator[None]:
    with open(repo / ".git" / "pi-streams.lock", "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


@contextlib.contextmanager
def stream_locks(repos: list[Path]) -> Iterator[None]:
    ordered = sorted({path.resolve() for path in repos}, key=os.fspath)
    handles: list[object] = []
    try:
        for repo in ordered:
            handle = open(repo / ".git" / "pi-streams.lock", "a", encoding="utf-8")
            fcntl.flock(handle, fcntl.LOCK_EX)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


def commit_repo(repo: Path, message: str) -> bool:
    git(repo, "add", "-A")
    if git(repo, "status", "--porcelain").strip() == "":
        return False
    git(repo, "commit", "-m", message)
    return True


def push_repo(repo: Path, remote: str) -> None:
    if remote == "":
        return
    ensure_origin(repo, remote)
    branch = git(repo, "branch", "--show-current").strip()
    if branch == "":
        raise StreamsError(f"HEAD is detached, so tick cannot push it to {remote}")
    try:
        pushed = git(repo, "rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{branch}").strip()
    except StreamsError:
        pushed = ""
    if pushed == git(repo, "rev-parse", "HEAD").strip():
        return
    git(repo, "push", "--quiet", "--set-upstream", "origin", branch)


def _ensure_index_files(index: Path) -> None:
    (index / "projects").mkdir(parents=True, exist_ok=True)
    streams = index / "streams.tsv"
    if not streams.exists():
        streams.write_text("id\tpath\tproject\n", encoding="utf-8", newline="\n")
    alerts = index / "ALERTS"
    if not alerts.exists():
        alerts.write_bytes(b"")


def init_project(
    project_root: Path,
    *,
    home: Path | None,
    assume_yes: bool,
    pi_web_url: str | None,
    coordinator_model: str | None,
    coordinator_thinking: str | None,
) -> Path:
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise StreamsError(f"project root is not a directory: {root}")
    if not PROJECT_NAME.fullmatch(root.name):
        raise StreamsError(f"project root name cannot be a project file name: {root.name}")
    index = home.expanduser().resolve() if home is not None else default_index().resolve()
    repos = discover_repos(root)
    _reject_index_inside_repo(index, repos)
    index.mkdir(parents=True, exist_ok=True)
    with index_lock(index):
        _ensure_index_files(index)
        path = project_file(index, root.name)
        if path.is_file():
            project = load_project(path)
            project.repos = repos
        else:
            url = _choose("Which URL do you open pi-web at?", default_pi_web_url(), pi_web_url, assume_yes)
            model = _choose(
                "Which model should coordinators use?",
                DEFAULT_MODEL,
                coordinator_model,
                assume_yes,
            )
            thinking = _choose(
                "Which thinking level should coordinators use?",
                DEFAULT_THINKING,
                coordinator_thinking,
                assume_yes,
            )
            _validate_model(model)
            if thinking.strip() == "":
                raise StreamsError("thinking level is empty")
            project = Project(
                info=ProjectSection(
                    name=root.name,
                    root=str(root),
                    pi_web_url=url,
                    worktrees_dir=str((root / ".worktrees").resolve()),
                    pi_stack_revision=pi_stack_revision(),
                ),
                coordinator=ModelSettings(model, thinking),
                threads=ModelSettings(model, thinking),
                caps=Caps(),
                repos=repos,
            )
        save_project(index, project)
        register_home(index)
    return index


def _is_index(path: Path) -> bool:
    return (path / "projects").is_dir() or (path / "streams.tsv").is_file()


def resolve_index(explicit: str | None, cwd: Path | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not _is_index(path):
            raise StreamsError(f"no index at {path}")
        return path
    here = (cwd or Path.cwd()).resolve()
    homes = read_homes()
    containing = [index for index in homes if here == index or here.is_relative_to(index)]
    if containing:
        containing.sort(key=lambda item: len(item.parts), reverse=True)
        return containing[0]
    if len(homes) == 1:
        return homes[0]
    listed = "\n".join(str(index) for index in homes) if homes else "(none)"
    raise StreamsError(f"could not resolve an index\n{listed}")


def resolve_project(index: Path, cwd: Path | None = None) -> Project:
    projects = load_projects(index)
    if len(projects) == 1:
        return projects[0]
    here = (cwd or Path.cwd()).resolve()
    by_root = [
        project
        for project in projects
        if here == Path(project.info.root) or here.is_relative_to(Path(project.info.root))
    ]
    if len(by_root) == 1:
        return by_root[0]
    named = {project.info.name: project for project in projects}
    for row in load_stream_rows(index):
        stream = Path(row.path)
        if here == stream or here.is_relative_to(stream):
            found = named.get(row.project)
            if found is not None:
                return found
    listed = "\n".join(project.info.name for project in projects) if projects else "(none)"
    raise StreamsError(f"could not resolve a project\n{listed}")


def require_stream(index: Path, project_name: str, stream_id: str) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    for row in load_stream_rows(index):
        if row.id == stream_id and row.project == project_name:
            path = Path(row.path)
            if (path / "threads.tsv").is_file():
                return path
            raise StreamsError(f"no stream {stream_id}")
    raise StreamsError(f"no stream {stream_id}")


def stream_rows(index: Path, stream_id: str | None = None) -> list[StreamRow]:
    rows = load_stream_rows(index)
    if stream_id is None:
        return rows
    found = [row for row in rows if row.id == stream_id]
    if not found:
        raise StreamsError(f"no stream {stream_id}")
    return found


def create_stream(index: Path, project: Project, stream_id: str) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    existing = [
        row for row in load_stream_rows(index) if row.id == stream_id and row.project == project.info.name
    ]
    dest = Path(existing[0].path) if existing else (Path(project.info.root) / "streams" / stream_id).resolve()
    fresh = not (dest / "stream.toml").is_file()
    dest.mkdir(parents=True, exist_ok=True)
    ensure_git(dest)
    copy_missing(templates_dir() / "stream", dest)
    if fresh:
        save_stream_config(
            dest,
            StreamConfig(project=project.info.name, pi_stack_revision=pi_stack_revision()),
        )
        seed_context(dest, project.repos)
        upsert_stream_row(index, StreamRow(id=stream_id, path=str(dest), project=project.info.name))
    return dest


def _protected(relative: Path) -> bool:
    return relative.parts[:1] == ("context",) or relative.as_posix() in PROTECTED_STREAM_FILES


def _template_bytes(revision: str, relative: str) -> bytes | None:
    if revision == "":
        return None
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo_root()), "show", f"{revision}:pi-streams/templates/stream/{relative}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def upgrade_stream(repo: Path, stream_id: str) -> bool:
    config = load_stream_config(repo / "stream.toml")
    recorded = config.pi_stack_revision
    current = pi_stack_revision()
    source_root = templates_dir() / "stream"
    for dirpath, _dirnames, filenames in os.walk(source_root):
        relative_dir = Path(dirpath).relative_to(source_root)
        if relative_dir.parts[:1] == ("context",):
            continue
        for name in filenames:
            relative = relative_dir / name
            if _protected(relative):
                continue
            source = Path(dirpath) / name
            target = repo / relative
            new = source.read_bytes()
            if not target.exists():
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(new)
                continue
            old = _template_bytes(recorded, relative.as_posix())
            have = target.read_bytes()
            if old is not None and have == old and have != new:
                target.write_bytes(new)
    config.pi_stack_revision = current
    text = dump_stream_config(config)
    path = repo / "stream.toml"
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        path.write_text(text, encoding="utf-8", newline="\n")
    return commit_repo(repo, f"pi-streams upgrade {stream_id}")

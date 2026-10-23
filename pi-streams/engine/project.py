from __future__ import annotations

import contextlib
import fcntl
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
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
PROTECTED_STREAM_FILES = frozenset({"STREAM.md", "STATE.md", "DECISIONS.md", "GOAL.md", "ACTIONS.md", "threads.tsv"})
STATE_SCHEMA = 1
TEMPLATE_STATE_SCHEMA = STATE_SCHEMA


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
    backend: str = "pi"
    prime_binary: str = ""
    prime_agent_dir: str = ""
    prime_sessions_dir: str = ""
    prime_socket: str = ""
    poteto_path: str = ""


@dataclass
class ModelSettings:
    model: str
    thinking: str


@dataclass
class Caps:
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
    state_schema: int = 0
    backend: str = "pi"


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
        f"thread_handover_tokens = {caps.thread_handover_tokens}",
        f"steer_queue_minutes = {caps.steer_queue_minutes}",
        "",
    ]
    if info.backend != "pi":
        lines[7:7] = [f"{key} = {_q(getattr(info, key))}" for key in (
            "backend", "prime_binary", "prime_agent_dir", "prime_sessions_dir", "prime_socket", "poteto_path")]
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
    if config.state_schema:
        lines.append(f"state_schema = {config.state_schema}")
    if config.backend != "pi":
        lines.append(f"backend = {_q(config.backend)}")
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
                **{key: str(info.get(key, "pi" if key == "backend" else "")) for key in (
                    "backend", "prime_binary", "prime_agent_dir", "prime_sessions_dir", "prime_socket", "poteto_path")},

            ),
            coordinator=ModelSettings(str(coordinator["model"]), str(coordinator["thinking"])),
            threads=ModelSettings(str(threads["model"]), str(threads["thinking"])),
            caps=Caps(
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
    _write(path, dump_project(project))


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
        schema = data.get("state_schema", 0)
        if type(schema) is not int or schema not in (0, STATE_SCHEMA):
            raise ValueError("unsupported STATE schema")
        config = StreamConfig(
            project=str(data["project"]),
            pi_stack_revision=str(data["pi_stack_revision"]),
            remote=str(remote),
            state_schema=schema,
            backend=str(data.get("backend", "pi")),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise StreamsError(f"{path}: {exc}") from exc
    return config


def save_stream_config(repo: Path, config: StreamConfig) -> None:
    _write(repo / "stream.toml", dump_stream_config(config))


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=".pi-streams-", suffix=".tmp", dir=path.parent)
    tmp = Path(name)
    try:
        if path.exists():
            os.fchmod(fd, path.stat().st_mode & 0o777)
        tmp.write_text(text, encoding="utf-8", newline="\n")
        os.fsync(fd)
        os.replace(tmp, path)
        _sync_directory(path.parent)
    finally:
        os.close(fd)
        tmp.unlink(missing_ok=True)


def _sync_directory(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


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


def _git_env(index: Path | None = None) -> dict[str, str]:
    env = os.environ.copy()
    env["GIT_TERMINAL_PROMPT"] = "0"
    if index is not None:
        env["GIT_INDEX_FILE"] = os.fspath(index)
    return env


def git(cwd: Path, *args: str, index: Path | None = None) -> str:
    try:
        proc = subprocess.run(
            ["git", "-C", os.fspath(cwd), *args],
            capture_output=True,
            text=True,
            encoding="utf-8",
            env=_git_env(index),
            check=False,
            timeout=60,
        )
    except subprocess.TimeoutExpired as exc:
        raise StreamsError(f"git {args[0] if args else ''} timed out in {cwd}; reconcile possible effects before retry") from exc
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or f"git {args[0]} failed"
        raise StreamsError(detail)
    return proc.stdout


def git_blob(cwd: Path, object_name: str) -> bytes:
    proc = subprocess.run(
        ["git", "-C", os.fspath(cwd), "cat-file", "blob", object_name],
        capture_output=True,
        env=_git_env(),
        check=False,
    )
    if proc.returncode != 0:
        raise StreamsError(proc.stderr.decode("utf-8", errors="replace").strip() or "git blob read failed")
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
    _write(path, "".join(f"{line}\n" for line in current))


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


def _stream_lock_path(repo: Path) -> Path:
    return Path(git(repo, "rev-parse", "--absolute-git-dir").strip()) / "pi-streams.lock"


@contextlib.contextmanager
def stream_lock(repo: Path) -> Iterator[None]:
    with open(_stream_lock_path(repo), "a", encoding="utf-8") as handle:
        fcntl.flock(handle, fcntl.LOCK_EX)
        yield


@contextlib.contextmanager
def stream_locks(repos: list[Path]) -> Iterator[None]:
    ordered = sorted({path.resolve() for path in repos}, key=os.fspath)
    handles: list[object] = []
    try:
        for repo in ordered:
            handle = open(_stream_lock_path(repo), "a", encoding="utf-8")
            fcntl.flock(handle, fcntl.LOCK_EX)
            handles.append(handle)
        yield
    finally:
        for handle in reversed(handles):
            handle.close()


_TEXT_SUFFIXES = frozenset({
    ".md", ".rst", ".txt", ".py", ".sh", ".js", ".mjs", ".cjs", ".ts", ".tsx",
    ".css", ".html", ".toml", ".yaml", ".yml",
})


def _commit_paths(repo: Path, head: str, paths: tuple[str, ...] | None, *, scope_only: bool = False) -> list[str]:
    templates = templates_dir() / "stream"
    seeded = {path.relative_to(templates).as_posix() for path in templates.rglob("*") if path.is_file()}
    records = seeded | {"stream.toml"}
    tracked = set(git(repo, "ls-tree", "-r", "--name-only", "-z", head).split("\0")) - {""} if head else set()

    def allowed(name: str) -> bool:
        return (
            Path(name).suffix in _TEXT_SUFFIXES
            or name in records
            or Path(name).name in {"README", ".gitkeep", ".gitignore"}
        )

    approved = set(paths or ())
    selected = approved if scope_only else records | {name for name in tracked if allowed(name)} | approved
    result: list[str] = []
    for name in sorted(selected):
        relative = Path(name)
        full = repo / relative
        if (
            relative.is_absolute() or not relative.parts or ".." in relative.parts
            or ".git" in relative.parts or not allowed(name)
            or not full.resolve().is_relative_to(repo.resolve()) or full.is_symlink()
            or (full.exists() and not full.is_file())
        ):
            raise StreamsError(f"not an approved text file: {name}")
        if full.is_file():
            data = full.read_bytes()
            try:
                data.decode("utf-8")
            except UnicodeDecodeError as exc:
                raise StreamsError(f"refusing binary candidate: {name}") from exc
            if b"\0" in data:
                raise StreamsError(f"refusing binary candidate: {name}")
        if full.exists() or name in tracked:
            result.append(name)
        elif name in approved and not scope_only:
            raise StreamsError(f"no approved file: {name}")
    return result


def commit_repo(repo: Path, message: str, *, paths: tuple[str, ...] | None = None, scope_only: bool = False) -> bool:
    index = Path(git(repo, "rev-parse", "--path-format=absolute", "--git-path", "index").strip())
    lock = index.with_name(index.name + ".lock")
    try:
        fd = os.open(lock, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError as exc:
        raise StreamsError(f"Git index is locked: {index}") from exc
    try:
        try:
            head = git(repo, "rev-parse", "--verify", "--quiet", "HEAD").strip()
        except StreamsError:
            git(repo, "symbolic-ref", "--quiet", "HEAD")
            head = ""
        selected = _commit_paths(repo, head, paths, scope_only=scope_only)
        if not selected:
            return False
        with tempfile.TemporaryDirectory(prefix="pi-streams-commit-", dir=index.parent) as directory:
            snapshot = Path(directory) / "snapshot"
            merged = Path(directory) / "merged"
            git(repo, "read-tree", head or "--empty", index=snapshot)
            git(repo, "--literal-pathspecs", "add", "--all", "--", *selected, index=snapshot)
            changed = git(repo, "diff", "--cached", "--no-renames", "--name-only", "-z", index=snapshot).split("\0")
            changed = [name for name in changed if name]
            if not changed:
                return False
            staged = set(git(repo, "diff", "--cached", "--no-renames", "--name-only", "-z").split("\0"))
            overlap = staged.intersection(changed)
            if overlap:
                raise StreamsError("refusing overlapping staged edits: " + ", ".join(sorted(overlap)))
            stats = git(repo, "diff", "--cached", "--no-renames", "--numstat", "-z", index=snapshot)
            if any(record.startswith("-\t-\t") for record in stats.split("\0")):
                raise StreamsError("refusing binary staged candidate")
            tree = git(repo, "write-tree", index=snapshot).strip()
            if index.exists():
                shutil.copyfile(index, merged)
                os.fchmod(fd, index.stat().st_mode & 0o777)
            else:
                git(repo, "read-tree", "--empty", index=merged)
            git(repo, "--literal-pathspecs", "restore", "--staged", f"--source={tree}", "--", *changed, index=merged)
            with os.fdopen(fd, "wb") as handle:
                fd = -1
                handle.write(merged.read_bytes())
                handle.flush()
                os.fsync(handle.fileno())
            parents = ("-p", head) if head else ()
            commit = git(repo, "commit-tree", tree, *parents, "-m", message).strip()
            git(repo, "update-ref", "-m", message, "HEAD", commit, head or "0" * len(commit))
            try:
                os.replace(lock, index)
                _sync_directory(index.parent)
            except OSError as exc:
                raise StreamsError(f"commit {commit} exists but index publication is unconfirmed: {exc}") from exc
        return True
    finally:
        if fd != -1:
            os.close(fd)
        lock.unlink(missing_ok=True)


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
        _write(streams, "id\tpath\tproject\n")
    alerts = index / "ALERTS"
    if not alerts.exists():
        _write(alerts, "")


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


def assert_artifacts_ready(stream: Path) -> None:
    path = stream / "log/migration.json"
    if not path.exists() and not path.is_symlink():
        return
    if path.is_symlink() or path.parent.is_symlink() or not path.is_file():
        raise StreamsError("unsafe migration journal; artifact operations are parked")
    try:
        operation = json.loads(path.read_bytes())
    except (OSError, ValueError) as exc:
        raise StreamsError("unreadable migration journal; artifact operations are parked") from exc
    if not isinstance(operation, dict) or operation.get("version") != 1 or operation.get("root") != str(stream.resolve()) or operation.get("phase") != "complete":
        raise StreamsError("artifact migration is pending; resume the exact migration before other operations")


def require_stream(index: Path, project_name: str, stream_id: str, *, allow_migration: bool = False) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    for row in load_stream_rows(index):
        if row.id == stream_id and row.project == project_name:
            path = Path(row.path)
            if (path / "threads.tsv").is_file():
                if not allow_migration:
                    assert_artifacts_ready(path)
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


def create_stream(index: Path, project: Project, stream_id: str, *, backend: str | None = None) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    existing = [
        row for row in load_stream_rows(index) if row.id == stream_id and row.project == project.info.name
    ]
    dest = Path(existing[0].path) if existing else Path(project.info.root) / "streams" / stream_id
    expected = Path(os.path.abspath(Path(project.info.root) / "streams" / stream_id))
    lexical = Path(os.path.abspath(dest))
    if any(path.is_symlink() for path in (lexical, *lexical.parents)):
        raise StreamsError("refusing symlink in stream path or ancestors")
    dest = lexical
    fresh = not (dest / "stream.toml").is_file()
    assert_artifacts_ready(dest)
    recorded_backend = load_stream_config(dest / "stream.toml").backend if not fresh else None
    backend = backend or recorded_backend or project.info.backend
    if backend == "prime" and dest != expected:
        raise StreamsError("registered Prime stream path escapes its project stream directory")
    if backend not in {"pi", "prime"} or recorded_backend not in {None, backend}:
        raise StreamsError("stream backend conflicts with existing stream")
    if backend == "prime" and (dest.is_symlink() or any((dest / name).is_symlink() for name in ("AGENTS.md", "STATE.md", "threads.tsv", "history"))):
        raise StreamsError("refusing symlink in Prime stream")
    if fresh and backend == "prime" and any((dest / name).exists() for name in ("AGENTS.md", "STATE.md")):
        raise StreamsError("refusing to replace existing stream instructions or current work")
    dest.mkdir(parents=True, exist_ok=True)
    ensure_git(dest)
    if backend == "prime":
        from engine.state import _publish, check_state
        if fresh:
            for name in ("AGENTS.md", "STATE.md"):
                _publish(dest / name, (templates_dir() / "prime" / name).read_text(encoding="utf-8"), immutable=True)
            _publish(dest / "threads.tsv", (templates_dir() / "stream" / "threads.tsv").read_text(encoding="utf-8"), immutable=True)
        (dest / "history").mkdir(exist_ok=True)
        check_state(dest)
    else:
        if not fresh and load_stream_config(dest / "stream.toml").state_schema != TEMPLATE_STATE_SCHEMA:
            raise StreamsError("stream/template STATE schema mismatch; explicit migration is required")
        copy_missing(templates_dir() / "stream", dest)
    if fresh:
        save_stream_config(
            dest,
            StreamConfig(project=project.info.name, pi_stack_revision=pi_stack_revision(), backend=backend,
                         state_schema=TEMPLATE_STATE_SCHEMA if backend == "pi" else 0),
        )
        if backend == "pi":
            seed_context(dest, project.repos)
    upsert_stream_row(index, StreamRow(id=stream_id, path=str(dest), project=project.info.name))
    return dest


def _protected(relative: Path) -> bool:
    return relative.parts[:1] in {("context",), ("history",), ("failures",)} or relative.as_posix() in PROTECTED_STREAM_FILES


def _template_bytes(revision: str, relative: str, template: str = "stream") -> bytes | None:
    if revision == "":
        return None
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo_root()), "show", f"{revision}:pi-streams/templates/{template}/{relative}"],
        capture_output=True,
        check=False,
    )
    if proc.returncode != 0:
        return None
    return proc.stdout


def upgrade_stream(repo: Path, stream_id: str) -> bool:
    assert_artifacts_ready(repo)
    config = load_stream_config(repo / "stream.toml")
    if config.backend == "pi" and config.state_schema != TEMPLATE_STATE_SCHEMA:
        raise StreamsError("stream/template STATE schema mismatch; explicit migration is required")
    recorded = config.pi_stack_revision
    current = pi_stack_revision()
    source_root = templates_dir() / ("prime" if config.backend == "prime" else "stream")
    if config.backend == "prime":
        from engine.state import check_state
        check_state(repo)
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
            old = _template_bytes(recorded, relative.as_posix(), source_root.name)
            have = target.read_bytes()
            if old is not None and have == old and have != new:
                if config.backend == "prime":
                    from engine.state import _publish
                    _publish(target, new.decode("utf-8"))
                else:
                    target.write_bytes(new)
    config.pi_stack_revision = current
    text = dump_stream_config(config)
    path = repo / "stream.toml"
    if not path.is_file() or path.read_text(encoding="utf-8") != text:
        save_stream_config(repo, config)
    return commit_repo(repo, f"pi-streams upgrade {stream_id}")


def write_prime_settings(stream: Path, threshold_percent: float) -> Path:
    import math
    from engine.state import _publish
    if isinstance(threshold_percent, bool) or not isinstance(threshold_percent, (int, float)) or not math.isfinite(threshold_percent) or not 0 < threshold_percent <= 100:
        raise StreamsError("compaction percentage must be finite, greater than zero and at most 100")
    path = stream / ".prime" / "agent" / "settings.json"
    if any(item.is_symlink() for item in (stream, *stream.parents, path.parent, path.parent.parent, path)):
        raise StreamsError("refusing symlink settings path")
    data = {"compaction": {"enabled": False, "agentCallable": False, "thresholdPercent": threshold_percent}}
    text = json.dumps(data, sort_keys=True, allow_nan=False) + "\n"
    if path.exists():
        if path.read_text() != text:
            raise StreamsError("owned Prime settings conflict; never reconfigure a constructed session")
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    _publish(path, text, immutable=True)
    return path

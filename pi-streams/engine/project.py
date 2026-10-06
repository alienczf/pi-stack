from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

from engine import StreamsError, repo_root

DEFAULT_MODEL = "openai-codex/gpt-6-astra"
DEFAULT_THINKING = "xhigh"
DEFAULT_PI_WEB_URL = "http://127.0.0.1:8504"
STREAM_ID = re.compile(r"^[a-z0-9][a-z0-9-]*$")
RESERVED_STREAM_IDS = frozenset({"context"})


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
    home: str
    pi_web_url: str
    remote: str
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
        f"home = {_q(info.home)}",
        f"pi_web_url = {_q(info.pi_web_url)}",
        f"remote = {_q(info.remote)}",
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


def _repo_from_toml(item: object) -> Repo:
    if not isinstance(item, dict):
        raise StreamsError("project.toml repo entry is not a table")
    worktrees: list[Worktree] = []
    for raw in item["worktrees"]:
        if not isinstance(raw, dict):
            raise StreamsError("project.toml worktree entry is not a table")
        worktrees.append(Worktree(path=str(raw["path"]), branch=str(raw["branch"])))
    return Repo(name=str(item["name"]), path=str(item["path"]), worktrees=worktrees)


def load_project(home: Path) -> Project:
    path = home / "project.toml"
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise StreamsError(f"project.toml: {exc}") from exc
    try:
        info = data["project"]
        coordinator = data["coordinator"]
        threads = data["threads"]
        caps = data["caps"]
        project = Project(
            info=ProjectSection(
                name=str(info["name"]),
                root=str(info["root"]),
                home=str(info["home"]),
                pi_web_url=str(info["pi_web_url"]),
                remote=str(info["remote"]),
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
        raise StreamsError(f"project.toml: {exc}") from exc
    return project


def save_project(home: Path, project: Project) -> None:
    (home / "project.toml").write_text(dump_project(project), encoding="utf-8", newline="\n")


def _git_env() -> dict[str, str]:
    # A credential prompt would hang a non-interactive init.
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


def discover_repos(root: Path, home: Path) -> list[Repo]:
    home_resolved = home.resolve()
    repos: list[Repo] = []
    for child in sorted(root.iterdir(), key=lambda item: item.name):
        if not child.is_dir() or child.resolve() == home_resolved:
            continue
        if not (child / ".git").is_dir():
            continue
        worktrees = _parse_worktrees(child, git(child, "worktree", "list", "--porcelain"))
        repos.append(Repo(name=child.name, path=str(child.resolve()), worktrees=worktrees))
    return repos


def homes_path() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "pi-streams" / "homes"


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


def register_home(home: Path) -> None:
    path = homes_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    resolved = str(home.resolve())
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


def _reject_home_inside_repo(home: Path, repos: list[Repo]) -> None:
    for repo in repos:
        if _inside(home, Path(repo.path)):
            raise StreamsError(f"project home {home} is inside repo {repo.name}")
        for item in repo.worktrees:
            if _inside(home, Path(item.path)):
                raise StreamsError(f"project home {home} is inside a worktree of {repo.name}")


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


def seed_context(home: Path, repos: list[Repo]) -> None:
    lines = ["# Shared context", ""]
    for repo in repos:
        agents = Path(repo.path) / "AGENTS.md"
        if agents.is_file():
            lines.append(f"{repo.name}\t{repo.path}\t{agents}")
        else:
            lines.append(f"{repo.name}\t{repo.path}")
    (home / "context" / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")


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


def _choose_remote(provided: str | None, assume_yes: bool) -> str:
    if provided is not None:
        return provided
    label = "Where should the project home's private remote live?"
    if assume_yes or not sys.stdin.isatty():
        print(f"{label}: none", file=sys.stderr)
        return ""
    entered = input(f"{label} [none]: ").strip()
    if entered == "" or entered == "none":
        return ""
    return entered


def ensure_git(home: Path) -> None:
    if (home / ".git").exists():
        return
    git(home, "init")


def ensure_origin(home: Path, remote: str) -> None:
    if remote == "":
        return
    proc = subprocess.run(
        ["git", "-C", os.fspath(home), "remote", "get-url", "origin"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        env=_git_env(),
        check=False,
    )
    if proc.returncode == 0:
        return
    git(home, "remote", "add", "origin", remote)


def commit_home(home: Path, message: str) -> bool:
    git(home, "add", "-A")
    if git(home, "status", "--porcelain").strip() == "":
        return False
    git(home, "commit", "-m", message)
    return True


def init_project(
    project_root: Path,
    *,
    home: Path | None,
    assume_yes: bool,
    pi_web_url: str | None,
    remote: str | None,
    coordinator_model: str | None,
    coordinator_thinking: str | None,
) -> Path:
    root = project_root.expanduser().resolve()
    if not root.is_dir():
        raise StreamsError(f"project root is not a directory: {root}")
    if root.name == "":
        raise StreamsError("project root has no name")
    home_path = home.expanduser().resolve() if home is not None else (root / "streams").resolve()
    repos = discover_repos(root, home_path)
    _reject_home_inside_repo(home_path, repos)
    toml_path = home_path / "project.toml"
    if toml_path.is_file():
        project = load_project(home_path)
        project.repos = repos
        first = False
    else:
        url = _choose("Which URL do you open pi-web at?", default_pi_web_url(), pi_web_url, assume_yes)
        chosen_remote = _choose_remote(remote, assume_yes)
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
                home=str(home_path),
                pi_web_url=url,
                remote=chosen_remote,
                worktrees_dir=str((root / ".worktrees").resolve()),
                pi_stack_revision=pi_stack_revision(),
            ),
            coordinator=ModelSettings(model, thinking),
            threads=ModelSettings(model, thinking),
            caps=Caps(),
            repos=repos,
        )
        first = True
    home_path.mkdir(parents=True, exist_ok=True)
    copy_missing(templates_dir() / "project", home_path)
    if first:
        seed_context(home_path, repos)
    save_project(home_path, project)
    ensure_git(home_path)
    ensure_origin(home_path, project.info.remote)
    register_home(home_path)
    commit_home(home_path, "pi-streams init")
    return home_path


def resolve_home(explicit: str | None, cwd: Path | None = None) -> Path:
    if explicit:
        path = Path(explicit).expanduser().resolve()
        if not (path / "project.toml").is_file():
            raise StreamsError(f"no project.toml in {path}")
        return path
    here = (cwd or Path.cwd()).resolve()
    homes = read_homes()
    containing = [home for home in homes if here == home or here.is_relative_to(home)]
    if containing:
        containing.sort(key=lambda item: len(item.parts), reverse=True)
        return containing[0]
    if len(homes) == 1:
        return homes[0]
    listed = "\n".join(str(home) for home in homes) if homes else "(none)"
    raise StreamsError(f"could not resolve a project home\n{listed}")


def create_stream(home: Path, stream_id: str) -> Path:
    if STREAM_ID.fullmatch(stream_id) is None:
        raise StreamsError(f"invalid stream id: {stream_id}")
    if stream_id in RESERVED_STREAM_IDS:
        raise StreamsError(f"reserved stream id: {stream_id}")
    dest = home / stream_id
    if dest.exists() and not dest.is_dir():
        raise StreamsError(f"not a directory: {dest}")
    dest.mkdir(parents=True, exist_ok=True)
    copy_missing(templates_dir() / "stream", dest)
    return dest


def stream_dirs(home: Path) -> list[Path]:
    if not home.is_dir():
        return []
    return [
        child
        for child in sorted(home.iterdir(), key=lambda item: item.name)
        if child.is_dir() and (child / "STREAM.md").is_file()
    ]

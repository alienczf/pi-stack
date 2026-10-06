from __future__ import annotations

import json
import os
import shutil
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from engine import StreamsError
from engine import piweb
from engine.project import git, load_project, read_homes, stream_dirs

PSTACK_SKILLS = (
    "correct",
    "reflect",
    "create-verification-skill",
    "maintain-verification-skill",
)
TICK_UNITS = ("pi-streams-tick.service", "pi-streams-tick.timer")
TICK_FRESH_SECONDS = 15 * 60


@dataclass(frozen=True)
class Finding:
    level: str
    name: str
    detail: str

    def line(self) -> str:
        return f"{self.level} {self.name}: {self.detail}"


def _search_pi(root: Path) -> Path | None:
    if not root.is_dir():
        return None
    base = root.resolve()
    for dirpath, dirnames, filenames in os.walk(base):
        current = Path(dirpath)
        if "pi" in filenames:
            candidate = current / "pi"
            if os.access(candidate, os.X_OK):
                return candidate.resolve()
        if len(current.relative_to(base).parts) >= 4:
            dirnames[:] = []
    return None


def find_pi() -> Path | None:
    found = shutil.which("pi")
    if found:
        return Path(found).resolve()
    return _search_pi(Path.home() / ".local" / "share" / "pi-node")


def check_pi() -> list[Finding]:
    found = find_pi()
    if found is None:
        return [Finding("FAIL", "pi", "not found on PATH or under ~/.local/share/pi-node")]
    return [Finding("PASS", "pi", f"found at {found}")]


def check_pi_web() -> list[Finding]:
    homes = read_homes()
    cwd = str(homes[0]) if homes else str(Path.home())
    try:
        piweb.list_sessions(cwd)
    except StreamsError:
        return [Finding("FAIL", "pi-web", "list failed")]
    return [Finding("PASS", "pi-web", "list ok")]


def check_steer() -> list[Finding]:
    if "--steer" in piweb.prompt_help():
        return [Finding("PASS", "steer", "prompt accepts --steer")]
    return [Finding("FAIL", "steer", "prompt --help does not offer --steer")]


def check_homes() -> list[Finding]:
    findings: list[Finding] = []
    for home in read_homes():
        if not (home / ".git").exists():
            findings.append(Finding("FAIL", "home", f"{home} is not a git repo"))
            continue
        try:
            status = git(home, "status", "--porcelain")
        except StreamsError as exc:
            findings.append(Finding("FAIL", "home", f"{home} is not a git repo: {exc}"))
            continue
        if status.strip() != "":
            findings.append(Finding("FAIL", "home", f"{home} has uncommitted changes"))
            continue
        try:
            load_project(home)
        except StreamsError as exc:
            findings.append(Finding("FAIL", "home", f"{home} project.toml does not parse: {exc}"))
            continue
        findings.append(Finding("PASS", "home", f"{home} is a clean git repo and project.toml parses"))
    return findings


def check_skills() -> list[Finding]:
    base = Path.home() / ".pi" / "agent" / "skills-pstack"
    missing = [name for name in PSTACK_SKILLS if not (base / name / "SKILL.md").is_file()]
    if missing:
        return [Finding("FAIL", "skills", "missing " + ", ".join(missing))]
    return [Finding("PASS", "skills", "present")]


def _config_base() -> Path:
    xdg = os.environ.get("XDG_CONFIG_HOME")
    if xdg:
        return Path(xdg)
    return Path.home() / ".config"


def systemd_user_dir() -> Path:
    return _config_base() / "systemd" / "user"


def check_systemd_units() -> list[Finding]:
    base = systemd_user_dir()
    missing = [name for name in TICK_UNITS if not (base / name).is_file()]
    if missing:
        return [Finding("FAIL", "systemd", "missing " + ", ".join(missing))]
    return [Finding("PASS", "systemd", "pi-streams-tick.service and pi-streams-tick.timer are installed")]


def _tick_state_fresh(path: Path, now: float) -> bool:
    if not path.is_file():
        return False
    try:
        mtime = path.stat().st_mtime
    except OSError:
        return False
    return mtime > now - TICK_FRESH_SECONDS


def check_tick() -> list[Finding]:
    now = time.time()
    considered = False
    for home in read_homes():
        streams = stream_dirs(home)
        if not streams:
            continue
        considered = True
        for stream in streams:
            if _tick_state_fresh(stream / "log" / "tick-state.json", now):
                return []
    if not considered:
        return []
    return [Finding("WARN", "tick", "no tick-state.json under any home is newer than 15 minutes")]


def pi_web_project_dirs() -> list[Path]:
    path = Path.home() / ".pi-web" / "projects.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return []
    if not isinstance(data, dict):
        return []
    projects = data.get("projects")
    if not isinstance(projects, list):
        return []
    found: list[Path] = []
    for item in projects:
        if not isinstance(item, dict):
            continue
        raw = item.get("path")
        if isinstance(raw, str) and raw.strip() != "":
            found.append(Path(raw).expanduser())
    return found


def _inside(child: Path, parent: Path) -> bool:
    try:
        child.resolve().relative_to(parent.expanduser().resolve())
    except (OSError, ValueError):
        return False
    return True


def check_pi_web_projects() -> list[Finding]:
    directories = pi_web_project_dirs()
    findings: list[Finding] = []
    for home in read_homes():
        if any(_inside(home, directory) for directory in directories):
            continue
        findings.append(
            Finding("WARN", "pi-web-project", f"{home} is not inside a directory listed in ~/.pi-web/projects.json")
        )
    return findings


def check_jig() -> list[Finding]:
    findings: list[Finding] = []
    for home in read_homes():
        try:
            project = load_project(home)
        except StreamsError:
            continue
        for repo in project.repos:
            if (Path(repo.path) / ".pi" / "jig").exists():
                findings.append(Finding("WARN", "jig", f"{repo.name} still holds .pi/jig/ (left alone)"))
    return findings


CHECK_FNS: list[Callable[[], list[Finding]]] = [
    check_pi,
    check_pi_web,
    check_steer,
    check_homes,
    check_skills,
    check_jig,
    check_systemd_units,
    check_tick,
    check_pi_web_projects,
]


def run_doctor() -> int:
    findings: list[Finding] = []
    for fn in CHECK_FNS:
        findings.extend(fn())
    for finding in findings:
        print(finding.line())
    if any(item.level == "FAIL" for item in findings):
        return 1
    return 0

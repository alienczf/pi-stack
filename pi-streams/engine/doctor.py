from __future__ import annotations

import os
import shutil
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

from engine import StreamsError
from engine import piweb
from engine.project import git, load_project, read_homes

PSTACK_SKILLS = (
    "correct",
    "reflect",
    "create-verification-skill",
    "maintain-verification-skill",
)


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

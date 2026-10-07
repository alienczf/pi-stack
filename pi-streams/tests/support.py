"""Temp project fixture and an explicit subprocess environment."""
from __future__ import annotations

import os
import shutil
import subprocess
import tempfile
import unittest
import urllib.parse
from dataclasses import dataclass
from pathlib import Path

from stub_piweb import StubPiWeb

ROOT = Path(__file__).resolve().parents[2]
CLI = ROOT / "bin" / "pi-streams"
LIVE = "http://127.0.0.1:8504"


def make_env(home: Path, xdg: Path, pi_web_url: str) -> dict[str, str]:
    if pi_web_url.rstrip("/") == LIVE:
        raise RuntimeError("refusing to call the live PI WEB server")
    return {
        "PATH": "/usr/bin:/bin",
        "HOME": str(home),
        "XDG_CONFIG_HOME": str(xdg),
        "PI_WEB_URL": pi_web_url,
        # A request to any address but the stub goes to a dead proxy, even when
        # a test removes PI_WEB_URL and the engine falls back to a default.
        "http_proxy": "http://127.0.0.1:9",
        "no_proxy": urllib.parse.urlsplit(pi_web_url).netloc,
        "GIT_AUTHOR_NAME": "Test",
        "GIT_AUTHOR_EMAIL": "test@example.com",
        "GIT_COMMITTER_NAME": "Test",
        "GIT_COMMITTER_EMAIL": "test@example.com",
        "GIT_CONFIG_NOSYSTEM": "1",
        "GIT_TERMINAL_PROMPT": "0",
        "LANG": "C.UTF-8",
        "LC_ALL": "C.UTF-8",
    }


def git(repo: Path, env: dict[str, str], *args: str) -> str:
    proc = subprocess.run(
        ["git", "-C", os.fspath(repo), *args],
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        check=False,
    )
    if proc.returncode != 0:
        raise AssertionError(proc.stderr or proc.stdout)
    return proc.stdout


def pi_stack_revision() -> str:
    return subprocess.check_output(
        ["git", "-C", os.fspath(ROOT), "rev-parse", "HEAD"],
        text=True,
        encoding="utf-8",
    ).strip()


@dataclass
class Fixture:
    alpha: Path
    alpha_wt: Path
    beta: Path
    beta_wt: Path
    gamma: Path
    gamma_wt: Path
    notes: Path


def _init_repo(path: Path, env: dict[str, str], filename: str, body: str) -> None:
    path.mkdir(parents=True)
    git(path, env, "init")
    (path / filename).write_text(body, encoding="utf-8")
    git(path, env, "add", "-A")
    git(path, env, "commit", "-m", "init")


def build_fixture(root: Path, outside: Path, env: dict[str, str]) -> Fixture:
    alpha = root / "alpha"
    _init_repo(alpha, env, "README", "alpha\n")
    (alpha / "AGENTS.md").write_text("alpha agents\n", encoding="utf-8")
    git(alpha, env, "add", "-A")
    git(alpha, env, "commit", "-m", "agents")
    git(alpha, env, "branch", "feat-a")
    alpha_wt = root / "alpha-wt"
    git(alpha, env, "worktree", "add", str(alpha_wt), "feat-a")

    beta = root / "beta"
    _init_repo(beta, env, "README", "beta\n")
    git(beta, env, "branch", "x")
    beta_wt = beta / ".worktrees" / "x"
    beta_wt.parent.mkdir()
    git(beta, env, "worktree", "add", str(beta_wt), "x")

    gamma = root / "gamma"
    _init_repo(gamma, env, "README", "gamma\n")
    git(gamma, env, "branch", "g")
    gamma_wt = outside / "gamma-wt"
    git(gamma, env, "worktree", "add", str(gamma_wt), "g")

    notes = root / "notes"
    notes.mkdir()
    (notes / "n.txt").write_text("note\n", encoding="utf-8")
    return Fixture(
        alpha=alpha,
        alpha_wt=alpha_wt,
        beta=beta,
        beta_wt=beta_wt,
        gamma=gamma,
        gamma_wt=gamma_wt,
        notes=notes,
    )


def snapshot(home: Path) -> dict[str, bytes]:
    found: dict[str, bytes] = {}
    for dirpath, dirnames, filenames in os.walk(home):
        dirnames[:] = [name for name in dirnames if name != ".git"]
        for name in filenames:
            path = Path(dirpath) / name
            found[str(path.relative_to(home))] = path.read_bytes()
    return found


class EngineCase(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = Path(tempfile.mkdtemp(prefix="pi-streams-test-"))
        self.addCleanup(lambda: shutil.rmtree(self.tmp, ignore_errors=True))
        self.user_home = self.tmp / "userhome"
        self.xdg = self.tmp / "xdg"
        self.user_home.mkdir()
        self.xdg.mkdir()
        self.stub = StubPiWeb()
        self.addCleanup(self.stub.stop)
        self.stub.start()
        self.assertNotEqual(self.stub.url.rstrip("/"), LIVE)
        self.env = make_env(self.user_home, self.xdg, self.stub.url)
        self.outside = Path(tempfile.mkdtemp(prefix="pi-streams-gamma-"))
        self.addCleanup(lambda: shutil.rmtree(self.outside, ignore_errors=True))
        self.root = self.tmp / "proj"
        self.root.mkdir()
        self.fx = build_fixture(self.root, self.outside, self.env)

    def run_streams(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [os.fspath(CLI), *args],
            env=self.env,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=True,
            encoding="utf-8",
            check=False,
        )

    @property
    def home(self) -> Path:
        return self.root / "streams"

    @property
    def index(self) -> Path:
        return self.xdg / "pi-streams"

    @property
    def project_file(self) -> Path:
        return self.index / "projects" / f"{self.root.name}.toml"

    def register_stream(
        self,
        stream_id: str,
        stream_dir: Path | None = None,
        index: Path | None = None,
        project: str | None = None,
    ) -> Path:
        stream_dir = (self.home / stream_id if stream_dir is None else stream_dir).resolve()
        stream_dir.mkdir(parents=True, exist_ok=True)
        index = self.index if index is None else index
        project = self.root.name if project is None else project
        path = index / "streams.tsv"
        header = "id\tpath\tproject\n"
        text = path.read_text(encoding="utf-8") if path.is_file() else header
        if not text.endswith("\n"):
            text += "\n"
        row = f"{stream_id}\t{stream_dir}\t{project}\n"
        lines = text.splitlines()
        if row.strip() not in lines:
            if not lines or lines[0] != "id\tpath\tproject":
                text = header + text
            text += row
            path.write_text(text, encoding="utf-8")
        return stream_dir

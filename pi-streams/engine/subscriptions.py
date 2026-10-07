from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import signal
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from engine import StreamsError

SUBSCRIPTION_COLUMNS = ("id", "source", "target", "when", "action")
TIMEOUT_SECONDS = 60
CMD_DETAIL_LINES = 20
GH_PR_FIELDS = "state,reviewDecision,statusCheckRollup,mergedAt,reviews"
_HHMM = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")
_PR = re.compile(r"([A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)#([0-9]+)")


@dataclass
class Subscription:
    id: str
    source: str
    target: str
    when: str
    action: str

    def watch(self) -> list[str]:
        return [self.source, self.target, self.when]


@dataclass
class Reading:
    fingerprint: str
    detail: list[str] = field(default_factory=list)


Source = Callable[[Subscription, Path, datetime], Reading]


def load_subscriptions(path: Path) -> list[Subscription]:
    if not path.is_file():
        return []
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc
    if not lines or tuple(lines[0].split("\t")) != SUBSCRIPTION_COLUMNS:
        raise StreamsError(f"{path} has an unexpected header")
    found: list[Subscription] = []
    for index, line in enumerate(lines[1:], start=2):
        if line == "":
            continue
        parts = line.split("\t")
        if len(parts) != len(SUBSCRIPTION_COLUMNS):
            raise StreamsError(f"{path}:{index} has {len(parts)} fields")
        if parts[0] == "" or any(item.id == parts[0] for item in found):
            raise StreamsError(f"{path}:{index} has an empty or repeated id")
        found.append(Subscription(*parts))
    return found


def read_schedule(sub: Subscription, _stream_dir: Path, now: datetime) -> Reading:
    match = _HHMM.fullmatch(sub.when)
    if match is None:
        raise StreamsError(f"when is not HH:MM: {sub.when}")
    # The date of the last due time changes once a day, at the first tick at or after it.
    due = now.replace(hour=int(match[1]), minute=int(match[2]), second=0, microsecond=0)
    day = due.date() if now >= due else due.date() - timedelta(days=1)
    return Reading(day.isoformat())


def read_cmd(sub: Subscription, stream_dir: Path, _now: datetime) -> Reading:
    code, out, err = _run(["bash", "-c", sub.target], stream_dir)
    lines = out.decode("utf-8", "replace").splitlines() + err.decode("utf-8", "replace").splitlines()
    return Reading(f"exit={code} sha256={hashlib.sha256(out).hexdigest()}", lines[-CMD_DETAIL_LINES:])


def read_gh_pr(sub: Subscription, stream_dir: Path, _now: datetime) -> Reading:
    match = _PR.fullmatch(sub.target)
    if match is None:
        raise StreamsError(f"target is not owner/repo#N: {sub.target}")
    code, out, err = _run(["gh", "pr", "view", match[2], "--repo", match[1], "--json", GH_PR_FIELDS], stream_dir)
    if code != 0:
        said = " / ".join(line.strip() for line in err.decode("utf-8", "replace").splitlines() if line.strip())
        raise StreamsError(f"gh exited {code}: {said}" if said else f"gh exited {code}")
    try:
        view = json.loads(out)
    except ValueError as exc:
        raise StreamsError(f"gh printed no JSON: {exc}") from None
    if not isinstance(view, dict):
        raise StreamsError("gh printed no JSON object")
    checks = sorted(_conclusion(check) for check in _items(view.get("statusCheckRollup")))
    summary = " ".join([
        f"state={view.get('state') or '-'}",
        f"reviewDecision={view.get('reviewDecision') or '-'}",
        f"checks={','.join(checks) or '-'}",
        f"mergedAt={view.get('mergedAt') or '-'}",
        f"reviews={len(_items(view.get('reviews')))}",
    ])
    return Reading(summary, [summary])


def _items(value: object) -> list[dict[str, object]]:
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _conclusion(check: dict[str, object]) -> str:
    # A commit status reports its result as state, and a check run has no conclusion until it completes.
    if check.get("__typename") == "StatusContext":
        return f"{check.get('context')}:{check.get('state') or 'PENDING'}"
    return f"{check.get('name')}:{check.get('conclusion') or 'PENDING'}"


def _run(argv: list[str], cwd: Path) -> tuple[int, bytes, bytes]:
    try:
        proc = subprocess.Popen(
            argv,
            cwd=cwd,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise StreamsError(f"could not start {argv[0]}: {exc}") from exc
    try:
        out, err = proc.communicate(timeout=TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # Children of the command keep the pipes open, so the whole group goes.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise StreamsError(f"timed out after {TIMEOUT_SECONDS} s") from None
    return proc.returncode, out, err


SOURCES: dict[str, Source] = {
    "schedule": read_schedule,
    "cmd": read_cmd,
    "gh-pr": read_gh_pr,
}

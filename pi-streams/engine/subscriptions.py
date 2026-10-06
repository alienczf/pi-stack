from __future__ import annotations

import contextlib
import hashlib
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
CMD_TIMEOUT_SECONDS = 60
CMD_DETAIL_LINES = 20
_HHMM = re.compile(r"([01][0-9]|2[0-3]):([0-5][0-9])")


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
    try:
        proc = subprocess.Popen(
            ["bash", "-c", sub.target],
            cwd=stream_dir,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            start_new_session=True,
        )
    except OSError as exc:
        raise StreamsError(f"could not start bash: {exc}") from exc
    try:
        out, err = proc.communicate(timeout=CMD_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        # Children of bash keep the pipes open, so the whole group goes.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(proc.pid, signal.SIGKILL)
        proc.communicate()
        raise StreamsError(f"timed out after {CMD_TIMEOUT_SECONDS} s") from None
    lines = out.decode("utf-8", "replace").splitlines() + err.decode("utf-8", "replace").splitlines()
    fingerprint = f"exit={proc.returncode} sha256={hashlib.sha256(out).hexdigest()}"
    return Reading(fingerprint, lines[-CMD_DETAIL_LINES:])


SOURCES: dict[str, Source] = {
    "schedule": read_schedule,
    "cmd": read_cmd,
}

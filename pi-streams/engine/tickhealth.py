from __future__ import annotations

import fcntl
import json
import os
import stat
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from pathlib import Path

from engine import StreamsError, clock, sessionlog
from engine.project import StreamRow, _write


@dataclass
class StreamPass:
    id: str
    project: str
    started: str = ""
    completed: str = ""
    ok: bool = False
    errors: list[str] = field(default_factory=list)


@dataclass
class TickPass:
    id: str
    started: str
    streams: dict[str, StreamPass]
    version: int = 1
    owner_pid: int = field(default_factory=os.getpid)
    completed: str = ""
    ok: bool = False
    errors: list[str] = field(default_factory=list)

    @classmethod
    def begin(cls, rows: list[StreamRow], at: str) -> TickPass:
        streams = {str(Path(row.path).resolve()): StreamPass(row.id, row.project) for row in rows}
        if len(streams) != len(rows):
            raise StreamsError("duplicate registered stream root; refusing ambiguous tick ownership")
        return cls(uuid.uuid4().hex, at, streams)

    def save(self, index: Path) -> None:
        path = index / "tick-health.json"
        try:
            mode = path.lstat().st_mode
        except FileNotFoundError:
            pass
        else:
            if not stat.S_ISREG(mode):
                raise StreamsError("tick health destination is not a regular owned report")
        _write(path, json.dumps(asdict(self), sort_keys=True, indent=2) + "\n")


@contextmanager
def tick_lease(index: Path):
    directory = os.open(index, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    descriptor = None
    try:
        descriptor = os.open(".pi-streams.tick.lock", os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW | os.O_NONBLOCK, 0o600, dir_fd=directory)
        if not stat.S_ISREG(os.fstat(descriptor).st_mode):
            raise StreamsError("tick lease must be a regular owned lock file")
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            raise StreamsError("another tick pass owns this index; no second writer started") from exc
        yield
    finally:
        if descriptor is not None:
            os.close(descriptor)
        os.close(directory)


def read(index: Path) -> dict | None:
    try:
        with sessionlog.regular_reader(index / "tick-health.json") as handle:
            value = json.load(handle)
    except FileNotFoundError:
        return None
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or not isinstance(value.get("id"), str) or not value["id"] or clock.parse(value.get("started")) is None or not isinstance(value.get("streams"), dict) or type(value.get("ok")) is not bool or not isinstance(value.get("completed"), str) or not isinstance(value.get("errors"), list) or not all(isinstance(error, str) for error in value["errors"]):
        raise StreamsError("invalid tick pass health report")
    for path, stream in value["streams"].items():
        if not isinstance(path, str) or not Path(path).is_absolute() or not isinstance(stream, dict) or not all(isinstance(stream.get(key), str) for key in ("id", "project", "started", "completed")) or type(stream.get("ok")) is not bool or not isinstance(stream.get("errors"), list) or not all(isinstance(error, str) for error in stream["errors"]):
            raise StreamsError("invalid per-stream tick health report")
        if any(stream[key] and clock.parse(stream[key]) is None for key in ("started", "completed")):
            raise StreamsError("invalid stream tick health timestamp")
    if value["completed"] and clock.parse(value["completed"]) is None:
        raise StreamsError("invalid tick completion timestamp")
    if value["ok"] and (not value["completed"] or any(not stream["completed"] or not stream["ok"] for stream in value["streams"].values())):
        raise StreamsError("successful tick health lacks complete successful stream results")
    return value

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from engine import StreamsError
from engine.project import _write, stream_lock

_HEADER = re.compile(rb" {0,3}(#{1,6})(?:[ \t]+(.*)|[ \t]*)")
_FENCE = re.compile(rb" {0,3}(`{3,}|~{3,})(.*)")
_CLOSING_HASHES = re.compile(rb"(?:[ \t]+|^)#+[ \t]*$")
_RATIFIED = re.compile(rb"ratified:(?:[ \t].*)?")


@dataclass(frozen=True)
class ByteSpan:
    start: int
    end: int


@dataclass(frozen=True)
class Section:
    name: str
    heading: ByteSpan
    body: ByteSpan


@dataclass(frozen=True)
class StreamState:
    source: bytes
    goals: Section
    rules: Section
    log: Section
    extras: tuple[Section, ...]
    authority: ByteSpan
    north_star: Section
    current_objective: Section
    charter: Section


@dataclass(frozen=True)
class _Heading:
    level: int
    name: str
    span: ByteSpan


def _headings(source: bytes) -> list[_Heading]:
    headings: list[_Heading] = []
    offset = 0
    fence = b""
    for line in source.splitlines(keepends=True):
        content = line.rstrip(b"\r\n")
        marker = _FENCE.fullmatch(content)
        if fence:
            if marker and marker[1][:1] == fence[:1] and len(marker[1]) >= len(fence) and not marker[2].strip(b" \t"):
                fence = b""
        elif marker and not (marker[1][:1] == b"`" and b"`" in marker[2]):
            fence = marker[1]
        else:
            heading = _HEADER.fullmatch(content)
            if heading:
                title = _CLOSING_HASHES.sub(b"", heading[2] or b"")
                name = title.rstrip(b" \t").decode("utf-8")
                headings.append(_Heading(len(heading[1]), name, ByteSpan(offset, offset + len(line))))
        offset += len(line)
    if fence:
        raise StreamsError("STATE has an unclosed code fence")
    return headings


def parse_state(source: bytes) -> StreamState:
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StreamsError("STATE is not valid UTF-8") from exc
    if b"\0" in source:
        raise StreamsError("STATE contains a NUL byte")
    headings = _headings(source)
    top = [heading for heading in headings if heading.level == 2]
    names = [heading.name for heading in top]
    if any(names.count(name) != 1 for name in ("Goals", "Rules", "Log")):
        raise StreamsError("STATE requires one Goals, Rules, and Log section")
    if len(set(names)) != len(names) or not all(names):
        raise StreamsError("STATE has duplicate or unnamed sections")
    if names[:2] != ["Goals", "Rules"] or names[-1] != "Log":
        raise StreamsError("STATE sections must be Goals, Rules, optional extras, then Log")
    if source[:top[0].span.start].strip():
        raise StreamsError("STATE has content before Goals")
    sections = tuple(
        Section(heading.name, heading.span, ByteSpan(
            heading.span.end, top[index + 1].span.start if index + 1 < len(top) else len(source),
        ))
        for index, heading in enumerate(top)
    )
    goals = sections[0]
    goal_headers = [
        heading for heading in headings
        if heading.level == 3 and goals.body.start <= heading.span.start < goals.body.end
    ]
    if [heading.name for heading in goal_headers] != ["North Star", "Current objective", "Charter"]:
        raise StreamsError("STATE Goals requires North Star, Current objective, and Charter headings in order")
    goal_sections = tuple(
        Section(heading.name, heading.span, ByteSpan(
            heading.span.end,
            goal_headers[index + 1].span.start if index + 1 < len(goal_headers) else goals.body.end,
        ))
        for index, heading in enumerate(goal_headers)
    )
    first_line = source[goals.body.start:goals.body.end].splitlines(keepends=True)[0]
    if not _RATIFIED.fullmatch(first_line.rstrip(b"\r\n")):
        raise StreamsError("STATE Goals must start with its ratified: marker")
    authority = ByteSpan(goals.body.start, goals.body.start + len(first_line))
    if source[authority.end:goal_sections[0].heading.start].strip():
        raise StreamsError("STATE Goals has content before North Star")
    north_star, current_objective, charter = goal_sections
    if not source[north_star.body.start:north_star.body.end].decode("utf-8").strip():
        raise StreamsError("STATE North Star is empty")
    return StreamState(
        source, goals, sections[1], sections[-1], sections[2:-1], authority,
        north_star, current_objective, charter,
    )


def resolve_current_goal(state: StreamState) -> str:
    objective = state.source[state.current_objective.body.start:state.current_objective.body.end].decode("utf-8").strip()
    if objective:
        return objective
    return state.source[state.north_star.body.start:state.north_star.body.end].decode("utf-8").strip()


def replace_current_objective(state: StreamState, objective: str) -> bytes:
    try:
        replacement = objective.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise StreamsError("current objective is not valid UTF-8") from exc
    heading = state.source[state.current_objective.heading.start:state.current_objective.heading.end]
    newline = b"\r\n" if heading.endswith(b"\r\n") else b"\n"
    if replacement and not replacement.endswith(b"\n"):
        replacement += newline
    span = state.current_objective.body
    candidate = state.source[:span.start] + replacement + state.source[span.end:]
    parsed = parse_state(candidate)
    if parsed.current_objective.body != ByteSpan(span.start, span.start + len(replacement)):
        raise StreamsError("current objective changes STATE section boundaries")
    return candidate


def update_current_objective(stream_dir: Path, objective: str) -> bool:
    with stream_lock(stream_dir):
        path = stream_dir / "STATE.md"
        if path.is_symlink():
            raise StreamsError("refusing a STATE.md symlink")
        try:
            source = path.read_bytes()
        except OSError as exc:
            raise StreamsError(f"could not read {path}: {exc}") from exc
        candidate = replace_current_objective(parse_state(source), objective)
        if candidate == source:
            return False
        _write(path, candidate.decode("utf-8"))
        return True

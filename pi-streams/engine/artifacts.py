from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import unicodedata
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path

from engine import StreamsError
from engine.project import STATE_SCHEMA, _sync_directory, _write, git_blob, load_stream_config, stream_lock

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


def parse_state(source: bytes, *, log_size: int | None = None) -> StreamState:
    try:
        source.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise StreamsError("STATE is not valid UTF-8") from exc
    if b"\0" in source:
        raise StreamsError("STATE contains a NUL byte")
    if log_size is not None and (type(log_size) is not int or not 0 <= log_size <= len(source)):
        raise StreamsError("invalid accepted Log size")
    headings = _headings(source if log_size is None else source[:len(source) - log_size])
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
    if log_size is not None and sections[-1].body.start != len(source) - log_size:
        raise StreamsError("accepted Log boundaries do not match STATE")
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
    parsed = parse_state(candidate, log_size=len(state.source) - state.log.body.start)
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
        data = _read_tick_data(stream_dir)
        state = _recover_log_locked(stream_dir, data)[1] if "state_log" in data else parse_state(source)
        source = state.source
        candidate = replace_current_objective(state, objective)
        if candidate == source:
            return False
        _write(path, candidate.decode("utf-8"))
        return True


@dataclass(frozen=True)
class LogEntry:
    occurrence: int
    start: int
    end: int
    sha256: str
    timestamp: str
    subject: str


@dataclass
class LogBook:
    version: int = 1
    next_occurrence: int = 1
    entries: list[LogEntry] = field(default_factory=list)
    receipts: dict[str, dict] = field(default_factory=dict)
    pending_history: list[dict[str, str]] = field(default_factory=list)


def _sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _timestamp(text: str) -> str:
    try:
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is None:
            raise ValueError("timezone required")
        return stamp.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    except (TypeError, ValueError) as exc:
        raise StreamsError("Log timestamp must include an ISO timezone") from exc


def _text(text: str) -> bytes:
    try:
        data = text.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise StreamsError("artifact text is not valid UTF-8") from exc
    if b"\0" in data:
        raise StreamsError("artifact text contains NUL")
    return data


def _read_tick_data(stream_dir: Path) -> dict:
    path = stream_dir / "log/tick-state.json"
    if path.is_symlink() or path.parent.is_symlink():
        raise StreamsError("refusing symlinked tick metadata")
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_bytes())
        if not isinstance(data, dict):
            raise ValueError("expected an object")
        return data
    except (OSError, ValueError) as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc


def _save_tick_data(stream_dir: Path, data: dict) -> None:
    _write(stream_dir / "log/tick-state.json", json.dumps(data, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    _sync_directory(stream_dir)


def _subject_slug(subject: str) -> str:
    text = unicodedata.normalize("NFKC", subject).casefold()
    words = "".join(char if char.isalnum() else "-" for char in text).split("-")
    return "-".join(word for word in words if word) or "entry"


def _history_path(stream_dir: Path, name: str) -> Path:
    match = re.fullmatch(r"\d{8}T\d{12}Z-(?:entry|rule-retired)-\d{8,}-(.+)-[0-9a-f]{16}\.md", name)
    if (not match or _subject_slug(match[1]) != match[1] or len(name.encode("utf-8")) > 255
            or Path(name).name != name):
        raise StreamsError("invalid engine history destination")
    path = stream_dir / "history" / name
    if path.parent.is_symlink() or path.is_symlink():
        raise StreamsError("refusing symlinked history")
    return path


def _book(raw: object) -> LogBook:
    try:
        if not isinstance(raw, dict) or type(raw["version"]) is not int or raw["version"] != 1:
            raise ValueError("unsupported Log metadata version")
        book = LogBook(raw["version"], raw["next_occurrence"],
                       [LogEntry(**item) for item in raw["entries"]], raw["receipts"], raw["pending_history"])
        if type(book.next_occurrence) is not int or book.next_occurrence < 1:
            raise ValueError("invalid next occurrence")
        offset = previous = 0
        for entry in book.entries:
            if (any(type(value) is not int for value in (entry.start, entry.end, entry.occurrence))
                    or entry.start != offset or entry.end <= offset
                    or not previous < entry.occurrence < book.next_occurrence
                    or not isinstance(entry.sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", entry.sha256)
                    or not isinstance(entry.subject, str) or not entry.subject.strip()
                    or any(char in entry.subject for char in "\r\n\0")
                    or _timestamp(entry.timestamp) != entry.timestamp):
                raise ValueError("invalid accepted Log occurrence")
            offset, previous = entry.end, entry.occurrence
        if not isinstance(book.receipts, dict) or not isinstance(book.pending_history, list):
            raise ValueError("invalid receipts/history metadata")
        for request, receipt in book.receipts.items():
            if (not isinstance(request, str) or not request or not isinstance(receipt, dict)
                    or type(receipt["occurrence"]) is not int or not 0 < receipt["occurrence"] < book.next_occurrence
                    or not re.fullmatch(r"[0-9a-f]{64}", receipt["intent"])):
                raise ValueError("invalid Log receipt")
        for item in book.pending_history:
            if (not isinstance(item, dict) or not isinstance(item["name"], str)
                    or not re.fullmatch(r"[0-9a-f]{64}", item["sha256"])):
                raise ValueError("invalid pending history")
        return book
    except (KeyError, TypeError, ValueError) as exc:
        raise StreamsError(f"invalid Log metadata: {exc}") from exc


def _checked_log(log: bytes, book: LogBook) -> None:
    if len(log) != (book.entries[-1].end if book.entries else 0):
        raise StreamsError("accepted Log length changed")
    for entry in book.entries:
        record = log[entry.start:entry.end]
        header = f"### {entry.timestamp} {entry.subject}\n".encode("utf-8")
        if _sha(record) != entry.sha256 or not record.startswith(header) or not record.endswith(b"\n"):
            raise StreamsError("accepted Log bytes changed; refusing to drop unregistered content")


def _checked_state(source: bytes, book: LogBook) -> StreamState:
    size = book.entries[-1].end if book.entries else 0
    state = parse_state(source, log_size=size)
    _checked_log(source[state.log.body.start:], book)
    return state


def _history_name(entry: LogEntry, kind: str, data: bytes) -> str:
    stamp = datetime.fromisoformat(entry.timestamp).strftime("%Y%m%dT%H%M%S%fZ")
    prefix = f"{stamp}-{kind}-{entry.occurrence:08d}-"
    suffix = f"-{_sha(data)[:16]}.md"
    room = 255 - len((prefix + suffix).encode("utf-8"))
    if room < len("entry"):
        raise StreamsError("history identity exceeds the filename component limit")
    slug = _subject_slug(entry.subject).encode("utf-8")[:room].decode("utf-8", errors="ignore").rstrip("-")
    return prefix + (slug or "entry") + suffix


def _decode_bytes(text: object) -> bytes:
    try:
        return base64.b64decode(text, validate=True)
    except (TypeError, ValueError) as exc:
        raise StreamsError("invalid journal bytes") from exc


def _history_write(stream_dir: Path, item: dict) -> None:
    path = _history_path(stream_dir, item["name"])
    data = _decode_bytes(item["bytes"])
    if _sha(data) != item["sha256"]:
        raise StreamsError("journal history hash mismatch")
    if path.exists():
        if path.read_bytes() != data:
            raise StreamsError(f"history collision: {path.name}")
        with path.open("rb") as handle:
            os.fsync(handle.fileno())
    else:
        _write(path, data.decode("utf-8"))
    if path.read_bytes() != data:
        raise StreamsError("history verification failed")
    _sync_directory(path.parent)
    _sync_directory(stream_dir)


def _state_bytes(state: StreamState, log: bytes, rules: bytes | None, book: LogBook) -> bytes:
    if rules is None:
        prefix = state.source[:state.log.body.start]
    else:
        prefix = (state.source[:state.rules.body.start] + rules
                  + state.source[state.rules.body.end:state.log.body.start])
    candidate = prefix + log
    parsed = _checked_state(candidate, book)
    if rules is not None and parsed.rules.body != ByteSpan(state.rules.body.start, state.rules.body.start + len(rules)):
        raise StreamsError("ruling changes STATE section boundaries")
    return candidate


def _check_journal(before: LogBook, after: LogBook, log: bytes, old_rules: bytes | None,
                   new_rules: bytes | None, history: list[dict]) -> None:
    _checked_log(log, after)
    contents = [_decode_bytes(item["bytes"]) for item in history]
    if any(_sha(content) != item["sha256"] for item, content in zip(history, contents)):
        raise StreamsError("journal history hash mismatch")
    if after.next_occurrence == before.next_occurrence:
        count = len(before.entries) - len(after.entries)
        if count <= 0 or len(history) != count or old_rules is not None or new_rules is not None:
            raise StreamsError("invalid rotation prefix plan")
        prefix = before.entries[count - 1].end
        expected = [LogEntry(item.occurrence, item.start - prefix, item.end - prefix,
                             item.sha256, item.timestamp, item.subject) for item in before.entries[count:]]
        if after.entries != expected or after.receipts != before.receipts:
            raise StreamsError("rotation changed retained occurrences")
        for entry, item, content in zip(before.entries[:count], history, contents):
            if item["name"] != _history_name(entry, "entry", content) or _sha(content) != entry.sha256:
                raise StreamsError("rotation destination does not preserve the exact prefix")
        _checked_log(b"".join(contents) + log, before)
    elif after.next_occurrence == before.next_occurrence + 1:
        if (len(after.entries) != len(before.entries) + 1 or after.entries[:-1] != before.entries
                or after.entries[-1].occurrence != before.next_occurrence):
            raise StreamsError("invalid appended occurrence plan")
        _checked_log(log[:after.entries[-1].start], before)
        added = set(after.receipts) - set(before.receipts)
        if (len(added) != 1 or any(after.receipts.get(key) != value for key, value in before.receipts.items())
                or after.receipts[next(iter(added))]["occurrence"] != before.next_occurrence):
            raise StreamsError("invalid appended receipt plan")
        if (old_rules is None) != (new_rules is None) or len(history) > 1:
            raise StreamsError("invalid ruling history plan")
        if history:
            retired = contents[0]
            if (old_rules is None or not retired or old_rules.count(retired) != 1 or retired in new_rules
                    or history[0]["name"] != _history_name(after.entries[-1], "rule-retired", retired)):
                raise StreamsError("retired history does not identify the exact old rule")
            left, right = old_rules.split(retired, 1)
            if not new_rules.startswith(left) or not new_rules.endswith(right) or len(new_rules) < len(left) + len(right):
                raise StreamsError("ruling changed unrelated Rules bytes")
        elif old_rules is not None and not new_rules.startswith(old_rules):
            raise StreamsError("new ruling changed existing Rules bytes")
    else:
        raise StreamsError("invalid artifact occurrence transition")
    expected_history = list(before.pending_history)
    for item in history:
        record = {"name": item["name"], "sha256": item["sha256"]}
        if record not in expected_history:
            expected_history.append(record)
    if after.pending_history != expected_history:
        raise StreamsError("pending history does not match the journal destinations")


def _recover_log_locked(stream_dir: Path, data: dict) -> tuple[LogBook, StreamState]:
    path = stream_dir / "STATE.md"
    if path.is_symlink():
        raise StreamsError("refusing a STATE.md symlink")
    source = path.read_bytes()
    raw = data["state_log"]
    book = _book(raw)
    pending = raw.get("pending")
    if pending is not None:
        try:
            before, after = _book(pending["before"]), _book(pending["after"])
            log = _decode_bytes(pending["log"])
            old_rules = _decode_bytes(pending["rules_before"]) if pending["rules_before"] is not None else None
            new_rules = _decode_bytes(pending["rules_after"]) if pending["rules_after"] is not None else None
            _check_journal(before, after, log, old_rules, new_rules, pending["history"])
            try:
                state = _checked_state(source, before)
                already_published = False
            except StreamsError:
                state = _checked_state(source, after)
                already_published = True
            if old_rules is not None:
                expected = new_rules if already_published else old_rules
                if source[state.rules.body.start:state.rules.body.end] != expected:
                    raise StreamsError("Rules changed during a pending artifact operation")
            candidate = _state_bytes(state, log, new_rules, after)
            for item in pending["history"]:
                _history_write(stream_dir, item)
            if source != candidate:
                _write(path, candidate.decode("utf-8"))
            if path.read_bytes() != candidate:
                raise StreamsError("STATE publication verification failed")
            data["state_log"] = asdict(after)
            _save_tick_data(stream_dir, data)
            book, source = after, candidate
        except (KeyError, TypeError, ValueError) as exc:
            raise StreamsError(f"invalid artifact journal: {exc}") from exc
    state = _checked_state(source, book)
    for item in book.pending_history:
        path = _history_path(stream_dir, item["name"])
        if not path.is_file() or _sha(path.read_bytes()) != item["sha256"]:
            raise StreamsError("pending history bytes changed")
    return book, state


def _open_log_locked(stream_dir: Path) -> tuple[dict, LogBook, StreamState]:
    if load_stream_config(stream_dir / "stream.toml").state_schema != STATE_SCHEMA:
        raise StreamsError("canonical STATE schema required; explicit migration is needed")
    data = _read_tick_data(stream_dir)
    if "state_log" not in data:
        state = parse_state((stream_dir / "STATE.md").read_bytes())
        if state.source[state.log.body.start:]:
            raise StreamsError("unregistered Log content requires explicit migration")
        data["state_log"] = asdict(LogBook())
    book, state = _recover_log_locked(stream_dir, data)
    return data, book, state


def _publish_log_locked(stream_dir: Path, data: dict, book: LogBook, state: StreamState,
                        after: LogBook, log: bytes, *, rules: bytes | None = None,
                        history: list[tuple[str, bytes]] = ()) -> None:
    _state_bytes(state, log, rules, after)
    destinations = []
    for name, content in history:
        _history_path(stream_dir, name)
        item = {"name": name, "sha256": _sha(content)}
        if item not in after.pending_history:
            after.pending_history.append(item)
        destinations.append({**item, "bytes": base64.b64encode(content).decode("ascii")})
    pending = {"before": asdict(book), "after": asdict(after),
               "log": base64.b64encode(log).decode("ascii"),
               "rules_before": base64.b64encode(state.source[state.rules.body.start:state.rules.body.end]).decode("ascii") if rules is not None else None,
               "rules_after": base64.b64encode(rules).decode("ascii") if rules is not None else None,
               "history": destinations}
    data["state_log"] = {**asdict(book), "pending": pending}
    _save_tick_data(stream_dir, data)
    _recover_log_locked(stream_dir, data)


def _receipt(book: LogBook, request: str, intent: str) -> int | None:
    if not request or any(char in request for char in "\r\n\0"):
        raise StreamsError("a stable single-line request ID is required")
    old = book.receipts.get(request)
    if old is not None and old["intent"] != intent:
        raise StreamsError("request ID reused for different artifact intent")
    return old["occurrence"] if old is not None else None


def _append_locked(stream_dir: Path, data: dict, book: LogBook, state: StreamState,
                   at: str, subject: str, body: str, request: str, intent: str,
                   *, rules: bytes | None = None, retired: bytes | None = None) -> int:
    stamp = _timestamp(at)
    if not subject.strip() or any(char in subject for char in "\r\n\0"):
        raise StreamsError("Log subject must be a nonempty single line")
    old = _receipt(book, request, intent)
    if old is not None:
        return old
    content = _text(f"### {stamp} {subject}\n{body}")
    if not content.endswith(b"\n"):
        content += b"\n"
    log = state.source[state.log.body.start:]
    entry = LogEntry(book.next_occurrence, len(log), len(log) + len(content), _sha(content), stamp, subject)
    after = _book(asdict(book))
    after.entries.append(entry)
    after.next_occurrence += 1
    after.receipts[request] = {"intent": intent, "occurrence": entry.occurrence}
    history = [(_history_name(entry, "rule-retired", retired), retired)] if retired is not None else []
    _publish_log_locked(stream_dir, data, book, state, after, log + content, rules=rules, history=history)
    return entry.occurrence


def append_log(stream_dir: Path, at: str, subject: str, body: str, *, request_id: str) -> int:
    intent = _sha(_text(json.dumps(["append", subject, body], ensure_ascii=False)))
    with stream_lock(stream_dir):
        data, book, state = _open_log_locked(stream_dir)
        return _append_locked(stream_dir, data, book, state, at, subject, body, request_id, intent)


def record_ruling(stream_dir: Path, at: str, subject: str, ruling: str,
                  *, notice_id: str, supersedes: str | None = None) -> int:
    intent = _sha(_text(json.dumps(["ruling", subject, ruling, supersedes], ensure_ascii=False)))
    request = "ruling:" + notice_id
    if not notice_id:
        raise StreamsError("human notice provenance is required")
    with stream_lock(stream_dir):
        data, book, state = _open_log_locked(stream_dir)
        old = _receipt(book, request, intent)
        if old is not None:
            return old
        current = state.source[state.rules.body.start:state.rules.body.end]
        replacement = _text(ruling)
        if replacement and not replacement.endswith(b"\n"):
            replacement += b"\n"
        retired = _text(supersedes) if supersedes is not None else None
        if retired is not None:
            if not retired or current.count(retired) != 1 or retired in replacement:
                raise StreamsError("superseded rule must identify one exact retired source span")
            rules = current.replace(retired, replacement, 1)
        else:
            if not replacement:
                raise StreamsError("new ruling is empty")
            rules = current + (b"\n" if current and not current.endswith(b"\n") else b"") + replacement
        body = f"Human notice {notice_id}\n{ruling}"
        if supersedes is not None:
            body += f"\nSuperseded exact text:\n{supersedes}"
        return _append_locked(stream_dir, data, book, state, at, subject, body, request, intent,
                              rules=rules, retired=retired)


def _rotate_log_locked(stream_dir: Path) -> list[str]:
    if load_stream_config(stream_dir / "stream.toml").state_schema == 0:
        return []
    data, book, state = _open_log_locked(stream_dir)
    overflow = max(0, len(book.entries) - 30)
    if overflow:
        log = state.source[state.log.body.start:]
        removed = book.entries[:overflow]
        prefix = removed[-1].end
        after = _book(asdict(book))
        after.entries = [LogEntry(entry.occurrence, entry.start - prefix, entry.end - prefix,
                                  entry.sha256, entry.timestamp, entry.subject) for entry in book.entries[overflow:]]
        history = [(_history_name(entry, "entry", log[entry.start:entry.end]), log[entry.start:entry.end]) for entry in removed]
        _publish_log_locked(stream_dir, data, book, state, after, log[prefix:], history=history)
        book = _book(data["state_log"])
    return ["history/" + item["name"] for item in book.pending_history]


def rotate_log(stream_dir: Path) -> list[str]:
    with stream_lock(stream_dir):
        return _rotate_log_locked(stream_dir)


def _acknowledge_history_locked(stream_dir: Path) -> None:
    data = _read_tick_data(stream_dir)
    if "state_log" not in data:
        return
    book, _state = _recover_log_locked(stream_dir, data)
    if not book.pending_history:
        return
    for item in book.pending_history:
        committed = git_blob(stream_dir, "HEAD:history/" + item["name"])
        if _sha(committed) != item["sha256"]:
            raise StreamsError("committed history does not match durable artifact bytes")
    book.pending_history = []
    data["state_log"] = asdict(book)
    _save_tick_data(stream_dir, data)

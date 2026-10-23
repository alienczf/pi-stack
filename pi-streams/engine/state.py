from __future__ import annotations

import contextlib
import hashlib
import json
import os
import re
import tempfile
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import UUID

from engine import StreamsError
from engine.project import stream_lock

NAME = re.compile(r"\d{8}T\d{6}\.\d{6}Z-[a-z0-9]+(?:-[a-z0-9]+)*\.md\Z")
STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z\Z")
STATUSES = {"active", "waiting", "paused", "complete", "unset"}
ENTRY_FIELDS = {
    "sent_text_sha256": {"command", "sent_text_sha256", "success", "error", "data", "messages"},
    "goals_rules_sha256": {"command", "body", "original_entries", "goals_rules_sha256", "result"},
    "trigger": {
        "command", "trigger", "percent", "threshold_percent", "before_entry",
        "dump_entry", "compaction_entry", "next_command", "result", "error",
    },
    "invocation": {
        "original_entries", "later_instruction_entries", "target", "invocation",
        "result", "findings", "proof_entries", "review",
    },
    "media_type": {"original_entries", "media_type", "text", "sha256"},
}


@dataclass(frozen=True)
class Work:
    summary: str
    original_entry: str
    required: str | None = None
    workers: tuple[dict, ...] = ()
    next: str | None = None
    waiting_for: str | None = None


@dataclass(frozen=True)
class Goals:
    north_star: str
    original_entry: str | None = None
    objective: str | None = None
    status: str = "unset"
    work: tuple[Work, ...] = ()


@dataclass(frozen=True)
class Rule:
    text: str
    original_entry: str
    applies_to: str


@dataclass(frozen=True)
class Entry:
    timestamp: str
    subject: str
    file: str
    session: str | None
    command: str | None
    prime_entry: str | None
    body: dict
    text: str


@dataclass(frozen=True)
class State:
    goals: Goals
    rules: tuple[Rule, ...]
    log: tuple[Entry, ...]
    goals_text: str
    rules_text: str
    text: str

    @property
    def sha256(self) -> str:
        return sha256(self.text)

    @property
    def goals_rules_sha256(self) -> str:
        return sha256(self.goals_text + self.rules_text)


def sha256(text: str) -> str:
    try:
        return hashlib.sha256(text.encode("utf-8")).hexdigest()
    except UnicodeError as exc:
        raise StreamsError("invalid UTF-8") from exc


def _json(value: object) -> str:
    try:
        return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid JSON: {exc}") from exc


def _pairs(items: list[tuple]) -> dict:
    result = {}
    for key, value in items:
        if key in result:
            raise StreamsError(f"duplicate JSON key: {key}")
        result[key] = value
    return result


def _decode(text: str):
    try:
        return json.loads(text, object_pairs_hook=_pairs, parse_constant=lambda value: _fail(f"nonfinite JSON: {value}"))
    except (ValueError, TypeError) as exc:
        raise StreamsError(f"invalid JSON: {exc}") from exc


def _fail(reason: str):
    raise StreamsError(reason)


def _string(value: object, *, nullable: bool = False) -> None:
    if not isinstance(value, str) and not (nullable and value is None):
        raise StreamsError("expected a JSON string" + (" or null" if nullable else ""))


def _line(value: str) -> None:
    if not isinstance(value, str) or not value or any(c in value for c in "\n\r"):
        raise StreamsError("expected nonempty one-line text")


def _name(value: object) -> str:
    if not isinstance(value, str) or not NAME.fullmatch(value):
        raise StreamsError("invalid entry basename")
    try:
        datetime.strptime(value[:23], "%Y%m%dT%H%M%S.%fZ")
    except ValueError as exc:
        raise StreamsError("invalid entry filename timestamp") from exc
    return value


def _uuid(value: str) -> None:
    try:
        if str(UUID(value)) != value:
            raise ValueError()
    except (ValueError, TypeError, AttributeError) as exc:
        raise StreamsError("command must be a canonical UUID") from exc


def _timestamp(value: str) -> None:
    if not isinstance(value, str) or not STAMP.fullmatch(value):
        raise StreamsError("expected RFC 3339 UTC timestamp")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise StreamsError("invalid UTC timestamp") from exc


def _text(text: str) -> None:
    if not isinstance(text, str) or "\r" in text or not text.endswith("\n") or text.endswith("\n\n"):
        raise StreamsError("expected UTF-8/LF text with one final LF")
    try:
        text.encode("utf-8")
    except UnicodeError as exc:
        raise StreamsError("invalid UTF-8") from exc


def _headings(text: str) -> list[tuple[int, str]]:
    found = []
    fence = None
    offset = 0
    for line in text.split("\n"):
        match = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", line)
        if fence:
            if match and match[1][0] == fence[0] and len(match[1]) >= len(fence) and not match[2].strip():
                fence = None
        elif match:
            fence = match[1]
        elif line.startswith("## ") or line.startswith("### "):
            found.append((offset, line))
        offset += len(line) + 1
    if fence:
        raise StreamsError("unclosed Markdown fence")
    return found


def _field(line: str, prefix: str):
    if not line.startswith(prefix):
        raise StreamsError(f"expected {prefix}")
    return _decode(line[len(prefix):])


def _parse_goals(text: str) -> Goals:
    lines = [line for line in text.split("\n") if line]
    if len(lines) < 7 or lines[:2] != ["## Goals", "### North Star"] or lines[4] != "### Current objective":
        raise StreamsError("malformed Goals")
    north = _field(lines[2], "Text: ")
    original = _field(lines[3], "Original entry: ")
    objective = _field(lines[5], "Text: ")
    if not lines[6].startswith("Status: "):
        raise StreamsError("missing objective status")
    status = lines[6][8:]
    _string(north)
    _string(objective, nullable=True)
    if original is not None:
        _name(original)
    if status not in STATUSES or (objective is None) != (status == "unset"):
        raise StreamsError("invalid objective/status")
    work = []
    for start in range(7, len(lines), 6):
        block = lines[start:start + 6]
        if len(block) != 6 or not block[0].startswith("- [ ] "):
            raise StreamsError("malformed whole-message work item")
        summary = block[0][6:]
        _line(summary)
        ref = _name(_field(block[1], "  Original entry: "))
        required = _field(block[2], "  Required: ")
        workers = _field(block[3], "  Workers: ")
        next_step = _field(block[4], "  Next: ")
        waiting = _field(block[5], "  Waiting for: ")
        for value in (required, next_step, waiting):
            _string(value, nullable=True)
        if not isinstance(workers, list) or any(not isinstance(w, dict) or set(w) != {"session", "worktree", "work"} for w in workers):
            raise StreamsError("invalid worker assignment")
        for worker in workers:
            for value in worker.values():
                _string(value)
        work.append(Work(summary, ref, required, tuple(workers), next_step, waiting))
    if len({item.original_entry for item in work}) != len(work):
        raise StreamsError("duplicate whole-message Goals item")
    return Goals(north, original, objective, status, tuple(work))


def _parse_rules(text: str) -> tuple[Rule, ...]:
    lines = [line for line in text.split("\n") if line]
    if not lines or lines[0] != "## Rules":
        raise StreamsError("missing Rules")
    rules = []
    for start in range(1, len(lines), 3):
        block = lines[start:start + 3]
        if len(block) != 3 or not block[0].startswith("- "):
            raise StreamsError("malformed Rule")
        _line(block[0][2:])
        original = _name(_field(block[1], "  Original entry: "))
        applies = _field(block[2], "  Applies to: ")
        _string(applies)
        rules.append(Rule(block[0][2:], original, applies))
    if len(set(rules)) != len(rules):
        raise StreamsError("duplicate Rule")
    return tuple(rules)


def _parse_entry(text: str) -> Entry:
    _text(text)
    lines = text.split("\n")
    match = re.fullmatch(r"### (\S+) (.+)", lines[0])
    if not match or len(lines) < 9:
        raise StreamsError("malformed Log entry")
    stamp, subject = match.groups()
    _timestamp(stamp)
    file = _name(_field(lines[1], "File: "))
    session = _field(lines[2], "Prime session: ")
    command = _field(lines[3], "Prime command: ")
    native = _field(lines[4], "Prime entry: ")
    for value in (session, native):
        _string(value, nullable=True)
    if command is not None:
        _uuid(command)
        if not file[24:].startswith(command + "-"):
            raise StreamsError("entry basename must include its command UUID")
    fence = re.fullmatch(r"(`{3,}|~{3,})json", lines[5])
    if not fence or lines[-2] != fence[1]:
        raise StreamsError("entry body must be fenced JSON")
    body = _decode("\n".join(lines[6:-2]))
    if not isinstance(body, dict):
        raise StreamsError("entry body must be a JSON object")
    _json(body)
    for marker, fields in ENTRY_FIELDS.items():
        if marker in body and not fields <= body.keys():
            raise StreamsError(f"malformed entry fields for {marker}")
    if "send_as" in body or ("received_at" in body and body.get("text") is not None):
        if set(body) != {"text", "sha256", "sender", "received_at", "send_as"}:
            raise StreamsError("malformed original message")
        _string(body["text"])
        _string(body["sender"], nullable=True)
        _timestamp(body["received_at"])
        if body["send_as"] not in {"steer", "followUp"} or body["sha256"] != sha256(body["text"]) or command is None:
            raise StreamsError("invalid original message identity/hash/lane")
    elif "received_at" in body:
        if not {"text", "command", "sender", "received_at"} <= body.keys() or body["text"] is not None:
            raise StreamsError("malformed operator stop")
        control = body["command"]
        if not isinstance(control, dict) or set(control) != {"type", "session"} or control["type"] != "abort":
            raise StreamsError("invalid stop control")
        _string(control["session"])
        _string(body["sender"], nullable=True)
        _timestamp(body["received_at"])
    if "media_type" in body:
        _string(body["text"])
        _string(body["media_type"])
        if body["sha256"] != sha256(body["text"]):
            raise StreamsError("text proof hash differs")
    if "original_entries" in body:
        if not isinstance(body["original_entries"], list):
            raise StreamsError("original_entries must be an array")
        for ref in body["original_entries"]:
            _name(ref)
    return Entry(stamp, subject, file, session, command, native, body, text)


def parse_state(text: str) -> State:
    _text(text)
    headings = _headings(text)
    sections = [(pos, line) for pos, line in headings if line.startswith("## ")]
    if [line for _, line in sections] != ["## Goals", "## Rules", "## Log"] or sections[0][0] != 0:
        raise StreamsError("STATE must have exactly Goals, Rules, Log in order")
    rules_at, log_at = sections[1][0], sections[2][0]
    goals_text, rules_text = text[:rules_at], text[rules_at:log_at]
    goals = _parse_goals(goals_text)
    rules = _parse_rules(rules_text)
    starts = [pos for pos, line in headings if pos > log_at and line.startswith("### ")]
    log = []
    previous = log_at + len("## Log\n")
    for index, start in enumerate(starts):
        if text[previous:start].strip():
            raise StreamsError("unexpected Log text")
        end = starts[index + 1] if index + 1 < len(starts) else len(text)
        raw = text[start:end].rstrip("\n") + "\n"
        log.append(_parse_entry(raw))
        previous = end
    if not starts and text[previous:].strip():
        raise StreamsError("unexpected Log text")
    if len({entry.file for entry in log}) != len(log):
        raise StreamsError("duplicate Log entry name")
    return State(goals, rules, tuple(log), goals_text, rules_text, text)


def _render_goals(goals: Goals) -> str:
    lines = [
        "## Goals", "### North Star", f"Text: {_json(goals.north_star)}",
        f"Original entry: {_json(goals.original_entry)}", "", "### Current objective",
        f"Text: {_json(goals.objective)}", f"Status: {goals.status}", "",
    ]
    for work in goals.work:
        lines.extend([
            f"- [ ] {work.summary}", f"  Original entry: {_json(work.original_entry)}",
            f"  Required: {_json(work.required)}", f"  Workers: {_json(list(work.workers))}",
            f"  Next: {_json(work.next)}", f"  Waiting for: {_json(work.waiting_for)}", "",
        ])
    return "\n".join(lines) + "\n"


def _render_rules(rules: tuple[Rule, ...]) -> str:
    lines = ["## Rules"]
    for rule in rules:
        lines.extend([f"- {rule.text}", f"  Original entry: {_json(rule.original_entry)}", f"  Applies to: {_json(rule.applies_to)}"])
    return "\n".join(lines) + "\n\n"


def render_state(state: State) -> str:
    return state.goals_text + state.rules_text + "## Log\n" + ("\n" + "\n".join(entry.text for entry in state.log) if state.log else "")


def _path(stream: Path, *parts: str) -> Path:
    if stream.is_symlink():
        raise StreamsError("symlink stream is not supported")
    path = stream
    for part in parts:
        path = path / part
        if path.is_symlink():
            raise StreamsError(f"refusing symlink: {path.name}")
    if not path.resolve().is_relative_to(stream.resolve()):
        raise StreamsError("path escapes stream")
    return path


def _read(path: Path) -> str:
    try:
        return path.read_bytes().decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise StreamsError(f"could not read {path.name}: {exc}") from exc


def _entries(stream: Path, state: State) -> dict[str, Entry]:
    entries = {entry.file: entry for entry in state.log}
    history = _path(stream, "history")
    if history.exists():
        if not history.is_dir():
            raise StreamsError("history is not a directory")
        for path in sorted(history.iterdir()):
            _name(path.name)
            entry = _parse_entry(_read(_path(stream, "history", path.name)))
            if entry.file != path.name:
                raise StreamsError("history filename differs from entry reference")
            if entry.file in entries and entry.text != entries[entry.file].text:
                raise StreamsError("unequal existing history bytes")
            entries[entry.file] = entry
    identities = set()
    for entry in entries.values():
        if entry.command is not None:
            purpose = entry.file[61:-3]
            identity = (entry.command, purpose)
            if identity in identities:
                raise StreamsError("duplicate command/purpose")
            identities.add(identity)
    return entries


def _original(entry: Entry) -> bool:
    return "received_at" in entry.body and "send_as" in entry.body


def _explained(original: Entry, entries: dict[str, Entry]) -> bool:
    fields = {"original_entries", "later_instruction_entries", "target", "invocation", "result", "findings", "proof_entries", "review"}
    for answer in entries.values():
        body = answer.body
        if not fields <= body.keys() or original.file not in body["original_entries"]:
            continue
        result = body["result"]
        if isinstance(result, dict) and result.get("status") == "complete":
            computed = result.get("computed")
            if (isinstance(computed, dict) and computed.get("exit") == 0
                    and body["invocation"] == {"argv": computed.get("argv"), "cwd": computed.get("cwd")}
                    and result.get("source_hashes", {}).get(original.file) == sha256(original.text)
                    and isinstance(result.get("binding_sha256"), str) and len(result["binding_sha256"]) == 64
                    and body["proof_entries"] and body["findings"]):
                return True
        if not isinstance(result, dict) or result.get("status") not in {"cancelled", "informational"}:
            continue
        if not isinstance(body["findings"], str) or not body["findings"].strip():
            continue
        sources = body["later_instruction_entries"]
        if not isinstance(sources, list) or not sources:
            continue
        for ref in sources:
            source = entries.get(ref) if isinstance(ref, str) else None
            if source is None or not _original(source) or source.body["sender"] is None:
                break
            if datetime.fromisoformat(source.timestamp.replace("Z", "+00:00")) <= datetime.fromisoformat(original.timestamp.replace("Z", "+00:00")):
                break
        else:
            return True
    return False


def _preserved(state: State, entries: dict[str, Entry]) -> None:
    refs = {work.original_entry for work in state.goals.work}
    for ref in refs:
        if ref not in entries or not _original(entries[ref]):
            raise StreamsError("Goals must reference a whole original message")
    for ref, entry in entries.items():
        if _original(entry) and ref not in refs and not _explained(entry, entries):
            raise StreamsError("whole original message remains requested; checked close required")
    if state.goals.original_entry is not None and state.goals.original_entry not in entries:
        raise StreamsError("missing North Star source")
    for rule in state.rules:
        source = entries.get(rule.original_entry)
        if source is None or not _original(source) or source.body["sender"] is None:
            raise StreamsError("Rule needs a trusted human source")


def check_state(stream: Path, *, expect: str | None = None) -> State:
    agents = _read(_path(stream, "AGENTS.md"))
    _text(agents)
    state = parse_state(_read(_path(stream, "STATE.md")))
    if expect is not None and state.sha256 != expect:
        raise StreamsError("stale STATE hash")
    if len(state.log) > 30:
        raise StreamsError("Log exceeds 30 entries")
    _preserved(state, _entries(stream, state))
    return state


def check_current_text(stream: Path, expected: str) -> State:
    state = check_state(stream)
    if state.goals_rules_sha256 != expected:
        raise StreamsError("stale Goals/Rules")
    return state


def read_entry(stream: Path, name: str) -> str:
    _name(name)
    state = parse_state(_read(_path(stream, "STATE.md")))
    found = _entries(stream, state).get(name)
    if found is None:
        raise StreamsError("entry not found")
    return found.text


def _sync_dir(path: Path) -> None:
    fd = os.open(path, os.O_RDONLY | os.O_DIRECTORY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def _publish(path: Path, text: str, *, immutable: bool = False) -> None:
    data = text.encode("utf-8")
    try:
        fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    except OSError as exc:
        raise StreamsError(f"{path.name}: not published: {exc}") from exc
    tmp = Path(temporary)
    published = False
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        if immutable:
            try:
                os.link(tmp, path)
                published = True
            except FileExistsError:
                if path.is_symlink() or path.read_bytes() != data:
                    raise StreamsError("unequal existing history bytes")
        else:
            os.replace(tmp, path)
            published = True
        _sync_dir(path.parent)
        if path.read_bytes() != data:
            raise StreamsError("publication readback differs")
    except OSError as exc:
        status = "unknown after publication" if published else "not published"
        raise StreamsError(f"{path.name}: {status}: {exc}") from exc
    finally:
        tmp.unlink(missing_ok=True)


def _archive(stream: Path, entry: Entry) -> str:
    history = _path(stream, "history")
    try:
        history.mkdir(exist_ok=True)
        _sync_dir(stream)
    except OSError as exc:
        raise StreamsError(f"history not published: {exc}") from exc
    _publish(_path(stream, "history", entry.file), entry.text, immutable=True)
    return entry.file


def _entry(
    subject: str, body: dict, *, session: str | None = None,
    command: str | None = None, prime_entry: str | None = None,
    purpose: str = "note", now: str | None = None,
) -> Entry:
    _line(subject)
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", purpose):
        raise StreamsError("invalid entry purpose")
    stamp = now or datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
    _timestamp(stamp)
    file_stamp = datetime.fromisoformat(stamp.replace("Z", "+00:00")).strftime("%Y%m%dT%H%M%S.%fZ")
    slug = f"{command}-{purpose}" if command else purpose
    file = f"{file_stamp}-{slug}.md"
    text = "\n".join([
        f"### {stamp} {subject}", f"File: {_json(file)}",
        f"Prime session: {_json(session)}", f"Prime command: {_json(command)}",
        f"Prime entry: {_json(prime_entry)}", "```json", _json(body), "```", "",
    ])
    return _parse_entry(text)


def _repeat(entries: dict[str, Entry], proposed: Entry) -> Entry | None:
    suffix = proposed.file[24:]
    for entry in entries.values():
        if proposed.command is not None and entry.command == proposed.command and entry.file[24:] == suffix:
            if (entry.subject, entry.session, entry.prime_entry, entry.body) != (proposed.subject, proposed.session, proposed.prime_entry, proposed.body):
                raise StreamsError("command/purpose conflicts with saved bytes or target")
            return entry
    return None


def _result(state: State, history: list[str], entry: Entry | None = None) -> dict:
    result = {"success": True, "reason": "checked", "state_sha256": state.sha256, "history_files": history}
    if entry:
        result["entry"] = entry.file
    return result


def _write_state(stream: Path, previous: State, proposed: State, *, archive: tuple[Entry, ...] = ()) -> dict:
    current = _read(_path(stream, "STATE.md"))
    if sha256(current) != previous.sha256:
        raise StreamsError("stale STATE hash")
    entries = _entries(stream, previous)
    for entry in proposed.log:
        if entry.file in entries and entry.text != entries[entry.file].text:
            raise StreamsError("existing entry bytes changed")
        entries[entry.file] = entry
    _preserved(proposed, entries)
    overflow = proposed.log[:-30]
    retained = proposed.log[-30:]
    final = replace(proposed, log=retained)
    text = render_state(final)
    parsed = parse_state(text)
    history = [_archive(stream, entry) for entry in (*archive, *overflow)]
    _publish(_path(stream, "STATE.md"), text)
    checked = check_state(stream, expect=parsed.sha256)
    return _result(checked, history)


def save_message(
    stream: Path, *, text: str, command_id: str, session_id: str,
    sender: str | None, send_as: str, received_at: str | None = None,
    locked: bool = False,
) -> dict:
    _string(text)
    _string(session_id)
    _string(sender, nullable=True)
    _string(send_as)
    _uuid(command_id)
    if not session_id or send_as not in {"steer", "followUp"}:
        raise StreamsError("invalid session or lane")
    sha256(text)
    with contextlib.nullcontext() if locked else stream_lock(stream):
        state = check_state(stream)
        entries = _entries(stream, state)
        existing = [entry for entry in entries.values() if entry.command == command_id and _original(entry)]
        if existing:
            entry = existing[0]
            if (entry.body["text"], entry.session, entry.body["sender"], entry.body["send_as"]) != (text, session_id, sender, send_as):
                raise StreamsError("command UUID conflicts with original text, target, sender or lane")
            return _result(state, [], entry)
        stamp = received_at or datetime.now(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")
        body = {"text": text, "sha256": sha256(text), "sender": sender, "received_at": stamp, "send_as": send_as}
        entry = _entry("Original message", body, session=session_id, command=command_id, purpose="original", now=stamp)
        work = Work(f"Unread message {command_id}", entry.file)
        goals = replace(state.goals, work=state.goals.work + (work,))
        proposed = replace(state, goals=goals, goals_text=_render_goals(goals), log=state.log + (entry,))
        result = _write_state(stream, state, proposed)
        result["entry"] = entry.file
        return result


def append_log(
    stream: Path, *, subject: str, body: dict, session_id: str | None = None,
    command_id: str | None = None, prime_entry: str | None = None,
    purpose: str = "note", expect: str | None = None, locked: bool = False,
) -> dict:
    with contextlib.nullcontext() if locked else stream_lock(stream):
        state = check_state(stream, expect=expect)
        entry = _entry(subject, body, session=session_id, command=command_id, prime_entry=prime_entry, purpose=purpose)
        if _original(entry):
            raise StreamsError("original messages must use save_message")
        if isinstance(body.get("result"), dict) and body["result"].get("status") == "complete":
            raise StreamsError("computed completion must use close_work")
        repeated = _repeat(_entries(stream, state), entry)
        if repeated:
            return _result(state, [], repeated)
        result = _write_state(stream, state, replace(state, log=state.log + (entry,)))
        result["entry"] = entry.file
        return result


def _goals_input(value: dict | Goals) -> Goals:
    if isinstance(value, Goals):
        return value
    try:
        north, objective = value["north_star"], value["current_objective"]
        work = tuple(
            Work(item["summary"], item["original_entry"], item["required"],
                 tuple(item["workers"]), item["next"], item["waiting_for"])
            for item in value["work"]
        )
        return Goals(north["text"], north["original_entry"], objective["text"], objective["status"], work)
    except (KeyError, TypeError) as exc:
        raise StreamsError("invalid Goals update") from exc


def update_state(
    stream: Path, *, expect: str, goals: dict | Goals | None,
    rules: list[dict] | tuple[Rule, ...] | None, entry: dict, locked: bool = False,
) -> dict:
    with contextlib.nullcontext() if locked else stream_lock(stream):
        state = check_state(stream, expect=expect)
        entries = _entries(stream, state)
        try:
            refs = entry["original_entries"]
            if not isinstance(refs, list):
                raise StreamsError("original_entries must be an array")
            for ref in refs:
                if _name(ref) not in entries or not _original(entries[ref]):
                    raise StreamsError("missing original update source")
            note_body = dict(entry["body"])
            if isinstance(note_body.get("result"), dict) and note_body["result"].get("status") == "complete":
                raise StreamsError("whole original message requires computed close_work")
            if "original_entries" in note_body and note_body["original_entries"] != refs:
                raise StreamsError("conflicting original update sources")
            note_body["original_entries"] = refs
            note = _entry(entry["subject"], note_body, purpose="update")
            new_goals = state.goals if goals is None else _goals_input(goals)
            new_rules = state.rules if rules is None else tuple(
                rule if isinstance(rule, Rule) else Rule(rule["text"], rule["original_entry"], rule["applies_to"])
                for rule in rules
            )
        except (KeyError, TypeError) as exc:
            raise StreamsError("malformed state update") from exc
        proposed = replace(
            state, goals=new_goals, rules=new_rules,
            goals_text=state.goals_text if goals is None else _render_goals(new_goals),
            rules_text=state.rules_text if rules is None else _render_rules(new_rules),
            log=state.log + (note,),
        )
        proposed = parse_state(render_state(proposed))
        retired = []
        for rule in state.rules:
            if rule in new_rules:
                continue
            original_time = datetime.fromisoformat(entries[rule.original_entry].timestamp.replace("Z", "+00:00"))
            later = [
                entries[ref] for ref in refs
                if entries[ref].body["sender"] is not None
                and datetime.fromisoformat(entries[ref].timestamp.replace("Z", "+00:00")) > original_time
            ]
            if rule.original_entry not in refs or not later:
                raise StreamsError("retiring a Rule needs its original and a later trusted human source")
            rule_lines = [line + "\n" for line in state.rules_text.split("\n") if line]
            start = 1 + 3 * state.rules.index(rule)
            exact_rule = "".join(rule_lines[start:start + 3])
            retired.append(_entry(
                "Retired Rule",
                {"original_entries": refs, "media_type": "text/markdown", "text": exact_rule, "sha256": sha256(exact_rule)},
                purpose="rule-retired-" + sha256(exact_rule)[:16],
            ))
        for rule in new_rules:
            if rule not in state.rules and rule.original_entry not in refs:
                raise StreamsError("new Rule must link its human source")
        if new_goals.north_star != state.goals.north_star and (new_goals.original_entry is None or new_goals.original_entry not in refs):
            raise StreamsError("North Star change needs its source")
        return _write_state(stream, state, proposed, archive=tuple(retired))


def rotate_log(stream: Path, *, expect: str | None = None, locked: bool = False) -> dict:
    with contextlib.nullcontext() if locked else stream_lock(stream):
        _text(_read(_path(stream, "AGENTS.md")))
        state = parse_state(_read(_path(stream, "STATE.md")))
        if expect is not None and state.sha256 != expect:
            raise StreamsError("stale STATE hash")
        return _write_state(stream, state, state)


def close_work(stream: Path, *, expect: str, entry: dict, target: dict, check: dict,
               report: dict, proof_entries: list, review=None, goals=None, rules=None) -> dict:
    from checks.state import check_close, run_check, target_identity, report_bytes
    originals = entry["original_entries"]
    findings = entry["body"].get("findings")
    if not isinstance(findings, str) or not findings.strip():
        raise StreamsError("close needs actual findings by whole original request")
    binding = sha256(_json({"original_entries": originals, "target": target, "check": check,
                           "report": report, "proof_entries": proof_entries, "review": review, "findings": findings}))
    with stream_lock(stream):
        current = check_state(stream)
        for saved in _entries(stream, current).values():
            result = saved.body.get("result")
            if isinstance(result, dict) and result.get("binding_sha256") == binding and result.get("status") == "complete":
                target_identity(target)
                report_bytes(target, report)
                return _result(current, [], saved)
        if current.sha256 != expect:
            raise StreamsError("stale STATE hash")
        verified = check_close(stream, current, originals=originals, target=target, check=check,
                               report=report, proof_entries=proof_entries, review=review)
        expected_text = current.goals_rules_sha256
    computed = run_check(check, target)
    if computed["exit"] != 0:
        raise StreamsError("computed check failed: " + _json(computed))
    with stream_lock(stream):
        current = check_current_text(stream, expected_text)
        fresh = check_close(stream, current, originals=originals, target=target, check=check,
                            report=report, proof_entries=proof_entries, review=review)
        if fresh != verified:
            raise StreamsError("source, target, report or proof changed during check")
        remaining = tuple(w for w in current.goals.work if w.original_entry not in originals)
        proposed_goals = _goals_input(goals) if goals is not None else replace(current.goals, work=remaining)
        if (proposed_goals.work != remaining or proposed_goals.north_star != current.goals.north_star
                or proposed_goals.original_entry != current.goals.original_entry or rules not in (None, current.rules)):
            raise StreamsError("close must preserve unrelated work, North Star and Rules")
        report_text = report_bytes(target, report).decode("utf-8")
        proof = _entry("Checked report", {"original_entries": originals, "media_type": "text/plain",
                        "text": report_text, "sha256": sha256(report_text)}, purpose="checked-report")
        proofs = [*proof_entries, {"entry": proof.file, "sha256": sha256(proof.text), "representation": "full"}]
        answer = _entry(entry["subject"], {"original_entries": originals,
            "later_instruction_entries": entry["body"].get("later_instruction_entries", []),
            "target": target, "invocation": {"argv": computed["argv"], "cwd": computed["cwd"]},
            "result": {"status": "complete", "computed": computed, "binding_sha256": binding,
                       "source_hashes": verified["originals"], "report": report},
            "findings": findings, "proof_entries": proofs, "review": review}, purpose="checked-answer")
        proposed = replace(current, goals=proposed_goals, goals_text=_render_goals(proposed_goals),
                           log=current.log + (proof, answer))
        result = _write_state(stream, current, proposed)
        result["entry"] = answer.file
        return result

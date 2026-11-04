from __future__ import annotations

import hashlib
import json
import os
import re
import stat
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Iterator

from engine import StreamsError

CHUNK = 65536


@contextmanager
def regular_reader(path: Path) -> Iterator[BinaryIO]:
    before = path.lstat()
    if not stat.S_ISREG(before.st_mode):
        raise StreamsError(f"native source must be a regular owned file: {path}")
    descriptor = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        opened = os.fstat(descriptor)
        def identity(value: os.stat_result) -> tuple[int, ...]:
            return value.st_dev, value.st_ino, value.st_mode, value.st_size, value.st_mtime_ns, value.st_ctime_ns
        if not stat.S_ISREG(opened.st_mode) or identity(before) != identity(opened):
            raise StreamsError(f"native source changed before read: {path}")
        with os.fdopen(descriptor, "rb", closefd=False) as handle:
            yield handle
        if identity(os.fstat(descriptor)) != identity(opened) or identity(path.lstat()) != identity(opened):
            raise StreamsError(f"native source changed during read: {path}")
    finally:
        os.close(descriptor)


@dataclass(frozen=True)
class EvidenceRecord:
    session_id: str
    entry_id: str
    sha256: str
    raw: bytes
    line_number: int
    path: str
    archived: bool


def read_record(path: Path, session_id: str, entry_id: str, expected_sha256: str, *, archived: bool = False) -> EvidenceRecord:
    if not session_id or not entry_id or re.fullmatch(r"[0-9a-f]{64}", expected_sha256) is None:
        raise StreamsError("evidence requires exact session/entry identity and a SHA-256 hash")
    found: tuple[int, bytes] | None = None
    try:
        with regular_reader(path) as handle:
            try:
                header = json.loads(handle.readline())
            except ValueError as exc:
                raise StreamsError("evidence source has invalid session identity") from exc
            if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != session_id:
                raise StreamsError("evidence source session identity does not match")
            for number, raw in enumerate(handle, start=2):
                try:
                    entry = json.loads(raw)
                except ValueError:
                    continue
                if isinstance(entry, dict) and entry.get("id") == entry_id:
                    if found is not None:
                        raise StreamsError(f"ambiguous evidence entry {entry_id}")
                    found = number, raw
    except OSError as exc:
        raise StreamsError(f"evidence source unavailable at {path}: {exc}") from exc
    if found is None:
        raise StreamsError(f"evidence entry {entry_id} unavailable")
    number, raw = found
    digest = hashlib.sha256(raw).hexdigest()
    if digest != expected_sha256:
        raise StreamsError(f"evidence hash mismatch for {session_id}/{entry_id}: expected {expected_sha256}, got {digest}")
    return EvidenceRecord(session_id, entry_id, digest, raw, number, str(path), archived)


def compaction_record(evidence: EvidenceRecord) -> dict:
    try:
        entry = json.loads(evidence.raw)
    except ValueError as exc:
        raise StreamsError("native compaction evidence is not valid JSON") from exc
    if not isinstance(entry, dict) or entry.get("type") != "compaction" or entry.get("id") != evidence.entry_id or not isinstance(entry.get("summary"), str) or not entry["summary"].strip() or not isinstance(entry.get("firstKeptEntryId"), str) or not entry["firstKeptEntryId"] or type(entry.get("tokensBefore")) is not int or entry["tokensBefore"] < 0:
        raise StreamsError("evidence is not a successful persisted native compaction entry")
    return {"sessionId": evidence.session_id, "entryId": evidence.entry_id, "sha256": evidence.sha256, "tokensBefore": entry["tokensBefore"], "summary": entry["summary"]}


def branch_records(path: Path, sid: str, cwd: str, leaf: object) -> list[tuple[dict, bytes]]:
    entries: dict[str, tuple[dict, bytes]] = {}
    with regular_reader(path) as handle:
        try:
            header = json.loads(handle.readline())
        except ValueError as exc:
            raise StreamsError("failure evidence has a malformed native header; backed-up repair is required") from exc
        if not isinstance(header, dict) or header.get("type") != "session" or header.get("id") != sid or not isinstance(header.get("cwd"), str) or Path(header["cwd"]).resolve() != Path(cwd).resolve():
            raise StreamsError("failure evidence does not match the exact native session/cwd")
        for raw in handle:
            if not raw.strip():
                continue
            try:
                value = json.loads(raw)
            except ValueError as exc:
                raise StreamsError("failure evidence contains torn or malformed JSONL; preserve the source and perform backed-up repair before recovery") from exc
            if isinstance(value, dict) and isinstance(value.get("id"), str):
                if value["id"] in entries:
                    raise StreamsError("failure evidence contains ambiguous native entry IDs")
                entries[value["id"]] = value, raw
    if not isinstance(leaf, str) or leaf not in entries:
        raise StreamsError("failure boundary cannot prove the exact current native branch")
    branch = []
    seen = set()
    while leaf is not None:
        if not isinstance(leaf, str) or leaf in seen or leaf not in entries:
            raise StreamsError("failure evidence has an incomplete or cyclic branch")
        seen.add(leaf)
        value, raw = entries[leaf]
        branch.append((value, raw))
        leaf = value.get("parentId")
    branch.reverse()
    return branch


def verify_good_checkpoint(path: Path, sid: str, cwd: str, leaf: object, checkpoint: dict, failure_entry: str) -> dict:
    if not isinstance(checkpoint.get("entryId"), str) or not isinstance(checkpoint.get("sha256"), str) or re.fullmatch(r"[a-f0-9]{64}", checkpoint["sha256"]) is None:
        raise StreamsError("native good-turn checkpoint identity/hash is invalid")
    pending: set[str] = set()
    healthy = True
    for entry, raw in branch_records(path, sid, cwd, leaf):
        if entry["id"] == failure_entry:
            break
        message = entry.get("message", {})
        if message.get("role") == "assistant":
            healthy = not pending
            calls = message.get("content", [])
            if isinstance(calls, list) and message.get("stopReason") not in ("error", "aborted"):
                for call in calls:
                    if isinstance(call, dict) and call.get("type") == "toolCall":
                        identity = call.get("id")
                        if not isinstance(identity, str) or not identity or identity in pending:
                            raise StreamsError("ambiguous tool-call identity in good-turn checkpoint")
                        pending.add(identity)
            if message.get("stopReason") in ("error", "aborted", "length"):
                healthy = False
        elif message.get("role") == "toolResult":
            identity = message.get("toolCallId")
            if not isinstance(identity, str) or identity not in pending:
                raise StreamsError("good-turn checkpoint has an unmatched tool result")
            pending.remove(identity)
            healthy = healthy and message.get("isError") is not True
        if entry["id"] == checkpoint["entryId"]:
            terminal = message.get("role") == "toolResult" or message.get("role") == "assistant" and message.get("stopReason") == "stop"
            if not terminal or pending or not healthy or hashlib.sha256(raw).hexdigest() != checkpoint["sha256"]:
                raise StreamsError("checkpoint is not the exact complete successful persisted turn")
            return {"entryId": checkpoint["entryId"], "sha256": checkpoint["sha256"], "nativeFile": str(path), "branchLeaf": leaf}
    raise StreamsError("good-turn checkpoint is absent or is not before the native failure")


def retry_dispositions(branch: list[tuple[dict, bytes]], sid: str, cwd: str, native_retry: dict | None = None) -> dict[str, dict]:
    anchor = next((entry.get("data", {}) for entry, _ in reversed(branch) if entry.get("customType") == "pi-web.stream-failure" and isinstance(entry.get("data"), dict) and entry["data"].get("sessionId") == sid), {})
    parents = {}
    for entry, _ in branch:
        if entry.get("customType") != "pi-web.stream-failure":
            continue
        data = entry.get("data", {})
        if not isinstance(data, dict):
            raise StreamsError("Retry lineage metadata is malformed")
        recovery = data.get("recovery", {})
        if not isinstance(recovery, dict):
            raise StreamsError("Retry lineage ownership is malformed")
        if data.get("version") != 1 or data.get("cwd") != cwd or any(data.get(key) != anchor.get(key) for key in ("root", "stream")) or data.get("state") not in {"recovering", "watching"} or not isinstance(recovery.get("originalSessionId"), str) or not isinstance(recovery.get("id"), str):
            continue
        if data.get("sessionId") in parents and parents[data["sessionId"]] != recovery["originalSessionId"]:
            raise StreamsError("Retry lineage changed its original session binding")
        parents[data.get("sessionId")] = recovery["originalSessionId"]
    lineage = {sid}
    current = sid
    while current in parents:
        current = parents[current]
        if current in lineage:
            raise StreamsError("Retry lineage is cyclic")
        lineage.add(current)
    positions = {entry["id"]: (index, entry, raw) for index, (entry, raw) in enumerate(branch)}
    result = {}
    for index, (entry, _) in enumerate(branch):
        if entry.get("customType") != "pi-web.stream-retry" or not isinstance(entry.get("data"), dict) or entry["data"].get("sessionId") not in lineage:
            continue
        data = entry["data"]
        failed = data.get("failure", {})
        identity = data.get("identity", {})
        source = positions.get(failed.get("entryId"))
        if source is None or source[0] >= index or data.get("version") != 1 or data.get("cwd") != cwd or hashlib.sha256(source[2]).hexdigest() != failed.get("sha256") or source[1].get("message", {}).get("stopReason") != "error" or any(not isinstance(identity.get(key), str) or not identity[key] for key in ("provider", "model", "thinking", "generation")) or any(identity[key] != source[1]["message"].get(key) for key in ("provider", "model")) or type(data.get("attempt")) is not int or data["attempt"] < 1 or data.get("delayMs") != 5000 or data.get("state") not in {"pending", "resolved", "terminal", "cancelled", "uncertain", "superseded"}:
            raise StreamsError("Native retry disposition changed exact entry/hash or identity")
        prior = result.get(failed["entryId"])
        if prior is not None and (prior["identity"] != identity or prior["attempt"] != data["attempt"] or prior["state"] != "pending" and not (prior["state"] == "cancelled" and prior.get("reason") == "new-input" and data["state"] == "superseded") and prior != data):
            raise StreamsError("Native retry disposition changed immutable settlement")
        if data["state"] == "superseded":
            target = positions.get(data.get("input", {}).get("entryId"))
            if target is None or not source[0] < target[0] < index or hashlib.sha256(target[2]).hexdigest() != data["input"].get("sha256") or target[1].get("message", {}).get("role") != "user":
                raise StreamsError("Superseded native retry has no exact newer admitted input")
        if data["state"] == "resolved":
            completion = data.get("completion", {})
            target = positions.get(completion.get("entryId"))
            if target is None or not source[0] < target[0] < index or hashlib.sha256(target[2]).hexdigest() != completion.get("sha256") or target[1].get("message", {}).get("role") != "assistant" or target[1]["message"].get("stopReason") == "aborted" or any(target[1]["message"].get(key) != identity[key] for key in ("provider", "model")) or any(value.get("message", {}).get("role") == "user" or value.get("type") in {"model_change", "thinking_level_change"} for value, _ in branch[source[0]+1:target[0]]):
                raise StreamsError("Native retry has no exact ordered same-identity completion")
        result[failed["entryId"]] = data
    for data in result.values():
        if data["state"] in {"cancelled", "uncertain"} or data["state"] == "pending" and data != native_retry:
            raise StreamsError("Native retry ownership is cancelled, uncertain or unavailable; no replay")
    return result


def _expansion_end(source: str, start: int, backtick: bool = False) -> int:
    quote, depth, at = None, 1, start
    while at < len(source):
        char = source[at]
        if char == "\\":
            at += 2
            continue
        if backtick and char == "`":
            return at
        if quote == "'":
            if char == "'":
                quote = None
            at += 1
            continue
        if source.startswith("$(", at) or char == "`":
            at = _expansion_end(source, at + (1 if char == "`" else 2), char == "`")
            if at < 0:
                return -1
        elif char == '"' or char == "'" and quote is None:
            quote = None if quote == char else char
        elif quote is None and not backtick:
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    return at
        at += 1
    return -1


def _heredoc_submission(body: str) -> bool:
    at = 0
    while at < len(body):
        if body[at] == "\\" and at + 1 < len(body) and body[at + 1] in "$`\\\n":
            at += 2
            continue
        if body[at] == "`" or body.startswith("$(", at):
            start = at + (1 if body[at] == "`" else 2)
            end = _expansion_end(body, start, body[at] == "`")
            if end < 0 or shell_submission(body[start:end]):
                return True
            at = end
        at += 1
    return False


def _split_string_submission(value: str) -> bool:
    return re.fullmatch(r"[-A-Za-z0-9_./=+,:@% ]*", value) is None or shell_submission(value)


def shell_submission(command: object) -> bool:
    """Retain explicit detached launches, not uncertainty about foreground syntax."""
    if not isinstance(command, str):
        return True
    heredoc_effects = False
    def heredoc(match):
        nonlocal heredoc_effects
        if not match[1] and _heredoc_submission(match[4]):
            heredoc_effects = True
        prefix = command[:match.start()]
        return match[3] + "\n" + (match[4] + "\n" if re.search(r"(?:^|[;|\s])(?:bash|sh|dash|ksh|zsh)\s", prefix) else "")
    command = re.sub(r"<<-?\s*(['\"]?)(\w+)\1([^\n]*)\n([\s\S]*?)\n\t*\2(?=\n|$)", heredoc, command)
    if heredoc_effects:
        return True
    operators = ("&>>", "&>", "&&", "||", "|&", ">>", "<>", ">|", ">&", "<&", ">", "<", ";", "|", "&", "\n")
    redirects = {"&>>", "&>", ">>", "<>", ">|", ">&", "<&", ">", "<"}
    opaque_words = {"sbatch", "qsub", "nohup", "setsid", "disown"}
    tokens: list[tuple[str, str]] = []
    word: str | None = None
    index = 0
    while index < len(command):
        char = command[index]
        if char == "\\":
            index += 1
            if index == len(command):
                break
            if command[index] != "\n":
                word = (word or "") + command[index]
            index += 1
            continue
        if char in ("'", '"'):
            quote = char
            word = word or ""
            index += 1
            while index < len(command) and command[index] != quote:
                char = command[index]
                if quote == '"' and command.startswith("$(", index):
                    end = _expansion_end(command, index + 2)
                    if end < 0 or shell_submission(command[index + 2:end]):
                        return True
                if quote == '"' and char == "`":
                    end = _expansion_end(command, index + 1, True)
                    if end < 0 or shell_submission(command[index + 1:end]):
                        return True
                if quote == '"' and char == "\\" and index + 1 < len(command) and command[index + 1] in '$`"\\\n':
                    index += 1
                    char = command[index]
                    if char == "\n":
                        index += 1
                        continue
                word += char
                index += 1
            if index == len(command):
                break
            index += 1
            continue
        if char == "#" and word is None:
            while index < len(command) and command[index] != "\n":
                index += 1
            continue
        if char in "(){}[]`":
            if word is not None:
                tokens.append(("word", word))
                word = None
            tokens.append(("operator", char))
            index += 1
            continue
        operator = next((value for value in operators if command.startswith(value, index)), None)
        if char in " \t" or operator is not None:
            if word is not None:
                tokens.append(("word", word))
                word = None
            if operator is not None:
                tokens.append(("redirect" if operator in redirects else "operator", operator))
                index += len(operator)
            else:
                index += 1
            continue
        word = (word or "") + char
        index += 1
    if word is not None:
        tokens.append(("word", word))
    invokers = {
        "env": ({"-u", "--unset", "-C", "--chdir", "-a", "--argv0", "-S", "--split-string"}, {"-i", "--ignore-environment", "-0", "--null", "-v", "--debug"}),
        "sudo": ({"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "--close-from", "-R", "--chroot", "-D", "--chdir", "-T", "--command-timeout", "-r", "--role", "-t", "--type", "-U", "--other-user"}, {"-n", "--non-interactive", "-E", "--preserve-env", "-H", "--set-home", "-k", "-K", "-S", "--stdin"}),
        "exec": ({"-a"}, {"-c", "-l"}),
        "command": (set(), {"-p", "-v", "-V"}),
        "builtin": (set(), set()),
        "time": ({"-f", "--format", "-o", "--output"}, {"-p", "--portability", "-v", "--verbose", "-a", "--append", "-q", "--quiet"}),
    }
    at_command, invoker, operand, redirect_operand, inspect = True, None, None, False, False
    for index, (kind, value) in enumerate(tokens):
        if kind == "operator":
            if value == "&":
                return True
            if value in {";", "|", "|&", "&&", "||", "\n", "(", "{", "`"}:
                at_command, invoker, operand, redirect_operand, inspect = True, None, None, False, False
            continue
        if kind == "redirect":
            redirect_operand = True
            continue
        if redirect_operand:
            redirect_operand = False
            continue
        if kind != "word" or not at_command:
            continue
        if operand:
            if operand == "script" and _split_string_submission(value):
                return True
            operand = None
            continue
        name = value.rsplit("/", 1)[-1]
        if re.match(r"^[A-Za-z_][A-Za-z0-9_]*=", value):
            continue
        if invoker and value.startswith("-"):
            if value == "--":
                invoker = None
                continue
            args, flags = invokers[invoker]
            option = next((flag for flag in args if value == flag or flag.startswith("--") and value.startswith(flag + "=") or re.fullmatch(r"-[^-]", flag) and value.startswith(flag) and len(value) > 2), None)
            if option is not None:
                script = invoker == "env" and option in {"-S", "--split-string"}
                attached = value[len(option) + (1 if option.startswith("--") else 0):] if len(value) > len(option) else None
                if attached is None:
                    operand = "script" if script else "argument"
                elif script and _split_string_submission(attached):
                    return True
                continue
            if value not in flags:
                return True
            if invoker == "command" and value in {"-v", "-V"}:
                inspect = True
            continue
        if name in invokers:
            invoker = name
            continue
        at_command = False
        if inspect:
            continue
        if name in opaque_words:
            return True
        end = next((at for at in range(index + 1, len(tokens)) if tokens[at][0] == "operator"), len(tokens))
        rest = tokens[index + 1:end]
        if name in {"eval", "bash", "sh", "dash", "ksh", "zsh"} and any(kind == "word" and re.search(r"[\s;&]", script) and shell_submission(script) for kind, script in rest):
            return True
        if name == "tmux" and any(re.fullmatch(r"-.*d.*|detach|detach-client", text) for _, text in rest):
            return True
        if name == "screen" and any(re.fullmatch(r"-.*[dD].*", text) for _, text in rest):
            return True
    return False


def failure_observation(path: Path, sid: str, cwd: str, leaf: object, failure_entry: str | None = None, *, native_retry: dict | None = None, checkpoint: dict | None = None) -> dict | None:
    branch = branch_records(path, sid, cwd, leaf)
    retries = retry_dispositions(branch, sid, cwd, native_retry)
    failed = None
    saved = ("", "")
    uncertain: dict[str, dict[str, str]] = {}
    pending: set[str] = set()
    checkpoint_at = -1
    if checkpoint is not None:
        verify_good_checkpoint(path, sid, cwd, leaf, checkpoint, failure_entry)
        checkpoint_at = next(index for index, (entry, _) in enumerate(branch) if entry["id"] == checkpoint["entryId"])
    for index, (entry, raw) in enumerate(branch):
        if retries.get(entry["id"], {}).get("state") in {"resolved", "pending", "superseded"}:
            continue
        message = entry.get("message")
        if not isinstance(message, dict):
            continue
        if message.get("role") == "user":
            saved = entry["id"], hashlib.sha256(raw).hexdigest()
        if index <= checkpoint_at:
            continue
        if message.get("role") == "assistant" and message.get("stopReason") not in ("error", "aborted"):
            content = message.get("content", [])
            for part in content if isinstance(content, list) else []:
                if not isinstance(part, dict) or part.get("type") != "toolCall":
                    continue
                identity = part.get("id")
                if not isinstance(identity, str) or not identity or identity in pending:
                    raise StreamsError("External-effect tool-call ownership is ambiguous")
                pending.add(identity)
                arguments = part.get("arguments", {})
                command = arguments.get("command") if isinstance(arguments, dict) else None
                if part.get("name") == "bash" and shell_submission(command):
                    key = "unclassified-shell-submission:" + identity
                    uncertain[key] = {"id": key, "state": "unknown"}
        if message.get("role") == "toolResult":
            pending.discard(message.get("toolCallId"))
            details = message.get("details")
            if isinstance(details, dict):
                job = details.get("jobId", details.get("job_id", details.get("externalJobId")))
                if isinstance(job, str) and job:
                    uncertain.pop("unclassified-shell-submission:" + str(message.get("toolCallId")), None)
                    status = str(details.get("status", "unknown"))
                    if status in ("completed", "succeeded", "failed", "cancelled"):
                        uncertain.pop(job, None)
                    else:
                        uncertain[job] = {"id": job, "state": status}
        is_tool = message.get("role") == "toolResult" and message.get("isError") is True
        is_model = message.get("role") == "assistant" and message.get("stopReason") == "error"
        if not is_tool and not is_model or failure_entry is not None and entry["id"] != failure_entry:
            continue
        body = message.get("errorMessage", "")
        if is_tool:
            content = message.get("content", [])
            body = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
            if failure_entry is None and not re.search(r"ENOSPC|no space left|resource exhausted|out of memory|login expired|unauthorized|token expired|authentication expired", body, re.I):
                continue
        failed = {"entryId": entry["id"], "sha256": hashlib.sha256(raw).hexdigest(), "provider": "tool" if is_tool else str(message.get("provider", "unknown")), "message": body if isinstance(body, str) else "", "toolError": is_tool, "savedEntryId": saved[0], "savedSha256": saved[1], "uncertainJobs": []}
    if failed is not None:
        for identity in sorted(pending):
            key = "unmatched-tool-call:" + identity
            uncertain[key] = {"id": key, "state": "unknown"}
        failed["uncertainJobs"] = list(uncertain.values())
    return failed


def control_checkpoint(path: Path, sid: str, cwd: str, leaf: object) -> dict:
    branch = branch_records(path, sid, cwd, leaf)
    entry, raw = branch[-1]
    proof = read_record(path, sid, entry['id'], hashlib.sha256(raw).hexdigest())
    with regular_reader(path) as handle:
        lines = sum(1 for _ in handle)
    return {'path': str(path), 'entryId': proof.entry_id, 'sha256': proof.sha256, 'lines': lines}


def control_outcome(path: Path, sid: str, cwd: str, leaf: object, checkpoint: dict, goal: str) -> tuple[EvidenceRecord, dict] | None:
    if checkpoint.get('path') != str(path) or type(checkpoint.get('lines')) is not int:
        return None
    branch = branch_records(path, sid, cwd, leaf)
    positions = {entry['id']: index for index, (entry, _) in enumerate(branch)}
    start = positions.get(checkpoint.get('entryId'))
    if start is None:
        return None
    read_record(path, sid, checkpoint['entryId'], checkpoint['sha256'])
    tail = branch[start + 1:]
    users = [(entry, raw) for entry, raw in tail if entry.get('message', {}).get('role') == 'user']
    if len(users) != 1:
        return None
    user, raw = users[0]
    message = user['message']
    content = message.get('content', [])
    text = content if isinstance(content, str) else '\n'.join(part.get('text', '') for part in content if isinstance(part, dict) and part.get('type') == 'text')
    if not text.startswith('<skill name="poteto-mode"') or not text.endswith('</skill>\n\n' + goal):
        return None
    owned = read_record(path, sid, user['id'], hashlib.sha256(raw).hexdigest())
    if owned.line_number <= checkpoint['lines']:
        return None
    result = None
    for entry, raw in branch[positions[user['id']] + 1:]:
        message = entry.get('message', {})
        if message.get('role') == 'assistant':
            if message.get('stopReason') in {'error', 'aborted', 'length'}:
                return None
            if message.get('stopReason') == 'stop':
                if result is not None:
                    return None
                result = read_record(path, sid, entry['id'], hashlib.sha256(raw).hexdigest())
    if result is None or result.line_number <= owned.line_number:
        return None
    return result, {'userEntryId': owned.entry_id, 'userSha256': owned.sha256, 'assistantEntryId': result.entry_id, 'assistantSha256': result.sha256}


def successful_control_completion(path: Path, sid: str, cwd: str, leaf: object, prefix: str, goal: str) -> bool:
    active = False
    completed = False
    for entry, _raw in branch_records(path, sid, cwd, leaf):
        message = entry.get("message", {})
        content = message.get("content", [])
        text = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
        if message.get("role") == "user" and text.startswith(prefix) and text.endswith(goal) and '<skill name="poteto-mode"' in text:
            active, completed = True, False
        elif active and message.get("role") == "assistant":
            if message.get("stopReason") == "error":
                return False
            if message.get("stopReason") == "stop":
                completed = True
    return completed


def resume_observation(path: Path, sid: str, cwd: str, leaf: object, identity: str, generation: str, compaction: str, compaction_sha256: str, text: str, goal: str, native: dict) -> dict | None:
    receipt = native.get("resume")
    if not isinstance(receipt, dict) or receipt.get("observation") is None:
        return None
    observation = receipt["observation"]
    if not isinstance(observation, dict) or native.get("state") != "resumed" or native.get("inputSequence") != 0 or receipt.get("state") != "admitted" or receipt.get("deliveryId") != identity+":resume" or receipt.get("generation") != generation or receipt.get("inputSequence") != 0 or receipt.get("text") != text or receipt.get("potetoGoal") != goal:
        raise StreamsError("RESUME observation changed its saved admission/epoch")
    required = ("entryId", "sha256", "userEntryId", "assistantEntryId", "assistantSha256")
    if any(not isinstance(observation.get(key), str) or not observation[key] for key in required):
        raise StreamsError("RESUME observation lacks exact entry/hash identities")
    entries = branch_records(path, sid, cwd, leaf)
    positions = {entry["id"]: index for index, (entry, _raw) in enumerate(entries)}
    keys = (compaction, observation["userEntryId"], observation["assistantEntryId"], observation["entryId"])
    if any(key not in positions for key in keys) or not all(positions[a] < positions[b] for a, b in zip(keys, keys[1:])):
        raise StreamsError("RESUME observation is not on its ordered post-compaction branch")
    entry = json.loads(read_record(path, sid, observation["entryId"], observation["sha256"]).raw)
    expected = {"kind": "assistant-stop", "operationId": identity, "sessionId": sid, "cwd": cwd, "generation": generation, "deliveryId": identity+":resume", "compactionEntryId": compaction, "userEntryId": observation["userEntryId"], "assistantEntryId": observation["assistantEntryId"], "assistantSha256": observation["assistantSha256"]}
    if observation.get("userSha256") is not None:
        expected["userSha256"] = observation["userSha256"]
    if entry.get("type") != "custom" or entry.get("customType") != "pi-web.resume-observed" or entry.get("data") != expected or any(observation.get(key) != expected[key] for key in ("kind", "deliveryId", "compactionEntryId")):
        raise StreamsError("RESUME observation is not its exact native correlated receipt")
    compaction_record(read_record(path, sid, compaction, compaction_sha256))
    assistant = json.loads(read_record(path, sid, observation["assistantEntryId"], observation["assistantSha256"]).raw).get("message", {})
    if assistant.get("role") != "assistant" or assistant.get("stopReason") != "stop":
        raise StreamsError("RESUME observation has no actual non-error completed assistant")
    owned, owned_raw = entries[positions[observation["userEntryId"]]]
    if observation.get("userSha256") is not None and hashlib.sha256(owned_raw).hexdigest() != observation["userSha256"]:
        raise StreamsError("RESUME observation user hash changed")
    message = owned.get("message", {})
    content = message.get("content", [])
    actual = content if isinstance(content, str) else "\n".join(block.get("text", "") for block in content if isinstance(block, dict) and block.get("type") == "text")
    invocation = "/poteto-mode " + goal
    prefix = text[:-len(invocation)] if text.endswith(invocation) else None
    if message.get("role") != "user" or prefix is None or not actual.startswith(prefix+'<skill name="poteto-mode"') or not actual.endswith("</skill>\n\n"+goal):
        raise StreamsError("RESUME observation user is not the actual expanded fixed mode/goal input")
    messages = [value.get("message", {}) for value, _raw in entries[positions[compaction]+1:positions[observation["entryId"]]] if value.get("type") == "message"]
    if sum(message.get("role") == "user" for message in messages) != 1 or any(message.get("stopReason") in {"error", "aborted"} for message in messages):
        raise StreamsError("New input or failed inference superseded the owned RESUME")
    return {**observation, "userSha256": hashlib.sha256(owned_raw).hexdigest()}


def last_assistant(path: Path, *, evidence: bool = False) -> dict[str, object] | None:
    try:
        with regular_reader(path) as handle:
            return _scan_back(handle, evidence=evidence)
    except FileNotFoundError:
        return None
    except OSError as exc:
        raise StreamsError(f"could not read {path}: {exc}") from exc


def _scan_back(handle: BinaryIO, *, evidence: bool = False) -> dict[str, object] | None:
    end = handle.seek(0, os.SEEK_END)
    pieces: list[bytes] = []
    while end > 0:
        start = max(0, end - CHUNK)
        handle.seek(start)
        data = handle.read(end - start)
        end = start
        stop = len(data)
        cut = data.rfind(b"\n", 0, stop)
        while cut >= 0:
            pieces.append(data[cut + 1 : stop])
            message = _assistant(b"".join(reversed(pieces)), evidence=evidence)
            if message is not None:
                return message
            pieces = []
            stop = cut
            cut = data.rfind(b"\n", 0, stop)
        pieces.append(data[:stop])
    return _assistant(b"".join(reversed(pieces)), evidence=evidence)


def _assistant(line: bytes, *, evidence: bool = False) -> dict[str, object] | None:
    # A line pi is still appending does not parse yet; the one before it counts.
    try:
        entry = json.loads(line)
    except ValueError:
        return None
    if not isinstance(entry, dict) or entry.get("type") != "message":
        return None
    message = entry.get("message")
    if isinstance(message, dict) and message.get("role") == "assistant":
        if evidence:
            return {"entryId": entry.get("id", ""), "sha256": hashlib.sha256(line).hexdigest(), "message": message}
        return message
    return None

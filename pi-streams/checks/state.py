from __future__ import annotations

import hashlib
import os
import subprocess
import sys
from pathlib import Path

from engine import StreamsError
from engine.project import git
from engine import state

check_state = state.check_state


def safe_path(root, path):
    root, path = Path(root), Path(path)
    if ".." in root.parts or ".." in path.parts:
        raise StreamsError("check, report or target artifact traversal is not allowed")
    if not root.is_absolute() or not path.is_absolute() or not path.is_relative_to(root):
        raise StreamsError("check or report path escapes actual target")
    if any(p.is_symlink() for p in (path, *path.parents)):
        raise StreamsError("symlink check or report path")
    if any(part in {".prime", ".pi", ".ssh", ".git", "sessions", "auth.json", "credentials", ".env"} for part in path.relative_to(root).parts):
        raise StreamsError("protected runtime or credential path is not a report")
    return path


def target_identity(target):
    root = Path(target["repo"])
    safe_path(root, root)
    if Path(git(root, "rev-parse", "--show-toplevel").strip()) != root:
        raise StreamsError("target is not the actual repository root")
    artifacts = target.get("artifacts")
    if not isinstance(artifacts, dict) or not artifacts:
        raise StreamsError("target artifacts must explicitly bind the requested product outputs")
    actual_artifacts = {}
    for name, expected_hash in artifacts.items():
        if not isinstance(name, str) or Path(name).is_absolute() or not isinstance(expected_hash, str):
            raise StreamsError("target artifact needs a relative path and SHA-256")
        path = safe_path(root, root / name)
        if not path.is_file():
            raise StreamsError("missing actual target artifact")
        actual_artifacts[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    actual = {"repo": str(root), "commit": git(root, "rev-parse", "HEAD").strip(),
              "diff_sha256": state.sha256(git(root, "diff", "--binary", "--no-ext-diff", "HEAD", "--")),
              "artifacts": actual_artifacts}
    if actual != target:
        raise StreamsError("target commit, diff or artifact bytes do not match actual worktree")
    return actual


def report_bytes(target, report):
    path = safe_path(Path(target["repo"]), report["path"])
    try:
        data = path.read_bytes()
        data.decode("utf-8")
    except (OSError, UnicodeError) as exc:
        raise StreamsError(f"missing or non-text report: {exc}") from exc
    if hashlib.sha256(data).hexdigest() != report["sha256"]:
        raise StreamsError("report hash differs from actual bytes")
    return data


def run_check(check, target):
    root = Path(target["repo"])
    cwd, argv = Path(check["cwd"]), check["argv"]
    if cwd != root or not isinstance(argv, list) or not argv or any(not isinstance(a, str) or "\0" in a for a in argv):
        raise StreamsError("check needs exact argv and actual target cwd")
    if argv[0] not in {"python3", sys.executable}:
        raise StreamsError("unsupported or unsafe local check; job submission is not a test")
    if argv[1:3] != ["-m", "unittest"]:
        if len(argv) != 2:
            raise StreamsError("only unittest or one tracked check script is authorized")
        path = safe_path(root, root / argv[1])
        if path.suffix != ".py" or not path.name.startswith(("check_", "test_")):
            raise StreamsError("not a named local Python check")
        git(root, "ls-files", "--error-unmatch", "--", str(path.relative_to(root)))
    elif any(a.startswith("-") and a not in {"-m", "-v", "-q", "-f", "-c", "-b", "--verbose", "--quiet", "--failfast", "--catch", "--buffer", "-s", "-p", "-t"} for a in argv[3:]):
        raise StreamsError("unsupported unittest check option")
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    result = subprocess.run(argv, cwd=cwd, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False)
    return {"argv": argv, "cwd": str(cwd), "exit": result.returncode,
            "stdout": result.stdout.decode("utf-8", errors="replace"), "stderr": result.stderr.decode("utf-8", errors="replace")}


def check_close(stream, current, *, originals, target, check, report, proof_entries, review):
    entries = state._entries(stream, current)
    if not originals or not set(originals) <= {w.original_entry for w in current.goals.work}:
        raise StreamsError("close source is not requested whole-message work")
    if current.goals.status == "paused" or any(w.required is None for w in current.goals.work):
        raise StreamsError("paused or unread current input prevents close")
    from engine.prime import unresolved
    if unresolved(entries):
        raise StreamsError("unknown native send prevents close")
    for ref in originals:
        work = next(w for w in current.goals.work if w.original_entry == ref)
        allowed = {worker["worktree"] for worker in work.workers}
        if target["repo"] not in allowed and target["repo"] not in entries[ref].body["text"]:
            raise StreamsError("target is not bound to the original request or an assigned worker")
    target_identity(target)
    report_bytes(target, report)
    if not isinstance(proof_entries, list) or not proof_entries:
        raise StreamsError("missing saved proof entries")
    for proof in proof_entries:
        raw = state.read_entry(stream, proof["entry"])
        if state.sha256(raw) != proof["sha256"] or proof["representation"] not in {"full", "excerpt"}:
            raise StreamsError("proof bytes or representation differ")
        body = entries[proof["entry"]].body
        if not set(originals) <= set(body.get("original_entries", [])):
            raise StreamsError("proof is not bound to the whole original request")
        if proof["representation"] == "excerpt":
            if not {"original", "range"} <= proof.keys() or not isinstance(proof["range"], list) or len(proof["range"]) != 2:
                raise StreamsError("excerpt proof must name original and inclusive line range")
            source = state._parse_entry(state.read_entry(stream, proof["original"])).body.get("text")
            start, end = proof["range"]
            if not isinstance(source, str) or type(start) is not int or type(end) is not int or not 1 <= start <= end:
                raise StreamsError("invalid excerpt source or range")
            parts = source.split("\n")
            lines = [line + "\n" for line in parts[:-1]] + ([parts[-1]] if parts[-1] else [])
            if end > len(lines) or body.get("text") != "".join(lines[start - 1:end]):
                raise StreamsError("excerpt does not match the named original line range")
    if review is not None:
        if review not in entries or not set(originals) <= set(entries[review].body.get("original_entries", [])):
            raise StreamsError("review is not source-bound")
    return {"target": target, "check": check, "report": report, "proof_entries": proof_entries, "review": review,
            "originals": {ref: state.sha256(entries[ref].text) for ref in originals}}

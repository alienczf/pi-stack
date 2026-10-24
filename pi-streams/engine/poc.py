"""One shared isolated PoC driver. Offline checks never establish native PASS."""
from __future__ import annotations

import argparse
import json
import math
import os
import subprocess
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from engine import StreamsError, repo_root, state
from engine import project, prime
from engine.install_prime import PRIME_REVISION, confined, digest, tree_hash, run
from engine.threads import Thread, Status, load_threads, save_threads, spawn_prime_worker, utc_now

STAGES = ("intake", "steer", "worker", "stale", "self_review", "percentage", "checked_save", "compact", "disk_readback", "continuation", "computed_close", "rotation")


def _installation(root):
    root = Path(root)
    path = confined(root, root / "reports/install.json")
    data = json.loads(path.read_text())
    if data.get("root") != str(root) or data.get("project") != str(root / "project"):
        raise StreamsError("install report names a foreign root or project")
    return data


def _stream(root, stream_id):
    if not project.STREAM_ID.fullmatch(stream_id):
        raise StreamsError("invalid stream id")
    return confined(root, root / "project/streams" / stream_id)


def _report(root, path, value):
    confined(root, path)
    if path.exists():
        previous = json.loads(path.read_text())
        if previous.get("stream") != value.get("stream") or previous.get("status") not in {"PASS", "FAIL", "BLOCKED", "INCONCLUSIVE"}:
            raise StreamsError("refusing conflicting report content")
    path.parent.mkdir(parents=True, exist_ok=True)
    state._publish(path, json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n")


def init(root, stream_id):
    root = Path(root)
    installation = _installation(root)
    stream = _stream(root, stream_id)
    config = project.load_project(root / "index/projects/project.toml")
    if stream.exists():
        if not (stream / "stream.toml").is_file() or load_threads(stream / "threads.tsv"):
            raise StreamsError("poc init refuses existing work or native assignments")
        if state.check_state(stream).goals.work or state.check_state(stream).log:
            raise StreamsError("poc init refuses an existing working stream")
    stream = project.create_stream(root / "index", config, stream_id, backend="prime")
    project.write_prime_settings(stream, installation["threshold_percent"])
    return {"status": "PASS", "stream": stream_id, "checks": {"created_owned_stream": True, "settings_before_session": True, "native_session_created": False}}


def doctor(root, stream_id):
    root = Path(root)
    checks = {}
    try:
        installation = _installation(root)
        stream = _stream(root, stream_id)
        for label, check in (
            ("source_revision", lambda: installation["prime_source_revision"] == PRIME_REVISION and project.git(root / "src/prime-agent", "rev-parse", "HEAD").strip() == PRIME_REVISION),
            ("binary_hash", lambda: digest(confined(root, root / "libexec/prime-agent")) == installation["prime_binary_sha256"]),
            ("runtime_sidecar", lambda: tree_hash(confined(root, root / "libexec/prime-agent-runtime")) == installation["prime_runtime_sha256"]),
            ("version", lambda: run([root / "bin/prime-agent", "--version"], env={"HOME": os.environ["HOME"], "PATH": os.environ["PATH"]}).strip() == "0.10.1"),
            ("selected_checkout", lambda: project.git(repo_root(), "rev-parse", "HEAD").strip() == installation["pi_stack_revision"] and Path(installation["paths"]["checkout"]) == repo_root()),
            ("poteto_source", lambda: confined(root, Path(installation["paths"]["poteto"])).is_file() and project.git(root / "src/plugins", "rev-parse", "HEAD").strip() == installation["pstack_revision"]),
            ("agents_template", lambda: (stream / "AGENTS.md").read_bytes() == (project.templates_dir() / "prime/AGENTS.md").read_bytes()),
            ("checked_state", lambda: bool(state.check_state(stream))),
            ("controllers_disabled", lambda: prime.validate_stream_settings(stream)["compaction"] == {"enabled": False, "agentCallable": False, "thresholdPercent": installation["threshold_percent"]}),
        ):
            checks[label] = bool(check())
            if not checks[label]:
                raise StreamsError(f"doctor failed {label}")
        config = project.load_project(root / "index/projects/project.toml")
        checks["explicit_model_thinking"] = config.coordinator.model == installation["model"] and config.coordinator.thinking == installation["thinking"]
        checks["worker_model_thinking"] = config.threads.model == installation["worker_model"] and config.threads.thinking == installation["worker_thinking"]
        settings = json.loads(confined(root, root / "prime/agent/settings.json").read_text())
        checks["allowed_role_models"] = set((installation["model"], installation["worker_model"])) <= set(settings["allowedModels"])
        for role, model_key, thinking_key in (("stream", "model", "thinking"), ("worker", "worker_model", "worker_thinking")):
            definition_path = repo_root() / "scripts/prime-models" / (installation[model_key].replace("/", "-") + ".json")
            if definition_path.is_file():
                definition = json.loads(definition_path.read_text())
                expected_model = {key: value for key, value in definition.items() if key != "provider"}
                models = json.loads(confined(root, root / "prime/agent/models.json").read_text())["providers"][definition["provider"]]["models"]
                matching = [model for model in models if model.get("id") == definition["id"]]
                checks[role + "_reasoning_metadata"] = matching == [expected_model] and installation[thinking_key] in definition["thinkingLevelMap"]
        if not all(checks.values()):
            raise StreamsError("doctor model configuration differs")
        result = {"status": "PASS", "stream": stream_id, "checks": checks, "protocol": 7, "schema": 30}
    except (StreamsError, OSError, ValueError, KeyError, TypeError) as exc:
        result = {"status": "FAIL", "stream": stream_id, "checks": checks, "reason": str(exc)}
    _report(root, root / "reports" / f"{stream_id}-doctor.json", result)
    return result


class RecordingClient(prime.PrimeClient):
    def __init__(self, path, stream):
        super().__init__(path)
        self.trace, self.snapshots, self.stream_path = [], {}, stream

    def write(self, kind, *, command_id=None, **fields):
        snapshot = None
        if kind == "prompt_and_wait" and fields["message"].startswith("Current files for stream "):
            current = state.check_state(self.stream_path)
            agents = (self.stream_path / "AGENTS.md").read_text()
            if state._json(current.text) not in fields["message"] or state._json(agents) not in fields["message"]:
                raise StreamsError("actual outgoing wrapper is not fresh")
            snapshot = {"state": current.text, "agents": agents}
        command = super().write(kind, command_id=command_id, **fields)
        self.trace.append({"operation": "write", "command_id": command, "command": kind, "fields": fields})
        if snapshot:
            self.snapshots[command] = snapshot
        return command

    def wait(self, command_id):
        self.trace.append({"operation": "wait", "command_id": command_id})
        return super().wait(command_id)


def assess(report, expected_identity=None):
    failures = []
    for stage in STAGES:
        value = report.get("stages", {}).get(stage)
        if not isinstance(value, dict) or value.get("verified") is not True or not value.get("evidence"):
            failures.append(stage)
    percentages = report.get("observed_percentages", [])
    threshold = report.get("threshold_percent")
    if (not isinstance(threshold, (int, float)) or not math.isfinite(threshold)
            or not any(isinstance(p, (int, float)) and not isinstance(p, bool) and math.isfinite(p) and threshold < p <= 100 for p in percentages)):
        failures.append("actual_percentage_crossing")
    expected_identity = expected_identity if expected_identity is not None else report.get("expected_identity")
    if not isinstance(expected_identity, dict):
        failures.append("missing_installed_identity")
    elif (report.get("prime_source_revision") != PRIME_REVISION
          or report.get("model") != expected_identity.get("model")
          or report.get("thinking") != expected_identity.get("thinking")):
        failures.append("stock_model_identity")
    if (not isinstance(expected_identity, dict) or report.get("worker_model") != expected_identity.get("worker_model")
            or report.get("worker_thinking") != expected_identity.get("worker_thinking")
            or not expected_identity.get("worker_model")):
        failures.append("worker_model_identity")
    for role, model_key, thinking_key in (("coordinator", "model", "thinking"), ("worker", "worker_model", "worker_thinking")):
        observed = report.get("native_identities", {}).get(role, {})
        entries = observed.get("entries", [])
        models = [e for e in entries if e.get("type") == "model_change"]
        levels = [e for e in entries if e.get("type") == "thinking_level_change"]
        if (observed.get("model") != report.get(model_key) or observed.get("thinking") != report.get(thinking_key)
                or not models or models[-1].get("provider", "") + "/" + models[-1].get("modelId", "") != report.get(model_key)
                or not levels or levels[-1].get("thinkingLevel") != report.get(thinking_key)
                or not observed.get("sha256") or not observed.get("session_id")):
            failures.append(role + "_native_identity")
    if not report.get("session_id") or report.get("protocol") != 7 or report.get("schema") != 30:
        failures.append("native_session_contract")
    trace = report.get("trace", [])
    stream_writes = [event for event in trace if event.get("operation") == "write" and event.get("command") == "prompt_and_wait" and event.get("fields", {}).get("message", "").startswith("Current files for stream ")]
    expected = 'Current files for stream ' + state._json(report.get("stream")) + ', Prime session ' + state._json(report.get("session_id")) + ', command '
    if not stream_writes or any(not event["fields"]["message"].startswith(expected) or event["fields"].get("activeSessionId") != report.get("active_session_id") for event in stream_writes):
        failures.append("same_durable_session")
    compacts = [e for e in trace if e.get("operation") == "write" and e.get("command") == "compact"]
    if len(compacts) != 1 or compacts[0]["fields"].get("activeSessionId") != report.get("active_session_id"):
        failures.append("one_direct_compact")
    if not any(e["fields"].get("streamingBehavior") == "steer" for e in stream_writes):
        failures.append("actual_steer_lane")
    return failures


def _fixture(root, stream_id, marker):
    product = confined(root, root / "worktrees" / (stream_id + "-product"))
    if product.exists():
        raise StreamsError("refusing existing native fixture worktree")
    product.mkdir(parents=True)
    project.git(product, "init")
    project.git(product, "config", "user.name", "PoC fixture")
    project.git(product, "config", "user.email", "poc@example.invalid")
    (product / "protected.txt").write_text("Must remain unchanged.\n")
    (product / "check_fixture.py").write_text('import json\nfrom pathlib import Path\ndata=json.loads(Path("answer.json").read_text())\nassert data == ' + repr({"marker": marker, "answer": 5}) + '\nassert Path("protected.txt").read_text() == "Must remain unchanged.\\n"\nprint("marker, answer and protected behavior verified")\n')
    project.git(product, "add", "--", "protected.txt", "check_fixture.py")
    project.git(product, "commit", "-m", "Finite PoC fixture")
    return product


def _rotation(root, stream_id):
    stream = root / "reports" / (stream_id + "-rotation")
    if stream.exists():
        raise StreamsError("refusing existing rotation fixture")
    stream.mkdir()
    project.git(stream, "init")
    project.copy_missing(project.templates_dir() / "prime", stream)
    original = state.save_message(stream, command_id=str(uuid4()), session_id="offline-rotation", text="Whole open request must survive unrelated notes", sender="fixture", send_as="steer")["entry"]
    raw = state.read_entry(stream, original)
    for number in range(31):
        state.append_log(stream, subject="Unrelated finding", body={"number": number})
    current = state.check_state(stream)
    if len(current.log) != 30 or current.goals.work[0].original_entry != original or state.read_entry(stream, original) != raw:
        raise StreamsError("rotation lost open work or exact original")
    return {"verified": True, "evidence": [str(stream / "STATE.md"), str(stream / "history" / original)]}


def _native_failure(result):
    frame = result.get("frame", {})
    if frame.get("success") is not True:
        raise NativeBlocked(frame.get("error", "native outcome unknown"))


class NativeBlocked(StreamsError):
    pass


def _stage(report, name, *evidence):
    report["stages"][name] = {"verified": True, "evidence": list(evidence)}


def _record_native_identity(root, client, identity, model, thinking):
    _, connection = prime.resolve_session(client, identity.session_id, identity.active_session_id)
    path = confined(root, Path(connection["sessionFile"]))
    if not path.is_relative_to(root / "prime/agent/sessions"):
        raise StreamsError("native identity transcript is outside owned session storage")
    entries = [json.loads(line) for line in path.read_text().splitlines()]
    models = [e for e in entries if e.get("type") == "model_change"]
    levels = [e for e in entries if e.get("type") == "thinking_level_change"]
    if not models or not levels or models[-1].get("provider", "") + "/" + models[-1].get("modelId", "") != model or levels[-1].get("thinkingLevel") != thinking:
        raise StreamsError("native transcript does not preserve requested role model/thinking")
    return {"session_id": identity.session_id, "active_session_id": identity.active_session_id, "model": model,
            "thinking": thinking, "entries": [models[-1], levels[-1]], "path": str(path), "sha256": digest(path)}


def _run_native(root, stream, installation, report, client, product, marker):
    identity = prime.create_stream_session(client, stream)
    report["session_id"], report["active_session_id"] = identity.session_id, identity.active_session_id
    _, initial_connection = prime.resolve_session(client, identity.session_id, identity.active_session_id)
    native_path = confined(root, Path(initial_connection["sessionFile"]))
    if not native_path.is_relative_to(root / "prime/agent/sessions"):
        raise StreamsError("native session file is not in owned storage")
    report["native_session_file"] = str(native_path)
    save_threads(stream / "threads.tsv", [Thread(identity.session_id, "coordinator", "", str(stream), "", "", installation["model"], installation["thinking"], Status.active, utc_now())])
    session_dir = root / "prime/agent/sessions"
    body = (f"Finite PoC whole request. Marker {marker}. Actual product worktree {product}. "
            "Answer 2 + 3 as 5 in answer.json with exactly keys marker and answer, and preserve protected.txt. "
            "Keep this whole request open until the verifier runs its computed closing check after compaction. "
            "Interpret every unread whole message through pi-streams state update with current --expect SHA; retain Required, all workers and waits. "
            "Use state check/read-entry on the supplied absolute stream path. Update JSON is {goals,rules,entry}, with null unchanged sections and entry {subject,body,original_entries}. "
            "The verifier will dispatch the clean worker and return its result. Do not create another worker or external job. "
            "On save-STATE, invoke the checked update and retain all unfinished work. After resume, review the worker's summary against this original intent, not just its plan. "
            "Record a source-bound text proof with media_type, text, sha256 and original_entries in the checked update entry body. Do not close from prose.\n"
            + ("Inert finite context fixture data. Preserve only its marker, not a new task. " * 350))
    pending = prime.send_stream_message(client, stream, identity, body=body, sender="poc-operator", lane="followUp", wait_result=False, sessions_dir=session_dir)
    if not isinstance(pending, prime.PendingMessage):
        raise NativeBlocked("initial fixture input was not sent")
    first_id = pending.command_id
    first_snapshot = state.parse_state(client.snapshots[first_id]["state"])
    original = next(e for e in first_snapshot.log if e.command == first_id and state._original(e))
    if original.body["text"] != body or not any(w.original_entry == original.file for w in first_snapshot.goals.work):
        raise StreamsError("intake snapshot did not contain whole original and Goals")
    _stage(report, "intake", original.file, state.sha256(pending.text))
    busy = False
    while first_id not in client.replies:
        _, connection = prime.resolve_session(client, identity.session_id, identity.active_session_id)
        usage = connection.get("contextUsage")
        if isinstance(usage, dict) and isinstance(usage.get("percent"), (int, float)):
            report["observed_percentages"].append(usage["percent"])
        if connection.get("isStreaming") is True:
            busy = True
            break
        if first_id not in client.replies:
            time.sleep(.05)
    if first_id in client.replies and client.replies[first_id]["success"] is False:
        _native_failure(prime.finish_message(client, stream, pending, sessions_dir=session_dir))
    if not busy:
        raise Inconclusive("fixture completed before a busy native steer could be observed")
    steer = prime.send_stream_message(client, stream, identity, body=f"Steer {marker}. Preserve the whole original ask, answer and protected behavior. Keep work requested until checked close.", sender="poc-operator", lane="steer", wait_result=False, sessions_dir=session_dir)
    if not isinstance(steer, prime.PendingMessage):
        raise StreamsError("actual steer was held instead of sent")
    _stage(report, "steer", steer.command_id, "busy native observation")
    first = prime.finish_message(client, stream, pending, sessions_dir=session_dir)
    _native_failure(first)
    report.setdefault("native_identities", {})["coordinator"] = _record_native_identity(root, client, identity, installation["model"], installation["thinking"])
    while True:
        if steer.command_id in client.replies and client.replies[steer.command_id]["success"] is False:
            _native_failure(prime.finish_message(client, stream, steer, sessions_dir=session_dir))
        idle, _ = prime.native_idle(client, identity)
        if steer.command_id in client.replies:
            if client.replies[steer.command_id]["success"] is False:
                _native_failure(prime.finish_message(client, stream, steer, sessions_dir=session_dir))
            if idle:
                break
        time.sleep(.05)
    refs = [w.original_entry for w in state.check_state(stream).goals.work]
    worker, worker_result = spawn_prime_worker(client, stream, worktree=product,
        work=f"Write answer.json with exactly marker={marker!r}, answer=5. Preserve protected.txt. Run python3 check_fixture.py, report actual target/invocation/result and uncertainty. Do not commit or create state files.",
        original_entries=refs, poteto_path=installation["paths"]["poteto"])
    _native_failure(worker_result)
    report["native_identities"]["worker"] = _record_native_identity(root, client, worker, installation["worker_model"], installation["worker_thinking"])
    if (product / "STATE.md").exists() or (product / "stream.toml").exists() or (product / "AGENTS.md").exists():
        raise StreamsError("clean worker created stream state or role files")
    _stage(report, "worker", worker.session_id, worker_result["entry"])
    current = state.check_state(stream)
    if {w.original_entry for w in current.goals.work} != set(refs) or current.goals.status == "paused":
        raise StreamsError("fixture instructions changed before worker-result handback")
    state.update_state(stream, expect=current.sha256,
        goals=replace(current.goals, objective="Review the returned clean-worker summary against the whole original fixture after compaction.", status="active",
                      work=tuple(replace(w, next="Review the saved worker result after compaction, then retain work for the verifier's computed check.", waiting_for=None) for w in current.goals.work)),
        rules=None, entry={"subject": "Verifier returned its fixture worker result", "original_entries": refs,
            "body": {"worker_session": worker.session_id, "worker_reply_entry": worker_result["entry"],
                     "findings": "The verifier-dispatched worker has returned a saved successful native result. Review is now eligible. Compaction and the later computed check do not require human permission. The whole original remains requested; this is not completion."}})
    result = prime.finish_message(client, stream, steer, sessions_dir=session_dir)
    _native_failure(result)
    compaction = result.get("compaction")
    if not isinstance(compaction, dict) or compaction.get("status") != "verified":
        if isinstance(compaction, dict) and compaction.get("status") in {"not-due", "unknown"} and "error" not in compaction:
            raise Inconclusive("finite native fixture did not prove the configured percentage crossing")
        raise StreamsError("percentage sequence did not verify: " + str(compaction))
    current, entries = prime.stream_entries(stream)
    notes = prime.dcr_entries(entries, identity.session_id)
    request = next(e for e in notes if e.command == compaction["command"] and e.body["result"] == "requested")
    if request.body["trigger"] != "percentage" or not request.body["percent"] > installation["threshold_percent"]:
        raise StreamsError("compact was not selected by the actual percentage predicate")
    report["observed_percentages"].append(request.body["percent"])
    report["compaction_entry_id"] = compaction["readback"]["id"]
    report["dump_entry_id"] = next(e.body["dump_entry"] for e in notes if e.command == compaction["command"] and e.body["dump_entry"])
    report["resume_command_id"] = compaction["continuation"]["pending"].command_id if compaction["continuation"] else None
    _stage(report, "percentage", request.file, str(request.body["percent"]))
    _stage(report, "checked_save", compaction["dump"]["entry"], report["dump_entry_id"])
    _stage(report, "compact", compaction["command"], report["compaction_entry_id"])
    _stage(report, "disk_readback", compaction["readback"]["path"], compaction["readback"]["sha256"])
    if not compaction["continuation"]:
        raise StreamsError("verified compact had no eligible continuation")
    trace = client.trace
    resume_id = report["resume_command_id"]
    write_at = next(i for i, e in enumerate(trace) if e["operation"] == "write" and e["command_id"] == resume_id)
    release_at = next(i for i, e in enumerate(trace) if i > write_at and e.get("command") == "release_session_input_pause")
    await_at = next(i for i, e in enumerate(trace) if i > write_at and e["operation"] == "wait" and e["command_id"] == resume_id)
    if not write_at < release_at < await_at:
        raise StreamsError("continuation was awaited before pause release")
    _stage(report, "continuation", resume_id, "write < release < await")
    previous = current.goals_rules_sha256
    state.update_state(stream, expect=current.sha256,
        goals=replace(current.goals, objective="Review the handed-over fixture against original intent. Stale probe " + str(uuid4())), rules=None,
        entry={"subject": "Authorized stale-command fixture", "body": {"findings": "Only the plan changes; the whole original remains requested"}, "original_entries": refs})
    sent_before = sum(e.get("command") == "prompt_and_wait" for e in trace)
    try:
        prime.send_stream_message(client, stream, identity, body="Must never be sent", mode="automatic", expected=previous, sessions_dir=session_dir)
    except StreamsError as exc:
        stale_reason = str(exc)
    else:
        raise StreamsError("stale automatic message was accepted")
    if sum(e.get("command") == "prompt_and_wait" for e in trace) != sent_before:
        raise StreamsError("stale refusal still wrote a model message")
    _stage(report, "stale", stale_reason)
    before_review = set(prime.stream_entries(stream)[1])
    review = prime.send_stream_message(client, stream, identity, mode="automatic", original_entries=refs,
        body=f"Review the returned worker summary adversarially against the whole original ask {marker}, the actual target {product}, 2 + 3 = 5 and protected.txt. Record findings and unanswered outcomes as one exact text-proof entry through the checked update. Include the marker, target, protected behavior and any uncertainty. Keep the original request open for computed close. Do not spawn another worker or reviewer unless necessary.", sessions_dir=session_dir)
    _native_failure(review)
    current, entries = prime.stream_entries(stream)
    reviews = [e for ref, e in entries.items() if ref not in before_review and e.file.endswith("-update.md") and e.body.get("media_type") == "text/plain" and set(refs) <= set(e.body.get("original_entries", [])) and all(text in e.body.get("text", "") for text in (marker, str(product), "protected", "5"))]
    if len(reviews) != 1:
        raise StreamsError("stream did not retain one source-bound adversarial self-review of actual result")
    review_entry = reviews[0]
    _stage(report, "self_review", identity.session_id, review_entry.file, state.sha256(review_entry.text))
    answer = (product / "answer.json").read_text()
    report_path = product / "report.txt"
    report_path.write_text(f"Actual target {product}\nOriginal marker {marker}\nExact answer bytes follow.\n{answer}\nStream review entry {review_entry.file}\n")
    target = {"repo": str(product), "commit": project.git(product, "rev-parse", "HEAD").strip(),
              "diff_sha256": state.sha256(project.git(product, "diff", "--binary", "--no-ext-diff", "HEAD", "--")),
              "artifacts": {name: digest(product / name) for name in ("answer.json", "protected.txt")}}
    payload = {"goals": None, "rules": None, "entry": {"subject": "Computed fixture close", "body": {"findings": "Whole marker, answer and protected behavior checked after native compaction and stream review"}, "original_entries": refs}, "target": target,
        "check": {"argv": ["python3", "check_fixture.py"], "cwd": str(product)}, "report": {"path": str(report_path), "sha256": digest(report_path)},
        "proof_entries": [{"entry": review_entry.file, "sha256": state.sha256(review_entry.text), "representation": "full"}], "review": review_entry.file}
    process = subprocess.run([str(root / "bin/pi-streams"), "state", "close", str(stream), "--expect", current.sha256], input=json.dumps(payload), text=True, capture_output=True)
    if process.returncode:
        raise StreamsError("actual state close refused: " + process.stdout + process.stderr)
    closed = json.loads(process.stdout)
    if set(closed) != {"success", "reason", "state_sha256", "history_files"} or closed["success"] is not True:
        raise StreamsError("state close returned a malformed checked result")
    answers = [entry for entry in prime.stream_entries(stream)[1].values()
               if entry.file.endswith("-checked-answer.md") and entry.body.get("original_entries") == refs]
    if len(answers) != 1:
        raise StreamsError("computed close did not retain one exact answer entry")
    saved = answers[0]
    report["check"] = saved.body["result"]["computed"]
    if state.check_state(stream).goals.work or "done" in state.check_state(stream).goals_text.split("### Current objective")[0]:
        raise StreamsError("close lost accounting or added a North Star completion flag")
    _stage(report, "computed_close", saved.file, state.sha256(saved.text), str(report_path))
    report["trace"] = client.trace
    report["artifact_hashes"] = {str(stream / "STATE.md"): digest(stream / "STATE.md"), str(product / "answer.json"): digest(product / "answer.json"), str(report_path): digest(report_path)}


class Inconclusive(StreamsError):
    pass


def verify(root, stream_id):
    root = Path(root)
    installation = _installation(root)
    stream = _stream(root, stream_id)
    report_path = root / "reports" / f"{stream_id}-poc.json"
    if report_path.exists():
        return {"status": "BLOCKED", "stream": stream_id, "reason": "retained verification already exists; inspect it and initialize a new stream instead of adopting or replaying", "report": str(report_path)}
    report = {**{key: installation[key] for key in ("pi_stack_revision", "prime_source_revision", "prime_version", "prime_binary_sha256", "prime_runtime_sha256", "pstack_revision", "model", "thinking", "worker_model", "worker_thinking", "threshold_percent")},
              "expected_identity": {key: installation[key] for key in ("model", "thinking", "worker_model", "worker_thinking")},
              "status": "FAIL", "root": str(root), "stream": stream_id, "session_id": None, "protocol": 7, "schema": 30, "stages": {}, "observed_percentages": []}
    owned = None
    try:
        if doctor(root, stream_id)["status"] != "PASS":
            raise StreamsError("owned installation doctor did not pass")
        if load_threads(stream / "threads.tsv"):
            raise StreamsError("refusing existing native assignments")
        socket = confined(root, root / "prime" / f"poc-{stream_id}.sock")
        if socket.exists() or socket.is_symlink():
            raise StreamsError("refusing existing test socket")
        report["stages"]["rotation"] = _rotation(root, stream_id)
        marker = "poc-" + str(uuid4())
        product = _fixture(root, stream_id, marker)
        log_path = root / "reports" / f"{stream_id}-daemon.log"
        env = {"HOME": os.environ["HOME"], "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"], "LANG": "C.UTF-8"}
        owned = prime.start_owned_daemon(root / "bin/prime-agent", socket, log_path, env=env)
        with RecordingClient(str(socket), stream) as client:
            try:
                _run_native(root, stream, installation, report, client, product, marker)
            finally:
                report["trace"] = client.trace
                report["command_ids"] = [event["command_id"] for event in client.trace if event["operation"] == "write"]
        missing = assess(report, installation)
        if missing:
            raise StreamsError("missing native proof stages: " + ", ".join(missing))
        report["status"] = "PASS"
    except prime.UsageQuotaError as exc:
        report.update(status="BLOCKED", reason="Usage/quota failure. Stopped without retry or fallback. " + str(exc))
    except NativeBlocked as exc:
        report.update(status="BLOCKED", reason=str(exc))
    except Inconclusive as exc:
        report.update(status="INCONCLUSIVE", reason=str(exc))
    except (StreamsError, OSError, ValueError, KeyError, TypeError, IndexError, StopIteration) as exc:
        reason = str(exc) or "missing native proof reference"
        report.update(status="BLOCKED" if any(word in reason.lower() for word in ("auth", "login", "quota", "usage")) else "FAIL", reason=reason)
    finally:
        if owned:
            try:
                prime.stop_owned_daemon(owned)
                report["owned_daemon_stopped"] = owned.process.poll() is not None
            except (StreamsError, OSError) as exc:
                report.update(status="FAIL", owned_daemon_stopped=False, shutdown_error=str(exc))
        for observed in report.get("native_identities", {}).values():
            path = confined(root, Path(observed["path"]))
            observed["sha256"] = digest(path)
            report.setdefault("artifact_hashes", {})[str(path)] = observed["sha256"]
        _report(root, report_path, report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--stream", required=True)
    args = parser.parse_args(argv)
    result = verify(args.root, args.stream)
    print(json.dumps(result, sort_keys=True, ensure_ascii=False))
    return 0 if result["status"] == "PASS" else 1

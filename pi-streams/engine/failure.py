from __future__ import annotations

import json
import hashlib
import re
import stat
import uuid
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import StreamsError, artifacts, clock, dcr, piweb, sessionlog

KINDS = {"usage-limit", "transient", "codex-login", "tool-login", "resource", "model-error", "content-policy"}
LABELS = {"usage-limit": "Codex usage limit", "transient": "Transient provider or connection failure", "codex-login": "Expired Codex login", "tool-login": "Tool login expiry", "resource": "Disk or resource exhaustion", "model-error": "Model error or outage", "content-policy": "Content-policy refusal"}
CONTENT_POLICY = re.compile(r"flagged for possible cybersecurity risk|content[ _-]?(?:policy|filter)|safety[ _-]?(?:policy|filter)|responsible[ _-]?ai[ _-]?policy", re.IGNORECASE)
POLICY_ANALYSIS = "Explain the content-policy restriction and record a blocker. Do not perform the rejected task or any external effects."
POLICY_BLOCKER = "Content-policy blocker. Original context, auto-loaded resources and artifact reads are not proven clean. Preserve lastgood and exact refusal evidence without inference, compaction or rejected-content replay. Drive intent remains on for different authorized work."
TRANSIENT = re.compile(r"overloaded|server.?busy|ECONNRESET|rate.?limit|too many requests|429|500|502|503|504|524|service.?unavailable|server.?error|internal.?error|provider.?returned.?error|network.?error|connection.?(?:error|refused|lost)|other side closed|fetch failed|getaddrinfo|ENOTFOUND|EAI_AGAIN|upstream.?connect|reset before headers|socket hang up|socket connection was closed|timed? out|timeout|terminated|websocket.?(?:closed|error)|ended without|stream ended before (?:message_stop|a terminal response event)|http2 request did not get a response|retry delay|you can retry your request|try your request again|please retry your request|ResourceExhausted", re.IGNORECASE)
NON_TRANSIENT = re.compile(r"insufficient_quota|quota exceeded|billing|usage.?limit|out of budget|available balance|GoUsageLimitError|FreeUsageLimitError", re.IGNORECASE)


@dataclass(frozen=True)
class Classification:
    kind: str
    code: str
    label: str
    provider: str
    reset_at: str = ""
    reset_source: str = ""

    @property
    def automatic_retry(self) -> bool:
        return self.kind == "usage-limit"

    def public(self) -> dict:
        return asdict(self)


def classify(provider: str, message: str, observed_at: str, *, tool_error: bool = False) -> Classification:
    if CONTENT_POLICY.search(message):
        return Classification("content-policy", "content_policy_blocked", LABELS["content-policy"], provider if provider in {"openai-codex", "tool", "engine"} else "unknown")
    data = None
    try:
        parsed = json.loads(message)
        if isinstance(parsed, dict) and isinstance(parsed.get("error"), dict):
            data = parsed["error"]
    except (ValueError, TypeError):
        pass
    code = str(data.get("code", data.get("type", ""))) if data else ""
    text = message.casefold()
    if not code:
        explicit_code = re.search(r"\b(usage_limit_reached|usage_not_included|rate_limit_exceeded)\b", text)
        if explicit_code:
            code = explicit_code[1]
    usage = (provider == "openai-codex" and (code in {"usage_limit_reached", "usage_not_included", "rate_limit_exceeded"} or "chatgpt usage limit" in text or "codex usage limit" in text)) or bool(re.search(r"insufficient_quota|quota exceeded|usage.?limit", text))
    if usage:
        reset, source = "", ""
        raw = data.get("resets_at", data.get("reset_at")) if data else None
        if type(raw) in (int, float):
            try:
                reset = clock.stamp(datetime.fromtimestamp(raw, timezone.utc))
                source = "provider-metadata"
            except (ValueError, OverflowError, OSError):
                pass
        if not reset:
            relative = re.search(r"try again in\s*~?(\d+)\s*min", text)
            observed = clock.parse(observed_at)
            if relative and observed is not None:
                try:
                    reset = clock.stamp(observed + timedelta(minutes=int(relative[1]) + 1))
                    source = "relative-message-fallback"
                except OverflowError:
                    pass
        return Classification("usage-limit", code if code in {"usage_limit_reached", "usage_not_included", "rate_limit_exceeded"} else "usage_limit_reached", LABELS["usage-limit"], provider, reset, source)
    if "enospc" in text or "no space left" in text or "resource exhausted" in text or "out of memory" in text:
        kind, normalized = "resource", "resource_exhaustion"
    elif tool_error and any(word in text for word in ("login expired", "unauthorized", "token expired", "authentication expired")):
        kind, normalized = "tool-login", "tool_auth_expired"
    elif provider == "openai-codex" and any(word in text for word in ("session expired", "login expired", "expired codex login", "token expired", "unauthorized")):
        kind, normalized = "codex-login", "codex_auth_expired"
    elif not tool_error and not NON_TRANSIENT.search(message) and TRANSIENT.search(message):
        kind, normalized = "transient", "transient_error"
    else:
        kind, normalized = "model-error", "model_error"
    return Classification(kind, normalized, LABELS[kind], provider if provider in {"openai-codex", "tool", "engine"} else "unknown")


@dataclass
class Episode:
    id: str
    session: str
    cwd: str
    kind: str
    code: str
    label: str
    observed_at: str
    failure_entry: str
    failure_sha256: str
    provider: str = "unknown"
    authorized_model: str = ""
    authorized_thinking: str = ""
    checkpoint: dict[str, str] | None = None
    recovery_id: str = ""
    authority: dict | None = None
    continuation: dict | None = None
    analysis: dict | None = None
    reset_at: str = ""
    reset_source: str = ""
    saved_entry: str = ""
    saved_sha256: str = ""
    pause_generation: str = ""
    pause_owned: bool = False
    notification: dict[str, str] | None = None
    uncertain_jobs: list[dict[str, str]] = field(default_factory=list)
    cancelled: bool = False
    state: str = "parked"
    retry_reset: str = ""
    retry_id: str = ""
    retry_state: str = ""
    retry_body: str = ""
    retry_goal: str = ""
    retry_generation: str = ""
    detail: str = ""

    def public(self) -> dict:
        return asdict(self)


def retry_ready(episode: Episode, now: str, generation: str, allowed: bool) -> bool:
    reset, current = clock.parse(episode.reset_at), clock.parse(now)
    consumed = clock.parse(episode.retry_reset)
    observed = clock.parse(episode.observed_at)
    if reset is None and observed is not None:
        reset = (consumed or observed) + timedelta(seconds=60)
    return bool(episode.kind == "usage-limit" and episode.pause_owned and not episode.cancelled and not episode.uncertain_jobs
        and episode.saved_entry and episode.saved_sha256 and episode.pause_generation == generation and not allowed
        and reset is not None and current is not None and current >= reset and (consumed is None or reset > consumed))


def load(stream_dir: Path, sid: str) -> Episode | None:
    records = artifacts._read_tick_data(stream_dir).get("failures", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid failure episode records")
    value = records.get(sid)
    if value is None:
        return None
    try:
        result = Episode(**{key: item for key, item in value.items() if key in {field.name for field in fields(Episode)}})
        if result.session != sid or result.kind not in KINDS or not result.id or not Path(result.cwd).is_absolute() or clock.parse(result.observed_at) is None or not isinstance(result.uncertain_jobs, list) or type(result.cancelled) is not bool or type(result.pause_owned) is not bool:
            raise ValueError("mismatched failure ownership or metadata")
        if result.authority is not None and (not isinstance(result.authority, dict) or result.authority.get("kind") != "engine-policy" or result.authority.get("policyId") != "enrolled-prefix-v1" or not isinstance(result.authority.get("enrollmentId"), str) or not result.authority["enrollmentId"] or not isinstance(result.continuation, dict)):
            raise ValueError("invalid or ambiguous saved recovery authority")
        return result
    except (TypeError, ValueError) as exc:
        raise StreamsError(f"invalid failure episode: {exc}") from exc


def save(stream_dir: Path, episode: Episode) -> None:
    data = artifacts._read_tick_data(stream_dir)
    records = data.setdefault("failures", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid failure episode records")
    records[episode.session] = episode.public()
    artifacts._save_tick_data(stream_dir, data)


def receipts(stream_dir: Path) -> list[dict]:
    records = artifacts._read_tick_data(stream_dir).get("failures", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid failure episode records")
    result = []
    for sid in records:
        episode = load(stream_dir, sid)
        if episode is not None:
            result.append({"id": episode.id, "session": episode.session, "kind": episode.kind, "label": episode.label, "state": episode.state, "resetAt": episode.reset_at, "resetSource": episode.reset_source, "retryState": episode.retry_state, "detail": episode.detail, "notificationState": (episode.notification or {}).get("state", "pending"), "uncertainJobs": episode.uncertain_jobs, "checkpoint": None if episode.checkpoint is None else {key: episode.checkpoint[key] for key in ("entryId", "sha256")}})
            if episode.analysis is not None:
                result[-1]["analysis"] = episode.analysis
            from engine.failure_recovery import load as recovery
            operation = recovery(stream_dir, sid)
            if operation is not None:
                pending = {"retiring": "Native retirement is unconfirmed; no deletion claim.", "retired": "Native retirement is verified; host cleanup is pending.", "clearing": "Exact registry/marker cleanup is pending."}
                result[-1]["recovery"] = {"id": operation.id, "fork": operation.fork, "phase": operation.phase, "detail": operation.detail or pending.get(operation.phase, ""), "retainedSha256": (operation.retirement or {}).get("sourceSha256", ""), "retainedEvidence": (operation.retirement or {}).get("cacheFile", "")}
    return result


def _native_boundary(stream_dir: Path, sid: str, cwd: str, status: dict) -> dict | None:
    value = status.get("failureBoundary")
    if value is None:
        return None
    if not isinstance(value, dict) or type(value.get("version")) is not int or value["version"] != 1 or value.get("sessionId") != sid or value.get("cwd") != cwd or value.get("root") != str(stream_dir.resolve()) or value.get("stream") != stream_dir.name or value.get("state") not in ("watching", "parked", "uncertain"):
        raise StreamsError("native failure boundary identity/root is unconfirmed")
    return value


def _publish_marker(stream_dir: Path, episode: Episode, checkpoint: dict | None) -> None:
    if checkpoint is None:
        return
    from engine.project import _write

    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", episode.session) is None:
        raise StreamsError("failure marker requires an exact safe native session ID")
    if episode.checkpoint is not None and any(episode.checkpoint[key] != checkpoint[key] for key in ("entryId", "sha256", "nativeFile")):
        raise StreamsError("parked good-turn checkpoint changed; explicit reconciliation required")
    episode.checkpoint = checkpoint if episode.checkpoint is None else episode.checkpoint
    save(stream_dir, episode)
    directory = stream_dir / "failures"
    if directory.exists() and (directory.is_symlink() or not directory.is_dir()):
        raise StreamsError("failure marker directory must be an owned regular directory")
    directory.mkdir(exist_ok=True)
    path = directory / (episode.session + ".lastgood")
    expected = (checkpoint["entryId"] + "\n").encode()
    try:
        mode = path.lstat().st_mode
    except FileNotFoundError:
        _write(path, expected.decode())
    else:
        if not stat.S_ISREG(mode):
            raise StreamsError("existing failure marker is not a regular owned file; preserved")
        with sessionlog.regular_reader(path) as source:
            if source.read() != expected:
                raise StreamsError("existing failure marker is not this exact owned checkpoint; preserved")


def enrolled_authority(stream_dir: Path, sid: str, cwd: str, path: Path, leaf: object, boundary: dict | None, status: dict, generation: str) -> tuple[dict, dict] | None:
    if status.get("engineFailureRecoverySupport") != "enrolled-prefix-v1" or boundary is None or boundary.get("state") != "parked":
        return None
    enrollment = boundary.get("enrollment")
    parking = boundary.get("parking", {})
    if parking != {"generation": generation, "owned": True}:
        return None
    branch = sessionlog.branch_records(path, sid, cwd, leaf)
    if enrollment is None:
        from engine.threads import load_threads, require_ratified
        require_ratified(stream_dir)
        rows = [row for row in load_threads(stream_dir / "threads.tsv") if row.session == sid and row.worktree == cwd]
        opening = next((entry["message"] for entry, _ in branch if entry.get("message", {}).get("role") == "user"), None)
        if len(rows) != 1 or opening is None:
            raise StreamsError("Recovery needs an exact registry role and original assignment evidence")
        assignment = json.dumps(opening["content"], ensure_ascii=False)
        enrollment = {"id": sid, "policyId": "enrolled-prefix-v1", "role": rows[0].role, "assignment": assignment, "assignmentSha256": hashlib.sha256(assignment.encode()).hexdigest(), "generation": generation}
    if enrollment.get("policyId") != "enrolled-prefix-v1" or any(not isinstance(enrollment.get(key), str) or not enrollment[key] for key in ("id", "role", "assignment", "assignmentSha256", "generation")) or re.fullmatch(r"[a-z][a-z0-9_-]*", enrollment["role"]) is None or hashlib.sha256(enrollment["assignment"].encode()).hexdigest() != enrollment["assignmentSha256"] or parking != {"generation": generation, "owned": True}:
        raise StreamsError("Engine recovery has no exact enrolled assignment or failure-owned parking")
    if not any(entry.get("customType") == "pi-web.stream-failure" and entry.get("data") == boundary for entry, _raw in branch):
        raise StreamsError("Engine recovery parking is not on the exact native branch")
    authority = {"kind": "engine-policy", "policyId": enrollment["policyId"], "enrollmentId": enrollment["id"]}
    continuation = {"role": enrollment["role"], "assignment": enrollment["assignment"], "assignmentSha256": enrollment["assignmentSha256"], "stateSha256": hashlib.sha256((stream_dir / "STATE.md").read_bytes()).hexdigest()}
    return authority, continuation


def observe(stream_dir: Path, sid: str, cwd: str, native: dict, status: dict, at: str, model: str = "", thinking: str = "") -> Episode | None:
    previous = load(stream_dir, sid)
    if status.get("conditionalAdmissionSupport") != "generation-cas-v1" or status.get("recoveryControlSupport") != "question-safe-v1":
        return previous
    path = native.get("path")
    if not isinstance(path, str):
        return previous
    safety = status.get("rotationSafety")
    leaf = safety.get("entryId") if isinstance(safety, dict) else None
    boundary = _native_boundary(stream_dir, sid, cwd, status)
    failed = boundary.get("failure") if boundary is not None and boundary["state"] == "parked" else None
    if boundary is not None and boundary["state"] == "parked" and failed is None:
        raise StreamsError("parked native boundary lacks its exact failure evidence")
    if failed is not None and (not isinstance(failed, dict) or not isinstance(failed.get("entryId"), str) or not isinstance(failed.get("sha256"), str)):
        raise StreamsError("native failure identity/hash is unconfirmed")
    observation = sessionlog.failure_observation(Path(path), sid, cwd, leaf, failed["entryId"] if failed else None, native_retry=status.get("streamRetry") if status.get("streamRetrySupport") == "entry-bound-v1" else None)
    if observation is None:
        return previous
    checkpoint = None
    if failed is not None:
        if observation["sha256"] != failed["sha256"]:
            raise StreamsError("native failure entry hash does not match the persisted branch")
        if boundary.get("checkpoint") is not None:
            if not isinstance(boundary["checkpoint"], dict):
                raise StreamsError("native checkpoint is malformed")
            checkpoint = sessionlog.verify_good_checkpoint(Path(path), sid, cwd, leaf, boundary["checkpoint"], failed["entryId"])
    if checkpoint is not None:
        observation = sessionlog.failure_observation(Path(path), sid, cwd, leaf, failed["entryId"], native_retry=status.get("streamRetry") if status.get("streamRetrySupport") == "entry-bound-v1" else None, checkpoint=checkpoint)
    jobs = observation["uncertainJobs"]
    replay = artifacts._read_tick_data(stream_dir).get("sessions", {}).get(sid, {}).get("replay", [])
    if replay:
        jobs.append({"id": "saved-unconfirmed-replay", "state": "unknown"})
    policy = classify(observation["provider"], observation["message"], at, tool_error=observation["toolError"])
    if previous is not None and previous.failure_entry == observation["entryId"] and previous.failure_sha256 == observation["sha256"]:
        if policy.kind != previous.kind:
            previous.authority = None
            previous.continuation = None
        previous.kind, previous.code, previous.label, previous.provider = policy.kind, policy.code, policy.label, policy.provider
        previous.uncertain_jobs = jobs
        save(stream_dir, previous)
        if previous.kind != "usage-limit" and previous.authority is None:
            _admit_recovery(stream_dir, previous, Path(path), leaf, boundary, status)
        _publish_marker(stream_dir, previous, checkpoint)
        return previous
    prior = previous
    if previous is not None and previous.state == "recovered":
        previous = None
    episode = previous or Episode(uuid.uuid4().hex, sid, cwd, policy.kind, policy.code, policy.label, at, observation["entryId"], observation["sha256"], retry_reset=prior.retry_reset if prior is not None else "")
    episode.kind, episode.code, episode.label, episode.provider = policy.kind, policy.code, policy.label, policy.provider
    if previous is None:
        episode.authorized_model, episode.authorized_thinking = model, thinking
    episode.failure_entry, episode.failure_sha256 = observation["entryId"], observation["sha256"]
    if previous is None or not previous.reset_at or policy.reset_at and clock.parse(policy.reset_at) > clock.parse(previous.reset_at):
        episode.reset_at, episode.reset_source = policy.reset_at, policy.reset_source
    episode.saved_entry, episode.saved_sha256 = observation["savedEntryId"], observation["savedSha256"]
    episode.uncertain_jobs = jobs
    episode.state = "parked"
    if episode.kind != "usage-limit" and checkpoint is None:
        episode.detail = "No confirmed complete native good-turn checkpoint; F-DCR remains blocked without an invented marker."
    if episode.retry_state:
        episode.retry_state = "failed"
    token, allowed = piweb.automatic_admission(status, sid, cwd, "recovery")
    save(stream_dir, episode)
    if allowed:
        stopped = piweb.set_automatic_admission(sid, False, expected_generation=token["generation"])
        episode.pause_generation, episode.pause_owned = str(stopped["generation"]), True
        status["automaticAdmission"] = stopped
    else:
        episode.pause_owned = False
        episode.detail = "Already disabled or stopped; no automatic reset trial may rearm this epoch."
    if episode.kind != "usage-limit":
        _admit_recovery(stream_dir, episode, Path(path), leaf, boundary, status)
    save(stream_dir, episode)
    _publish_marker(stream_dir, episode, checkpoint)
    artifacts.append_log_locked(stream_dir, at, f"Failure {episode.id}", f"Observed {episode.label} for exact session {sid}. Code: {episode.code}. Native failure entry: {episode.failure_entry} SHA-256 {episode.failure_sha256}. Saved input: {episode.saved_entry or 'unknown'}. Reset: {episode.reset_at or 'unknown'}. Task effects remain parked; no environment, rule, skill, memory or provider remedy is authorized.", request_id=f"failure:{episode.id}:{episode.failure_entry}")
    return episode


def policy_continuation(stream_dir: Path, episode: Episode, role: str) -> dict:
    goal = artifacts.resolve_current_goal(artifacts._read_stream_state_locked(stream_dir))
    return {"mode": "permitted-analysis-v1", "role": role, "assignment": POLICY_ANALYSIS,
            "assignmentSha256": hashlib.sha256(POLICY_ANALYSIS.encode()).hexdigest(),
            "blockedGoalSha256": hashlib.sha256(goal.encode()).hexdigest(),
            "policyFailure": {"entryId": episode.failure_entry, "sha256": episode.failure_sha256}}


def policy_blocks_goal(stream_dir: Path, goal: str) -> bool:
    digest = hashlib.sha256(goal.encode()).hexdigest()
    for sid in artifacts._read_tick_data(stream_dir).get("failures", {}):
        episode = load(stream_dir, sid)
        if episode is not None and episode.kind == "content-policy" and (episode.continuation or {}).get("blockedGoalSha256") == digest:
            return True
    return False


def _admit_recovery(stream_dir: Path, episode: Episode, path: Path, leaf: object, boundary: dict | None, status: dict) -> None:
    if episode.kind == "content-policy":
        from engine.threads import load_threads
        rows = [row for row in load_threads(stream_dir / "threads.tsv") if row.session == episode.session and row.worktree == episode.cwd]
        episode.authority = None
        if (episode.continuation or {}).get("policyFailure") != {"entryId": episode.failure_entry, "sha256": episode.failure_sha256}:
            episode.continuation = policy_continuation(stream_dir, episode, rows[0].role) if len(rows) == 1 else None
        episode.detail = POLICY_BLOCKER + (" Separate metadata analysis " + episode.analysis["state"] + ". Original task remains blocked." if episode.analysis is not None else "")
        save(stream_dir, episode)
        artifacts.append_log_locked(stream_dir, episode.observed_at, "Content-policy safe blocker", f"{POLICY_BLOCKER} Native refusal {episode.failure_entry} SHA-256 {episode.failure_sha256}.", request_id=f"policy-safe-blocker:{episode.id}")
        if status.get("cleanPolicyAnalysisSupport") == "clean-policy-analysis-v1" and episode.analysis is None and episode.continuation is not None and not episode.uncertain_jobs and not episode.cancelled:
            from engine.threads import require_ratified
            require_ratified(stream_dir)
            token, allowed = piweb.automatic_admission(status, episode.session, episode.cwd, "recovery")
            if allowed or not episode.authorized_model or not episode.authorized_thinking or boundary is None or boundary.get("parking") != {"generation": token["generation"], "owned": True}:
                return
            piweb.require_settings(status, episode.authorized_model, episode.authorized_thinking)
            request = {"id": episode.id + "-analysis", "basis": "clean-policy-analysis-v1", "expected": {**boundary, "generation": token["generation"]}, "blockedGoalSha256": episode.continuation["blockedGoalSha256"]}
            episode.analysis = {"id": request["id"], "basis": request["basis"], "state": "sending"}
            save(stream_dir, episode)
            try:
                episode.analysis = piweb.analyze_policy(episode.session, episode.cwd, request, episode.authorized_model, episode.authorized_thinking)
            except StreamsError as exc:
                episode.analysis.update(state="uncertain", detail=str(exc))
            episode.detail = POLICY_BLOCKER + " Separate metadata analysis " + episode.analysis["state"] + ". Original task remains blocked. No fork, compaction, RESUME or acceptance."
            save(stream_dir, episode)
            artifacts.append_log_locked(stream_dir, episode.observed_at, "Separate policy metadata analysis", f"Analysis {request['id']} is {episode.analysis['state']}. Basis clean-policy-analysis-v1. Original task remains blocked. Audit evidence: {episode.analysis.get('audit', {})}. No task recovery or acceptance is claimed.", request_id=f"policy-analysis:{episode.id}")
        return
    token, allowed = piweb.automatic_admission(status, episode.session, episode.cwd, "recovery")
    if allowed or episode.cancelled:
        return
    enrolled = enrolled_authority(stream_dir, episode.session, episode.cwd, path, leaf, boundary, status, token["generation"])
    if enrolled is None:
        return
    episode.authority, episode.continuation = enrolled
    episode.continuation.update(nativeFile=str(path), savedInput={"entryId": episode.saved_entry, "sha256": episode.saved_sha256}, handovers=[])
    handover = stream_dir / "handover" / episode.continuation["role"] / (episode.session + ".md")
    if handover.exists():
        with sessionlog.regular_reader(handover) as source:
            raw = source.read()
        if raw.splitlines()[:1] != [("session: " + episode.session).encode()]:
            raise StreamsError("Existing original handover identity is invalid; preserve its evidence")
        episode.continuation["handovers"].append({"path": str(handover), "sha256": hashlib.sha256(raw).hexdigest()})
    episode.pause_owned, episode.pause_generation = True, token["generation"]
    episode.recovery_id = episode.recovery_id or uuid.uuid4().hex
    episode.detail = "Standing charter authorizes exact good-prefix recovery; no new notice is required."
    save(stream_dir, episode)


def trial_receipt_matches(episode: Episode, native: dict) -> bool:
    expected = {"sessionId": episode.session, "cwd": episode.cwd, "generation": episode.retry_generation, "kind": "recovery"}
    return native.get("text") == episode.retry_body and native.get("potetoGoal") == episode.retry_goal and native.get("runId") == episode.id and type(native.get("sequence")) is int and native["sequence"] == 1 and native.get("automaticAdmission") == expected


def step(stream_dir: Path, episode: Episode, status: dict, at: str, native_info: dict | None = None) -> bool:
    from engine.drive import is_paused

    if is_paused(stream_dir):
        return True
    if episode.state == "recovered":
        return False
    if episode.retry_state in {"rearming", "sending", "retained", "uncertain"}:
        if episode.retry_state in {"sending", "retained"}:
            try:
                native = piweb.control_goal_status(episode.session, episode.cwd, episode.retry_id)
            except StreamsError as exc:
                episode.retry_state, episode.detail = "uncertain", str(exc)
                save(stream_dir, episode)
                return True
            if not trial_receipt_matches(episode, native):
                episode.retry_state, episode.detail = "uncertain", "Recovery receiver changed the exact saved trial identity/body/generation."
                save(stream_dir, episode)
                return True
            if native["state"] == "uncertain":
                episode.retry_state = "uncertain"
            elif native["state"] == "superseded":
                episode.cancelled, episode.retry_state = True, "superseded"
            elif native["state"] == "ended" and native_info is not None and isinstance(native_info.get("path"), str):
                safety = status.get("rotationSafety")
                leaf = safety.get("entryId") if isinstance(safety, dict) else None
                prefix = f"Usage-reset reconciliation for failure episode {episode.id}."
                if sessionlog.successful_control_completion(Path(native_info["path"]), episode.session, episode.cwd, leaf, prefix, episode.retry_goal):
                    episode.state, episode.retry_state = "recovered", "ended"
                    artifacts.append_log_locked(stream_dir, at, f"Usage reconciliation {episode.id}", f"The exact saved usage-reset reconciliation {episode.retry_id} completed a native assistant turn. This is continuation evidence, not product completion. No provider/model change or uncertain-job replay was authorized.", request_id=f"failure-recovered:{episode.id}")
            else:
                episode.retry_state = "retained"
            save(stream_dir, episode)
            if episode.state == "recovered":
                from engine.drive import confirm_resume
                confirm_resume(stream_dir, episode.session, episode.session, episode.cwd, episode.retry_generation)
        return True
    token, allowed = piweb.automatic_admission(status, episode.session, episode.cwd, "recovery")
    if not retry_ready(episode, at, token["generation"], allowed) or status.get("pendingAsk") or status.get("pendingDialogs") or status.get("pendingMessageCount", 0):
        return True
    if not episode.authorized_model or not episode.authorized_thinking:
        episode.detail = "Saved authorized model/thinking is unknown; no automatic trial is admitted."
        save(stream_dir, episode)
        return True
    piweb.require_settings(status, episode.authorized_model, episode.authorized_thinking)
    if not piweb.recovery_readiness(episode.session, episode.cwd, status, episode.kind):
        return True
    artifacts._rotate_log_locked(stream_dir)
    goal = artifacts.resolve_current_goal(artifacts._read_stream_state_locked(stream_dir))
    prefix = (f"Usage-reset reconciliation for failure episode {episode.id}. The interrupted owned native input is {episode.saved_entry} SHA-256 {episode.saved_sha256}. "
              "Reconcile that saved step under the latest STATE. Never replay an arbitrary shell submission, resubmit an uncertain external job, revive cancelled work, or repair environment/auth/resources. If safe job status/idempotence is unknown, park and report.\n")
    episode.retry_reset, episode.retry_id, episode.retry_state = episode.reset_at or at, uuid.uuid4().hex, "rearming"
    episode.retry_goal, episode.retry_body = goal, prefix + dcr.resume_text(stream_dir, goal)
    save(stream_dir, episode)
    try:
        ready = piweb.set_automatic_admission(episode.session, True, expected_generation=episode.pause_generation)
        episode.retry_generation, episode.retry_state = str(ready["generation"]), "sending"
        save(stream_dir, episode)
        response = piweb.control_goal(episode.session, episode.retry_id, episode.id, 1, episode.retry_body, goal, {"sessionId": episode.session, "cwd": episode.cwd, "generation": episode.retry_generation, "kind": "recovery"})
        if not trial_receipt_matches(episode, response):
            raise StreamsError("Recovery receiver changed the exact saved trial identity/body/generation")
        episode.retry_state = "uncertain" if response["state"] == "uncertain" else "retained"
        save(stream_dir, episode)
    except StreamsError as exc:
        episode.retry_state, episode.detail = "uncertain", str(exc)
        save(stream_dir, episode)
    return True

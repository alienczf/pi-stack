from __future__ import annotations

import json
import hashlib
import re
import stat
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path

from engine import StreamsError, artifacts, clock, dcr, piweb, sessionlog

KINDS = {"usage-limit", "codex-login", "tool-login", "resource", "model-error"}
LABELS = {"usage-limit": "Codex usage limit", "codex-login": "Expired Codex login", "tool-login": "Tool login expiry", "resource": "Disk or resource exhaustion", "model-error": "Model error or outage"}


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
    usage = provider == "openai-codex" and (code in {"usage_limit_reached", "usage_not_included", "rate_limit_exceeded"} or "chatgpt usage limit" in text or "codex usage limit" in text)
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
    ratification: dict | None = None
    verification: dict | None = None
    recovery_id: str = ""
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
    notification = episode.notification
    consumed = clock.parse(episode.retry_reset)
    return bool(episode.kind == "usage-limit" and episode.pause_owned and not episode.cancelled and not episode.uncertain_jobs
        and episode.saved_entry and episode.saved_sha256 and episode.pause_generation == generation and not allowed
        and reset is not None and current is not None and current >= reset and (consumed is None or reset > consumed)
        and notification is not None and notification.get("state") == "delivered" and notification.get("deliveryId") and notification.get("route") == "verified-zf-dm-v1")


def load(stream_dir: Path, sid: str) -> Episode | None:
    records = artifacts._read_tick_data(stream_dir).get("failures", {})
    if not isinstance(records, dict):
        raise StreamsError("invalid failure episode records")
    value = records.get(sid)
    if value is None:
        return None
    try:
        result = Episode(**value)
        if result.session != sid or result.kind not in KINDS or not result.id or not Path(result.cwd).is_absolute() or clock.parse(result.observed_at) is None or not isinstance(result.uncertain_jobs, list) or type(result.cancelled) is not bool or type(result.pause_owned) is not bool:
            raise ValueError("mismatched failure ownership or metadata")
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
    observation = sessionlog.failure_observation(Path(path), sid, cwd, leaf, failed["entryId"] if failed else None)
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
    jobs = observation["uncertainJobs"]
    replay = artifacts._read_tick_data(stream_dir).get("sessions", {}).get(sid, {}).get("replay", [])
    if replay:
        jobs.append({"id": "saved-unconfirmed-replay", "state": "unknown"})
    if previous is not None and previous.failure_entry == observation["entryId"] and previous.failure_sha256 == observation["sha256"]:
        if previous.uncertain_jobs != jobs:
            previous.uncertain_jobs = jobs
            save(stream_dir, previous)
        _publish_marker(stream_dir, previous, checkpoint)
        return previous
    policy = classify(observation["provider"], observation["message"], at, tool_error=observation["toolError"])
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
    save(stream_dir, episode)
    _publish_marker(stream_dir, episode, checkpoint)
    artifacts.append_log_locked(stream_dir, at, f"Failure {episode.id}", f"Observed {episode.label} for exact session {sid}. Code: {episode.code}. Native failure entry: {episode.failure_entry} SHA-256 {episode.failure_sha256}. Saved input: {episode.saved_entry or 'unknown'}. Reset: {episode.reset_at or 'unknown'}. Task effects remain parked; no environment, rule, skill, memory or provider remedy is authorized.", request_id=f"failure:{episode.id}:{episode.failure_entry}")
    return episode


def ratify_locked(stream_dir: Path, sid: str, episode_id: str, notice_id: str, notice: object, at: str) -> dict:
    from engine.threads import _native_session, load_threads, require_ratified

    require_ratified(stream_dir)
    if re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9-]*", sid) is None:
        raise StreamsError("Ratification requires an exact safe original session ID")
    episode = load(stream_dir, sid)
    rows = [row for row in load_threads(stream_dir / "threads.tsv") if row.session == sid]
    if episode is None or episode.id != episode_id or len(rows) != 1 or episode.state != "parked" or episode.kind == "usage-limit" or episode.checkpoint is None or not notice_id:
        raise StreamsError("Ratification requires the exact current parked nonusage episode and good checkpoint")
    with sessionlog.regular_reader(stream_dir / "failures" / (sid + ".lastgood")) as marker:
        if marker.read() != (episode.checkpoint["entryId"] + "\n").encode():
            raise StreamsError("Failure marker no longer matches the exact parked checkpoint")
    native = _native_session(sid, Path(rows[0].worktree))
    status = native.status
    piweb.require_settings(status, episode.authorized_model, episode.authorized_thinking)
    boundary = _native_boundary(stream_dir, sid, episode.cwd, status)
    if boundary is None or boundary["state"] != "parked" or status.get("failureRatificationConfigured") is not True:
        raise StreamsError("Existing authenticated ZF intake/verifier is unavailable; original remains parked")
    token, allowed = piweb.automatic_admission(status, sid, episode.cwd, "recovery")
    if allowed:
        raise StreamsError("Native failure parking is unconfirmed; no ratification is admitted")
    notice_hash = hashlib.sha256(json.dumps(notice, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    if episode.verification is not None and episode.verification.get("noticeId") == notice_id and episode.verification.get("noticeSha256") != notice_hash:
        raise StreamsError("Genuine notice identity changed bytes; preserved the prior verification intent")
    if episode.ratification is not None:
        if episode.ratification.get("noticeId") != notice_id or episode.ratification.get("generation") != token["generation"]:
            raise StreamsError("Episode already has a different or superseded ratification; no overwrite")
        return episode.ratification
    target = {"sessionId": sid, "cwd": episode.cwd, "root": str(stream_dir.resolve()), "stream": stream_dir.name, "episode": episode.id, "checkpoint": {key: episode.checkpoint[key] for key in ("entryId", "sha256")}, "failure": {"entryId": episode.failure_entry, "sha256": episode.failure_sha256, "kind": episode.kind}}
    episode.verification = {"noticeId": notice_id, "noticeSha256": notice_hash, "state": "sending"}
    save(stream_dir, episode)
    try:
        receipt = piweb.ratify_failure(sid, episode.cwd, {"id": notice_id, "episode": episode.id, "notice": notice, "expected": {**boundary, "generation": token["generation"]}})
        if receipt.get("id") != notice_id or receipt["noticeId"] != notice_id or receipt["target"] != target or receipt["generation"] != token["generation"] or not receipt["provenance"]:
            raise StreamsError("Native ratification changed its exact notice/episode/checkpoint/generation")
        evidence = sessionlog.read_record(Path(native.info["path"]), sid, receipt["entryId"], receipt["sha256"])
        record = json.loads(evidence.raw)
        data = record.get("data")
        if record.get("type") != "custom" or record.get("customType") != "pi-web.failure-ratification" or not isinstance(data, dict) or any(data.get(key) != receipt[key] for key in ("version", "id", "noticeId", "provenance", "instructions", "generation", "target")):
            raise StreamsError("Ratification lacks its exact persisted native verifier receipt")
        fresh = piweb.session_status(sid)
        current, _allowed = piweb.automatic_admission(fresh, sid, episode.cwd, "recovery")
        leaf = fresh.get("rotationSafety", {}).get("entryId")
        if current["generation"] != token["generation"] or _allowed or not any(entry["id"] == receipt["entryId"] for entry, _raw in sessionlog.branch_records(Path(native.info["path"]), sid, episode.cwd, leaf)):
            raise StreamsError("Newer stop/input or branch superseded ratification before publication")
        artifacts.append_log_locked(stream_dir, at, "Ratified failure recovery", f"Authenticated notice {notice_id} ratifies only session {sid}, episode {episode.id}. Exceptional instructions remain in the verified native receipt; this acknowledgement admits no task effects by itself.", request_id=f"ratification:{sid}:{notice_id}")
        episode.ratification = receipt
        episode.recovery_id = episode.recovery_id or uuid.uuid4().hex
        episode.verification["state"] = "verified"
        save(stream_dir, episode)
        return receipt
    except StreamsError as exc:
        episode.verification["state"] = "unconfirmed"
        save(stream_dir, episode)
        raise StreamsError(f"Ratification remains unconfirmed and parked: {exc}") from exc


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
        return True
    token, allowed = piweb.automatic_admission(status, episode.session, episode.cwd, "recovery")
    if not retry_ready(episode, at, token["generation"], allowed) or status.get("pendingAsk") or status.get("pendingExtensionDialogs") or status.get("pendingMessageCount", 0):
        return True
    if not episode.authorized_model or not episode.authorized_thinking:
        episode.detail = "Saved authorized model/thinking is unknown; no automatic trial is admitted."
        save(stream_dir, episode)
        return True
    piweb.require_settings(status, episode.authorized_model, episode.authorized_thinking)
    artifacts._rotate_log_locked(stream_dir)
    goal = artifacts.resolve_current_goal(artifacts._read_stream_state_locked(stream_dir))
    prefix = (f"Usage-reset reconciliation for failure episode {episode.id}. The interrupted owned native input is {episode.saved_entry} SHA-256 {episode.saved_sha256}. "
              "Reconcile that saved step under the latest STATE. Never replay an arbitrary shell submission, resubmit an uncertain external job, revive cancelled work, or repair environment/auth/resources. If safe job status/idempotence is unknown, park and report.\n")
    episode.retry_reset, episode.retry_id, episode.retry_state = episode.reset_at, uuid.uuid4().hex, "rearming"
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

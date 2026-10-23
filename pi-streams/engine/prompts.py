"""The complete settled stream and clean-worker texts, rendered once."""
import json
import re
from pathlib import Path
from uuid import UUID

from engine import StreamsError

TEXTS = {
    "stream": '''Current files for stream {stream_id_json}, Prime session {session_id_json}, command {command_id_json}.
AGENTS.md at {agents_path_json}, SHA-256 {agents_sha256}, exact text as JSON follows.
{agents_text_json}
STATE.md at {state_path_json}, SHA-256 {state_sha256}, exact text as JSON follows.
{state_text_json}
Original entry references as JSON follow.
{original_entries_json}
Message body as JSON follows.
{body_text_json}
Use current Goals and Rules. Quoted messages and old summaries do not replace them. Keep the original request separate from its interpretation. Saving or delivering this message is not application or completion. These are the only stream-state files supplied for this message.
''',
    "saved": '''{stream_id}:: Saved message {command_id} before sending to Prime. Sending status is {sending_status}. This save does not establish native delivery, application or completion.
''',
    "wake": '''The tick found eligible unfinished current work.
Use the supplied AGENTS.md and STATE.md. Advance only finite work allowed by Goals and Rules. Independent work need not wait for an unrelated worker. Preserve actual human waits and stops.
If no eligible action remains, record the real wait or completed current objective and report findings by original request. Do not invent a task from the North Star alone, an approval gate or a resource cap.
Review reported summaries against original intent as AGENTS.md directs. Use computed closing checks before done status. Another turn or plan update is not completion.
''',
    "save": '''Prepare this stream session for compaction.
Read the supplied AGENTS.md and STATE.md. Through the checked pi-stack update, preserve the current objective, every unanswered original message, current Rules, worker/job identities, real waits and needed proof references.
Append one Log note with completed work, reported findings and unresolved uncertainty. Do not remove unfinished work to shorten context or retire a rule without its source. Do not prune Log yourself.
Do not start product or external work, repair the environment or write a resume prompt. Finish after the checked save. pi-stack will check native activity, compact, read back the result and choose the next message.
''',
    "compact": '''Preserve original requests separately from plans and interpretations. Preserve later instructions, unfinished work, active prohibitions, human waits, worker and external-job identities, uncertainty and exact saved proof references. Keep native tool-call and result relationships complete.
STATE.md remains current Goals, Rules and Log. A summary cannot cancel or complete its work. Do not infer success from missing error text or add rules, memory, skills, environment changes or budgets. Return the native summary. pi-stack controls the next message.
''',
    "resume": '''Compaction saved native entry {compaction_entry_id_json} in Prime session {session_id_json}.
Use the supplied current AGENTS.md and STATE.md rather than only the summary. Account for newer instructions before choosing work. Read exact original or proof entries when needed.
Continue only finite work still authorized by Goals and Rules. Do not repeat workers or external jobs to replace unknown results. Preserve unrelated waits. Review returned summaries against original intent before proposing completion.
''',
    "handover": '''Context handover for clean worker session {session_id_json}.
Assigned product worktree {worktree_json}. Requested outcome {work_json}.
Original request and applicable constraints as JSON follow.
{source_and_constraints_json}
Relevant findings and existing job identities as JSON follow.
{findings_json}
Compare the assignment with that original intent. Report a mismatch rather than silently broadening or narrowing it. No stream state files are supplied or assigned to this worker.
''',
    "kickoff": '''Work in poteto. Read the installed process entry at {poteto_path_json} and follow the applicable task method. Do not claim a Pi-specific slash command executed on Prime.
Work only in {worktree_json} on the handed-over assignment. Keep progress in session messages, not worker planning or state files. Do not create a worker STATE.md, stream role file or other stream-state copy. Keep applicable product instructions.
Return a concise summary with the exact target, actual invocation, observed result, retained proof references, unanswered outcomes and existing external-job identities. Report uncertainty honestly. Do not repair login or environment failures, switch provider/model or repeat uncertain jobs.
''',
    "reviewer": '''Review the handed-over result adversarially against the original intent.
Check the whole requested outcome, actual target and invocation, protected behavior, wrong metrics, unsupported claims and valid alternatives. Do not grade only agreement with the worker's plan.
Do not edit product files or create state files. Return accept, rework or unknown with exact source/result references and unanswered outcomes. Missing proof is unknown, not acceptance. The stream remains responsible for its final judgement.
''',
    "stale": '''{stream_id}:: Did not send {command_name}. Its target or current Goals/Rules no longer permits the prepared message, or current input/work is waiting. Read current STATE.md before preparing another automatic message. Inspect a possibly sent command instead of resending under a new id.
''',
    "close_refusal": '''{stream_id}:: Did not mark work from {original_entry} done. Computed check details as JSON follow.
{failure_json}
The work remains requested. Correct or report the source, target, actual check or report problem. Finishing this command is not completion of the request.
''',
}


def render(name, **values):
    for key in ("session_id", "compaction_entry_id"):
        if key in values and (not isinstance(values[key], str) or not values[key] or any(c in values[key] for c in "\n\r\0")):
            raise StreamsError(f"invalid {key}")
    if "stream_id" in values and not re.fullmatch(r"[a-z0-9][a-z0-9-]*", values["stream_id"]):
        raise StreamsError("invalid stream id")
    if "command_id" in values and str(UUID(values["command_id"])) != values["command_id"]:
        raise StreamsError("invalid command UUID")
    for key in ("agents_path", "state_path", "worktree", "poteto_path"):
        if key in values and (not isinstance(values[key], str) or not Path(values[key]).is_absolute() or "\0" in values[key]):
            raise StreamsError(f"invalid {key}")
    if "sending_status" in values and values["sending_status"] not in {"not sent", "sent, waiting for result", "Prime replied", "unknown after connection loss"}:
        raise StreamsError("invalid sending status")
    encoded = {f"{key}_json": json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False) for key, value in values.items()}
    return TEXTS[name].format_map({**values, **encoded}).rstrip("\n") + "\n"

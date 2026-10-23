Runtime: stock Prime, no Prime changes; merged candidate (Z23)

# Repo judgement and stock Prime hooks

**New concepts**

| plain name | one-line meaning | corpus failure it fixes | why no existing artifact or term can carry it |
|---|---|---|---|

None. Goals holds current requested work, Rules holds current rulings, and Log/history hold original messages, commands, results and reviews. Prime session and command IDs keep their existing meanings.

## 1 Overview

This candidate combines repo-owned work from [31](31-design-a-detailed.md) with public stock Prime commands from [42](42-design-b-prime-unchanged.md). [Z25/G36](03-decisions.md#z25-zf-t232u-2026-10-24-0042-sgt--t233u-0044-sgt-answers-to-the-seven-open-questions-on-51) answers the seven former questions. [ZF's t232u and t233u](00b-zf-messages-verbatim.md) are the original instructions. Nothing beyond those answers is locked under Z17. No percentage, model or other runtime default is selected here.

The stream reads one current STATE. pi-stack saves the messages it sends to that stream, supplies fresh STATE once per message, rejects stale pi-stack messages, wakes eligible work and checks computable completion conditions. Running tools receive a best-effort stock abort when the operator requests a stop. Terminal input is intentionally uncaptured. Attachments are rejected. These are the accepted boundaries under Z25.

Workers are not streams. They are clean poteto sessions with a context handover and kickoff, no stream role file and no state files. The stream reviews every reported summary adversarially against original intent. It creates a reviewer only when its judgement calls for one. That guidance belongs in AGENTS.md, not a review hook.

Compaction is owned by pi-stack. [43](43-prime-compaction-hooks.md) establishes that stock v0.10.1 has an after-compaction signal but no before-compaction hook. Set `compaction.enabled=false` before constructing the stream session. One pi-stack percentage check then drives save STATE, direct compact, readback and resume. Explicit DCR uses that same sequence.

Only the stream receives AGENTS.md and STATE.md automatically. STATE has exactly Goals, Rules and Log, with only Log capped at 30. Native safety/tool/project instructions remain stock. Login/auth failures, outages and recovery are permanently outside this design.

Stock Prime is v0.10.1, source `8aac8692456c00c01d4e53e60e6d3347a3506559`. Rust paths below identify existing behavior, never implementation targets. All proposed changes are in pi-stack. [41](41-design-b-prime-detailed.md) remains reference only. This document is the coding plan for the `feat/merged-poc` branch requested in Z26, not evidence that the PoC already works.

## 2 Components and justification

Layers follow [02-principles.md](02-principles.md). F-numbers retain the corpus definitions in [30](30-research-designs.md#input-3-the-explicit-balance-after-zfs-remedies). Coverage is a proposed mechanism, not a measured prevention rate.

| Component | Layer and why a stronger layer cannot carry it | Corpus purpose and limit |
|---|---|---|
| Current work and rulings | LAYER 1. Goals/Rules are the current context. No stronger layer exists. | F2, F3, F9, F10, F12. Replanning does not cancel another request. |
| Originals, results and reviews | LAYER 1. Log/history retain exact repo bytes. No stronger layer exists. | F5, F6, F8, F10. Hashes alone prove neither retained bytes nor human authority. |
| File and completion checks | LAYER 2. Context cannot execute source, target, report and actual-test checks. | F2, F4, F5, F10, F11. A chosen test can still ask the wrong question. |
| Saving, freshness and stale-message rejection | LAYER 3. Files/CI cannot order a live send or refresh its message. | F2, F3, F6, F8, F10. Covers pi-stack's selected stock input paths. |
| Tick wake and best-effort stop | LAYER 3. Files/CI cannot wake idle work or call native abort. | F1, F9, F12. An accepted abort is not proof that all effects stopped. |
| One compaction controller | LAYER 3. Files/CI cannot sequence a live save turn, compact and resume. | F6. Waits for observed idle. No hard token ceiling is claimed. |
| History rotation and narrow publication | LAYER 3 moves files/stages paths. LAYER 2 verifies bytes, which layout alone cannot do. | F6, F11. No broad cleanup or disk-growth remedy. |
| Stream judgement and worker method | LAYER 4 gives adversarial-review guidance. LAYER 5 supplies poteto task methods where stronger checks cannot decide meaning. | F3, F4, F5, F9, F10. No mandatory reviewer session or review-admission hook. |

F7 environment recovery is permanently excluded. Reporting a received error is not a recovery mechanism. Bootstrap installs the same checker/update implementation used by local verification and supported CI. Unsupported wiring reports unwired, not success. Product regressions remain in the product's existing test location.

## 3 Hooks

`engine/` abbreviates `pi-streams/engine/`. All named functions are proposed pi-stack functions. The public transport in `bin/prime_cli.py` validates protocol 7/schema 30, command IDs, response shape and interleaved events. Resolve routing `activeSessionId` separately from durable `get_connection_state.sessionId`. Repo entries use the durable ID; stock command fields use the routing ID. [31 §3][a-hooks] [42 §3][stock-hooks]

### Save-incoming-message hook

- **Trigger/layer.** Human text entering a stream through pi-stack's supported `prompt_and_wait` path. LAYER 3 must save before the live send; files/CI cannot enforce that order.
- **Input/output.** Registered stream/session, retained command UUID, exact UTF-8 text, trusted sender and `steer` or `followUp` lane. Atomically append the original Log entry and an unread Goals item. Reject attachments. Generated controls and worker results link existing work instead of becoming new human requests.
- **Code/stock command.** `engine/prime.py::send_stream_message` calls `engine/state.py::save_message`, then sends `prompt_and_wait{activeSessionId,message,streamingBehavior}` with that UUID as envelope `id`. [42 §3][stock-hooks]
- **Failure/repeat.** Failed local write sends nothing and makes no saved claim. Same ID plus identical text/target/lane reuses the existing local entry; changed bytes conflict. Save a before-send note before socket write. A possible send with no saved reply stays unknown and is not automatically repeated. Stock command IDs are not native durable deduplication.

### Fresh-STATE hook

- **Trigger/layer.** Before each model-directed pi-stack message to the stream. LAYER 3 reads current files at the live message boundary; files/CI cannot run that step themselves.
- **Input/output.** Validate exact AGENTS/STATE bytes and source preservation, then render the complete stream-message text in §4 with their hashes. Once per pi-stack message satisfies Z25.
- **Code/stock command.** `engine/prime.py::send_stream_message`, `engine/state.py::check_state`, `engine/prompts.py::render`, and `prompt_and_wait.message`.
- **Failure/repeat.** Missing/malformed files prevent sending. Rebuild an unsent message after a relevant change. Do not resend a possibly delivered message merely to refresh it. Worker messages do not pass through this hook.

### Save-Prime-reply hook

- **Trigger/layer.** A connected client receives a correlated result or queries messages after an event. LAYER 3 captures a live result that files/CI cannot await.
- **Input/output.** Save actual success/error/data, sent-text hash, durable session and relevant queried messages in Log. A finished run does not close requested work. Save a worker's returned summary in the stream, never in worker STATE.
- **Code/stock commands.** `engine/prime.py::save_reply`, `engine/state.py::append_log`; `prompt_and_wait`, `get_messages`, `get_connection_state`, optionally `attach`.
- **Failure/repeat.** Report an unsaved reply if writing fails. Identical repeated results add no duplicate entry; conflicting bytes fail. A native failure leaves affected work waiting and suppresses automatic wake/compaction, without classifying or repairing the environment. A missing reply is unknown, not success or permission to repeat external work. No outcome-recovery service is added.

### Stall-wake hook

- **Trigger/layer.** Each existing tick, including event-free idle work. LAYER 3 supplies a clock unavailable to files/CI.
- **Input/output.** Read Goals/Rules, coordinator and worker assignments, prior commands, `get_state`, `get_connection_state`, `get_queue`. Wake eligible finite current work once. Preserve human waits, pauses, unread newer input and unknown sends. A healthy worker blocks dependent work, not independently authorized work. Run the compaction check before a wake.
- **Code/stock command.** `engine/tick.py::wake_prime_if_needed` and `engine/prime.py::send_stream_message`, using the stock queries and `prompt_and_wait`.
- **Failure/repeat.** Failed/ambiguous observations produce no wake. Under the stream lock recheck current session and Goals/Rules. Coalesce by durable session, objective-text hash and last observed leaf recorded with the wake. A later completed run permits reconsideration. A leaf is not proof of success.

### Reject-stale-command and stop hook

- **Trigger/layer.** Before a pi-stack automatic message, compaction step or computed close; also on an explicit operator stop. LAYER 3 controls a live send or abort that files/CI cannot perform.
- **Input/output.** Compare the prepared target and Goals/Rules with current bytes under the stream lock. Relevant changes, pauses, unread input or unresolved prior sends refuse a prepared automatic product message. Human delivery and the state-only compaction save are not product continuations. The save preserves unread messages without granting permission to act on them. An explicit stop still supersedes DCR. Log-only rotation does not invalidate unrelated work.
- **Code/stock commands.** `engine/prime.py::check_current_command`, `engine/state.py::check_current_text`; explicit stops use `engine/prime.py::stop_session` and stock `abort{activeSessionId}`. `abort_and_send_queued` retains its separate meaning.
- **Best-effort stop.** Save the actual stop and pause the affected current work when storage permits. Send abort promptly even if saving fails. Record the actual native reply and subsequent observed activity; report unknown on timeout. Never report guaranteed tool termination or rollback. A worker stop affects its assignment; a stream stop prevents further automatic stream work.
- **Failure/repeat.** Missing current state blocks a new automatic message, not an operator's abort. Rebuild only unsent commands. Never bypass a refused or uncertain send by inventing another ID. Z25 requires no per-tool stop check.

### Compaction hook

This is the only compaction controller. Percentage-triggered and explicit DCR requests share it. LAYER 3 owns the live sequence because files/CI cannot coordinate a save turn and native compaction.

**Configuration and percentage.** Before stream session creation, write `compaction.enabled=false` and the explicitly supplied `compaction.thresholdPercent` to its owned project settings. In this owned controller setup, also set stock `compaction.agentCallable=false` so the model cannot schedule a competing `compact.run`; public direct `compact` and session usage queries remain the chosen path. This does not change other sessions or establish a global setting. No percentage is selected here. Do not use `set_auto_compaction` as a live-core switch. Stock `compaction_start` does not pause the summarizer; `compaction_end` is an after signal, not permission to skip readback. [43][compaction-evidence]

Use `get_connection_state.contextUsage.percent`, with `tokens` and `contextWindow`, or the same `contextUsage` from `get_session_stats`. These are Prime's estimated session percentage, `100 * tokens / contextWindow`, not an invented token counter. `compact.status` exposes the corresponding native usage inside the agent; pi-stack uses the public session query so no model turn is needed just to obtain it. Stock source is `pa-daemon/src/worker/summary.rs:84-139`, `session_stats.rs::store_context_usage`, and `pa-core/src/session_engine/turn_boundary.rs:212-260` at the pinned revision.

**When it runs.** `engine/prime.py::check_compaction` runs before ordinary stream sends, after each captured stream run result and on every existing tick. A finite valid percentage strictly above the configured percentage requests this same DCR sequence. A busy stream is marked due in Log and reconsidered on result/tick; it is not aborted for maintenance. Missing percentage is reported as unknown, never zero or an automatic compact. A verified just-compacted session can receive its intended resume even while new usage is unknown. Internal dump/resume messages do not recursively start another compaction check.

**Sequence and exact commands.** `engine/prime.py::run_compaction` performs the following steps:

1. Under the existing stream lock, find any pending DCR command in Log/history, recheck session/current instructions and record this request once. Unknown prior results prevent another compact. Save new human text arriving during the sequence locally; hold its native send. An operator stop still sends abort.
2. Wait for observed stream idle. Send the save-STATE text through the normal stream sender and await its checked update and native result. This turn may synchronize current work but does not start product work.
3. On a retained connection call `acquire_session_input_pause{activeSessionId,leaseKey}`. Save the returned `pauseId`. Requery `get_state`, `get_connection_state`, `get_queue`. Active model/tool/bash/compaction, queued native input or known work mutating the stream causes deferral and pause release. Independent clean workers in separate worktrees do not share this stream session.
4. Recheck the target and current files, using the fresh Goals/Rules produced by this request's checked save rather than its own older prepared hash. A stop or unrelated instruction change still invalidates the prepared action. Capture the existing on-branch compaction IDs. Call direct `compact{activeSessionId,customInstructions}` with the full §4 text. Never send `/compact` into a paused queue or schedule `compact.run` as a second path.
5. Await the correlated compact result. A received `compaction_end` prompts inspection; failure/cancel/skip is not success. Query `get_session_tree` and require one new matching compaction entry on the current branch. Read its actual ID/type/summary in the exact owned native transcript. Missing, ambiguous or in-memory-only output is not verified persistence.
6. Append the compact reply/readback to Log. Reread current Goals/Rules and saved input. Newer saved human input takes precedence over the automatic resume. Otherwise choose the resume body only if current work is still eligible.
7. Record and write that next `prompt_and_wait` command while paused, using `streamingBehavior:"followUp"`. Do not await its model result yet. Send `release_session_input_pause{activeSessionId,pauseId}` on the same connection, then await the pending message result. Release on every locally known exit, including when no continuation is eligible. Waiting for the resumed model before releasing pickup would deadlock.

**Failure and repeat.** Failed/unknown save, compact or readback yields no automatic resume and no blind second compact. Report the actual result without adding recovery. The native pause ends on disconnect. It blocks queued pickup, not another client's direct commands. Cooperative idle checks are not an atomic native reservation. [42 §3][stock-hooks]

With automatic compaction disabled and no separately scheduled native compact, overflow recovery does not compact: the turn returns stock overflow failure. pi-stack never schedules `compact.run`. Long runs can cross the percentage before a tick/result boundary; the setting is not a hard ceiling. These are implementation facts, not new questions. [43][compaction-evidence]

### Checked-state-update and computed-close hook

- **Trigger/layer.** The stream proposes Goals/Rules/findings changes or completes requested work. LAYER 2 computes source/target/test checks; LAYER 3 rechecks and publishes the live file update. Context cannot execute those checks, and CI cannot serialize that write.
- **Input/output.** Original/later source entries, expected STATE hash and proposed changes. A close also names the actual target revision/diff, authorized check argv/cwd and exact report bytes/hash. Keep incomplete work open; save accepted findings in Log/history.
- **Code/stock integration.** `engine/state.py::{update_state,close_work}` and `pi-streams/checks/state.py::{check_state,run_check,check_close}`, exposed by `engine/cli.py`. Invoke through existing stock tools or directly through pi-stack's CLI; no native ask-close API is claimed.
- **Computed checks.** Every captured human message remains under Goals or has a linked complete answer, explicit cancellation or informational explanation. Preserve originals, prior Log bytes and unrelated Rules. Check target/report identity, execute the named safe local check and retain actual argv/cwd/exit/output. Do not accept a claimed green run or rerun an uncertain job-submission command as a harmless test.
- **Failure/repeat.** Run checks outside the short file lock, then compare current text/target before publishing. Missing/stale/failed/unknown output leaves work open. Duplicate identical closes reuse the saved result. Review text is optional recorded judgement. This hook neither creates reviewers nor requires a fresh-session review; review guidance is solely in AGENTS.md under Z25.

### Rotate-history-and-stage hook

- **Trigger/layer.** Every checked write and tick. LAYER 3 performs file movement/publication, which static context/CI cannot; LAYER 2 verifies preservation.
- **Input/output/code.** `engine/state.py::rotate_log` writes exact overflow/retired-rule entries before publishing at most 30 Log entries. Existing `engine/project.py::commit_repo` stages only exact authorized paths. Goals and current Rules never expire by count.
- **Failure/repeat.** Unequal existing history bytes fail instead of overwriting. A partial history-first publication can leave an identical extra copy, never prune unavailable bytes. Refuse unrelated staged paths. Retention grants no remote-publication, cleanup or push authority.

Keep final send checks, before-send Log append, fresh file read/render and socket write inside one short stream lock. An already-locked caller uses the same updater without another flock. Release before awaiting replies, tests or inference. The transport must multiplex pause-release commands while a prompt awaits pickup. Writes use temp files, file/directory sync, atomic replacement and readback. A post-replace sync error is unknown, not guaranteed rollback. Caller cancellation propagates; no default deadline or resource cap is introduced.

**Worker dispatch is not a stream hook.** `engine/threads.py::spawn_prime_worker` creates an independent stock session in its assigned product worktree, records the assignment in the stream, and calls `engine/prime.py::send_worker` with only the handover and poteto kickoff. No stream AGENTS/STATE files or message wrapper are copied or supplied. Native product instructions remain applicable. Worker results return to the stream's Log for its own review. Optional reviewer sessions use this same clean-session path, only when chosen by the stream.

## 4 Prompts

`engine/prompts.py::render` owns the complete texts below. Encode `_json` values as JSON, validate IDs/paths, render once with one final LF, and never reparse substituted data as a template or slash command. Native base/tool prompts remain stock. Only stream messages use the stream wrapper.

### Stream AGENTS.md role text

The installer writes this only in the stream. Review guidance is here, not in a hook.

```text
You coordinate this stream. Delegate product changes to clean poteto workers in separate assigned worktrees. Workers are not streams and receive no state files.
Use STATE.md Goals for the North Star, finite current objective and work still requested. Rules contains only rulings in force. Log/history retain original messages and findings. A new priority or plan does not cancel another request.
Read the whole original request before interpreting or closing its work. Keep the original intent separate from your plan. Use the named existing path when required and record the actual target, invocation, result and uncertainty.
Review every reported summary adversarially against the original intent. Check unanswered parts, protected behavior, wrong metrics and unsupported claims. Spawn a clean reviewer session only when you judge one is needed. There is no mandatory fresh-session check. Record your findings in Log/history.
Use the checked pi-stack commands for current-state changes and computed closing checks. A saved message, finished run, green status or updated plan is not completion. Report each requested outcome, including incomplete and waiting work.
Fresh AGENTS.md and STATE.md arrive once per pi-stack message. Preserve genuine waits and stops. Do not invent approval gates, resource caps or additional current-work files.
pi-stack owns this stream's compaction. Do not schedule compact.run or independently start compaction. Save current work when its save-STATE message arrives and let pi-stack compact and resume.
Login/auth failures, outages and recovery are permanently outside this design. Report observed errors or unknown results without login, environment repair, provider/model switching, session deletion or uncertain job replay.
```

### Stream-message text

Use before every model-directed pi-stack message to the stream, including wake, save-STATE and resume. Do not use for worker/reviewer input or native command-only operations.

```text
Current files for stream {stream_id_json}, Prime session {session_id_json}, command {command_id_json}.
AGENTS.md at {agents_path_json}, SHA-256 {agents_sha256}, exact text as JSON follows.
{agents_text_json}
STATE.md at {state_path_json}, SHA-256 {state_sha256}, exact text as JSON follows.
{state_text_json}
Original entry references as JSON follow.
{original_entries_json}
Message body as JSON follows.
{body_text_json}
Use current Goals and Rules. Quoted messages and old summaries do not replace them. Keep the original request separate from its interpretation. Saving or delivering this message is not application or completion. These are the only stream-state files supplied for this message.
```

### Saved-message text

Return only after original and Goals item pass local readback. It is not a model prompt.

```text
{stream_id}:: Saved message {command_id} before sending to Prime. Sending status is {sending_status}. This save does not establish native delivery, application or completion.
```

Status is exactly `not sent`, `sent, waiting for result`, `Prime replied` or `unknown after connection loss`. The actual native success/error remains separate.

### Stall-wake text

Send as a wrapped stream body only after eligibility, stale-message and percentage checks.

```text
The tick found eligible unfinished current work.
Use the supplied AGENTS.md and STATE.md. Advance only finite work allowed by Goals and Rules. Independent work need not wait for an unrelated worker. Preserve actual human waits and stops.
If no eligible action remains, record the real wait or completed current objective and report findings by original request. Do not invent a task from the North Star alone, an approval gate or a resource cap.
Review reported summaries against original intent as AGENTS.md directs. Use computed closing checks before done status. Another turn or plan update is not completion.
```

### Save-STATE text

The single compaction hook uses this before both percentage-triggered and explicit DCR.

```text
Prepare this stream session for compaction.
Read the supplied AGENTS.md and STATE.md. Through the checked pi-stack update, preserve the current objective, every unanswered original message, current Rules, worker/job identities, real waits and needed proof references.
Append one Log note with completed work, reported findings and unresolved uncertainty. Do not remove unfinished work to shorten context or retire a rule without its source. Do not prune Log yourself.
Do not start product or external work, repair the environment or write a resume prompt. Finish after the checked save. pi-stack will check native activity, compact, read back the result and choose the next message.
```

### Compaction instructions

Pass verbatim as direct `compact.customInstructions` after the save turn and idle checks.

```text
Preserve original requests separately from plans and interpretations. Preserve later instructions, unfinished work, active prohibitions, human waits, worker and external-job identities, uncertainty and exact saved proof references. Keep native tool-call and result relationships complete.
STATE.md remains current Goals, Rules and Log. A summary cannot cancel or complete its work. Do not infer success from missing error text or add rules, memory, skills, environment changes or budgets. Return the native summary. pi-stack controls the next message.
```

### Resume text

Use once after compact reply and disk readback, unless newer saved human input takes precedence or work is no longer eligible.

```text
Compaction saved native entry {compaction_entry_id_json} in Prime session {session_id_json}.
Use the supplied current AGENTS.md and STATE.md rather than only the summary. Account for newer instructions before choosing work. Read exact original or proof entries when needed.
Continue only finite work still authorized by Goals and Rules. Do not repeat workers or external jobs to replace unknown results. Preserve unrelated waits. Review returned summaries against original intent before proposing completion.
```

### Worker context handover

Send with the kickoff to a clean session, not through the stream wrapper. Include relevant original wording and constraints as data, not live stream-state files.

```text
Context handover for clean worker session {session_id_json}.
Assigned product worktree {worktree_json}. Requested outcome {work_json}.
Original request and applicable constraints as JSON follow.
{source_and_constraints_json}
Relevant findings and existing job identities as JSON follow.
{findings_json}
Compare the assignment with that original intent. Report a mismatch rather than silently broadening or narrowing it. No stream state files are supplied or assigned to this worker.
```

### Worker kickoff

Append to the handover in the same initial worker message. The installed poteto path is a process skill, not a worker state file.

```text
Work in poteto. Read the installed process entry at {poteto_path_json} and follow the applicable task method. Do not claim a Pi-specific slash command executed on Prime.
Work only in {worktree_json} on the handed-over assignment. Keep progress in session messages, not worker planning or state files. Do not create a worker STATE.md, stream role file or other stream-state copy. Keep applicable product instructions.
Return a concise summary with the exact target, actual invocation, observed result, retained proof references, unanswered outcomes and existing external-job identities. Report uncertainty honestly. Do not repair login or environment failures, switch provider/model or repeat uncertain jobs.
```

### Optional reviewer text

Use only after the stream decides a separate reviewer is useful. Its clean handover contains relevant original text, constraints, target and reported results. No hook selects or requires it.

```text
Review the handed-over result adversarially against the original intent.
Check the whole requested outcome, actual target and invocation, protected behavior, wrong metrics, unsupported claims and valid alternatives. Do not grade only agreement with the worker's plan.
Do not edit product files or create state files. Return accept, rework or unknown with exact source/result references and unanswered outcomes. Missing proof is unknown, not acceptance. The stream remains responsible for its final judgement.
```

### Stale-command text

Return to the caller when refusing an unsent automatic command.

```text
{stream_id}:: Did not send {command_name}. Its target or current Goals/Rules no longer permits the prepared message, or current input/work is waiting. Read current STATE.md before preparing another automatic message. Inspect a possibly sent command instead of resending under a new id.
```

### Close-refusal text

Return without removing requested work when a computed closing check fails.

```text
{stream_id}:: Did not mark work from {original_entry} done. Computed check details as JSON follow.
{failure_json}
The work remains requested. Correct or report the source, target, actual check or report problem. Finishing this command is not completion of the request.
```

No failure-repair, login or recovery prompt is added. Best-effort stop reporting uses actual native response fields, not a claim that a tool certainly stopped.

## 5 Artifact storage

Only the stream has the Z15 files. Workers and optional reviewers have no state files and receive no stream AGENTS/STATE pair. They use ordinary product worktrees and native session storage. The stream retains their handed-over assignments and returned findings.

| Path | Schema/writer | Reader and retention |
|---|---|---|
| `<stream>/AGENTS.md` | Exact §4 stream role text. Installer/authorized template update writes. | Supplied to the stream once per pi-stack message. No periodic additions or rotation. |
| `<stream>/STATE.md` | UTF-8/LF Markdown with exactly Goals, Rules, Log below. Checked updater writes. | Stream/human, sender, tick and checker. Rewrite Goals/Rules; only Log caps at 30. |
| `<stream>/history/<UTC ts>-<slug>.md` | One exact immutable entry per file. Updater writes overflow, retired Rules, original/proof/review detail. | Exact named reads on demand. No automatic deletion. Retired Rules use `<UTC ts>-rule-retired-<slug>.md`. |
| `<stream>/.prime/agent/settings.json` | Existing stock project settings. Installer writes `compaction.enabled=false`, `agentCallable=false` and supplied `thresholdPercent` before constructing the owned stream session. | Stock construction and pi-stack percentage check. Not model context or another task store. No live supervisor-toggle substitute. |
| Existing product/native/index files | Product tests/reports remain in assigned worktrees. Prime alone writes native session files. Existing pi-stack registry/tick/locks retain their purposes. | Needed proof may be retained as exact text history entries. No worker state directory, failure-marker tree or runtime task database. |

### STATE and entry schemas

```markdown
## Goals
### North Star
Text: <JSON string>
Original entry: <JSON basename or null for unverified migrated text>

### Current objective
Text: <JSON string or null>
Status: <active|waiting|paused|complete|unset>

- [ ] <one-line summary of a whole human message>
  Original entry: <JSON basename>
  Required: <JSON string or null while unread>
  Workers: <JSON array of {session,worktree,work}>
  Next: <JSON string or null>
  Waiting for: <JSON string or null>

## Rules
- <short current ruling>
  Original entry: <JSON basename>
  Applies to: <JSON work or stream description>

## Log
### <UTC timestamp> <one-line subject>
File: <JSON eventual history basename>
Prime session: <JSON durable session ID or null>
Prime command: <JSON command UUID or null>
Prime entry: <JSON observed native entry ID or null>
<entry body with fenced JSON>
```

The North Star has no completion flag. Every captured whole message remains under Goals until answered, explicitly cancelled or explained as informational in a linked entry. Required starts null. A missing native result stays waiting, not ready for automatic replay. Planning does not close work. Only applicable human sources change rulings; model-supplied sender fields cannot grant authority.

Entry bodies use these exact fields in existing Log/history, not new named record types:

| Entry | Required JSON fields |
|---|---|
| Original message | `text,sha256,sender,received_at,send_as`. Exact original UTF-8 text, trusted sender or null, RFC 3339 UTC time, `steer` or `followUp`. |
| Operator stop | `text:null,command:{type:"abort",session},sender,received_at`. Record the actual control, not invented speech. |
| Before-send command | `command,body,original_entries,goals_rules_sha256,result`. Result is `unknown until reply saved`. Body is unwrapped text. Do not include a self-referential hash of the final wrapper. |
| Native reply | `command,sent_text_sha256,success,error,data,messages`. Retain actual relevant fields, not greetings, ownership data or credentials. |
| Checked answer | `original_entries,later_instruction_entries,target,invocation,result,findings,proof_entries,review`. Target identifies actual repo/worktree and commit/diff or job. Invocation is actual argv/cwd. Proof refs are `{entry,sha256,representation}` with full/excerpt; excerpts add original/range. Review is null or a saved stream/optional-reviewer note, never a required fresh-session result. |
| Text proof, handover or review | `original_entries,media_type,text,sha256`. Retain exact needed text and name excerpt ranges honestly. No binary/credential import. |
| DCR request/result | `command,trigger,percent,threshold_percent,before_entry,dump_entry,compaction_entry,next_command,result,error`. Trigger is percentage or explicit. Unknown native refs are null. These are ordinary Log command notes, not another DCR store. |

Names use `YYYYMMDDTHHMMSS.ffffffZ-<lowercase-ascii-slug>.md`. Slugs include command UUID and plain purpose. Reuse the first timestamp/name for an identical command/purpose; unequal existing bytes fail. Different messages with equal text remain distinct. Entry references name the eventual history basename while hot in Log. `state read-entry` resolves Log or history without another index file. Parse headings only outside fences; reject traversal/symlink escapes. Hash exact original UTF-8 bytes without newline normalization. JSON uses sorted keys, finite numbers and exact decoded strings, with one final LF.

Proposed CLI is `state check/read-entry/update/close <stream>` with `--expect <SHA-256>` for writes. Update stdin is `{goals,rules,entry}`; unchanged sections are null and entry is `{subject,body,original_entries}`. Close adds `{target,check:{argv,cwd},report:{path,sha256},proof_entries,review}`. Review may be null. Results are `{success,reason,state_sha256,history_files}` with nonzero failure exits. Caller identity comes from the registered channel, not JSON assertions.

History is synced before STATE pruning/replacement. Retention is not publication permission. Stage only exact authorized AGENTS/STATE/history and selected report paths; never native sessions, arbitrary task data, credentials or unrelated staged work.

## 6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure)

### Intake to close

1. pi-stack saves the original human text and unread Goals item before sending. It includes fresh stream AGENTS/STATE once in that message.
2. The stream interprets the whole request and records needed outcomes/rulings. It hands product work to a clean poteto worker with context and kickoff only. The worker receives no state files.
3. pi-stack saves the connected result. The stream reviews the summary adversarially against original intent, records findings and requests a separate reviewer only when useful.
4. The computed close executes/checks actual source, target and test/report bindings. It does not require a fresh reviewer. Only fully accounted-for work leaves Goals; findings and originals remain in Log/history.

### A stall and compaction

Tick wakes eligible idle work without another event, but checks the percentage first. Above the configured percentage, the one compaction hook saves current STATE, waits for observed idle, pauses pickup, compacts directly, verifies the disk entry and sends current input or one resume. A busy stream is reconsidered later without a maintenance abort. New human input is saved locally during DCR and takes precedence over an old automatic resume. An explicit stop calls stock abort best-effort and records the actual response.

### A failure

Failed local save sends nothing. A received native error is saved and reported without closing work. Missing output is unknown and never automatically replayed. Login/outage/recovery behavior is permanently excluded below. With native automatic compaction disabled, an overflow can fail the turn instead of compacting it.

## 7 Risks and notes

- `compaction_start` is notification-only; reacting to it cannot insert save STATE before stock summarization. Hence the required pre-construction disable and pi-stack-owned sequence. The supervisor toggle does not update an existing core. [43][compaction-evidence]
- Percentage checks occur at the specified send/result/tick boundaries. A long run can overflow before it yields. Missing context metadata and post-compaction null usage are not treated as zero. No absolute token threshold or percentage default is introduced.
- Stock automatic overflow compaction is disabled. Owned stream settings also disable agent-callable `compact.run`, and pi-stack starts a new unscheduled session. An unrelated direct client's manual compact remains its own action; report an unexpected native compact instead of pretending pi-stack's ordered sequence ran.
- Local save/native dispatch are separate writes. Native result persistence is not repaired by a connected client. Report uncertainty without building recovery machinery. Native pause/status checks are cooperative and may race unrelated direct clients. [42 §3][stock-hooks]
- Per-message freshness, selected input capture and best-effort abort are the accepted Z25 contract. Terminal input is intentionally outside capture; attachment rejection is deliberate. There is no per-tool stop check to implement or qualify.
- Stream self-review and optional reviewers can share a wrong premise. Computed checks do not prove semantic intent. Keep actual source, invocation and proof. Review is guidance, not a new mandatory gate.
- Original text in the last 30 Log entries can make STATE large. Neither current work nor original messages are silently truncated. History and proof can grow. No additional cap or cleanup policy is selected.
- Workers receive a handover snapshot, not a live state feed. Subsequent task changes use a new explicit handover/message. Worker product instructions and native process context remain applicable. The installer must not put workers in the stream directory or copy its state files.
- Stock native continuation/refinement can act independently. The PoC starts a new stream with no native goal or scheduled compact and verifies the observed save/compact/resume ordering. It does not silently rewrite unrelated native policy or another installation.
- Source/document checks are not successful inference, compaction or deployment evidence. The end-to-end gate below must observe those operations on stock Prime.

### Not handled (permanently out of scope)

| Case | What happens today; not intended to be solved |
|---|---|
| Login/auth failure | Stock can return an error without an assistant row. Report a received error or unknown result. User login/repair is their own step; this design will not perform it. |
| Quota or provider outage | Stock settings govern native waiting/errors. Stop and report the blocker. No probe, fallback provider, automatic reset/release or outage repair is planned. |
| Resource/storage failure after a native send | Saving output may fail after effects. Report unsaved/unknown and stop new automatic work. Cleanup and reconstruction are not planned. Pre-send local failure still refuses the send. |
| Host crash, lost effects or external-job rollback | Inspect surviving work manually. Exactly-once replay, rollback and automated recovery are not planned. |
| Parent replacement, moving running children or F-DCR | Stock replacement may close children. Do not automatically replace/delete the original or duplicate work. Transfer and recovery are not planned; this design uses clean independent workers. |

All seven former questions are answered by Z25. There are zero open questions in this revision. The facts above do not reopen them.

## 8 Implementation plan

throughput checkpoint: n/a, read-only investigation.

Z26 makes this the direct PoC plan for `feat/merged-poc`. The units below are pi-stack commits only, in order, each with focused tests. Rebase on the actual track-1/Prime CLI landing; reuse equivalent code. Paths marked add are proposed files. Existing code paths need failing-before-fix behavior tests; absent APIs/formats use labelled new-functionality tests. No implementation or runtime operation is performed by this docs-only revision.

### Ordered commits

| Order and commit | Exact files and functions | Tests in the unit |
|---|---|---|
| 1. `state: implement the Z15 stream writer` | Add `pi-streams/engine/state.py` with `parse_state`, `check_state`, `save_message`, `append_log`, `read_entry`, `update_state`, `rotate_log`; add `pi-streams/templates/prime/{AGENTS.md,STATE.md}`. Extend `engine/project.py::{create_stream,upgrade_stream,stream_lock}` for these templates and linked-worktree-safe locks. | Add `tests/test_prime_state.py`. Exact Unicode/fenced-body round-trip, source preservation, partial whole-message completion, retired rule, 31 unrelated entries, duplicate command, stale write, concurrent writers and history-before-prune failures. Old creation must fail the missing-current-work preservation assertion. |
| 2. `prime: expose public stock transport and owned sessions` | Reuse the gated CLI logic in one `engine/prime.py::PrimeClient` with `connect`, `write`, `wait`, `query`, `close`; make reused/added `bin/prime_cli.py` its thin CLI entry. Add `resolve_session`, `validate_stream_settings`, `create_stream_session`, `save_reply`, `start_owned_daemon`, `stop_owned_daemon` in that engine module. Extend `engine/project.py` project parsing with `backend`, `prime_binary`, `prime_agent_dir`, `prime_sessions_dir`, `prime_socket`, `poteto_path` alongside existing coordinator model/thinking. No task facts in transport. | Add `tests/test_prime_transport.py` and `stub_prime.py`. Protocol/schema errors, interleaved events, routing versus durable ID, actual preflight error without assistant, possible send with no resend, and multiplexed pause release while a prompt is pending. Never query another socket. |
| 3. `streams: save and refresh messages, wake and stop` | `engine/prime.py::{send_stream_message,check_current_command,stop_session}`; `engine/tick.py::wake_prime_if_needed`; add `engine/prompts.py::render`. Extend `engine/cli.py::_parser/main` with `state` commands and the `poc` subcommands specified below. Use existing tick/registry, not another task clock. | Add `tests/test_prime_messages.py`, `test_prime_tick.py`, `test_prime_prompts.py`. Native fixture sees original/Goals before first socket write, save failure yields zero sends, each stream message carries current files, stale message rejected, Log-only changes tolerated, event-free wake once, independent work eligible, explicit abort success/error/timeout reported without a termination guarantee. |
| 4. `workers: use clean poteto handover and kickoff` | `engine/threads.py::spawn_prime_worker` and `render_prime_handover`; `engine/prime.py::{create_worker_session,send_worker}`. Create in the assigned product worktree, record full ID/assignment in the stream before kickoff. Render §4 worker/reviewer text, with optional reviewer choice solely in stream AGENTS. | Add `tests/test_prime_workers.py`. Capture handover/kickoff and poteto path; assert no stream wrapper, AGENTS/STATE copy or worker state file. Preserve product instructions. Worker summary returns to stream Log. Both stream self-review and stream-chosen reviewer paths work; computed close does not force a reviewer. |
| 5. `compaction: own percentage, save, compact and resume` | `engine/prime.py::{check_compaction,run_compaction,read_compaction_entry}`; call check from sender, reply path and tick. Read stock session contextUsage and owned `thresholdPercent`. Add `engine/project.py::write_prime_settings`; reuse `engine/prime.py::validate_stream_settings` before construction, with no live toggle. Implement one direct compact path for percentage and explicit DCR. | Add `tests/test_prime_compaction.py`. Below/equal/above percentage, missing/null usage, busy deferral, fresh settings before create, no stock automatic/overflow compact, disabled agent-callable scheduling with public usage still available, no scheduled competing compact, save before direct compact even with unread source, refreshed hash after that save, stop superseding DCR, pause release without deadlock, new human input before resume, missing disk entry, duplicate request and no resume on unknown. Source/fixture tests are not native-runtime proof. |
| 6. `checks: close only computed results and stage owned paths` | Add `pi-streams/checks/state.py::{check_state,run_check,check_close}`; `engine/state.py::close_work`; `engine/cli.py` dispatch; narrow existing `engine/project.py::commit_repo`. Same checker from supported repo verification. | Add `tests/test_prime_close.py`. Wrong original/target/report, nonexecuted claimed test, changed instructions during check, actual argv/cwd/exit, missing proof and valid alternative. Review null is valid; no mandatory fresh-session hook. Old broad staging captures scratch before the fix; candidate refuses foreign staged work. |
| 7. `install: isolate a stock Prime PoC on an external machine` | Add early `--merged-poc` dispatch in `install.sh`, before normal Pi overlay/package/systemd code. Add `engine/install_prime.py::{main,preflight,install_prime,install_poteto,write_wrappers,prepare_project}`; `poc init` reuses `engine/project.py::write_prime_settings`. Add the exact options/layout below and document them in `README.md`. Leave ordinary install behavior unchanged. | Add `tests/test_prime_install.py` and `scripts/check-prime-install.sh`. Temporary-prefix install, pinned binary/runtime sidecar, rejection of a missing or mismatched sidecar, owned kernel venv, settings before session create, idempotence, foreign-path refusal, no auth/global/Pi/service writes, explicit branch source and no model/percentage defaults. Full stock build/version is a later real test, not a stub assertion. |
| 8. `poc: prove intake through compaction to checked close` | Add `engine/poc.py::{init,doctor,verify}`; wire `poc init/doctor/verify` in `engine/cli.py`. Add `scripts/check-merged-poc.py` as the rerunnable E2E driver using those functions; add `tests/test_merged_poc.py`. Extend `scripts/check-readme-commands.py` for the new documented commands. | Offline driver negatives for every asserted stage, then the real one-stream stock check below. Emit PASS only with actual percentage-triggered save/compact/readback/resume and checked close. Missing login/quota/outage is BLOCKED, not a reason to repair or switch provider. Stop only the owned daemon afterward; retain report/session/task bytes. |

All `tests/` paths in the table are under `pi-streams/tests/`; all `engine/` paths are under `pi-streams/engine/`. The native daemon launch is `<prefix>/bin/prime-agent --mode daemon --daemon-socket <prefix>/prime/poc-<stream>.sock`, through the installed wrapper so its complete owned agent/session/runtime/venv/cache environment applies. Use `subprocess.Popen` and an owned shutdown/wait path inside the PoC runner, never a global daemon/service operation. The checked public command shapes are specified in §3. Prime's `crates/pa-cli/Cargo.toml` names package `pa-cli` and binary `prime-agent` at the pinned stock revision.

### External-machine installer contract

Proposed command options are `--merged-poc --prefix <absolute-root> --project <root>/project --coordinator-model <provider/id> --coordinator-thinking <level> --compaction-percent <number>`. Require explicit model/thinking/percentage. Validate a finite percentage greater than zero and at most 100, without choosing a value. This mode does not run the existing installer's unrelated Pi setup or accept its defaults. It supports a fresh user-owned Linux prefix; preflight requires Git, Python 3.11 or newer, Cargo/Rust, a C build toolchain and uv. Missing prerequisites are reported without sudo or system package changes.

The installer sets up the following owned paths:

- `<prefix>/src/prime-agent` is an unchanged clone of `https://github.com/PrimeIntellect-ai/prime-agent.git` at `8aac8692456c00c01d4e53e60e6d3347a3506559`. Build with `CARGO_HOME=<prefix>/build/cargo CARGO_TARGET_DIR=<prefix>/build/prime cargo build --locked --release -p pa-cli --bin prime-agent`. Install to `<prefix>/libexec/prime-agent` and copy the unchanged `prime-agent-runtime/` sidecar from the same revision beside it. Verify version 0.10.1, runtime `pyproject.toml`, `src/rlm/__init__.py` and `src/rlm/repl.py`; record binary and runtime hashes. The stock lookup in `pa-core/src/kernel/bootstrap/venv/runtime_source.rs:8-57` requires that sidecar. A working `--version` alone is not a complete installation. No latest-channel installer or Prime patch.
- `<prefix>/bin/prime-agent` wraps that binary with `PRIME_AGENT_CODING_AGENT_DIR=<prefix>/prime/agent`, `PRIME_AGENT_SESSION_DIR=<prefix>/prime/agent/sessions`, `PRIME_AGENT_DAEMON_SOCKET=<prefix>/prime/daemon.sock`, `PI_PACKAGE_DIR=<prefix>/libexec` and `PRIME_AGENT_KERNEL_VENV=<prefix>/prime/kernel-venv`. The kernel-venv override is necessary because stock otherwise uses `~/.prime/agent/kernel-venv`, independently of its agent directory. Clear an inherited `PRIME_AGENT_KERNEL_PYTHON` inside this wrapper. Put `UV_CACHE_DIR` and `UV_PYTHON_INSTALL_DIR` under `<prefix>/cache`, and XDG cache/config/data roots under `<prefix>/xdg`. The user uses the wrapper for their own login. Installation does not open, copy or generate credentials.
- `<prefix>/bin/pi-streams` points explicitly to the selected `feat/merged-poc` checkout and its hooks. It does not update another checkout or silently return to main. `<prefix>/src/plugins` holds the existing pstack source fetched by the normal installer logic, confined to this prefix; record its actual revision and reuse it on rerun. The kickoff references its `pstack/skills/poteto-mode/SKILL.md` and related installed method files, not a worker role/state copy.
- `<prefix>/index` and `<prefix>/project` hold the owned existing pi-streams registries/project. `poc init` creates `<prefix>/project/streams/<stream>` with §4 AGENTS and §5 STATE/history. Before creating its native session in that stream directory, write `<stream>/.prime/agent/settings.json` with `compaction.enabled=false`, `compaction.agentCallable=false` and the supplied `thresholdPercent`. Read back the file first. An already-built session is not reconfigured by `set_auto_compaction`.
- `<prefix>/reports/install.json` records `pi_stack_revision,prime_source_revision,prime_binary_sha256,prime_runtime_sha256,prime_version,pstack_revision,root,project,model,thinking,threshold_percent,paths,checks`. `<prefix>/reports/<stream>-doctor.json` records `status,stream,checks`. The E2E report schema is below. All are outside source Git and contain no auth/ownership data. Installer creates no live model session or systemd timer. `poc verify` owns its tick loop and test daemon. Clean workers use their product worktree as cwd and receive no stream state or role files.

Do not touch global PATH links, shell profiles, `~/.pi`, `~/.prime`, existing sessions/sockets, pi-web, system services, unrelated projects, credentials, existing native source or another pi-stack checkout. Preserve unknown files and fail on conflicting owned-path content. No installer login, provider/model substitution, resource budgets or automatic user-data cleanup. Installer-managed runtime, settings and cache paths are confined to the prefix; product tools remain subject to their explicit worktree assignment.

The exact fresh-machine branch test commands below are future commands supplied by commits 7-8. They are not run in this docs task. The user sets `POC_MODEL`, `POC_THINKING` and `POC_PERCENT` explicitly; no values are implied.

```bash
set -eu
git clone --branch feat/merged-poc --single-branch https://github.com/alienczf/pi-stack.git pi-stack-merged-poc
cd pi-stack-merged-poc
export POC_ROOT="$HOME/pi-stack-merged-poc-test"
test -n "${POC_MODEL-}"
test -n "${POC_THINKING-}"
test -n "${POC_PERCENT-}"
./install.sh --merged-poc --prefix "$POC_ROOT" --project "$POC_ROOT/project" \
  --coordinator-model "$POC_MODEL" --coordinator-thinking "$POC_THINKING" \
  --compaction-percent "$POC_PERCENT"
"$POC_ROOT/bin/pi-streams" poc init --root "$POC_ROOT" --stream weekend-poc
"$POC_ROOT/bin/pi-streams" poc doctor --root "$POC_ROOT" --stream weekend-poc
```

The user now completes stock Prime login themselves using `"$POC_ROOT/bin/prime-agent"`. The installer, doctor and verifier do not perform login or copy another installation's credentials. After that user step:

```bash
"$POC_ROOT/bin/pi-streams" poc verify --root "$POC_ROOT" --stream weekend-poc
```

`poc init` creates the new owned stream/settings without a native model session and reports conflicts rather than adopting existing work. `poc doctor` verifies version, paths, templates, settings and the pinned command contract without reading auth files or making inference. `poc verify` validates those settings, then starts its daemon on `<prefix>/prime/poc-<stream>.sock` and creates the stream session. This test socket is separate from the user's login-wrapper socket. Refuse an existing test socket/session instead of replacing it; shut down only the test daemon the verifier started.

### End-to-end proof and acceptance

`scripts/check-merged-poc.py --root <prefix> --stream <id>` is the same verifier used by `poc verify`. One fresh stream on stock v0.10.1 must demonstrate the following observable sequence:

1. Save a fixture ask and unique marker to Log/Goals before the real native send. Capture the actual wrapped input with current AGENTS/STATE.
2. Run a finite fixture exchange whose completion is deliberately left open until after compaction. Record actual native percentage observations. The configured percentage must genuinely be crossed; do not change it, fake the percentage or force explicit DCR to pass the automatic-path check. If the chosen model/percentage cannot be crossed safely by the fixture, report INCONCLUSIVE.
3. Observe pi-stack's percentage predicate selecting the single compaction hook. The save-STATE turn must finish with checked Goals/Rules and a saved Log note before direct compact starts. Verify native automatic compaction and agent-callable scheduling were disabled for this owned stream at construction.
4. Observe direct compact, its correlated result and matching persisted compaction entry, then one current-input/resume message in the same durable stream session. Validate pause release and no duplicate resume. `compaction_start` notification alone cannot pass the pre-save assertion.
5. The stream answers the original fixture ask after resume, preserving its marker and actual target/result. It reviews that summary against original intent itself; a separate reviewer is optional. Execute a real local deterministic fixture check and close through `state close`.
6. Inspect actual STATE, history, test output, native entries and outgoing messages. The fixture ask is closed with its findings retained, no unresolved part lost, and the North Star still exists without a done flag. A second offline scenario rotates 31 unrelated entries and preserves an open request.

Write `<prefix>/reports/<stream>-poc.json` with `status`, stock/build/model identity, stream/session/command IDs, observed percentages, dump/compaction/resume entry IDs, check argv/cwd/exit, retained artifact hashes and stage findings. Status is PASS, FAIL, BLOCKED or INCONCLUSIVE. Redact connection ownership/auth data. Only PASS with the real ordered native observations establishes a working PoC; socket fixtures or source inspection do not. Shut down only the daemon the verifier started, wait for that process, and preserve test artifacts.

Run `python3 -m unittest discover -s pi-streams/tests`, `bash scripts/check-overlay.sh`, `bash scripts/check-prime-install.sh` and `python3 scripts/check-readme-commands.py` before the real PoC gate. Login/auth, outages and recovery remain permanently excluded even when a verification run is blocked. This revision changes documentation only; none of those implementation tests is claimed executed.

[a-hooks]: 31-design-a-detailed.md#3-hooks
[stock-hooks]: 42-design-b-prime-unchanged.md#3-hooks
[compaction-evidence]: 43-prime-compaction-hooks.md

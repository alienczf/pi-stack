Runtime: stock Prime, no Prime changes; merged candidate (Z23)

# Repo judgement and stock Prime hooks

**New concepts**

| plain name | one-line meaning | corpus failure it fixes | why no existing artifact or term can carry it |
|---|---|---|---|

None. Current requested work stays in Goals. Current rulings stay in Rules. Original messages, commands, results, proof and reviews are ordinary Log/history entries. Command IDs and session IDs keep their existing Prime meanings. Function names below describe operations, not additional task objects.

## 1 Overview

This candidate combines the repo work in [31](31-design-a-detailed.md) with the stock commands and limits in [42](42-design-b-prime-unchanged.md). It is not selected. Z17 remains in force. Z23 and G29 authorize this design exercise, not a deployment or new defaults. [Decisions, Z17 and Z23/G29](03-decisions.md)

For the operator, one checked STATE answers what remains requested and why a result counts. For the maintainer, pi-stack supplies small sending, file-writing and checking functions. Stock Prime supplies session execution and its existing automatic compaction hook. There is no additional task service, runtime task database or Prime patch.

The split is concrete. Code saves messages before sending, includes current files on each pi-stack send, wakes eligible idle work, rejects stale pi-stack commands and checks computable completion conditions. People and agents interpret the request, choose meaningful tests and review the result in the existing repo files. Native threshold compaction uses stock configuration and its existing loop-boundary checks. [31 §§2-3][a-components] [42 §§2-3][stock-components]

Two requested guarantees cannot be supplied in full by the documented stock interfaces. Fresh STATE before every internal provider request is not fresh STATE before every pi-stack message. Rejecting stale pi-stack commands is not rejecting every subsequent model tool. These are normal long-run cases, not login or rare-failure exclusions. This candidate implements the narrower sending checks and leaves those two stronger requirements visibly unmet. An instruction to reread is not a deterministic hook. [42 §3][stock-hooks]

Only AGENTS.md and STATE.md are automatically supplied by pi-stack for stream work. STATE has exactly Goals, Rules and Log, in that order. Goals keeps every unanswered message outside Log rotation. Only Log is capped at 30 entries. Existing native prompts, project discovery, tool output and skill loading remain stock. The candidate does not claim that Prime's entire provider context contains only these two files. [31 §5][a-storage] [42 §5][stock-storage]

### Source and implementation boundary

Stock means Prime v0.10.1 at source `8aac8692456c00c01d4e53e60e6d3347a3506559`. All proposed implementation paths are in pi-stack. Rust paths identify existing stock behavior, not files to edit. The externally usable operations are public commands. The available Rust callback fields are not a hook-registration API for a running daemon. There is no new in-process Prime extension point hidden behind these pi-stack hook names. [42 §§1,3][stock-overview] [31 §3][a-hooks]

[41](41-design-b-prime-detailed.md) is reference only for stronger native behavior. Its proposed receiving, result, per-request and tool integrations are not stock features. The new native commands and custom session data proposed in 31 are not imported. No runtime test or successful inference is claimed by this document. [31 §3][a-hooks] [41 §3][native-hooks] [42 §1][stock-overview]

## 2 Components and justification

Layer numbers use [02-principles.md](02-principles.md). Coverage means a proposed mechanism for the named path, not measured prevention of a whole failure class. F-numbers retain the definitions in [30, lines 105-124](30-research-designs.md#input-3-the-explicit-balance-after-zfs-remedies).

| Component | Layer and why a stronger layer cannot carry it | Corpus coverage and limit |
|---|---|---|
| Requested work and rulings | LAYER 1. Goals/Rules are the current bytes the agent reads. No stronger context layer exists. | F2, F3, F9, F10, F12. Replanning does not remove another request. Natural-language interpretation remains fallible. |
| Original messages, proof and reviews | LAYER 1. Log/history retain exact repo bytes independently of conversation. No stronger context layer exists. | F5, F6, F8, F10. A source hash alone proves neither authority nor retention. |
| Computed file and closing checks | LAYER 2. Context can name a source, target and command but cannot execute their integrity/behavior checks. | F2, F4, F5, F10, F11. The code can run the wrong chosen test correctly. |
| Save incoming messages and connected replies | LAYER 3. Files and CI cannot order a live socket send or capture its response. | F2, F8 and part of F7. Covers participating text callers only. Unknown native results remain unknown. |
| Include current files and reject stale commands | LAYER 3. Context and CI cannot reread just before a live pi-stack command. | F3, F6, F10, F12. No every-request refresh or all-tool veto is claimed. |
| Tick wake | LAYER 3. Files and CI cannot wake an idle session. Reuse the existing tick. | F1, F9, F12. A wake is reconsideration, not proof of useful progress. |
| Native threshold compaction and explicit DCR | LAYER 3. Only the runtime can yield at a live tool boundary. Stock already performs the threshold check. | F6. Automatic compaction does not first dump Z15 state. Explicit DCR is cooperative, not an atomic native idle-and-compact operation. |
| History rotation and checked publication | LAYER 3 writes history before pruning and stages exact authorized paths. Static files/CI cannot perform periodic file movement or Git admission. LAYER 2 checks preservation. | F6, F11. No broad cleanup or disk-growth remedy. |
| Role text and task methods | LAYER 4 states the remaining interpretation rules. LAYER 5 selects task methods and source comparison because stronger checks cannot decide all meaning. | F3, F4, F5, F9, F10. A review is saved judgement, not an infallible result. |

The installer places the same checked-update and close commands in the existing repo verification entry where supported. It reports missing tooling or unwired CI instead of success. Task regressions remain in the product's existing test location. Reviews and needed exact text proof go into Log/history, not another always-loaded file. [31 §2][a-components] [31 §5][a-storage]

## 3 Hooks

`engine/` below means `pi-streams/engine/` in pi-stack. Every named function is proposed. Commands are stock public Prime commands unless explicitly called pi-stack commands. They use the existing public transport from `bin/prime_cli.py`, with protocol 7/schema 30 validation and command/reply correlation. No arbitrary callback installation is proposed. [42 §3][stock-hooks]

Resolve the current routing `activeSessionId` and verify its durable `get_connection_state.sessionId` before effects. Do not assume those names identify the same thing. Store the full durable session ID in repo entries and use the routing ID in command fields. This follows 31's explicit identity distinction rather than copying 42's abbreviated command examples literally. [31 §3][a-hooks] [42 §3][stock-hooks]

### Save-incoming-message hook

- **Trigger and layer.** A participating caller submits text for the coordinator or a registered worker. LAYER 3 orders save before the live send, which files and CI cannot do.
- **Input.** Registered stream/role/worktree, full durable session ID, caller-retained command UUID, exact UTF-8 text, requested `steer` or `followUp` lane and trusted sender reference if available. Unsupported attachments are rejected before saving/sending, not replaced with text pretending to retain them.
- **Output.** One original-message Log entry and an unread Goals item in the same STATE replacement. Generated wake, dump, resume and worker-result messages are recorded commands linked to existing work, not new human requests. Return the saved-message text only after local readback.
- **Code and stock command.** `engine/prime.py::send_message` calls `engine/state.py::save_message`. After the fresh-STATE and stale-command checks, send `prompt_and_wait` with the routing `activeSessionId`, rendered `message` and requested `streamingBehavior`. The envelope `id` is the caller's UUID. Stock fields are in `crates/pa-types/src/daemon/command.rs:82-108,367-375`. [42 §3, save hook][stock-hooks]
- **Failure and repeat.** Local write/sync failure sends nothing and returns no saved claim. Same UUID plus identical text/target/lane reuses the saved entry. Different bytes conflict. Before socket write, save an ordinary Log entry saying the native result is unknown. A timeout or crash after that entry never triggers an automatic resend. Stock does not deduplicate the command UUID durably. A local save is not proof of native acceptance or application.
- **Limit.** Direct TUI/socket/worker input and native scheduled, child or goal messages can bypass this hook. Their capture is not claimed. Never-sent bot input is also outside its knowledge.

### Fresh-STATE hook

- **Trigger and layer.** Immediately before each model-directed pi-stack send, including a wake, worker brief, dump, review or resume. LAYER 3 runs at the live send boundary because context and CI cannot refresh themselves there.
- **Input/output.** Read exact AGENTS/STATE bytes and hashes, validate current work/source preservation, then render the complete send-message text in §4. This is a fresh message, not a second editable current-state copy.
- **Code and stock command.** `engine/prime.py::send_message`, `engine/state.py::check_state` and `engine/prompts.py::render`, using `prompt_and_wait.message`.
- **Failure and repeat.** Missing/malformed files prevent the send. An unsent message can be rebuilt. A possibly sent message is not repeated just to refresh context. No lock is held while awaiting its result.
- **Limit.** No external per-provider-request project-file callback is established. Construction/reload, executable skills and native memory refresh do not supply that guarantee. The unchanged stock constructor leaves tool callbacks at default and uses a pass-through context transform. Later internal requests can see older supplied STATE. [42 §§1,3][stock-overview] [42 §3, fresh hook][stock-hooks]

### Save-Prime-reply hook

- **Trigger and layer.** The client receives its correlated reply, or queries messages after an observed event. LAYER 3 must await a live response; files and CI cannot capture it.
- **Input/output.** Command UUID, actual sent-message hash, durable session, exact success/error/data and relevant returned/queryable messages become an ordinary Log entry. A finished run is not a completed request.
- **Code and stock commands.** `engine/prime.py::save_reply` and `engine/state.py::append_log`, using `prompt_and_wait`, `get_messages`, `get_connection_state` and optionally `attach`. Preserve interleaved events without mistaking them for replies. [42 §3, reply hook][stock-hooks]
- **Failure and repeat.** A failed local save reports unsaved output and prevents automatic follow-on work. Identical repeated reply adds no second entry. Conflicting reply bytes are an error. Disconnect/missing output is unknown, never success or permission to repeat an external job. Old event history cannot be replayed.

### Stall-wake hook

- **Trigger and layer.** Existing tick observes idle finite current work, even with no new event. LAYER 3 supplies the clock unavailable to files and CI.
- **Input/output.** Current coordinator, Goals/Rules, known worker assignments, prior saved commands, and `get_state`, `get_connection_state`, `get_queue`. Send one wrapped stall-wake text only when work is eligible. Human waits, paused/completed work, unread newer human input, unexplained running work or an unknown earlier send prevent automatic product continuation. A healthy worker blocks only dependent work when an independent eligible request is established.
- **Code and stock commands.** `engine/tick.py::wake_prime_if_needed` calls `engine/prime.py::send_message` through the checks above. Reuse stock queries and `prompt_and_wait`, not a new timer or native command.
- **Failure and repeat.** Failed/ambiguous query gives no wake. Under the existing stream lock, compare current session and relevant Goals/Rules again. Use durable session, objective-text hash and last observed native leaf already recorded with a wake to find duplicates. An unknown/pending matching send blocks another. A later finished run's changed leaf permits reconsideration. A leaf is not evidence of success. [42 §3, stall hook][stock-hooks]
- **Limit.** Status queries are observations, not a native reservation. Deployment must explicitly resolve stock goal/scheduled continuation versus tick ownership. This document enables neither a competing driver nor a new delay.

### Compact-at-threshold hook

- **Trigger and layer.** The existing stock checks run before prompts and after completed tool batches. LAYER 3 can yield during a live run where files/CI cannot. Native overflow recovery can also compact. [42 §3, threshold hook][stock-hooks]
- **Input/output.** Existing settings `compaction.enabled`, `thresholdPercent`, `reserveTokens`, `keepRecentTokens`, model context window and output limit determine the native threshold. A positive computed boundary triggers when estimated context is strictly greater than it. Output is native summary/context reduction and continuation. No new threshold or settings value is chosen here.
- **Code and stock extension point.** Existing `crates/pa-daemon/src/agent_engine/turn/run_loop.rs:44-57,166-173`, `agent_engine/lifecycle.rs:1183-1237`, `agent_engine/turn/model.rs:390-446` and `pa-core/src/session_engine/compaction.rs:152-201`. Proposed `engine/prime.py::check_compaction_settings` validates explicitly authorized settings before creating an owned session. `observe_compaction` records an observed saved entry. No Prime code changes.
- **Failure and repeat.** Do not add a tick threshold compactor. Missing/error results are not successful compaction and do not authorize a second compact. Verify live behavior rather than trusting the supervisor's enabled flag, which can differ from an already-constructed core session. [42 §3, threshold hook][stock-hooks]
- **Limit.** The percentage is adjusted by retained-context and output/reserve headroom. It does not promise a literal absolute 150k boundary. Stock automatic compaction does not wrap every occurrence in the explicit dump/resume prompts below. Context metadata and settings require a future real-runtime check. These are ordinary-path gaps, not excluded login failures.

### Explicit-DCR hook

- **Trigger and layer.** An explicit user or separately authorized stream policy requests DCR. LAYER 3 coordinates native compaction, which files/CI cannot do. This is not a second automatic threshold driver.
- **Input/output.** Current session/files, known jobs/workers, queue/activity and compaction entries. Output is a saved dump, one observed compact result and at most one appropriate resume.
- **Code and stock commands.** `engine/prime.py::dcr` sends the dump via the normal sender and awaits its result. On the same retained connection, call `acquire_session_input_pause{activeSessionId,leaseKey}`. Save the returned `pauseId` in the command's Log reply. Requery `get_state`, `get_connection_state`, `get_queue`; require no active model/tool/compaction/user bash, queued input, running child or known external work. Otherwise release and defer. While paused, call direct `compact{activeSessionId,customInstructions}`. Never put `/compact` in a paused message queue. Public pause/release fields are at `pa-types/src/daemon/command.rs:786-800`; compact is at `:968-975`. [42 §3, DCR hook][stock-hooks]
- **Readback.** Capture pre-command compaction IDs and current branch. After reply, query `get_session_tree` and require exactly one new matching compaction entry on that branch. Verify its actual ID/type/summary in the exact owned native transcript before reporting it saved. Read only; never rewrite native files. Tree memory alone does not prove disk persistence. Ambiguity, target change or absent disk entry is unknown. This does not certify power-loss durability.
- **Resume and release.** Save compact reply/readback first. Reread Goals/Rules and pending saved human input. Deliver newer human input instead of an old automatic resume. Otherwise prepare the full resume body once, wrapped with fresh files and `streamingBehavior:"followUp"`. Record and write the intended next command while paused, but do not await its model result yet. Send `release_session_input_pause{activeSessionId,pauseId}` on the same connection, then await the pending command's correlated result. Waiting for that result before releasing pickup would deadlock. Release in all locally known exit paths, including when no continuation is eligible. A failed/unknown release is reported, not treated as a durable pause. Disconnection releases the pause natively.
- **Failure and repeat.** No resume after failed/unknown dump, compact or readback. Inspect the original command and actual native entries before any retry. The stock pause blocks queued pickup, not another client's compact/fork/bash or a hidden external process. Stock manual compact aborts active work, so observed-idle checks are only cooperative protection. Known running workers/jobs defer explicit DCR; missing activity flags do not prove all jobs stopped. [42 §3, DCR hook][stock-hooks]

### Reject-stale-command hook

- **Trigger and layer.** Before every pi-stack automatic send, DCR step and computed close update. LAYER 3 compares at the live boundary that files/CI alone cannot control.
- **Input/output.** Compare target durable/routing session and exact Goals/Rules used to prepare the command with current values under the existing stream lock. Unchanged authorized work proceeds; changed session/instructions, relevant unread input, real wait, stop or unknown prior send returns the full stale-command text. Log-only rotation does not invalidate unrelated work.
- **Code and stock integration.** `engine/prime.py::check_current_command` and `engine/state.py::check_current_text`, called before stock commands. Participating operator stops use proposed `engine/prime.py::stop_session` and stock `abort{activeSessionId}`. This is not an installed `before_tool_call` callback.
- **Stop handling.** A participating explicit operator stop is saved as original control fields, pauses the affected Goals work and invokes stock `abort`. Do not delay the native abort merely because local saving fails. Report an unsaved pause truthfully. Coordinator stop blocks automatic stream work; worker stop affects that assignment. `abort_and_send_queued` keeps its distinct meaning and is not relabelled as cancellation. A human message changing current instructions is saved before deciding whether older automatic work is stale. [31 §3, stop and tool hooks][a-hooks]
- **Failure and repeat.** Missing current files/unknown state blocks new automatic action. An unsent command can be rebuilt. A possibly sent command cannot bypass a stop by using a new ID. Stock abort does not save this repo pause or prove external work ended.
- **Limit.** Every native model tool within an existing run, direct file edit, direct Prime client and external process can bypass this check. Stock shell wrapping is not an all-tool guard. The full stale-action requirement remains unmet under stock-only. [42 §3, stale hook][stock-hooks]

### Checked-state-update and check-before-close hooks

- **Trigger and layer.** Coordinator submits interpretation/ruling/findings changes or proposes removing/completing requested work. LAYER 2 computes source/target/test checks unavailable to mere context. LAYER 3 publishes after a current-text comparison because CI cannot serialize the live file write.
- **Input/output.** Original entry names, applicable later source, expected STATE hash, proposed Goals/Rules changes and new Log entry. Closure additionally names actual target revision/diff, exact check argv/cwd, report bytes/hash and review entry when required. Reject invalid/stale/missing evidence; keep the request open. A successful check appends the answer and removes only explicitly accounted-for work.
- **Code and stock integration.** `engine/state.py::{update_state,close_work}` and `pi-streams/checks/state.py::{check_state,run_check,check_close}`, exposed by `engine/cli.py`. The agent uses stock tools to invoke the pi-stack CLI. No new native model tool or ask-close API is asserted.
- **Computed checks.** Enumerate saved human-message entries. Each must be represented under Goals or have an explicit linked answer, human cancellation or informational explanation. A new message with no interpretation remains unread, not done. Preserve original bytes, prior Log bodies and unaffected Rules. Verify original/report hashes and target identity. Execute the named authorized local check in its named worktree, recording actual argv/cwd/exit/output. Do not accept a claimed green run as execution. Do not rerun a job-submission command as a harmless test. Before publication, recheck target and current instructions. [31 §§3,5][a-hooks] [42 §3, close hook][stock-hooks]
- **Review.** Proposed nontrivial current-objective completion includes a fresh source-comparison worker's saved accept/rework/unknown findings. A wholly mechanical result can carry no review if current Rules permit it. Deciding which case is mechanical remains judgement, not a computed proof. The source-comparison text in §4 is the complete added review instruction. [31 §§2,4][a-components]
- **Failure and repeat.** Run tests/review outside the short file lock, then compare again before writing. Nonzero/error/unknown/timeout produces no done status. Return structured errors plus the close-refusal text for close requests. Identical prior source/result updates reuse the linked entry; changed target, source or check needs new evidence. Direct STATE edits, publication outside this command and a wrong semantic criterion remain bypasses.

### Rotate-history-and-stage hook

- **Trigger and layer.** Every successful checked update and each tick, even while work waits. LAYER 3 performs live file movement/publication that static layout cannot. LAYER 2 checks exact preservation.
- **Input/output.** Parsed Log and exact authorized changed paths. Write overflow and retired-rule history before publishing STATE with at most 30 Log entries. Goals/unanswered work and live Rules do not expire by count.
- **Code and stock integration.** `engine/state.py::rotate_log` and existing `engine/project.py::commit_repo`; no native command is needed.
- **Failure and repeat.** Different existing history bytes refuse publication. Interrupted history-before-STATE publication can leave an extra identical copy, never prune missing bytes. Retry compares content. Stage only exact authorized AGENTS/STATE/history and selected report paths. Refuse unrelated staged files. Capturing private messages does not authorize publishing them remotely. No automatic push, broad staging or cleanup authority is added. [31 §§3,5][a-hooks] [42 §5][stock-storage]

### Shared command and file rules

Keep the final current-text check, before-send Log write, fresh STATE read/render and socket write within one short stream lock. An already-locked caller uses the same updater's locked entry, not a second flock. Release it before awaiting replies, tests or inference. The transport must separate write from wait and correlate multiple outstanding commands so pause release can proceed while a resumed prompt awaits pickup. No all-stream lock spans a model call. A direct Prime client remains outside that lock. [31 §3][a-hooks] [42 §3, common behavior][stock-hooks]

Use same-directory temporary files, file sync, atomic replacement, parent-directory sync and readback. History must be durable before its source is pruned. A post-replace sync error is unknown until inspection, not guaranteed rollback. Propagate caller cancellation/explicit command timeout. No timeout proves an effect stopped, and no default deadline or resource budget is added. [31 §5][a-storage] [42 §3][stock-hooks]

## 4 Prompts

These are the complete new fixed texts. `engine/prompts.py::render` is their single implementation source. All `_json` fields use JSON encoding. IDs/paths are validated before substitution. Render once with one final LF. Never reinterpret substituted text as template code or a slash command. Native base/tool/system prompts stay stock. Native automatic compaction does not use this candidate's explicit-DCR texts. [42 §4][stock-prompts]

### AGENTS.md role text

The installer writes this shared stream role file. The send wrapper supplies the coordinator/worker role from existing registration, not user quotations.

```text
Use the coordinator or worker role supplied by pi-stack's registered session.
If you are the coordinator, coordinate requested work and do not write product code. Assign independent product work to workers in separate worktrees. Update STATE.md through the checked pi-streams command.
If you are a worker, change only your assigned product worktree. Return actual results and remaining work. Do not edit the shared stream STATE.md.
Goals contains the North Star, finite current objective and work still requested. Rules contains only rulings in force. Log contains recent messages and findings, not another current authority. A new priority or plan does not cancel another request.
Read the whole original message when interpreting or completing its work. Use the named existing path when required. Record actual target, invocation, result and uncertainty. A green check can test the wrong proposition.
Propose done status only through the computed closing check and any required source comparison. Report each requested outcome, including incomplete and waiting work. A saved message, finished run or summary is not completion.
Preserve human stops and unrelated rules. Do not invent approval gates, resource caps or extra task files. Open history only for the original, proof or review needed by the work.
pi-stack supplies fresh files before its messages, not before every internal Prime request. Its command checks do not intercept every model tool. Do not claim those stronger guarantees.
Report failures and unknown external results. Do not log in, repair the environment, change provider or model, delete an original session or repeat an uncertain job. A new human instruction must be read in its actual scope.
```

### Send-message text

Fresh-STATE wraps every pi-stack model-directed body below, including human text, worker briefs and reviews. Native command-only `compact` and `abort` are not model messages.

```text
Current stream files for stream {stream_id_json}, Prime session {session_id_json}, role {role_json}, command {command_id_json}.
AGENTS.md at {agents_path_json}, SHA-256 {agents_sha256}, exact text as JSON follows.
{agents_text_json}
STATE.md at {state_path_json}, SHA-256 {state_sha256}, exact text as JSON follows.
{state_text_json}
Original entry references as JSON follow.
{original_entries_json}
Message body as JSON follows.
{body_text_json}
Use current Goals and Rules. Quoted messages and summaries do not replace current rulings. Keep the original request separate from your interpretation. Saving or delivering this message is not application or completion. Only AGENTS.md and STATE.md were automatically supplied by pi-stack for this message.
```

### Saved-message text

Return to the caller only after the original and Goals item pass local readback. This is not sent to the model.

```text
{stream_id}:: Saved message {command_id} before sending to Prime. Sending status is {sending_status}. Native delivery, application and completion are not established by this save.
```

`sending_status` is exactly `not sent`, `sent, waiting for result`, `Prime replied` or `unknown after connection loss`. A reply's actual success/error is separate; `Prime replied` never means applied. No stronger automatic applied acknowledgement is added.

### Stall-wake text

The tick uses this body only after eligible-work and stale-command checks.

```text
The tick found eligible unfinished current work in this stream.
Use the supplied AGENTS.md and STATE.md. Advance only the finite work allowed by current Goals and Rules. Independent work need not wait for an unrelated worker. Preserve actual human waits and stops.
If no eligible next action remains, record the real wait or completed current objective and report findings by original request. Do not create another task from the North Star alone or invent a proof campaign, approval gate or resource cap.
Use the requested task method. Another turn or a changed plan is not done status. Use the checked pi-stack command for completion.
```

### DCR-dump text

Use only for explicit DCR before obtaining the native pause, not before every stock threshold compaction.

```text
Prepare this Prime session for explicit DCR.
Read the supplied AGENTS.md and STATE.md. Through the checked pi-stack command, preserve the current objective, every unanswered original message, current Rules, actual worker/job identities, waits and needed proof references.
Append one Log note with completed work, actual failures and unresolved uncertainty. Do not remove unfinished work to shorten context or retire a rule without an applicable source. Do not prune Log yourself.
Do not start new product or external work, repair the environment or write a resume prompt. Finish after the checked save. pi-stack must still inspect native activity before requesting compaction.
```

### Explicit-compaction instructions

Pass this verbatim as `compact.customInstructions` only after dump and cooperative idle checks.

```text
Preserve original user requests separately from plans and interpretations. Preserve later human instructions, unfinished work, active prohibitions, human waits, running worker and external-job identities, uncertain effects and exact saved proof references. Keep native tool-call and result relationships complete.
Checked STATE.md remains the current Goals, Rules and Log. A conversation summary cannot cancel or complete its work. Do not infer success from missing error text. Do not add rules, memory, skills, environment changes or budgets. Return the native summary. pi-stack decides whether a separate resume is appropriate.
```

### DCR-resume text

Use once after compact reply and disk readback, only when no newer saved message takes precedence and current work remains eligible.

```text
Explicit DCR saved compaction entry {compaction_entry_id_json} in Prime session {session_id_json}.
Use the supplied current AGENTS.md and STATE.md, not only the compacted narrative. Account for newer messages before choosing work. Open exact history entries for the original or proof when needed.
Continue only finite work still authorized by Goals and Rules. Do not repeat a worker or external job to replace an unknown result. Inspect its existing identity or report uncertainty. This resume neither moves workers to another parent nor releases unrelated waits.
```

### Worker-brief text

The coordinator uses this body for an independent registered worker's initial task, after recording its full session and disjoint worktree under Goals.

```text
You are a worker for stream {stream_id_json}, session {session_id_json}.
Your assigned product worktree is {worktree_json}. Your requested work is {work_json}.
Read the supplied shared stream AGENTS.md and STATE.md under their worker role. Keep applicable product instructions.
Original message entries are {original_entries_json}. Compare this brief with those originals before changing the product. Report any mismatch rather than silently narrowing or broadening the work.
Change only the assigned worktree. Do not edit stream STATE.md or create a worker-report file. Return exact target, actual invocation, observed result, retained proof references, unanswered outcomes and existing worker/job identities. The coordinator saves needed findings and proof in Log/history.
```

### Source-comparison text

Use for the fresh read-only worker required by a nontrivial current-objective close. Creating that worker is future implementation behavior, not an operation performed by this design task.

```text
Compare the proposed result with the whole original requested work.
Original message entries are {original_entries_json}. Applicable later instructions are {later_entries_json}.
Current AGENTS.md and STATE.md are supplied. Actual target is {target_json}. Saved results and proof are {result_entries_json}.
Check whether the result answers every requested outcome and whether the chosen test asks that question rather than an easier substitute. Check protected behavior, the actual named tool invocation and legitimate alternative implementations.
Do not edit product files or STATE.md, run destructive commands or touch credentials. Return one JSON object with answer equal to accept, rework or unknown, findings as an array of exact source/result references and statements, and unanswered as an array of remaining requested outcomes. Missing proof is unknown, not acceptance.
```

### Stale-command text

Return to the requesting caller for a refused unsent command. Do not inject it into a stopped model.

```text
{stream_id}:: Did not send {command_name}. The session, current Goals/Rules, newer input or waiting condition no longer permits the prepared command. Read current STATE.md before preparing another automatic action. A possibly sent command must be inspected, not resent under a new id.
```

### Close-refusal text

Return from a computed close that did not pass, without removing requested work.

```text
{stream_id}:: Did not mark work from {original_entry} done. Check details as JSON follow.
{failure_json}
The work remains requested. Correct or report the original-source, target, actual check, proof or review problem. Finishing this command is not completion of the request.
```

No automatic failure-repair, login, F-DCR or native-child-transfer prompt is added. Other runtime diagnostics use actual structured command results, not additional model instructions.

## 5 Artifact storage

`<stream>` is the existing registered stream directory. This candidate uses 31's shared stream AGENTS/STATE pair for coordinator and workers. Only the coordinator and pi-stack's checked updater publish STATE. Workers write disjoint product worktrees and return findings. This differs from 42's worker-owned STATE paths but introduces no additional current copy. It is a candidate contract, not a change applied to existing streams. [31 §§4-5][a-storage] [42 §5][stock-storage]

| Path | Schema and writer | Reader/timing | Rotation and retention |
|---|---|---|---|
| `<stream>/AGENTS.md` | Exact UTF-8 role text in §4. Authorized installer/template update writes it. | Sender before each participating message. Coordinator/workers receive its exact text. | No rotation or per-failure additions. |
| `<stream>/STATE.md` | UTF-8 Markdown, LF, exactly Goals/Rules/Log using the schema below. Checked updater is the sole supported writer. | Human, sender, tick and close checker use the same bytes. | Rewrite Goals/Rules in place. Keep at most 30 Log entries. Unanswered work and current Rules have no count expiry. |
| `<stream>/history/<UTC ts>-<slug>.md` | One immutable Log-style entry per file. Contains rotated messages/results/reviews or explicitly retained detailed text proof. Updater writes it. | Read exact named entries on demand. Integrity checks can read them without loading them into model context. | No automatic deletion. Retired rulings use `<UTC ts>-rule-retired-<slug>.md`, including their original and replacing source. |
| Existing task repo/worktree files | Product/test files use existing project formats. Assigned worker writes them. | Task check/reviewer uses exact revision/diff and authorized file paths. | Preserve needed exact text outputs in history before a native path or task report can disappear. No data-directory import or automatic cleanup. |
| Existing Prime settings | Stock `<agent-dir>/settings.json` and `<cwd>/.prime/agent/settings.json`. Only explicitly authorized user/installer settings changes. | Construction and existing native compaction. | Stock lifetime. No chosen values or settings writes in this document. |
| Existing Prime session/worker files | Stock `<session-dir>/<session-id>.jsonl` and existing worker storage, unchanged and Prime-written. | Stock reload/context, and read-only checks of entries named by public queries. | Stock retention. Never edit or delete them to manufacture successful recovery. |
| Existing pi-stack registries/tick/locks | Existing `threads.tsv`, `stream.toml`, project index, tick files and Git-directory stream lock keep existing formats/purposes. | Registered coordinator/worker lookup and short cooperating file operations. | Existing lifecycle. No new task store, counter, marker tree or command-progress file. |

Only the three Z15 stream artifact paths carry new task content. Product files and existing native/engine files are listed to state their boundaries, not to add another artifact family. [31 §5][a-storage] [42 §5][stock-storage]

### Exact STATE schema

```markdown
## Goals
### North Star
Text: <JSON string>
Original entry: <JSON entry basename or null for unverified migrated text>

### Current objective
Text: <JSON string or null>
Status: <active|waiting|paused|complete|unset>

- [ ] <one-line summary of a whole human message>
  Original entry: <JSON entry basename>
  Required: <JSON string or null while unread>
  Workers: <JSON array of {session,worktree,work}>
  Next: <JSON string or null>
  Waiting for: <JSON string or null>

## Rules
- <short current ruling>
  Original entry: <JSON entry basename>
  Applies to: <JSON description of affected work or stream>

## Log
### <UTC timestamp> <one-line subject>
File: <JSON eventual history basename>
Prime session: <JSON full durable session ID or null>
Prime command: <JSON command UUID or null>
Prime entry: <JSON observed native entry ID or null>
<entry body with a fenced JSON object>
```

The North Star has no completion flag. An unanswered whole message stays under Goals while plans/assignments change. Initially Required is null and Waiting for names its unverified send until the connected result or inspected native input supports an update. An unread or unknown human send blocks unrelated automatic product interpretation of that source; it does not block saving a new human stop. Removal requires a linked complete answer/proof, explicit applicable human cancellation, or a saved informational explanation. Code can check the explanation exists, not that its interpretation is correct. Rules retire only with the named source; changing one ruling cannot silently remove another. [31 §5][a-storage]

### Exact Log/history bodies

These are fields in existing entries, not named record types. Each JSON object uses UTF-8, sorted keys, no non-finite numbers, and exact decoded strings. The entry file ends with one LF. `sha256` of original/report text covers its UTF-8 bytes without newline normalization. Only trusted operator-channel provenance can support human ruling or stop changes. A model-supplied sender field cannot grant that authority. Retain necessary command fields, not daemon greetings, connection ownership data, credentials or auth/settings payloads.

| Entry content | Required JSON fields and values |
|---|---|
| Original human message | `text`, `sha256`, `sender`, `received_at`, `send_as`. `text` is the exact pre-expansion message. `sender` is trusted channel reference or null, not a model's authority claim. `send_as` is `steer` or `followUp`. Log's Prime command is the retained caller UUID. |
| Operator stop | `text:null`, `command:{type:"abort",session:<durable ID>}`, `sender`, `received_at`. Preserve actual control fields, not invented human wording. |
| Before sending a command | `command`, `body`, `original_entries`, `goals_rules_sha256`, `result:"unknown until reply saved"`. Body is exact human/generated text before wrapping. Do not include a hash of the final outgoing wrapper here because the included STATE would then hash itself. |
| Connected Prime reply | `command`, `sent_text_sha256`, `success`, `error`, `data`, `messages`. Retain actual relevant content. Absent result/error is not invented success. Link to the before-send command in the entry header. |
| Proposed/checked answer | `original_entries`, `later_instruction_entries`, `target`, `invocation`, `result`, `findings`, `proof_entries`, `review`. Target includes repo/worktree and exact commit/diff or native job ID. Invocation is actual argv/cwd. Result includes observed exit/error and output reference. Each proof ref is `{entry,sha256,representation}` with full/excerpt. Excerpts also require original reference and exact range. Review is null or `{entry,answer}` with accept/rework/unknown. |
| Detailed text proof or review | `original_entries`, `media_type`, `text`, `sha256`. Review text retains the exact source-comparison JSON. Its references must agree with the answer entry. A task report path can be provenance, but needed retained text bytes live here. No binary/credential import. |
| DCR attempt/result | `command`, `before_entry`, `dump_entry`, `compaction_entry`, `next_command`, `result`, `error`. Unknown/not-yet-observed native refs are null. Result describes actual command/readback, not task acceptance. These are ordinary command/result notes, not a separate DCR store. |

Repo entry names use `YYYYMMDDTHHMMSS.ffffffZ-<lowercase-ascii-slug>.md`. The slug includes the existing command UUID and its plain purpose, such as incoming-message, before-send or reply; successive intended changes use their own existing command ID. Reuse the first stored timestamp/name for a repeated command/purpose. Identical bytes reuse that entry; changed bytes under the same name fail. Different messages with equal text remain separate. Store `<UTC timestamp>` in headers as RFC 3339 UTC with fractional seconds. Entry references are the eventual history basename even while the entry is hot in Log. `state read-entry` resolves it in Log or history without an index file. [31 §5][a-storage] [42 §5][stock-storage]

A before-send note means the socket write may have started. On restart, absence of a reply never means safe to resend. Inspect native messages and actual work; keep unknown work waiting. Command IDs correlate this client's records, not stock native deduplication. Scanning Log/history for these notes has a cost; no additional index is justified without measuring it. [42 §§3,5][stock-hooks]

### Checked file interface and publication

Proposed pi-stack commands are `state check <stream>`, `state read-entry <stream> <basename>`, `state update <stream> --expect <SHA-256>` and `state close <stream> --expect <SHA-256>`. Update stdin contains `goals`, `rules`, `entry`; unchanged sections are null. Entry contains `subject`, `body`, `original_entries`. Close additionally supplies `target`, `check:{argv,cwd}`, `report:{path,sha256}`, `proof_entries`, `review`. Paths are canonical authorized locations. Replies contain `success`, `reason`, `state_sha256`, `history_files`; failures exit nonzero. The checker, updater and controlled publication invoke the same implementation, not independent copies. These are proposed pi-stack CLI shapes, not stock Prime APIs. [31 §3][a-hooks] [42 §3][stock-hooks]

Entry names are basenames created by the updater. Reject traversal/symlink escapes. Parse Log headings only outside fenced blocks. Preserve existing entries exactly. Publish needed history before shortening Log and atomically replacing STATE. Raw edits can bypass the supported updater, so every participating send/publication rechecks captured-source completeness. That check cannot stop an unrestricted shell from changing all files. [31 §5][a-storage]

Do not automatically publish private original messages or output just because they were retained locally. Exact-path staging needs the user's existing publication authority. No native sessions, credentials, arbitrary task data or scratch directories enter Git. Remote configuration is not new permission. [31 §5][a-storage] [42 §5][stock-storage]

## 6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure)

### An ask

1. The caller keeps one command UUID with its text. pi-stack writes the exact original Log entry and unread Goals item together. Save failure causes no send.
2. Under the short stream lock, pi-stack checks the current session/Goals/Rules, appends the before-send note, reads the resulting files and writes the wrapped stock command. It releases the lock before awaiting the native reply.
3. The coordinator interprets the whole original and submits checked Required/Rules/assignment changes. Independent workers use separate worktrees and the shared stream pair. Plans do not remove other requests. Worker creation/registration is inspected after an uncertain result before another spawn.
4. The connected native reply is saved. An error can be retained even without an assistant row. A missing reply leaves unknown current work, not an automatic retry or successful result.
5. The task's actual target/invocation/output and needed text proof are saved. At nontrivial current-objective completion, the source-comparison worker challenges the original proposition. The computed close checks bytes, actual test result, target and current instructions, then removes only accounted-for requested work.
6. Findings remain in Log/history. Another unanswered message remains under Goals after 31 unrelated entries. Completing finite current work stops automatic continuation without completing the North Star. Semantic correctness remains fallible.

### A stall and compaction

The next tick can wake eligible idle work without waiting for a new event. It preserves real waits and reuses the existing saved command when a response is unknown. If a new stop is saved before socket write, the stale-command check rejects the old wake. If an older Prime run is already choosing tools, this stock-only candidate cannot veto its next arbitrary tool. [42 §6][stock-lifecycle]

During a long run, stock threshold compaction can occur after a complete tool batch using its configured computed boundary. There is no second tick threshold loop and no claim that STATE was dumped first. Explicit DCR separately uses dump, pause, activity/queue checks, direct compact, disk readback and current-input-first resume. Another direct client's activity can race those checks. A failed/unknown result produces no automatic resume. [42 §§3,6][stock-hooks]

### A failure

A local save fails before the send. pi-stack returns the actual error, sends no native command and does not say saved. If the native request instead fails after sending and returns a connected error, pi-stack saves that error and keeps the request open. If the response disappears, report unknown and inspect the actual session/work before any retry. No automatic environment-repair or fork path is added. [42 §6][stock-lifecycle]

## 7 Risks and notes

The strongest claim is the participating pi-stack path, not all stock activity. Native input, tools, continuation, project context and compaction remain Prime-owned. A public status query plus a local hash comparison cannot become an atomic native tool guard. Likewise a command result captured by a connected client cannot repair missing native persistence. [42 §§3,7][stock-hooks]

Ordinary-path limits remain in scope for assessment:

- Every-provider-request STATE freshness and every-tool stale-action rejection are unmet. They cannot be hidden in the exclusions below. 31 would add native wiring for them. [31 §3][a-hooks] [42 §7][stock-risks]
- Strict native save-before-runnable, complete result persistence and durable same-command retry lookup are not supplied by local Log saves. The repo and native queue are separate writes. Unknown sends remain waiting. [31 §3][a-hooks] [42 §2][stock-components]
- A literal 150k boundary and dump before every automatic compact are not promised by stock percentage/headroom handling. The supervisor toggle can differ from a live core. A new owned session's explicit settings and captured behavior must be checked. [42 §3][stock-hooks]
- Native refinement may write additional memory and native goal continuation may add a competing driver. Before an owned deployment, explicitly review global `harnessRefinements`, its separate `autoRefine` settings and native goal/scheduled behavior. No live settings are changed here, and no selected values are implied. [42 §7][stock-risks]
- Same-stream workers share the current file but never publish it. Relevant Rules changes need rereading, not a new human approval. A native worker/RLM message that does not use the common sender remains a bypass. A long Python cell can perform many effects before another participating send. [31 §§3,7][a-hooks] [42 §3][stock-hooks]
- The original request and its chosen checker can be wrong together. Fresh review can miss or falsely reject. Use original-source cases, valid alternatives and actual task artifacts, not record counts, to measure that cost. [31 §7][a-risks] [30, evaluation cases](30-research-designs.md#checks-required-before-selecting-a-design-for-implementation)
- Keeping exact text in the latest 30 Log entries can make STATE large. No hidden early rotation, token cap or deletion rule is applied. Retained history can also grow. Measure costs before introducing more storage machinery. [31 §7][a-risks] [42 §7][stock-risks]
- The earlier spike verified limited connected controls and graceful restart, not successful inference, active-tool DCR or safety under a crash. Source inspection is not a real provider-context test. [42 §1][stock-overview]

### Not handled

| Excluded case | What happens today and what this candidate does |
|---|---|
| Login/auth failure | Stock may return a command/live error with no assistant row. Save a received error, otherwise report unknown. Human repair; no login or credential operation. |
| Quota/provider outage | Existing stock settings govern native retry/wait behavior. This candidate adds no reset/release automation, probe, provider switch or recovery prompt. Stop/report the observed blocker. |
| Disk/resource emergency after native send | A repo save can fail after native effects. Report unsaved/unknown output and stop new automatic sends. No cleanup or reconstruction guarantee. Pre-send local save failure is still handled by refusing the send. |
| Total storage loss or host crash with uncertain effects | Inspect surviving native/repo/work bytes manually. No exactly-once replay or rollback is claimed. |
| Moving running children to another parent | Stock replacement can close children. Keep the parent; wait or require a deliberate human session decision. Reading transcripts does not transfer live results. |
| Automatic F-DCR or arbitrary external-job rollback | No hook performs it. Preserve the original and actual job identity; manual decision is required. Never duplicate a worker/job or delete the original because another session streams. |

These exclusions follow Z23's reduced scope. They do not claim that excluded failures disappear from the corpus. [42 §§2,7][stock-components] [31 §6][a-lifecycle]

## 8 Implementation plan

throughput checkpoint: n/a, read-only investigation.

These are proposed stacked pi-stack commits only. No Prime source change, modified binary, installed-dist edit or runtime operation is part of this document. Reuse actual landed track-1/CLI work. Every unit includes tests; existing-path bugs need an observed old-behavior failure, while a missing new API/parser is labelled new functionality. [31 §8][a-plan] [42 §8][stock-plan]

| Proposed commit | Change | Tests and old-behavior evidence |
|---|---|---|
| `state: keep requested work and exact sources in Z15 files` | One parser/updater and entry lookup using Goals/Rules/Log/history. Preserve text proof/review and retire named Rules. | UTF-8 round-trip, fake headings inside fences, 31 unrelated entries, partial multi-part answer, informational/cancelled versus done, byte-preserving rotation, interrupted writes, missing originals, traversal/symlink rejection. Existing stream creation must fail a preservation case before the fix; new-format unit tests are new functionality. |
| `state: expose checked updates and computed close` | CLI shapes above, actual local test invocation, source/target/proof/review checks, short locks and exact authorized staging. | Nonexecuted green claim, wrong target/report, stale instructions during check, valid alternative, missing review and wrong-sign/smallest-working source cases. Include direct file/shell publication as bypasses, not successful fencing tests. Old broad staging must capture a scratch file before the fix; candidate refuses foreign staged files. |
| `prime: save before sends and preserve connected replies` | Public transport write/wait split, command UUID reuse locally, before-send Log and unknown-result handling. No task storage in transport. | Socket fixture reads saved original/current work before accepting bytes. Save failure emits zero commands. Cover changed content under same ID, equal text/new ID, interleaved events, missing-assistant native error, lost response and restart with no automatic resend. Current thin sender lacks the repo-save ordering and must fail that effect assertion first. |
| `prime: send current files and reject stale client commands` | Fresh wrapper, verified routing/durable session mapping, changed-Goals/Rules checks and cooperative operator-stop handling. | Literal full prompt fixtures, new STATE on every participating send, missing source stops send, Log-only changes do not block unrelated work, stop before socket write rejects old wake, worker stop preserves independent work. Negative tests demonstrate a stock internal request/tool can bypass these client functions. Do not make those tests pass by pretending native callbacks were installed. |
| `tick: reconsider only eligible current work` | Existing tick, native state/queue queries, known worker assignments and leaf-based duplicate lookup in Log/history. | Event-free idle work wakes once. Human wait, unread newer source, completed objective, unknown send and dependent healthy-worker wait do not. Independent work remains eligible. Race concurrent ticks and a later stop. Observe actual command/no-command effects rather than timer activity. |
| `prime: use stock threshold compaction and explicit DCR commands` | Configuration diagnostics before new owned session, observation of native automatic compact, explicit dump/pause/check/direct compact/readback/resume only. | Characterize native before-prompt/after-tool threshold and headroom calculation without a Prime patch. Cover misleading supervisor/live-core toggle, busy tool/bash/child, unknown jobs, new input, pause release, disk entry missing, response loss and duplicate compact. Assert no second threshold driver, no paused `/compact`, and no resume on uncertainty. Source/fixture checks do not count as successful runtime compaction. |
| `templates: install role, worker and source-comparison text` | Exact §4 prompts, shared role pair and repo review findings. Install existing-method integration and supported repo checks without additional current files. | Full-string fixtures, correct coordinator/worker scope, original-versus-brief mismatch, review accept/rework/unknown with saved refs, same configured provider and no fallback, unsupported CI reported. Temporary-home install creates only specified artifacts. |
| `verification: qualify only the stock behavior actually observed` | Rerunnable offline scenarios and a future optional isolated stock verification command. Doctor reports unmet every-request/all-tool requirements and unreviewed native continuation/memory settings. | Run existing pi-streams/overlay suites and focused source/transport checks. With separate authorization and available auth, capture actual provider context, long internal runs, stale-tool bypass, stock automatic compact and explicit DCR. Test direct-client bypass honestly. No product or safety guarantee is promoted from a fake server. |

Canonical source checks remain `python3 -m unittest discover -s pi-streams/tests` and `bash scripts/check-overlay.sh`. The proposed stock-runtime checks need separate authorization and the actual configured provider; missing auth is reported, not fixed by copying credentials or changing provider. No such tests are run for this docs-only deliverable. [31 §8][a-plan] [42 §8][stock-plan]

The open questions and explicit losses are in [50 v2](50-a-vs-b.md). Passing document structure/link checks establishes a complete proposal, not that stock Prime meets the unmet freshness or stale-tool requirements.

[a-components]: 31-design-a-detailed.md#2-components-and-justification
[a-hooks]: 31-design-a-detailed.md#3-hooks
[a-storage]: 31-design-a-detailed.md#5-artifact-storage
[a-lifecycle]: 31-design-a-detailed.md#6-lifecycle-walkthrough-an-ask-from-intake-to-close-a-stall-a-failure
[a-risks]: 31-design-a-detailed.md#7-risks-and-notes
[a-plan]: 31-design-a-detailed.md#8-implementation-plan
[stock-overview]: 42-design-b-prime-unchanged.md#1-overview
[stock-components]: 42-design-b-prime-unchanged.md#2-components-and-justification
[stock-hooks]: 42-design-b-prime-unchanged.md#3-hooks
[stock-prompts]: 42-design-b-prime-unchanged.md#4-prompts
[stock-storage]: 42-design-b-prime-unchanged.md#5-artifact-storage
[stock-lifecycle]: 42-design-b-prime-unchanged.md#6-lifecycle-walkthrough-an-ask-from-intake-to-close-a-stall-a-failure
[stock-risks]: 42-design-b-prime-unchanged.md#7-risks-and-notes
[stock-plan]: 42-design-b-prime-unchanged.md#8-implementation-plan
[native-hooks]: 41-design-b-prime-detailed.md#3-hooks

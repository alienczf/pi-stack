Runtime: stock Prime, no Prime changes (Z22)

# B over stock Prime

### New concepts

| plain name | one-line meaning | corpus failure it fixes (F-number or core cause) | why no existing artifact or term can carry it |
|---|---|---|---|

None. Incoming messages, Prime commands and their replies are saved as ordinary Log entries and rotate into history. Current work stays in Goals. There is no second task store, new task vocabulary, or numbered name for a hook or prompt.

## 1 Overview

This is input to the merged candidate requested in Z23. It is not a selected design. Z17 remains in force. G29 stops the rename of 41; [41](41-design-b-prime-detailed.md) is reference only and was not changed for this follow-up. [40](40-b-over-prime.md) retains the feasibility evidence. This document describes only additions to pi-stack around unmodified Prime v0.10.1.

The useful stock integration is an external client hook around existing commands. It can save text before sending it, include current STATE in the message, run the tick, request native compaction when idle, reject stale pi-stack commands, and check a proposed update to Goals. It cannot install arbitrary Rust callbacks into an already-running Prime daemon.

Two limits matter to the merged design. A client hook can refresh STATE before each message it sends, not before every internal model request in a long Prime run. A client check can reject a stale wake or close command, not every `bash`, `edit`, or `python_repl` action inside that run. Those are ordinary-path limits, not login corner cases. Calling the client functions hooks must not conceal them.

The candidate therefore puts deterministic checks in pi-stack's sending and file-writing code. Judgement stays beside the work in Goals, Rules, Log and review notes. This makes the overlap with A explicit. Stock Prime cannot retain B's full runtime ownership without moving some authority back into these files. There is no reason to invent a second store to preserve an A/B distinction.

### Stock source and verification boundary

All Prime source citations below are at stable revision `8aac8692456c00c01d4e53e60e6d3347a3506559`, not the moving nightly. Paths are relative to `/home/alphalab/Projects/prime-agent`. Read-only `git show` and `git grep` inspected that revision without switching its checkout. Both protocol 7 and schema 30 are checked by the client, but neither label promises these higher-level behaviours.

The earlier spike's final stock-binary control check is `/tmp/prime-t4.F0zJfHkm/live-check.json`, with graceful restart readback in `restart-check.json`. It proved connected input control, an awaited provider refusal without an assistant row, and explicit refusal of older event replay. It did not verify successful inference or compaction. No new runtime, code, model call, credential operation, or live-session action was performed for this docs-only follow-up.

## 2 Components and justification

The six requested behaviours have the following limits. Each implementation path named in this document is a proposed pi-stack change, not existing code unless identified as such. No Prime source file is an implementation target.

| Behaviour | What stock Prime carries | What pi-stack adds | Corpus and layer justification |
|---|---|---|---|
| Save incoming messages | `prompt_and_wait` accepts text and an optional `streamingBehavior`. Native saving is not a durable message-id API. | Save the exact text and command id in Log before sending. Add its current-work line under Goals before returning a saved response. Never deduplicate different messages by equal text. | F2/F8, C1/C4. LAYER 3 saves before a live send; files and CI alone cannot control that order. The saved source and current work are LAYER 1 because no stronger context layer exists. |
| Fresh STATE each turn | Text in `prompt_and_wait` or `steer` can include AGENTS and STATE. There is no demonstrated external per-model-request callback for arbitrary project files. | Read current files immediately before every pi-stack send and include their exact bytes. Keep native internal-turn freshness explicitly uncovered. | F2/F6/F12, C1/C5. LAYER 1 carries the current text. LAYER 3 reads and sends it because context and CI cannot run at a live command boundary. A textual instruction to reread on an internal turn is only LAYER 4. |
| Stall wake | `get_state`, `get_connection_state`, `get_queue` and `prompt_and_wait` supply observations and delivery. | The existing tick checks finite unfinished work, waits, current session and queued commands before sending one wake. | F1/F3/F9/F12, C3. LAYER 3 can run while the agent is idle; context and CI cannot provide that clock. A new model turn still does not prove useful progress. |
| Compaction at the threshold | `compact` is an awaited public command. Input pause prevents queued pickup. Current native compact aborts active work, so it must not be called blindly. | At the next observed idle boundary after the configured threshold, pause input, recheck work and queue, perform DCR, read back the saved compaction entry, then resume only if still appropriate. | F6, C3/C5. LAYER 3 coordinates the live session; stronger layers cannot pause it. This is polling at a safe observed boundary, not exact enforcement before every model request. |
| Stale-action guard | Native status and queue controls exist. Stock daemon has no externally installed before-tool gate covering its model tools. | Compare the current session and current Goals/Rules with the values used to prepare each pi-stack wake, DCR step and close command. Refuse a mismatch. | F3/F10, C4. LAYER 3 rejects the live pi-stack action; files and CI cannot stop a queued client command. This does not guard arbitrary native tools or external writers. |
| Closing checks that can be computed | Prime ends runs and returns results. It has no native ask-close command or evidence requirement. | A pi-stack close command checks source, target, actual test invocation, report bytes and unchanged current instructions before updating Goals and appending Log. | F4/F5/F10/F11, C2. LAYER 2 performs the deterministic checks because context cannot execute them. LAYER 3 applies the checked file update because CI cannot serialize that write. Whether those tests answer the user is still judgement. |
| Review and methods | Existing Prime messages/tools can read files and invoke a pi-stack command. | AGENTS gives short rules. Goals records what the original request requires; Log/history hold the actual method and review findings. Use task-specific methods on demand. | F3/F4/F5/F9, C1/C2. LAYER 4 retains interpretation rules that stronger checks cannot fully encode. LAYER 5 selects methods that are not universal runtime transitions. |

### Four gaps from 41

Here, covers means the requirement is checked for the named pi-stack path. Works around means pi-stack supplies a narrower replacement outside Prime. Leaves open means the native behaviour is unavailable. None of these labels claims that an unmodified daemon enforces pi-stack's file rules.

| Gap | Answer | Exact action and cost | What bypasses it | Recovery that stays manual |
|---|---|---|---|---|
| The message save ignores write errors and returns no id | **Works around.** | pi-stack saves the original text in Log, with the id it will put on its outgoing command, before sending or reporting saved. Failed local writes stop the send. This does not repair Prime's discarded write errors or create a native message id. | Direct TUI input, another socket client, direct-worker input, native scheduled prompts, native goal continuation and child notices not sent through pi-stack. | A lost native reply leaves an uncertain send. Inspect native history and actual work before choosing whether to retry. Reusing a command id is not native deduplication. |
| Results are not stored durably on every path | **Works around.** | A connected `prompt_and_wait` client saves its reply and the queried messages as Log/history reports. A captured error remains readable even without an assistant row. Live events are only a reason to query. | Disconnected or lagged observers, work from other clients, internal continuations, and a crash between native completion and the local save. Native event replay remains unavailable. | Missing results are reported as unknown. A human checks native history and task outputs. Never rerun an uncertain external job merely to recover a missing response. |
| No evidence check before an ask closes | **Covers the pi-stack close command; works around the native gap.** | The computed check must pass before that command can mark the corresponding current work done. The original message id remains linked to the check and report. No new native closure is claimed. | Direct editing of STATE, arbitrary shell/Git publication, an agent's final prose, another client and a checker whose meaning is wrong. | Reopen or correct the Goals line and review the original message and actual result. Semantic review remains in repo files, not a runtime success string. |
| No way to move child workers to a new parent | **Leaves open.** | Keep the current parent while its children are running. Defer automatic fork/replacement in that case. Reading a child's transcript is not moving its live completion handling. | A direct native fork, kill, replacement, or another client's coordinator change can still close or strand the relationship. | Wait for workers to finish, or have the human explicitly resolve/stop them and choose the next parent. Do not duplicate workers or delete the original merely because another session streams. |

The native source behind these gaps is concrete. `crates/pa-daemon/src/worker/input.rs:137-161` calls the queue checkpoint before answering. `worker/queue.rs:248-294` ignores its write failure. `worker/turn.rs:597-603` creates message entries later and discards the saved id/error. `worker/turn.rs:838-878` emits terminal events without storing those boundary events. `protocol.rs:412-470` refuses older event replay. `worker/lifecycle.rs:141-163` closes children on replacement rather than moving them to another parent.

## 3 Hooks

These hooks live in pi-stack. Stock command names are their integration points, not a claim that Prime loads these functions as plugins. `crates/pa-agent/src/agent.rs` has Rust callback fields, but the stock product constructor at `crates/pa-core/src/session_engine/engine.rs:690-733` leaves the tool hooks at their default and supplies a pass-through context transform. Source locations are evidence, not additional design vocabulary.

All hooks below have descriptive names. Each live hook is LAYER 3 because files and CI cannot execute its command ordering. The close hook also invokes LAYER 2 checks, which context alone cannot compute. All proposed code is in the pi-stack repository. Use the existing transport from `bin/prime_cli.py` on the read-only track-2 branch as the starting point, not a private worker protocol.

### Save-incoming-message hook

- **Trigger.** A supported pi-stack caller submits a text message for a stream/session, including a user steer. Non-text attachments are not silently accepted by this version.
- **Input.** Stream path, full durable session id, caller-retained command UUID, verbatim UTF-8 text, and requested prompt/steer/follow-up behaviour.
- **Output.** A saved Log entry, a line for unreviewed current work under Goals, and either a queued local send, a native reply, or an explicit unknown result. A saved message is not an applied acknowledgement.
- **Code.** Proposed `pi-streams/engine/prime.py::save_incoming_message` and `send_message`; `engine/state.py::append_log`. Existing `engine/project.py::stream_lock` provides cooperating file-writer exclusion, with worktree-safe Git-directory resolution added there if needed.
- **Stock command.** Send `prompt_and_wait` with `{activeSessionId: <durable id>, message: <full message template>, streamingBehavior: "steer"|"followUp"}`. The public fields are at `crates/pa-types/src/daemon/command.rs:82-108,367-375`. The worker chooses the lane and awaits that input's result at `worker/input.rs:80-161`. Do not pretend that the command-envelope id is a returned native message id.
- **Failure and repeat.** Local write/fsync/rename failure causes no send and no saved response. The same UUID with identical text/target/kind returns its existing local status; changed content under that UUID is rejected. Before the socket write, append an entry saying the send may have started. A crash or timeout after that point does not automatically resend. Report unknown and inspect the native session. A fresh user resend gets a new id only after an explicit retry decision.
- **Bypass.** Anything that sends directly to Prime, native internal producers, and direct edits of the files. This hook is not a native admission veto. Unsupported attachments remain with the caller, not a lossy text substitute.

### Fresh-STATE hook

- **Trigger.** Immediately before every message pi-stack sends, including a wake or DCR resume.
- **Input.** Exact current AGENTS.md and STATE.md bytes, the target durable session id, original message and the current Goals/Rules text.
- **Output.** The full send-message template in section 4. It contains both files and their SHA-256 values. Only those two project-state files are automatically read.
- **Code.** Proposed `engine/prime.py::send_message` reads files and calls `engine/state.py::check_state`. Do not create a separately editable copy of STATE.
- **Stock command.** The `message` field of `prompt_and_wait`. A real `steer` or `follow_up` command can also carry text, but only acknowledges queuing; the proposed pi-stack path uses the awaited form when it needs that input's eventual command result.
- **Failure and repeat.** Malformed/missing files or a changed current session/Goals/Rules before the send stops the call and rereads current state. An unsent retry can rebuild the text. A possibly sent message is not resent merely to refresh it.
- **Bypass and limit.** This covers client sends, not every assistant/tool iteration or provider retry inside one native run. Stock project context is assembled into the system prompt at `pa-core/src/session_engine/engine.rs:566-594`. There is no demonstrated external callback that rereads arbitrary STATE bytes at every internal request. A promise in AGENTS to reread is LAYER 4, not this hook. New direct TUI input and internal child/goal messages can omit the wrapper.

### Save-Prime-reply hook

- **Trigger.** The connected pi-stack client receives its correlated command reply, or an attached observer sees activity and queries current messages.
- **Input.** Command UUID, full session id, exact returned success/error/data and queried message content. Queries never infer an absent error as success.
- **Output.** One Log entry linked to the outgoing command. A successful native prompt means its run finished, not that the original request passed its closing check.
- **Code.** Proposed `engine/prime.py::save_reply`, using `engine/state.py::append_log`. Extend the transport to retain the correlated response/error needed by this function; do not put task state in the transport.
- **Stock commands.** `prompt_and_wait`, `get_messages`, `get_connection_state`, optionally `attach`. Correlate response id and command while accepting interleaved event frames. `worker/input.rs:153-161` returns awaited failure even when no assistant row exists.
- **Failure and repeat.** Save failure reports a local error and does not announce durable capture. A repeated identical reply for the same command adds no second entry; conflicting replies remain an explicit error. Timeout/disconnect is unknown, not success and not a reason to resend. Lost events are not replayable through attach.
- **Bypass.** Native work whose client has gone away, other clients, and events missed before pi-stack records them. This hook cannot manufacture a missing native outcome.

### Stall-wake hook

- **Trigger.** The existing tick observes an idle coordinator with finite unfinished current work.
- **Input.** Current Goals and Rules, stream's current coordinator from existing stream files, pending local commands, `get_state`, `get_connection_state` and `get_queue`.
- **Output.** No message for a real wait, stopped work, a running worker, an unknown prior send or an empty current objective. Otherwise send the full stall-wake text through save-incoming-message and fresh-STATE.
- **Code.** Proposed `engine/tick.py::wake_prime_if_needed`, calling `engine/prime.py::send_message`. Reuse the existing tick, not another timer or daemon.
- **Stock commands.** Query the commands above, then use `prompt_and_wait`. `get_state` supplies the session summary, including running-tool/worker flags; `get_connection_state` supplies context use and leaf id. These are observations, not an atomic native lock.
- **Failure and repeat.** A failed/unknown query prevents the wake. Under the stream file lock, compare the exact Goals/Rules and coordinator used to prepare it. Coalesce duplicate ticks using session id, current-objective text hash and the last native leaf id already recorded with a wake. A pending or unknown matching send prevents a duplicate; a later completed run changes the leaf and permits reconsideration. A leaf id is used for coalescing, not as proof of a successful turn.
- **Bypass.** Native goal/autonomous continuations, schedules, child notices, other clients and code that does not consult current files. The deployment must choose who drives its sessions; the installer must not silently turn on two continuation paths. No default delay, resource cap or universal stalled-time heuristic is introduced.

### Compact-at-threshold hook

- **Trigger.** The tick or the send path observes context at or above an explicitly configured compaction threshold, or a user requests DCR. This is not a default resource budget. No threshold value is selected here.
- **Input.** Current session, known model/context metadata, current STATE, native queue/work observations and the configured threshold.
- **Output.** A saved DCR attempt, a native compaction reply plus readback, and at most one appropriate resume. Busy work is allowed to finish. Unknown model/context use prevents automatic compaction rather than pretending it is zero.
- **Code.** Proposed `engine/prime.py::compact_if_idle`, `engine/tick.py::check_prime_context`, and `engine/state.py::append_log`.
- **Stock commands and sequence.** First run the dump prompt through the normal send path and wait for its result. Then acquire `acquire_session_input_pause{activeSessionId,leaseKey}` on a connection kept open. Requery `get_state`, `get_connection_state` and `get_queue`. Require no active model run, compaction, user bash, tool, running child or queued native input. If any is present, release the pause and defer. While the pause still holds, call `compact{activeSessionId,customInstructions:<full compact text>}` directly. Do not send `/compact` into a paused prompt queue. Direct `compact` awaits its result at `worker/lifecycle.rs:339-357,458-522`; its public shape is `pa-types/src/daemon/command.rs:968-975`.
- **Readback.** Native compaction currently discards a persistence error at `compaction.rs:183-246`. Therefore query `get_session_tree`, find the new compaction entry, and verify its id/type/summary in the owned native transcript file before calling the attempt successful. A worker's in-memory tree alone is not proof of a disk write. Never rewrite Prime's transcript. Native file visibility does not prove power-loss durability.
- **Resume.** Save the command reply/readback in Log first. Recheck current Goals/Rules and pending user messages. Deliver saved newer messages first; do not add a stale automatic resume behind them. Otherwise, if current work is still authorized, send the full DCR-resume text once with `streamingBehavior:"followUp"`, which resumes native queued-input suspension. Release the input pause only after the intended next input is safely identified. The pause ends on disconnect and is not a durable stop.
- **Failure and repeat.** Never compact solely on an earlier idle observation. Summary error, missing disk entry, timeout or disconnect means no success and no automatic resume. An unknown compact result is inspected before a new compact is attempted. New incoming messages can be saved while compaction runs; their sends wait. Do not clear/replay an arbitrary native queue. Current native compact aborts active work at `compaction.rs:55-64,152-180`, which is why all these idle checks are required.
- **Bypass and timing.** The pause blocks queue pickup, not another client's compact/fork/user-bash command. Direct native actions can race the checks. Native automatic overflow compaction can happen inside a run. Stock has `set_auto_compaction{activeSessionId,enabled}`; choosing native automatic compaction or pi-stack's controlled idle policy is an explicit deployment question. This hook cannot enforce the threshold before every provider request and can overshoot it during a long run.

### Reject-stale-command hook

- **Trigger.** Immediately before pi-stack sends an automatic wake, a DCR step, a saved message replay explicitly approved by the user, or a close command.
- **Input.** Target session id and the exact Goals/Rules bytes used to prepare that command. Read current files and current coordinator again under the existing stream lock.
- **Output.** Proceed with the still-current command, or refuse it and return the full stale-command text in section 4. There is no owner counter or extra state file.
- **Code.** Proposed `engine/prime.py::check_current_command` and `engine/state.py::check_current_text`, called by the sending/closing functions, not left for a skill to remember.
- **Stock integration.** Before the existing native command; no native before-tool extension point is claimed. A native input pause is used for DCR but does not turn this check into an OS or tool fence.
- **Failure and repeat.** Missing state, changed coordinator, changed Goals/Rules, stopped/waiting work, or an unresolved older command prevents a new automatic action. An unsent command may be rebuilt after rereading. A possibly sent command stays unknown. This check must not reject an incoming human stop merely because it changes current state; save that human message first and use it to invalidate older automatic work.
- **Bypass.** Every model tool already running or subsequently chosen inside a native run, direct file edits, direct Prime clients and external processes. Stock `shellPath` can wrap shell execution, but it does not intercept all edit/Python operations or carry an expected message/state hash for every call. It is not used here to claim a complete stale-action guard. The full all-tool requirement remains open under Z22.

### Check-before-close hook

- **Trigger.** An agent or human asks pi-stack to mark a message's requested current work done, or automatic publication would rely on that status.
- **Input.** Original saved message id, current Goals/Rules, exact target repo/commit or diff hash, the named test/check command, an existing report path and its hash, and any source-bound review note required by the current Rules.
- **Output.** Checked update of that line in Goals plus an appended Log entry linking the original message, actual invocation, result and report. A failed check leaves the work open and returns the full close-refusal text.
- **Code.** Proposed `pi-streams/checks/state.py::check_close`, `engine/state.py::close_current_work`; expose through `engine/cli.py`. Reuse the existing controlled publication path and call the same checker there. There is no new native tool name or Prime close API.
- **Stock integration.** The agent can invoke the pi-stack CLI through existing tools, or a user can invoke it directly. `agent_end`, `turn_end`, `prompt_and_wait` success and `isStreaming:false` do not invoke a native closure.
- **Computed checks.** Read the original Log/history entry. Check its id/text hash, target existence and identity, unchanged current Goals/Rules, exact report bytes, actual test invocation and exit/result, and required review references. Do not take a test name or a claimed green result as execution evidence. Require every saved user message to remain represented as current work or have an explicit done/stopped/informational Log entry; unrelated Log rotation cannot erase it.
- **Failure and repeat.** Run checks outside the short file lock, then reacquire it and compare the relevant text/target before updating. Changed source/target, missing output, checker error or timeout writes no done status. Duplicate identical close commands return the prior checked result. Different evidence requires a new check. The checker does not decide that a wrong experiment answers the original question.
- **Bypass.** Direct STATE edits, other tools, direct Git actions and semantic errors in the criterion. The publication check can catch missing computed evidence on its own path; it cannot forbid all shell publication or validate every natural-language interpretation.

### Common failure behaviour

Socket framing validates protocol 7/schema 30, response id, command and boolean success. It handles events before replies. No command is automatically retried after an uncertain send. A caller can set an explicit command timeout; this document introduces no default deadline or resource cap. A timeout does not prove that native work stopped.

File writes use a same-directory temp file, flush/fsync, atomic rename, parent-directory sync and readback. History overflow is written before STATE is shortened. A local save failure prevents a saved acknowledgement. Do not hold an all-stream lock while awaiting the model or compaction; use short existing per-stream locks to merge entries and revalidate before sending. Losing a connection releases its native pause. No hook claims the pause survives a restart.

## 4 Prompts

These are all new fixed text templates. Names describe their purpose. Rendering is one pass. Identifiers are validated. Free text uses JSON strings, including escaped newlines and delimiters, and is never reparsed as template code. `agents_text_json` and `state_text_json` contain the exact current file bytes as UTF-8 JSON strings. Native base/tool/system prompts remain stock and are not replaced by this document.

### Send-message text

Used by the fresh-STATE hook for every pi-stack model-directed message. `body_text_json` is the original user text or the complete applicable wake/dump/resume body below. Command-only operations such as `compact` do not get wrapped as user text.

```text
pi-stack stream {{stream_id}}, session {{session_id}}, message {{message_id}}.
Read the current role and state supplied below. These are the only project-state files automatically included by pi-stack for this message.
AGENTS.md, SHA-256 {{agents_sha256}}, exact content as JSON:
{{agents_text_json}}
STATE.md, SHA-256 {{state_sha256}}, exact content as JSON:
{{state_text_json}}
Message body as JSON:
{{body_text_json}}
Keep the original request separate from your plan. Use Goals and Rules for current work. Open history only when the task needs it. Saving or delivering this message does not mean you applied it or completed its requested work. Record your response to the original message in STATE through the pi-stack command.
```

This guarantees what pi-stack sent, not that the model reread the files before every internal tool call. Stock automatic project-context discovery is separate and is not advertised as a configurable arbitrary-file callback.

### Saved-message text

Returned to the caller only after the local message and current-work line are written/read back. It is not injected into the model and is not Z5's applied acknowledgement.

```text
{{stream_id}}:: Saved message {{message_id}} before sending to Prime. Sending status is {{sending_status}}. This is not confirmation that the coordinator applied it or that its requested work is done.
```

Allowed `sending_status` text is `not sent`, `sent, waiting for result`, `Prime replied`, or `unknown after connection loss`. The code must not translate an unknown send into a successful application acknowledgement.

### Stall-wake text

The tick supplies this as the body of send-message text only after the stall-wake and reject-stale-command hooks pass.

```text
The tick found unfinished current work and no recorded human wait, running worker, or unresolved earlier send that explains this idle session.
Read the supplied AGENTS.md and STATE.md. Continue only the current work authorized by Goals and Rules. Preserve unrelated prohibitions. If a real dependency or human decision prevents progress, write its exact release condition in Goals and report it by the original message.
Do not treat another turn, an updated plan, or idle status as completion. Use the pi-stack close command only with the actual check and result. Do not invent an approval gate or a resource cap. Use the task method requested by the user; do not claim a Pi-specific slash command ran on Prime.
```

### DCR-dump text

Sent as one ordinary wrapped message before native compaction. The agent may interpret and propose updates; pi-stack still validates and writes them.

```text
Prepare this session for DCR. Read the supplied AGENTS.md and STATE.md.
Update the finite current work under Goals and the rulings still in force under Rules through the pi-stack command. Preserve every unresolved original message and its exact history reference. Do not mark work done to shorten context and do not retire a rule without an applicable source.
Add one Log entry describing completed work, unresolved uncertainty, running workers and actual report paths needed after compaction. Do not launch new external work for this dump. Finish after submitting that entry. pi-stack will check whether the session is idle before requesting compaction.
```

### Compact instructions

Passed verbatim as native `compact.customInstructions`, never sent as `/compact` into a paused queue.

```text
Preserve the original user requests separately from plans and interpretations. Preserve unfinished work, current rulings, human waits, running worker identities, uncertain external work and exact existing report paths. Keep native tool-call and result relationships complete. STATE.md remains the current Goals, Rules and Log; the summary must not cancel or complete its work. Do not infer success from missing error text. Return the native summary. pi-stack decides whether to send a resume.
```

### DCR-resume text

Used once as a wrapped body only after the native compaction reply and saved entry pass readback and no newer message/stop takes precedence. If saved user input is waiting, deliver that instead of adding a separate old-goal resume.

```text
DCR compacted session {{session_id}} at saved native entry {{entry_id}}.
First read the supplied AGENTS.md and STATE.md. Goals and Rules are current; the compacted conversation may contain older instructions. Continue the finite current work only if it is still authorized. Open the named history entries or reports when needed.
Do not repeat work whose external result is unknown. Report the uncertainty and inspect the actual work before proposing a retry. Running workers still belong to their existing parent; this resume does not move them. Use the task method requested by the user and the pi-stack closing check for any proposed done status.
```

### Stale-command text

Returned to the caller when the reject-stale-command hook refuses an unsent automatic action. It is not a command to a parked or stopped model.

```text
{{stream_id}}:: Did not send {{command_name}}. Its session or Goals/Rules changed after it was prepared, or current work is waiting/stopped. Read current STATE.md before preparing another automatic command. A possibly sent command must be checked, not resent under another id.
```

### Close-refusal text

Returned by the close command without marking current work done.

```text
{{stream_id}}:: Did not mark work for message {{message_id}} done. Check failure as JSON:
{{failure_json}}
The work remains open. Correct or report the source, target, actual check, report, or review problem. Finishing this command is not completion of the original request.
```

### AGENTS.md role text

This is the complete new stream-role text. `role` is coordinator or worker with its assigned task. It is written by pi-stack's stream template and remains short enough to be read with STATE. It is not an extra automatically loaded file.

```text
You are the {{role}} for stream {{stream_id}}.

Use AGENTS.md and STATE.md for current project instructions. Goals contains the single mutable North Star and the finite current work. Rules contains the rulings still in force. Log contains recent completed work, messages and failures; history holds older entries. Read history and reports only when needed. Do not create another current-work file.

Keep the original user request separate from your interpretation and plan. Record how each incoming message changes current work, rules, or a real wait. A saved message, a delivered steer, an updated plan and a finished Prime run are not proof that the work is done.

Use the named native or known-good path when requested. Report the actual invocation if you use another path. Choose checks that answer the original question and record the result, including uncertainty. A checker can agree with the wrong interpretation. Keep judgement and review findings in the existing files.

Use the pi-stack command to update STATE and propose done status with the original message, exact target, actual check and report. Respect later stops and unrelated standing prohibitions. Do not invent resource caps or new approval gates.

A fresh STATE message from pi-stack does not mean every internal Prime action is intercepted. Do not claim that native tools were fenced or that workers moved to another parent. Wait for existing workers rather than replacing them to hide missing results. Report unsupported operations plainly. Do not change provider or model without explicit user authorization.
```

No automatic login, failure-repair or F-DCR prompt is added. Those are outside this Z23 version, not silently handled by another template.

## 5 Artifact storage

`<stream>` is the existing stream directory. Each worker that uses these hooks has its own STATE path and task worktree; it does not write the coordinator's STATE. The coordinator records received worker results through the same local Log writer. No shared generated task files are introduced.

| Path | Exact format and writer | Reader and timing | Rotation and retention |
|---|---|---|---|
| `<stream>/AGENTS.md` | The full role text above, with validated role/stream values. pi-stack's stream template writes it; explicit role changes replace it. | The fresh-STATE hook reads it before every pi-stack model-directed send. The agent reads the supplied text. | No automatic per-failure additions. Explicit template changes are reviewable code changes. |
| `<stream>/STATE.md` | UTF-8 Markdown with exactly Goals, Rules, Log in that order. The pi-stack file-writing functions are the intended writer. Human/agent judgement is submitted through them; a direct editor can bypass that contract. | Every pi-stack send includes it. The tick and close checker read the same file, not a second current copy. | Goals and Rules rewritten in place. Only Log is capped at 30 entries, as Z15 requires. Current unfinished messages and active Rules never expire with recency. |
| `<stream>/history/<UTC ts>-<slug>.md` | One complete older Log entry per file, with the same heading/body bytes. Example `<UTC ts>-incoming-message-<command-uuid>.md`. Retired Rules use `<UTC ts>-rule-retired-<slug>.md`. pi-stack writes overflow before shortening Log. | The checker reads original messages/results on demand; humans/agents open specific entries when needed. It is not automatically loaded. | No automatic expiry. Repeated rotation with the same entry id must compare content, not overwrite different bytes. Current Rules move here only with a named superseding source. |
| Existing Prime session files and worker storage | Stock format and paths, unchanged. Prime alone writes them. pi-stack may read the exact owned session path for compaction/result verification. | Existing Prime reload/context/fork; pi-stack readback of entries named by native APIs. | Stock retention remains stock. This design never edits the transcript or deletes the old parent to manufacture a clean result. |
| Existing pi-stack session/tick files and locks | Existing paths, such as `threads.tsv`, `log/tick-state.json`, and the Git-directory stream lock. Reuse their existing purposes. They do not become another task store or a source of truth for Goals/Rules. | Existing coordinator lookup, tick delivery and short cooperating file operations. | Existing lifecycle. Add no new task database, ownership counter, failure-marker tree or phase files. |
| Reports already created by the task | Existing task-owned text reports and test outputs, addressed by their real path/hash. The task creates them; the close hook reads and checks them without inventing a new evidence directory. | Source-bound checks and review when proposing done status. | Retain referenced reports until no current work/review needs them. A moved/missing report fails the check. No automatic report copying or generic filesystem scan is proposed. |

The data added to these files are ordinary message/command fields, not new named record types. Every id used for a local incoming message is the caller's UUID and outgoing command id. It is never presented as Prime's message id.

### STATE.md schema

```markdown
## Goals
### North Star
source: <original message id or human ruling>
<one mutable human-authorized objective>

### Current objective
session: <full durable coordinator session id>
drive: <on|off|waiting>
<finite immediate objective>

- message: <uuid>; source: <Log entry id or history path>; status: <unread|open|waiting|done|stopped|informational>
  request: <original requested outcome, kept separate from interpretation>
  interpretation: <current plan or none>
  check: <named command/expected observation or needs review>
  report: <existing task report path and hash, or none>
  wait: <exact dependency/human release condition or none>

## Rules
- <short ruling>; source: <message id/history path>; applies-to: <current work or stream>

## Log
### <UTC ts> <plain one-line subject>
entry: <uuid>
message: <original message uuid or none>
session: <full durable session id>
<message text, command/reply, completed work, failure or review detail>
```

There is no fourth top-level section. The lines under Current objective are the current work, not a second file or an additional named task system. The incoming-message hook initially adds an unread line rather than inventing an interpretation. After reading the user message, the coordinator proposes its request/interpretation/check or an explicit informational reason. Misclassification remains reviewable against the saved source.

An incoming-message Log entry stores a canonical single-line JSON object inside a `json` fence with `kind:"incoming message"`, `id`, `session`, `sendAs`, `text`, and `sha256`. `sha256` hashes the original UTF-8 text, not its JSON encoding. JSON escaping preserves embedded newlines without creating spurious Log headings. The current-work line and this Log entry are written together in one atomic STATE replacement. That is the local save-before-send guarantee.

A before-send entry contains `kind:"Prime command"`, `id`, `session`, `command`, exact sent text hash, the Goals/Rules hash used for its check, and `result:"unknown until reply saved"`. It is committed before the socket write. A reply entry contains `kind:"Prime reply"`, the same command id, native success/error/data and referenced queried messages/reports. A local close entry contains `kind:"checked current work"`, message id, exact target hash, actual command and exit/result, report path/hash, current Goals/Rules hash and reviewer reference when required. Repeated identical entries use the same stored id and do not append duplicates.

This avoids a second send journal but has a cost. Startup and checks may need to scan Log plus history for prior commands and replies. That is acceptable for this candidate and is measured before adding an index. A parsed in-memory lookup is disposable, not another writable authority. A source id with no reply is not guessed to be ready for replay.

A ZF steer is an incoming-message Log entry before dispatch, then reaches history by normal rotation. A new ruling updates Rules and appends Log; retiring one writes the original text to the required rule-retired history filename. Goals and Rules are never chronological append dumps. Only Log entries rotate. Unknown/unread/open/waiting current work stays under Goals beyond 30 unrelated entries.

The client reads the exact current text, not a summary it independently maintains. Native Prime may also discover its normal project context. Stock has no demonstrated switch that makes all its internal context consist of exactly these two arbitrary files on every request. The statement here concerns pi-stack's automatically supplied project-state files; it is not a claim that native prompts, skill inventory or tool results disappear.

Original messages, native replies and session material are runtime data. Do not blanket-stage STATE/history or native files into Git. Code/templates and deliberately selected small reviewed reports may be published by an explicitly checked path. Task outputs, credentials, binary data and runtime roots are never imported merely to satisfy a closing check. This text-only candidate rejects unsupported attachments instead of storing lossy references.

## 6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure)

### An ask

1. The caller keeps a UUID with its text until pi-stack reports saved. The save-incoming-message hook atomically writes the exact incoming text to Log and an unread current-work line to Goals. Native Prime is not involved in that save.
2. The fresh-STATE hook reads the two files, checks the intended current session and sends the full wrapped message using `prompt_and_wait`. It records before writing to the socket. A direct TUI message would bypass this path and is not silently claimed covered.
3. The coordinator reads the original source and proposes how it changes current work and Rules. Judgement remains visible in STATE. pi-stack does not turn a plan update into done status.
4. A connected reply is saved, including a native error even if there is no assistant row. A disconnect instead leaves the send unknown. Neither response alone closes the request.
5. The task runs its named method and produces a real report in its owned worktree. The close hook executes/checks the applicable computed checks, compares source/target/current instructions, and updates the corresponding Goals line only if they pass. A reviewer still asks whether the chosen check answers the original question.
6. A done/stopped/informational line can leave current work only with its explicit linked Log entry. Another unresolved message remains in Goals when the related Log source rotates. Finishing finite current work switches drive off; it does not complete the North Star.

### A stall and DCR

1. Tick queries stock state and checks current Goals/Rules. A human wait or healthy running worker gives no wake. If work is genuinely eligible, it records and sends one wrapped stall-wake message. Concurrent ticks find the same pending wake and do not send a duplicate.
2. A newer stop arrives before that wake is sent. It is saved first. The changed Goals/Rules cause reject-stale-command to refuse the old wake. If Prime is already acting on an earlier message, this version cannot intercept its next arbitrary tool call. That ordinary-path gap is explicit.
3. Context crosses the chosen threshold during a long run. pi-stack records that compaction is needed but does not abort the active tool. It cannot stop precisely at that provider boundary. After the run, it performs the dump and idle/pause/recheck sequence before calling direct `compact`.
4. The client saves the reply and verifies the native compaction entry on disk. New user messages saved during compaction take precedence over a stale automatic resume. If none waits and work is still authorized, it sends one wrapped DCR-resume message. A duplicate/unknown compact attempt is inspected, not repeated blindly.

### A failure

If a local incoming-message save fails, nothing is sent and nothing is acknowledged as saved. If a native request fails while the client is connected, the reply hook saves and reports that failure without claiming task completion. If the client loses the result, current work stays open and the result is unknown. Recovery uses the actual session and task outputs, not an automatic duplicate request. Login and rare environmental recovery are excluded as specified below.

## 7 Risks and notes

The main result is a boundary, not an excuse to add a framework. The stock commands are enough for useful pi-stack sending and checking hooks. They do not provide an external callback before every native model/tool action. If the merged design requires that universal guarantee, this candidate does not meet it under Z22. Giving the client functions hook names does not change the scope.

The following are ordinary-path risks.

- Fresh STATE means fresh bytes in each pi-stack message, not fresh context before every internal Prime turn. The latter remains open. Native project-context reload and the existing native memory features must not be relabelled as a Z15 STATE loader without a captured-provider-context test.
- Reject-stale-command covers pi-stack actions only. An agent can still edit STATE, run tools, change another checkout or publish directly. File hashes are comparisons, not process fencing. Separate worker worktrees remove shared mutation where possible.
- Native input pause does not stop already active work or every external producer. Idle status followed by compact can race a direct client. Controlled clients must use the same pi-stack path for its cooperative guarantee to apply. This is not permission to stop or modify existing sessions during design work.
- Prime `compact` can run automatic refinement and native goal continuation. A deployment that uses only Z15 project-state files must explicitly review the stock global `harnessRefinements` setting and its independent `autoRefine` settings. `pa-core/src/settings/interactive_settings.rs:13-23` reads `harnessRefinements` globally; `session_engine/refinement_gate.rs:1-17` and `refine.rs:499-571` apply it. Do not silently import an additional writable memory authority or change the live user's settings. Whether to disable it for a future owned deployment remains an explicit configuration question.
- `set_auto_compaction` can separate native overflow behaviour from the client threshold policy, but no option is selected here. Turning native automatic compaction off may cause a long run to reach context limits before the tick can compact. Leaving it on means not all compactions pass this client hook. The implementation must report which behaviour was explicitly configured.
- Source/target/report checks can be computed. Deciding the right outcome, whether an alternate implementation is valid, and whether a checker has the wrong sign still needs original-source review. Record uncertainty in the existing files, not a new vocabulary of acceptance states.
- Full incoming text and replies in the latest 30 Log entries may add substantial context. This candidate does not add a hidden token/disk cap or silently truncate original input. Measure actual provider context and decide whether a different use of history is needed. The count of 30 is Z15's Log rule, not a new resource budget.
- The write/dispatch gap cannot be made atomic by an external client. Unknown sends remain unknown. Scanning history for prior commands is simpler than another store, but can become expensive; measure it before adding any index.
- Prime's queued input and semantic state remain Prime-owned. Do not clear/replay native internal queues from preview strings, and do not invent interactive answer support that stock lacks. A human answer is an ordinary saved source message unless a future separately specified correlated-question API is available.

### Not handled

Login/authentication, quota/provider outages, disk/resource emergencies after a native send, arbitrary external-job rollback, worker transfer to a different parent and automatic F-DCR are not implemented here. Today stock Prime reports failures through command results/live events and some transcript rows; pi-stack can save the responses it receives and otherwise reports unknown. Human repair or a deliberate manual session decision is required. No hook logs in, copies credentials, switches provider/model, deletes a failed original, duplicates a worker or repairs the environment. These exclusions keep the Z23 candidate focused; they do not erase the four-gap table or the ordinary-path freshness/tool limits.

### Open questions

- Is including current STATE before every pi-stack message sufficient, or is rereading before every native provider request a requirement?
- Is rejecting stale pi-stack commands sufficient, or must every native mutation be prevented after a new stop?
- Which clients must use the common send path, and is direct TUI/native internal input an accepted bypass?
- Should a future deployment use native automatic compaction, the controlled idle threshold path, or an explicitly tested combination?
- Are Log/history sufficient for the saved text/replies at measured scale, or does evidence justify another file? No additional file is selected now.

These questions have no applied defaults. The document makes concrete choices for the candidate, not product decisions for pi-stack.

## 8 Implementation plan

This is a proposed stack of pi-stack commits only. No Prime changes, patched binary, installed-dist edit or native hook registration is part of the plan. Each commit includes its tests. Existing functions must get a failing old-behaviour test first; new-functionality tests are labelled as such. No implementation is claimed in this docs-only follow-up.

| Proposed commit | Change in pi-stack | Tests and old-code failure first |
|---|---|---|
| `state: preserve incoming text and current work in Z15 files` | Add the small `engine/state.py` parser/writer. Exactly three top-level sections. Preserve current work beyond Log rotation and write history before shortening STATE. Use the existing per-stream lock with correct linked-worktree Git-directory resolution. | New-feature tests for exact UTF-8/JSON message round-trip, duplicate id versus equal text/new id, embedded heading text, failure before save, 31 unrelated Log entries, retired ruling names, two concurrent writers and repeated rotation after interruption. Assert final bytes and no premature saved response. |
| `prime: save text before sending and save the connected reply` | Add `engine/prime.py` using the track-2 public transport. Expose a pi-stack text-send command. Record the exact source and possible send before the socket write. Use awaited native prompt with the requested lane. Keep unknown sends from auto-retry. | Socket fixture reads STATE before accepting the command and finds the exact original message. Storage failure causes zero commands. Interleaved event/response correlation, same-id conflicts, native refusal without assistant row, lost acknowledgement and duplicate client restart all get literal expected outcomes. Current thin CLI has no pre-send save, so the before-send assertion fails first on that path. |
| `prime: include current AGENTS and STATE on each managed send` | Render the exact send-message text and hashes. Recheck target session/Goals/Rules before writing the command. No context cache or native per-turn callback is advertised. | Capture the outgoing/provider fixture context after changing STATE. All managed user, wake and resume messages carry current bytes. A missing file stops the call. Explicit negative test shows an internal multi-turn native run has no new automatic file-read hook. Do not pass this test by merely counting tokens. |
| `tick: wake only current unfinished work` | Integrate native status/queue queries and current files into the existing tick. Reuse recorded pending commands for duplicate prevention. Add reject-stale-command to every automatic send. | Idle current work wakes once. Human wait, healthy worker, current work done/stopped, unknown prior send and stale coordinator do not. Race two ticks and a later user stop before socket write. Existing activity-only/reinject behaviour must fail these effect assertions before the fix. Test records actual command bodies and zero stale sends. |
| `prime: compact only at the observed idle threshold` | Add dump/pause/recheck/direct compact/readback/resume using existing stock commands. Require an explicitly chosen threshold and report native automatic-compaction configuration. Save new user input without adding a stale resume. | Native wire fixtures for busy tool, user bash, child, nonempty queue, new input during compaction, successful reply with missing disk entry, summary error, lost compact reply and duplicate tick. Assert no busy compact command, no paused-queue `/compact`, and no automatic resume after unknown/failed compaction. Old unchecked compact would fail the safety tests. Real model-backed compaction remains a later authorized test, not an offline claim. |
| `checks: verify computed completion before updating Goals` | Add `pi-streams/checks/state.py` and the close command. Check saved source, actual target/invocation/report and current text before the update. Call the same check from controlled publication. Keep semantic review in Log/history. | Known wrong source/target, nonexecuted check, changed report, newer stop during check, omitted saved message and missing review all fail. Valid alternate implementation with truthful invocation can pass. Wrong-sign and smallest-working/failing cases require an actual source-bound oracle; do not claim a schema alone detects them. Direct STATE/shell edits are tested as explicit bypasses, not magically blocked. |
| `templates: install the short role and descriptive prompt text` | Add the role template and fixed text above. Doctor reports stock build/protocol, supplied context scope, unsupported all-tool guard, active native automatic policies and available commands without changing them silently. No additional automatically loaded project files. | Temporary-home installer fixtures, exact prompt bytes, no retired artifact names, no invented hook/prompt codes, no new default budgets, and no silent provider/model change. A deployment with unreviewed conflicting continuation settings reports the question instead of enabling another driver. |
| `verification: check stock boundaries without patching Prime` | Add rerunnable offline tests and an optional future isolated stock control check. Keep code/templates/small reports in Git, runtime roots and output data outside it. | Run the existing 105-test stream baseline and focused transport/state tests. With separate authorization, run a stock isolated server for control operations and captured failures; future successful inference/compaction tests require its own authorized authentication. Include direct-client bypass and missed-event demonstrations. An all-internal-turn freshness or all-tool claim must fail qualification unless actual stock evidence changes. |

The source audit for this design also considered native project reload, native memory APIs, executable skills and stock shell wrapping. None should be promoted to a broader guarantee without its exact trigger and actual captured context/action test. Stock-only is a constraint to describe honestly, not a reason to relabel a partial client check as a native guarantee.

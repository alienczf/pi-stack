# Pi-streams must-fix catalog

| # | Fix | Symptom with corpus rows | LAYER | Blast radius | ZF-call? | Order |
|---|---|---|---|---|---|---|
| 1 | Make the tick drive unfinished work, not just forward edges. | ZF supplies the next turn and progress request. F1, rows 3, 26, 34, 39, 40, 51, 55, 59, 60, 64. C rank 1. | LAYER 3 | **Med.** Tick, a stream-level drive switch, status, doctor, timer health. | No. Z1 decides. | S4, after safe targeting and maintenance. |
| 2 | Break circular recovery with all five G5 classes. | Reset or repaired auth still needs a human "continue". F7, rows 13, 17, 23-25, 47, 52-53, 63, 67. C rank 2. | LAYER 3 | **Med.** Error metadata, tick parking and probes, lane recovery. | No. G5 adopts all five. | S5. |
| 3 | At a tick-observed 150k, dump, compact, and resume the same coordinator. | Directly driven coordinators grow through long turns. F6, rows 11, 16, 32, 69, 71. | LAYER 3 | **Med.** Tick maintenance phases, CLI command adapter, small pi-web idle-compaction boundary. No native Pi core change planned. | No. Z3 supersedes D2 and G4. | S3. |
| 4 | Delete numeric-cap interviews and budget or guard defaults. | Invented spend and host guards persist and kill work. F3, rows 10, 44-45. Issue #33, D1. | LAYER 2 | **Low.** Kickoff, generated instructions, design examples, regression checks. | No. D1 decides. | S1. |
| 5 | Resolve exact evidence after archive relocation. | A checker cannot open a retired session's former live path. Corpus row 37, A rank 2. G16 clarifies the reference. | LAYER 3 | **Low to med.** One session-evidence adapter and archive-boundary tests. | No. Preserve bytes, change the locator. | S2. |
| 6 | Keep STATE current and put checkpoint history outside the pickup view. | 654 preserved a 10 MB STATE and reimported obsolete checkpoints. F6, rows 11, 16, 32, 71. A rank 3. | LAYER 1 | **Low.** State and context templates, a narrow structural check, explicit migration recipe. | No. | S1. |
| 7 | Acknowledge a steer only after the coordinator consumes and applies it. | Queued, unsent, and transport-accepted steers are reported as delivered. F8, rows 21, 35, 72-73. | LAYER 3 | **Med.** CLI, tick delivery receipts, coordinator acknowledgement, bot relay. | No. Z5 decides. | S2, before autonomous wakes. |
| 8 | Use one explicitly designated coordinator ID everywhere. | The tick observes an old fcf coordinator and can adopt an unrelated session. Rows 51-53, 55, 72. Issue #36. | LAYER 3 | **Low to med.** Registry lifecycle, tick targeting, status and doctor. | No. Never guess from the newest same-directory session. | S2. |
| 9 | Stop restarting Twingate on every remote CLI call. | Repeated calls cause SSH banner timeouts. G15, outside the 75-row corpus. | LAYER 3 | **Low.** Grok Bot box wrappers, not pi-stack's host CLI. | No. G15 decides. | External prerequisite to real-stream checks. |
| 10 | Remove template defaults that override goals, stops, or the requested acceptance. | "Continue on the default" can escape AUTONOMY. Mandatory new check scripts become paperwork gates. Rows 37, 43, 69, 75. B rank 3. | LAYER 4 | **Low.** Coordinator and kickoff text, dispatch ratification check, tests. | No. Keep explicit gates. | S1. |
| 11 | Stop routine rotation and make explicit rotation refuse an unsafe boundary. | Size and age rotations change identity and require manual queue transfer. Rows 16, 32, 37, 71-72. | LAYER 3 | **Low to med.** Wake selection, manual rotation, checkpoint precondition, tests. | No. Z3 selects same-session maintenance. | S2, before S3 and S4. |
| 12 | Review current state and rules during the existing dump step. | STATE, DECISIONS, TODO, and rules accumulate obsolete material. D7, issue #36, corpus cross-check §3. | LAYER 3 | **Low.** Coalesce review into item 3, current/history file layout and instructions. | No. No independent-review policy. | S3. |
| 13 | Stop the tick auto-staging worker binaries and data. | Scratch DLLs and packages enter the stream repository. F11, row 29. | LAYER 3 | **Low.** Automatic staging policy, ignore template, Git fixture tests. | No. | S1. |
| 14 | Bind each handover to its session, not a reusable role name. | A successor can close using its predecessor's handover. Source-derived companion to row 37, not a proved corpus incident. | LAYER 1 | **Low.** Handover paths, brief rendering, close checks, stream skill. | No. | S1. |
| 15 | Publish registry snapshots atomically and repair interrupted registration. | Status can read a truncated registry, and create retry can leave the stream unindexed. Source-derived companion to issue #36's drift. | LAYER 3 | **Low.** Existing file writers, create retry, persistence tests. | No. | S1, before identity and runtime operations. |

## Scope and evidence

This is an implementation catalog, not an implementation. It incorporates Z1-Z5 from the 09:22 SGT relay and G16's corpus-reference clarification in `03-decisions.md`. The relay in `00-brief-verbatim.md`, section t211u, is labelled a paraphrase. The earlier 4,482-character brief gap remains unknown.

**Z3 replaces the original 252k requirement.** There is no proposed 252k request-boundary trigger, model-window override, inflated reserve, or new native request hook in this catalog. The selected policy is tick-driven maintenance at an observed context of at least 150,000 tokens. It is not a hard per-request token ceiling.

All source citations refer to pi-stack `3acf0f01e6084a317b89cef3a86f4781e60877cf` unless a dependency or stream root is named. In item details, `engine/`, `templates/`, and `tests/` are under `pi-streams/`. Bare engine filenames such as `tick.py` mean `pi-streams/engine/tick.py`. `E/` means `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`. Row numbers refer to `E/context/stall-corpus-2026-10-22.md`, not GitHub issues. A, B, and C mean the dated interrogation reports under `E/context/interrogations/`. Research means `E/context/research/deep-research-2026-10-23.md`. `Q/` means `/home/alphalab/Projects/alphalab/streams/qslite-654-datapull/` for the stream-owned incident checker and evidence.

Installed dependency observations are separate from that Git pin. `W/` means `/home/alphalab/.local/share/pi-node/node-v22.23.1-linux-x64/lib/node_modules/@jmfederico/pi-web/`, version `1.202607.3`. `N/` means its `node_modules/@earendil-works/pi-coding-agent/dist/core/`, Pi `0.82.1`. The installed package metadata identifies `jmfederico/pi-web` as the owner. Its source maps identify `src/server/sessions/{sessionCommandService,piSessionService,sessionRoutes,sessionArchiveStore}.ts`. Pin the matching upstream source revision before changing those files. Never edit installed `dist` as the delivery method.

The bar is a small correction or a change that is required regardless of track 3's design. Items 1, 2, 3, and 7 meet the second bar even where their integration crosses repositories. They are not represented as one-line fixes. The remaining items remove concrete contradictory defaults or repair existing boundaries.

Historical claims are not assumed current. A records 654's `STATE.md` at stream commit `c146285` as 10,195,068 bytes and 165,597 lines. This investigation verified that blob size. A later live size-only sample was 15,687 bytes. That does not retroactively remove the recursive-checkpoint defect or prove a generic fix landed.

### Implementation boundaries

Keep one small record for the current stream drive disposition and a few existing tick operations. Do not build the research report's canonical control transaction, ask database, workflow engine, or general authority model.

Use these narrow records only:

- A stream-level drive disposition. It says whether this stream is being driven, its current actionable next step or named wait, and its next observation time. It is not a record per user ask.
- A recovery episode for an affected session or lane. It retains the class, saved continuation reference, external job identity if any, readiness observation, retry time, and notification IDs.
- A current delivery receipt and a current maintenance operation. They correlate transport, application, and dump/compact/resume retries. They do not grade product completion.

Extend existing stream configuration and `log/tick-state.json` under their existing locks. Add only the boundary commands needed to update those records. Protect in-flight recovery, maintenance, and delivery state from generic log cleanup. Keep terminal narrative in existing history. No database, second daemon, cross-repository ownership protocol, or mandatory per-ask ledger is included.

## Per-item detail

### 1. Make the tick drive the stream

**Symptom and evidence.** C rank 1 traces F1 polling in rows 26, 39, 40, 51, 55, 59, 60, and 64. Rows 3 and 34 also show unfinished work waiting for an outer nudge. A timely report and an actual computation are different outcomes. This fix must demonstrate both where requested.

**Root cause.** `pi-streams/engine/tick.py:317-339` observes worker edges but not the coordinator's obligation to take another turn. `:435-445` returns when `pending` is empty and clears it after a prompt call. `TickState` at `:67-74` has no continuation due time. The timer already runs every five minutes at `systemd/pi-streams-tick.timer:4-6`. Installing another timer does not fix this predicate.

**Fix.** Keep the existing timer. When a ratified stream is explicitly being driven, reconcile its current unfinished work on every tick. An idle coordinator with runnable work gets one coalesced prompt to take the next authorized action. Do not wait for another worker edge. Keep driving after a reporting-only turn if execution remains runnable. A busy coordinator gets no growing queue of routine "continue" messages. Do not wait for a complete per-ask ledger before delivering this Z1 fix.

Use one explicit stream-level driven/paused switch, not inferred prose or `active` registry counts. Ratification and an authorized start arm driving without another maintenance interview. A missing switch during migration is visibly unknown and stays paused until existing intent is mapped. For an explicitly driven stream, a missing turn-end disposition triggers one reconciliation of current STATE/TODO rather than another silent stop. It is not a replay of the old action.

A named child wait retains its observed owner and a recheck. A human gate or explicit stop suspends execution wakes. Done disables driving. The coordinator updates the current disposition at turn end. Reuse `_working()` so streaming, bash, compaction, and queued input all count as busy. Inspect `pendingAsk` before a routine prompt. The installed prompt path voids open asks, so a heartbeat must never serve as an answer to a human question. Direct native stop or cancellation invalidates the current automatic-admission generation at the receiving session adapter before it completes. Every automatic wake, recovery probe, and maintenance RESUME carries that generation. The receiver rejects a stale generation even if the sender checked driving before the stop. This shared prerequisite lands in S2 before S3 can resume anything. Explicit new user prompting after a stop remains allowed. Natural-language classification remains the coordinator's job. Do not claim the harness understands every arbitrary stop sentence.

Observe independent workers separately so one unavailable row cannot skip the coordinator's continuation pass. `run()` currently wraps observation, subscriptions, and wake together at `tick.py:217-234`. Isolate observation failures, retain their errors, and still run the independent checks. A failed observation is unknown, not evidence that an existing writer died. A failed write must not authorize an unrecorded dispatch. Bound CLI/network/Git waits at their I/O boundaries and avoid holding every stream's lock through remote calls or pushes. Reacquire the relevant lock and revalidate the drive switch and destination before dispatch. These are control-call deadlines, not D1 resource budgets or authority to kill remote jobs. A sender-side recheck alone does not close the stop-versus-prompt race. Installed pi-web can reopen a stopped runtime for a later prompt at `W/dist/server/sessions/piSessionService.js:1793-1804,1992-2035,2064-2081`. Admission must compare the generation on the receiving side.

Keep progress notifications tied to an explicit request or a new blocker, not to every tick. Row 39's half-hour march is a stream-specific request, not a universal deadline or reporting cadence. Report the current next action, actual owner or blocker, and requested findings. Do not call transcript activity progress.

**Layer.** LAYER 3 owns due wake decisions and observation isolation. LAYER 1 gives the disposition one unambiguous home. LAYER 2 tests the transitions, but cannot wake a deployed coordinator. Rules or skills cannot supply a clock after the model has stopped. No stronger static layer can observe the live owner and dispatch a due turn.

**Blast radius.** Medium. `engine/tick.py`, `project.py`, `cli.py`, `doctor.py`, the current-state template, and tick tests. Also correct `doctor.py:179-195`, which treats any fresh stream tick-state as sufficient for the whole fleet. Check each stream's completed pass and the actual timer/service state. Keep tick health distinct from useful work.

**Verification.** Add a baseline regression to `test_tick.py` with an idle, driven coordinator, unfinished next action, no workers, no subscription change, and empty `pending`. Baseline sends zero prompts. Candidate advances a tiny disposable two-step task without a ZF message between steps. Repeat ticks while busy and assert no duplicate queued continuation. Test stopped, done, unratified, pending-human-gate, and healthy child-wait cases. Pause an automatic delivery after its last sender-side check, complete native stop, then release that stale request. It must produce zero task effects. A fresh explicit user prompt must still work. Inject one inaccessible worker and prove another ready lane still progresses. One fresh stream must not hide another stale or failed stream in `test_doctor.py`.

**Dependencies.** Items 7, 8, 10, and 11 precede autonomous driving. Item 3 takes priority over ordinary continuation while maintenance is pending. Item 2 handles provider and tool recovery separately.

### 2. Break circular recovery with all five G5 classes

**Symptom and evidence.** F7 rows 13, 17, 23, 24, 25, 47, 52, 53, 63, and 67. Rows 25 and 53 specifically need an external "reset, continue" after availability returns. C rank 2 reproduces the circularity. Research Q9 supports preserving existing provider error metadata rather than adding Codex app-server solely to poll it.

**Root cause.** `tick.py:347-367` calls every assistant error an outage and uses `waiting_quota` for workers. It clears the outage only after a later non-error assistant entry. `:435-440` suppresses prompts to an out coordinator. `sessionlog.py:13-21,45-56` exposes only the last assistant message. Existing `test_tick_outage.py:63-118,135-187` injects a human Continue and a successful reply before expecting recovery. Tool logout inside a normal assistant turn and the tick's own ENOSPC are different paths and can be missed.

**Fix.** G5 is adopted. Replace the harness's stop-and-report default with these transitions. Keep the original provider and model.

| Class | Park and alert | Release and retry |
|---|---|---|
| Codex usage limit | Retain reset time, affected continuation, and job identity. | At the reset time, permit one saved-step retry without requiring a prior successful assistant reply. Persist that attempt before dispatch. Reconcile uncertain external effects first. If it fails again, re-park until new valid retry/reset evidence. A restart must not replenish the same attempt. Missing reset metadata is an explicit unknown, not permission for an immediate retry. |
| Expired Codex login | Alert once. Never inspect, copy, refresh, or modify credentials. | Resume after a supported real sign-in/readiness signal or an explicit "auth fixed" instruction. File mtime is not readiness. |
| Tool login expiry | Park only the affected lane and name the relevant non-secret login check. | When that check passes, query any already-submitted job before retrying. Independent authorized work stays eligible. |
| Full disk | Report the failed path and owner when known. Do not clean up or add caps. | An off-host observer alerts even if the host cannot write ALERTS. Resume after the required write probe succeeds. |
| Other model errors | Keep their actual error label, not `waiting_quota`. | Resume only on a relevant recovery observation or authorized retry. Do not blindly retry unknown permanent failures. |

Across all five, never switch provider or model, never re-run an uncertain job, and never resume cancelled or gated work. Recovery resumes reconciliation of the saved step, not replay of an arbitrary shell command. If an external job has no safe status query or idempotency, leave that effect uncertain and report it instead of duplicating it.

Require item 7's receiving-side generation check for recovery admission as well. A stop after readiness was checked still prevents the stale retry from running.

Retain allowlisted provider, error class, retry/reset time, observation time, and affected session. Do not persist raw headers, account identifiers, or credentials. A small adapter can retain reset metadata already parsed by the installed provider. Text parsing is an explicit fallback, not an invented account-readiness API.

**Alert route, Z4.** Alerts and waits go through the existing Grok Bot's off-host deployment to ZF's Slack DM only. The exact message format is `<stream-id>:: <message>`. Do not send to BossOps. Retain an episode ID until the bot records successful Slack delivery. One blocker episode gets one blocker notification and at most one recovery notification. Unchanged waits produce no recurring DM. Transport retries use the same episode and delivery identity. A failed attempt is not a delivered alert. If Slack may have accepted a message but its reply was lost, reconcile the remote message identity before resending. Do not claim that a local episode ID alone prevents duplicate Slack messages.

The bot observes both typed ALERTS and failure or absence of a completed tick pass. This keeps full-disk or dead-tick notification independent of host writes and the exhausted Codex pool. Do not require another model call to send the DM. Resolve ZF's Slack destination through the deployment's existing identity binding, not a guessed username or a new credential flow.

**Layer.** LAYER 3 owns error classification, independent recovery probes, and the off-host notification routine. LAYER 1 stores stable episode and job identities. LAYER 2 proves retries and suppression, but cannot observe restored login or disk writes in deployment. A skill telling the failed coordinator to alert cannot work when that coordinator cannot run.

**Blast radius.** Medium. `engine/tick.py`, `sessionlog.py`, error metadata at the provider or pi-web adapter, outage tests, and the bot-side ALERTS/Slack routine. The latter is outside this checkout. Its owning deployment source must be located before implementation. No new monitoring service is proposed.

**Verification.** Leave the last assistant error unchanged. Advance a controlled reset clock or provide only a real-readiness fixture. Candidate issues the due same-provider probe where baseline issues none. Cover all five classes, a tool-auth failure inside an otherwise successful turn, cancellation during an outage, an uncertain submitted job, failed reset retry, and changed error class. For ENOSPC, use a disposable faulting directory or private test filesystem, never fill options-01's host disk. Demonstrate one ZF DM with exact formatting, no BossOps message, no repeated unchanged-wait DM, and at most one recovery DM. Slack delivery tests need the existing authorized deployment route. Local ALERTS bytes alone do not pass.

**Dependencies.** Items 1, 7, and 8. Item 9 is a prerequisite for reliable repeated off-host observations. Policy needs no further ZF call. The operator stop-and-report rule still applies to these program sessions.

### 3. Dump, compact, and resume at tick-observed 150k

**Symptom and evidence.** F6 rows 11, 16, 32, 69, and 71. A rank 1 shows an uninterrupted coordinator run crossing 252k and continuing near 481k. That historical observation supports earlier maintenance, not retaining the superseded 252k policy.

**Root cause.** `tick.py:317-339` does not make a coordinator-context observation. `:447-479` either queues a follow-up to a streaming coordinator or uses the old 60k/six-hour rotation rule. Direct `pi-web-cli prompt` calls bypass that decision. `engine/piweb.py:75-86` and `bin/pi-web-cli:101-111` have prompt and archive adapters but no command-run adapter for native compaction.

The installed integration provides the needed primitives, with two important gaps. `W/dist/server/sessions/sessionRoutes.js:318-326` exposes `POST /api/sessions/:id/commands/run`. `sessionCommandService.js:78-96` starts native compaction asynchronously and returns "Compaction started" before success. `N/agent-session.js:1367-1370` aborts the active operation before manual compaction. Therefore do not issue `/compact` to a busy session or mistake command acceptance for completed compaction. Sending `/compact` as ordinary `/prompt` text is not the verified built-in-command path.

**Fix.** Add one retryable maintenance operation to the existing tick. Its identity binds the stream, designated coordinator, trigger observation, dump checkpoint, resume artifact, and eventual compaction entry. Coalesce later over-threshold ticks into that same operation.

1. **DUMP.** On each tick where the coordinator is taking a turn and observed context is at least 150,000, request maintenance. Deliver the request at the next native steering boundary without aborting the active model call or tool batch. The coordinator updates STATE, TODO, and every relevant status/progress artifact. It writes its own exact resume prompt for this same session into a stream-owned handover artifact. The prompt states the current task, unfinished next action, active owners, applicable stops, and evidence locations. The coordinator records a cycle-matching ready manifest with artifact digests and yields normally. After observing its completed response, the tick binds that ready manifest to the actual terminal session leaf. The agent does not guess the ID of its future final response. File existence, mtime, and an accepted steer are not dump-complete receipts.
2. **COMPACT.** Wait for the dump receipt and actual quiescence, including no streaming, compaction, bash operation, pending ask requiring resolution, or queued input. Add an idle-only, expected-checkpoint precondition at the pi-web command boundary. Check it atomically with starting compaction so a direct prompt between the tick's status call and command cannot be aborted. If a newer input changed the checkpoint, let it run and refresh the dump. Do not trust the existing queue as durable. Before acknowledging compaction-time input, the receiving maintenance record must retain its identity, exact body, kind, order, and attachment references until admission. The pi-web adapter is the sole writer of that input record. Tick state references its maintenance operation ID rather than duplicating ownership of the queue. Reuse native admission after recovery. No general mailbox migration engine is required.
3. **RESUME.** Observe a new successful native compaction entry for this operation, not just an idle status or HTTP success. Before admitting the saved resume, compare the current automatic-admission generation and direct-input sequence at the receiver. A newer stop makes it ineligible. New direct input invalidates blind replay of the old task. Preserve and admit that input in order, then reconcile the agent-authored resume context with it only if driving still applies. Do not let today's independent compaction-queue drain race a separate old RESUME prompt. Use item 7's correlated application receipt. If compaction fails, preserve the dump and resume artifact, park under item 2 where applicable, and do not claim successful maintenance. A retry after process failure adopts the already-recorded compaction instead of compacting or resuming twice.

The existing queue is an in-memory Map at `W/dist/server/sessions/piSessionService.js:317,1371-1376`, drains independently at `:2483-2525`, and is cleared on disposal at `:502`. It is not proof of accepted-input durability or resume ordering. The narrow maintenance record must close those two gaps. Preserve ordinary explicit input and control stops while reserving the session for compaction.

A short current phase record is sufficient. It is not a general workflow definition. Persist phases before dispatch, inspect the native transcript on uncertain completion, and keep one pending resume identity. A later stop invalidates execution resumption without deleting the saved checkpoint.

**Direct prompts are covered by observation.** The tick resolves the actual coordinator and checks it regardless of whether its turn came from a tick, browser, CLI, or bot. Safe-point steering is already part of the installed agent loop at `W/node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js:88-169`. The check is per tick, not per model request. A long in-flight call or tool can exceed 150k before it yields. That is permitted by Z3's no-interruption requirement and must be reported honestly.

**Native hook decision.** No new native Pi request-boundary hook is needed for Z3. Reuse safe-point message admission and idle native `compact()`. A small pi-web command precondition and an observable compaction result are needed to close the direct-prompt race. They belong in pi-web source, not a monkeypatch of Pi core, a global model override, or an extension that calls aborting compaction inside an active tool loop. The existing installer returns early when pi-web is already present at `install.sh:466-468`. A normal pi-stack reinstall therefore does not deploy this dependency fix. Install the explicitly tested pi-web artifact for verification, expose its maintenance capability, and have doctor refuse automatic compaction until that capability is present.

**Layer.** LAYER 3 owns trigger observation and the three phases. LAYER 1 gives the agent-authored resume artifact a stable location. LAYER 2 tests the boundaries but cannot order a running session's maintenance. An always-on rule alone cannot guarantee a future compaction. A stronger static layer cannot observe live token use and safely serialize direct input.

**Blast radius.** Medium. `engine/{tick,piweb,sessionlog,doctor}.py`, `bin/pi-web-cli`, coordinator templates, tick maintenance tests, and the small pi-web command boundary. Threads retain their existing Pi behavior. No fresh coordinator, provider switch, global reserve change, or transcript deletion.

**Verification.** In a real disposable stream, directly prompt the coordinator into a turn that crosses 150k and keep a benign tool running through a tick. Baseline sends no maintenance. Candidate must not abort the tool. Observe agent-authored dump and resume bytes, one successful compaction entry, identical session ID, and resumed task progress. Test 149,999 and 150,000 observations, repeated ticks, queued direct input, a direct prompt racing compaction start, failed summarization, and a stop racing RESUME admission. Accept a unique direct input during delayed compaction, restart the disposable service before its drain, and prove the accepted body and attachments remain recoverable. Separately drain a later stop or changed task before releasing an old saved resume and prove no obsolete task effects occur. Also crash after compaction succeeds but before the tick observes it. Null token status after compaction is not another threshold crossing. Record actual token observations for ZF's external monitoring rather than invent a hard ceiling.

**Dependencies.** Items 6, 7, 8, 11, 12, and 15. Item 7's receiving-side stop-generation check must land before automatic RESUME is enabled. G5 recovery may park this maintenance operation without losing its phase. Do not wait for track 3.

### 4. Delete budget and guard defaults at their source

**Symptom and evidence.** D1 and issue #33. F3 rows 10 and 44-45. B rank 3 distinguishes originally ratified fcf guards from their later revocation. Do not rewrite that history as proof that every original cap was unauthorized.

**Root cause.** `skills/stream-kickoff/SKILL.md:31` requires "Get each cap as a number". `docs/design/pi-streams.md:269,272,289,330,333,350` carries cap-first examples and accounting. This contradicts the recorded "Assume no limits" at `:41`. The generated STATE and STREAM templates contain no CPU or disk numbers to remove. Do not invent a nonexistent engine resource limiter.

**Fix.** Keep WRITES as a write-authority question. Remove the spend demand, numeric-cap demand, default dry-run/cost-budget workflow, and cap accounting examples. A cap is recorded only when the incoming task explicitly names it. Do not substitute a required guard-ratification interview, guard expiry scheme, default concurrency budget, or word limit. Keep normal tool timeouts, queue observation timing, and Z3's explicitly requested maintenance threshold conceptually separate from resource budgets.

**Layer.** LAYER 2 makes "no shipped default budget demand" a deterministic test over the actual generated instructions and examples. Delete the demand at its LAYER 5 kickoff source and correct the LAYER 4 coordinator rule. A skill file does not become layer 1 enforcement because Git stores it. Repo layout alone cannot prevent a future contradictory default from returning. Arbitrary model-invented guards remain a semantic problem, not something this literal-source test proves solved.

**Blast radius.** Low. `skills/stream-kickoff/SKILL.md`, `pi-streams/templates/stream/AGENTS.md`, relevant design examples, and template/prose tests. Existing stream-owned resource policies are not silently rewritten by upgrade.

**Verification.** A new kickoff accepts "no caps" and produces no token, CPU, RAM, disk, byte, or default concurrency guard. Add a negative assertion over the generated text and examples, then replay a kickoff with an explicit user cap to prove opt-in still works. The baseline contains the numeric demand. The candidate does not. Existing explicit freezes and stops remain unchanged.

**Dependencies.** None. This is a deletion-first commit.

### 5. Make archived evidence resolvable without restoring a session

**Symptom and evidence.** Corpus row 37 and A rank 2. G16 clarifies that "#37" means this corpus row, not a GitHub issue. GitHub pi-stack #37 is the program's draft PR and is unrelated to the evidence locator.

**Root cause.** At `threads.py:446-462`, rotation archives the predecessor and gives the successor only a STATE pickup. No stable evidence resolver is offered by `engine/piweb.py:43-86`. The actual checker is stream-specific, not pi-stack code. `Q/checks/coordinator_delivery_ledger_20261022.py:21-41` opens a frozen live pathname and restricts it to the live session directory. Installed archive code at `W/dist/server/sessions/sessionArchiveStore.js:29-56,154-166` copies the transcript, records `originalPath` and `archivePath`, then removes the original pathname.

The receipt bytes survived in archived session `01a1634d-80c3-7d03-88f7-0623480d3598`. This investigation independently matched exact JSONL lines 316 and 360 to their frozen SHA-256 values, including newlines. A identifies their entry IDs as `fdede143` and `fc2b9e3f`. They are `57a038ab902ddf9526bfa52e6c51252744798b91b55ee406ec144d05e7295414` and `b6517adac9d05743419314a00df7b11773351addc0988e1ca44804beaac9aa2a`. A missing live path is not lost evidence.

**Fix.** Add one evidence-read adapter at the session/archive boundary. Resolve full session identity through active and archive metadata, locate the exact record, and verify its original-byte hash. A physical line number is a hint, not identity. Return unavailable or hash mismatch explicitly. Do not reconstruct JSON and call it the original bytes, search guessed archive directories in every checker, or restore the retired coordinator.

For new small evidence used by stream checks, retain the exact needed record in a stable stream-owned evidence artifact when created. Preserve its session and record provenance. This is a small copy, not all transcripts in Git. D6 requires copying needed outputs from repositories used as tools into the stream's owned worktree.

The old publication gate was also unnecessary bookkeeping. A documents the authorized replacement with current artifact re-verification. Fixing the locator is not a reason to reinstall that historical gate.

**Layer.** LAYER 3 is the reusable live/archive read boundary. LAYER 1 supplies stable copied evidence where sufficient. LAYER 2 verifies exact bytes across relocation but cannot choose the live deployed location. Neither a handover summary nor another skill can repair a path that archive removes.

**Blast radius.** Low to medium. One adapter in `sessionlog.py` or `piweb.py`, a CLI evidence-read operation if needed, and archive relocation tests. Expose existing archive metadata in pi-web only if the client cannot already retrieve it. Affected stream checkers migrate separately with permission. No general artifact registry or retention subsystem.

**Verification.** A fixture returns the same two hashes before and after archive and rejects a one-byte change, unknown record, missing source, or wrong session. A disposable real stream creates a tiny evidence record, retires its coordinator safely, and resolves the same bytes afterward without restoring it. No production session is touched to reproduce the bug.

**Dependencies.** None for the adapter. Item 11 uses it at retirement. Migration of a real product-stream checker is a separately authorized rollout action, not part of this artifact.

### 6. Make STATE a current view

**Symptom and evidence.** A rank 3 and the corpus cross-check §3. The historical 654 STATE was 10,195,068 bytes. A found 71 "Preserved prior checkpoint" headings, not 3,284 such headings. The larger number counts all headings. Reads were truncated, so this is not a claim that each prompt loaded 10 MB.

**Root cause.** `templates/stream/AGENTS.md:4,8` combines mandatory rereading with "Rewrite STATE" but supplies no current/history separation. `templates/stream/STATE.md:1-6` is only four blank labels. `templates/stream/context/README.md:1` is an empty index heading. In the frozen 654 sample, new checkpoints preserve the old file underneath. Rotation reimports the same input.

**Fix.** Replace the STATE skeleton with a current-only view. It contains the goal pointer, current task and next action, active owners, actual blockers, relevant artifact references, and applicable stop. Preserve all still-open work. Put old checkpoint text in Git history or an existing retained history artifact outside mandatory reads. Do not recursively append or prepend prior STATE. Keep `context/README.md` an index rather than another diary.

Add a narrow deterministic check for known recursive-checkpoint sections and full prior STATE embedded beneath a new checkpoint. Do not use a byte, token, or line cap as a substitute. The check proves that specific bad shape is absent, not semantic completeness. A coordinator still has to choose the correct current facts.

For an explicit migration, save the old bytes once, derive a current view from current source-backed work, and compare active owners, blockers, and next actions. Keep original evidence retrievable. Do not replay the entire old file at pickup. `project.py:703-749` already protects stream-owned STATE from automatic template upgrades. Preserve that protection.

**Layer.** LAYER 1 separates current work and history in the files the agent must read. LAYER 2 rejects the demonstrated recursive shape. LAYER 4 describes semantic rewriting that a structural check cannot prove. No stronger static mechanism can infer which arbitrary prose facts remain true. Item 12 supplies the runtime trigger instead of relying on an optional skill.

**Blast radius.** Low. State and context templates, current-view structural check, tests, and an explicit migration recipe. No bulk rewrite of existing streams in this program session.

**Verification.** Feed the frozen `c146285` STATE shape through the check. Baseline accepts it because there is no check. Candidate rejects recursive preservation. A curated candidate must preserve every current owner, blocker, and next action in the test fixture while removing historical checkpoints from the pickup text. A fresh disposable pickup reads the current view and resolves a historical receipt only when asked. File-size reduction alone does not pass.

**Dependencies.** None. Item 12 uses this shape, and item 3's dump must update it.

### 7. Acknowledge consumed and applied steers

**Symptom and evidence.** Z5, F8 rows 21, 35, 72, and 73. C rank 3. A establishes that all 20 saved messages in row 72 eventually reached the successor manually. Do not cite that row as proved permanent message loss.

**Root cause.** `bin/pi-web-cli:62-66` returns success on HTTP 200 and `accepted: true`. `engine/piweb.py:75-79` discards the response. `tick.py:435-445` clears pending events after this call. Worker replay at `:398-429` has useful crash recovery, but does not establish coordinator consumption or application. The server returns before the asynchronous prompt completes at `W/dist/server/sessions/piSessionService.js:1326-1370`.

**Fix.** Give each steer or coalesced tick delivery a stable delivery ID. Preserve the exact body, destination coordinator, and current delivery state before sending. Distinguish transport acceptance, consumed, applied, and blocked. Report "applied" only after the coordinator records that it consumed the identified instruction and applied its requested change to the current plan or behavior, with a concrete evidence reference. A queued message, an echoed ID, and "I will do it" do not pass. A blocked or rejected instruction stays visibly blocked, not delivered-and-done.

The receipt is a narrow delivery record, not an ask lifecycle. It does not track product acceptance or turn every instruction into a new task ledger. Applying a steer and finishing the resulting product work remain different claims. Full product-completion and own-paraphrase oracle design stays in track 3 under Z2.

Expose the receipt through CLI/status so Grok Bot does not translate `accepted` into "delivered". A send response may say `transportAccepted`, but must not emit a delivered/applied acknowledgement until the application receipt exists. Keep pending tick events until the corresponding application receipt. Coalesce routine wake requests, but do not deduplicate distinct user commands by text. Retries retain delivery identity. After uncertain application, inspect the transcript and affected artifact rather than replay a potentially side-effecting instruction blindly. Do not promise exactly-once arbitrary external effects.

Use one current automatic-admission generation for tick-produced requests. Stop/cancel invalidates it durably, and the receiver compares it before admitting a wake, recovery continuation, or maintenance RESUME. Keep ordinary explicit user prompts usable. This is bounded control-delivery bookkeeping, not an ask lifecycle or a general authority epoch model.

The bot must retain a message it has not sent and show it as undelivered. A host-side receipt cannot recover a steer still trapped in the bot's approval card. Change that caller's wording and retention alongside the CLI.

**Layer.** LAYER 3 owns correlation and the acknowledgement boundary. LAYER 1 preserves exact input and receipt identity. LAYER 2 tests the distinction but cannot make a running coordinator consume input. Coordinator application evidence still requires semantic judgment. This is not an independent acceptance-oracle subsystem.

**Blast radius.** Medium. `bin/pi-web-cli`, `engine/{piweb,tick,sessionlog}.py`, coordinator instructions, tests, and bot caller handling. Use a small coordinator acknowledgement command or tool. Add pi-web client-message correlation only where required for durable deduplication. Do not introduce an ask database.

**Verification.** Return `accepted: true` but leave the steer queued. Baseline reports success and drops the wake. Candidate must report only transport acceptance and retain it. Consume without applying and assert no applied ack. Apply a tiny requested configuration or plan change, then assert a correlated receipt names the observed change. Cover crash after application before receipt, identical bodies with distinct IDs, stale destination, compaction, and a blocked instruction. For each automatic request type, complete a stop after sender revalidation but before receiving admission. Candidate rejects the stale request before task effects, not merely after an application acknowledgement. The real disposable-stream check must inspect the changed artifact, not trust a generic assistant sentence.

**Dependencies.** Item 8 for targeting. Items 1, 2, and 3 consume the receipt mechanism. Wider ask semantics are explicitly not a dependency.

### 8. Repair stale coordinator IDs without guessing ownership

**Symptom and evidence.** The corpus cross-check and C rank 3 find fcf steering in `01a158c6` while the registry names `01a13a29`. Relevant rows are 51-53 and 55. Issue #36 also records registry/runtime disagreements.

**Root cause.** `threads.py:157-165` immediately returns the first active coordinator row. `tick.py:311-339` targets that row and repairs only the archived flag observed in the listing. `_resume_or_spawn` at `threads.py:139-155` adopts the first unrecorded same-directory live session and may send no opening prompt to a nonempty session. `_one_stream` at `:211-244` reports only the registered coordinator. A different conversation can therefore be silently treated as the coordinator, or missed entirely.

**Fix.** Make `threads.tsv`'s explicit coordinator designation authoritative and validate it against live and archived identity before dispatch. Require exactly one designated active coordinator. Status and doctor must show missing, archived, duplicate, or unregistered candidates as mismatches. They must not return a falsely healthy old ID.

All normal coordinator creation, adoption, replacement, tick targeting, and status use the same resolver. Adopt an existing nonempty session only by an explicit adoption operation. Recover a crash-created session only from the exact saved spawn attempt identity, not list order or newest timestamp. Save registry updates atomically through item 15. Reject duplicate session IDs and reserve the `coordinator` role from worker spawn/adopt, which currently accepts it at `threads.py:361-363,391,502`. Do not convert idle workers to done. Registry lifecycle is not task acceptance.

For deployed fcf, first read the explicit replacement evidence and verify predecessor quiescence. Updating a row is not permission to resume its frozen work. Do not operate it as part of the disposable verification.

**Layer.** LAYER 3 validates runtime designation and dispatch. LAYER 1 keeps the one designation in the existing registry rather than STATE and bot caches. LAYER 2 tests ambiguity. Static repo shape cannot establish which runtime session is still live, so it cannot carry the whole fix.

**Blast radius.** Low to medium. `threads.py`, `tick.py`, `doctor.py`, status output, and new/adopt/rotation tests. No global session census, lease system, or arbitrary session adoption.

**Verification.** Baseline returns a stale active row without querying runtime. Candidate reports the mismatch and sends no prompt. Test two same-directory sessions, archived old plus designated live new, a crash after spawn before registry save, missing session, and duplicate active coordinator rows. Every path must resolve one identical coordinator ID or refuse ambiguity. Repeat on the disposable stream after deliberate replacement.

**Dependencies.** Item 15. Required before items 1, 2, 3, and 7.

### 9. Fix the Grok Bot box's Twingate wrapper

**Symptom and evidence.** G15 records per-call `--ensure-tg` restarting Twingate and causing SSH banner timeouts. This is a new program observation, not a row in the 75-row corpus.

**Root cause and ownership.** Neither `pi-web-cli-remote` nor `options-01-ssh` is a tracked pi-stack file at `3acf0f0`, and neither executable is available on this host. `bin/pi-web-cli:1-15` explicitly owns the host loopback CLI, not Twingate. The generic pi-bot `skills/pi-web-access/SKILL.md` assigns deployment reach helpers to an installed transport binding. The actual Grok Bot box wrapper source was not available here. No fictitious pi-stack file:line is supplied for it.

**Fix.** Keep this as an external prerequisite in track 1, implemented in the owning Grok Bot deployment repository after locating its source and pin. Repeated `pi-web-cli-remote` calls use `options-01-ssh` without unconditional `--ensure-tg`. Reuse the live userspace connection. Reinitialize Twingate only after a classified connectivity failure. Do not restart it for a remote command failure, an auth error inside pi, or a nonzero application exit.

Only retry a read-only request automatically after reconnect. For a mutating request with uncertain remote acceptance, query its correlated receipt before resending. Preserve exit status and stderr. Never add Twingate management to pi-stack's generic host CLI.

**Layer.** LAYER 3 is the deployment transport adapter. LAYER 2 wrapper tests prevent unconditional reconnects, but cannot manage the actual connection. A skill reminder is weaker than fixing the executable used on every call.

**Blast radius.** Low. The two box wrappers and their deployment tests. This is a companion change outside the pi-stack stack. Exact repository/path discovery is an engineering prerequisite, not a ZF decision or permission to edit installed scripts ad hoc.

**Verification.** In wrapper tests, repeated successful read-only calls cause zero Twingate restarts. Inject one connection failure and observe one reconnect attempt. An application exit must not reconnect. A timed-out mutation remains uncertain until its receipt is read. On the Grok Bot box, repeat safe `status` calls against the disposable stream and inspect the Twingate process identity and SSH results. Do not report a measured timeout improvement before that comparison exists.

**Dependencies.** None. Required before real off-host checks for items 1, 2, and 7.

### 10. Remove goal- and stop-overriding template defaults

**Symptom and evidence.** B rank 3 identifies a concrete template contradiction. Rows 37 and 43 show bookkeeping/proof gates replacing useful work. Row 69 exposes a wrong-source interpretation, whose general oracle design is deferred by Z2. Row 75's Phase-2 hold was explicitly relayed and must remain held. C also disputes the fresh-OK explanation for row 54, so it is not proof for removing a genuine approval gate.

**Root cause.** `templates/stream/AGENTS.md:5` says act only inside AUTONOMY, then says continue on the default for anything else. `:7` requires a matching `checks/` script for every done claim. `skills/stream-kickoff/SKILL.md:29,44` likewise demands new check scripts. These defaults can create new deliverables and gates even for artifact-only or small requests. `threads.py:127-137` scans for a ratification marker anywhere, and spawn/adopt at `:378-443,494-531` do not enforce the kickoff's stated ratification boundary.

**Fix.** Delete the out-of-authority default permission. A recommended default is usable only inside the existing grant. It cannot change a goal, acceptance, protected user change, stop, or explicit gate. Do not replace a goal with the latest execution status. Keep stopping and completion in STATE, not in place of GOAL.

Remove the requirement to invent a new script for every check. Use the requested artifact, existing tests, and direct observed evidence. Preserve an explicitly requested script or acceptance check. Do not make this a reviewer policy or a general completion engine. In the close skill, corrective or reflective work must stay inside the stream's existing grant rather than silently expanding closure.

At the engine boundary, parse the actual first-line ratification marker and refuse worker spawn/adoption for an unratified stream before creating a worktree, changing pointers, or prompting a session. Status must not accept a marker buried in historical prose. Keep kickoff itself available while unratified. Existing malformed contracts are reported for explicit repair, not silently rewritten or auto-ratified.

**Layer.** LAYER 4 is the corrected always-loaded coordinator rule. LAYER 5 is the corrected kickoff/close guidance. LAYER 1 separates standing goal and execution status in the actual files. LAYER 3 enforces first-line ratification before worker dispatch, with LAYER 2 tests. Stronger static layers cannot determine arbitrary task authority, so the semantic rule remains text. This deliberately stops short of Z2's deferred constraint-lifetime model.

**Blast radius.** Low. Coordinator and thread templates, `skills/{stream,stream-kickoff}/SKILL.md`, `threads.py`, and prose/spawn/adopt tests. No automatic rewriting of ratified product-stream contracts.

**Verification.** Baseline accepts a historical embedded `ratified: yes` and can dispatch an unratified stream. Candidate refuses before any side effect. Kickoff with an artifact-only request must not create a new proof campaign. Replay cap revocation plus a surviving research freeze and assert the freeze remains. Replay row 75's hold and assert no Phase 2. These are boundary fixtures, not a general authority-reasoning evaluation.

**Dependencies.** None. Needed before autonomous continuation. Full own-paraphrase oracle, ask lifecycle, and constraint-lifetime work stays deferred.

### 11. Remove routine rotation and refuse unsafe manual rotation

**Symptom and evidence.** F6 rows 16, 32, 37, 71, and 72. A shows that queue transfer was manual and all 20 saved bodies arrived. It also corrects issue #36's implication that archive itself necessarily killed active execution. Installed pi-web already refuses archive while streaming, compacting, running bash, or holding queued work.

**Root cause.** `tick.py:447-479` rotates on size or age. `project.py:56-60` supplies the 60k/six-hour defaults. `threads.py:446-462` has no coordinator checkpoint request or queue transfer and opens the successor with "Read STATE.md, then continue". The stubbed scenario in `tests/test_scenario.py:158-188` does not prove native archive safety or carry-forward.

**Fix.** Delete routine size/age rotation from ordinary wake selection. Reuse the same designated session and let item 3 handle context. Do not replace 60k with another rotation threshold or fixed compaction count. Retain explicit replacement for an intentional boundary or genuinely unusable session.

Mark `docs/design/pi-streams-handover.md:3,20,26,92` as historical rather than an authoritative current pickup guide. It still says nothing is built and recommends fresh coordinators when large. Keep the original historical evidence, but do not seed that policy into new implementation sessions.

Manual rotation must not abort first to make archive possible. Retain native busy/queue refusal. Require a current coordinator-authored checkpoint and stable references to unfinished work before retirement. If queues or session-local native child callbacks still need the old owner, refuse rotation and explain the unresolved boundary. Do not build a general native-child adoption or queue migration subsystem in track 1. After successful retirement, create or explicitly adopt the successor using item 8, then confirm its pickup before calling rotation complete. Persist enough existing rotation phase to recover archive-then-spawn failure.

**Layer.** LAYER 3 owns replacement and native refusal. LAYER 1 supplies the checkpoint. LAYER 2 checks crash boundaries but cannot prevent a deployed abort/archive. A handover skill cannot enforce the archive precondition.

**Blast radius.** Low to medium. `tick.py`, `threads.py`, obsolete warm configuration handling, the current design and historical-handover label, and rotation tests. Accept old config fields while ignoring their retired rotation behavior during migration. Do not silently assign them a different meaning. No automatic cleanup of old sessions or worktrees.

**Verification.** Baseline rotates an idle coordinator at 60k or six hours. Candidate does neither. Attempt manual rotation during a benign tool, queued steer, or unresolved callback and assert no abort, archive, or second coordinator. At a deliberate clean boundary, rotate once, retain exact evidence through item 5, and verify one successor. Crash after archive and recover without arbitrary adoption or duplicate opening prompts.

**Dependencies.** Items 5, 8, 14, and 15. Removal of routine rotation precedes items 1 and 3. General callback migration belongs to track 3 if it cannot remain a refusal.

### 12. Put D7's review in the dump, not in another workflow

**Symptom and evidence.** D7 reframes issue #36 around STATE, DECISIONS, TODO, and rules. A rank 3 and B rank 3 document recursive current files and stale competing text. The corpus cross-check records 654 DECISIONS at about 202 KB and TODO at about 394 KB. These are historical measurements, not new limits.

**Root cause.** `templates/stream/AGENTS.md:3-8` has an every-turn read and STATE rewrite, but no compaction/review trigger for the other files. `templates/stream/DECISIONS.md:1` has no current/history separation. `skills/stream/SKILL.md:21-29` harvests at closure, too late for a long-running coordinator.

**Fix.** Use item 3's DUMP as the mandatory maintenance trigger. The coordinator reviews STATE, TODO, current DECISIONS, and the rules actually loaded for that stream before it marks the dump complete. It updates current progress and open work, moves completed narrative to linked history, and checks that current instruction files do not reproduce superseded checkpoint text. Keep exact source history retrievable.

At coordinator pickup, do the same review if the last dump/checkpoint does not match the current file revisions. Reuse content hashes or the stream Git revision to avoid another periodic scheduler. Do not force a review on every unchanged tick. Do not silently delete rules, invent constraint expiries, or decide new precedence. Unknown or conflicting rules stay visible. Constraint lifetimes and independent review remain track 3 under Z2 and D9.

**Layer.** LAYER 3 guarantees the review request occurs at the selected maintenance boundary. LAYER 1 separates current files and cold history. LAYER 2 checks exact duplicate/recursive forms. Semantic rule review remains LAYER 4 coordinator work. Neither structure nor CI alone can schedule maintenance in an already running session or establish the meaning of arbitrary rules.

**Blast radius.** Low. Extend the existing dump instruction and receipt with the reviewed artifact revisions. Update templates and tests. No new reviewer agent, workflow definition, retention timer, or transcript deletion.

**Verification.** In a fixture with unchanged STATE but changed TODO and rules, baseline has no review trigger. Candidate's next dump reviews all named files and retains the unresolved TODO and stop. Repeat unchanged ticks and get no additional review operation. Verify that completed history leaves mandatory reads while its exact source stays recoverable. In the real disposable compaction check, inspect those files before permitting COMPACT.

**Dependencies.** Items 3 and 6. Ship this as the same PR as the dump sequence, not an independent lifecycle subsystem.

### 13. Stop automatic Git capture of binaries and data

**Symptom and evidence.** F11 row 29 records tick-committed DLLs and packages. C explicitly separates this from liveness and recovery.

**Root cause.** `project.py:522-527` runs `git add -A` for every automatic commit. `tick.py:548-563` applies that to each stream and can push it. The stream `.gitignore:1` ignores only `log/`. Human convention is not a staging boundary.

**Fix.** Remove whole-worktree auto-staging. Seed known harness files explicitly at creation. For later ticks, stage only known current-record paths and changes to already-approved code, docs, checks, and small reports. Leave arbitrary new worker output untracked. New report/check paths are explicitly approved by the owning coordinator, not discovered through `add -A`. Compute and commit only the approved path set, without absorbing unrelated pre-staged entries. Preserve the foreign index state. Refuse binary candidates in that set, including already tracked binary updates, without deleting data or resetting the user's index. A path allowlist and binary check cannot prove that arbitrary text contains no dataset, so do not advertise semantic data classification. Ignore standard scratch/output directories in the template as a secondary convenience.

Do not add a file-size budget. Git is for code, docs, and small reports, never data. Already tracked binary/data contamination needs an explicit cleanup change. Merely adding `.gitignore` does not untrack it and must not be claimed sufficient.

**Layer.** LAYER 3 fixes the automatic staging operation shared by new, tick, upgrade, and lifecycle commands. LAYER 1 places scratch outside tracked report paths. LAYER 2 tests and rejects bad staged content. Repo shape alone cannot stop the existing `add -A` from collecting arbitrary new output.

**Blast radius.** Low. `project.py`, `.gitignore`, and Git fixture tests in new/tick/upgrade suites. No production history rewrite, data deletion, branch pruning, or forced push.

**Verification.** Put a tiny fake DLL, package, and CSV in a disposable stream beside an updated STATE and a deliberately staged Markdown report. Baseline commits all unignored files. Candidate commits only approved records/report and leaves data out. Also test an already-staged binary and an already-tracked binary update. Neither may slip through the automatic commit. Preserve bytes and the caller's index on refusal.

**Dependencies.** None. Land before enabling more autonomous tick turns.

### 14. Bind handovers to session identity

**Symptom and evidence.** This is a source-derived low-blast-radius defect. Row 37 and A show why successor pickup needs the correct predecessor evidence, but no corpus row proves this particular role-name collision occurred.

**Root cause.** `templates/thread-brief.md:11` writes `handover/{role}.md`. `_has_handover()` at `threads.py:465-476` accepts any nonempty file at that path. `spawn_thread()` at `:411-421` permits a successor in an archived predecessor's worktree. `tests/test_thread_spawn.py:183-226` codifies that reuse. A stale role handover can therefore satisfy close for the successor. `skills/stream/SKILL.md:22-23` also skips asking for a handover when that old role file exists.

**Fix.** Key the path by role and full session ID, such as `handover/<role>/<session-id>.md`. Render that exact path into the new thread's brief after spawn. Close requires the current session's artifact, not any nonempty predecessor document. Preserve old handovers unchanged. D6 also means that a handover's required tool outputs live in the worker's owned worktree, or are small exact copies in the owned stream repository. Do not point at another tool repository's disposable output as the only copy.

**Layer.** LAYER 1 puts identity into the artifact path, so stale evidence cannot masquerade as current by reusing a role. No stronger layer exists. LAYER 2 tests the close predicate. LAYER 3 reads the session-bound path at close, with no new artifact registry.

**Blast radius.** Low. Thread brief/rendering, `_has_handover()`, close, the stream skill, and literal brief/close tests. Existing role-only handovers need an explicit compatibility/migration decision based on their actual recorded session, not an automatic copy that pretends they are current.

**Verification.** Leave only a predecessor's handover, then create a same-role successor in a disposable fixture. Baseline close accepts the stale file. Candidate refuses without archiving. Supply the successor's own file and close succeeds. Assert predecessor bytes stay unchanged. A disposable helper output copied to the owned worktree remains resolvable after that helper's original is removed.

**Dependencies.** None. Item 11 reuses the same identity rule for coordinator checkpoints. No native-child migration or historical retention policy is added.

### 15. Publish registry snapshots atomically and repair creation retries

**Symptom and evidence.** Source-derived low-blast-radius companion to issue #36's registry drift and corpus cross-check §3. No numbered corpus row establishes these exact crash points. They are reproducible from the existing persistence code.

**Root cause.** `threads.py:105-124` directly truncates and rewrites `threads.tsv`. `project.py:190-194,220-221` similarly writes project and stream configuration directly. Status reads without those mutation locks at `cli.py:194-200`. Locks alone do not prevent a concurrent reader or process failure from seeing partial bytes. `create_stream()` at `project.py:682-700` upserts the index row only under `if fresh`. A crash after writing `stream.toml` but before index registration leaves a retry that never repairs its missing row.

**Fix.** Reuse the existing same-directory atomic replacement helper at `project.py:224-235` for engine-owned registry and configuration snapshots. Keep the existing lock order. Always idempotently upsert the stream's index row after successful create/retry, outside one-time template initialization. Do not overwrite stream-owned documents on retry. These are visibility and retry fixes, not a transaction over remote spawn/archive/prompt effects.

**Layer.** LAYER 3 owns runtime snapshot publication and idempotent retry. LAYER 2 tests interruption and concurrent reads. File layout alone cannot keep a killed writer from truncating an open file, and CI cannot run on each deployed write. Where an acknowledged delivery or maintenance receipt needs power-loss durability, synchronize its file and containing directory before acknowledging it. Atomic rename alone does not prove that stronger guarantee.

**Blast radius.** Low. Existing writers in `project.py` and `threads.py`, stream-create retry, and persistence tests. Reuse a helper rather than create a general control store. Preserve the old valid file when writing or replacing fails.

**Verification.** Inject a short write and replacement failure. Baseline can leave a truncated registry. Candidate leaves either old or new complete bytes. With config present and index row absent, retry creates exactly one row without changing owned document hashes. Run a concurrent disposable status reader through repeated writes. Keep remote-operation uncertainty tests separate.

**Dependencies.** None. Land before item 8 and all new runtime operation receipts.

## Needs a ZF call

None for the listed fixes. Z1, Z3, Z4, Z5, D1, and G5 settle the policy choices. P7 assigns remaining reversible engineering decisions to Grok Bot. The program's first-pass go-ahead remains the implementation gate.

Recommended defaults are already stated in the items. In particular, keep the same session, apply no new budgets, hold explicit stops, refuse unsafe rotation, and use ZF-only Slack DM. Missing box-wrapper source and pi-web source pins are engineering discovery tasks, not questions for ZF.

## Deferred to track 3

- **Per-ask lifecycle and ask ledgers.** The stream can lose an obligation when plans or priorities change. Z2 moves the lifecycle design out of this stack.
- **The coordinator grading its own homework.** A brief and its checker can share the same wrong paraphrase, and context decay may amplify that error. Z2 defers the oracle and fidelity design.
- **Constraint lifetimes.** Obsolete policies can survive beside later corrections. Z2 defers expiry, supersession, and general rule-lifecycle machinery.
- **General control record or engine.** The research proposal combines authority, asks, ownership, and transactions. Its broader contract is not required for these bounded tick operations.
- **Workflow definitions and reviewer policy.** D9 requires a workflow shape before choosing costly independent-review boundaries.
- **General native-child adoption and callback migration.** A replacement coordinator can read an old run ID without owning its completion subscription. Track 1 refuses unsafe replacement rather than invent a second worker backend.
- **General parallel-lane scheduling.** Independent work can be serialized behind unnecessary dependencies. Track 1 wakes ready work but does not infer a dependency graph from arbitrary goals.
- **Broad overbuild and known-good-path enforcement.** Custom loaders, runners, images, and redundant APIs need better design judgment and outcome checks, not another universal tick rule.
- **Historical cleanup and transcript retention.** Old sessions, worktrees, and raw evidence need an explicit deletion policy. D7 does not authorize automatic deletion.

These are problem statements, not commitments to a framework. D6 excludes a contested-authority precedence subsystem.

## Stacked implementation plan

All work below is future work after the catalog's first-pass go-ahead. Start fresh branches above pi-stack main `3acf0f0`. Keep each implementation commit small and its regression test in the same commit. Show each new regression failing against the base before accepting its fix. Do not merge a partial liveness stack that depends on an unlanded safety boundary.

### Verification setup on options-01

Use a new disposable project, source fixture repo, stream directory, explicit private index, and disposable `XDG_CONFIG_HOME`. Set the private XDG environment for every verification CLI process and its private systemd unit. Pass the private index through `--home` on every command, including the real tick. Set `PI_WEB_URL` explicitly to the dedicated verification instance. Do not borrow an existing coordinator or product-stream worktree.

`--home` alone is not isolation. `init_project()` registers that index in the homes file under XDG at `project.py:341-348,370-386,610-611`. The production service runs the global tick at `systemd/pi-streams-tick.service:6` and would discover a test index registered under shared XDG. Assert that the production homes file's bytes remain unchanged and its global selection excludes the test index. Do not stop or edit the production timer to compensate.

LAYER 1 gives verification configuration a separate filesystem identity. LAYER 2 checks the boundary. Add an offline production/test-XDG fixture before any real-stream test. With shared XDG, baseline global selection includes the new test index. With private XDG, production selection excludes it and the private unit carries the same isolated environment.

Use the real pi-web/native Pi integration in a dedicated verification instance and the same configured provider/model. Use supported instance configuration, not guessed flags. Do not copy or rewrite credentials to provision it. If an authorized isolated instance is unavailable, report the real-stream check blocked instead of falling back to a production destination. Drive only newly created disposable sessions. Use a separately named user-level systemd unit that executes `pi-streams tick --home <private-index>`, so timer behavior is exercised without editing or restarting the production unit. Keep generated context and fault fixtures outside Git.

Run baseline and candidate with the same small task and controlled clock/error observations. Name and retain both results under the disposable stream's evidence folder. Fault injection occurs at the external boundary of that stream only. Do not exhaust real quota, expire real auth, modify credentials, fill the host disk, or send production alerts for a test. A real notification test uses the existing authorized ZF DM route once and labels itself as verification. Mocks alone cannot certify that route.

The existing offline suite is `python3 -m unittest discover -s pi-streams/tests`. Keep its stub-only isolation from `tests/support.py:26-50`. In the pinned pi-web source checkout, use `npm test -- <focused-test-path>` for the command, archive, and maintenance cases. Its installed package metadata defines `npm test` as `vitest run --config vitest.config.ts`. No upstream test filename is claimed to exist until that source pin is checked out. The planned real-stream cases below are additional tests, not a claim that the candidate already exists.

### External prerequisite E. Reliable box transport

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `box: reuse Twingate across remote CLI calls` | Owning deployment source for `pi-web-cli-remote`, `options-01-ssh`, and wrapper tests. Locate and pin it first. | Item 9's reconnect classification. Repeat read-only disposable-stream status calls from the box. |

This companion change does not go into the pi-stack PR or generic host CLI.

### Stack S1. Remove bad seeds and accidental Git capture

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: remove default caps and unauthorized fallback text` | `skills/{stream,stream-kickoff}/SKILL.md`, stream/thread templates, `docs/design/pi-streams.md`, template/prose tests. | Items 4 and 10. New disposable kickoff with no caps and an artifact-only goal. |
| `streams: reject unratified worker dispatch` | `engine/threads.py`, spawn/adopt/status tests. | First-line marker fixture and no side effects before ratification. Attempt dispatch in the new unratified stream. |
| `streams: separate current state from checkpoint history` | `templates/stream/{STATE,DECISIONS,AGENTS}.md`, `context/README.md`, a narrow current-view check and tests. | Item 6's frozen-shape fixture. Disposable pickup with current work and separately retained history. |
| `streams: bind handovers to the full session identity` | Thread brief/rendering, close checks, `skills/stream/SKILL.md`, brief/close tests. | Item 14's predecessor/successor case and owned helper-report reference. |
| `streams: publish snapshots atomically and repair create retries` | `engine/{project,threads}.py`, create/persistence tests. | Item 15's interrupted write, concurrent read, and config-present/index-absent retry. |
| `streams: stage records explicitly instead of git add -A` | `engine/project.py`, ignore template, new/upgrade/tick Git tests. | Item 13's DLL/package/CSV and staged-index cases. Inspect actual disposable-stream commits. |

This stack can land independently. It must not migrate or resume existing streams.

### Stack S2. Correct identity, receipts, archive reads, and rotation

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: resolve the designated coordinator before dispatch` | `engine/{threads,tick,doctor}.py`, new/adopt/status tests. | Item 8's stale and ambiguous identities. Verify one designated disposable coordinator. |
| `streams: expose archive-stable evidence reads` | `engine/{sessionlog,piweb}.py`, `bin/pi-web-cli` if needed, new evidence tests. Small pi-web metadata exposure only if needed. | Item 5's exact hashes before/after a safe disposable archive. |
| `streams: distinguish transport acceptance from applied steer` | `bin/pi-web-cli`, `engine/{piweb,tick,sessionlog}.py`, receipt command/tool, coordinator template, CLI/tick tests. | Item 7's accepted-only, consumed-only, applied, blocked, and uncertain cases. Inspect a real changed artifact. |
| `pi-web: reject stale automatic admissions after stop or cancel` | `src/server/sessions/piSessionService.ts`, narrow persisted control-delivery generation, matching CLI/engine adapter fields, and focused race tests. | Delay a wake, recovery, and RESUME after sender revalidation. Stop, release, and observe zero task effects. Fresh explicit input remains usable. |
| `streams: reuse coordinators and refuse unsafe explicit rotation` | `engine/{tick,threads,project}.py`, rotation/scenario tests, obsolete-policy docs. | Item 11. No size/age rotation, no busy abort, safe clean replacement and crash recovery. |

Update the bot relay's receipt handling in its owning deployment source alongside this stack. It must stop claiming a transport receipt is delivery. Land the CLI response semantics and caller changes together or version the added fields without breaking the caller.

### Stack S3. One dump, compact, resume operation

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `pi-web: compact only at the expected idle checkpoint and retain maintenance input` | `jmfederico/pi-web` source `src/server/sessions/{sessionCommandService,piSessionService}.ts`, narrow persisted maintenance record, capability/result fields, and focused tests. No installed `dist` edits. | Busy/direct-input races, accepted input across a restart during compaction, and newer input before saved RESUME. A command-start reply must not pass as compaction completion. |
| `streams: add native command-run and compaction-result observation` | `bin/pi-web-cli`, `engine/{piweb,sessionlog,doctor}.py`, CLI/doctor tests. | Call the real command endpoint and identify one successful compaction entry. |
| `streams: dump compact and resume coordinators at tick-observed 150k` | `engine/tick.py`, maintenance phase persistence, coordinator/dump template, new maintenance tests. | Item 3's direct-prompt, active-tool, threshold, crash, failure, and same-session cases. |
| `streams: review current records and rules during dump` | Current/history templates and dump instruction/receipt, maintenance tests. | Item 12. Inspect STATE, TODO, DECISIONS, loaded-rule revisions, and the agent-authored resume prompt before compaction. |

Build and install the exact tested pi-web artifact before enabling this stack, then require its maintenance capability in doctor. The current installer skips an existing pi-web, so merely reinstalling pi-stack is not this deployment step. Do not revive the superseded 252k native-hook work. Real verification must show no interruption of the running tool and actual resumed task progress.

### Stack S4. Make the existing tick a driver

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: persist stream drive disposition and continue due work` | `engine/{project,cli,tick}.py`, current-state template, tick tests. | Item 1's two-step no-human-nudge case and stop/wait/done suppression. |
| `streams: isolate observations and report per-stream tick health` | `engine/{tick,doctor,piweb}.py`, tick-failure/doctor tests, systemd unit only if needed for completed-pass reporting. | One unavailable worker must not starve ready work. One healthy stream must not hide another failing pass. Run through the disposable systemd unit. |

Reuse S2's receiving-side generation check for all driver admissions. Native stop/cancel invalidation is already present before S3, not postponed until this stack. Test the sender-check/stop/receiver-admission race before enabling automatic execution wakes. Tick receipt, maintenance, and registry prerequisites must already be present.

### Stack S5. Same-provider recovery and quiet Slack notifications

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: retain typed blockers and allow due recovery probes` | `engine/{tick,sessionlog}.py`, provider/pi-web metadata adapter, outage/failure tests. | All five G5 cases while the old assistant error remains unchanged. One reset retry, then re-park on failure. |
| `bot: deliver blocker and recovery episodes to ZF DM` | Owning bot deployment's ALERTS reader, completed-pass observer, Slack delivery state/tests. `systemd/pi-streams-tick.service` only if the existing observer needs an exit-status signal. | Exact `<stream-id>:: <message>`, ZF only, no BossOps, one blocker and at most one recovery. ENOSPC notification originates off-host. |
| `streams: preserve stops and uncertain jobs across recovery` | Focused recovery tests and small integration fixes in existing adapters. | Cancel during outage, gated lane, already-submitted job, unrepaired auth, and failed write probe. Inspect the real disposable task after recovery. |

No automatic retries are enabled until both the retained recovery state and off-host notification path pass. Simulated failures in a real disposable stream are labelled fault-injection results, not claims that real accounts expired or quota was exhausted.

### Rollout and rebase

After each stack, run the focused red/green cases, the full offline suite, and its named real disposable-stream check. Retain exact source and dependency revisions with the observations. A test that does not reproduce on baseline is not evidence that a regression was fixed.

After ZF's first-pass go-ahead and the verified stack lands on main, rebase all program and open feature branches onto the new main before streams-on-prime work. Do not port today's broken tick or template defaults. Existing-stream migration is explicit, source-backed, and separate from template upgrade. G14's harness-stream goal reset belongs to that authorized rollout, not this investigation.

## Decisions

| Decision | Reason and evidence |
|---|---|
| Apply Z1-Z5 over the original track brief. | The 09:22 SGT relay explicitly makes them binding. D2 and G4 are marked superseded in `03-decisions.md`. |
| Keep liveness and recovery as separate catalog items. | Z1 requires forward driving even with no new event. C rank 2 shows a different recovery predicate. |
| Use tick-observed 150k and the agent's own dump/resume prompt. | Z3 selects this policy. Do not keep a competing 252k request hook or quietly turn 150k into a hard ceiling. |
| Reuse safe-point steering, then compact only when idle. | The installed agent loop admits steering after tool batches. Native manual compaction aborts active work. |
| Add a small pi-web idle/checkpoint guard, not a native Pi core hook. | A status-then-compact race can interrupt a direct prompt. Z3 does not require per-request compaction. |
| Land receiving-side stop invalidation before any automatic RESUME. | The adversarial review demonstrated that stopping a runtime does not prevent a later prompt reopening it. Sender-side checks alone leave a race. |
| Persist accepted maintenance-time input and reconcile it before old RESUME. | The existing compaction Map is volatile and drains independently. Its acceptance does not establish durability or stop ordering. |
| Give verification a private XDG home as well as an explicit index. | `init --home` registers the index under XDG. Shared XDG would let the production global timer discover the test stream. |
| Store only current drive, recovery, delivery, and maintenance facts in existing tick state. | These bounded operations need crash recovery. Z2 and P3 reject growing this into the research plan's general control engine. |
| Keep applied-steer receipts, but no per-ask completion ledger. | Z5 requires actual application. Z2 separately defers product lifecycle and self-grading. |
| Use ZF-only Slack DM and episode-based suppression. | Z4 chooses the destination and quiet behavior. Full-disk notices must originate off-host under G5. |
| Read "#37" as corpus row 37, not a GitHub issue. | G16 corrects the ambiguous original brief reference. GitHub #37 is the program's draft PR. |
| Retain archived raw evidence without restoring retired coordinators. | Both exact row-37 receipt hashes survive. The failing component is the live-path binding. |
| Refuse unsafe manual rotation instead of building queue/callback migration. | A demonstrates native busy protection and successful manual replay. Z3 removes routine replacement pressure. |
| Bind handovers to session identity and reuse atomic snapshot writes. | Both are low-blast-radius source-proven defects, independent of the deferred lifecycle design. |
| Keep STATE current without a size budget. | The frozen 10 MB example is recursive history. D1 rules out replacing it with another arbitrary cap. |
| Leave stream-owned files untouched by automatic migration. | `upgrade_stream` protects them. Historical caps, freezes, and current authority cannot be inferred safely from template bytes. |
| Keep Twingate repair in the box deployment, not pi-stack. | G15 names the faulty wrappers. They are not tracked host-CLI files at the base revision. |
| Treat claimed coverage as hypotheses, not prevented-row counts. | A corrects row 37 and row 72. C qualifies rows 54 and 75. No controlled treatment replay exists yet. |
| Write only this artifact and do not commit. | This is the requested handoff. Progress and decisions are retained here, and Grok Bot collects the file. |

### Investigation and interrogation record

Throughput checkpoint: n/a, read-only investigation.

The corpus, A, B, C, deep research, issue snapshots #33 through #36, the harness DECISIONS and ZF brief, and program documents 00 through 03 were read. Main was verified at `3acf0f0`. No production stream was prompted, steered, stopped, rotated, archived, or spawned.

Parent in-memory probes reproduced ten baseline facts without filesystem or network effects. An idle coordinator with empty pending gets no wake. An unchanged quota error blocks all recovery prompts. `ensure_coordinator` trusts an active registry row without checking runtime. `_resume_or_spawn` adopts a nonempty unrelated same-directory session. The ratification parser accepts a marker buried in history. A predecessor's role handover satisfies close for a successor. Worker role validation accepts `coordinator`. Existing config without an index row is not re-registered. Automatic commit begins with `git add -A`. One fresh stream hides a stale neighbor. Exact archived receipt hashes and the frozen STATE blob size were checked separately.

The proposed post-fix tests and real-stream checks have not run because no fixes are implemented. No full test-suite or deployment pass is claimed.

Laziness Protocol changed the design to deletion-first defaults, existing tick phases, and refusal at unsafe rotation rather than a transfer subsystem. Fix Root Causes kept the continuation predicate, recovery circularity, evidence locator, and Git staging operation separate. Guard the Context Window split the source audit into read-only slices. Sequence Work into Verifiable Units shaped the small commit stacks. Prove It Works prevented accepting transport responses, file-size changes, or workflow dispatch receipts as completion.

### Adversarial review and lead judgment

A single `poteto-agent` reviewer on `openai-codex/gpt-6.1-sol` reviewed all 15 items against the source and binding calls. This is same-model adversarial review, not multi-model consensus. The first review attempt could not obtain a readiness handshake and was not counted. After an explicit readiness reply, retained review run `f9d54e5a-962f-487c-b752-98c43a98c7ac` returned a substantive review. The workflow wrapper had returned launch receipts before its children finished, so the parent consumed each actual terminal report instead.

The review challenged every item's layer and admission bar. It defended the bounded drive, recovery, delivery, and maintenance records rather than requiring a general engine. It also confirmed the source-derived handover and atomic-write fixes clear the low-blast-radius bar. It rejected carrying forward the superseded 252k hook, treating body delivery as application, or interpreting archived evidence as lost bytes.

| Finding | Lead judgment and correction |
|---|---|
| W1. A stop can race an already-selected automatic prompt, and the safety work was scheduled after S3. | **Act on.** Item 7 now requires receiving-side generation validation for every automatic wake, recovery, and RESUME. S2 lands this before S3. Race tests retain explicit new user prompting after stop. |
| W2. Accepted compaction-time input is only in memory and may drain before the saved resume. | **Act on.** Item 3 now requires recoverable maintenance-time input identity/body/order/attachments and receiving-side reconciliation of newer input before old RESUME. Crash-during-compaction and newer-stop tests were added to the plan. |
| W3. A private index without private XDG is discoverable by the production timer. | **Act on.** The real-stream recipe now isolates XDG for every CLI and private unit, sets an explicit verification pi-web destination, and checks unchanged production homes bytes. |

No warning was dismissed as style. No critical finding was established. These corrections change the implementation specification only. They are not a claim that the proposed race or deployment tests have already passed.

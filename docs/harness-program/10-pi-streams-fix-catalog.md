# Pi-streams must-fix catalog

## Review tables

Stable item numbers let ZF amend a row without renumbering the plan. Each item belongs to exactly one Z10 class.

### A. Mechanical failures

| # | Fix | Symptom with corpus rows | LAYER | Blast radius | ZF-call? | Order |
|---|---|---|---|---|---|---|
| 1 | While driven and stalled, always re-inject `/poteto-mode <current goal>`. | Event-only tick leaves ZF as the clock. F1, rows 3, 26, 34, 39, 40, 51, 55, 59, 60, 64. | LAYER 3 | **Med.** Tick, drive switch, prompt renderer/adapter, health checks. No stall-cause engine. | No. Z6 replaces Z1's design. | S4. |
| 2 | Break circular usage-limit recovery; route the other four classes to Z11. | Reset or repaired auth still needs human continuation. F7, rows 13, 17, 23-25, 47, 52-53, 63, 67. | LAYER 3 | **Med.** Usage-reset retry plus typed handoff and quiet off-host alerts. | No. G5 is narrowed by Z11. | S5. |
| 3 | At 150k, sync artifacts, compact the same session, and run a fixed engine resume template. | Directly driven coordinators overrun; free-form pickup can drift. F6, rows 11, 16, 32, 69, 71. | LAYER 3 | **Med.** Tick DCR, pi-web idle boundary, fixed path/goal renderer. | No. Z8 refines Z3. | S3. |
| 5 | Resolve exact evidence after archive relocation. | Corpus row 37's retired live path fails although bytes survive. A rank 2, G16. | LAYER 3 | **Low to med.** One evidence adapter and tests. | No. | S2. |
| 7 | Acknowledge a steer only after consumption and application. | Transport acceptance is presented as delivery. F8, rows 21, 35, 72-73. | LAYER 3 | **Med.** CLI, receipts, bot caller, stop-safe admission. | No. Z5. | S2. |
| 8 | Resolve one explicitly designated coordinator ID everywhere. | Old fcf ID and arbitrary same-directory adoption. Rows 51-53, 55, 72; issue #36. | LAYER 3 | **Low to med.** Registry, tick, status and doctor. | No. | S2. |
| 9 | Reuse Twingate instead of restarting it on every call. | SSH banner timeouts. G15, outside the 75-row corpus. | LAYER 3 | **Low.** Grok Bot box wrappers, not the host CLI. | No. | External prerequisite. |
| 11 | Remove routine rotation and refuse unsafe explicit replacement. | Identity churn and manual queue transfer. Rows 16, 32, 37, 71-72. | LAYER 3 | **Low to med.** Wake/rotation path and pickup references. | No. Same-session DCR is selected. | S2. |
| 14 | Bind handovers to session ID, not a reusable role. | Source-derived stale-handover close bug, companion to row 37. | LAYER 1 | **Low.** Brief/rendering, close, stream skill. | No. | S1. |
| 15 | Atomically publish registries and repair interrupted registration. | Source-derived partial-write and create-retry holes; issue #36's drift is related. | LAYER 3 | **Low.** Existing writers and retry tests. | No. | S1. |
| 18 | Park environment failures at last-good turn IDs; human-ratified fork/DCR, then wipe originals. | Auth, disk and outage handling creates noise and drift. F7 rows 13, 17, 24, 47, 63; Z11. | LAYER 3 | **High, mandatory.** Exact fork boundary, per-session markers, fixed DCR, narrowly scoped deletion. | No. Z11 selects it; backend capability must be verified. | S6. |

### B. Artifact health

| # | Fix | Symptom with corpus rows | LAYER | Blast radius | ZF-call? | Order |
|---|---|---|---|---|---|---|
| 4 | Remove budget and guard defaults at their source. | Invented guards and killed runs. F3, rows 10, 44-45; D1/#33. | LAYER 2 | **Low.** Default text and regression checks. | No. D1. | S1. |
| 6 | Retire STATE for append-only ACTIONS, keeping 30 entries and tick-rotating overflow to history. | Every-turn history pile. A rank 3, F6; artifact map §per stream. | LAYER 3 | **Med.** Append/rotation engine first, then protected files, templates and skills. | No. Z9/G17 fix names and count. | S1. |
| 10 | Keep one mutable North Star GOAL and coordinator-editable CURRENT in STREAM. | Charter amendments and execution state bury the goal. F12 rows 27, 30, 38, 75; map reports 654 at 66 KB. | LAYER 3 | **Low to med.** Charter parser/CURRENT update, then template and kickoff wording. | No. Z7/G17. | S1. |
| 12 | Rotate history out of TODO/PLAN and make context/README an index; retire duplicate ledgers. | Map's full-read 654 load is about 1 MB; invented ALERTS.md and decisions.tsv duplicate records. | LAYER 3 | **Med.** Stream-scoped artifact maintenance, overlay integration, context layout. | No. Rotate, do not add numeric resource caps. | S1 and S3. |
| 13 | Stop automatic Git capture of binaries/data. | Tick committed scratch. F11, row 29. | LAYER 3 | **Low.** Exact-path staging and ignore layout. | No. | S1. |
| 16 | Add idempotent per-stream migration with one commit and no worker-worktree writes. | New templates alone cannot repair existing STATE/charter/history piles. Map, A/B, Z9/G17. | LAYER 3 | **Med.** `migrate` CLI, stream-owned artifacts and migration tests. | No. Required rollout step. | S2a. |
| 17 | Give large log/output areas an owner and archive/cleanup handoff. | Map reports 654 log/ at 34 GB and analysis/ at 47 GB, despite small tick logs. | LAYER 3 | **Low to med.** Inventory/report and output placement. No automatic data deletion. | No. Actual destructive cleanup stays separately authorized. | S1 and rollout. |

## Scope and evidence

This is an implementation catalog, not an implementation. The t212u text in `00b-zf-messages-verbatim.md`, Z6-Z10, and G17 in `03-decisions.md` govern this amendment. They supersede the earlier disposition-based liveness design and agent-written resume prompt. The full t209u text is now available in 00b, so the old transport gap in 00 is not guessed or treated as a continuing evidence gap.

Z6 selects unconditional goal re-injection when driven and stalled, without identifying its cause. Z8 selects a fixed code-owned DCR resume template. Z9/G17 retire STATE, name ACTIONS and history/, fix the count at 30 entries, and define STREAM's GOAL/CURRENT roles. The 150,000 tick trigger remains. The superseded 252k request-boundary proposal does not return.

All source citations refer to pi-stack `3acf0f01e6084a317b89cef3a86f4781e60877cf` unless a dependency or stream root is named. In item details, `engine/`, `templates/`, and `tests/` are under `pi-streams/`. Bare engine filenames such as `tick.py` mean `pi-streams/engine/tick.py`. `E/` means `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`. Row numbers refer to `E/context/stall-corpus-2026-10-22.md`, not GitHub issues. A, B, and C mean the dated interrogation reports under `E/context/interrogations/`. Research means `E/context/research/deep-research-2026-10-23.md`. `Q/` means `/home/alphalab/Projects/alphalab/streams/qslite-654-datapull/` for the stream-owned incident checker and evidence.

Installed dependency observations are separate from that Git pin. `W/` means `/home/alphalab/.local/share/pi-node/node-v22.23.1-linux-x64/lib/node_modules/@jmfederico/pi-web/`, version `1.202607.3`. `N/` means its `node_modules/@earendil-works/pi-coding-agent/dist/core/`, Pi `0.82.1`. The installed package metadata identifies `jmfederico/pi-web` as the owner. Its source maps identify `src/server/sessions/{sessionCommandService,piSessionService,sessionRoutes,sessionArchiveStore}.ts`. Pin the matching upstream source revision before changing those files. Never edit installed `dist` as the delivery method.

The bar is a small correction or a change required for the dictated MVP. Items 1, 2, 3, 6, 7, 16, and 18 meet the second bar even where integration crosses repositories. Item 18 is honestly high blast radius because it deletes original sessions; it is included because Z11 requires it, not because deletion is a small patch. They are not represented as one-line fixes. The remaining items remove concrete contradictory defaults or repair existing boundaries.

Historical claims are not assumed current. A's verified `c146285:STATE.md` was 10,195,068 bytes and 165,597 lines. The newer `11-artifact-map.md` reports 654 STATE at 19 KB. Its larger current pickup problem is TODO 465 KB, PLAN 255 KB, context/README 212 KB, STREAM 66 KB, and STATE 19 KB, about 1 MB if read in full. These are map observations, not a new live measurement or proof that 250k tokens entered a request. The map also reports invented ALERTS.md at 294 KB, log/ at 34 GB, and analysis/ at 47 GB.

### Implementation boundaries

Keep a driven/paused switch, correlated delivery and DCR progress, and the small G5 recovery record. Delete the proposed runnable/wait/done turn-disposition requirement as a condition for Z6 re-injection. Do not build a stall-cause classifier, canonical control engine, ask ledger, or workflow definition.

The current goal has one code-owned resolver. It reads the nonempty CURRENT paragraph in STREAM.md, falling back to GOAL. GOAL is the stream's one mutable North Star, never a completed/uncompleted flag. Objective completion may change CURRENT or end a drive run without completing the North Star.

The engine owns the Z6 prompt and Z8 fixed DCR template, the ACTIONS append/rotation API, and migration. Then templates and skills name the implemented commands and artifact paths. A rule asking the agent to remember these policies is not their enforcement.

Keep engine state in existing configuration/tick state and the narrow receiving-side operation record. ACTIONS and history are human-readable work/failure summaries, not a replayable command engine. Index ALERTS remains the notification route. It is not a stream-local ALERTS.md. Protect live control records and referenced evidence from cleanup. No database, second daemon, history_full/history_index file, empty Git-commit history store, or mandatory per-ask ledger is included.

## Per-item detail

### 1. Drive-mode goal re-injection, without stall-cause detection

**Symptom and evidence.** F1 rows 3, 26, 34, 39, 40, 51, 55, 59, 60, and 64. C rank 1 identifies the event-only wake gap. Z6 now specifies its remedy, replacing this catalog's earlier runnable/wait/done disposition design.

**Root cause.** `tick.py:317-339` does not observe the coordinator's own stalled/settled state. `:435-445` requires pending events and suppresses an out coordinator. The five-minute timer already exists at `systemd/pi-streams-tick.timer:4-6`. `prompts/poteto.md:1-5` loads process but does not implement the requested goal-bearing command contract.

**Fix.** Code the rule first. While the explicit stream drive switch is on, whenever the tick observes a stalled session or stream, re-inject exactly `/poteto-mode <current goal>` into the designated stream coordinator. Resolve current goal from STREAM's CURRENT, falling back to GOAL, through item 10's single parser. Worker stalls are reported to that coordinator for stream-level remedy, not repaired by blindly replaying a worker's old command.

A settled/idle runtime or an explicit runtime stall indication is an observable trigger, not a diagnosis. Do not infer death from file mtime or kill a running tool because its output is unchanged. Reuse the actual busy flags. Once a stall is observed, do not branch on quota, auth, disk, missing disposition, pending-event count, or a claimed completion of the North Star. Always re-inject while driven. Do not require the coordinator to produce a new control record before receiving the prompt. G5 remains a separate stream-level recovery policy, never an `out()` veto on this branch.

Reassert one correlated outstanding injection per stream/current-goal revision rather than growing identical queued copies. This is transport coalescing, not cause-based suppression. Re-injection requests current-goal reconciliation, not repetition of an external job. G5 still prohibits duplicate uncertain jobs and gates the actual saved-step retry. Repeated quota failures do not create repeated blocker notifications.

Implement the literal `/poteto-mode <goal>` command in the harness adapter. Do not assume `/poteto` or a silently ignored slash command forwards arguments. Its thin alias must load the installed poteto-mode skill and preserve the full goal, including multiline content and punctuation. Test the expanded model input, not just the submitted string. Native Pi expands leading commands only; a slash invocation after the DCR read-path instructions must be explicitly expanded/invoked by the engine adapter without dropping either those instructions or the goal. Use a control-input path that does not treat the injected goal as a human answer or void `pendingAsk`; the current ordinary prompt path does void open asks. The coordinator can then keep a genuine task prohibition while autonomously remedying stream problems.

Turning drive off or an explicit native stop invalidates stale automatic admissions at the receiver. This is a drive switch/delivery generation, not stall-cause detection. A completed current objective can end that drive run or select another CURRENT; it never marks GOAL completed. Fresh explicit user input remains allowed. Preserve the prior stop-versus-in-flight-prompt race test.

Isolate worker/status failures so one unavailable observation cannot skip another stream's reinjection or ACTIONS rotation. Bound boundary I/O and avoid all-stream locks through network/Git waits. An unknown owner is not permission to start another writer. Correct doctor's any-fresh-stream shortcut at `doctor.py:179-195`. Report requested progress and new blockers, not a DM per tick.

**Layer.** LAYER 3 owns drive observation, the prompt renderer, and automatic admission. LAYER 2 tests the literal rule and expanded goal. Stronger static layers cannot run a future coordinator turn. Implement those code paths first, then name them in LAYER 4 AGENTS and LAYER 5 skills. Those texts cannot supply a clock or fix the event-only return.

**Blast radius.** Medium. `engine/{tick,project,cli,piweb,doctor}.py`, a small command alias/control-input adapter, and tests, followed by templates/skills. No stall classifier, remedy engine, or per-ask lifecycle.

**Verification.** Baseline produces no prompt for an idle coordinator with empty pending. Candidate emits the same goal-bearing injection for idle, quota, auth, disk-error, and missing-disposition fixtures while driven. Assert no cause-specific branch changes the payload. A stalled worker targets its coordinator. Verify CURRENT fallback, runtime skill expansion, pending-ask preservation, unchanged North Star after objective completion, off-drive suppression, coalesced retries, and a stop racing admission. In the disposable stream, finish two tiny work steps across a stall without a human nudge. Observation errors must not mask another ready stream.

**Dependencies.** Items 7, 8, 10, 11, and 15. Item 3 coalesces its DCR with ordinary reinjection. Item 2 is separate, not an eligibility dependency for Z6.

### 2. Usage-limit recovery and the narrowed five-class contract

**Symptom and evidence.** F7 rows 13, 17, 23, 24, 25, 47, 52, 53, 63, and 67. Rows 25 and 53 specifically need an external "reset, continue" after availability returns. C rank 2 reproduces the circularity. Research Q9 supports preserving existing provider error metadata rather than adding Codex app-server solely to poll it.

**Root cause.** `tick.py:347-367` calls every assistant error an outage and uses `waiting_quota` for workers. It clears the outage only after a later non-error assistant entry. `:435-440` suppresses prompts to an out coordinator. `sessionlog.py:13-21,45-56` exposes only the last assistant message. Existing `test_tick_outage.py:63-118,135-187` injects a human Continue and a successful reply before expecting recovery. Tool logout inside a normal assistant turn and the tick's own ENOSPC are different paths and can be missed.

**Fix.** Keep all five classes explicit, but apply Z11's narrowing of G5. Only the usage limit retains automatic wait-and-retry. Classes 2-5 park for human repair and ratified F-DCR under item 18. Do not retain this catalog's older automatic sign-in/tool/write-readiness resumes as operative policy. Z6's driven-stall reinjection remains cause-independent and goes through the stream recovery boundary; it is not permission for a parked session to mutate the environment or retry a job.

| Class | Park and alert | Release and retry |
|---|---|---|
| Codex usage limit | Retain reset time, affected continuation, and job identity. | At the reset time, permit one saved-step retry without requiring a prior successful assistant reply. Persist that attempt before dispatch. Reconcile uncertain external effects first. If it fails again, re-park until new valid retry/reset evidence. A restart must not replenish the same attempt. Missing reset metadata is an explicit unknown, not permission for an immediate retry. |
| Expired Codex login | Save the affected sessions' last-good IDs, park, and alert once. Never touch credentials. | Human repair plus a ratified notice starts item 18's F-DCR. Login-file mtime or an unrelated successful reply is not release. |
| Tool login expiry | Park the affected lane and preserve submitted job IDs; do not block independent authorized lanes. | Human repair and ratification, then F-DCR. Reconcile already-submitted jobs before the fork performs further task effects. |
| Full disk/resource exhaustion | Save last-good markers if possible; off-host alert names path/owner or explicitly unknown. No cleanup or new caps. | Human fixes the environment and ratifies. F-DCR must not erase evidence or originals before its fork streams. A local write probe alone is not authorization. |
| Other model errors/outages | Keep the specific label and last-good ID, not generic `waiting_quota`. | Park and use the ratified F-DCR path. No blind generic retry or autonomous environment repair. |

Across all five, never switch provider or model, never re-run an uncertain job, and never resume cancelled or gated work. Recovery resumes reconciliation of the saved step, not replay of an arbitrary shell command. If an external job has no safe status query or idempotency, leave that effect uncertain and report it instead of duplicating it.

Require item 7's receiving-side generation check for recovery admission as well. A stop after readiness was checked still prevents the stale retry from running.

Retain allowlisted provider, error class, retry/reset time, observation time, and affected session. Do not persist raw headers, account identifiers, or credentials. A small adapter can retain reset metadata already parsed by the installed provider. Text parsing is an explicit fallback, not an invented account-readiness API.

**Alert route, Z4.** Alerts and waits go through the existing Grok Bot's off-host deployment to ZF's Slack DM only. The exact message format is `<stream-id>:: <message>`. Do not send to BossOps. Retain an episode ID until the bot records successful Slack delivery. One blocker episode gets one blocker notification and at most one recovery notification. Unchanged waits produce no recurring DM. Transport retries use the same episode and delivery identity. A failed attempt is not a delivered alert. If Slack may have accepted a message but its reply was lost, reconcile the remote message identity before resending. Do not claim that a local episode ID alone prevents duplicate Slack messages.

The bot observes both typed ALERTS and failure or absence of a completed tick pass. This keeps full-disk or dead-tick notification independent of host writes and the exhausted Codex pool. Do not require another model call to send the DM. Resolve ZF's Slack destination through the deployment's existing identity binding, not a guessed username or a new credential flow.

**Layer.** LAYER 3 owns the separate stream failure boundary, usage-reset trial, and off-host notification routine. It is not a classifier in Z6's generic reinjection branch. LAYER 1 stores stable episode and job identities. LAYER 2 proves retries and suppression, but cannot observe restored login or disk writes in deployment. A skill telling the failed coordinator to alert cannot work when that coordinator cannot run.

**Blast radius.** Medium. `engine/tick.py`, `sessionlog.py`, error metadata at the provider or pi-web adapter, outage tests, and the bot-side ALERTS/Slack routine. The latter is outside this checkout. Its owning deployment source must be located before implementation. No new monitoring service is proposed.

**Verification.** Keep the last assistant error unchanged and advance a controlled usage-reset clock. Candidate makes one saved-step retry where baseline makes none, then re-parks on another failure. For each other class, readiness without human ratification must not auto-resume; it hands off to item 18 with preserved job identities. Cover a tool-auth failure inside a normal turn, cancellation, and an uncertain submitted job. Simulate ENOSPC only in a disposable faulting directory or private filesystem. Verify one exact-format ZF-only DM, no BossOps message or unchanged-wait repeats, and at most one recovery DM. Local ALERTS bytes do not certify Slack delivery.

**Dependencies.** Items 7 and 8, plus item 9 for off-host access. Share the drive-admission boundary from item 1, but never make G5 classification a prerequisite for Z6 injection. No ZF policy call is needed. The operator stop-and-report rule still applies to these program sessions.

### 3. Fixed-template DCR at tick-observed 150k

**Symptom and evidence.** F6 rows 11, 16, 32, 69, and 71. A rank 1 shows an uninterrupted coordinator run crossing 252k and continuing near 481k. That historical observation supports earlier maintenance, not retaining the superseded 252k policy.

**Root cause.** `tick.py:317-339` does not make a coordinator-context observation. `:447-479` either queues a follow-up to a streaming coordinator or uses the old 60k/six-hour rotation rule. Direct `pi-web-cli prompt` calls bypass that decision. `engine/piweb.py:75-86` and `bin/pi-web-cli:101-111` have prompt and archive adapters but no command-run adapter for native compaction.

The installed integration provides the needed primitives, with two important gaps. `W/dist/server/sessions/sessionRoutes.js:318-326` exposes `POST /api/sessions/:id/commands/run`. `sessionCommandService.js:78-96` starts native compaction asynchronously and returns "Compaction started" before success. `N/agent-session.js:1367-1370` aborts the active operation before manual compaction. Therefore do not issue `/compact` to a busy session or mistake command acceptance for completed compaction. Sending `/compact` as ordinary `/prompt` text is not the verified built-in-command path.

**Fix.** Implement Z8 as one fixed engine operation. Tick-observed coordinator context of at least 150,000 during a turn triggers DCR, irrespective of whether a browser, CLI, bot, or tick started the turn. Coalesce repeated observations into the same operation.

1. **SYNC/DUMP.** At a native safe steering boundary, the coordinator synchronizes stream state into STREAM's CURRENT, ACTIONS, TODO/PLAN when present, relevant progress artifacts, and the short context index. It does not author a resume prompt. It appends completed work/failure summaries through item 6's engine append command, never prunes ACTIONS itself. A ready receipt identifies the operation and artifact revisions. After the coordinator yields normally, bind the receipt to its actual terminal leaf, not a guessed future final-response ID. Run the ACTIONS overflow operation before the resumed read.
2. **COMPACT.** Compact the same idle session through the command API. Retain the atomic idle/expected-leaf precondition so a direct prompt racing this step is not aborted. An HTTP command-start receipt is not compaction completion. Failed compaction leaves the synced artifacts and phase intact; it does not authorize forced rotation or provider switching.
3. **RESUME.** After a successful native compaction entry, the engine renders the fixed template below using absolute paths and CURRENT, falling back to GOAL. Re-read the goal at admission so a CURRENT change during compaction is not replaced by a stale cached string. Compare the current drive generation and admitted-input sequence. A new stop disables that automatic admission. Preserve and reconcile newer direct input before admitting an obsolete objective. The coordinator resumes in the same session with code-owned instructions, not an agent-written free-form prompt.

The fixed template belongs in `engine/tick.py` or a small imported engine prompt renderer. Optional-file lines are included only when those paths exist. This is the rendered contract, not a new skill:

```text
Read the current stream artifacts before acting:
- {stream_dir}/STREAM.md
- {stream_dir}/ACTIONS.md
- {stream_dir}/TODO.md
- {stream_dir}/PLAN.md
- {stream_dir}/context/README.md
Open a DECISIONS or history file only when current artifacts reference it.
Historical work/failure entries do not override the current charter.
/poteto-mode {current_goal}
```

Do not load the history directory wholesale or the old STATE. Do not render full TODO/PLAN history back into this template. Item 12 repairs those files at their source. Free-length ACTIONS bodies mean the 30-entry policy is not a token ceiling; measure the resulting read load rather than add an unrequested body budget.

Keep the prior intake safety corrections. The compaction-time queue is an in-memory Map at `W/dist/server/sessions/piSessionService.js:317,1371-1376`, drains independently at `:2483-2525`, and is cleared at `:502`. Accepted input needs recoverable identity, exact body, order/kind, and attachment references in the narrow receiving-side maintenance record. Do not race its drain with a separate stale RESUME. Tick state references that operation ID rather than owning another input queue.

Advance ready phases through the existing `agent_end`/`compaction_end` path at `W/dist/server/sessions/piSessionService.js:2478-2490`; do not impose an extra five-minute delay per phase. Later ticks reconcile crashes. Persist phase before dispatch and use the native transcript to discover an already-completed compaction. The same fixed template applies on retry, with the current goal re-resolved. No general workflow engine is added.

**Direct prompts are covered by observation.** The tick resolves the actual coordinator and checks it regardless of whether its turn came from a tick, browser, CLI, or bot. Safe-point steering is already part of the installed agent loop at `W/node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js:88-169`. The check is per tick, not per model request. A long in-flight call or tool can exceed 150k before it yields. That is permitted by Z3's no-interruption requirement and must be reported honestly.

**Native hook decision.** No new native Pi request-boundary hook is needed for Z8's tick-triggered DCR. Reuse safe-point message admission and idle native `compact()`. A small pi-web command precondition and an observable compaction result are needed to close the direct-prompt race. They belong in pi-web source, not a monkeypatch of Pi core, a global model override, or an extension that calls aborting compaction inside an active tool loop. The existing installer returns early when pi-web is already present at `install.sh:466-468`. A normal pi-stack reinstall therefore does not deploy this dependency fix. Install the explicitly tested pi-web artifact for verification, expose its maintenance capability, and have doctor refuse automatic compaction until that capability is present.

**Layer.** LAYER 3 owns the trigger, ordering, fixed resume renderer, and native admission. Implement and test that code first, then update LAYER 4 AGENTS and LAYER 5 skills to name ACTIONS and the implemented sync step. LAYER 1 supplies the actual current-artifact layout. LAYER 2 can reject regressions but cannot compact a live runtime. No stronger static layer can guarantee the runtime ordering, and an agent-authored prompt would defeat Z8's fixed harness contract.

**Blast radius.** Medium. `engine/{tick,piweb,sessionlog,doctor}.py`, `bin/pi-web-cli`, coordinator templates, tick maintenance tests, and the small pi-web command boundary. Threads retain their existing Pi behavior. No fresh coordinator, provider switch, global reserve change, or transcript deletion.

**Verification.** Baseline has no 150k DCR or fixed artifact-loading resume. In the disposable stream, cross 150k during a direct turn while a benign tool spans a tick. Observe no tool abort, successful artifact sync, ACTIONS rotation, one native compaction, and the engine-rendered fixed prompt in the same SID. The prompt must contain absolute STREAM/ACTIONS/TODO paths, conditional PLAN/index paths, no STATE or agent-generated resume text, and the correctly expanded `/poteto-mode` goal. Test 149,999/150,000, CURRENT fallback and mutation during compaction, repeated ticks, a stop racing admission, failed summarization, accepted input surviving a restart during compaction, and crash after native success before observation. Check actual artifact reads and resumed task effects, not just the HTTP payload.

**Dependencies.** Items 6, 7, 8, 10, 11, 12, 15, and 16 for existing-stream rollout. Receiving-side admission safety precedes automatic RESUME. G5 may retain a failed maintenance operation without losing its phase, but does not become Z6 stall-cause detection.

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

### 6. Retire STATE for ACTIONS plus tick-rotated history

**Symptom and evidence.** A rank 3, F6 rows 11, 16, 32, and 71, and the new artifact map. The frozen 654 STATE reached 10,195,068 bytes, with 71 preserved-checkpoint headings. The map's current 19 KB STATE does not remove the every-turn history pattern or the separate TODO/PLAN/index load. Z9/G17 now choose an action log rather than this catalog's earlier rewritten current-view STATE.

**Root cause.** `templates/stream/AGENTS.md:4,8` reads STATE every turn and asks for a rewrite. `templates/stream/STATE.md:1-6` does not distinguish history. `threads.py:459-461` explicitly loads it at pickup. `project.py:24,703-749` protects the old artifact and normal upgrade cannot migrate its contents.

**Fix.** Implement the ACTIONS append/parser/rotation code first, in a small engine artifact helper called by the existing tick. Add an engine append command that takes the stream lock and writes one complete work/failure entry atomically. The contract is:

```text
### <UTC timestamp> <one-line commit-style subject>
<free body with the relevant context>
```

Append one entry for each completed piece of work or encountered failure mode. The agent never rewrites or prunes prior entries. Bodies are free length. The canonical append operation records accepted entry spans and disambiguates a body line that looks exactly like a timestamped entry delimiter. Do not guess boundaries from arbitrary headings or examples inside code fences. Keep only the 30 newest appended entries. This is G17's explicit record-count policy, not a default token/CPU/RAM/disk budget.

On every tick, before the pending-event/drive/outage gates, move the oldest overflow to `history/<YYYYMMDDTHHMMZ>-<slug>.md`, one file per entry. Convert entry timestamps to UTC for chronological names. Put a stable source-occurrence/hash suffix inside the slug so same-minute/same-subject entries do not overwrite each other. Two legitimate entries with identical content are still two occurrences, not a content-deduplication opportunity. Preserve exact entry bytes and append order. Do not use history_full, history_index, another Git repository, or empty Git commits as the history store.

Serialize append and overflow removal through the same short stream lock. Journal the planned source prefix and destinations in existing engine state, write/verify and synchronize destination bytes before trimming the prefix, then atomically publish and synchronize the 30-entry tail and directory metadata before acknowledging completion. Preserve a concurrently appended tail. Retry after a crash recognizes already-written files instead of duplicating them. Never overwrite a different history file or drop an incomplete/malformed entry to satisfy the count. Report that structural fault for stream-level repair. Do not claim this protects arbitrary bypass writes that ignore the canonical append API.

Only after code/tests exist, replace the STATE template with ACTIONS and a history directory. Change AGENTS steps 1/5 to read ACTIONS and append through the engine helper. Change `rotate_coordinator`'s opening to load STREAM/ACTIONS/current artifacts and resolve CURRENT/GOAL. Update every kickoff STATE reference, including Interview storage and the Plan step. Replace STATE with ACTIONS in `PROTECTED_STREAM_FILES`, protect the history prefix as stream-owned, and ensure ordinary new/upgrade never recreates retired STATE or overwrites ACTIONS/history. Existing STATE is retired only through item 16's explicit migration. Gate legacy create retries and ordinary upgrade on the artifact schema so they cannot seed an empty ACTIONS next to an unmigrated STATE.

**Layer.** LAYER 3 first enforces append serialization, the 30-entry count, every-tick movement, and crash-safe publication. LAYER 1 is the resulting ACTIONS/history layout. LAYER 2 checks byte preservation and counts. LAYER 4/5 instructions are downstream callers, not the rotation mechanism. Stronger static structure alone cannot rotate a deployed file on each tick or arbitrate concurrent appends.

**Blast radius.** Medium. `engine/{tick,project,threads,cli}.py`, a small proposed `engine/artifacts.py`, ACTIONS/history templates, coordinator instructions, stream/kickoff skills, and new artifact tests. No live worktree changes, transcript deletion, or generic log-retention engine.

**Verification.** Baseline has no ACTIONS cap/rotation. Test 0, 29, 30, 31, and many entries. Candidate retains the last 30 and one exact history file for every overflow entry, including same-minute duplicate subjects, Unicode, multiline bodies, and fenced fake headers. Test paused/outage/eventless ticks, concurrent append, destination collision, malformed final entry, and crash after history write but before tail publication. A retry produces identical bytes/names, not duplicate history. New stream, rotation pickup, kickoff and upgrade must contain ACTIONS and no live STATE read. Real disposable DCR must read ACTIONS only after overflow rotation.

**Dependencies.** Item 15's atomic writer and item 13's scoped commits. This code precedes templates/skills and item 3. Item 16 handles existing repositories.

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

All normal coordinator creation, adoption, replacement, tick targeting, and status use the same resolver. Adopt an existing nonempty session only by an explicit adoption operation. Recover a crash-created session only from the exact saved spawn attempt identity, not list order or newest timestamp. Save registry updates atomically through item 15. Reject duplicate session IDs and reserve the `coordinator` role from worker spawn/adopt, which currently accepts it at `threads.py:361-363,391,502`. Also enforce the actual first-line ratification marker before worker spawn/adopt side effects; `threads.py:127-137` currently scans historical prose and dispatch does not consult it. Keep unratified kickoff available. Do not convert idle workers to done. Registry lifecycle is not task acceptance.

For deployed fcf, first read the explicit replacement evidence and verify predecessor quiescence. Updating a row is not permission to resume its frozen work. Do not operate it as part of the disposable verification.

**Layer.** LAYER 3 validates runtime designation and dispatch. LAYER 1 keeps the one designation in the existing registry rather than STATE and bot caches. LAYER 2 tests ambiguity. Static repo shape cannot establish which runtime session is still live, so it cannot carry the whole fix.

**Blast radius.** Low to medium. `threads.py`, `tick.py`, `doctor.py`, status output, and new/adopt/rotation tests. No global session census, lease system, or arbitrary session adoption.

**Verification.** Baseline returns a stale active row without querying runtime. Candidate reports the mismatch and sends no prompt. Test two same-directory sessions, archived old plus designated live new, a crash after spawn before registry save, missing session, duplicate active coordinator rows, and an unratified stream or marker buried in history. Reject unratified worker dispatch before worktree or session effects. Every path must resolve one identical coordinator ID or refuse ambiguity. Repeat on the disposable stream after deliberate replacement.

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

### 10. One North Star and one coordinator-editable CURRENT

**Symptom and evidence.** F12 rows 27, 30, 38, and 75, B rank 1/3, and the artifact map's 66 KB 654 charter. STREAM amendments bury the actual goal. Z7/G17 now define the separation rather than a new ask ledger.

**Root cause.** `templates/stream/STREAM.md:1-25` has a GOAL but no CURRENT section. `skills/stream-kickoff/SKILL.md:40` makes the entire ratified file ZF-only. `threads.py:285-310` renders briefs from pointers without a shared current-objective reader. `templates/stream/AGENTS.md:5,7` also permits out-of-grant defaults and mandates matching new check scripts.

**Fix.** Implement one charter parser and a narrow CURRENT-update operation first. Support the real bare-uppercase section labels, not only Markdown headings. Exactly one GOAL is the mutable North Star. Exactly one CURRENT is a single paragraph describing the immediate objective. Missing/empty CURRENT on a legacy charter uses GOAL until migration, rather than creating a second goal source. The coordinator may replace only CURRENT in place; everything else, including GOAL and the ratification marker, remains ZF-only. The goal resolver returns nonempty CURRENT, otherwise GOAL. Reject duplicate/ambiguous sections rather than selecting an arbitrary last paragraph or a TODO item.

Both tick reinjection and DCR call this same resolver and bind the selected charter revision to admission. Do not mark GOAL completed/uncompleted. A current objective can finish, be replaced, or leave the stream paused while the North Star remains. Preserve explicit stops and NO-GO constraints. Re-injection is not permission to override them.

Only then update STREAM's template, AGENTS, worker brief, and kickoff Interview/Ratify/Plan wording. Move accreted amendment paragraphs into sourced DECISIONS records through item 16, while retaining their still-binding effect in the clean current charter. Do not merely hide an active freeze in cold history. Remove the out-of-authority "continue on the default" permission and requirement to invent a new check script for every small/artifact-only ask. Keep explicitly requested acceptance. This is not an independent-review policy.

**Layer.** LAYER 3 first provides a single parser, a CURRENT-only mutation boundary, and shared prompt construction. LAYER 1 is the charter's actual GOAL/CURRENT shape. LAYER 2 checks exact untouched section bytes. LAYER 4/5 wording follows the implemented interface. Stronger static structure alone cannot stop two runtime callers selecting different goals or validate a CURRENT-only update. Arbitrary semantic authorization remains a rule, not a claimed theorem.

**Blast radius.** Low to medium. `engine/{project,threads,tick,cli}.py`, a small shared artifact/goal reader, STREAM/coordinator/brief templates, kickoff/stream skills, and tests. Runtime ratification enforcement is retained in mechanical item 8, not counted twice here.

**Verification.** Baseline lacks CURRENT and the edit boundary. Candidate selects CURRENT, falls back for absent/empty CURRENT, rejects duplicate labels, preserves multiline/quoted goal bytes, and rejects a CURRENT update that changes GOAL, NO-GO, or ratification. Current-objective completion must not mutate the North Star into STOPPED/done. Kickoff respects the sole coordinator-editable exception and creates no unsolicited proof campaign. Real disposable tick and DCR must use the same CURRENT value. Migration preserves a live freeze while relocating old amendments.

**Dependencies.** Item 15's snapshot writer. This code precedes its template/skill callers, items 1/3, and item 16 migration. Per-ask lifecycle stays in track 3.

### 11. Remove routine rotation and refuse unsafe manual replacement

**Symptom and evidence.** F6 rows 16, 32, 37, 71, and 72. A shows that queue transfer was manual and all 20 saved bodies arrived. It also corrects issue #36's implication that archive itself necessarily killed active execution. Installed pi-web already refuses archive while streaming, compacting, running bash, or holding queued work.

**Root cause.** `tick.py:447-479` rotates on size or age. `project.py:56-60` supplies the 60k/six-hour defaults. `threads.py:446-462` has no coordinator checkpoint request or queue transfer and opens the successor with "Read STATE.md, then continue". The stubbed scenario in `tests/test_scenario.py:158-188` does not prove native archive safety or carry-forward.

**Fix.** Delete routine size/age rotation from ordinary wake selection. Reuse the same designated session and let item 3 handle context. Do not replace 60k with another rotation threshold or fixed compaction count. Retain explicit replacement for an intentional boundary. Z11's environment-failure recovery is the separate ratified fork/DCR/delete operation in item 18, not an excuse to use this generic rotate path.

Mark `docs/design/pi-streams-handover.md:3,20,26,92` as historical rather than an authoritative current pickup guide. It still says nothing is built and recommends fresh coordinators when large. Keep the original historical evidence, but do not seed that policy into new implementation sessions.

Manual rotation must not abort first to make archive possible. Retain native busy/queue refusal. Require a current coordinator-authored checkpoint and stable references to unfinished work before retirement. If queues or session-local native child callbacks still need the old owner, refuse rotation and explain the unresolved boundary. Do not build a general native-child adoption or queue migration subsystem in track 1. After successful retirement, create or explicitly adopt the successor using item 8, then load STREAM/ACTIONS/current artifacts with the shared CURRENT/GOAL resolver before calling rotation complete. No active pickup instruction may still request STATE. Persist enough existing rotation phase to recover archive-then-spawn failure.

**Layer.** LAYER 3 owns replacement and native refusal. LAYER 1 supplies the checkpoint. LAYER 2 checks crash boundaries but cannot prevent a deployed abort/archive. A handover skill cannot enforce the archive precondition.

**Blast radius.** Low to medium. `tick.py`, `threads.py`, obsolete warm configuration handling, the current design and historical-handover label, and rotation tests. Accept old config fields while ignoring their retired rotation behavior during migration. Do not silently assign them a different meaning. No automatic cleanup of old sessions or worktrees.

**Verification.** Baseline rotates an idle coordinator at 60k or six hours. Candidate does neither. Attempt manual rotation during a benign tool, queued steer, or unresolved callback and assert no abort, archive, or second coordinator. At a deliberate clean boundary, rotate once, retain exact evidence through item 5, and verify one successor. Crash after archive and recover without arbitrary adoption or duplicate opening prompts.

**Dependencies.** Items 5, 8, 14, and 15. Removal of routine rotation precedes items 1 and 3. General callback migration belongs to track 3 if it cannot remain a refusal.

### 12. Repair the other loaded artifacts and retire duplicate ledgers

**Symptom and evidence.** D7, Z10b, A rank 3, B rank 3, and the new artifact map. The map reports TODO 465 KB, PLAN 255 KB, context/README 212 KB, plus invented ALERTS.md 294 KB. ACTIONS alone cannot repair the roughly 1 MB full-read pickup load. These are byte observations, not measured input tokens.

**Root cause.** TODO and PLAN belong to `overlay/AGENTS.md:17-19`; their required reads are in `overlay/APPEND_SYSTEM.md:6-8`. They are not pi-streams templates. `templates/stream/AGENTS.md:4` makes context/README an every-turn read, while `project.py:417-429` seeds it as a short index. `templates/stream/DECISIONS.md:1` has no navigation structure. Per-stream ALERTS.md and decisions.tsv are not part of the shipped stream contract. Index `ALERTS` is real at `project.py:551-553`; the repository's historical root decisions.tsv is a different file and stays untouched.

**Fix.** Give each artifact one job, using item 6's history layout and item 3's SYNC trigger:

| Artifact | Current role and rotation decision |
|---|---|
| TODO.md | Overlay-owned current checklist, open owners/blockers, and pointers. Move completed narrative/checked-off history to one history file per identified completed section. Keep every unresolved task represented. |
| PLAN.md | Overlay-owned current execution plan only. Rotate explicitly superseded plans to history and retain the current plan and unresolved dependencies. |
| context/README.md | Entry-point index, not a diary or pasted reports. Move detail into named context/topic files and keep short descriptive paths. Topic indexes are read on demand, not recursively on every turn. |
| DECISIONS.md | Sourced rulings and the charter amendments moved here. Add section navigation and current-source links, not a second action log. Read relevant rulings on demand. Do not silently expire or revoke rules. |
| stream-local ALERTS.md | Migrate useful past failure notes into ACTIONS/history, and map live notification facts to the existing index ALERTS/episode route. Do not keep a competing active alert ledger. |
| stream-local decisions.tsv | Preserve imported source rows in cold owned history and carry current rulings into DECISIONS. Stop creating a second per-stream ledger. Do not touch identically named files outside the stream root. |

Implement a stream-scoped archive/rebuild helper with explicit source spans, exact-byte preservation, and current-file checks before changing overlay instructions. Closed TODO items and explicitly replaced plan sections are movable facts. Unmarked or mixed-status prose is not mechanically proved obsolete. A source-backed migration mapping supplies the current view; ambiguous blocks remain retained and reported for coordinator review, never silently dropped. No numeric byte/token/line or retention-age cap is introduced. Genuine open work can still be large; do not claim a hard context bound.

After that code exists, make the overlay's stream-specific behavior use current TODO/PLAN and ACTIONS for completed-work summaries. Keep ordinary non-stream progress/plan behavior unchanged. During DCR SYNC, update those actual files, rebuild the context entry index, and record reviewed artifact revisions. The fixed resume then reads those current files by path. Do not solve the problem with a small excerpt while leaving mandatory readers pointed at the same historical blobs.

Rule review is organizational maintenance, not failure-driven self-remediation. Under Z11 a failure must not cause new rules, skills, or memory policy. Explicit human-authorized rule changes belong in the ratified continuation. Constraint lifetimes and independent reviewer policy remain track 3.

**Layer.** LAYER 3 owns the stream-scoped archive/update command and DCR trigger. LAYER 1 makes the loaded files actual current views and moves historical detail out of mandatory reads. LAYER 2 proves open-task/source preservation and non-stream isolation. LAYER 4 overlay and LAYER 5 skill changes come after the code. Static layout alone cannot periodically reconcile a running stream's completed sections, while code cannot decide arbitrary prose is obsolete.

**Blast radius.** Medium. Stream artifact helper, DCR sync template, `overlay/{AGENTS,APPEND_SYSTEM}.md` with a stream-only exception, context template/seed, and tests. Migration touches only the stream folder, not any worker's TODO/PLAN or product repository.

**Verification.** Use a synthetic map-shaped fixture with long completed TODO/PLAN history and a diary-like context index. Baseline loads all retained history. Candidate preserves exact archived bytes, all open checklist items and current plan constraints, and current context links, while historical text is no longer a mandatory read. Test ambiguous mixed sections, both real index ALERTS and invented ALERTS.md, duplicate rulings, repeated maintenance, and unchanged non-stream overlay behavior. Inspect actual reads during disposable DCR rather than claim bytes/4 are tokens.

**Dependencies.** Items 6, 10, 15, and 16 for migration. Implement the helper before overlay/skill instructions. No new general ledger or default resource cap.

### 13. Stop automatic Git capture of binaries and data

**Symptom and evidence.** F11 row 29 records tick-committed DLLs and packages. C explicitly separates this from liveness and recovery.

**Root cause.** `project.py:522-527` runs `git add -A` for every automatic commit. `tick.py:548-563` applies that to each stream and can push it. The stream `.gitignore:1` ignores only `log/`. Human convention is not a staging boundary.

**Fix.** Remove whole-worktree auto-staging. Seed known harness files explicitly at creation. For later ticks, stage only known current-record paths and changes to already-approved code, docs, checks, and small reports. Leave arbitrary new worker output untracked. New report/check paths are explicitly approved by the owning coordinator, not discovered through `add -A`. Compute and commit only the approved path set, without absorbing unrelated pre-staged entries. Preserve the foreign index state. Refuse binary candidates in that set, including already tracked binary updates, without deleting data or resetting the user's index. A path allowlist and binary check cannot prove that arbitrary text contains no dataset, so do not advertise semantic data classification. Ignore standard scratch/output directories in the template as a secondary convenience.

Do not add a file-size budget. Git is for code, docs, and small reports, never data. Already tracked binary/data contamination needs an explicit cleanup change. Merely adding `.gitignore` does not untrack it and must not be claimed sufficient.

**Layer.** LAYER 3 fixes the automatic staging operation shared by new, tick, upgrade, and lifecycle commands. LAYER 1 places scratch outside tracked report paths. LAYER 2 tests and rejects bad staged content. Repo shape alone cannot stop the existing `add -A` from collecting arbitrary new output.

**Blast radius.** Low. `project.py`, `.gitignore`, and Git fixture tests in new/tick/upgrade suites. No production history rewrite, data deletion, branch pruning, or forced push.

**Verification.** Put a tiny fake DLL, package, and CSV in a disposable stream beside an updated ACTIONS and a deliberately staged Markdown report. Baseline commits all unignored files. Candidate commits only approved records/report and leaves data out. Also test an already-staged binary and an already-tracked binary update. Neither may slip through the automatic commit. Preserve bytes and the caller's index on refusal.

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

### 16. Migrate existing stream artifacts once, without worker-worktree writes

**Symptom and evidence.** The artifact map shows active STATE/charter/TODO/index piles that new templates cannot repair. A's historical 10 MB STATE and B's accreted charters are concrete precursors. Z9/G17 require an explicit existing-stream migration.

**Root cause.** `project.py:682-700` calls `copy_missing()` on create, and `:703-749` deliberately protects owned STATE/STREAM/DECISIONS/context during upgrade. It cannot transform content or delete retired STATE. Seeding an empty ACTIONS beside an old STATE would create two competing current artifacts. `cli.py:204-217` already enumerates registered stream roots, which is the correct migration selection boundary.

**Fix.** Add explicit `pi-streams migrate <id> --home <index>` with a plan/dry-run view, not a silent change to every ordinary upgrade. It operates on that registered stream root only. It does not follow thread worktree paths, repo lists, `.stream` pointers, or symlinks outside the root. No worker prompt, fork, worktree write, cleanup, or publication is part of migration.

Use one persisted migration identity and UTC start time, source file hashes, and a destination/write plan. Under the stream lock and artifact-writer barrier:

1. Split the original STATE at real level-two `##` headings outside code fences. Preserve the preamble, repeated headings, empty sections, and a no-heading file. Create one history file per section. Reconstructing section bytes in original order must match the source hash.
2. Use that section's identifiable Git introduction timestamp for the history prefix. A header's blame commit and its Git log timestamp can supply it. If section attribution is ambiguous, untracked, or unavailable, use the persisted migration time and mark the fallback. Do not use the newest whole-file commit or filesystem mtime as a fake section timestamp. Slug occurrence identities prevent collisions and make retries stable.
3. Verify all section files, seed ACTIONS with exactly one migration entry, and only then delete STATE. The entry links to retained provenance and gives counts, not a pasted STATE or full history index. Record the artifact schema/migration identity in engine-owned stream metadata so create/upgrade cannot later seed a misleading legacy layout.
4. Move identified STREAM amendment paragraphs into sourced DECISIONS entries, preserve the current ratified marker and all still-binding charter terms, and add exactly one CURRENT paragraph. GOAL remains the one North Star. Use a source-backed per-stream extraction map for messy charters. Do not guess that arbitrary text below `ratified:` is obsolete. If current authority cannot be recovered, refuse that stream's apply with a concrete report; Grok Bot resolves it from evidence, without a new ZF interview.
5. Apply item 12's rotation/rebuild mapping to stream-local TODO/PLAN and context/README, preserving all open work and current constraints. Archive clearly completed/superseded detail; retain ambiguous sections with an explicit review pointer. Preserve useful invented ALERTS.md/decisions.tsv content in the canonical destinations, then retire those duplicate stream-local files. Never apply this mapping to worker worktrees or the source repository's root decisions.tsv.
6. Make one scoped migration commit containing only approved stream paths, including the STATE deletion, ACTIONS/history, charter/decisions changes, and migration marker. Preserve unrelated staged changes. A second invocation makes no duplicate seed, amendment copy, history file, or commit. Resume interruptions from the recorded inputs/destinations, including a crash after commit but before local completion acknowledgement.

No TODO/PLAN byte cap or indiscriminate truncation is added. The chosen remedy is rotation of proven history plus preservation of all open work. Ambiguous semantic cleanup is reported, not treated as completed. Log data deletion is outside this migration, per item 17.

**Layer.** LAYER 3 owns explicit scope, lossless transformations, commit boundary, and idempotent retry. LAYER 1 is the new stream layout, with LAYER 2 reconstruction and path-fence tests. A template or skill cannot safely transform existing owned content or coordinate a crash halfway through migration. Code lands before instructions recommend running it.

**Blast radius.** Medium, stream-root only. `engine/{cli,project}.py`, the artifact helper, protected-file/schema handling, scoped Git helper, and proposed `test_artifact_migration.py`. No live threads' worktrees, provider configuration, auth, or existing session lifecycle is touched.

**Verification.** Baseline upgrade leaves STATE and never creates the requested history/current layout. Candidate migration preserves a synthetic large STATE byte-for-byte across sections, uses known section Git timestamps or a stable fallback, seeds one ACTIONS entry, deletes STATE only after verification, and extracts amendments without losing a freeze. Test preambles, duplicate/fenced headings, no headings, existing ACTIONS/history, unratified/ambiguous charters, unrelated staged files, path escapes, and crashes before/after deletion and commit. A second run adds zero commits. Hash every worker worktree fixture before/after and require equality. Run on the disposable stream before production rollout, not on any existing stream in this investigation.

**Dependencies.** Items 6, 10, 12, 13, and 15. All must exist before migration is offered. Ordinary upgrade continues protecting stream-owned artifacts.

### 17. Give large logs and outputs an owner without inventing cleanup authority

**Symptom and evidence.** `11-artifact-map.md` reports 654 log/ at 34 GB, analysis/ at 47 GB, and repeated message dumps around 19 MB, while native tick events remain at or below about 216 KB. F11 rows 17, 29, and 47 show the disk/Git consequences. The directory sizes are map observations, not measurements made by this amendment.

**Root cause.** `templates/stream/.gitignore:1` ignores log/ but defines no ownership or retrieval policy. `templates/thread-brief.md:7-11` constrains worker ownership but not ad hoc duplicate capture. `tick.py:290-302` owns events/tick-state; it does not own every file an agent puts under log/. Gitignore cannot prevent disk growth.

**Fix.** Add a stream-root artifact inventory that records metadata, owner, purpose, current references, and disposition candidates. Separate tick-state/events and active receipt/migration/rotation records from bulk worker outputs and copied transcripts. Normal health maintenance uses metadata only, not whole 34 GB reads, and does not walk or mutate worker worktrees through symlinks.

Stop default full-message/transcript copying when a stable source reference or selected exact evidence record suffices. Put future bulk job data in a named private, stream/worker-owned output area outside mandatory reads and Git, with handover pointers. Keep small source-bound reports and exact required evidence retrievable under D6 and item 5. Do not mistake an unreferenced file for safe-to-delete data.

For existing log/ and analysis/ growth, produce a source-backed ownership and proposed archive/cleanup list. Actual deletion, compression with evidence implications, retention ages, byte caps, and host cleanup are deferred pending explicit authorization. This is a stated limit, not a claim that inventory bounds disk usage. Z11 leaves physical environment repair to the human. Its explicit deletion of recovered original sessions is a separate narrowly scoped operation, not blanket permission to clean stream outputs.

**Layer.** LAYER 3 makes inventory and no-default-duplicate-capture behavior part of existing health maintenance. LAYER 1 separates current reports, evidence and bulk output. LAYER 2 checks path safety and zero deletion without authorization. CI or a directory name alone cannot identify a live output's owner, and a skill reminder cannot prevent the coded automatic capture path. Do not build a retention service.

**Blast radius.** Low to medium. Artifact inventory/helper, output/handover guidance, ignore/layout documentation, and tests. No resource guards, automatic data deletion, transcript purge, or new daemon.

**Verification.** A disposable sparse/metadata fixture represents large output trees, active control files, exact evidence, symlinks, and unknown ownership. Candidate inventories without reading payloads or deleting anything, identifies protected live state, and reports unknowns honestly. A new small job records an owned output reference without committing data or duplicating its whole transcript. Original evidence hashes still resolve. Baseline has no such ownership/current-read separation.

**Dependencies.** Items 5, 12, 13, and 15. Destructive cleanup is not an implementation prerequisite for Z6, DCR, or migration.

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

All work below is future work after the catalog's first-pass go-ahead. Start fresh branches above pi-stack main `3acf0f0`. Keep each implementation commit small and its regression test in the same commit. Show each new regression failing against the base before accepting its fix. Do not merge a partial liveness stack that depends on an unlanded safety boundary. Rows labelled pi-web or bot are companion PRs in their owning repositories, not commits mixed into a pi-stack PR. Their tested API/capability is a dependency of the corresponding pi-stack stack.

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

### Stack S1. Code-owned artifact operations, then their callers

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: publish snapshots and scope automatic commits` | `engine/{project,threads}.py`, create/persistence/Git tests. | Items 13/15. Short-write, retry, unrelated staged files, binary/data exclusion. |
| `streams: parse the charter and update CURRENT only` | Proposed `engine/artifacts.py`, `project.py`, charter tests. | Item 10. Real bare-label format, CURRENT/GOAL fallback, duplicate rejection, unchanged protected section bytes. |
| `streams: append and rotate ACTIONS under the stream lock` | Artifact helper, `engine/{cli,tick,project}.py`, protected-file/schema changes, proposed `test_action_rotation.py`. | Item 6. 30/31, identical occurrences, collisions, append races, crash durability, rotation on paused/outage/eventless ticks. |
| `streams: archive completed views and inventory bulk outputs` | Artifact helper, proposed artifact-health tests. | Items 12/17. Open-task preservation, index-only README, duplicate-ledger import, zero unauthorized data deletion. |
| `streams: teach the new artifact contract and remove bad defaults` | ACTIONS/history/STREAM templates, remove STATE template, AGENTS steps 1/5, kickoff Interview/Ratify/Plan, stream skill, stream-scoped overlay, design docs, literal tests. | Code already exists. New kickoff has no caps, CURRENT-only exception, real append command, no active STATE read, and unchanged non-stream overlay behavior. |
| `streams: bind handovers to full session identity` | Brief/rendering, close checks, stream skill, brief/close tests. | Item 14's predecessor/successor case and owned report reference. |

The ACTIONS/charter/health code precedes the template/skill commit. Do not activate legacy streams with a mixed STATE/ACTIONS layout. This stack does not itself migrate or resume an existing stream.

### Stack S2. Correct identity, receipts, archive reads, and rotation

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: resolve the designated coordinator before dispatch` | `engine/{threads,tick,doctor}.py`, new/adopt/status tests. | Item 8's stale and ambiguous identities. Verify one designated disposable coordinator. |
| `streams: expose archive-stable evidence reads` | `engine/{sessionlog,piweb}.py`, `bin/pi-web-cli` if needed, new evidence tests. Small pi-web metadata exposure only if needed. | Item 5's exact hashes before/after a safe disposable archive. |
| `streams: distinguish transport acceptance from applied steer` | `bin/pi-web-cli`, `engine/{piweb,tick,sessionlog}.py`, receipt command/tool, coordinator template, CLI/tick tests. | Item 7's accepted-only, consumed-only, applied, blocked, and uncertain cases. Inspect a real changed artifact. |
| `pi-web: reject stale automatic admissions after stop or cancel` | `jmfederico/pi-web` `src/server/sessions/piSessionService.ts`, narrow persisted control-delivery generation, matching CLI/engine adapter fields, and focused race tests. | Delay a wake, recovery, and RESUME after sender revalidation. Stop, release, and observe zero task effects. Fresh explicit input remains usable. |
| `streams: reuse coordinators and refuse unsafe explicit rotation` | `engine/{tick,threads,project}.py`, rotation/scenario tests, obsolete-policy docs. | Item 11. No size/age rotation, no busy abort, safe clean replacement and crash recovery. |

Update the bot relay's receipt handling in its owning deployment source alongside this stack. It must stop claiming a transport receipt is delivery. Land the CLI response semantics and caller changes together or version the added fields without breaking the caller.

### Stack S2a. Explicit existing-stream migration

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: plan a lossless stream-root artifact migration` | `engine/{cli,project}.py`, artifact helper, proposed `test_artifact_migration.py`. | Item 16. Exact STATE section reconstruction, section Git timestamps/fallback, charter extraction map, path/symlink fence. |
| `streams: apply migration once with one scoped commit` | Migration journal/schema marker, scoped Git helper, tests. | Crash before/after delete/commit, one seed, second-run zero commits, no duplicate amendments/history, unchanged worker-worktree hashes. |

Run this on the disposable stream before enabling DCR there. Real existing-stream migration is explicit after the first-pass go-ahead, per-stream evidence review, and tested code deployment. It never writes worker worktrees.

### Stack S3. Fixed-template DCR, code before instructions

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `pi-web: compact only at the expected idle checkpoint and retain maintenance input` | `jmfederico/pi-web` source `src/server/sessions/{sessionCommandService,piSessionService}.ts`, narrow persisted maintenance record, capability/result fields, and focused tests. No installed `dist` edits. | Busy/direct-input races, accepted input across a restart during compaction, and newer input before saved RESUME. A command-start reply must not pass as compaction completion. |
| `streams: add native command-run and compaction-result observation` | `bin/pi-web-cli`, `engine/{piweb,sessionlog,doctor}.py`, CLI/doctor tests. | Call the real command endpoint and identify one successful compaction entry. |
| `streams: implement argument-preserving poteto-mode invocation` | Engine/receiving adapter and installer capability checks, actual prompt-expansion tests. | Exact goal punctuation/newlines and loaded skill; fixed DCR read-path prefix survives the non-leading invocation. |
| `streams: sync compact and resume with the fixed 150k DCR template` | `engine/tick.py`, small code-owned prompt renderer, maintenance state/adapter tests. | Item 3. CURRENT/GOAL resolution, real artifact reads, no agent-written resume, same SID, no active-tool abort, changed CURRENT/stop/input races. |
| `streams: describe the implemented DCR sync in coordinator instructions` | AGENTS/skills and literal tests only after code is present. | SYNC updates CURRENT/ACTIONS/TODO/PLAN/index; no new failure-driven rules or skills. |

Build and install the exact tested pi-web artifact before enabling this stack, then require its maintenance capability in doctor. The current installer skips an existing pi-web, so merely reinstalling pi-stack is not this deployment step. Do not revive the superseded 252k native-hook work. Real verification must show no interruption of the running tool and actual resumed task progress.

### Stack S4. Make the existing tick a driver

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: re-inject the current goal whenever driven and stalled` | `engine/{project,cli,tick,piweb}.py`, shared goal/prompt renderer, tick tests. | Item 1. Identical injection across stall reasons and missing dispositions; no `out()`/pending-event veto; CURRENT fallback, worker-to-stream routing, preserved human ask. |
| `streams: isolate observations and report per-stream tick health` | `engine/{tick,doctor,piweb}.py`, failure/doctor tests, systemd pass reporting if needed. | One unavailable worker does not skip another reinjection or ACTIONS rotation. One healthy stream cannot hide a failed pass. |
| `streams: align generated drive instructions with the coded rule` | Coordinator/skill wording and literal tests after the reinjection code. | No next-action/disposition requirement, no session-level stall-remedy classifier, no North Star done flag. |

Reuse S2's receiving-side generation check for all driver admissions. Native stop/cancel invalidation is already present before S3, not postponed until this stack. Test the sender-check/stop/receiver-admission race before enabling automatic execution wakes. Tick receipt, maintenance, and registry prerequisites must already be present.

### Stack S5. Usage-reset recovery and quiet Slack notifications

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: retry a saved usage-limited step once at reset` | `engine/{tick,sessionlog}.py`, provider metadata adapter, outage tests. | Item 2. Unchanged assistant error, one saved-step reset trial, failed-trial restart does not replenish it. Other classes hand off to Z11, not automatic readiness resumes. |
| `bot: deliver blocker and recovery episodes to ZF DM` | Owning bot deployment's ALERTS reader, completed-pass observer, Slack delivery state/tests. `systemd/pi-streams-tick.service` only if the existing observer needs an exit-status signal. | Exact `<stream-id>:: <message>`, ZF only, no BossOps, one blocker and at most one recovery. ENOSPC notification originates off-host. |
| `streams: preserve stops and uncertain jobs across recovery` | Focused tests and existing adapters. | Cancelled/gated work and uncertain submitted jobs are not replayed by reinjection, reset retry, or the later fork. Auth/write readiness without ratification does not release Z11 parking. |

No automatic retries are enabled until both the retained recovery state and off-host notification path pass. Simulated failures in a real disposable stream are labelled fault-injection results, not claims that real accounts expired or quota was exhausted.

### Stack S6. Ratified environment-failure F-DCR

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: persist affected-session last-good failure markers` | Failure boundary/session reader, `failures/` protection, engine metadata and tests. | Item 18. Exact safe turn boundary, multiple simultaneous sessions, ENOSPC reporting, no environmental/rule/skill changes. |
| `pi-web: expose exact-point fork and single-original deletion` | Owning session adapter/CLI, backend capability and scope tests. | Verify Pi entry/turn mapping and tool-pair integrity. Prime needs its own capability proof before its port. No subtree deletion or worker-worktree writes. |
| `streams: run ratified fork DCR and wipe only after the fork streams` | Failure operation state, shared fixed DCR renderer, registry/receipt adapters, fault tests. | Human ratification, exact prefix, same fork through DCR, observed streaming before original wipe/marker removal, crashes and cancellation at every boundary. |
| `streams: teach park-and-log failure behavior` | Generated stream prompt and skills after the code contract. | No self-remedy of the harness environment; only explicitly ratified additional instructions enter continuation. |

No destructive operation is executed by this catalog task. The implementation must pass item 18's exact-scope and evidence-preservation tests on disposable sessions before production F-DCR is enabled.

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
| Store only current drive, recovery, delivery, and maintenance facts. | Tick state retains dispatch progress and operation IDs. Pi-web owns accepted maintenance input and native outcomes. Z2 and P3 reject a general control engine or competing input queues. |
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

No warning was dismissed as style. No critical finding was established. Focused recheck run `96d8d074-ec39-4378-9cca-135ee306920b` closed W1-W3 and found no new concrete issue in their corrections. The reviewer confirmed the single-operation event path does not create a competing input queue. These are catalog-specification verdicts only. They do not claim that implementation, race, or deployment tests have passed.

Final artifact checks confirmed all 15 review rows have matching symptom, root cause, fix, layer, blast radius, verification, and dependency details. Source stayed unchanged at `3acf0f0`, and no files were staged or committed. Other tracks' shared-doc changes were left untouched.

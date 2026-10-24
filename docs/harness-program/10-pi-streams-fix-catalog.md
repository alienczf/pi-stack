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
| 6 | Keep STATE Goals/Rules current; append only Log and tick-rotate beyond 30 entries. | Every-turn history pile. A rank 3, F6; Z15. | LAYER 3 | **Med.** Section-aware mutation and rotation, then templates/skills. | No. Z15 replaces earlier file names. | S1. |
| 10 | Resolve STATE Goals' current objective, falling back to its one mutable North Star. | Charter amendments bury the goal. F12 rows 27, 30, 38, 75; Z7/Z15. | LAYER 3 | **Low to med.** One goal resolver and narrow Goals updates. | No. Z15. | S1. |
| 12 | Load only AGENTS and STATE; replace stream TODO/PLAN with Goals plus Log. | Overlay and mandatory index/history reads bloat pickup. Artifact map; Z13-Z15. | LAYER 2 | **Low.** Tier regression tests, stream template/brief and conditional overlay. Invented files are untouched. | No. Z13/Z15. | S1. |
| 13 | Stop automatic Git capture of binaries/data. | Tick committed scratch. F11, row 29. | LAYER 3 | **Low.** Exact-path staging and ignore layout. | No. | S1. |
| 16 | Add idempotent per-stream migration with one commit and no worker-worktree writes. | New templates alone cannot repair existing STATE/charter/history piles. Map, A/B, Z9/Z15. | LAYER 3 | **Med.** `migrate` CLI, stream-owned artifacts and migration tests. | No. Required rollout step. | S2a. |

## Scope and evidence

GO at 11:35 SGT authorizes implementing this catalog. Z13-Z15 and G25 in `03-decisions.md`, plus t215u/t216u/t220u/t221u in `00b-zf-messages-verbatim.md`, govern the latest amendment. Z15 wins over Z14/G22 and G17/G21. This catalog defines the contract; actual implementation evidence is recorded separately in `12-track-1-progress.md`. Later calls already superseded disposition-gated liveness, agent-written resume, and automatic readiness release for G5 classes 2-5. The full t209u text is now available in 00b, so the old transport gap in 00 is not guessed or treated as a continuing evidence gap.

Z6 selects unconditional goal re-injection when driven and stalled, without identifying its cause. Z8 selects a fixed code-owned DCR resume template. Z15 replaces the earlier artifact split with STATE sections Goals, Rules, Log. Only Log is append-only and capped at 30 entries; the tick moves overflow to history/. Goals and Rules are rewritten in place. STREAM, GOAL, DECISIONS and ACTIONS files, and the separate CURRENT-section idea, are retired. The 150,000 tick trigger remains. The superseded 252k request-boundary proposal does not return. Z11 adds per-session failure parking, human repair and ratification, then fork/DCR and narrowly scoped original-session deletion. Usage limits alone retain automatic wait-and-retry. G18 keeps this MVP independent of track 3's timing or preferred design.

All source citations refer to pi-stack `3acf0f01e6084a317b89cef3a86f4781e60877cf` unless a dependency or stream root is named. In item details, `engine/`, `templates/`, and `tests/` are under `pi-streams/`. Bare engine filenames such as `tick.py` mean `pi-streams/engine/tick.py`. `E/` means `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`. Row numbers refer to `E/context/stall-corpus-2026-10-22.md`, not GitHub issues. A, B, and C mean the dated interrogation reports under `E/context/interrogations/`. Research means `E/context/research/deep-research-2026-10-23.md`. `Q/` means `/home/alphalab/Projects/alphalab/streams/qslite-654-datapull/` for the stream-owned incident checker and evidence.

Installed dependency observations are separate from that Git pin. `W/` means `/home/alphalab/.local/share/pi-node/node-v22.23.1-linux-x64/lib/node_modules/@jmfederico/pi-web/`, version `1.202607.3`. `N/` means its `node_modules/@earendil-works/pi-coding-agent/dist/core/`, Pi `0.82.1`. The installed package metadata identifies `jmfederico/pi-web` as the owner. Its source maps identify `src/server/sessions/{sessionCommandService,piSessionService,sessionRoutes,sessionArchiveStore}.ts`. Pin the matching upstream source revision before changing those files. Never edit installed `dist` as the delivery method.

The bar is a small correction or a change required for the dictated MVP. Items 1, 2, 3, 6, 7, 16, and 18 meet the second bar even where integration crosses repositories. Item 18 is honestly high blast radius because it deletes original sessions; it is included because Z11 requires it, not because deletion is a small patch. They are not represented as one-line fixes. The remaining items remove concrete contradictory defaults or repair existing boundaries.

Historical claims are not assumed current. A's verified `c146285:STATE.md` was 10,195,068 bytes and 165,597 lines. The later historical observation in `11-artifact-map.md` reports 654 STATE at 19 KB. Its then-observed pickup load includes TODO 465 KB, PLAN 255 KB, context/README 212 KB, STREAM 66 KB, and STATE 19 KB, about 1 MB if read in full. These are map observations, not a new live measurement or proof that 250k tokens entered a request. The map also reports invented ALERTS.md at 294 KB, log/ at 34 GB, and analysis/ at 47 GB.

### Current artifact contract under Z15

This is the implementation target, not a claim about deployed streams. The 17 current fixes comprise 11 mechanical fixes and 6 artifact fixes. Historical reviews below retain their original counts.

| Tier | Name | Sole concept and access |
|---|---|---|
| Every turn | `AGENTS.md` | Role and operating instructions. Read with STATE, not an additional planning ledger. |
| Every turn | `STATE.md` | Current Goals, active Rules, and recent Log in that order. The only always-loaded stream state. |
| On demand | `history/<UTC ts>-<slug>.md` | One cold entry per file. Rotated Log entries, retired rules, historical decisions, and migration provenance. |
| On demand | `context/` and `context/README.md` | Reference material and its index. The README is not a diary or a required turn read. |
| On demand | `checks/` | Acceptance checks and their small source-bound reports. |
| On demand | `handover/<role>/<full-session-id>.md` | One session's exit evidence. Never a role-reusable current-state file. |
| Engine-only | Index `streams.tsv`, `projects/<name>.toml`, and `homes` | Stream/project registration and discovery. Never read by agents. |
| Engine-only | `threads.tsv` | Session designation and runtime lifecycle. Never an agent-maintained task plan. |
| Engine-only | `subscriptions.tsv` | Tick watch definitions. Agent interaction uses the existing command boundary. |
| Engine-only | `stream.toml` | Stream identity, schema, and engine metadata. |
| Engine-only | `log/events.jsonl` and `log/tick-state.json` | Engine events and durable delivery/maintenance/recovery progress. This grants no ownership of other `log/` contents. |
| Engine-only | Index `ALERTS` | Typed off-host notification intake, not stream-local ALERTS.md. |
| Engine-only | Index and stream locks | Short writer exclusion. No network/Git wait under an all-stream lock. |
| Engine-only | `failures/<full-session-id>.lastgood` | Parking marker containing only that session's last completely persisted good-turn entry ID. |

Every turn reads only AGENTS.md and STATE.md. Everything else is engine-only or opened on demand. GOAL.md, STREAM.md, DECISIONS.md, and ACTIONS.md are retired. There is no separate CURRENT section. Stream instructions disable overlay TODO.md/PLAN.md planning and use Goals plus Log instead. Non-stream overlay behavior is unchanged. Existing TODO/PLAN and invented ALERTS.md, decisions.tsv, ad-hoc log/ and analysis directories are not migration, import, retention, or ownership targets. Fix 12 only stops referencing invented artifacts.

The STATE shape is explicit:

```markdown
## Goals
ratified: <authority reference, empty until ratified>
### North Star
<one mutable, human-authorized goal>
### Current objective
<coordinator-editable immediate objective, possibly empty>
### Charter
<remaining ratified scope, acceptance, WRITES, and NO-GO terms>
## Rules
<only human rulings still in force>
## Log
### <UTC timestamp> <subject>
<free body>
```

The marker is the first line of the Goals body. It is not a marker found by searching historical prose. A single section parser recognizes headers outside code fences, rejects duplicate required sections, and validates Goals before Rules before Log. It preserves an extra level-two section between Rules and Log byte-for-byte. Future Asks is tolerated, not created or implemented. Goals has exactly one North Star and one Current objective. The shared goal resolver returns the nonempty current objective, otherwise North Star. No goal-completion flag exists.

The parsed shape retains exact byte spans for Goals, Rules, Log entries, and intervening sections. The goal resolver and narrow section mutations share that shape. Accepted Log occurrence boundaries and rotation progress live in existing engine metadata, not a second agent-facing stream file. Helpers stay specific to STATE, scoped staging, or migration rather than becoming a general document/workflow engine.

### Implementation boundaries

Keep a driven/paused switch, correlated delivery and DCR progress, usage-reset state, and one narrow Z11 recovery operation per affected original session. Delete the proposed runnable/wait/done turn-disposition requirement as a condition for Z6 re-injection. Do not build a stall-cause classifier, canonical control engine, ask ledger, or workflow definition.

The current goal has one code-owned resolver. It reads the current objective in STATE's Goals section, falling back to that section's single mutable North Star. The North Star is never marked completed/uncompleted. Finishing a current objective may replace it or end driving without completing the North Star.

The engine owns the Z6 prompt, Z8 fixed DCR template, section-aware STATE mutation and Log rotation, rule retirement, migration, and Z11's detect/park/ratify/fork/DCR/wipe path. Then templates and skills name the implemented commands and artifact paths. A rule asking the agent to remember these policies is not their enforcement.

Keep engine state in existing configuration/tick state and the narrow receiving-side operation record. STATE is the one current decision state plus recent Log; history is cold retired information, not a second current truth or replayable command engine. Index ALERTS remains the notification route. It is not a stream-local ALERTS.md. Protect live control records, `failures/` markers, and referenced evidence from cleanup. Z11 permits only the verified recovered original's deletion, not general transcript or output retention cleanup. No database, second daemon, history_full/history_index file, empty Git-commit history store, or mandatory per-ask ledger is included.

### Z coverage and the available track 3 verdicts

Track 3 now has verdicts in `30-research-designs.md:344-364`. Proposal A is its recommendation. B/C differences are shown where material. Under G18 these are review annotations, not permission to replace or delay the dictated MVP. A later design change is follow-up work.

| Call | Coverage in this catalog | Track 3 verdict and reason |
|---|---|---|
| Z1 | Item 1. Drive unfinished work, refined by Z6. | Adopt. Another turn is not progress and cannot release a hold. |
| Z2 | Deferred section only. | Adopt. Lifecycle, source-bound acceptance and constraint lifetimes belong in the proposals, not this tick stack. |
| Z3 | Item 3. Tick-observed >=150k, no interruption, same-session DCR. | Modify. Use a measured early-maintenance trial with safe tool boundaries, not a hard ceiling or proved optimum. |
| Z4 | Items 2/18. Quiet off-host ZF-only DM, exact stream prefix. | Adopt. Deduplicate episodes; delivery is not proof of reading. |
| Z5 | Item 7. Consumed/applied steer acknowledgement. | Adopt. Receipt, consumption, blocking and application remain distinct from product completion. |
| Z6 | Item 1. Always construct/coalesce the current-goal injection while driven and stalled. | A rejects the blanket-safety claim; B/C modify admission. Skill text cannot grant authority. MVP retains cause-independent reinjection, with explicit stop and Z11 receiving-side boundaries, not A's proposed open-set scheduler. |
| Z7 | Item 10; shared by items 1/3. STATE Goals' North Star/current objective, then workers. | Adopt. Finite objectives may end without completing the North Star. |
| Z8 | Item 3; reused by item 18. Fixed read-path/current-goal renderer. | Modify. Keep fixed same-session DCR but expose retryable phases; calling it one action does not make it atomic. |
| Z9 | Items 6/12/16. STATE Log, 30 entries, every-tick history rotation and migration, with Z15's layout. | Historical verdict on G17. Z15 replaces those names. Recent activity is neither the full open-work set nor a token bound. |
| Z10 | Two review classes. Z13 removes bulk artifact ownership from this catalog. | Adopt. These are review lenses, not an exhaustive causal model or another engine. |
| Z11 | Item 18; narrows item 2 and adds failures/ to item 16. | A modifies with no default fork; B modifies with qualified fork; C rejects automatic fork/wipe. All retain human repair and reject streaming alone as deletion safety. MVP still implements ratified F-DCR, with evidence/input/ownership prerequisites before narrowly scoped deletion. |

The earlier verdicts above are historical annotations, not authority to retain superseded file names. Z15 preserves the 30-entry Log rule but replaces G17's layout. G18's independent MVP path remains. Z13 excludes invented-file work; item 17 is removed without renumbering the remaining 17 fixes. GO authorizes execution, not pushes, merges, live-instance changes or other-branch rebases by this session.

## Per-item detail

### 1. Drive-mode goal re-injection, without stall-cause detection

**Symptom and evidence.** F1 rows 3, 26, 34, 39, 40, 51, 55, 59, 60, and 64. C rank 1 identifies the event-only wake gap. Z6 now specifies its remedy, replacing this catalog's earlier runnable/wait/done disposition design.

**Root cause.** `tick.py:317-339` does not observe the coordinator's own stalled/settled state. `:435-445` requires pending events and suppresses an out coordinator. The five-minute timer already exists at `systemd/pi-streams-tick.timer:4-6`. `prompts/poteto.md:1-5` loads process but does not implement the requested goal-bearing command contract.

**Fix.** Code the rule first. While the explicit stream drive switch is on, whenever the tick observes a stalled session or stream, re-inject exactly `/poteto-mode <current goal>` into the designated stream coordinator. Resolve current goal from STATE Goals' Current objective, falling back to North Star, through item 10's single parser. Worker stalls are reported to that coordinator for stream-level remedy, not repaired by blindly replaying a worker's old command.

A settled/idle runtime or an explicit runtime stall indication is an observable trigger, not a diagnosis. Do not infer death from file mtime or kill a running tool because its output is unchanged. Reuse the actual busy flags. Once a stall is observed, do not branch on quota, auth, disk, missing disposition, pending-event count, or a claimed completion of the North Star. Always re-inject while driven. Do not require the coordinator to produce a new control record before receiving the prompt. G5 remains a separate stream-level recovery policy, never an `out()` veto on this branch.

Reassert one correlated outstanding injection per stream/current-goal revision rather than growing identical queued copies. This is transport coalescing, not cause-based suppression. Re-injection requests current-goal reconciliation, not repetition of an external job. G5 still prohibits duplicate uncertain jobs and gates the actual saved-step retry. Repeated quota failures do not create repeated blocker notifications.

Implement the literal `/poteto-mode <goal>` command in the harness adapter. Do not assume `/poteto` or a silently ignored slash command forwards arguments. Its thin alias must load the installed poteto-mode skill and preserve the full goal, including multiline content and punctuation. Test the expanded model input, not just the submitted string. Native Pi expands leading commands only; a slash invocation after the DCR read-path instructions must be explicitly expanded/invoked by the engine adapter without dropping either those instructions or the goal. Use a control-input path that does not treat the injected goal as a human answer or void `pendingAsk`; the current ordinary prompt path does void open asks. The coordinator keeps genuine task prohibitions. The injected stream instructions also say to park and log environment failures, not self-remedy them; the human repairs those under Z11.

Turning drive off or an explicit native stop invalidates stale automatic admissions at the receiver. This is a drive switch/delivery generation, not stall-cause detection. A completed current objective can end that drive run or select another current objective. It never marks North Star completed. Fresh explicit user input remains allowed. Preserve the prior stop-versus-in-flight-prompt race test.

Isolate worker/status failures so one unavailable observation cannot skip another stream's reinjection or STATE Log rotation. Bound boundary I/O and avoid all-stream locks through network/Git waits. An unknown owner is not permission to start another writer. Correct doctor's any-fresh-stream shortcut at `doctor.py:179-195`. Report requested progress and new blockers, not a DM per tick.

**Layer.** LAYER 3 owns drive observation, the prompt renderer, and automatic admission. LAYER 2 tests the literal rule and expanded goal. Stronger static layers cannot run a future coordinator turn. Implement those code paths first, then name them in LAYER 4 AGENTS and LAYER 5 skills. Those texts cannot supply a clock or fix the event-only return.

**Blast radius.** Medium. `engine/{tick,project,cli,piweb,doctor}.py`, a small command alias/control-input adapter, and tests, followed by templates/skills. No stall classifier, remedy engine, or per-ask lifecycle.

**Verification.** Baseline produces no prompt for an idle coordinator with empty pending. Candidate emits the same goal-bearing injection for idle, quota, auth, disk-error, and missing-disposition fixtures while driven. Assert no cause-specific branch changes the payload. A stalled worker targets its coordinator. Verify current-objective fallback to North Star, runtime skill expansion, pending-ask preservation, unchanged North Star after objective completion, off-drive suppression, coalesced retries, and a stop racing admission. In the disposable stream, finish two tiny work steps across a stall without a human nudge. Observation errors must not mask another ready stream.

**Dependencies.** Items 7, 8, 10, 11, and 15. Item 3 coalesces DCR with ordinary reinjection. Items 2/18 do not classify a stall before Z6 constructs its goal injection. At the receiver, a published Z11 marker parks the original: retain/coalesce the goal intent without another failed-session turn until ratified F-DCR. That later Z11 safety boundary is not an `out()` veto or a change to Z6's cause-independent payload. Test both facts together.

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

1. **SYNC/DUMP.** At a native safe steering boundary, the coordinator reads and safely synchronizes STATE. Replace the current objective in Goals only within its grant. Preserve the ratified North Star, charter, and active Rules. Append completed-work/failure summaries to Log through item 6's engine append command. A failure does not authorize a rule change. The agent never prunes or rotates Log and never authors a resume prompt. A ready receipt identifies the operation and STATE revision. After the coordinator yields normally, bind the receipt to its actual terminal leaf, not a guessed future final-response ID. Run Log overflow rotation before the resumed read.
2. **COMPACT.** Compact the same idle session through the command API. Retain the atomic idle/expected-leaf precondition so a direct prompt racing this step is not aborted. An HTTP command-start receipt is not compaction completion. Failed compaction leaves the synced artifacts and phase intact. It does not authorize forced rotation or provider switching.
3. **RESUME.** After a successful native compaction entry, the engine renders the fixed template below using absolute paths and the shared STATE goal resolver. Re-read Goals at admission so an objective change during compaction is not replaced by a stale cached string. Compare the current drive generation and admitted-input sequence. A new stop disables that automatic admission. Preserve and reconcile newer direct input before admitting an obsolete objective. The coordinator resumes in the same session with code-owned instructions, not an agent-written free-form prompt.

The fixed template belongs in `engine/tick.py` or a small imported engine prompt renderer. This is the rendered contract, not a new skill:

```text
Read the current stream artifacts before acting:
- {stream_dir}/AGENTS.md
- {stream_dir}/STATE.md
Resolve the current objective in STATE Goals, falling back to its North Star.
Open history/, context/ and its README index, checks/, or handover/ only on demand.
Historical entries do not override current Goals or Rules.
Do not self-remedy environment/auth/resource failures or write new rules, skills,
or memory because of them. Park and append a Log entry via the engine;
the human repairs them.
{explicit_human_ratified_instructions_if_present}
/poteto-mode {current_goal}
```

Do not load history wholesale or revive any retired file or separate CURRENT section. Do not read TODO/PLAN in a stream. Item 12 disables those stream-specific overlay demands. Free-length Log bodies mean the 30-entry policy is not a token ceiling. Measure actual reads rather than add an unrequested body budget.

Keep the prior intake safety corrections. The compaction-time queue is an in-memory Map at `W/dist/server/sessions/piSessionService.js:317,1371-1376`, drains independently at `:2483-2525`, and is cleared at `:502`. Accepted input needs recoverable identity, exact body, order/kind, and attachment references in the narrow receiving-side maintenance record. Do not race its drain with a separate stale RESUME. Tick state references that operation ID rather than owning another input queue.

Advance ready phases through the existing `agent_end`/`compaction_end` path at `W/dist/server/sessions/piSessionService.js:2478-2490`; do not impose an extra five-minute delay per phase. Later ticks reconcile crashes. Persist phase before dispatch and use the native transcript to discover an already-completed compaction. The same fixed template applies on retry, with the current goal re-resolved. No general workflow engine is added.

**Direct prompts are covered by observation.** The tick resolves the actual coordinator and checks it regardless of whether its turn came from a tick, browser, CLI, or bot. Safe-point steering is already part of the installed agent loop at `W/node_modules/@earendil-works/pi-agent-core/dist/agent-loop.js:88-169`. The check is per tick, not per model request. A long in-flight call or tool can exceed 150k before it yields. That is permitted by Z3's no-interruption requirement and must be reported honestly.

**Native hook decision.** No new native Pi request-boundary hook is needed for Z8's tick-triggered DCR. Reuse safe-point message admission and idle native `compact()`. A small pi-web command precondition and an observable compaction result are needed to close the direct-prompt race. They belong in pi-web source, not a monkeypatch of Pi core, a global model override, or an extension that calls aborting compaction inside an active tool loop. The existing installer returns early when pi-web is already present at `install.sh:466-468`. A normal pi-stack reinstall therefore does not deploy this dependency fix. Install the explicitly tested pi-web artifact for verification, expose its maintenance capability, and have doctor refuse automatic compaction until that capability is present.

**Layer.** LAYER 3 owns the trigger, ordering, fixed resume renderer, and native admission. Implement and test that code first, then update LAYER 4 AGENTS and LAYER 5 skills to name STATE and the implemented sync step. LAYER 1 supplies the actual current-artifact layout. LAYER 2 can reject regressions but cannot compact a live runtime. No stronger static layer can guarantee the runtime ordering, and an agent-authored prompt would defeat Z8's fixed harness contract.

**Blast radius.** Medium. `engine/{tick,piweb,sessionlog,doctor}.py`, `bin/pi-web-cli`, coordinator templates, tick maintenance tests, and the small pi-web command boundary. Routine DCR leaves thread policy unchanged. It creates no fresh coordinator and performs no provider switch, global reserve change, or transcript deletion. Item 18 separately runs this same DCR on an explicitly ratified recovery fork.

**Verification.** Baseline has no 150k DCR or fixed artifact-loading resume. In the disposable stream, cross 150k during a direct turn while a benign tool spans a tick. Observe no tool abort, successful STATE sync, Log rotation, one native compaction, and the engine-rendered fixed prompt in the same SID. The prompt must contain absolute AGENTS/STATE paths, no mandatory history/index/TODO/PLAN or retired-file reads, no agent-generated resume text, and the correctly expanded `/poteto-mode` goal. Test 149,999/150,000, current-objective fallback and mutation during compaction, repeated ticks, a stop racing admission, failed summarization, accepted input surviving a restart during compaction, and crash after native success before observation. Check actual artifact reads and resumed task effects, not just the HTTP payload.

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

### 6. Keep current Goals and Rules, append Log, and tick-rotate its overflow

**Symptom and evidence.** A rank 3, F6 rows 11, 16, 32, and 71, and the artifact map. The frozen 654 STATE reached 10,195,068 bytes, with 71 preserved-checkpoint headings. The map's later 19 KB STATE does not remove the history-pile pattern or TODO/PLAN/index load. Z15 now specifies one STATE with current Goals, active Rules, and a recent Log.

**Root cause.** At the historical base, `templates/stream/AGENTS.md:4,8` reads STATE every turn and asks for a rewrite. `templates/stream/STATE.md:1-6` does not distinguish history. `threads.py:459-461` explicitly loads it at pickup. `project.py:24,703-749` protects the old artifact and normal upgrade cannot migrate its contents.

**Fix.** Implement the shared section-aware STATE parser and mutations before templates. Goals and Rules are rewritten in place. Only Log is append-only and capped. An engine append command takes the short stream lock and atomically writes one complete entry into Log:

```text
### <UTC timestamp> <one-line commit-style subject>
<free body with the relevant context>
```

Append completed-work/failure entries through that command. Log each new ZF steer when it arrives. Ordinary Log rotation later carries that steer to history. A new human ruling both updates Rules and appends Log. A superseded ruling is removed from Rules only after its exact old text is durably retained as `history/<UTC ts>-rule-retired-<slug>.md`. Preserve its source authority. Do not add a tag field. The agent never prunes, rotates, or rewrites prior Log entries. Goals and Rules have no entry cap. Rules stay short without silently dropping active constraints.

The canonical append operation records accepted occurrence spans in engine metadata. It distinguishes literal delimiter-like body text and examples inside code fences from entry boundaries. Bodies are free length. A malformed structure is reported without dropping bytes. The shared parser preserves an extra level-two section between Rules and Log. This neither creates nor implements Asks.

On every tick, before pending-event, drive, or outage gates, move the oldest Log overflow to `history/<UTC ts>-<slug>.md`, one file per entry. Retain the 30 newest Log entries. Convert timestamps to UTC. A stable source-occurrence/hash suffix in the slug prevents collisions between identical subjects or even identical entries. Preserve exact entry bytes and append order. Goals, Rules, and intervening sections remain byte-identical during Log rotation. No history_full, history_index, second Git repository, or empty-commit history store is added. The 30-entry rule is Z15's explicit record-count policy, not a token or resource budget.

Serialize append, rule retirement, section updates, and rotation through the same short stream lock. Record the source spans and destinations in existing engine state. Write, verify, and synchronize history before removing source text. Atomically publish and synchronize the remaining STATE and containing directory before acknowledging completion. Revalidate source revisions and preserve concurrent changes. Restart reconciliation recognizes existing matching destinations and never overwrites different bytes or duplicates an occurrence. A partially written entry stays intact with a structural error rather than being discarded to satisfy the count.

After code/tests exist, replace the old STATE template's meaning with this three-section shape and history/. AGENTS steps read only AGENTS and STATE every turn. Agents append via the engine, update the current objective through item 10, and never rotate. Kickoff Interview/Ratify/Plan and `rotate_coordinator` pickup use STATE Goals and the shared resolver. `PROTECTED_STREAM_FILES` retains STATE and protects history/ and failures/. Retired GOAL/STREAM/DECISIONS/ACTIONS files remain protected from ordinary upgrade until explicit item 16 migration. New/upgrade and create retries respect the schema marker. They never overwrite owned STATE/history or seed a mixed legacy/current layout.

**Layer.** LAYER 3 enforces section mutations, rule retirement, append serialization, every-tick rotation, and crash-safe publication. LAYER 1 is STATE/history. LAYER 2 checks byte preservation and counts. LAYER 4/5 instructions are callers, not the rotation mechanism. Static layout cannot run rotation or arbitrate concurrent writes.

**Blast radius.** Medium. `engine/{tick,project,threads,cli}.py`, a narrow proposed `engine/artifacts.py`, STATE/history templates, coordinator instructions, stream/kickoff skills, and artifact tests. No live worktree changes, transcript deletion, or generic log-retention engine.

**Verification.** Baseline has no section-aware STATE Log cap/rotation. Test 0, 29, 30, 31, and many Log entries. Preserve Goals, Rules, an intervening unknown section, Unicode, multiline bodies, fenced fake headers, duplicate subjects, and identical occurrences. Test paused/outage/eventless ticks, concurrent updates, collisions, malformed entries, and crashes after history sync before STATE publication. Retry yields identical history names/bytes. Test exact retired-rule text, new-ruling Log entries, and steer arrival followed by ordinary rotation. New stream, kickoff, upgrade, and replacement pickup read AGENTS/STATE only. Disposable DCR reads STATE after overflow rotation and does not load cold history.

**Dependencies.** Item 15's atomic writer and item 13's scoped commits. This code precedes templates/skills and item 3. Item 10 shares the parser. Item 16 handles existing repositories.

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

All normal coordinator creation, adoption, replacement, tick targeting, and status use the same resolver. Adopt an existing nonempty session only by an explicit adoption operation. Recover a crash-created session only from the exact saved spawn attempt identity, not list order or newest timestamp. Save registry updates atomically through item 15. Reject duplicate session IDs and reserve the `coordinator` role from worker spawn/adopt, which currently accepts it at `threads.py:361-363,391,502`. Also enforce the actual first-line `ratified:` marker in STATE Goals, with nonempty source-backed authority, before worker spawn/adopt side effects. The historical `threads.py:127-137` scans old charter prose and dispatch does not consult it. The new parser accepts the marker only on Goals' first line, not in Log/history or another body. Keep unratified kickoff available. Do not convert idle workers to done. Registry lifecycle is not task acceptance.

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

### 10. One STATE goal resolver and a narrow current-objective update

**Symptom and evidence.** F12 rows 27, 30, 38, and 75, B rank 1/3, and the artifact map's historical 66 KB 654 charter. STREAM amendments bury the goal. Z7/Z15 now place the one mutable North Star and immediate objective together in STATE Goals, not another ask ledger.

**Root cause.** At the source base, `templates/stream/STREAM.md:1-25` has a bare GOAL label but no current-objective field. `skills/stream-kickoff/SKILL.md:40` makes the entire ratified file ZF-only. `threads.py:285-310` renders briefs from pointers without a shared resolver. `templates/stream/AGENTS.md:5,7` also permits out-of-grant defaults and mandates new check scripts.

**Fix.** Use item 6's STATE parser. Goals contains exactly one `### North Star` and one `### Current objective`. The first Goals line carries `ratified:` authority. `### Charter` retains the remaining ratified terms. The sole goal resolver selects the nonempty current objective, otherwise North Star. Reject duplicate or ambiguous sections and an empty North Star. Never select a TODO item or historical paragraph. Legacy bare-label parsing belongs only to explicit migration, not a second live goal source.

Provide a current-objective-only engine update that rewrites that Goals subsection in place. Preserve exact North Star, charter/ratification, Rules, Log, and intervening-section bytes. Human-authorized changes may replace North Star or charter through the authorized boundary, not through this coordinator edit. Both reinjection and DCR use the same resolver and bind the STATE revision to admission. No completion flag is added. Completing an objective may replace it or end driving, but never completes the North Star or overrides a stop or NO-GO.

Only after code exists, update STATE/coordinator/brief templates and every kickoff Interview/Ratify/Plan reference. Ratify records authority in Goals. Planning uses Goals plus Log, not TODO/PLAN or a separate CURRENT section. Item 16 splits old STREAM and DECISIONS into current Goals, active Rules, and cold history with a source-backed map. Never hide an active freeze in history. Remove the out-of-authority "continue on the default" permission and the demand for a new check script for every small/artifact-only ask. Keep explicitly requested acceptance. This is not a new independent-review policy.

**Layer.** LAYER 3 provides the shared resolver and narrow objective mutation. LAYER 1 is the explicit Goals shape. LAYER 2 proves untouched section bytes. LAYER 4/5 wording follows the implemented interface. Static structure cannot reconcile runtime goal selection or prove arbitrary semantic authorization.

**Blast radius.** Low to medium. `engine/{project,threads,tick,cli}.py`, the shared STATE helper, STATE/coordinator/brief templates, kickoff/stream skills, and tests. Runtime ratification enforcement remains mechanical item 8, not a second counted fix.

**Verification.** Baseline lacks the STATE Goals shape and objective edit boundary. Candidate selects current objective, falls back when it is empty, rejects missing/duplicate subsections, preserves multiline/quoted goal bytes, and refuses an objective edit that changes North Star, charter, ratification, or Rules. An unknown section between Rules and Log survives. Objective completion never writes STOPPED/done onto North Star. Kickoff follows the edit grant and creates no unsolicited proof campaign. Disposable tick and DCR resolve the same value. Migration preserves a binding freeze while archiving its superseded source text.

**Dependencies.** Items 6 and 15's snapshot writer. This code precedes template/skill callers, items 1/3, and item 16 migration. Per-ask lifecycle stays in track 3.

### 11. Remove routine rotation and refuse unsafe manual replacement

**Symptom and evidence.** F6 rows 16, 32, 37, 71, and 72. A shows that queue transfer was manual and all 20 saved bodies arrived. It also corrects issue #36's implication that archive itself necessarily killed active execution. Installed pi-web already refuses archive while streaming, compacting, running bash, or holding queued work.

**Root cause.** `tick.py:447-479` rotates on size or age. `project.py:56-60` supplies the 60k/six-hour defaults. `threads.py:446-462` has no coordinator checkpoint request or queue transfer and opens the successor with "Read STATE.md, then continue". The stubbed scenario in `tests/test_scenario.py:158-188` does not prove native archive safety or carry-forward.

**Fix.** Delete routine size/age rotation from ordinary wake selection. Reuse the same designated session and let item 3 handle context. Do not replace 60k with another rotation threshold or fixed compaction count. Retain explicit replacement for an intentional boundary. Z11's environment-failure recovery is the separate ratified fork/DCR/delete operation in item 18, not an excuse to use this generic rotate path.

Mark `docs/design/pi-streams-handover.md:3,20,26,92` as historical rather than an authoritative current pickup guide. It still says nothing is built and recommends fresh coordinators when large. Keep the original historical evidence, but do not seed that policy into new implementation sessions.

Manual rotation must not abort first to make archive possible. Retain native busy/queue refusal. Require a current coordinator-authored checkpoint and stable references to unfinished work before retirement. If queues or session-local native child callbacks still need the old owner, refuse rotation and explain the unresolved boundary. Do not build a general native-child adoption or queue migration subsystem in track 1. After successful retirement, create or explicitly adopt the successor using item 8, then load only AGENTS and STATE with the shared current-objective/North-Star resolver before calling rotation complete. No pickup instruction may request retired files or mandatory cold-history/index reads. Persist enough existing rotation phase to recover archive-then-spawn failure.

**Layer.** LAYER 3 owns replacement and native refusal. LAYER 1 supplies the checkpoint. LAYER 2 checks crash boundaries but cannot prevent a deployed abort/archive. A handover skill cannot enforce the archive precondition.

**Blast radius.** Low to medium. `tick.py`, `threads.py`, obsolete warm configuration handling, the current design and historical-handover label, and rotation tests. Accept old config fields while ignoring their retired rotation behavior during migration. Do not silently assign them a different meaning. No automatic cleanup of old sessions or worktrees.

**Verification.** Baseline rotates an idle coordinator at 60k or six hours. Candidate does neither. Attempt manual rotation during a benign tool, queued steer, or unresolved callback and assert no abort, archive, or second coordinator. At a deliberate clean boundary, rotate once, retain exact evidence through item 5, and verify one successor. Crash after archive and recover without arbitrary adoption or duplicate opening prompts.

**Dependencies.** Items 5, 8, 14, and 15. Removal of routine rotation precedes items 1 and 3. General callback migration belongs to track 3 if it cannot remain a refusal.

### 12. Load only AGENTS and STATE, without importing invented artifacts

**Symptom and evidence.** D7, Z10b, A rank 3, B rank 3, and the baseline artifact map. Historical observations include TODO 465 KB, PLAN 255 KB, context/README 212 KB, and invented ALERTS.md 294 KB. Z13 excludes invented artifacts. Z15 removes competing stream planning files. These byte counts are not measured request tokens.

**Root cause.** TODO and PLAN come from `overlay/AGENTS.md:17-19`. `overlay/APPEND_SYSTEM.md:6-8` requires their reads. `templates/stream/AGENTS.md:4` also requires context/README every turn, despite `project.py:417-429` seeding it as an index. `templates/stream/DECISIONS.md:1` ships a separate decision file. Invented ALERTS.md and decisions.tsv have no pi-stack source. Index `ALERTS` at `project.py:551-553` is real and separate. The repository's historical root decisions.tsv stays untouched.

**Fix.** Follow the explicit tier/name table above and in `11-artifact-map.md`. Stream template/brief instructions disable overlay TODO/PLAN planning. A stream-only overlay exception makes Goals plus Log the planning record. Non-stream behavior is unchanged. Every turn reads only AGENTS.md and STATE.md. Reference history/, context/ and its README index, checks/, and session-bound handover/ only on demand. Never direct agents to registries, threads.tsv, subscriptions.tsv, stream.toml, events, tick-state, locks, or failures/. Runtime operations use implemented CLI boundaries rather than mandatory raw metadata reads.

Stop referencing invented ALERTS.md, decisions.tsv, ad-hoc log/, and analysis directories. Do not import, migrate, archive, delete, assign owners to, inventory, or repair them. TODO/PLAN are also not migration targets. Existing files remain unchanged and are not silently repurposed. Do not add an archive/rebuild helper for these excluded artifacts. Only item 16's specified legacy stream artifacts migrate.

DCR and kickoff use current STATE, not short excerpts from still-mandatory blobs. The context README remains an index by contract, but this fix does not rewrite existing index contents or transfer their ownership. Rule changes use item 6's human-ruling lifecycle. General constraint expiry and independent reviewer policy stay in track 3. A Z11 failure never authorizes new rules, skills, or memory policy.

**Layer.** LAYER 2 tests the actual generated read instructions and conditional overlay behavior. LAYER 4 templates/overlay and LAYER 5 skills name the implemented STATE contract after items 6/10. This fix removes reader obligations. It does not claim a new runtime cleanup mechanism or hard context bound.

**Blast radius.** Low. Stream template/brief, `overlay/{AGENTS,APPEND_SYSTEM}.md` with a stream-only exception, related skills, and literal/read-contract tests. No invented-file ownership work, worker-file edits, or ad-hoc directory maintenance.

**Verification.** Baseline requires TODO/PLAN and the context index. Candidate stream instructions require only AGENTS/STATE, while non-stream overlay behavior remains identical. Supply long TODO/PLAN, invented files/directories, and a large context index as private fixtures. Their hashes remain unchanged. Assert no migration/import/inventory call or engine-only agent read. Inspect disposable DCR's actual reads, not an HTTP payload or bytes/4 estimate.

**Dependencies.** Items 6 and 10 provide the STATE operations before template/skill callers. Item 16 migrates only its explicit legacy files. No general ledger, resource cap, or cleanup helper is added.

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

### 16. Losslessly migrate to STATE Goals, Rules, and Log once per stream

**Symptom and evidence.** The baseline artifact map shows STATE/charter/decisions piles that new templates cannot repair. A's historical 10 MB STATE and B's accreted charters are concrete precursors. Z15 requires explicit migration into one STATE, superseding Z9/G17's intermediate names.

**Root cause.** At the source base, `project.py:682-700` calls `copy_missing()` on create, and `:703-749` protects owned STATE/STREAM/DECISIONS/context during upgrade. It cannot split legacy authority or transform STATE. Creating a new schema alongside an unmigrated legacy charter would leave competing current truth. `cli.py:204-217` enumerates registered stream roots, the migration selection boundary.

**Fix.** Add explicit `pi-streams migrate <id> --home <index>` with a plan/dry-run view. It operates only on the selected registered stream root. It never follows thread worktrees, repo lists, `.stream` pointers, or symlinks outside the root. No worker prompt, live lifecycle change, fork, cleanup, or remote publication is included.

Persist a migration identity, UTC start time, exact source hashes, and a source-backed extraction/write map. The map identifies original byte spans, source authority/provenance, and destinations in Goals, active Rules, or history. Legacy bare-uppercase charter labels must be supported. Do not automatically classify ambiguous active authority. If the map cannot establish current authority, refuse that stream's apply and report exact unresolved spans. Grok Bot can resolve them from evidence without inventing an authority decision.

Under the short stream lock and artifact-writer barrier:

1. Retain exact original STREAM.md and DECISIONS.md bytes in stable history snapshots with source path, hash, and Git provenance recorded in engine migration metadata. Archive old STATE into history before publishing fresh STATE. Its real level-two sections outside fences may become individual entries. Preserve preambles, repeated/empty headings, and no-heading files. Ordered reconstruction must match the old STATE hash. Archive destinations contain original bytes, not reformatted Markdown.
2. Use identifiable section/entry Git introduction timestamps when available. Otherwise use the persisted migration start time and label the fallback in provenance, never filesystem mtime or the latest whole-file commit as a fake section time. Stable occurrence/hash slugs prevent collision and make retry destinations identical.
3. Split STREAM through the explicit map into Goals, active Rules, and historical material. Retain its ratified authority on the first line of Goals, its one mutable North Star, its current objective if source-backed, and remaining charter terms. No separate CURRENT section survives. Move still-in-force DECISIONS entries into Rules and the rest into history. Keep every active freeze/ruling visible in Rules or the ratified charter. Never treat all text below an old ratified marker as obsolete.
4. Verify and synchronize retained history before atomically publishing a fresh STATE with Goals, Rules, Log. Seed Log with exactly one migration entry linking provenance and counts, not a pasted old STATE or a full history index. Retire the migrated STREAM.md and DECISIONS.md only after verification. Record schema/migration identity in protected engine metadata. Do not create GOAL.md or ACTIONS.md.
5. Create and protect failures/. Preserve existing `<full-session-id>.lastgood` files and recovery-operation state byte-for-byte. Never fabricate checkpoint IDs or clear parked episodes. Use the shipped empty-directory marker without inventing a failure entry.
6. Make exactly one scoped commit per stream for approved migration paths, fresh STATE, history, legacy retirements, failures/ layout/protection, and schema metadata. Preserve unrelated staged content and all worker-worktree bytes. A retry creates no duplicate seed, archive, rule, or commit, including after a crash following commit but before acknowledgement.

TODO.md, PLAN.md, invented ALERTS.md/decisions.tsv, ad-hoc log/ and analysis directories, and existing context contents are not migration targets. Do not import, classify, assign ownership, or clean them. Existing GOAL.md/ACTIONS.md from an unknown intermediate schema require an explicit source-backed plan or refusal, not silent adoption. No arbitrary prose truncation, byte cap, or automatic lifecycle action is added.

**Layer.** LAYER 3 owns explicit scope, lossless mapping, commit boundary, and restart reconciliation. LAYER 1 is the final STATE/history layout. LAYER 2 proves exact source retention, reconstruction, and path fences. Templates/skills cannot transform existing owned content or resolve interrupted commits. Code precedes rollout instructions.

**Blast radius.** Medium, stream-root only. `engine/{cli,project}.py`, the narrow STATE/migration helper, protected-file/schema handling, scoped Git helper, and proposed `test_artifact_migration.py`. No worker-worktree, provider/auth, or existing session lifecycle writes.

**Verification.** Baseline upgrade leaves the old layout. Candidate archives original bytes/provenance, reconstructs old STATE exactly, and builds fresh Goals/Rules/Log from an explicit STREAM/DECISIONS map. Test known section times and stable fallbacks, preambles, duplicate/fenced headings, no headings, existing history, simultaneous failure markers, active freezes, ambiguous authority refusal, unratified sources, unrelated staged files, path escapes, and crashes before/after archive, STATE publication, legacy retirement, and commit. A second run adds zero commits. Failure/recovery bytes and all worker-worktree fixture hashes remain identical. Assert zero session operations and unchanged excluded-file hashes. Run only on a new disposable legacy-layout fixture before separately authorized rollout.

**Dependencies.** Items 6, 10, 12, 13, and 15. Ordinary upgrade remains protective. S2a follows S2 and precedes S3.

### 18. Park environment failures, then run ratified F-DCR

**Symptom and evidence.** Z11, F7 rows 13, 17, 24, 47, and 63, and C rank 2. Auth, resource exhaustion, and outages provoke repeated error-handling turns and remedial rules. The catalog must remove that noise without assuming forking undoes external effects. G5 classes 2-5 now use this path, not automatic readiness release.

**Root cause.** `tick.py:347-367,435-440` uses a last-assistant outage flag and has neither per-session checkpoints nor ratification/fork phases. `sessionlog.py:45-56` drops the containing JSONL entry's ID. `engine/piweb.py:75-86` and `bin/pi-web-cli:101-111,150-156` lack exact-entry fork and delete adapters.

Pi exposes persisted entry IDs, not a durable display turn number. `N/session-manager.js:766-775,883-890,943-954` stores `id`/`parentId` and walks a selected branch. `N/agent-session.js:427-451` resets extension turnIndex per agent run. A successful checkpoint must include a whole persisted tool batch, not merely the assistant that requested it. `N/agent-session.js:350-365` emits message events before persistence, and `:285-289` does not await subscribers. Memory can advance before a disk write fails at `N/session-manager.js:724-758`. A naive event callback or last non-error assistant is therefore insufficient.

**Fix.** Implement and test the following engine/receiving-side operation before changing templates or skills:

1. **Record and park.** During healthy execution retain the exact inclusive end-entry ID of each fully successful persisted turn, including every tool result. On a stream failure, atomically publish `failures/<full-original-session-id>.lastgood` for the coordinator and each affected spawned worker. Content is only that session's last-good entry ID. Several files coexist. File existence means parked on failure. Bind native ID, full SID, cwd, file/branch identity and episode in existing engine-owned operation state. Never advance a parked marker into error-handling turns. Leave unaffected worker lanes alone.
2. **Do not self-remedy.** Park at the owning runtime admission/retry boundary, not only in tick memory. Native retries at `N/agent-session.js:2079-2140` must not bypass classes 2-5 parking. Do not call settings-writing repair methods such as `setAutoRetryEnabled()` at `:2181-2182`. No credential changes, cleanup, provider/model switch, or new rules, skills, memory lessons, or persistent harness configuration. Required marker/STATE Log/operation bookkeeping is permitted, not a license to write remedial policy. The fixed Z6/Z8 instructions carry this prohibition after the code exists.
3. **Alert and await ratification.** Send one Z4 episode through the existing off-host bot route to ZF only, in exact `<stream-id>:: <message>` format. The human repairs the environment. Sign-in probes, a writable disk, or an ordinary assistant/user-role "fixed" string do not release parking. Preserve the authenticated ratified notice and any explicit exceptional instructions through O4 below.
4. **Fork the exact good prefix.** Once ratified and quiescent, fork inclusively at the saved entry, checking branch membership and complete tool-call/result pairs. Bind the new full SID to this operation and preserve the authorized provider, model, thinking, cwd and file identity. No abort to force quiescence, newest-session adoption, or tree navigation in the old file. Check inherited logical entries through the checkpoint and exclude failure descendants. Genuine later user input must be preserved and reconciled in order outside the discarded error noise.
5. **DCR on that fork.** Update the explicit registry to the verified replacement while holding ordinary admissions for this recovery operation. Before syncing, read the current owned artifacts so inherited pre-failure context cannot overwrite newer work facts. Run item 3's sync, successful native compaction, and fixed path-loading/current-goal resume on the returned fork SID. F-DCR is explicit recovery and does not wait for the routine 150k trigger. DCR itself does not change the fork SID. Include only additional instructions explicitly authorized in the ratified human notice. A generic repair notice grants no rules/skills/memory change. Preserve uncertain submitted-job identities and reconcile them before further task effects.
6. **Confirm, wipe, then clear.** After correlated post-RESUME streaming, archive only the exact old original if still live, then delete only that archived original. Require all evidence, newer-input and child-ownership prerequisites below first. Record the exact deletion result durably, then remove that original's lastgood file. A coordinator recovery never deletes its workers. Each affected worker needs its own operation and independently verified fork.

Native inclusive forking already exists at `N/agent-session-runtime.js:216-229`. However web `/fork` is a user-message selector and calls `runtime.fork(value)` without `position: "at"` at `W/dist/server/sessions/sessionCommandService.js:61-65,137-150`. `/clone` selects the current leaf at `:124-128`, including failure noise, and trailing entry arguments are ignored at `:38-41`. Neither is the required command. Add a narrow noninteractive pi-web exact-entry endpoint using `runtime.fork(lastgood, {position: "at"})` and the existing exclusive-operation guard at `W/dist/server/sessions/piSessionService.js:2686-2722`. Expose cancellation and uncertain outcomes, not generic success. A crash after native branch creation needs an operation-bound result, never a blind second fork.

Prime also has source-level entry IDs and exact-entry fork support. In `/home/alphalab/Projects/prime-agent` at `71beca9478f552dc6fc898bba9685f9ce00515cf`, `crates/pa-types/src/session.rs:694-704` defines optional entry `id`/`parent_id`; `crates/pa-types/src/daemon/command.rs:1045-1053,1296-1302` defines Fork with entry_id and position At. `crates/pa-daemon/src/branch_navigation.rs:333-375` validates that entry and selects it inclusively for position=at. `:571-628` replaces the runtime. This verifies source support, not safe persisted-turn capture or the deployed v0.10.1 server's contract. The track-2 CLI at `bin/prime_cli.py:252-273` does not expose this recovery capability. Prime's saved-session delete command exists at `crates/pa-types/src/daemon/command.rs:1136-1145` and rejects the current file in `crates/pa-daemon/src/saved_session_commands.rs:898-945`; its full safety contract still needs real-server tests.

`DELETE /api/sessions/:id` at `W/dist/server/sessions/sessionRoutes.js:389-397` calls `deleteArchived()`, which requires an archive record at `piSessionService.js:1649-1659`. Singular archive is at `:1519-1528`. Use this singular archive/delete sequence after the fork streams. Never use `archive-tree` at `sessionRoutes.js:373-380`; its planner follows parentSessionPath at `sessionArchiveTree.js:13-33` and includes the recovery fork and linked workers. Reject prefix IDs, wrong cwd, original/fork mismatch, bulk operations, directory deletion and worktree pruning.

A fork preserves the selected logical branch, not every original byte or alternate branch. Before deletion, item 5 retains any required exact evidence with provenance/hash. Preserve and route accepted later human input, stops, pending asks and attachments using the receiving-side operation boundary. Verify native child callback ownership separately; `W/dist/server/sessions/piSessionService.js:1041-1086` binds it to the original parent. Copying text or updating threads.tsv is not adoption. If an unresolved callback still needs that original and no supported transfer exists, keep the original and marker and report the deletion prerequisite blocked. Do not delete a worker or duplicate it to hide the dependency.

Missing/unsafe checkpoints, unsupported capabilities, cancelled hooks, ENOSPC marker writes and uncertain results default to parking/reporting, with no fork/deletion claim. Maintain the healthy checkpoint early; an off-host observer must still alert when the host cannot save a marker. Do not invent an entry ID or claim durable parking from a failed write. Persist each phase before mutation. On restart reconcile the exact recorded fork/delete result. A not-found response without this operation's prior deletion receipt is not proof of correct deletion.

**Four open engineering items, with chosen defaults.** These are implementation facts/defaults, not questions for ZF. They do not wait for track 3.

| Open item | Chosen default and fallback |
|---|---|
| O1. Detect the failure and capture last-good. | Use explicit assistant `stopReason=error`, known provider/auth/tool error results, and OS errors such as ENOSPC. Classify these at the failure boundary, never diagnose generic Z6 stalls. Usage-reset metadata routes only class 1 to item 2. Checkpoint after the complete successful tool batch is persisted and synchronized, using an awaited boundary. If the current integration cannot provide that boundary, add the smallest owning native/receiving hook. Unknown positive failures park under their actual label. No earlier safe checkpoint means blocked recovery, not a guessed header ID. Probes may diagnose but never ratify or repair. |
| O2. Exact fork support in Pi CLI and Prime. | Add pi-web's exact-entry receiving operation and expose it in bin/pi-web-cli; current slash fork/clone do not qualify. Reuse Prime's source-verified Fork(entry_id, At) through a matching CLI adapter, not another fork implementation. Guard quiescence before its replacement path. Track 2 must prove persisted complete-turn IDs, durable/active-session rebinding, inclusive prefix, correlated streaming and singular retirement on its real server. Missing IDs or unsupported deployed routes return a capability error and stay parked. Add the narrow native capability only if the tested revision lacks it. Do not substitute Prime archive/kill, which also closes children per `20-prime-cli-design.md:73`. No free-form new-session or delete fallback. Pi MVP work proceeds under G18. |
| O3. What counts as the fork streaming. | Persist a receiver observation of an actual assistant text/thinking delta from this fork's RESUME admission, correlated to recovery ID and completed compaction. A non-error resumed assistant completed between ticks also qualifies when that observation is retained. DUMP streaming, HTTP acceptance, agent.start, message-count growth alone, and an uncorrelated isStreaming flag do not. Pre-stream failure retains the original and marker. Streaming is the timing condition, not evidence/queue/callback deletion safety by itself. |
| O4. How the ratified notice reaches tick. | The existing authenticated ZF-to-bot intake forwards the exact notice ID/provenance and explicit stream/session/episode set to a proposed `pi-streams failure ratify` operation. That operation durably records ratification plus any expressly authorized extra instructions for tick to consume once. Do not keyword-scan ordinary conversation or trust role=user as proof of ZF. Locate/test the deployment's existing identity binding. If provenance is unavailable or the notice targets a stale episode, remain parked and report the adapter prerequisite. No new credential flow or model call is needed. |

**Layer.** LAYER 3 owns detection, ordered checkpoint capture, parking, ratification, exact fork, fixed DCR, streaming observation and scoped wipe. LAYER 1 is the per-session marker layout. LAYER 2 checks prefix preservation and deletion scope. Stronger static files/tests cannot observe and recover a live native runtime. LAYER 4/5 explain the implemented park/log/no-self-remedy contract afterward; text cannot implement forking or authenticate ratification. Routine Z8 needs no new native request hook; Z11 may need the ordered checkpoint/retry boundary O1 identifies.

**Blast radius.** High but required by Z11. `engine/{tick,sessionlog,piweb,cli,threads,doctor,project}.py`, bin/pi-web-cli, narrow recovery records and proposed `test_failure_recovery.py`; pi-web session source and a native checkpoint hook only if existing APIs cannot establish it; bot ratification intake; then templates/skills. Prime implementation belongs to track 2's capability adapter. No worker-worktree or general retention changes.

**Verification.** Baseline has no lastgood/ratify/F-DCR path. In disposable Pi sessions, inject a synthetic class 2-5 error after a successful multi-tool turn. Require concurrent coordinator/worker markers with exact safe IDs, zero environment-policy changes, one quiet alert, no release on readiness alone, authenticated ratification, one inclusive good-prefix fork, fixed same-fork DCR and actual RESUME streaming before singular original archive/delete and marker removal. Exact evidence, unrelated sessions, the fork, worker files and worktree hashes survive. Repeat for all four classes. Also test no checkpoint, failed marker write, mixed-success tool batch, wrong branch/SID/cwd, cancelled fork, timeout after creation, short between-tick resume, provider failure before streaming, newer input/stop, unresolved child ownership, and crashes at each phase including after delete before marker cleanup. Reconcile uncertain jobs without repeating their effects. Prime must independently pass its real-server contract before that adapter is enabled; no Prime round trip is claimed here.

**Dependencies.** Items 2, 3, 5, 6, 7, 8, 10, 15, 16, and the off-host route. S6 is the explicit F-DCR round-trip gate; do not enable classes 2-5 production recovery without it. Missing backend capability is reported with the chosen parked fallback, not a ZF policy card.

## Needs a ZF call

None for the listed fixes. Z1-Z15, GO, G25, G18, D1, and narrowed G5 settle the policy and execution boundaries. P7 assigns remaining reversible engineering decisions to Grok Bot. GO is granted. Unsupported source/capability or genuinely ambiguous authority remains a reportable blocker, not permission to guess.

Four Z11 engineering items remain open, all with chosen defaults O1-O4 in item 18. They cover detection/checkpointing, Pi/Prime fork capability, correlated RESUME streaming, and authenticated ratified-notice intake. Unsupported or uncertain recovery remains parked without deletion. Routine DCR stays in the same session; ratified F-DCR first creates its one verified fork. Apply no new budgets, retain explicit stops, refuse unsafe rotation, and use ZF-only Slack DM. Missing box-wrapper source and dependency source pins are discovery prerequisites, not ZF questions.

## Deferred to track 3

- **Per-ask lifecycle and ask ledgers.** The stream can lose an obligation when plans or priorities change. Z2 moves the lifecycle design out of this stack.
- **The coordinator grading its own homework.** A brief and its checker can share the same wrong paraphrase, and context decay may amplify that error. Z2 defers the oracle and fidelity design.
- **General constraint lifetimes.** Z15's specific active-Rule replacement and exact retirement are in scope. Z2 still defers general expiry and broader constraint-lifecycle machinery.
- **General control record or engine.** The research proposal combines authority, asks, ownership, and transactions. Its broader contract is not required for these bounded tick operations.
- **Workflow definitions and reviewer policy.** D9 requires a workflow shape before choosing costly independent-review boundaries.
- **General native-child adoption and callback migration.** A replacement coordinator can read an old run ID without owning its completion subscription. Track 1 refuses unsafe replacement rather than invent a second worker backend.
- **General parallel-lane scheduling.** Independent work can be serialized behind unnecessary dependencies. Track 1 wakes ready work but does not infer a dependency graph from arbitrary goals.
- **Broad overbuild and known-good-path enforcement.** Custom loaders, runners, images, and redundant APIs need better design judgment and outcome checks, not another universal tick rule.
- **General cleanup and transcript retention.** Worktrees, bulk logs and raw evidence have no new deletion policy. Z11 authorizes only the specifically recovered original-session wipe after its prerequisites, not a general purge.

These are problem statements, not commitments to a framework. D6 excludes a contested-authority precedence subsystem.

## Stacked implementation plan

GO authorizes the local run in order S1, S2, S2a, S3, S4, S5, S6. Create pi-stack `feat/streams-must-fix` at `/home/alphalab/Projects/worktrees/pi-stack-streams-must-fix` from exact base `3acf0f01e6084a317b89cef3a86f4781e60877cf`. All code/test/local-commit writes occur there. Keep concise TODO.md and PLAN.md there as process artifacts, not stream files or commit noise. Pin matching pi-web source first and use its same-named isolated local branch. Never deliver installed dist edits.

Each code commit includes a new regression actually run on its immediate parent before implementation, then focused green and the full offline suite. Record commands/results in its commit body and one progress row per commit. Do not manufacture historical red evidence or call old-candidate tests a baseline. Inspect/deslop each diff before committing. Do not enable a partial liveness stack whose safety boundary is absent. Pi-web/bot rows are companion source changes, not pi-stack commits. If bot owning source is unavailable on options-01, retain exact add-file adapter contract patches under this docs folder without claiming deployment. Do not invent edits to unknown owning paths.

After amended docs plus baseline checks, and after each local code commit, report the exact status line, SHA, red/green commands and results, full-suite count/result, disposable result, and progress-file update to the parent. Wait for acknowledgement before the next commit. This is a reporting checkpoint, not a product gate. If the reporting tool is unavailable, emit the status and return a clear checkpoint rather than silently batching commits. No push, PR, merge, other-branch rebase, live lifecycle action, or docs-worktree commit is authorized for this writer.

### Verification setup on options-01

Use a new disposable project, source fixture repo, stream directory, explicit private index, and private `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, and `XDG_STATE_HOME`. The isolated pi-web uses dedicated config/data/session paths and a port other than 8504. Set all three XDG variables for every verification process and any dedicated user unit. Pass the private index through `--home` on every command, including the real tick. Set `PI_WEB_URL` explicitly. Never borrow an existing stream/session or touch live8504, the production systemd tick, `~/.pi-stack`, or `~/.local/bin`.

`--home` alone is not isolation. `init_project()` registers that index in the homes file under XDG at `project.py:341-348,370-386,610-611`. The production service runs the global tick at `systemd/pi-streams-tick.service:6` and would discover a test index registered under shared XDG. Prove the production/test selection separation with private fixtures. Do not run production discovery or write its homes file. Never stop or edit the production timer to compensate.

LAYER 1 gives verification configuration a separate filesystem identity. LAYER 2 checks the boundary. Add an offline production/test-XDG fixture before any real-stream test. With shared XDG, baseline global selection includes the new test index. With private XDG, production selection excludes it and the private unit carries the same isolated environment.

Use the real pi-web/native Pi integration in a dedicated verification instance and only `openai-codex/gpt-6.1-sol`. Use supported instance configuration, not guessed flags. Read existing auth in place only. Never copy, print, modify, or replace credentials and never log in. If isolation needs copied credentials or new login, stop that check and report blocked. Never fall back to production. Usage/quota errors stop this implementation run without a model switch. Drive only new disposable sessions. Run a long-lived verification server in tmux, never a background bash process. If needed, use a dedicated user unit executing `pi-streams tick --home <private-index>` with the same private XDG paths. Keep generated context and fault fixtures outside Git.

Run baseline and candidate with the same small task and controlled clock/error observations. Name and retain both results under the disposable stream's evidence folder. Fault injection occurs at the external boundary of that stream only. Do not exhaust real quota, expire real auth, modify credentials, fill the host disk, or send production alerts for a test. A real notification test uses the existing authorized ZF DM route once and labels itself as verification. Mocks alone cannot certify that route.

The existing offline suite is `python3 -m unittest discover -s pi-streams/tests`. Keep its stub-only isolation from `tests/support.py:26-50`. In the pinned pi-web source checkout, use `npm test -- <focused-test-path>` for the command, archive, and maintenance cases. Its installed package metadata defines `npm test` as `vitest run --config vitest.config.ts`. No upstream test filename is claimed to exist until that source pin is checked out. The planned real-stream cases below are additional tests, not a claim that the candidate already exists.

### External prerequisite E. Reliable box transport

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `box: reuse Twingate across remote CLI calls` | Owning deployment source for `pi-web-cli-remote`, `options-01-ssh`, and wrapper tests. Locate and pin it first. | Item 9's reconnect classification. Repeat read-only disposable-stream status calls from the box. |

External prerequisite E is Grok Bot's work and is skipped by this implementation writer. This companion change does not go into pi-stack or the generic host CLI.

### Stack S1. Code-owned artifact operations, then their callers

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: publish snapshots and scope automatic commits` | `engine/{project,threads}.py`, create/persistence/Git tests. | Items 13/15. Short-write, retry, unrelated staged files, binary/data exclusion. |
| `streams: parse STATE Goals and update the current objective only` | Proposed `engine/artifacts.py`, `project.py`, STATE section/goal tests. | Item 10. Explicit North Star/current-objective shape, fallback, duplicate rejection, exact untouched bytes and intervening-section preservation. |
| `streams: append STATE Log and rotate overflow under the stream lock` | STATE helper, `engine/{cli,tick,project}.py`, protected-file/schema changes, proposed `test_state_rotation.py`. | Item 6. Only Log capped at 30, occurrence identities, collisions, append races, durability, paused/outage/eventless ticks, exact rule retirement and steer logging. |
| `streams: teach STATE tiers and remove conflicting stream defaults` | STATE/history templates, retire STREAM/DECISIONS templates, AGENTS steps, kickoff Interview/Ratify/Plan, stream skill/brief, conditional overlay, design docs, literal tests. | Items 4/12 after code exists. No caps, objective-only edit grant, real append operation, AGENTS/STATE-only reads, no TODO/PLAN or invented-file imports, unchanged non-stream overlay behavior. |
| `streams: bind handovers to full session identity` | Brief/rendering, close checks, stream skill, brief/close tests. | Item 14's predecessor/successor case and owned report reference. |

STATE parsing/mutation code precedes template/skill callers. Do not activate a legacy stream with mixed old/new schemas. On the new disposable stream, verify Goals/Rules/Log and kickoff's objective/no-cap contract. Append 31 Log entries, tick to 30 plus one exact history file, preserve Goals/Rules/an intervening test section, and inspect actual reads and Git contents. No bulk-output inventory commit remains. This stack does not migrate or resume an existing stream.

### Stack S2. Correct identity, receipts, archive reads, and rotation

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: resolve the designated coordinator before dispatch` | `engine/{threads,tick,doctor}.py`, new/adopt/status tests. | Item 8's stale/ambiguous IDs, reserved worker role and first-line ratification before dispatch effects. Verify one designated disposable coordinator. |
| `streams: expose archive-stable evidence reads` | `engine/{sessionlog,piweb}.py`, `bin/pi-web-cli` if needed, new evidence tests. Small pi-web metadata exposure only if needed. | Item 5's exact hashes before/after a safe disposable archive. |
| `streams: distinguish transport acceptance from applied steer` | `bin/pi-web-cli`, `engine/{piweb,tick,sessionlog}.py`, receipt command/tool, coordinator template, CLI/tick tests. | Item 7's accepted-only, consumed-only, applied, blocked, and uncertain cases. Inspect a real changed artifact. |
| `pi-web: reject stale automatic admissions after stop or cancel` | `jmfederico/pi-web` `src/server/sessions/piSessionService.ts`, narrow persisted control-delivery generation, matching CLI/engine adapter fields, and focused race tests. | Delay a wake, recovery, and RESUME after sender revalidation. Stop, release, and observe zero task effects. Fresh explicit input remains usable. |
| `streams: reuse coordinators and refuse unsafe explicit rotation` | `engine/{tick,threads,project}.py`, rotation/scenario tests, obsolete-policy docs. | Item 11. No size/age rotation, no busy abort, safe clean replacement and crash recovery. |

Update the bot relay's receipt handling in its owning deployment source alongside this stack. It must stop claiming a transport receipt is delivery. Land the CLI response semantics and caller changes together or version the added fields without breaking the caller.

### Stack S2a. Explicit existing-stream migration

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: plan a lossless stream-root artifact migration` | `engine/{cli,project}.py`, artifact helper, proposed `test_artifact_migration.py`. | Item 16. Exact legacy STATE reconstruction and raw STREAM/DECISIONS provenance, stable timestamps/fallback, explicit Goals/active-Rules/history map, ambiguity refusal, path fence, failures/ and unchanged markers. |
| `streams: apply migration once with one scoped commit` | Migration journal/schema marker, scoped Git helper, tests. | Crash before/after history/STATE/legacy-retirement/commit, one migration Log seed, second-run zero commits, unchanged excluded-file and worker-worktree hashes, no session operations. |

Run this on a new disposable legacy-layout stream before enabling DCR there. Real existing-stream migration requires separate rollout by the lead after per-stream evidence review and tested deployment. This writer never migrates an existing stream or writes worker worktrees.

### Stack S3. Fixed-template DCR, code before instructions

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `pi-web: compact only at the expected idle checkpoint and retain maintenance input` | `jmfederico/pi-web` source `src/server/sessions/{sessionCommandService,piSessionService}.ts`, narrow persisted maintenance record, capability/result fields, and focused tests. No installed `dist` edits. | Busy/direct-input races, accepted input across a restart during compaction, and newer input before saved RESUME. A command-start reply must not pass as compaction completion. |
| `streams: add native command-run and compaction-result observation` | `bin/pi-web-cli`, `engine/{piweb,sessionlog,doctor}.py`, CLI/doctor tests. | Call the real command endpoint and identify one successful compaction entry. |
| `streams: implement argument-preserving poteto-mode invocation` | Engine/receiving adapter and installer capability checks, actual prompt-expansion tests. | Exact goal punctuation/newlines and loaded skill; fixed DCR read-path prefix survives the non-leading invocation. |
| `streams: sync compact and resume with the fixed 150k DCR template` | `engine/tick.py`, small code-owned prompt renderer, maintenance state/adapter tests. | Item 3. Shared STATE goal resolution, AGENTS/STATE reads, no agent-written resume, same SID, no active-tool abort, changed objective/stop/input races. |
| `streams: describe the implemented DCR sync in coordinator instructions` | AGENTS/skills and literal tests only after code is present. | SYNC safely updates STATE Goals and appends Log, preserves active Rules, and tick-rotates only Log. No TODO/PLAN/index read mandate or failure-driven rule/skill change. |

Build the exact tested pi-web source artifact and run it only in the isolated verification instance before enabling this stack there. Require its maintenance capability in doctor. Do not replace the global installed package or production service. The current installer skips an existing pi-web, so merely reinstalling pi-stack is not this deployment step. Do not revive the superseded 252k native-hook work. Real verification must show no interruption of the running tool and actual resumed task progress.

### Stack S4. Make the existing tick a driver

| Commit title | Files | Test and real-stream check |
|---|---|---|
| `streams: re-inject the current goal whenever driven and stalled` | `engine/{project,cli,tick,piweb}.py`, shared goal/prompt renderer, tick tests. | Item 1. Identical injection across stall reasons and missing dispositions; no `out()`/pending-event veto; STATE objective/North-Star fallback, worker-to-stream routing, preserved human ask. |
| `streams: isolate observations and report per-stream tick health` | `engine/{tick,doctor,piweb}.py`, failure/doctor tests, systemd pass reporting if needed. | One unavailable worker does not skip another reinjection or STATE Log rotation. One healthy stream cannot hide a failed pass. |
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
| `pi-web: expose exact-point fork and single-original retirement` | Owning session source, bin/pi-web-cli and engine/piweb.py adapters, native checkpoint hook only if required, capability/scope tests. | Inclusive entry-ID fork, cancellation/uncertainty, singular archive then existing archived DELETE. No archive-tree or worker-worktree writes. Prime requires independent proof. |
| `streams: admit authenticated failure ratification` | Engine CLI/operation record and existing bot deployment intake, provenance tests. | Item 18 O4. Exact episode/session set, deduplicated genuine notice, explicit exceptional payload. Assistant quotes and readiness signals do not ratify. |
| `streams: run ratified fork DCR and wipe only after the fork streams` | Failure operation state, shared fixed DCR renderer, registry/receipt adapters, fault tests. | Human ratification, exact prefix, same fork through DCR, observed streaming before original wipe/marker removal, crashes and cancellation at every boundary. |
| `streams: teach park-and-log failure behavior` | Generated stream prompt and skills after the code contract. | No self-remedy of the harness environment; only explicitly ratified additional instructions enter continuation. |

**F-DCR round-trip check on options-01.** In the isolated disposable instance, create a coordinator and worker, complete a successful multi-tool turn, then inject a labelled auth/outage failure without changing real auth. Inspect both applicable lastgood files and the unchanged environment. Send the authenticated test ratification through the real bot-to-engine route. Verify the exact inclusive prefix in each recovery fork, successful fixed DCR on its returned SID, observed post-RESUME streaming, and only then singular original archive/delete and marker removal. Keep the fork, exact evidence, unrelated sessions and worker worktrees unchanged. Capture original/fork IDs, checkpoint, compaction, stream-observation and delete receipts. Repeat fault/crash cases before enabling production recovery. No destructive operation is executed by this catalog task.

### Rollout and rebase

For every code commit, run its new regression on the immediate parent, then focused green and the full offline suite on the implementation. Run each stack's named real disposable-stream check after that stack. Retain exact source/dependency revisions and results. Fixtures alone or HTTP 200 are not real task-effect evidence. Blocked checks stay labelled blocked and capabilities stay gated. S6 requires the actual isolated ratified F-DCR round trip before any S1-S6 completion claim.

Production activation requires the integrated S1-S6 capabilities, the off-host route, and explicit migration of that stream. Earlier stack checks use only disposable sessions. Do not enable a production driver or DCR path before S6 supplies the receiver's Z11 parking boundary, or let an unsupported classes 2-5 handoff fall through to an ordinary prompt. This gate orders deployment without delaying Pi work for Prime or track 3.

The parent/driver owns merging the verified stack and rebasing other branches before streams-on-prime work. This writer makes local commits only. Existing-stream migration remains explicit, source-backed, and separate from template upgrade. G14's harness-stream goal reset belongs to lead-owned rollout, never this isolated implementation run.

## Decisions

| Decision | Reason and evidence |
|---|---|
| Apply Z13-Z15, GO, and G25 over older layouts; retain other Z1-Z11 safety calls. | Z15's single STATE supersedes G17/G21/G22. GO authorizes this isolated local run. It does not authorize this writer to touch live streams or merge. |
| Keep liveness and recovery as separate catalog items. | Z1 requires forward driving even with no new event. C rank 2 shows a different recovery predicate. |
| Use tick-observed 150k with Z8's fixed engine read-state/goal resume. | Z8 replaces the agent-written resume. Preserve Z3's no-interruption/same-session maintenance and do not revive 252k. |
| Reuse safe-point steering, then compact only when idle. | The installed agent loop admits steering after tool batches. Native manual compaction aborts active work. |
| Add a small pi-web idle/checkpoint guard, not a native Pi core hook. | A status-then-compact race can interrupt a direct prompt. Z3 does not require per-request compaction. |
| Land receiving-side stop invalidation before any automatic RESUME. | The adversarial review demonstrated that stopping a runtime does not prevent a later prompt reopening it. Sender-side checks alone leave a race. |
| Persist accepted maintenance-time input and reconcile it before old RESUME. | The existing compaction Map is volatile and drains independently. Its acceptance does not establish durability or stop ordering. |
| Isolate all three XDG homes, the index, session/config/data paths, and verification port. | G25 and the stop/compaction review require separation from production discovery and port 8504. Auth is read in place only. |
| Store only current drive, recovery, delivery, and maintenance facts. | Tick state retains dispatch progress and operation IDs. Pi-web owns accepted maintenance input and native outcomes. Z2 and P3 reject a general control engine or competing input queues. |
| Keep applied-steer receipts, but no per-ask completion ledger. | Z5 requires actual application. Z2 separately defers product lifecycle and self-grading. |
| Use ZF-only Slack DM and episode-based suppression. | Z4 chooses the destination and quiet behavior. Full-disk notices must originate off-host under G5. |
| Read "#37" as corpus row 37, not a GitHub issue. | G16 corrects the ambiguous original brief reference. GitHub #37 is the program's draft PR. |
| Retain archived raw evidence without restoring retired coordinators. | Both exact row-37 receipt hashes survive. The failing component is the live-path binding. |
| Refuse unsafe manual rotation instead of building queue/callback migration. | A demonstrates native busy protection and successful manual replay. Z3 removes routine replacement pressure. |
| Bind handovers to session identity and reuse atomic snapshot writes. | Both are low-blast-radius source-proven defects, independent of the deferred lifecycle design. |
| Keep one STATE with ordered Goals, Rules, Log. | Z15 supersedes all older names. Only Log is capped at 30 and tick-rotated. Goals/Rules are rewritten in place, and an intervening level-two section is preserved without building Asks. |
| Use explicit North Star/current-objective subsections and one resolver. | Goals' first line carries ratified authority and its Charter subsection retains remaining terms. The coordinator may update only the objective. No goal completion flag or separate CURRENT section exists. |
| Retain exact retired rules, log new rulings and ZF steers. | Z15 moves superseded rule text to timestamped rule-retired history. Steers enter Log on arrival and later rotate normally. No tag field or automatic authority classification. |
| Disable stream TODO/PLAN planning; leave non-stream behavior unchanged. | Goals plus Log replace the global-overlay plan inside streams. History/context/checks/handover are on demand, never extra mandatory turn reads. |
| Exclude invented artifacts and remove item 17 without renumbering. | Z13 permits only stopping references to invented files. There is no import/migration/ownership work or bulk-output inventory commit. Current count is 17, split 11 mechanical and 6 artifact fixes. |
| Migrate only explicit legacy stream artifacts, once, with one scoped commit. | Z15 maps STREAM into Goals/active Rules/history, DECISIONS into active Rules/history, and old STATE into history before fresh STATE. Retain exact bytes/provenance, failures/ markers, and worker hashes. Ambiguous authority refuses apply. TODO/PLAN and invented files are excluded. |
| Only usage-limit recovery stays automatic. | Z11 narrows G5 classes 2-5 to park, human repair/ratification, F-DCR and original wipe. Readiness alone cannot release them. |
| Choose O1-O4 defaults and fail visibly on unsupported capability. | Last-good IDs, exact Pi/Prime fork semantics, correlated RESUME streaming and notice provenance are implementation facts, not ZF policy cards. |
| Preserve required evidence and ownership before singular original deletion. | Native fork is not a byte archive or callback transfer. Streaming is Z11's timing condition, not the only safety prerequisite. No archive-tree or general cleanup. |
| Carry track 3 verdicts without waiting for or silently adopting its alternatives. | G18 keeps the dictated MVP independent. The available verdicts and reasons are included in the Z coverage table. |
| Keep Twingate repair in the box deployment, not pi-stack. | G15 names the faulty wrappers. They are not tracked host-CLI files at the base revision. |
| Treat claimed coverage as hypotheses, not prevented-row counts. | A corrects row 37 and row 72. C qualifies rows 54 and 75. No controlled treatment replay exists yet. |
| Keep doc edits within catalog, artifact map, and progress; no docs-worktree commits. | The parent collects these artifacts. Exact companion adapter patches are allowed here only when bot owning source is unavailable. Source commits belong only in the named isolated checkouts. |
| Keep per-commit red/green/full-suite evidence and report before the next commit. | The parent owns review/reporting. Without the supervisor tool, return an explicit checkpoint instead of batching commits or interpreting silence as acknowledgement. |

### Historical investigation and interrogation record

This record predates Z13-Z15. Its source findings remain evidence, but old layouts, counts, review readiness, and read-only status below do not describe the authorized implementation run. Current amendments and actual checks are in `12-track-1-progress.md`.

Historical throughput checkpoint was n/a for the read-only investigation. Current throughput is one verified local code commit per parent reporting checkpoint, with a disposable check after each stack.

The corpus, A, B, C, deep research, issue snapshots #33 through #36, the harness DECISIONS and ZF brief, and program documents 00 through 03 were read. Main was verified at `3acf0f0`. No production stream was prompted, steered, stopped, rotated, archived, or spawned.

Parent in-memory probes reproduced ten baseline facts without filesystem or network effects. An idle coordinator with empty pending gets no wake. An unchanged quota error blocks all recovery prompts. `ensure_coordinator` trusts an active registry row without checking runtime. `_resume_or_spawn` adopts a nonempty unrelated same-directory session. The ratification parser accepts a marker buried in history. A predecessor's role handover satisfies close for a successor. Worker role validation accepts `coordinator`. Existing config without an index row is not re-registered. Automatic commit begins with `git add -A`. One fresh stream hides a stale neighbor. Exact archived receipt hashes and the frozen STATE blob size were checked separately.

The proposed post-fix tests and real-stream checks have not run because no fixes are implemented. No full test-suite or deployment pass is claimed.

Laziness Protocol changed the design to deletion-first defaults, existing tick phases, and refusal at unsafe rotation rather than a transfer subsystem. Fix Root Causes kept the continuation predicate, recovery circularity, evidence locator, and Git staging operation separate. Guard the Context Window split the source audit into read-only slices. Sequence Work into Verifiable Units shaped the small commit stacks. Prove It Works prevented accepting transport responses, file-size changes, or workflow dispatch receipts as completion.

### Historical adversarial review and lead judgment

**Historical review, before this amendment.** A single `poteto-agent` reviewer on `openai-codex/gpt-6.1-sol` reviewed the original 15 items against the source and binding calls. This is same-model adversarial review, not multi-model consensus. The first review attempt could not obtain a readiness handshake and was not counted. After an explicit readiness reply, retained review run `f9d54e5a-962f-487c-b752-98c43a98c7ac` returned a substantive review. The workflow wrapper had returned launch receipts before its children finished, so the parent consumed each actual terminal report instead.

The review challenged every item's layer and admission bar. It defended the bounded drive, recovery, delivery, and maintenance records rather than requiring a general engine. It also confirmed the source-derived handover and atomic-write fixes clear the low-blast-radius bar. It rejected carrying forward the superseded 252k hook, treating body delivery as application, or interpreting archived evidence as lost bytes.

| Finding | Lead judgment and correction |
|---|---|
| W1. A stop can race an already-selected automatic prompt, and the safety work was scheduled after S3. | **Act on.** Item 7 now requires receiving-side generation validation for every automatic wake, recovery, and RESUME. S2 lands this before S3. Race tests retain explicit new user prompting after stop. |
| W2. Accepted compaction-time input is only in memory and may drain before the saved resume. | **Act on.** Item 3 now requires recoverable maintenance-time input identity/body/order/attachments and receiving-side reconciliation of newer input before old RESUME. Crash-during-compaction and newer-stop tests were added to the plan. |
| W3. A private index without private XDG is discoverable by the production timer. | **Act on.** The real-stream recipe now isolates XDG for every CLI and private unit, sets an explicit verification pi-web destination, and checks unchanged production homes bytes. |

No warning was dismissed as style. No critical finding was established. Focused recheck run `96d8d074-ec39-4378-9cca-135ee306920b` closed W1-W3 and found no new concrete issue in their corrections. The reviewer confirmed the single-operation event path does not create a competing input queue. These are catalog-specification verdicts only. They do not claim that implementation, race, or deployment tests have passed.

Those historical artifact checks covered the original 15 rows only, not this amendment. The steer-2 input audit and its Z11 native-capability follow-up were consumed from the actual managed report, not a workflow launch receipt. They established source gaps and safety prerequisites, not approval of this later draft. The follow-up inspected native entry IDs, tool-batch ordering, inclusive fork, singular deletion versus archive-tree, correlated streaming and callback ownership with read-only source and mock-only probes. No live fork/delete or Prime test was run.

**Historical pre-Z13 amendment interrogation.** Actual child run `b96a2f70-5e5d-4dfd-bff2-e84f5138895f` completed and its terminal report was consumed. It found no concrete critical or warning findings and judged the 18-item catalog ready for first-pass review. It checked every layer/bar, Z1-Z11/G17/G18 coverage, the four Z11 defaults, migration and failure-marker preservation, receipt/stop safety, exact fork and deletion scope, and code-before-template ordering. This was one same-model review on `openai-codex/gpt-6.1-sol`, not multi-model agreement. There are no Act On, Consider, Noted or Dismissed findings from this pass.

The reviewed draft hash was `c3771f5e1fb426647cc49649295643215290c4c9ad57c514fd6b3c3487083bda`. Afterward the parent added only source-cited Prime capability/default clarification, the explicit integrated-production-activation gate, and this record. Those narrow clarifications were parent-checked; no second independent review of them is claimed.

Historical direct artifact assertions passed for the then-current 18 unique review rows and matching details, the disjoint 11-mechanical/7-artifact partition, all seven detail fields, Z1-Z11 verdict annotations, O1-O4, failures/ migration, and the F-DCR round-trip plan. Its whitespace and stale-design checks passed against that superseded design, which excluded active STATE reads. Those assertions are not a review of this Z15 amendment. The current contract requires active STATE reads and retains neither agent-authored resume nor disposition-gated reinjection.

Prove It Works required checking the actual catalog and terminal child report. Guard the Context Window kept re-entry and capability checks targeted. Sequence Work into Verifiable Units kept code ahead of template callers and made integrated recovery a production gate. At that historical checkpoint, progress remained in this artifact only, source was clean at `3acf0f0`, and no other project file had been edited, staged, or committed by that amendment. Current progress now belongs in `12-track-1-progress.md`. No implementation, full-suite, deployment, live recovery, or Prime-server verification is claimed. The four open engineering items retain chosen defaults and parked fallbacks; none requires a new ZF policy decision.

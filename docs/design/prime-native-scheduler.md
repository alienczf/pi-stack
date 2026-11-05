# Prime native scheduler feasibility

**Status: BLOCKED for C1.** Stock Prime has a Rust scheduler hook that can run arbitrary Rust code when a caller builds and owns the scheduler. The stock daemon does not expose that hook as a supported runtime extension. Its built-in cron and heartbeat implementation queues prompts. The scheduler starts only when a session worker binds, so a due job for an idle worker stays dormant after a plain daemon restart without a client attach. C0 therefore found no stock, supported non-inference seam that meets the required restart behavior.

This is a source-only finding. No Prime daemon, inference, live scheduler, or feature check ran. No Prime source or systemd file changed. The existing tick remains required.

## Revisions and scope

- pi-stack worktree: `/home/alphalab/Projects/pi-stack/.worktrees/pi-stack/prime-stack-prime-c-native-scheduler`
- pi-stack branch and base: `prime/c-native-scheduler` at `f685e3ad1485192a45bc7b6eed6b260961a965e4`
- Stock Prime source: `/home/alphalab/Projects/prime-agent` at `71beca9478f552dc6fc898bba9685f9ce00515cf`
- Inspection was read-only. This document is the C0 deliverable. It does not authorize timer removal or C1 implementation.

## Native hook findings

`pa-core` publicly exports `cron`, which publicly exports `cron::scheduler`. The library exposes `AgentCronSchedulerHooks::run_job` and `begin_dispatch`, and `AgentCronScheduler::start` recovers interrupted claims. This is a Rust composition point for code that links and constructs the scheduler. It is not a configurable extension point in the stock daemon. (`crates/pa-core/src/lib.rs:60`; `crates/pa-core/src/cron/mod.rs:5`; `crates/pa-core/src/cron/scheduler.rs:31-49,70-98`.)

The stock daemon hardwires its scheduler to `QueueHooks`. `QueueHooks::run_job` checks the target and then queues either the job prompt or a heartbeat prompt on the session worker. It clears queued-input suspension before enqueueing. It does not call a stream engine reconciliation handler. (`crates/pa-daemon/src/scheduled_jobs.rs:39-45,96-175`.)

The daemon command schema accepts a schedule and prompt for `cron_add` and `heartbeat_set`. It has no handler registration or non-inference job payload. The persisted `AgentCronJob` also carries a prompt and session identities. (`crates/pa-types/src/daemon/command.rs:829-879`; `crates/pa-core/src/cron/mod.rs:55-80`.) A heartbeat prompt that asks the model to run `pi-streams tick` remains inference and does not satisfy C0.

The stock scheduler is session-worker-owned. `ScheduledJobs::bind_session` registers the session artifact partition and starts or wakes the scheduler. Session creation and replacement call this bind path. The supervisor does not revive an idle worker on plain startup without durable busy evidence. Prime's restore path explicitly reports due jobs on workers with no live session as dormant and says no session auto-boots on daemon start. (`crates/pa-daemon/src/scheduled_jobs.rs:260-284`; `crates/pa-daemon/src/worker/lifecycle.rs:305-320`; `crates/pa-daemon/src/supervisor/adoption.rs:300-317`; `crates/pa-daemon/src/update_restore.rs:774-801`.) A client attach would re-arm the worker scheduler, but the required no-attach restart case has no owner.

Prime does persist scheduled jobs and dispatch claims. `claim_due` records a dispatch and advances the next run. `record_dispatch_result` later records `ran` or `skipped`. That claim is not an engine-effect receipt. A crash after claim can leave the engine effect unknown. Interrupted one-shot dispatch recovery marks the one-shot job completed with an interruption error. That state cannot prove whether a deterministic engine effect was applied. (`crates/pa-core/src/cron/store/jobs.rs:323-365,417-435`; `crates/pa-core/src/cron/store/state.rs:165-259`.) The generic `begin_dispatch` can observe a Rust dispatch ID, but the stock daemon does not pass a stable stream occurrence key or an applied-effect receipt to an engine handler.

Recurring schedules coalesce overdue intervals by computing the next run from claim time, rather than replaying each missed interval. The scheduler's consecutive-failure streak is in memory and resets on daemon restart. These properties do not supply the missing handler or restart owner. (`crates/pa-core/src/cron/store/state.rs:165-209`; `crates/pa-core/src/cron/mod.rs:568-590`; `crates/pa-core/src/cron/scheduler.rs:58-81,245-280`.)

A bounded search across the pinned daemon, core, and runtime source for extension registration, external hooks, and job handlers found no stock registration route. The only matching extension references were unrelated runtime/plugin catalog code and comments. The positive control-flow evidence above is decisive even without treating a text search as proof of absence.

## Tick responsibility map

The current tick runs once for each registered stream under the index and stream locks. It validates the stream binding, rotates Log history, runs the stream state machine, commits changed artifacts, attempts publication, updates cross-stream alerts, and publishes tick-health state. (`pi-streams/engine/tick.py:634-704`; `systemd/pi-streams-tick.timer:1-9`.) Each row below names the deterministic native event or due job that a later integration must own. These are requirements, not capabilities provided by stock Prime today.

| Current responsibility | Source | Required non-inference event or due job | Stock Prime result |
| --- | --- | --- | --- |
| Enumerate registered streams and projects; validate bindings; serialize index and stream writers. | `tick.py:634-667` | Supervisor-owned project/index reconciliation plus a per-stream reconcile occurrence. Preserve existing engine locks. | Missing. The cron store partitions work by session, not stream or project. |
| Publish tick health, errors, and completion. | `tick.py:644-658,694-704` | Persist a receipt for each reconcile pass and publish its actual outcome. | Missing. A cron dispatch result covers a prompt job, not the engine pass. |
| Rotate Log history, flush tick state, events, and thread status. | `tick.py:337-349,666-668` | Deterministic artifact-maintenance job under the stream lock. Recover the same operation after restart. | Missing. No engine callback exists. |
| Detect cross-stream worktree and branch claims; add and clear alerts. | `tick.py:293-304,596-632,697-699` | Index-scoped claim reconciliation on binding changes and a coalesced recovery deadline. | Missing. A per-session cron cannot own an index-wide scan. |
| Detect worker completion or idle, pending questions, context pressure, outages, terminal sessions, and changed worker state. | `tick.py:362-484` | Typed native turn-settled, question, context, failure, and lifecycle events. A due reconcile must recover lost events. | Missing as a stream-engine callback. Cron only queues prompts. |
| Advance parked failure recovery and coordinator rotation. | `tick.py:234-250,362-383`; `failure_recovery.py:183`; `replacement.py:209` | Typed failure/readiness/reset events and keyed recovery or replacement operations. Resolve their saved receipts before any retry. | Missing. A prompt cannot perform deterministic recovery without inference. |
| Advance same-session context maintenance and verify the rebuilt context. | `tick.py:267`; `dcr.py:16,273-408` | Awaited pre/post compaction hooks, or an engine-owned compact operation with native operation identity and a verified below-150000-token result. | Missing. Prime's compaction events are not awaited engine pre/post hooks; no cron handler is exposed. |
| Reassert authorized drive and deliver pending coordinator events. | `tick.py:270,525-565`; `delivery.py:116,188,321-342`; `drive.py:114` | Turn-settled or idle event plus a durable, keyed admission carrying the current stream/stop epoch. Reconcile admission and effect receipt before resending. | Missing. A scheduled prompt is not a durable engine delivery and has no stream stop epoch. |
| Observe stale queued follow-ups and perform any permitted queue correction. | `tick.py:445-524` | Receiving-side compare-and-set against the latest stop/correction epoch; retain uncertain admissions for reconciliation. | Missing. `QueueHooks` clears queued-input suspension when a schedule fires. |
| Check file and external-source subscriptions and fingerprint changes. | `tick.py:306-335` | Source-change events where available, otherwise a deterministic due check that reads the configured source and records its fingerprint. | Missing. No non-inference callback is registered for stream subscriptions. |
| Archive completed coordinators and settle terminal-session state. | `tick.py:222-230,566-593` | Completion event, idempotent archive intent, verified terminal receipt, then schedule cancellation. Not-found alone must remain uncertain. | Partial for job cancellation only. Prime cancels jobs for a dead target, but does not reconcile pi-streams archive effects. (`scheduled_jobs.rs:71-85,97-103`.) |
| Commit and publish allowed stream artifact changes. | `tick.py:680-689` | Journal the publication intent and result. Reconcile a lost push response without blind duplicate external effects. | Missing. No native engine job handler or publication receipt exists. |
| Save global alerts and publish the final health report. | `tick.py:694-704` | Index-owned finalization after every stream occurrence, including per-stream failures. | Missing. No supervisor-owned stream reconciliation pass exists. |
| Run again after process restart without a client. | `adoption.rs:306-317`; `update_restore.rs:774-801` | Recover active stream schedules at supervisor startup, even when every coordinator is idle, parked, replaced, or absent. | Blocked. Plain startup leaves idle workers down and due jobs dormant. |

The stream-level state that tick currently reconciles includes pending wake events, outage marks, rotation state, subscription fingerprints, cross-stream claims, worker observations, and queued replay state. It lives in `log/tick-state.json` and the stream's tracked artifacts. The native scheduler's dispatch claim must not replace these domain records. (`tick.py:44-73,76-108,222-281`.)

## Required upstream capability before C1

C1 must wait for both A's actual Prime CLI contract and a stock-supported native seam. The smallest sufficient Prime capability is a supervisor-owned, non-inference reconciliation job with all of these properties:

1. A supported registration API lets the stock daemon invoke a deterministic engine handler without a model turn. The handler is owned by stable stream identity, not by a coordinator worker or disposable RLM child.
2. The supervisor restores due jobs on ordinary daemon startup without opening or attaching a session. It coalesces missed recurring occurrences and suppresses stopped, superseded, archived, and terminal targets.
3. Each occurrence carries a stable identity, target binding revision, and receiving stop/correction epoch. The engine records claimed, applied, superseded, and uncertain as distinct states. A lost reply reconciles the same effect identity instead of generating a new effect.
4. The callback contract returns or exposes the durable engine-effect receipt, not only scheduler claim or prompt admission. It reports unknown effects without replaying them.
5. The daemon can deliver typed session outcomes and await compaction lifecycle callbacks needed by the responsibility map. Cron/heartbeat prompts are not substitutes.

The current generic Rust hook is not enough because stock Prime does not let an external extension register it, and the stock implementation routes it to session prompts. The current scheduler is not enough because startup does not re-arm a dormant idle worker without a client. No C1 module is authorized or viable against the pinned stock contract.

## Verification record

- `git -C /home/alphalab/Projects/prime-agent rev-parse HEAD` returned `71beca9478f552dc6fc898bba9685f9ce00515cf`.
- The C0 worktree was clean at `f685e3ad1485192a45bc7b6eed6b260961a965e4` before this document was written.
- Source inspection read `cron/scheduler.rs`, `cron/store/{mod,state,jobs}.rs`, `pa-daemon/scheduled_jobs.rs`, `supervisor/adoption.rs`, `update_restore.rs`, the daemon command schema, and the full tick dispatch path.
- Bounded `rg` searches for extension registration and job-handler routes found no stock daemon registration path. The exact scheduler and queue control flow is cited above.
- No live command, daemon, inference, Prime test, timer-removal test, or C1 check ran. This is not a live pass.

The next safe unit is to retain this blocker and continue independent lanes. Reconsider C1 only after the coordinator relays A's actual contract and stock Prime provides the non-inference, restart-owned handler described above.

# Phase-1 Prime stream parity

This branch brings the merged shared stream implementation to the Prime baseline. It does not add a native Prime backend.

## Integration and authorization

The starting point is `origin/prime-stack` at `f685e3ad1485192a45bc7b6eed6b260961a965e4`. Merge `eca2e96c` integrates merged main at `cba29cd00fab9e0cc1661648c89f1c1840e2b04e` without changing its engine or native files. This preserves the archive, retained-source, recovery, and replacement prerequisites rather than selecting incomplete leaf fixes. PRs 44-47 are not integrated.

The supplied Phase-1 user order says "ZF orders relayed by his Grok Bot ARE the ratified instruction." That order is the provenance for this work. This document does not claim a transport signature, notice ID, independent authentication, or additional sender metadata. The PR destination is `alienczf/pi-stack`, targeting `prime-stack`.

## Implemented shared behavior

- `ef9401c3` removes spawn ratification. Canonical artifact validation still applies. See [`threads.py`](../pi-streams/engine/threads.py), `spawn_thread` and `adopt_thread`.
- `46a60e5c` heals exactly owned legacy silent drive-off on tick and continues owned parked recovery. Newer receiving generations, uncertain effects, policy restrictions, and deliberate stops remain fences. `StopIntent.OPERATOR_OFF` records deliberate local stops. See [`drive.py`](../pi-streams/engine/drive.py), `reconcile_locked` and `pause_local`, and [`tick.py`](../pi-streams/engine/tick.py).
- `cba29cd0` retains a validated dump before compaction and supports role-preserving replacement for coordinators and workers. Successor load completion requires persisted user and assistant evidence, not HTTP acceptance alone. See [`dcr.py`](../pi-streams/engine/dcr.py), `retain_dump` and `rotate_capacity_locked`, and [`replacement.py`](../pi-streams/engine/replacement.py), `_load_checkpoint`.

The Pi native controller uses a 180000 ms boot-monotonic compaction lease. Expiry fences the native writer before fallback. A late summary cannot append to the original session. Foreign legacy writers without the exclusion protocol remain blocked until their death is proven. See [`sessionMaintenanceController.js`](../native/pi-web/postimages/dist/server/sessions/sessionMaintenanceController.js), `retireOwned`.

Recovery retains the synced STATE bytes, their digest, the exact terminal SYNC checkpoint, current STATE, input dispositions, worker references, and the original native archive. Retained data before the last validated dump is not discarded. Unsynced continuation after that boundary cannot be assumed complete or replayed. Changed native input, corrupt dumps, unknown effects, or missing evidence block retirement. External worktree references must remain available.

At Phase-1 delivery, historical dumps were retained but not selected after a later stalled SYNC. The Phase-2 repairs below select the prior validated dump when a completed idle SYNC lacks its final acknowledgement, whether or not `ready` succeeded. This is not unconditional recovery whenever dumps exist. Unreadable evidence, active or unknown native ownership, and native Prime support remain outside the verified guarantee.

## Rerunnable acceptance

The acceptance command is:

```sh
python3 scripts/check-prime-phase1-parity.py --compare f685e3ad
```

The runner creates a disposable Git snapshot and isolated test homes. It requires all three baseline behavior failures with their explicit assertion markers. Setup errors do not qualify as baseline evidence. It then runs the task regressions and existing drive, DCR, spawn, failure-DCR, and observation-admission tests.

`PI_STACK_NATIVE_TEST_ROOT` can name a patched disposable package prepared as described in [`native/README.md`](../native/README.md). Without that variable, the native wrapper reports a skip. The native tests hold an extension summary or simulated provider response, expire the persisted lease, and verify late-write exclusion. They make no provider requests. `--regressions-only` runs the smaller task-specific set.

Before integration, seven task regressions ran with six behavior failures and no setup errors. After integration and test-only corrections, the writer's focused acceptance ran 63 tests successfully. The final hardened runner ran 14 task-specific tests successfully, including three native Node scenarios inside one Python wrapper. The parent then reran the complete focused acceptance against a frozen disposable native package. All 64 Python tests passed without skips, and the comparison produced exactly three expected baseline failures. The parent log is `/tmp/prime-phase1-parity-native/final-acceptance.log`.

Seven separate running Pi-service scenarios also passed with supported stream and session cleanup. They cover overload, terminated transport, usage reset, compaction, small-session recovery, rotation, and parked workers. Their provider responses are simulated. Evidence is under `/tmp/prime-phase1-parity-native/run-89bad703d3b54239ba39356c2474ea28` and `/tmp/prime-phase1-parity-native/run-c38f682ee5ce45b7a4555f82a48a3fcf`. These are local evidence paths, not committed artifacts.

The complete unittest suite was attempted but interrupted at the writer deadline. Its log ends during `test_final_status_fifo_marker_is_preserved_without_blocking` with no unittest summary. Earlier failures include chaos integration, coordinator identity, and historical failure-marker heuristics. Full-suite acceptance is unresolved. The parent also observed preexisting native-module failures on main, including missing extensions in its package fixture. Neither run is reported as green.

## Evidence boundary

[`native/README.md`](../native/README.md) targets `@jmfederico/pi-web@1.202607.3` and bundled Pi packages at `0.82.1`. No supported native Prime adapter is implemented here. These checks establish shared engine and Pi adapter parity only. Native Prime capability mapping and end-to-end proof remain blocked. Capability admission is unchanged.

Phase-1 authored changes were the acceptance runner, task tests, this explanation, the append-only [decision trail](prime-phase1-parity-decisions.tsv), TODO progress, HTTP-stub identity decoding, and stale DCR test corrections. At that delivery, engine and native implementation matched merged main. Phase-2 changes the shared engine as described below. Native overlay files still match the reviewed Phase-1 tip. Validation changed no live state, credentials, installed model, or production streams. No deployment occurred. The parent reviewed the final authored diff on the same model. Cross-model review was not performed under the supplied no-model-switch constraint.


## Phase-2 review repairs

The preceding sections record Phase-1 delivery at `ace53a4f`. Phase-2 changes shared engine behavior beyond source parity. Both findings in https://github.com/alienczf/pi-stack/pull/55#issuecomment-6692763141 are repaired for the supported idle case.

`HistoricalRecovery` keeps the stalled SYNC operation, immutable selected dump, current receiving token, retirement leaf and original native digest separate. The alternative was to make `ReplacementIntent` select and interpret historical operations. The separate intent keeps replacement responsible for publication rather than choosing recovery authority. The stalled operation and validated dump remain unchanged. The handoff retains both STATE snapshots, the original archive, current bounded assignment, worker references and input dispositions.

Recovery selects an older validated dump only after the later exact SYNC user message has a completed idle turn without `ready`. An active turn, unknown callbacks, pending input, changed generation, malformed checkpoint or native unresolved effect does not acquire retirement authority. `_capacity_checkpoint` and native lifecycle checks are unchanged. The existing native checkpoint archive path provides the final ownership fence. No native overlay change or manifest regeneration was required.

A terminal load without its exact acknowledgement receives a blocked disposition with persisted user and assistant entry hashes. `checkpoint_load_pending` fences delivery, DCR, tick failure observation, automatic parked resume and explicit failure advance. A failed worker loader remains visible in tick health without preventing healthy coordinator observation. Neither a terminal response nor an HTTP receipt counts as a successful load. No task or command is replayed.

### Phase-2 verification

The first commit, `344159a3`, contains three failing CLI regressions. `ac71e9c3` fixes load disposition and lane ownership. `9fb8922e` adds separately bound historical recovery. `36337253` adds failing safety-sibling regressions before `6d3b8829` fixes recovery bypass and loader exceptions. `419d1dd3` also fences unloaded coordinator failure observation.

Run the real-service check with the frozen static package:

```sh
python3 scripts/check-pr55-recovery.py --source-tar /home/alphalab/.local/state/pi-stack-backups/20261103T125658.584050Z/pi-web.tar --logs /tmp/pr55-phase2-writer/final-live-three
```

The final run passed coordinator historical recovery, worker historical recovery and missing worker-load acknowledgement. Each first completed a real SYNC, native compaction and RESUME. It then stalled a distinct later SYNC. The fixture retained `openai-codex/gpt-6.1-sol` with `xhigh`, used simulated provider responses, and denied external network connections. All three cases completed supported cleanup. Evidence is `/tmp/pr55-phase2-writer/final-live-three/run-1098150765534b3285bb855caa18e6e2/results.json`.

The same service probe against an isolated `ace53a4f` engine failed with `P1 later idle SYNC did not recover from its retained validated dump`. Its supported cleanup passed. Evidence is `/tmp/pr55-phase2-writer-live-red/run-8af4f62f504346508c2ff5c109480aec/results.json`. CLI red and green logs are under `/tmp/pr55-phase2-writer/logs`.

The initial focused DCR and capacity check passed 34 tests. Final affected validation passed 24 tests with this command:

```sh
PYTHONPATH=pi-streams:pi-streams/tests python3 -m unittest -v test_phase2_review test_phase2_acceptance test_failure_recovery test_mass_resume
```

The existing Phase-1 focused acceptance and new regressions ran with a disposable native package in a 28-test command. Twenty-seven tests passed. `test_recovery_lane_isolation.RecoveryLaneIsolationTests.test_unresolved_job_in_ratified_worker_does_not_block_other_authorized_lanes` failed because tick health returned success rather than the expected failure. The same test fails unchanged at `ace53a4f`. It is not fixed in this bounded pass. Logs are `final-focused.log` and `baseline-lane-check.log` in `/tmp/pr55-phase2-writer/logs`. No full suite was repeated.

An additional `worker-load-error` diagnostic demonstrated the native parked-failure fence and blocked load evidence. Supported stream close and archive then correctly refused that parked successor. The strengthened verification runner returned failure rather than accepting process and path cleanup alone. That diagnostic is opt-in, not part of the three passing acceptance scenarios. Evidence is `/tmp/pr55-phase2-writer/final-live/run-e50ddf1e4ec142bd95bb5bd0aa86cc32/results.json`. Safe automatic retirement of an active or parked native failure without its required ownership proof is not claimed.

All writer-owned fixture processes stopped. Disposable package copies, baseline source copy and session scratch paths were removed. Evidence logs remain outside the worktree. Native Prime support, full-suite completion and general recovery through indefinitely active or unknown owners remain outside this proof. The parent owns final review, independent reruns and publication. The child did not push, update the PR, merge, change credentials, edit a live install or contact a provider.


### Final pending-load ownership correction

The parent identified another consequence of releasing stream-wide worker-load ownership. A second replacement could move the first pending load into history, where its later exact acknowledgement would never be observed. `55a9a178` and fixture completion `b055f1a1` reproduce the demotion. `817abd07` refuses a new replacement until the current checkpoint load reaches a terminal disposition. Ordinary coordinator observation still proceeds. A later exact acknowledgement completes the retained current load. Terminal blocked, stopped or superseded successor fences remain retained in history.

The alternative was history-aware advancement and saving for concurrent pending loads. The refusal guard is smaller and avoids expanding mutable publication ownership. It serializes replacement starts, not healthy lane observation.

The targeted command ran `test_phase2_review.MissingLoadAckTests.test_second_replacement_cannot_demote_pending_worker_load_before_ack` and `test_phase2_review.MissingLoadAckTests.test_pending_worker_load_does_not_starve_healthy_coordinator`. Both passed. Evidence is `/tmp/pr55-phase2-writer/logs/pending-history-green.log`. The definitive red assertion records a changed current replacement intent in `pending-history-red.log`. Initial incomplete admission setup and an unregistered target in the fixture were corrected before accepting that result. Runtime source is frozen at `817abd07`.

### Final parent verification

The parent reviewed the complete engine diff and reran affected regressions with existing Phase-1 controls after the pending-load correction. All 89 Python tests passed without skips, including the three native late-writer scenarios in one wrapper. The log is `/tmp/pr55-phase2-parent/final-unit.log`.

The parent also reran `scripts/check-pr55-recovery.py` against the final source and the frozen static package. Coordinator recovery, worker recovery, and worker missing-ack isolation all passed. Each case completed supported stream close and session archival, stopped its service, and removed its scratch paths. The package copy was removed. Evidence is `/tmp/pr55-phase2-parent/final-live/run-f51e57400b20496ab614318473e6a944/results.json`.

Independent parent reproductions retain the failing original P1 service result under `/tmp/pr55-phase2-parent/live-red-f5664f9213344e6186b8835f8c5d4507` and the failing original P2 CLI result in `/tmp/pr55-phase2-parent/red-cli.log`. The P2 probe then passed in `/tmp/pr55-phase2-parent/p2-green-cli.log`. The parent independently reproduced the unrelated baseline lane-health assertion failure in `/tmp/pr55-phase2-parent/inherited-lane-failure.log`. No full-suite green or native Prime readiness is claimed. PR #55 remains open for adversarial re-review.

## Re-review ownership repairs

The independent [BLOCK at ac979607](https://github.com/alienczf/pi-stack/pull/55#issuecomment-6695085146) identified three remaining gaps. All reproduced through actual CLI commands and disposable HTTP/native-transcript fixtures. The ready-without-ack gap also reproduced through a running Pi service after a real earlier SYNC, compaction, and RESUME. The primary red run reports `Ran 3 tests` and `FAILED (failures=3)` in `/tmp/pr55-rereview-repairs/red-primary.log`. Tests were committed before runtime changes in `3cb6c08f` and `95e7f778`. Runtime repairs and the extended service check are `20024fa9`.

The repairs retain separate source, replacement, and delivery ownership.

- `IncompleteSyncAcknowledgement` distinguishes a complete well-formed assistant turn without its exact acknowledgement from malformed messages or watcher metadata. Eligible `sync-admitted` and persisted `blocked` attempts can select an older validated dump. Attempts with checkpoints, admitted compaction, RESUME, capacity, or failure-recovery ownership cannot use this path. The incomplete current snapshot never becomes a validated dump.
- An initial loader exception no longer marks the already published replacement's source DCR blocked. Completed replacements can also reconcile an older corrupted blocked source. The current operation must match the entire frozen operation except its phase and detail, and its full capacity outcome must match. Exact active-target validation still applies. A new regression rejected an initial reconciliation draft that trusted only capacity-outcome equality.
- Sending and uncertain load journals now call the existing receiver observer. Exact receiver intent, current receiving control, native load transcript, and final acknowledgement remain mandatory. Observation never resends the load or rearms admission.

### Re-review verification

The final focused command passed 88 tests without skips.

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=pi-streams:pi-streams/tests python3 -m unittest -v test_phase2_rereview test_phase2_review test_phase2_acceptance test_dcr test_phase1_parity test_failure_dcr test_failure_recovery test_mass_resume
```

The 21 new tests cover missing final acknowledgement with and without a prior dump, persisted blocked attempts, exact-ack normal compaction, maintenance ownership, receiving stops, malformed watchers, newer input, callback ownership, corrupt dumps, exact late receipts, changed owners, stale targets, initial refused loads, and lost replies. They assert persisted outcomes and no replay through the CLI. The log is `/tmp/pr55-rereview-repairs/final-focused.log`.

The native-service command now includes coordinator and worker `ready` without final acknowledgement, alongside the three previous cases.

```sh
PYTHONDONTWRITEBYTECODE=1 python3 scripts/check-pr55-recovery.py --source-tar /home/alphalab/.local/state/pi-stack-backups/20261103T125658.584050Z/pi-web.tar --logs /tmp/pr55-rereview-repairs/verified-live
```

All five cases passed with supported stream close, session archival, process stop, and scratch removal. Evidence is `/tmp/pr55-rereview-repairs/verified-live/run-de505950873d4f7da0d250a7bfc4a4db/results.json`. The runner verifies a real successful `dcr ready`, absent final acknowledgement, unchanged prior dump, retained current STATE, role, and exact load disposition. Simulated provider responses made no provider requests.

The ready coordinator case captured only a source prefix before the turn finished appending. The archive retains that prefix and matches the full source hash frozen by replacement before retirement. `archiveCapturedBeforeRetirement` is false for that case, not an independent full-file capture claim. The initial runner incorrectly equated an early capture with final bytes and failed. Its correction changes only verification, not runtime retirement fences.

A wider command ran 193 tests with 169 passes and 24 errors in `test_resume_admission`. Every error was the same coordinator-status `NoneType` fixture failure. All 24 reproduce at unchanged `ac979607`. Logs are `/tmp/pr55-rereview-repairs/final-unit.log` and `baseline-resume.log`. Those failures and the previously recorded lane-health failure remain outside this bounded repair. No full-suite green, native Prime readiness, or recovery through active or unknown owners is claimed. The same Sol xhigh model was retained throughout. No live installation, production stream, credential, deployment, or merge changed.

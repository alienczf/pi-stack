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

This does not establish unconditional recovery whenever dumps exist. The fallback requires its matching maintenance attempt and readable native checkpoint. A later SYNC that never becomes ready has no new timeout or historical-dump selection here. Previously validated dumps remain retained, but automatic selection of one after that failure is not implemented. Full native Prime parity and that stronger recovery guarantee remain open.

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

Newly authored changes are the acceptance runner, task tests, this explanation, the append-only [decision trail](prime-phase1-parity-decisions.tsv), TODO progress, HTTP-stub identity decoding, and stale DCR test corrections. Engine and native implementation changes are inherited exactly from merged main. Validation changed no live state, credentials, installed model, or production streams. No deployment occurred. The parent reviewed the final authored diff on the same model. Cross-model review was not performed under the supplied no-model-switch constraint.


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

# Phase-1 Prime stream parity

This branch brings the merged shared stream implementation to the Prime baseline. It does not add a native Prime backend.

## Integration and authorization

The starting point is `origin/prime-stack` at `f685e3ad1485192a45bc7b6eed6b260961a965e4`. Merge `eca2e96c` integrates merged main at `cba29cd00fab9e0cc1661648c89f1c1840e2b04e` without changing its engine or native files. This preserves the archive, retained-source, recovery, and replacement prerequisites rather than selecting incomplete leaf fixes. PRs 44-47 are not integrated.

The supplied Phase-1 user order says "ZF via Grok Bot is authorized." That order is the provenance for this local work. This document does not claim a transport signature, notice ID, independent authentication, or additional sender metadata. Push and PR creation remain with the parent session. The PR destination is `alienczf/pi-stack`, targeting `prime-stack`.

## Implemented shared behavior

- `ef9401c3` removes spawn ratification. Canonical artifact validation still applies. See [`threads.py`](../pi-streams/engine/threads.py), `spawn_thread` and `adopt_thread`.
- `46a60e5c` heals exactly owned legacy silent drive-off on tick and continues owned parked recovery. Newer receiving generations, uncertain effects, policy restrictions, and deliberate stops remain fences. `StopIntent.OPERATOR_OFF` records deliberate local stops. See [`drive.py`](../pi-streams/engine/drive.py), `reconcile_locked` and `pause_local`, and [`tick.py`](../pi-streams/engine/tick.py).
- `cba29cd0` retains a validated dump before compaction and supports role-preserving replacement for coordinators and workers. Successor load completion requires persisted user and assistant evidence, not HTTP acceptance alone. See [`dcr.py`](../pi-streams/engine/dcr.py), `retain_dump` and `rotate_capacity_locked`, and [`replacement.py`](../pi-streams/engine/replacement.py), `_load_checkpoint`.

The Pi native controller uses a 180000 ms boot-monotonic compaction lease. Expiry fences the native writer before fallback. A late summary cannot append to the original session. Foreign legacy writers without the exclusion protocol remain blocked until their death is proven. See [`sessionMaintenanceController.js`](../native/pi-web/postimages/dist/server/sessions/sessionMaintenanceController.js), `retireOwned`.

Recovery retains the synced STATE bytes, their digest, the exact terminal SYNC checkpoint, current STATE, input dispositions, worker references, and the original native archive. Retained data before the last validated dump is not discarded. Unsynced continuation after that boundary cannot be assumed complete or replayed. Changed native input, corrupt dumps, unknown effects, or missing evidence block retirement. External worktree references must remain available.

## Rerunnable acceptance

The acceptance command is:

```sh
python3 scripts/check-prime-phase1-parity.py --compare f685e3ad
```

The runner creates a disposable Git snapshot and isolated test homes. It requires all three baseline behavior failures with their explicit assertion markers. Setup errors do not qualify as baseline evidence. It then runs the task regressions and existing drive, DCR, spawn, failure-DCR, and observation-admission tests.

`PI_STACK_NATIVE_TEST_ROOT` can name a patched disposable package prepared as described in [`native/README.md`](../native/README.md). Without that variable, the native wrapper reports a skip. The native tests hold an extension summary or simulated provider response, expire the persisted lease, and verify late-write exclusion. They make no provider requests. `--regressions-only` runs the smaller task-specific set.

Before integration, seven task regressions ran with six behavior failures and no setup errors. After integration and test-only corrections, the focused acceptance ran 63 tests successfully. The final hardened runner ran 14 task-specific tests successfully, including three native Node scenarios inside one Python wrapper. The comparison still produced exactly three expected baseline failures.

The complete unittest suite was attempted but interrupted at the writer deadline. Its log ends during `test_final_status_fifo_marker_is_preserved_without_blocking` with no unittest summary. Earlier failures include chaos integration, coordinator identity, and historical failure-marker heuristics. Full-suite acceptance is unresolved. The parent also observed preexisting native-module failures on main, including missing extensions in its package fixture. Neither run is reported as green.

## Evidence boundary

[`native/README.md`](../native/README.md) targets `@jmfederico/pi-web@1.202607.3` and bundled Pi packages at `0.82.1`. No supported native Prime adapter is implemented here. These checks establish shared engine and Pi adapter parity only. Native Prime capability mapping and end-to-end proof remain blocked. Capability admission is unchanged.

Newly authored changes are the acceptance runner, task tests, this explanation, the append-only [decision trail](prime-phase1-parity-decisions.tsv), TODO progress, HTTP-stub identity decoding, and stale DCR test corrections. Engine and native implementation changes are inherited exactly from merged main. No live state, credentials, installed model, production streams, push, or deployment changed.

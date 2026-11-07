# Retired native residue after coordinator adoption

## Failure and fix

An archived coordinator row records the engine's disposition. It does not prove native retirement. Explicit adoption could register a successor while the predecessor remained native-live. The resolver then blocked every dispatch with `retired-native-residue`.

Tick now reconciles that exact retired predecessor before it resolves the successor again. It requires the registered cwd, unique native identities, an idle checkpoint, known callbacks and the current receiving generation. Native conditional archive retains responsibility for input, callback, effect and failure-lifecycle guards. Status remains read-only. It keeps the blocker until native retirement is confirmed.

The operation reuses terminal dispositions. Sending, uncertain, refused or inconsistent completed outcomes do not authorize another archive request. Positive native archive evidence allows resolution without reopening the predecessor. Unknown candidates and explicit drive-off remain fenced.

Native archive also rejects an existing destination whose bytes differ from the current source before it removes that source. Identical interrupted copies still reconcile. The guarded overlay accepts the complete previous package tree without permitting arbitrary mixed bytes.

## Verification

The red-first regression commit is `48696b78`. Before the fix, its output ended with `FAILED (failures=5)`. The parent final focused run passed 69 tests, including the CLI lifecycle, lost-reply reconciliation, native byte-retention guard, callback ownership and overlay checks.

Run the real native-service check after preparing the disposable fixture described in [Native healing overlay](../native/README.md):

```sh
python3 scripts/check-retired-native-residue.py \
    --native-root "$PWD/.harness-heal/retired-native-residue/native" \
    --logs /tmp/pi-retired-residue/verification
```

The check synthesizes the legacy registry-only retirement state, explicitly adopts a persisted successor and runs tick through the real native HTTP routes. It uses controlled provider responses without credentials or external traffic. Its verified run archived the predecessor, retained the complete captured bytes, removed the live source and dispatched once to the exact successor. Supported teardown closed the stream, archived remaining owned sessions, stopped the service and removed scratch. Each run retains its result and command receipts outside scratch.

Focused checks can run independently:

```sh
PYTHONPATH=pi-streams/tests python3 -m unittest test_retired_native_residue
PI_STACK_NATIVE_TEST_ROOT="$PWD/.harness-heal/retired-native-residue/native" \
    PYTHONPATH=pi-streams/tests python3 -m unittest \
    test_native_modules.NativeModuleTests.test_actual_archive_retention
```

## Limits

The base is `prime-stack` at `b250dc6f`, which includes recovery changes absent from `main`. Existing coordinator-identity, status and native-rotation fixture failures reproduce on that base. This work does not claim a full-suite pass.

The reported tenv status confirmed the retired-native blocker. It did not establish that the predecessor's parked failure was safely retireable. Genuine parked failures and unresolved native ownership still refuse archival. Explicitly stopped qslite was not resumed. No production stream repair, native installation, daemon restart or merge occurred.

## Principles and choices

| Principle | Choice |
| --- | --- |
| Fix Root Causes | Retire safe residue instead of suppressing the resolver's diagnostic. |
| Model the Domain | Reuse the existing thread and terminal-disposition records. |
| Make Operations Idempotent | Preserve uncertain outcomes without replay. |
| Laziness Protocol | Keep reconciliation in tick without another lifecycle registry. |
| Build the Lever | Keep the native-service reproduction as a rerunnable script. |
| Test Behavior, Not Implementation | Require an actual successor dispatch and retained bytes. |
| Prove It Works | Check real native routes, archive contents and supported teardown. |
| Sequence Work into Verifiable Units | Commit failing regressions before each runtime repair. |

# Run isolated stream chaos verification

Run this from a checked pi-stack worktree. Supply frozen owned package inputs so rolling installations cannot race the copy. The runner refuses implicit inputs and known live installation roots. It copies a frozen static native package into a fresh owned `.harness-heal` directory and applies the current worktree's overlay.

This pre-rollout backup is a read-only frozen input. Archive extraction copies only static package material and excludes credential and session files.

```sh
FROZEN_NATIVE_TAR=/home/alphalab/.local/state/pi-stack-backups/20261103T125658.584050Z/pi-web.tar
python3 scripts/check-streams-chaos.py --source-tar "$FROZEN_NATIVE_TAR" --cases baseline
python3 scripts/check-streams-chaos.py --source-tar "$FROZEN_NATIVE_TAR" --cases all
```

The baseline selects overload, terminated, usage reset, and compaction. `all` selects 16 scenarios. The checked combined tree expects 15 `PASS` results and one `NOTIMPLEMENTED` result, so its honest exit code is 1. Any `FAIL` or `NOTIMPLEMENTED` result exits nonzero. Nothing silently skips unfinished product behavior.

`policy-safe-analysis` proves one isolated generic metadata inference with a complete context capture. It does not receive or complete the permitted `SAFE_DOC_UNIT_6a` assignment. `policy-narrowing` exercises that same analysis boundary but reports the remaining useful-continuation requirement as structured `NOTIMPLEMENTED` evidence. The original rejected task stays blocked. The full-suite integration test passes only when all 16 expected dispositions and the nonzero chaos exit agree.

Select individual cases or inspect the registry.

```sh
python3 scripts/check-streams-chaos.py --list
python3 scripts/check-streams-chaos.py --source-tar "$FROZEN_NATIVE_TAR" --cases login-refresh,model-error,parked-worker,rotation
python3 scripts/check-streams-chaos.py --source-tar "$FROZEN_NATIVE_TAR" --cases policy-safe-analysis,policy-narrowing,blocked-loop,tick-noise,unratified-close,archived-worker,dead-worker
python3 scripts/check-streams-chaos.py --source-tar "$FROZEN_NATIVE_TAR" --cases small-recovery
```

The last command is the minimal executable reproducer for small-session recovery failure. It creates a stream through `pi-streams new`, completes one good assistant turn, injects a terminal error, and drives actual recovery ticks. It does not seed large history.

## Supply a prepared package

A caller-owned disposable package must be under `.harness-heal`. The runner checks its overlay but neither modifies nor removes it.

```sh
python3 scripts/check-streams-chaos.py --native-root "$PI_STACK_NATIVE_TEST_ROOT" --cases baseline
PI_STACK_CHAOS_SOURCE_TAR="$FROZEN_NATIVE_TAR" PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests -p test_chaos_lever.py -v
```

`--source-tar` accepts a frozen `pi-web.tar` backup. `--source` accepts a complete frozen native package directory. `--node` selects the Node executable. The earlier `fix-local-landing/sandbox-native` snapshot lacks Fastify and is not a complete service fixture. They do not change the tested provider or model. No package installation occurs. The integration unittest accepts `PI_STACK_NATIVE_TEST_ROOT` or `PI_STACK_CHAOS_SOURCE_TAR`. Without either explicit input only that unittest skips, not any standalone chaos scenario.

## Inspect the evidence

Logs stay under `/tmp/pi-stack-spawn-only-ratify-20261103/chaos-lever/run-*`. `--logs` selects another external directory.

Each run records these files.

- `run.json` records the source revision, verification source hashes, selected cases, and simulation labels.
- `prepare.log` and `overlay-check.log` record the static package checks.
- `results.json` records each case's actual result and cleanup outcome.
- Each case's `ownership.jsonl` journals stream, session, process, and path ownership before effects.
- `commands.json` records actual CLI arguments, replies, exit codes, and elapsed time.
- `native-evidence.json` records provider requests, registered HTTP route requests, persisted entries, native maintenance stores, and rebuilt context estimates.
- `state-evidence.json` records owned STATE, registry, handovers, and engine journals before teardown.
- `cleanup-before.json`, `cleanup-after.json`, and `cleanup.json` record supported close/archive attempts and fixture teardown.
- `fixture-cleanup.json` records removal of the runner-owned static package copy.

## Understand the test boundary

This is an isolated running native service smoke, not production daemon evidence and not a fake HTTP contract server. `chaos-service.mjs` constructs real `PiSessionService`, `AgentSessionRuntime`, `AgentSession`, session-manager gateway, admission stores, archive store, maintenance controllers, and event hub. It registers the package's actual session routes with Fastify. `sessiond.js` is never imported.

The injected model runtime and `Agent.streamFn` simulate provider transport and login readiness. They do not inspect credentials or call a provider. The exact identity stays `openai-codex/gpt-6.1-sol` with `xhigh` session reasoning. Title generation uses the native title request's `minimal` reasoning. The fixture loads no extensions, so it does not copy or attest extension-adapter behavior. Provider responses and usage counters are simulated. Transient retry timers use actual five-second waits, with a real engine tick during the pending retry. No clock or sleep replacement exists.

The history fixture appends simulated historical messages through the real persistent `SessionManager`. Native `estimateTokens` measures the rebuilt context. The compaction case requires an actual context above 150000, a real native summarization call and persisted compaction entry, a rebuilt context below 150000, and an exact current-goal RESUME with a completed assistant-stop observation. These estimates are not billed provider token counts.

The simulated agent executes only the exact owned `pi-streams dcr ready` command when it receives SYNC. It never executes a command supplied by provider output. Native DCR events use the package's real `runStreamsDcrAdvance` callback. No model tools or external effects are enabled.

Every case has a fresh project, index, HOME, XDG directories, session store, process, and ephemeral loopback port. Port 8504 is forbidden. Worker repositories and worktrees belong only to that case. No existing stream or session is contacted. The dead-worker case archives and deletes only its owned fixture session through registered supported API routes before testing missing-session reconciliation.

Cleanup first uses `pi-streams close` and `pi-web-cli archive`. A case cannot pass if those operations fail. Product lifecycle guards can refuse archive for failed or held sessions. The report preserves those refusals instead of claiming successful archival. The runner then stops its fixture process and removes only marker-owned scratch paths. A red run can therefore have complete process/path cleanup but incomplete supported session archival.

## Known failures at acfd37a

These are observed product findings, not expected-pass substitutions. Rerun against the combined source before rollout.

- High. `pi-streams/engine/failure_recovery.py:329` prevents coordinator retirement because an unsent prepared drive delivery remains attached to the original. Large-context login, model-error, and rotation cases reach completed native RESUME but do not release the successor.
- High. `native/pi-web/postimages/node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js:1404` rejects small-session compaction. `sessionMaintenanceController.js:297` makes that compaction mandatory during recovery. The small recovery becomes failed maintenance and later reports a superseded generation.
- High. `pi-streams/engine/failure.py:17` explicitly leaves policy narrowing unimplemented. The policy case supplies an authorized documentation-only alternative and requires non-replay.
- High. `pi-streams/engine/drive.py:156` permits a fourth identical blocked-unit dispatch. The case observes seven identical sent prompts and seven controlled blocked replies.
- Medium. `pi-streams/engine/tick.py:549` repeats the charter error after closing a never-ratified coordinator.
- Medium. `pi-streams/engine/tick.py:423` repeatedly queries an archived worker still registered active and reports the missing original JSONL path on each tick. The dead-worker variant observes repeated 404 status requests after supported deletion of that exact owned fixture.

Ratified done-coordinator cleanup passes one-shot reconciliation at this base. Parked-worker recovery with large simulated history also passes, including completed RESUME and scoped original retirement. The coordinator-specific failures remain red.

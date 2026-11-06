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

## Documentation fixture contract

`policy-narrowing` now prepares the independent `SAFE_DOC_UNIT_6a` definition under its existing documentation-only fixture grant. The unit produces a Markdown protocol note for maintainers of automatic-admission bootstrap. It documents protocol 49, not the rejected task or generic policy metadata.

The separate benign input is `scratch/document-input/bootstrap-facts.json`, exposed by the handle `bootstrap-facts-v1`. Its literal facts describe these tested rules.

- Initialization creates a durable epoch only when no durable epoch exists. Retrying bootstrap must not replace an epoch that a later receiving stop can invalidate.
- Initialization preserves an existing disabled epoch and its generation. Bootstrap must not reenable stale automatic work after a receiving stop.
- Initialization dispatches neither inference nor queued goals. Bootstrap retries must not duplicate work or bypass a later stop.

`pi-streams/tests/native/initial-control.test.mjs` exercises these rules through the actual admission store and registered initialization route. Its cases cover absent initialization, cold retries, existing stops, queued goals, and concurrent stops. The facts artifact contains no rejected assignment, source prefix, project resources, or source paths.

The concrete absent-epoch example starts at `generation=unarmed`, `allowed=false`, and `durable=false`. Initialization returns the illustrative durable epoch `init-1` with `allowed=true`. The existing-stop example starts and ends at `generation=stop-2`, `allowed=false`, and `durable=true`. Both examples retain a queued goal and zero inference calls. The epoch names are fixture data, not production identifiers or authorization patterns.

The only output is `scratch/private-docs/automatic-admission-bootstrap.md`, identified by `owned-bootstrap-note`, with a 16384-byte limit. `document-contract.json` records the self-contained formatting assignment, exact input hash, output identity, private grant root, and explicit exclusions. The original task stays blocked. Arbitrary tools, arbitrary paths, source-prefix reads, project-resource reads, and business writes remain excluded. This descriptor is test data. It does not authorize a native request.

### Artifact acceptance

`policy_document_oracle` reads only the fixed owned input and output after checking ownership and symlinks. It requires the original input bytes. A candidate document has the title `# Automatic-admission bootstrap` and exactly these sections.

- `## Provenance and facts` contains one `json` fence. Its object has `schema=bootstrap-note-v1`, the input protocol, `inputHandle`, the exact `inputSha256`, `outputHandle`, and the input's literal `facts` and `examples` objects. Unknown fields, duplicate keys, and numeric substitutes for booleans refuse.
- `## Rules` contains a Markdown table with the columns `Rule` and `Protection`. It includes every supplied human-readable rule and its explanation of stop protection or duplicate-work prevention.
- `## Examples` contains a Markdown table with the columns `Scenario`, `Before initialization`, and `After initialization`. Each state lists the input fields in order as `key=value`, separated by `; `. String values have no quotes. Booleans use `true` and `false`.

Acceptance compares structured facts and complete table contents, not an exact generated document. JSON key order, section order, table row order, alignment, whitespace within cells, and whole-cell code formatting can vary. The human-readable tables form a closed projection of the benign input. Free-form paraphrases and extra prose are outside this fixture format. That restriction prevents an otherwise valid fact block from concealing contradictory stop or dispatch claims in unchecked prose.

The oracle rejects markers alone, generic policy reports, completion claims, missing explanations or examples, contradicted structured facts or outcomes, wrong input or output bindings, changed input bytes, symlinks, oversize documents, and injected rejected canaries. Its `fixtureArtifactValid` receipt proves only that candidate content satisfies the fixture contract. It is not evidence of native execution.

The chaos runner creates no candidate or placeholder document and never submits the task or input to inference. `policy-narrowing` remains `NOTIMPLEMENTED` until a later bounded native execution produces and passes this artifact while preserving the original boundary and source bytes. The unchanged native context guard tests still exercise the real SDK factory, empty tool registry, complete context capture, and source preservation.

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
- `policy-narrowing/document-contract.json` records the independent documentation fixture definition. The retained scratch input supplies its benign facts. No document output is claimed.
- `cleanup-before.json`, `cleanup-after.json`, and `cleanup.json` record supported close/archive attempts and fixture teardown.
- `fixture-cleanup.json` records removal of the runner-owned static package copy.

## Understand the test boundary

This is an isolated running native service smoke, not production daemon evidence and not a fake HTTP contract server. `chaos-service.mjs` constructs real `PiSessionService`, `AgentSessionRuntime`, `AgentSession`, session-manager gateway, admission stores, archive store, maintenance controllers, and event hub. It registers the package's actual session routes with Fastify. `sessiond.js` is never imported.

The injected model runtime and `Agent.streamFn` simulate provider transport and login readiness. They do not inspect credentials or call a provider. The exact identity stays `openai-codex/gpt-6.1-sol` with `xhigh` session reasoning. Title generation uses the native title request's `minimal` reasoning. The fixture loads no extensions, so it does not copy or attest extension-adapter behavior. Provider responses and usage counters are simulated. Transient retry timers use actual five-second waits, with a real engine tick during the pending retry. No clock or sleep replacement exists.

The history fixture appends simulated historical messages through the real persistent `SessionManager`. Native `estimateTokens` measures the rebuilt context. The compaction case requires an actual context above 150000, a real native summarization call and persisted compaction entry, a rebuilt context below 150000, and an exact current-goal RESUME with a completed assistant-stop observation. These estimates are not billed provider token counts.

The simulated agent executes only the exact owned `pi-streams dcr ready` command when it receives SYNC. It never executes a command supplied by provider output. Native DCR events use the package's real `runStreamsDcrAdvance` callback. No model tools or external effects are enabled.

Every case has a fresh project, index, HOME, XDG directories, session store, process, and ephemeral loopback port. Port 8504 is forbidden. Worker repositories and worktrees belong only to that case. No existing stream or session is contacted. The dead-worker case archives and deletes only its owned fixture session through registered supported API routes before testing missing-session reconciliation.

Cleanup first uses `pi-streams close` and `pi-web-cli archive`. A case cannot pass if those operations fail. Product lifecycle guards can refuse archive for failed or held sessions. The report preserves those refusals instead of claiming successful archival. The runner then stops its fixture process and removes only marker-owned scratch paths. A red run can therefore have complete process/path cleanup but incomplete supported session archival.

## Historical failures at acfd37a

These are historical observed findings, not current policy or expected-pass substitutions. The former ratification gate no longer applies. The retained `unratified-close` case now checks compatibility with documentary `ratified: no` bytes. Rerun against the combined source before rollout.

- High. `pi-streams/engine/failure_recovery.py:329` prevents coordinator retirement because an unsent prepared drive delivery remains attached to the original. Large-context login, model-error, and rotation cases reach completed native RESUME but do not release the successor.
- High. `native/pi-web/postimages/node_modules/@earendil-works/pi-coding-agent/dist/core/agent-session.js:1404` rejects small-session compaction. `sessionMaintenanceController.js:297` makes that compaction mandatory during recovery. The small recovery becomes failed maintenance and later reports a superseded generation.
- High. `pi-streams/engine/failure.py:17` explicitly leaves policy narrowing unimplemented. The policy case supplies an authorized documentation-only alternative and requires non-replay.
- High. `pi-streams/engine/drive.py:156` permits a fourth identical blocked-unit dispatch. The case observes seven identical sent prompts and seven controlled blocked replies.
- Medium. `pi-streams/engine/tick.py:549` repeats the charter error after closing a never-ratified coordinator.
- Medium. `pi-streams/engine/tick.py:423` repeatedly queries an archived worker still registered active and reports the missing original JSONL path on each tick. The dead-worker variant observes repeated 404 status requests after supported deletion of that exact owned fixture.

Done-coordinator cleanup with the former affirmative marker passed one-shot reconciliation at this base. Parked-worker recovery with large simulated history also passes, including completed RESUME and scoped original retirement. The coordinator-specific failures remain red.

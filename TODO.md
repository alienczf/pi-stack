# Track 6 progress

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [ ] Phase C: Run the loop.
- [x] Unit 1. Implement the Z15 stream writer and focused behavior tests.
- [x] Unit 2. Expose public stock transport and owned sessions.
- [x] Unit 3. Save and refresh messages, wake eligible work, and stop best effort.
- [x] Unit 4. Dispatch clean poteto workers with handover and kickoff only.
- [x] Unit 5. Own percentage-triggered save, compact, readback, and resume.
- [ ] Unit 6. Close only computed results and stage owned paths.
- [ ] Unit 7. Install stock Prime and pi-stack under an isolated external prefix.
- [ ] Unit 8. Prove intake through compaction to checked close with the shared verifier.
- [ ] Phase D: Keep the audit trail.
- [ ] Phase E: Verify and hand back.
- [ ] Opening a PR. skip: The user permits local commits only and forbids pushes and PRs.

The implementation and verification contract is in `PLAN.md`. The canonical decisions, commit SHAs, checks and evidence paths are in `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/13-track-6-progress.md`. Historical track-2 work remains in the merged CLI branch history and artifact 20.

## Serial implementation owner

The retained owner continues Units 2 through 8 without children or unit-only returns. The parent owns independent review. Each ordered commit still requires focused tests and both full suites. This supersedes the original fresh-per-unit workflow after runner `660682b8-9446-46d1-b39b-70d2122effb2` returned only a launch receipt.

## Unit 1 verification

Commit `ea6ef52187a6b23a6ee68df7ae3b893881ff9f6c` has subject `state: implement the Z15 stream writer`. This full-SHA note is an unstaged post-commit report update.

New functionality adds typed Goals, Rules and immutable entries, exact parsing, checked updates, original saves, history-first Log retention, Prime templates and linked-worktree locks. Existing Pi templates remain unchanged. Reused project Git/config/registry helpers and kernel flock; no new index or task store.

Evidence is under `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/evidence/`.

- `unit-1-before.log` records old creation failing the missing-current-work assertion and the linked-worktree lock error before correction.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests -p test_prime_state.py` passed 31 tests in `unit-1-focused.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests` passed 136 tests in `unit-1-streams.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` passed 71 tests in `unit-1-root.log`.
- Exact section-4 AGENTS bytes, Python syntax and `git diff --check` passed in `unit-1-static.log`.

Unit 2 passed 39 focused tests, 144 stream tests and 72 root tests. Logs are `evidence/unit-2-{focused,streams,root}.log`. The shared transport owns protocol 7/schema 30, pending commands and interleaved events. The thin CLI preserves compatibility projections and error outcomes. Prime session creation refuses thinking clamps. The parent-reported path escape has a failing regression and now rejects destination/ancestor symlinks and registered Prime paths outside the project stream directory.

Unit 2 commit is `ffbacff02fb2d2dc689ad216b6f3cfc5da3a779b`. Unit 3 passed 48 focused, 153 stream and 72 root tests in `evidence/unit-3-{focused,streams,root}.log`.

Unit 3 commit is `c3555ce4b8188e9d6962f1d5609e7ee9c11b3bbe`. Unit 4 passed 49 focused, 154 stream and 72 root tests in `evidence/unit-4-{focused,streams,root}.log`. Worker assignment and existing thread registry are saved before the exact unwrapped handover/kickoff. Native product instructions remain untouched; returned summaries are saved only in stream Log.

Unit 4 commit is `e82609ec59be46d36fe9eccdd4c704827ac71d52`. Unit 5 passed 62 focused, 167 stream and 72 root tests in `evidence/unit-5-{focused,streams,root}.log`. Percentage and explicit requests share one controller. Checked save precedes pause, idle/queue recheck and direct compact. Readback verifies the current branch and exact owned disk entry. A parked-input fixture proves release-before-await. Native runtime proof remains pending.

Next is Unit 6. Prime creation currently takes an explicit `backend="prime"` and persists it in `stream.toml`. Project-level backend settings remain Unit 2. Writers accept `locked=True` for callers already holding the stream lock. Successful computed completion remains blocked until Unit 6 supplies its actual closing checks. Explicit cancellation or informational explanation uses a complete linked answer and later trusted human source. Broad legacy staging remains unchanged until Unit 6. No native inference or authentication check was attempted.

## Track 2 integration history

## G41 authenticated in-place verification

1. [x] Ground. Inspected verifier and native directory ownership without opening credential storage. The installed wrapper hardcodes track 6's session/socket paths; use its unchanged stock binary directly.
2. [x] Sketch. Selected existing agent metadata/auth through environment with a separately owned socket, cwd, and session directory. No credential copies/links or shared-settings rollback.
3. [x] Agree. G41 authorizes this runtime and real Sol 6.1 xhigh inference. No further login or provider/model change.
4. [x] Implement. Red/green pairs cover agent environment selection, unchanged existing directory permissions, and awaited compaction outcomes. Code revision is 4fd0c90.
5. [x] Scrap. Skip. Native environment selectors isolate the owned sessions and socket; no alternative topology is needed.
6. [x] Verify. Actual Sol 6.1 xhigh marker completion passed. Native compaction returned an explicit short-history skip, not success. Real helper is unavailable on this host; local-executor wrapper/control check passed. No actual usage error occurred.
7. [x] Handoff. Artifact 20 records commands, outcomes and the exact genuine box command. Five owned sessions are archived, daemons stopped and socket/lock absent. Design edits stay uncommitted.

Throughput checkpoint:

- Blocking first steps. Verify actual launcher behavior and split authenticated agent storage from this run's owned session/socket root before any native call.
- Independent workstreams. Bounded read-only source investigation can run beside parent verifier review. Parent remains the sole code writer and owns every native call.
- Shared mutable state. Track 6 owns its sessions, streams, daemon and configuration. Do not run its installed wrapper blindly because it hardcodes its session directory and socket. Credentials remain in place and are never opened by tools.
- Smallest safe decomposition. Keep the existing verifier and public protocol. Prefer a small explicit environment-selected shared-agent mode over credential links, copied configuration, or another service.

G41 result. `/tmp/prime-cli-check-7uekbeka/g41-live-corrected.json` exits 0 with inferenceVerified true, effective xhigh, exact marker response, native cost 0.017224 and context usage 8496 of 500000. Native compaction is explicitly skipped because the session is too short; compactionVerified and parityComplete remain false. Model/thinking setter probes are skipped to preserve shared defaults. The two model-backed session transcripts identify the requested provider/model/API and stopReason stop. No tool opened or manipulated credentials.

The genuine wrapper reports remote_unavailable because options-01-ssh is absent here. `g41-local-wrapper-control.json` passes through the actual wrapper and a deliberately local-only executor; it proves no SSH/Twingate/box connectivity. All five sessions in the owned directory end archived. Final verification passes 76 Prime fixtures, 105 stream fixtures, installer, syntax and whitespace checks. Full track status remains BLOCKED on real box-side verification and unsupported/omitted native parity, not on authentication. No push.

## G20 follow-up

- [x] Phase A: Frame. Continue from pushed bccf159. No Prime login, credential access/import/copy, provider switch, or model inference is authorized in this follow-up.
- [x] Phase B: Design the workflow. Read both completed investigations. Public same-session queue resumption is feasible. Correlated answers, resident-root disposal without archive, and rich cross-session replay remain unavailable.
- [x] Phase C: Run the loop. Commit failing regressions before each feasible fix. Parent's final suite passes 71 Prime fixture tests. The implementation worker made no push, auth, inference, real daemon, or SSH call.
- [x] Phase D: Keep the audit trail. Code decisions and adjacent reference are updated. Artifact 20 contains the operator login, post-login runner, exact off-host command, native findings, and remaining gaps. Its edits remain uncommitted for Grok Bot.
- [x] Phase E: Verify and hand back. Parent reviewed the worker diff, reran 71 Prime tests, 105 stream tests, installer and syntax checks, and verified the real non-inference path. Provider-auth and unsupported native parity gates remain blocked.

Throughput checkpoint for G20:

- Blocking first steps. Confirmed bccf159 and the parent's pre-existing TODO edit. Read artifact 20, the decisions, and both actual investigations. Native login is bare TUI /login with provider selection, not a CLI login subcommand. It was not executed.
- Independent workstreams. Read-only control-plane and operator-setup investigations run in parallel. One implementation writer follows them. The parent owns artifact 20 and real non-inference verification.
- Shared mutable state. No upstream, stream, credential, or other-branch writes. Child code writes and parent code writes never overlap. Docs remain parent-owned.
- Smallest safe decomposition. Prefer native public operations over a gateway, a shadow session registry, or mutation of Prime internals. A missing native operation stays explicitly missing, with an executable safety regression and evidence.

Deliver the exact operator login command, a ready-to-run post-login inference check that this session does not execute, and the exact Grok Bot off-host wrapper command in artifact 20. Same-model subagents only.

G20 worker result at code revision `b7c326d`:

- Added durable `SessionIdentity`, typed queue previews and observed capability limits. Existing unflagged grammar remains unchanged. Exact-stop and replay-safe-clear requirements return 501 before connecting.
- Added only `queue-resume`, a one-request native same-session wake. It cannot restore cleared inputs or transfer internal objects. Empty-queue errors propagate without fallback. No real resume was invoked.
- Added an endpoint-free catalog snapshot with the observed reasoning map, context window, maximum output, and flat costs. Strict metadata input and native registration are limited to the existing isolated agent directory. Pricing tiers and unsupported compatibility data remain explicit losses.
- Added `scripts/check-prime-cli-live.py verify --root EXISTING_ROOT --runtime ABSOLUTE_BINARY`. It never prepares a new root or invokes login. It refuses collisions, registers temporary native metadata without reading existing models.json, pins all runtime paths, runs control first, and authorizes runnable checks only with explicit `--inference`.
- Verification checks complete metadata and effective xhigh before input. Native model/usage failures remain typed and stop without provider switches or uncertain retries. Cleanup archives only known created IDs, shuts down only the owned dedicated process/socket, restores its saved nonsecret settings, and removes only its owned metadata file.
- All runtime tests use fake executables and owned socket fixtures. No successful authentication, inference, active-turn steering, compaction, off-host access, exact stop, or rich replay is claimed. The verifier always reports `parityComplete:false`.
- Manual cleanup replaced unavailable control-cli/deslop and forbidden child review. No new line comments, suppressions, workflow service, HTTP gateway, private close markers, or worker-protocol calls were introduced.

## G20 parent acceptance

Code revision `84e551d` adds the two real-boundary follow-ups. Commit `1f84327` reproduces Prime's thin connection-state model summary; `ed3e118` checks full metadata through public get_model_catalog. Commit `9f99f62` requires future inference verification to exercise queue-resume; `84e551d` does so while input delivery is paused. Neither parent nor worker executed inference under G20.

The fresh credential-free root `/tmp/prime-cli-check-vqui570y` leaves the original ZF login root untouched. Native full metadata matches the sourced definition and effective xhigh is retained. Native set_model now returns typed model_provider_unauthenticated before any runnable input. No substitute, login, credential read/import, or retry followed.

The separate empty-session smoke passed queue-resume's exact empty-queue error, both pre-mutation 501 guards, empty clear and abort, xhigh setter, empty messages, the stop shim, and archive. All four G20 sessions are archived. No owned live sessions, daemon, socket, lock, or temporary model registration remain. Native nonsecret setter changes were restored after shutdown.

Evidence remains outside git at `/tmp/prime-cli-check-vqui570y/g20-native-control-catalog-fix.json`, `g20-empty-controls.json`, and `/tmp/g20-parent-*.log`. The model-backed runner and off-host command are ready but deliberately unexecuted. Full track status remains BLOCKED on operator authentication and missing native APIs. Grok Bot owns pushing the local commits.

## Bounded review fixes

1. [x] Reproduce it yourself on the matching surface via the control skill. Reproduced all four through offline CLI/socket fixtures. Control-cli is unavailable; no real daemon was contacted.
2. [x] Binary-search the cause. Failing executable regressions confirmed the four reviewed boundary mechanisms. No broader source survey was needed.
3. [x] Plan the fix. Durable session identity, local readback-error normalization, inference-only runnable checks, and leading backend selection. Inline ownership replaced forbidden subagents.
4. [x] Verify on the same surface. Original regressions pass. Full validation passed with 48 Prime tests, 105 existing stream tests, check-overlay.sh, shell syntax, and diff whitespace checks.
5. [x] Stage the commits so the failing repro lands before the fix in git history. Each failing regression commit precedes its tested fix. Failing-then-passing evidence is in the managed report.
6. [x] Run Opening a PR. Skipped under the explicit no-push/no-PR handoff.

Throughput checkpoint. Establish clean c323b30 first. Reproduce and fix one defect at a time. This worker owns this worktree; the parent owns artifact 20 and live checks. Four independently tested commits avoid overlapping code ownership.

- [x] P1. Default checks admit no runnable input; inference-only queue checks clear inside their pause scope on ordinary failure. The two disconnect-aware CLI regressions failed before the fix, exposing three runnable inputs, then passed. This supersedes the historical control-only safety claim below.
- [x] P2. Spawn readback transport errors preserve the known created session. Timeout and reset regressions reproduced identity loss; timeout, reset, and EOF now preserve the received row without retry/deletion.
- [x] P2. Compatibility IDs use durable sessionId with no shim registry or binding-event dependency. The replacement workflow regression now retains one durable ID across fresh prompt/status/list/archive connections and verifies durable pause acquisition.
- [x] P2. Dispatcher consumes only a leading backend selection and forwards backend options verbatim. Both backend-selection spellings now forward --socket, later backend tokens, Unicode/newlines, and stdin unchanged.

Final review was manual because this assignment prohibits subagents and the installed control-cli/deslop skills are unavailable. Removed the binding-event cache rather than adding a shim registry. No new line comments or suppressions were introduced. The parent must rerun live checks after the durable-ID change. Inference-enabled connection loss can still release queued work; default checks admit none.

## Feature playbook

1. [x] `how` over the affected subsystem.
2. [x] `architect` for parallel design exploration. Direct socket and HTTP gateway compared in artifact 20. Inline implementation under the no-subagent constraint.
3. [x] Write the throughput checkpoint as four todo items.
4. [x] Delegate code-writing to a subagent. This assigned worker owns the diff directly. No children permitted.
5. [x] Verify on the matching surface. Offline subprocess and Unix-socket checks passed. Parent owns real-daemon and off-host checks; those are not claimed here.
6. [x] Rebase into small, ordered commits. Base is the authorized 3acf0f0. Adapter and native-compatibility correction are separate verified commits. No rebase needed.
7. [x] If the design is contested, `interrogate` before shipping. Not contested. Same-model constraint remains.
8. [x] Run Opening a PR. Skipped under explicit no-push/no-PR authorization.

## Architecture phases

- [x] Ground. Protocol findings are in the managed research report.
- [x] Sketch. Correlated command envelope/response; simple verb registry; explicit composite projections.
- [x] Agree. Artifact 20 was written before implementation and is parent-owned.
- [x] Implement.
- [x] Scrap. Not required unless the design fails its checks.

## Throughput checkpoint

- [x] Blocking first steps. Read program 00/01/02/03 and artifact 20; confirm feat/prime-cli at 3acf0f0.
- [x] Independent workstreams. Parent owns artifact 20 and isolated live checks. This worker owns code and offline checks. No child delegation.
- [x] Shared mutable state. Project writes stay in this worktree. No edits to upstream, streams, credentials, or other worktrees.
- [x] Smallest safe decomposition. One writer avoids overlapping transport/adapter/tests changes. Verify and commit the adapter before packaging/wrappers.

## Delivery

- [x] Record read-only findings. Direct supervisor protocol is feasible; structured answers are unsupported; exact model/auth remain live prerequisites.
- [x] Unit 1. Direct stdlib adapter and offline socket/subprocess tests. 25 tests passed with `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests -p 'test_prime_cli.py' -v`. `git diff --check` passed.
- [x] Unit 2. Dispatcher, remote wrapper, installer links, adjacent reference, and owned-session live check script. The live check was exercised against an offline owned-session supervisor fixture, including failure cleanup.
- [x] Manual deslop and complete offline verification. 40 Prime tests and 18 existing pi-web-cli tests passed. Shell syntax and diff whitespace checks passed. Removed dead/duplicate paths. Installed control-cli/deslop skills are unavailable; neither ran.
- [x] Return commit IDs and evidence in the managed report. Parent owns actual daemon/model verification.

## Initial delivery limits

Structured answers return 501. Stop does not dispose the resident runtime. Queue previews are not mechanically replay-safe. Archive holds a native input pause but does not claim atomicity against every producer. Unknown-model provider templates can clamp xhigh to off; native set_model can reject an unregistered ID. Status uses three non-atomic reads. No actual Prime authentication, inference, active-run steering, compaction, or off-host connection was tested by this worker.

## Parent verification

- [x] The design was written first at `docs/harness-program/20-prime-cli-design.md` in the shared docs worktree and remains uncommitted.
- [x] Repeat the final 49 Prime offline tests and all 105 existing stream tests on the implementation branch.
- [x] Run the real stable v0.10.1 daemon under this user with a dedicated socket and agent directory. No sudo or service installation.
- [x] Exercise every mapped command against owned sessions. Default checks now submit no text. Explicit inference mode verifies queued admission and clears it inside the pause scope, without claiming safety after connection loss or successful model delivery.
- [x] Record explicit model-set refusal, unsupported answer, and xhigh-to-off metadata clamp rather than claim parity.
- [x] Run the full installer fixture. It initially failed because its synthetic source clone omitted the new installer helper. Add the helper to that fixture and rerun successfully.
- [x] Consume independent same-model final review. All four accepted findings were verified fixed at 8ff0b59.
- [x] Attempt inference only with openai-codex/gpt-6.1-sol. Prime returned `No API key found for openai-codex.` No credentials or provider were changed, and model attempts stopped.
- [x] Preserve the exact failure through native prompt_and_wait in the live-check script. The initial admission-plus-message-poll probe timed out because Prime persisted no assistant error row. Add a regression and rerun all 49 Prime tests.
- [x] Verify installed agent-cli forwarding to the real socket with durable IDs and archived metadata.
- [x] Archive every owned session and stop both owned daemons through their dedicated sockets. The final check reported zero retained sessions and the final daemon socket was removed.
- [x] Record the final blocked result in artifact 20. Keep this session's design edits uncommitted and code commits local. No pushes or STATUS.md edits.

## Initial delivery result at bccf159

BLOCKED, not full parity. The exact native inference error was `No API key found for openai-codex.` The stable catalog also clamped requested xhigh to off and rejected native model selection for gpt-6.1-sol. Structured answers, exact runtime-disposing stop, safe internal queue replay, atomic archive, and real off-host connectivity remain documented gaps. No successful inference, active-run steering delivery, or compaction is claimed.

Small real-server reports remain outside git under `/tmp/prime-cli-check-v5p3iz67/`. The final inference report is `final-inference-check-exact.json`. Code, tests, and small docs are the only committed artifacts.

## Constraints

The worker made no real daemon/model calls or auth/session mutations. The parent may run the explicitly authorized isolated real-server checks. No existing sessions or streams, auth files, other branches, pushes, PRs, provider switches, or resource budgets are permitted. The CLI never starts a runtime. Missing capabilities return errors. Admission is not completion. Stop/report on a quota error.

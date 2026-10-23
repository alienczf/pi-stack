# Track 2 progress

## G20 follow-up

- [x] Phase A: Frame. Continue from pushed bccf159. No Prime login, credential access/import/copy, provider switch, or model inference is authorized in this follow-up.
- [x] Phase B: Design the workflow. Read both completed investigations. Public same-session queue resumption is feasible. Correlated answers, resident-root disposal without archive, and rich cross-session replay remain unavailable.
- [x] Phase C: Run the loop. Commit failing regressions before each feasible fix. All 69 Prime fixture tests pass. No push, auth, inference, real daemon, or SSH call by this writer.
- [ ] Phase D: Keep the audit trail. Code decisions and adjacent reference are updated. Parent owns the uncommitted artifact 20 update for Grok Bot.
- [ ] Phase E: Verify and hand back. Worker passed 69 Prime tests, 105 stream tests, the installer fixture, shell/Python syntax, and whitespace checks. Parent owns real non-inference checks and independent acceptance review.

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

## Current limits

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

## Final result

BLOCKED, not full parity. The exact native inference error was `No API key found for openai-codex.` The stable catalog also clamped requested xhigh to off and rejected native model selection for gpt-6.1-sol. Structured answers, exact runtime-disposing stop, safe internal queue replay, atomic archive, and real off-host connectivity remain documented gaps. No successful inference, active-run steering delivery, or compaction is claimed.

Small real-server reports remain outside git under `/tmp/prime-cli-check-v5p3iz67/`. The final inference report is `final-inference-check-exact.json`. Code, tests, and small docs are the only committed artifacts.

## Constraints

The worker made no real daemon/model calls or auth/session mutations. The parent may run the explicitly authorized isolated real-server checks. No existing sessions or streams, auth files, other branches, pushes, PRs, provider switches, or resource budgets are permitted. The CLI never starts a runtime. Missing capabilities return errors. Admission is not completion. Stop/report on a quota error.

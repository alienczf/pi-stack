# Track 2 progress

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
- [x] Repeat all 40 Prime offline tests and all 105 existing stream tests on the implementation branch.
- [x] Run the real stable v0.10.1 daemon under this user with a dedicated socket and agent directory. No sudo or service installation.
- [x] Exercise every mapped command against owned sessions. Queue tests hold a native input pause and clear inputs before release, so admission tests do not invoke an unintended model.
- [x] Record explicit model-set refusal, unsupported answer, and xhigh-to-off metadata clamp rather than claim parity.
- [x] Run the full installer fixture. It initially failed because its synthetic source clone omitted the new installer helper. Add the helper to that fixture and rerun successfully.
- [ ] Consume independent same-model final review.
- [ ] Attempt inference only with openai-codex/gpt-6.1-sol. Stop on missing credentials or quota. Record exact error and clean up owned sessions.
- [ ] Stop the owned daemon, finalize artifact 20, and hand back local commits without pushing.

## Constraints

The worker made no real daemon/model calls or auth/session mutations. The parent may run the explicitly authorized isolated real-server checks. No existing sessions or streams, auth files, other branches, pushes, PRs, provider switches, or resource budgets are permitted. The CLI never starts a runtime. Missing capabilities return errors. Admission is not completion. Stop/report on a quota error.

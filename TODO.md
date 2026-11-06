# PR #55 re-review recovery fixes

## Bug fix playbook

- [x] 1. Reproduce it yourself on the matching surface via the control skill (Non-negotiables), even when a debug or instrumentation protocol says to ask the user to reproduce. Ask the user only with a stated, specific reason the control surface cannot reach the target, and only after driving it as far as it goes. If it won't reproduce directly, synthesize the trigger, tighten conditions, or instrument until it fires.
- [x] 2. Binary-search the cause. Form the candidate hypotheses, then rule them out until one survives. Seed them with `how` over the affected subsystem and the **why** skill for regression history. Each pass, take the split that cuts the most remaining problem space, get runtime evidence, eliminate. When program state is unclear, add instrumentation or logging and read it as the code runs. Don't guess. Drive a long or stubborn hunt with Cursor's `/loop` command. Confirm the surviving *mechanism* with runtime evidence before the step-3 architect/interrogate fan-out.
- [x] 3. Plan the fix. If it crosses a function boundary, `architect` first. Delegate implementation to a subagent using your configured bug-fix model (default `grok-4.7-xhigh-fast`) with a specific scope.
- [x] 4. Verify on the same surface. The original repro now passes. "Inconclusive" or wrong-surface is not a pass. Flag it. Unit tests show branch behavior, not bug absence.
- [x] 5. Stage the commits so the failing repro lands before the fix in git history. See the **tdd** skill for the failing-test-first cadence when the bug has a cheap local test path. Skip it when the test would be expensive, integration-heavy, or unclear.
- [x] 6. Run **Opening a PR**. Update the existing PR only. Leave it open and unmerged for re-review.

## Current re-review scope and throughput checkpoint

Address P1, P2a and P2b from https://github.com/alienczf/pi-stack/pull/55#issuecomment-6695085146 at ac979607. The parent is the only source writer for these localized, known-mechanism state-transition fixes. One fresh read-only child independently checks the state census and design. No new lifecycle API or native adapter is planned. All work uses openai-codex/gpt-6.1-sol xhigh in this branch worktree. No live install edits, credentials, provider requests, force-push, model switch, or merge.

The rejected premise is that one journal's intermediate state can determine another actor's completed ownership. The census covers the current SYNC operation with and without ready, replacement publication versus source DCR phase, and successor delivery transport state versus exact receiver receipt and native transcript. Existing HistoricalRecovery, Operation, ReplacementIntent and Delivery records remain the data shapes. The previous validated dump, published replacement owner and exact completed receipt are distinct facts.

- [x] Commit failing behavior regressions and a rerunnable census across the three ownership boundaries. `3cb6c08f` and `95e7f778` precede runtime fixes.
- [x] Select the historical dump for eligible incomplete ready-but-unacknowledged SYNC, including previously blocked records, without validating that incomplete current dump.
- [x] Preserve and reconcile the exact completed replacement owner after initial loader failures, including previously corrupted DCR phases. Compare the entire frozen operation except phase and detail, not only its capacity receipt.
- [x] Observe sending and uncertain receiver receipts without redispatch, retaining every intent, generation and transcript fence.
- [x] Run the affected state matrix, existing recovery controls, and throwaway native ready-without-ack checks before publication. The final focused run passed 88 tests. All five native-service cases passed with supported cleanup.
- [x] Push and document the repair on the existing PR, leaving it open for independent re-review. Runtime repairs are `20024fa9`. The remote branch was verified at that SHA after a normal push from `ac979607`. PR #55 remains open against `prime-stack`.

### Re-review verification and limits

Evidence is under `/tmp/pr55-rereview-repairs`. The three primary red regressions failed without errors. The expanded owner matrix found and prevented overly broad reconciliation of a changed worktree, ready snapshot, or maintenance phase. `final-focused.log` passed 88 tests without skips. `verified-live/run-de505950873d4f7da0d250a7bfc4a4db/results.json` passed the three existing cases and both new ready-without-final-ack role cases. Every case completed supported close/archive and process/path cleanup. The coordinator ready case independently captured a prefix, not the entire final source. The runner checks prefix retention and the full hash frozen before retirement and reports this distinction.

A wider 193-test command passed 169 tests and produced 24 errors in the unrelated resume-admission status fixture. All 24 reproduce at `ac979607` in `baseline-resume.log`. No unrelated fix or full-suite rerun was attempted. The first native rerun failed because its verification captured bytes before the final turn finished appending. The corrected runner checks prefix retention rather than equating an early snapshot with a final file. No runtime safety rule changed to accommodate that probe. Native Prime support and general active/unknown-owner recovery remain outside this proof. The optional deslop skill was not found. Direct diff and comment review found no new application-code comments or suppressions to remove.

## Previous Phase-2 scope and throughput checkpoint

Address P1 and P2 from https://github.com/alienczf/pi-stack/pull/55#issuecomment-6692763141 at ace53a4f. One child owns implementation in this worktree. The parent independently reproduces and explores design in disposable state, then verifies and publishes. All work remains on openai-codex/gpt-6.1-sol xhigh. No live-install edits, provider requests, model changes, force-push, or merge. This is a bounded review-fix pass, not a merge-readiness watcher.

The data shapes are a separately bound historical-dump recovery intent, the immutable validated dump record, current retirement identity, and a terminal lane-local load disposition. The selected dump must not impersonate the stalled SYNC operation. No acknowledgement means no worker task admission, but unrelated coordinator observation must continue.

- [x] Reproduce stalled SYNC with retained dump and missing worker-load acknowledgement on the CLI and disposable native service.
- [x] Compare distinct recovery-intent and lane-ownership designs before implementation.
- [x] Add red-first regression tests for both findings and safety fences.
- [x] Implement historical-dump selection with exact checkpoint, current generation, role, assignment, archive, and stop protections.
- [x] Record terminal failed load evidence, fence its successor, and scope post-publication ownership to the worker lane.
- [x] Verify repeated ticks, restart reconciliation, negative safety cases, and the targeted acceptance suites. Parent final validation passed 89 tests without skips and three running-service cases after the pending-load guard. The unrelated baseline lane-health assertion still fails at ace53a4f. No full suite was repeated.
- [x] Push one fix wave to PR #55 and leave it open for re-review. The parent pushed all runtime repairs through 98be5f52 and posted https://github.com/alienczf/pi-stack/pull/55#issuecomment-6694492612. No merge occurred.

## Phase-2 writer handoff

The writer completed bounded P1 and P2 fixes through `817abd07`. `HistoricalRecovery` freezes the selected dump separately from the later stalled SYNC, current generation and retirement leaf. Native idle archival still enforces callback, input, effect and lifecycle ownership. Active or unknown owners remain fenced. Terminal unacknowledged loads retain transcript hashes and block successor task and failure-recovery admission. Worker loading and loader exceptions no longer starve coordinator observation.

The parent delegated one implementation writer and independently reviewed the final diff. Additional child delegation, model diversity, and child publication were excluded by the same-model contract. No native overlay change or manifest regeneration was necessary.

The final three running-service scenarios passed with supported stream close, archive dispositions, process stop and scratch cleanup. Evidence is `/tmp/pr55-phase2-writer/final-live-three/run-1098150765534b3285bb855caa18e6e2/results.json`. CLI red, green and unchanged-baseline evidence is under `/tmp/pr55-phase2-writer/logs`. An extra native model-error probe proved its successor stayed fenced, but supported cleanup refused its parked failure. The strengthened runner correctly failed that diagnostic. No lifecycle bypass was added. A final red-first regression exposed pending loads being stranded in replacement history. New replacements now wait for the current pending load to settle without blocking coordinator observation. Its late exact acknowledgement is still observed. The final two targeted checks passed in `/tmp/pr55-phase2-writer/logs/pending-history-green.log`. Parent reruns then passed 89 tests and all three default native-service scenarios. Evidence is `/tmp/pr55-phase2-parent/final-unit.log` and `/tmp/pr55-phase2-parent/final-live/run-f51e57400b20496ab614318473e6a944/results.json`. Full native Prime support and unconditional active-owner recovery remain unverified.

# Previous Phase-1 work

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame
- [x] Phase B: Design the workflow
- [x] Phase C: Run the loop
- [x] Phase D: Keep the audit trail
- [ ] Phase E: Verify and hand back. Shared parity checks passed. Full native Prime support and unconditional historical-dump recovery remain unimplemented.

## Definition of done

Open a ready pull request to alienczf/pi-stack against the correct Prime baseline. The shared stream path must remove spawn ratification, heal silently disabled or stalled drive on tick while preserving deliberate stops, and bound compaction so validated dump recovery works for coordinators and workers. Recovery must not silently lose retained data before the last validated dump. Do not claim native Prime support without a real supported backend.

## Throughput checkpoint

The baseline is origin/prime-stack at f685e3ad1485192a45bc7b6eed6b260961a965e4. It is an ancestor of merged main at cba29cd0. PRs 44-47 remain open against prime-stack and are context, not destinations. Two read-only investigations will compare dependency-safe integration choices and backend limits. One child writer owns this worktree afterward. One fresh child reviews its result. The parent owns final artifact inspection, validation, push, and PR creation. All children inherit the current model. No live-tree writes, deployment, credentials, or production streams are permitted.

## Writer checkpoint

The reversible choice is an exact local integration of merged main at cba29cd0, including its archive, retained-source, and replacement prerequisites. Six of seven new acceptance regressions fail at f685e3ad after correcting test-fixture setup errors. The existing drive record, StopIntent, per-session DCR operations, retained dump snapshots, and ReplacementIntent remain the data shapes. No native Prime adapter appears in this baseline or merged implementation. Shared Pi adapter evidence cannot prove native Prime behavior.

## Data shapes

Use the existing stream drive record and stop provenance, per-role recovery records, and validated dump manifests. Reuse merged engine and native adapter behavior rather than inventing another lifecycle or weakening pending Prime capability admission.

## Designed units

- [x] Inspect ancestry and PR 44-47 context. Create an isolated branch from prime-stack.
- [x] Trace shared-engine parity and Prime backend constraints. Compare a dependency-safe main integration with selected backports.
- [x] Capture reproducible pre-change failures or missing behavior.
- [x] Integrate the merged implementation and a rerunnable parity acceptance check.
- [ ] Run focused checks and the complete available stream suite in disposable state. Parent final focused acceptance passed 64 tests without skips. The full run was interrupted at the deadline with failures already recorded and no summary. It was not repeated.
- [x] Review the diff, comments, provenance, and evidence without changing the model. Parent review of the final writer diff is complete. The prematurely launched child review is not final verification.
- [x] Inspect the actual artifacts and run a throwaway native-service validation when dependencies permit. Writer native-module regressions pass. Parent supplied seven passing disposable Pi service cases. Neither proves native Prime.
- [x] Commit, push, and open a ready PR targeting prime-stack. https://github.com/alienczf/pi-stack/pull/55 is open and not a draft. No merge or deployment occurred.

## Handoff

The hardened comparison runner rejects setup errors and requires three named baseline behavior failures. The parent final focused run passed 64 Python tests without skips, including three native Node scenarios in one wrapper. Engine and native files remain byte-identical to cba29cd0. The explanation and append-only trail are under docs. Native Prime support, automatic selection of a historical dump after a later stalled SYNC, and full-suite completion remain open. PR https://github.com/alienczf/pi-stack/pull/55 delivers the verified shared-engine unit without claiming the complete acceptance predicate.

## Constraints

ZF's supplied order relayed by Grok Bot authorizes the in-scope reversible work. No additional spawn-ratification or human confirmation gate is warranted. Preserve deliberate stops and existing capability safety. Do not change the installed model or expose authentication material. Use only throwaway live validation.

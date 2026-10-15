# Grok Bot cron-only scope update

## Feature playbook

- [x] 1. `how` over the affected subsystem. Read the current records, CLI, tests, and four skills before editing.
- [x] 2. `architect` for parallel design exploration. skip: explicit subtraction retains the tested wait model and needs no new architecture.
- [x] 3. Write the throughput checkpoint as four todo items.
- [x] 4. Delegate code-writing to a subagent with a specific scope and named data shape. One writer retained `AssistantOutcome` and `SessionObservation`; the parent independently reviewed the result.
- [x] 5. Verify on the matching surface. Actual CLI subprocess tests and all documented root checks passed.
- [ ] 6. Rebase into small, ordered commits. Stack follow-ups. Publish ordinary follow-up commits on the existing branch. No force-push.
- [x] 7. If the design is contested, `interrogate` before shipping. skip: ZF supplied an explicit scope and there is no contested design.
- [ ] 8. Run **Opening a PR**. Update https://github.com/alienczf/pi-stack/pull/31 to the current scope and confirm it remains open and unmerged.

## Throughput checkpoint

- [x] **Blocking first steps.** Read the current plan and source, confirm the branch, and preserve the parent's plan edits.
- [x] **Independent workstreams.** n/a: the CLI and replacement text share one contract, so one writer owns them.
- [x] **Shared mutable state.** Only this worktree changes. No installed CLI, live routines, other repositories, or provider and model settings change.
- [x] **Smallest safe decomposition.** Retain the wait model, reduce the command set, then verify the CLI and all four complete skills together.

## Scope gates

- [x] Expose only the original CLI commands plus short bounded wait.
- [x] Retain idle, error, and usage_limit classification without event selection or unused assistant timestamp storage.
- [x] Preserve strict API validation, all busy flags and queued work, current and stale errors, usage limits, byte caps, hard deadlines, and verified-or-null cwd.
- [x] Put the full copyable scheduled routine prompt in pi-async-wait with all required placeholders.
- [x] Include cancellation and deadline checks first, one status read, all three stream files, artifact verification, meaningful-change reports, and terminal self-deletion with disable-on-failure.
- [x] Link all three complete replacement routing skills to pi-async-wait and document copying all four skills and reloading.
- [x] Preserve deployment authorization restrictions, pi's repository ownership, and operator merge ownership.
- [x] Inspect current files for scope compliance and tracked filenames for key or URL files. No matches found.
- [x] Run `python3 -m unittest discover -s grokbot/tests -v`. All 26 tests passed with no skips, including 10 added tests.
- [x] Run `python3 scripts/check-readme-commands.py --execute`. All seven commands passed, including 105 pi-streams tests.
- [x] Run `git diff --check`, inspect the diff, and confirm no staged files.

## Remaining acceptance gate

- [x] The parent independently reviewed code, tests, all four skills, and rollout instructions. It reran all 26 CLI tests without skips and all root checks, including 105 pi-streams tests. No actionable findings.
- [x] Current-file scope, skill metadata, links, routine template, and CLI command-set checks passed.
- [ ] Commit, push over HTTPS, and update the existing PR description. Live routine permissions still need an authorized rollout check.

## Constraints

NEVER use a background worker, executor, AwaitShell or sleep loop to wait on a pi session or stream.

A Grok Bot scheduled cron invocation checks durable signals once and returns. Do not use OS cron, extend the deadline, or spawn replacement routines. Failed API is unknown, not idle. Idle is not task proof. Compact before 70 percent context. Stop and report usage limits without provider switching. The parent may commit, push over HTTPS, and update the existing PR. No installed CLI changes, live routines, real secret reads, force-pushes, or merges.

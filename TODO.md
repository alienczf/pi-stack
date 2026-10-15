# Grok Bot async handoff

## Feature playbook

- [x] 1. `how` over the affected subsystem.
- [x] 2. `architect` for parallel design exploration.
- [x] 3. Write the throughput checkpoint as four todo items.
- [x] 4. Delegate code-writing to a subagent using your configured feature model with a specific scope, named data shape, and success criteria.
- [x] 5. Verify on the matching surface.
- [x] 6. Rebase into small, ordered commits. Stack follow-ups. The branch remains based on fetched main with separate implementation, rollout, and decision-record commits.
- [x] 7. If the design is contested, `interrogate` before shipping. skip: scouts and cross-judge selected the same design; the parent's fresh review remains required.
- [x] 8. Run **Opening a PR**. https://github.com/alienczf/pi-stack/pull/31 is open, ready, based on main, and not merged.

## Throughput checkpoint

- [x] **Blocking first steps.** Inspect installed CLI, fetch main over HTTPS, create the requested worktree, and locate replacement skill sources before implementation.
- [x] **Independent workstreams.** Two read-only scouts compared status-based and event-based designs. Both recommended status/messages. The cross-judge selected the shared observer before the single writer resumed. Implementation and verification ran in that one writer.
- [x] **Shared mutable state.** One implementation writer owns this worktree. Read-only scouts use separate result artifacts. No edits to the live installed CLI or other repositories.
- [x] **Smallest safe decomposition.** One writer keeps the CLI, tests, and rollout commands consistent. A fresh read-only review follows.

## Delivery gates

- [x] Create `feat/grokbot-async-watch` from `origin/main` at the requested worktree path.
- [x] Trace PI WEB status, messages, and error signals against installed server code.
- [x] Record design alternatives, synthesis, event semantics, and exit codes in `PLAN.md`.
- [x] Implement bounded wait and detached host notify with private-file secrets and bounded retries.
- [x] Add fake PI WEB and webhook integration tests, including detach, timeout, failure, and secret safety.
- [x] Add four complete generic skills and rollout instructions with webhook auth TODO and cron fallback.
- [x] Run CLI tests and existing repository checks, inspect diff, and remove unnecessary comments. All 29 CLI tests and all 105 pi-streams tests passed. No detached tests skipped.
- [x] Parent obtains independent review before commit or PR creation. The original paused reviewer resumed after the host workflow failed to await. It passed the full change and independently reran all tests.
- [x] Commit, push through HTTPS with the credential helper, and open a ready PR.
- [x] Verify PR URL and prepare the files, tests, and setup-question report. GitHub reports OPEN, isDraft false, and mergedAt null. No merge was attempted.

## Constraints

No secrets in argv, output, logs, or commits. Do not provision a real webhook or change the installed CLI during this build. Never switch providers on a usage limit. Compact before 70 percent context. Keep all user-facing recipes independent of Slack, named hosts, and access wrappers.

## Skill availability

The installed skill tree has no `control-cli` or `deslop` leaf. Use direct CLI subprocess tests and a manual diff cleanup instead. Only `poteto-agent` is executable, so design and review roles use bounded tasks on that agent with the inherited model.

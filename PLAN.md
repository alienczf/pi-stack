# Grok Bot cron handoff plan

## Current scope

ZF's scope change makes Grok Bot scheduled cron routines the only long-wait mechanism. Hand the repository unit to pi, create one short self-deleting routine, and return control. Each invocation reads durable signals once and exits. Require an explicit done condition and an absolute UTC deadline.

Keep `pi-web-cli wait <sid> --timeout <seconds>` for one short bounded check. The timeout must be finite and satisfy `0 < seconds <= 300`. Never chain calls into a long wait.

## Worktree and authorization

Use an isolated worktree on `feat/grokbot-async-watch`. The existing PR is https://github.com/alienczf/pi-stack/pull/31.

The delegated writer changed repository files without commit or publication authority. The parent reviews, commits, pushes through the explicit HTTPS URL and host credential helper, and updates the existing PR. Do not force-push, change the installed CLI, create live routines, or read real secrets. Keep provider and model unchanged. Preserve generic deployment authorization restrictions. Pi owns code, worktrees, checks, commits, pushes, and PRs within its brief. The operator owns merges.

## Retained data shape

`AssistantOutcome` and `SessionObservation` remain the validated data shape for bounded wait. One classifier returns idle, error, or usage_limit, or continues the bounded check while busy. The command set is the original commands plus wait. Event selection and the unused assistant timestamp field are removed. Existing wait JSON fields and strict response validation remain unchanged.

Wait retains all activity flags, queued-work handling, current-assistant parsing, stale-error suppression, response byte caps, a hard deadline, and verified-or-null cwd. `PI_WEB_URL` and original command implementations remain unchanged.

## Routine contract and documents

The durable record contains the sid, authorized host access, expected artifact, optional stream directory, explicit done condition, absolute UTC deadline, routine id, and last reported state. Session idle is not the done condition.

The full copyable prompt is in `grokbot/skills/close-the-promise-loop/SKILL.md`. Each invocation checks cancellation and deadline first, reads `pi-web-cli status` once, and reads relevant stream `STATE.md`, `ALERTS.md`, and `STREAM.md` once. It verifies the artifact, reports meaningful changes only, saves state, and returns. Failed API is unknown, not idle.

Delete the routine on verified done, terminal error, usage limit, cancellation, or deadline expiry. If deletion fails, disable it and report. Never extend the deadline or spawn a replacement routine. Use Grok Bot scheduling, not OS cron. Compact before 70 percent context. Stop and report usage limits without provider switching.

The three complete replacement routing skills link to close-the-promise-loop. `grokbot/README.md` covers copying all four skills, reloading, scheduling, and short wait exit codes.

## Throughput checkpoint

1. Read the current records and source before editing. Confirm the branch and preserve the parent's existing plan edits.
2. Use one writer for the CLI, tests, four skills, and rollout guide because their references must agree. No child launches.
3. Keep installed tools and other repositories unchanged. The parent independently reviews the complete diff and reruns the checks after the writer returns.
4. Keep the tested wait model, reduce the command set, then verify CLI behavior and documentation together. No new architecture is needed.

## Verification evidence

- `python3 -m unittest discover -s grokbot/tests -v` passed all 26 tests with no skips. Tests run the actual CLI against fake loopback PI WEB servers and temporary session metadata.
- Retained all 16 bounded-wait and compatibility tests. Added 10 tests for unsafe cwd metadata, text parsing, assistant schemas, status byte caps, trickled headers, invalid responses, argument validation, original GET and POST commands, and the CLI command set.
- `python3 scripts/check-readme-commands.py --execute` passed all seven documented commands. The pi-streams suite passed all 105 tests. Installer checks used temporary fixture homes.
- `git diff --check` passed. CLI help exposes only the original commands plus wait.
- Current-file scope inspection found no excluded-path references. A tracked filename audit found no key or URL files.
- The parent independently reran all 26 CLI tests without skips and all seven documented root commands, including 105 pi-streams tests. Manual review found no actionable issues or new phase-narrating comments.
- A separate scope check confirmed that removed commands fail as invalid choices, all four skills have valid metadata and links, and the routine template includes every required signal and retirement condition.

## Publication

The parent pushed the cron-only scope update through the explicit HTTPS repository URL. The existing PR title and description now reflect only scheduled routines and bounded wait. GitHub reports https://github.com/alienczf/pi-stack/pull/31 open, ready, and unmerged. The installed GitHub CLI's edit command hit a deprecated Projects API, so the parent updated the same PR through `gh api` instead. No merge or force-push occurred.

## Current limitations

Snapshot checks can miss short transitions and daemon-only errors. Idle does not prove that the repository goal passed. Live scheduling and routine deletion or disabling remain unverified because this task forbids live routine creation. An authorized rollout must verify those permissions. The parent completed independent code and documentation review. No merge is authorized.

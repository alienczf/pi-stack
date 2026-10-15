---
name: orchestrate-with-pi
description: >-
  Routes a repository unit to pi after Hand off the unit applies. Prefer
  pi-streams for campaigns and PI WEB for single sessions. Uses pi-async-wait
  to resume through routines after a work prompt or steer.
---
# Orchestrate with pi

This is a recipe. Decide whether to hand off with [Hand off the unit](sand-workflow:principle-hand-off-the-unit) first. Use the bot's authorized PI host access and the commands in [PI WEB control plane](sand-workflow:pi-web-control-plane). Existing deployment and host-authority gates still apply.

## Prefer pi-streams for campaigns

A stream has a coordinator, pi sessions for bounded units, and a private stream repository with durable state. Use the installed `/stream` and `stream-kickoff` workflows rather than invent alternate stream CLIs.

- Read the registered pi-streams project index to find the stream repository.
- Read that repository's `STATE.md`, `ALERTS.md`, and `STREAM.md` for decisions, outages, and conflicting ownership. Do not rely on an empty global alert index.
- Run the authorized `pi-streams doctor` check after stack updates. Do not prompt live sessions until the deployed host build matches the intended stack version.
- Hand the full campaign brief to its authorized coordinator. Do not become a second planner or sequence implementation workers from the bot chat.

Jig is not the stream workflow. Do not start a new stream with `jig init`, `/jig`, or `/skill:jig`. Leave old Jig data alone unless the operator asks for cleanup.

For a campaign, use the full scheduled cron routine template in [Pi async wait](sand-workflow:pi-async-wait). Each short invocation reads `STATE.md`, `ALERTS.md`, and `STREAM.md` once and returns. Verify the campaign's explicit done condition before its absolute UTC deadline. One idle coordinator turn does not prove that every stream thread is complete.

## Single-session path

1. Have pi create one isolated worktree per unit on the authorized PI host. Do not create it on the bot's disk or reuse a dirty tree across units.
2. Use `pi-web-cli list --cwd <worktree>` to find an existing session. Adopt its sid if appropriate. Otherwise use `pi-web-cli spawn <worktree>`.
3. Send `/poteto`, then `/goal <checkable predicate>` or the complete authorized work brief.
4. After the work prompt returns accepted, follow [Pi async wait](sand-workflow:pi-async-wait). Create one short self-deleting Grok Bot scheduled cron routine from its full template, not an OS cron job. Do not poll status or the transcript in a bot-side loop.
5. For a focused steer, use `pi-web-cli prompt <sid> "<correction>" --steer`. Retire an obsolete routine before a separately authorized replacement. Do not create a routine merely for an empty new session.
6. On a routine wake, verify the expected artifact against the explicit done condition. Idle is not proof that the goal passed. Pi owns code, worktrees, checks, commits, pushes, and PR creation. Do not perform that repository work from the bot chat.
7. Do not merge. The operator owns merge authorization.

## Close the promise loop

After a work prompt, steer, or stream handoff, record the sid, authorized host access, expected artifact, optional stream path, done condition, absolute UTC deadline, routine id, and durable last-state record. Return control after the routine is scheduled. Do not promise a later confirmation without a durable wake.

Each invocation checks cancellation and deadline first, reads status once, verifies the artifact, reports only meaningful changes, and returns. Follow pi-async-wait to delete the routine on verified done, terminal error, usage limit, cancellation, or deadline. If deletion fails, disable it and report. Never extend its deadline or spawn a replacement routine.

NEVER use a background worker, executor, AwaitShell or sleep loop to wait on a pi session or stream. For a genuinely short check, `pi-web-cli wait <sid> --timeout 240` may run once. Do not chain short waits into a long one.

## Local-work exception

An explicit `dowork` request permits local work only when this deployment's policy allows it. It does not override network restrictions, repository restrictions, host-authority gates, or the assigned stream owner.

## Pi skills and context

Point pi at the installed `/poteto`, `/goal`, `/stream`, `correct`, `reflect`, and verification skills. Do not reimplement them in the bot.

Compact before 70 percent context. Preserve the durable routing record across compaction. On a usage limit, stop and report. Do not switch provider.

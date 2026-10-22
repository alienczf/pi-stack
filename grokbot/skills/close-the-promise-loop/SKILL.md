---
name: Close the promise loop
description: >-
  Always apply before ending ANY turn that says I'll tell you / confirm / send /
  update you, once X lands, when it's done, or that waits on a pi session,
  stream, PR, CI, or other external result. Either deliver now or create a
  self-deleting routine naming that exact deliverable; never a background worker
  or sleep loop.
---
# Close the promise loop

One rule for every Grok Bot: promises and async waits. Replaces the old Pi async wait skill.

## The rule

Never end a turn on a verbal promise alone. "I'll confirm once…", "I'll tell you when…", "once X finishes I'll…", "my watch will send…", "I'll update you" may be the last act of a turn only if that same turn:

1. Creates or updates a **self-deleting routine** whose prompt names the **exact promised deliverable** as its done condition (e.g. "send ZF the mid row for the 3-way post-trade table"), not just "check the stream".
2. Gives it a **deadline**, after which it reports honest status to the user and deletes itself.
3. **Reads the routine back** (UpdateRoutine get) and confirms the saved prompt contains the deliverable and the delete step.
4. Registers an `in_progress` todo for the deliverable.

Otherwise: deliver now, or say plainly that no follow-up is coming.

### Attaching to an existing watch

Allowed only if you edit that watch's prompt to add the deliverable as a named done item, then read it back. A generic stream watch that doesn't name the promise does not count; that is how promises leak.

## Waiting on external work

- NEVER start a background worker, executor, `AwaitShell`, or shell `sleep`/`while` loop to wait on a pi session, stream, PR, CI, or PI WEB status. Workers only wake you for your own subagents and shell jobs; an external wait silently dies.
- One inline status check (`pi-web-cli status <sid>`) is fine. A bounded `pi-web-cli wait <sid> --timeout <=300` is fine if the host has it.
- Anything longer: hand off the unit, create the routine above, end the turn.
- Short promises that ride on your own subagent's completion wake are fine only if the todo exists; on that wake you deliver.

## Watch routine recipe

Cadence 10-30 min, stepped off the hour (e.g. `23,53 * * * *`). The prompt states:

1. Target: session id, host, worktree/branch, PR, CI run, or stream repo.
2. Durable signals: `pi-web-cli status`, git/PR/CI state, stream `STATE.md` / `ALERTS.md` / `STREAM.md` in the stream's own repo (not the empty `~/.config/pi-streams/ALERTS` index).
3. Light care: compact if context >85% (abort, then `/compact`); re-prompt once if idle >40 min with no progress; on a usage limit never switch provider, notify the user instead.
4. **Done condition** = the named deliverable. When met: send it to the user, then delete the routine.
5. **Deadline**: report status and what's blocking, then delete.
6. Otherwise silent. No "no change" pings.

## On every wake

Before ending any wake (routine tick, executor finish, agent message), scan open promised todos. Deliver the result or honest status for each. Quiet is allowed only when nothing was promised and nothing actionable changed.

## Allowed without a routine

- Answers, drafts, status delivered in this turn
- Hand-offs that return a live session / stream link now (promise already closed)

## Anti-patterns

- Ending on "I'll update you" after a dispatch
- "My 30-min watch will send it" when the watch prompt never mentions it
- Changing a routine and not reading it back (it may pause or delete itself on old instructions)
- Executors that `sleep 600` and check again
- Permanent watches with no done condition or deadline
- Todo without routine, or routine without todo

## Related

- Routine shapes: the Cursor-managed routines skill
- [Hand Off the Unit](sand-workflow:principle-hand-off-the-unit)
- [Orchestrate with pi](sand-workflow:orchestrate-with-pi)

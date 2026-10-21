---
name: Orchestrate with pi
description: >-
  Use when handing an Alphalab / options-01 unit to pi after Hand Off the Unit
  applies. Prefer pi-streams (/stream) for multi-thread campaigns; PI WEB
  spawn/prompt for a single session. Not for deciding whether to hand off.
---
# Orchestrate with pi

Recipe only. Decide with [Hand Off the Unit](sand-workflow:principle-hand-off-the-unit) first.

Drive work on `hpc180-options-01` over Twingate userspace (`options-01-ssh` / `pi-web-cli-remote`). Reach: [Alphalab access](sand-workflow:alphalab-access). Control plane details: [PI WEB control plane](sand-workflow:pi-web-control-plane).

## Prefer pi-streams for campaigns

**pi-streams** is the harness (pi-stack main ≥ `5c0e41e`). A stream is a Cursor Project whose threads are pi-web sessions: one coordinator plans and delegates into code worktrees; it does not write product code itself.

- Index: `~/.config/pi-streams` (`projects/<name>.toml`, `streams.tsv`, `ALERTS`). Read `ALERTS` for outages and for two streams claiming the same worktree or branch.
- Each stream has a private git repo at `<project-root>/streams/<id>/`.
- Skills: `/stream` (new, status, close) and `stream-kickoff`. A five-minute `pi-streams tick` timer runs with no model tokens. `pi-streams upgrade` refreshes unedited template files.
- Design: `docs/design/pi-streams.md` in `~/.pi-stack`.
- Doctor: `pi-streams doctor` on the host after stack updates.

**Jig is removed** from pi-stack. Do not start streams with `jig init`, `/jig`, or `/skill:jig`. Leftover `.pi/jig/` trees may still exist in old worktrees — leave them alone unless asked to clean up.

For multi-thread / long-running desk campaigns (ETL, migrations, multi-PR features): have the owning desk bot (or a live pi session that already has streams skills) run `/stream` and hand full context to the coordinator. Grok Bots do not invent alternate stream CLIs.

Hard rule: do not prompt any live session until the host `pi-streams` build matches the intended pi-stack main (verify with `pi-streams doctor` / `~/.pi-stack` HEAD).

## Single-session path (still valid)

1. One isolated git worktree per unit on options-01. Never this computer's disk. Never share one dirty tree across units. Have **pi** create the worktree — do not `git worktree` yourself.
2. Via `pi-web-cli-remote` (or `options-01-ssh`): `pi-web-cli spawn <cwd>`, then `prompt` `/poteto`, then `prompt` `/goal <checkable predicate>`. If a session is already live in that cwd, `list --cwd` and `prompt` it instead of spawning another.
3. Do not wait on it in this turn. Create a self-deleting watch routine per [Close the promise loop](sand-workflow:close-the-promise-loop), then end the turn. Never a background worker or sleep loop.
4. Live steer: `pi-web-cli-remote prompt <sid> …`. Target by session id.
5. When a unit has a GitHub PR, have pi open it (or comment `@claude` if GitHub is usable). Do not commit, push, or `gh pr create` yourself.
6. Do not merge. The operator owns merge.

## Outer-loop delivery

After a spawn, steer, or stream handoff, close the promise loop with [Close the promise loop](sand-workflow:close-the-promise-loop). Do not end on "I'll confirm once…". For long campaigns, watch the stream repo's `ALERTS.md` / `STATE.md` / `STREAM.md`, not the empty index `~/.config/pi-streams/ALERTS` alone.

## `dowork` exception

Only when [Hand Off the Unit](sand-workflow:principle-hand-off-the-unit) allows it: user clearly said do the work here, and it does not need `hpc180-options-01`, `10.0.60.45`, or other gated hosts. Alphalab repo edits never qualify.

## pstack

Pi loads the live allowlist in [pstack on pi](sand-workflow:pstack-on-pi). Point pi at `/poteto`, `/goal`, `/stream`, `correct`, `reflect`, and verification skills. Do not reimplement them here.

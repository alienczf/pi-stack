/skill:poteto-mode

# Harness program, track 4: proposal B over prime (feasibility spike)

This is the /poteto entry point, loaded as the poteto-mode skill. Work in poteto style throughout. Brief written by Grok Bot, 2026-10-23 11:50 SGT (Z18/G26).

**Goal.** Investigate how pi-stack harness **proposal B** ("Runtime-owned obligations and hooks", section `## Proposal B` in `docs/harness-program/30-research-designs.md`, mechanisms B1-B6) can be implemented over **prime** (prime-agent). ZF's hypothesis: prime is durable, so setting up hooks and runtime-owned records might be easy. Test that hypothesis with evidence; don't defend it or dismiss it.

**The design is not locked (Z17).** ZF is still iterating. Your output is input to the next design round, not a decision. Make your own calls inside this spike and log them, but don't frame anything as chosen for pi-stack.

## Your outputs

1. **Artifact:** `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/40-b-over-prime.md`. Write it there and **don't commit it**. Grok Bot collects it. Write this file and no other file in the docs worktree; the other tracks share it.
2. **Spike code (only where cheap):** your own worktree on branch `spike/b-over-prime` off origin main. Create it first, before anything else:
   ```bash
   git -C /home/alphalab/Projects/pi-stack/pi-stack fetch origin
   git -C /home/alphalab/Projects/pi-stack/pi-stack worktree add /home/alphalab/Projects/worktrees/pi-stack-b-over-prime -b spike/b-over-prime origin/main
   ```
   (origin/main is `3acf0f0` as of 11:48 SGT.) Do all spike work there, in small local commits. **Don't push, merge or open PRs**; Grok Bot collects.

## Inputs (read these; targeted reads with rg and line ranges, not whole-file dumps)

All docs are in the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`:
- `30-research-designs.md`: Proposal B in full, plus "Checks required before selecting a design", the backend-capability caveat ("A shared CLI spelling does not establish Pi/prime equivalence"), and B's coverage table.
- `20-prime-cli-design.md`: track 2's map of Prime's supervisor protocol (daemon protocol 7, schema 30), the command mapping table, the known gaps (correlated questions, replayable queue data, durable failure/completion channel, preflight errors without a persisted assistant row), and the Verification section.
- `02-principles.md`: the layer rule. Every mechanism you propose gets `LAYER n` and one sentence on why that layer, and why a stronger layer can't carry it. Not frameworky. No default budgets (D1).
- `03-decisions.md`: especially Z11 (failure parking, last-good turn id, F-DCR fork), Z15 (single STATE.md with Goals, Rules and a capped Log, plus history/), Z16/G24 (A/C merge draft, intake-written ask rows), Z17, Z18/G26.
- The **feat/prime-cli** branch, read-only: worktree `/home/alphalab/Projects/worktrees/pi-stack-prime-cli` (or `git show feat/prime-cli:<path>` from the main clone). Don't commit to it or edit it.
- **prime-agent source and docs:** checkout `/home/alphalab/Projects/prime-agent` (HEAD `71beca9`, nightly; crates `pa-agent pa-ai pa-cli pa-core pa-daemon pa-models pa-types ...`, plus `docs/`, `skills/`, `AGENTS.md`, README). The stable v0.10.1 release that track 2 verified is source revision `8aac869` and the checksum-verified binary is `/tmp/prime-t2.3qhjos6h/prime-agent`. Look for anything else installed (`~/.cargo/bin`, `~/.local/bin`, other clones) and say what you found. Where nightly and v0.10.1 differ on a primitive you rely on, say which one has it.

## Deliverable contents (40-b-over-prime.md)

Put a short summary and the (b) table near the top so ZF can read it first.

**(a) Inventory of prime primitives, with file:line evidence** (crate path and line range, and the revision). At least: the durable session and turn store (format, where it lives, what survives a daemon restart), the event stream (subscribe, replay from offset, event types), hooks / extension / plugin / tool-interception points (pre and post turn, on message admission, on tool call, on compaction, on error), turn and message ids (stable? addressable?), fork (at an exact turn id?), the input queue (steer, follow-up, persistence of pending input before ack), intake (where a user message enters and gets an id), compaction, cancellation, child or sub-agent sessions and their adoption, and errors as durable records. Mark each one **exists / partial / absent**, with evidence. Absence claims need the searches you ran.

**(b) Mapping table:** each B mechanism (B1-B6, and the lifecycle items: persist pending input before ack, typed intake keyed by source message, cancellation, single designated owner, generated read-only views into the Z15 STATE.md layout, completion admission with pinned evidence, Z11 park / last-good / fork / adopt, quiescence before a second writer) to the prime primitive that carries it, or to a **gap** and exactly what's needed (an upstream change, an out-of-process supervisor client, or a pi-stack-side shim), each with LAYER n. Compare the same row against pi-web as it exists today (the installed pi-web, read-only; find its source as track 1 did, and never edit an installed dist).

**(c) A minimal hook prototype, where cheap**, on `spike/b-over-prime`. For example: a small client of Prime's supervisor socket or event stream that records a typed intake row keyed by message id before dispatch, or that reacts to a turn-completed or error event by writing a last-good file. Verify it against a **local, isolated prime server you start yourself** under your own user: its own temporary `PRIME_AGENT_CODING_AGENT_DIR`, `PRIME_AGENT_SESSION_DIR` and `PRIME_AGENT_DAEMON_SOCKET`, run in a tmux session you name `prime-t4-<short>`, with provider failover and quota parking disabled as in track 2's isolated settings. Shut it down through its own socket when you're done. **Real inference is blocked** (no Prime Codex login on this host). Verify without a model: use control operations, a fixture, a failing provider preflight, or Prime's own test harness where it fits. Say exactly what was and wasn't verified. Add a test that runs offline. If the prototype isn't cheap, say why and stop at the design.

**(d) Effort, risks, verdict.** An effort estimate per mechanism (and total) for B over prime vs B over pi-web. The risks, including upstream churn (the nightly is moving), protocol stability, how much of B would live in an upstream fork vs pi-stack, and the "service grows into a framework" risk named in Proposal B. Then a plain answer: **is B over prime materially simpler than B over pi-web?** Yes, no or partly, and why, citing the rows in (b). Also note what it implies for the A/C merge draft (G24), if anything.

Add a short **Decisions** section: your calls with a one-line reason each.

## Hard limits

- **Don't touch** the live PI WEB on 127.0.0.1:8504 (read-only status calls at most), the pi-streams tick service or timer, `~/.pi-stack`, `~/.local/bin`, or any system service. No sudo.
- **Don't touch track 2's Prime roots, sockets or tmux sessions** (`/tmp/prime-t2.*`, `/tmp/prime-cli-check-*`, `prime-cli-t2-*`). Read the binary and source only; use your own temp root.
- Don't prompt, steer, stop, rotate, archive or spawn any other existing session or stream. That includes tracks 1, 2 and 3, the pi-streams-harness coordinator and the prime-stack coordinator `01a16177-96a3-7923-bfe9-55fbc3774482`. You may use your own subagents on the same model (openai-codex/gpt-6.1-sol).
- **No credentials.** Never run a login, never open, copy, import or print any auth file, token or secret, pi's or Prime's. If a step would need one, stop that step and report what's missing.
- Never stash or reset in any live worktree. Don't touch other branches.
- **Never switch provider or model.** On a usage limit or quota error, stop and report.
- No push, no merge, no PR, no GitHub comments. Grok Bot is the only pusher.
- No default budgets or caps (D1). Git holds code, docs and small reports, never data; runtime roots, logs and JSON reports stay in `/tmp/`.
- Don't edit STATUS.md.

## Status line

Whenever you finish a phase, stop, or get blocked, end your reply with one line:
`TRACK 4 STATUS: <inventory|mapping|prototype|done|blocked|partial> | artifact=docs/harness-program/40-b-over-prime.md | branch=spike/b-over-prime@<sha or none> | next=<one line>`
Grok Bot reads that line and updates STATUS.md.

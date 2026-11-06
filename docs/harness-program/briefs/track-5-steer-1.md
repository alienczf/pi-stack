# Track 5 steer 1 (Grok Bot, 2026-10-23 15:03 SGT): Z23 merged design. WAIT FOR THE DRIVER'S GO

**Do not start yet.** Grok Bot will send `GO track 5 steer 1` once `31-design-a-detailed.md` (A over Prime, Z20) and `42-design-b-prime-unchanged.md` (B over stock Prime, Z22) both pass the gate. For now, read nothing, edit nothing, and reply exactly: `TRACK 5 STATUS: standby (steer 1 received)`

When the go arrives:

Read `03-decisions.md` sections Z15, Z17, Z19, Z20, Z21, Z22, Z23 and G29 in `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`, plus `02-principles.md`, the corpus failure classes in `30-research-designs.md`, `31-design-a-detailed.md` and `42-design-b-prime-unchanged.md`. Read `41-design-b-prime-detailed.md` only as a reference, for what Prime changes would add. Use targeted reads.

ZF (Z23, verbatim): "Tbh so far the differences feels artificial? Feels like we can easily arrive at a merged solution where most of the deterministic behaviour goes into hooking prime, ignore corner cases like login and fringe failure. Less deterministic stuff stays in repo?" This is a candidate: not golden, held to the same rigor, design unlocked (Z17).

**1. Write `docs/harness-program/51-design-merged.md`**, ZF's merged candidate. The first line must be exactly: `Runtime: stock Prime, no Prime changes; merged candidate (Z23)`
- **Deterministic behaviour goes into hooks on stock Prime v0.10.1:**
  - saving incoming messages;
  - fresh STATE each turn;
  - the stall wake;
  - compaction at the threshold;
  - the stale-action guard;
  - closing checks that can be computed.
- **Judgement work stays in repo files under the Z15 layout:** goals, rules, log entries, what counts as done, and reviews. That layout is the AGENTS.md role file, `STATE.md` with `## Goals`, `## Rules`, and `## Log` capped at 30, and `history/<UTC ts>-<slug>.md`.
- **Out of scope:** login/auth failures and rare failure modes, listed in one short **"Not handled"** section that says what happens today for each.
- Use the same 8 headings: 1 Overview; 2 Components and justification; 3 Hooks; 4 Prompts; 5 Artifact storage; 6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure); 7 Risks and notes; 8 Implementation plan.
- **Z21 vocabulary:** the baseline is only the Z15 artifacts plus existing pi-stack and Prime terms (stream, session, worker, tick, DCR, F-DCR, compaction, fork).
  - Any other concept gets a row in a **New concepts** table at the top: plain name | one-line meaning | corpus failure it fixes | why no existing artifact or term can carry it. Zero rows is the target.
  - Use plain words, with no coined labels, no two names that blur together, and no near-synonyms.
  - Hooks and prompts get descriptive names, not codes.
- **Exact hooks:** trigger, layer per 02-principles.md, I/O, code location naming the stock Prime extension point or command, and failure behaviour.
- **Exact full prompts**, with when each one fires.
- **Exact artifact paths and schemas**, with writer, reader, rotation and retention.
- Tie each component to a corpus failure class and its layer.
- Give a stacked commit plan with tests.
- No retired STREAM/ACTIONS/GOAL/DECISIONS names and no defaults.

**2. Rewrite `docs/harness-program/50-a-vs-b.md` as v2** (replacing v1 in place). Keep it short: a check of 51 against 31 and 42. It must cover:
- what the merge loses from 31, and what it loses from 42;
- which corpus failures are no longer covered (by F-number);
- where the A/B difference was real and where it was artificial, said honestly;
- open questions in plain words, with no defaults and no recommendation.

**Limits:** docs only. No code, no commit or push (Grok Bot collects), don't edit 31, 41 or 42, no other sessions, no credentials, never switch provider. On a quota error, stop and report.

Finish by replying exactly: `TRACK 5 STATUS: done (51 merged + 50 v2)` (or `TRACK 5 STATUS: blocked | <reason>`)

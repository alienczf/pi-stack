# Track 4 steer 4 (Grok Bot, 2026-10-23 15:03 SGT): Z23, stop the 41 rename, focus on 42

`03-decisions.md` now has Z23 and G29.

ZF (Z23, verbatim): "Tbh so far the differences feels artificial? Feels like we can easily arrive at a merged solution where most of the deterministic behaviour goes into hooking prime, ignore corner cases like login and fringe failure. Less deterministic stuff stays in repo?"

**Change of plan:**
- **Stop the Z21 rename pass on 41 now.** Keep whatever edits you've already made, but don't do any more. 41 is reference only.
- **Put your effort into `42-design-b-prime-unchanged.md` (steer 3).** It's now an input to a merged design, which will put deterministic behaviour into hooks on stock Prime and keep judgement work in repo files. So 42 must be exact about what stock Prime v0.10.1 hooks and commands can carry from outside. That means:
  - saving incoming messages;
  - fresh STATE each turn;
  - the stall wake;
  - compaction at the threshold;
  - the stale-action guard;
  - closing checks that can be computed.
- For each of these, give the extension point or command, the hook's I/O and failure behaviour, and what bypasses it.
- All the steer 3 requirements stand: first line, 8 headings, Z21 vocabulary and New concepts table, the gap table for the four gaps, the commit plan with tests, and no defaults.

Finish by replying exactly: `TRACK 4 STATUS: done (42 stock Prime; 41 reference only)` (or `TRACK 4 STATUS: blocked | <reason>`)

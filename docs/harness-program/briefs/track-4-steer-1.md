# Track 4 steer 1 (Grok Bot, 2026-10-23 11:55 SGT): Z19, add a detailed B-over-prime design

Keep going with your current work on `40-b-over-prime.md` as briefed. This adds a second artifact; it doesn't replace anything.

Read `03-decisions.md` section Z19 in the docs worktree (refreshed just now).

**After** 40-b-over-prime.md is complete, write `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/41-design-b-prime-detailed.md`: a detailed design for proposal B implemented over prime, built on your 40 findings (primitives that exist, gaps and what fills them). Don't commit it; Grok Bot collects. Track 3 is writing the matching design for proposal A in `31-design-a-detailed.md`; don't edit it.

**What the detailed design must specify exactly (Z19):**
- **Hooks:** for every hook, its trigger event, LAYER n, input and output, where the code lives (repo, path, function), and its failure behaviour (what happens when it errors, times out, or fires twice).
- **Prompts:** the full text of every injected or template prompt (resume, re-injection, intake acknowledgement, recovery, and so on), and exactly when each one fires.
- **Artifact storage:** paths, file formats and section schemas against the **Z15 layout**: one always-loaded `STATE.md` with `## Goals` (single mutable North Star plus current objective, rewritten in place), `## Rules` (rulings in force, rewritten in place, kept short), and `## Log` (append-only `### <ts> <subject>` entries, capped at 30), plus `history/` with one file per entry named `<UTC ts>-<slug>.md` (rotated log entries, retired rules as `<ts>-rule-retired-<slug>.md`, ZF steers via the Log). Every turn loads only AGENTS.md and STATE.md. If your design needs another section (for example `## Asks`) or file, name it, give its schema, and justify it against that rule. For each artifact: who writes it, who reads it and when, rotation and retention.
- **Important notes and risks.**
- **Justification for every component,** tied to a corpus failure class (F1-F12 and the core causes in 30-research-designs.md) and its LAYER per 02-principles.md, with why a stronger layer can't carry it.
- **Implementation plan** as stacked commits, each with its tests (a test that fails on the old code first where that applies).

**Use exactly these section headings,** so the A and B designs line up side by side:
1 Overview
2 Components and justification
3 Hooks
4 Prompts
5 Artifact storage
6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure)
7 Risks and notes
8 Implementation plan

The design is **not locked (Z17)**. This is input to the next iteration. Grok Bot will write `50-a-vs-b.md` from both detailed designs.

All track 4 hard limits still apply. Status line phases now: `inventory|mapping|prototype|feasibility-done|design-b-detailed|done|blocked|partial`, with `artifact=` naming 40 and 41.

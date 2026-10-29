# Track 3 steer 3 (Grok Bot, 2026-10-23 11:55 SGT): Z19, detailed design for proposal A

Read `03-decisions.md` sections Z15, Z16, Z17 and Z19 in the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/` (refreshed just now). Use targeted reads.

**ZF dropped proposal C, and the G24 A/C merge is withdrawn.** A stands on its own. Take parts of C into A only where A's design justifies them, and say so.

Write `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/31-design-a-detailed.md`: a detailed design and plan for **proposal A (repo-owned work and evidence)** from your `30-research-designs.md`, rewritten against the Z15 layout. Your 30 doc still uses the superseded STREAM/ACTIONS names; 31 must not. If A still needs per-ask records, decide whether they live in a STATE.md section or under history/ or elsewhere, and justify it. Don't commit; Grok Bot collects. Don't edit other files in the docs worktree (30 may get a one-line pointer to 31 at the top, nothing else). A new track 4 session is writing the matching B-over-prime design in `41-design-b-prime-detailed.md`; don't touch it or its session.

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

All track 3 hard limits from your brief still apply (artifact only, no code, no push, no other sessions, no credentials, never switch provider; on a quota error stop and report).

End with: `TRACK 3 STATUS: <design-a-detailed|done|blocked|partial> | artifact=docs/harness-program/31-design-a-detailed.md | next=<one line>`

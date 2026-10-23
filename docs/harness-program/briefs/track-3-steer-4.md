# Track 3 steer 4 (Grok Bot, 2026-10-23 15:00 SGT): Z20 design A over Prime, Z21 nomenclature cleanup

Read `03-decisions.md` sections Z15, Z17, Z19, Z20 and Z21 in the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/` (refreshed just now). Use targeted reads.

**Z20, ZF verbatim: "For A the ask is to design it over prime not pi".** Your current `31-design-a-detailed.md` designs A over pi-web/pi. That is the wrong runtime. The 13:25 A vs B comparison (`50-a-vs-b.md` v1) is superseded. A v2 comparison, A-over-Prime vs B-over-Prime, will be written from your rewrite.

**Task:** rewrite `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/31-design-a-detailed.md` (in place) for **proposal A** (obligations and evidence are owned by the stream repo, and the checked `STATE.md` is the authority) with **Prime as the runtime, not pi-web/pi**.
- For what Prime v0.10.1 supports and its extension points, read track 4's `40-b-over-prime.md` and `41-design-b-prime-detailed.md` in the same docs folder. Track 4's spike code is in `/home/alphalab/Projects/worktrees/pi-stack-b-over-prime` (branch `spike/b-over-prime`), and Prime's source is in `/home/alphalab/Projects/prime-agent`. Read only. Don't edit them.
- Every hook must name the Prime extension point it uses. Anything Prime lacks goes in a list of **native Prime changes**, each with what it needs and why.
- The first line of the file must be exactly: `Runtime: Prime (Z20)`

**Z21, ZF verbatim: "Clean up the nomenclature. We spent time to reduce the abstraction bloat and here you just created another set. Clean all of this up and really justify the need of a new concept".** Apply it in the same rewrite:
- **Baseline vocabulary:** only the Z15 artifacts (the AGENTS.md role file; `STATE.md` with `## Goals`, `## Rules`, `## Log` capped at 30 entries; `history/<UTC ts>-<slug>.md`), plus existing pi-stack and Prime terms (stream, session, worker, tick, DCR, F-DCR, compaction, fork).
- **Every other concept** is removed, merged into an existing artifact, or kept only with a row in a short **"New concepts" table near the top of the doc**, right after the Runtime line and the title. Columns: plain name | one-line meaning | corpus failure it fixes (F-number or core cause) | why no existing artifact or term can carry it. Aim for the fewest rows. Zero is best.
- Examples in your current 31 that must go through this test: the `## Asks` section, `sources/`, `evidence/`, `handover/`, generation, settlement, quiescence, disposition, receipts, and H-numbered hooks and P-numbered prompts used as names.
- Use plain words, not coined labels. No two names that blur together (Z14), and no near-synonyms for one thing. Hooks and prompts get descriptive names (for example "save-incoming-message hook"), not codes.
- Track 4 is cleaning up 41 under the same rule at the same time. Use the baseline vocabulary and plain English, so A and B share one vocabulary and the comparison lines up. Don't touch 40, 41, 50 or track 4's session.

**Keep (Z19):** the same 8 headings (1 Overview; 2 Components and justification; 3 Hooks; 4 Prompts; 5 Artifact storage; 6 Lifecycle walkthrough (an ask from intake to close, a stall, a failure); 7 Risks and notes; 8 Implementation plan).
- **Hooks:** each with its trigger, LAYER n (per 02-principles.md), input and output, code location (repo, path, function, Prime extension point), and failure behaviour (errors, timeouts, firing twice).
- **Prompts:** the exact full text of each one, and when it fires.
- **Artifacts:** exact paths and schemas against Z15, with writer, reader, rotation and retention.
- **Components:** each justified by a corpus failure class and its layer, with why a stronger layer can't carry it.
- **Implementation plan:** stacked commits, each with its tests.
- No retired STREAM/ACTIONS/GOAL/DECISIONS names. No defaults locked (Z17). Open questions stay questions.

**Limits:** artifact only, no code, no commit or push (Grok Bot collects), don't edit other docs, no other sessions, no credentials, never switch provider. On a quota error, stop and report.

Finish by replying exactly: `TRACK 3 STATUS: done (A over Prime)` (or `TRACK 3 STATUS: blocked | <reason>`)

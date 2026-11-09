# Track 4 steer 2 (Grok Bot, 2026-10-23 15:00 SGT): Z21 nomenclature cleanup for 41 (and 40 where cited)

Read `03-decisions.md` sections Z15, Z17, Z20 and Z21 in `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/` (refreshed just now). Use targeted reads.

**Z21, ZF verbatim: "Clean up the nomenclature. We spent time to reduce the abstraction bloat and here you just created another set. Clean all of this up and really justify the need of a new concept".**

**Task:** revise `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/41-design-b-prime-detailed.md` in place. Also revise `40-b-over-prime.md` wherever 41 cites its terms, so the two agree.
- **Baseline vocabulary:** only the Z15 artifacts (the AGENTS.md role file; `STATE.md` with `## Goals`, `## Rules`, `## Log` capped at 30 entries; `history/<UTC ts>-<slug>.md`), plus existing pi-stack and Prime terms (stream, session, worker, tick, DCR, F-DCR, compaction, fork). Prime's own source names may be cited as code locations, but they are not design vocabulary.
- **Every other concept** is removed, merged into an existing artifact, or kept only with a row in a short **"New concepts" table near the top of 41**, right after the title. Columns: plain name | one-line meaning | corpus failure it fixes (F-number or core cause) | why no existing artifact or term can carry it. Aim for the fewest rows. Zero is best.
- Examples in the current 41 that must go through this test: facts journal / InputFact, owner epoch / generation, adoption, maintenance records, settlement, quiescence, disposition, projection/view, receipts, and H-numbered hooks and P-numbered prompts used as names.
- Use plain words, not coined labels. No two names that blur together (Z14), and no near-synonyms for one thing. Hooks and prompts get descriptive names (for example "save-incoming-message hook"), not codes.
- Z20: track 3 is rewriting design A over Prime (`31-design-a-detailed.md`) under the same rule at the same time. Use the baseline vocabulary and plain English, so A and B share one vocabulary and the v2 comparison lines up. Don't touch 31, 50 or other sessions.

**Keep:** the same 8 Z19 headings, exact hooks (trigger, layer, I/O, code location, failure behaviour), exact full prompts, exact artifact paths and schemas against Z15, per-component justification, and the stacked commit plan with tests. No retired STREAM/ACTIONS/GOAL/DECISIONS names. No defaults locked (Z17). Open questions stay questions.

**Limits:** docs only. No new spike code, and no commit or push in the docs worktree (Grok Bot collects). No credentials, never switch provider. On a quota error, stop and report.

Finish by replying exactly: `TRACK 4 STATUS: done (naming cleanup)` (or `TRACK 4 STATUS: blocked | <reason>`)

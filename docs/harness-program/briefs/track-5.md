/skill:poteto-mode

# Harness program, track 5: A vs B side-by-side comparison (Z19)

This is the /poteto entry point, loaded as the poteto-mode skill. Work in poteto style throughout. Brief written by Grok Bot, 2026-10-23 12:55 SGT (Z19).

**Goal.** Write `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/50-a-vs-b.md`: a neutral side-by-side comparison of the two detailed designs, for ZF to read. **The design is not locked (Z17).** Don't recommend, choose, or apply defaults. Present open questions as questions.

## Inputs (docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/`; targeted reads with rg and line ranges)
- `31-design-a-detailed.md`: proposal A, repo-owned work and evidence (track 3).
- `41-design-b-prime-detailed.md`: proposal B, runtime-owned obligations and hooks, over prime (track 4), plus `40-b-over-prime.md` (feasibility verdict, evidence, effort). Spike branch `spike/b-over-prime@8811a7a` (read-only).
- `30-research-designs.md` for the corpus failure classes F1-F12 and the core causes; `02-principles.md` for the layer rule; `03-decisions.md` Z15, Z17, Z19 for the STATE.md layout and framing. C is dropped.
Both designs use the same 8 headings (Overview, Components and justification, Hooks, Prompts, Artifact storage, Lifecycle walkthrough, Risks and notes, Implementation plan). Line them up on those.

## 50-a-vs-b.md must contain, in this order
1. **Core difference:** one short paragraph in plain words (who owns obligations and evidence, where the authority lives, what that changes in practice).
2. **Side-by-side per component:** tables with columns `Component | A | B | Note`, one row per hook, prompt, artifact (path and schema), and lifecycle step (intake, dispatch, stall, failure/park, F-DCR, close, compaction, adoption). Where one design has a component the other lacks, say "none" and what covers that need instead. Cite section or line refs in each design.
3. **Pros and cons table** for A and for B.
4. **Effort and risk:** commits, new code surface, dependencies (B on prime and its gaps from 40), what is verified vs unverified, migration cost from the current Z15 layout.
5. **Corpus coverage:** table of F1-F12 and the core causes, with covered / partial / missed for each design and the mechanism and LAYER that covers it.
6. **Open questions:** numbered questions for ZF's next iteration, with no default answers and no recommendation. Include genuinely blocking ones and mark them as blocking.
Use plain names. Don't use the retired STREAM or ACTIONS file names except to note they don't exist. Every claim must trace to 31, 40, 41 or 30; if the designs disagree on a fact (for example what pi-web or prime can do), say so instead of resolving it silently.

## Hard limits
- Write only `50-a-vs-b.md` in the docs worktree. Don't commit, push, merge, or touch other files, sessions, or branches. Grok Bot collects it.
- No code, no credentials, never switch provider; on a quota or usage-limit error, stop and report.
- When done, end your final message with exactly one line:
  `TRACK 5 STATUS: done | artifact=docs/harness-program/50-a-vs-b.md`
  (or `TRACK 5 STATUS: blocked | reason=...`).

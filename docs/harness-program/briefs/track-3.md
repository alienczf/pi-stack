/skill:poteto-mode

# Harness program, track 3: problem-state research and three competing designs

This is the /poteto entry point, loaded as the poteto-mode skill. Work in poteto style throughout.

**Your artifact:** `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/30-research-designs.md`. Write that one file. If the merged corpus gets big you may also write `30a-external-corpus.md`, which holds links and short quotes but no data dumps. **Artifact only, no code changes.** Don't commit; Grok Bot collects. The end state is a **three-design proposal table that ZF can read**.

ZF found the deep-research build plan (one control record, inbox/outbox, ask ledger, and so on) "too frameworky": it won't generalise across workflows. This track steps back to the problem state. Run the steps in this order:

**(a) Problem statements.** Collect every item left unsure or unresolved. Sources: the corpus, interrogations A/B/C (their open questions), the deep research's "does not settle" sections, ZF's decision answers 2, 4 and 6 (now G5, D7 and D9), and anything track 1 defers. Track 1's catalog is being written in parallel at `docs/harness-program/10-pi-streams-fix-catalog.md`; read its "Deferred to track 3" section when it appears, and re-check before you finish. Write each item as a problem statement with an id and source, not as a solution.

**(b) Light scout of pi-stack's own structure and principles.** Don't go too deep. Start at the single poteto-mode entry point (`~/.pi-stack/.plugins/pstack/skills/poteto-mode/SKILL.md` and its Principles index), then trace the spectrum. Principles (abstract, light) sit at one end, and playbooks (very detailed) at the other. Skills, prompts, overlay and AGENTS.md sit in between. Say what works, what doesn't, and why, citing the corpus where a principle or playbook was ignored, followed, or over-followed. Workflow nomenclature may stay, but review what actually works.

**(c) External corpus of real, non-hype failure modes.** These are practitioners complaining that their agent workflows or inner loops break: memory, workflows, long-running agents, goal drift, compaction, orchestration, steering and queued messages, and stalls. Sources: X, HN, GitHub issues of agent harnesses (Claude Code, Codex CLI, OpenHands, Aider, Cline, Cursor, LangGraph, Goose, Roo, and so on), Reddit and blogs. Exclude influencer hype and vendor marketing. Each item gets a link, a one-line failure, and a tag. **Grok Bot has seeded this from X** (X isn't reachable from this host) in `docs/harness-program/31-x-corpus-seed.md`, in the docs worktree and also at `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/context/harness-program/31-x-corpus-seed.md`. Merge it, de-duplicate it, and drop anything that is hype. If you can't reach a source from the host, note that in the artifact. Use subagents on the same model for parallel source sweeps if that helps.

**(d) Merge and interrogate.** Merge the internal corpus (75 rows, F1–F12) with the external one. Then /interrogate them together to find the **few core high-level causes**, about 3–6. Do this before designing anything, and show which corpus items support each cause.

**(e) Three competing holistic designs.** Each one gets:
- its core idea, and why it will work against the core causes
- the mechanisms, each with **LAYER n** per `02-principles.md` and the reason it sits at that layer
- what it asks of the repo (layer 1) and CI (layer 2), and how layers 3–5 *produce* those changes deterministically across repos
- the failure modes it doesn't fix
Make the designs genuinely different, for example code- and repo-shape-first, harness-hooks-first, and principles-plus-playbooks-first. **Penalise frameworky designs** that need per-workflow configuration or a general engine. Respect D1 (no default budgets), D6, D7, D8, D9, G4 and G5.

**(f) For ZF.** Write a pros/cons comparison table across the three designs, a coverage matrix (problem statements × designs: covered, partly, not), and a recommendation with the single biggest risk of each design. Put the table near the top so ZF can read it first.

Also add a short **Decisions** section of calls you made, each with a reason. Expect about 2–4 hours.

## Common rules (all three harness-program tracks)

You are one of three parallel sessions in ZF's **harness program** for pi-stack, started 2026-10-23 by Grok Bot. Grok Bot owns every decision in this program. Make your own calls, log each one in your artifact's "Decisions" section with a short reason, and don't wait on ZF.

**Read first, in full:**
- `docs/harness-program/00-brief-verbatim.md`, ZF's brief. A ~4.5k-character gap in it is marked; don't guess at its content.
- `docs/harness-program/01-scope.md`, the three tracks and how they're ordered.
- `docs/harness-program/02-principles.md`, layer affinity. Every mechanism you propose gets `LAYER n` plus a reason.
- `docs/harness-program/03-decisions.md`, D1–D9, P1–P7 and G1–G12.

These files are in the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program` (branch `docs/harness-program`). A copy is in `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/context/harness-program/`.

**Evidence base** (all under `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`):
- `context/stall-corpus-2026-10-22.md`: 75 ZF steering rows, F1–F12
- `context/interrogations/A-mechanical-2026-10-22.md`, `B-goal-integrity-2026-10-22.md`, `C-control-loop-2026-10-22.md`
- `context/research/deep-research-2026-10-23.md`
- `context/updates/2026-10-22-1743-sgt/issue-3{3,4,5,6}.json`, the pi-stack issues #33–#36. `gh` may be unauthenticated on this host, so use these snapshots.
- `DECISIONS.md` and `context/zf-brief.md`
- the pi-stack source in your cwd `/home/alphalab/Projects/pi-stack/pi-stack` (main @ 3acf0f0), mainly `pi-streams/`, `overlay/`, `skills/`, `prompts/`, `docs/design/`. The installed copy is `~/.pi-stack`.
- live stream repos under `/home/alphalab/Projects/alphalab/streams/` and `/home/alphalab/Projects/pi-stack/streams/`, read-only. Sample big files (the 654 STATE.md is 10 MB) with head, grep and wc. Never cat them whole.

**Hard limits:**
- Don't prompt, steer, stop, rotate, archive or spawn any *other* existing session or stream. That covers the pi-streams-harness coordinator and the prime-stack coordinator `01a16177-96a3-7923-bfe9-55fbc3774482`. Run only `pi-streams status`/`doctor` against streams. You may use your own subagents on the same model (openai-codex/gpt-6.1-sol).
- Don't push to GitHub, open PRs, or comment on issues. Grok Bot is the only pusher. Commit locally on your own branch only where your track says so.
- Touch no auth or credentials, and never print tokens or secrets.
- On a usage limit or quota error, **stop and report** in your final message. Never switch provider or model.
- No default budgets or caps (D1). Git holds code, docs and small reports, never data.
- Only edit the files your track names. Leave everything else in the docs worktree alone, because the other tracks share it.

**Status line.** When you finish (or stop), end your final reply with one line:
`TRACK <n> STATUS: <done|blocked|partial> | artifact=<path> | next=<one line>`
Grok Bot reads that line and updates `docs/harness-program/STATUS.md`. Don't edit STATUS.md yourself.

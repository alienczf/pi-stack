/skill:poteto-mode

# Harness program, track 1: the pi-streams must-fix catalog

This is the /poteto entry point, loaded as the poteto-mode skill. Work in poteto style throughout.

**Your artifact:** `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/10-pi-streams-fix-catalog.md`. Write that one file and no others. **Artifact only, no code changes.** Don't implement anything.

**Who reads it:** this catalog is the ONLY thing ZF reviews in the program. It's his first-pass review. After his go-ahead the fixes are implemented, merged to pi-stack main, and every branch is rebased onto the new main. So write it to be reviewable in one sitting.

## What to catalog

Catalog every obvious or must-fix change to **pi-streams itself** (pi-stack `pi-streams/`, its templates, the stream and stream-kickoff skills, and the systemd tick). An item makes the bar only if it has a low blast radius, or if it must change no matter what. Draw on the corpus, interrogations A, B and C, the deep research and #33–#36. It must include, at minimum:
- Fix the tick's continuation and liveness, so ZF stops being the clock (F1, C rank 1).
- Fix the circular recovery: the tick waits for a successful reply before it lets the probe prompt through (C rank 2). Use G5 as decided: same-provider auto-recovery for all five classes (usage limit, expired Codex login, tool login expiry, full disk, other model errors), with its cross-cutting rules. It replaces stop-and-report as the harness default, so it is not a ZF call.
- Impose the coordinator compaction boundary in the harness at 252k, as a request-boundary check with no defensive user check (D2, G4). Use the least-machinery mechanism that really fires on the coordinator's path, including direct prompts. State whether it needs a native pi hook.
- Remove the numeric-caps kickoff question and every default budget or guard seeded by templates (D1).
- Fix the evidence-path bug at the archive boundary (#37, A).
- Make STATE a current view rather than an append log. History moves out. Covers the 10 MB 654 STATE.md.
- Acknowledge steer delivery: "accepted for transport" must not count as delivered.
- Fix stale coordinator ids in the tick and registry.
- Make `pi-web-cli-remote` / `options-01-ssh --ensure-tg` stop restarting Twingate on every call, because that causes SSH banner timeouts (G15). It is a Grok Bot box tool, so state the right repo or layer, or move it out of scope with a reason.
- Add anything else in the evidence that clears the bar, such as kickoff template defaults that override goals or stops, rotation mid-turn, and the D7 compaction/review trigger for STATE, DECISIONS, TODO and the rules, if it can be small.

**Out of scope, sent to track 3:** anything frameworky or speculative, or that needs a new subsystem. Examples are a general control record or engine, ask ledgers beyond a minimal form, workflow definitions (D9) and reviewer policy. List these in a short "Deferred to track 3" section, each with a one-line problem statement.

## Shape of the artifact

1. **Review table first**, readable in one sitting. Columns: `#`, fix (one line), symptom with corpus rows, LAYER (1–5, per 02-principles), blast radius (files/behaviour touched; low/med/high), ZF-call? (no, or the question plus **recommended default**), and order.
2. **Per-item detail** under the table: symptom and corpus rows (cite row ids); root cause with file:line in pi-stack @ 3acf0f0; the fix; its LAYER, why that layer is right, and why a stronger layer can't carry it; blast radius; verification (a test or a real-stream check that reproduces on 3acf0f0 and passes after); dependencies.
3. **Needs a ZF call**, kept separate, each with a recommended default. Under P7, Grok Bot will take your default unless it's wrong. Keep this list short, because principle "impose and measure, don't defend" applies.
4. **Deferred to track 3**, as above.
5. **Stacked implementation plan**, ready to run: an ordered list of small commits (title, files, test), grouped into PR-sized stacks on top of main 3acf0f0, and how each is verified on a real disposable stream on options-01.
6. **Decisions** that you made, each with a reason.

Use /interrogate (or /why) on your own catalog before you finish, to check each item's layer placement and that it really clears the bar. Expect about 60–120 minutes. Don't commit; Grok Bot collects the file.

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

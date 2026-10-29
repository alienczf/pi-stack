Steer from Grok Bot, 2026-10-23 10:10 SGT. ZF has redefined your deliverable (t214u, recorded as Z12 in `docs/harness-program/03-decisions.md`; his paraphrased words are in `00b-zf-messages-verbatim.md` section t214u). Where this differs from your brief or steer 1, this wins. Keep what you have already gathered; don't restart.

Paths: S = /home/alphalab/Projects/pi-stack/streams/pi-streams-harness, D = /home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program.

**Five inputs:**
1. **Local failure corpus.** `S/context/stall-corpus-2026-10-22.md`, plus the interrogation outputs `S/context/interrogations/A-mechanical-2026-10-22.md`, `B-goal-integrity-2026-10-22.md`, `C-control-loop-2026-10-22.md`.
2. **ZF's human-provided remedies Z1–Z11** in `D/03-decisions.md` (G5 and G17 are the Grok Bot calls that shape them), with his words in `D/00b-zf-messages-verbatim.md` (t208u–t213u). These are candidates to evaluate, not requirements. Give them the same rigor as everything else.
3. **The balance.** Derive it explicitly as a table: each corpus failure class (from input 1) → the ZF remedy that covers it, or **none**. The "none" rows are what the design has to handle beyond ZF's remedies.
4. **Internet failure corpus and deep research.** `D/31-x-corpus-seed.md` plus whatever you have already gathered (`D/30a-external-corpus.md`), and `S/context/research/deep-research-2026-10-23.md`. ZF found the deep research too frameworky: use its evidence, not its framework.
5. **pi-stack's guiding principles.** The poteto-mode entry point `~/.pi/agent/skills-pstack/poteto-mode/SKILL.md` (its Principles section and `playbooks/`), the principle-* skills in `~/.pi-stack/.plugins/pstack/skills/principle-*/SKILL.md`, and the layer rule in `D/02-principles.md`.

**Deliverable:** `D/30-research-designs.md` with three competing proposals. Each one:
- is justified against the core causes and the layers (02-principles.md order);
- says which ZF remedies (Z1–Z11) it adopts, modifies or rejects, and why;
- shows the coverage table from input 3, with this proposal's handling of every "none" row.

End the doc with a pros/cons table across the three, and a short **"Blocking decisions for ZF"** list: only real forks that change the design, each with a recommended default. The per-ask lifecycle (Z2) remains your job, inside the proposals.

Context: track 1 keeps implementing Z1–Z11 as the MVP and is not waiting for you (G18). Where you reach a verdict on a Z remedy, state it in one line per Z so it can be attached to the track 1 review. When done, end with `TRACK 3 STATUS: <phase> | artifact=<path> | next=<...>`.

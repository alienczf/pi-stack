# Track 1 implementation progress

## Contract and resume point

GO at 2026-10-23 11:35 SGT authorizes implementation. Z15 wins over earlier artifact layouts. Source base is pi-stack 3acf0f01e6084a317b89cef3a86f4781e60877cf. Code worktree will be /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix on feat/streams-must-fix. Docs stay uncommitted for Grok Bot.

Resume here after compaction, not from the old catalog summary. No implementation commit exists yet. Next action is finish the catalog/artifact-map amendment, validate it, then create the specified code worktree.

## Designed workflow

- [x] Read the Principles section of poteto-mode.
- [x] Phase A: Frame. Done means S1, S2, S2a, S3, S4, S5, S6 committed locally with a parent-red regression and green/full-suite evidence per commit, plus isolated disposable checks and an F-DCR round trip. Partial or blocked verification is not completion.
- [ ] Phase B: Design the workflow. Amend the catalog and artifact tiers for Z13-Z15. Pin the pi-web source. Keep one writer per code worktree. The existing approved boundaries are the implementation contract.
- [ ] Phase C: Run the loop. Each catalog commit starts with its regression on the parent, then the smallest fix, focused green, full offline suite, diff review, and local commit with evidence.
- [ ] S1. State layout and safe persistence/staging; code before templates.
- [ ] S2. Identity, evidence, applied receipts, receiver stop safety and safe replacement.
- [ ] S2a. Lossless explicit stream-root migration, once, without worker writes.
- [ ] S3. Fixed same-session DCR and receiving-side maintenance support.
- [ ] S4. Cause-independent driven-stall goal reinjection.
- [ ] S5. Usage-reset retry and quiet off-host alert contract.
- [ ] S6. Human-ratified failure parking and exact-point F-DCR, then singular original retirement.
- [ ] Phase D: Keep the audit trail. Add one row per commit here and record red/green evidence in its body.
- [ ] Phase E: Verify and hand back. Check the integrated result, exact branch heads, pending companion patches and isolated F-DCR evidence. No push, PR, merge or other-branch rebase.

## Throughput and isolation

This is a high-rigor cross-repository change with destructive recovery semantics. The unit is one small catalog commit, verified before the next. External prerequisite E is Grok Bot's and is skipped here. The main checkout, live pi-web port 8504, production tick, ~/.pi-stack, ~/.local/bin, existing streams/sessions and credentials are not mutation targets. Disposable instances require their own port, XDG_CONFIG_HOME, XDG_DATA_HOME, XDG_STATE_HOME, index and streams root. Auth may be read in place only, never copied or printed. If isolated verification needs copied credentials or login, stop that check and report it.

## Amendments

Pending. Final layout is only AGENTS.md plus STATE.md every turn. STATE has Goals, Rules, Log, tolerates an extra level-two section before Log, and only Log rotates at 30 entries. Invented files/data directories are out of scope. Fix 17 is removed.

## Source pins and companion changes

- pi-stack base: 3acf0f01e6084a317b89cef3a86f4781e60877cf.
- pi-web source: discovery pending. Installed dist is read-only and is not a source checkout.
- Bot deployment: locate source without guessing. If unavailable on options-01, store exact companion patch files in this progress folder and record them here.

## Commit evidence

| Stack | Title | SHA | Parent red test | Focused green | Full offline suite | Disposable check |
|---|---|---|---|---|---|---|

## Current limitations

No code, test, disposable instance or live recovery has run for this implementation phase. The earlier catalog's reviews and source-only probes are not implementation evidence.

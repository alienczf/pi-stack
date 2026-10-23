# Track 1 implementation progress

## Contract and resume point

GO at 2026-10-23 11:35 SGT authorizes implementation. Z15 wins over earlier artifact layouts. Source base is pi-stack 3acf0f01e6084a317b89cef3a86f4781e60877cf. Code worktree is /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix on feat/streams-must-fix, verified at the exact base with no implementation commits. Docs stay uncommitted for Grok Bot.

Resume here after compaction, not from the old catalog summary. Catalog/artifact-map amendments and the untouched 105-test baseline are checked. The exact named branch/worktree exists at base 3acf0f01e6084a317b89cef3a86f4781e60877cf. No implementation commit exists. The writer returns the required docs/baseline checkpoint because no subagent_supervisor tool is available. Next action after parent acknowledgement is pin matching pi-web source, then write/run the first S1 regression on this parent before implementation. Do not interpret this checkpoint as completed S1 or S1-S6.

## Designed workflow

- [x] Read the Principles section of poteto-mode.
- [x] Phase A: Frame. Done means S1, S2, S2a, S3, S4, S5, S6 committed locally with a parent-red regression and green/full-suite evidence per commit, plus isolated disposable checks and an F-DCR round trip. Partial or blocked verification is not completion.
- [ ] Phase B: Design the workflow. Catalog and artifact tiers amended for Z13-Z15 and validated. Pi-web source pin remains pending. Keep one writer per code worktree. The approved boundaries remain the implementation contract.
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

Completed in 10-pi-streams-fix-catalog.md and 11-artifact-map.md on 2026-10-23. Both now have identical 14-row tier/name tables. Every turn reads only AGENTS.md and STATE.md. Goals contains explicit North Star, Current objective, Charter, and a first-line ratified authority marker. The one resolver falls back from current objective to North Star. Goals/Rules rewrite in place. Only Log is append-only and tick-rotated beyond 30. Header parsing preserves an extra section between Rules and Log without implementing Asks.

Items 6, 10, 12, and 16, DCR/reinjection/pickup/protection/kickoff references, commit titles, and Decisions now follow Z15. New rulings update Rules and Log; retired exact rule text goes to rule-retired history; ZF steers enter Log at arrival. Stream TODO/PLAN planning is disabled in favor of Goals plus Log. Non-stream behavior stays unchanged. S2a maps STREAM into Goals/active Rules/history, DECISIONS into active Rules/history, and old STATE into history before fresh STATE. It preserves raw source bytes/provenance and failure markers, refuses ambiguous authority, and commits once per selected disposable stream without worker writes or live lifecycle actions.

Fix 17 and the S1 bulk-output inventory commit are removed. Invented files, TODO/PLAN, ad-hoc log/analysis, and existing context contents are not migration/ownership targets. Stable IDs are 1-16 and 18. Current count is 17, with 11 mechanical and 6 artifact fixes. Earlier 18-item review verdicts are explicitly historical, not approval of this amendment. S1,S2,S2a,S3,S4,S5,S6 ordering and all other safety boundaries remain.

Validation passed for row/detail identity, the 11+6 partition, seven detail fields per item, identical tiers, explicit goal shape, required stack order, stale active-policy exclusions, Z1-Z11/O1-O4 coverage, balanced fences, final newlines, and trailing whitespace. The first one-off validator incorrectly split on the fenced Log example and failed at item 6 Layer. Restricting detail boundaries to numbered headings corrected that validator. No product regression or implementation red/green is claimed.

## Source pins and companion changes

- pi-stack base and current feat/streams-must-fix head: 3acf0f01e6084a317b89cef3a86f4781e60877cf. Worktree created with the exact authorized command. TODO.md and PLAN.md are untracked process artifacts, not commit content. Main remains clean.
- pi-web source: discovery pending. Installed dist is read-only and is not a source checkout.
- Bot deployment: locate source without guessing. If unavailable on options-01, store exact companion patch files in this progress folder and record them here.

## Commit evidence

| Stack | Title | SHA | Parent red test | Focused green | Full offline suite | Disposable check |
|---|---|---|---|---|---|---|

## Docs and baseline checkpoint evidence

- Model verified from PI_PROVIDER and PI_MODEL as openai-codex/gpt-6.1-sol. No model call or switch was made for verification.
- Catalog SHA-256 is abb68471f7319b1fdae46c0183074f9a05c679b656f8fc66bcb47bbf991559f5. Artifact-map SHA-256 is 35128839d73e2dd73e2a6a604d91e5d7ac2968d0c2e518acd4d5273980be48a1.
- Structural Python assertions pass for the amended docs as described above. A failed initial validator was corrected without treating it as a product regression.
- Baseline command was `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests` in the exact-base code worktree, with HOME and all three XDG variables set under `/tmp/pi-streams-track1-baseline.NwE2UY`. Result was 105 tests, OK, exit 0. Retained output is `/tmp/pi-streams-track1-baseline.NwE2UY/unittest.log`. Existing subprocess fixtures use private homes/stub pi-web. No live pi-web/session was contacted.
- Additional checks passed under the same private environment. `bash -n install.sh`, `bash scripts/check-cross-repo.sh`, `PI_STACK_SMOKE=0 bash scripts/check-subagents.sh`, and `python3 scripts/check-readme-commands.py`. The last command validated/extracted the README block without executing it. Installed/live subagent discovery and smoke were not run.
- `check-overlay.sh`, `check-conform-skills.sh`, and `check-update-pstack.sh` were read but not executed at this baseline-only reporting checkpoint. Run the applicable full repository checks with implementation changes. No full README-command execution is claimed.
- `git diff --check` passed in main, code, and docs worktrees. The separate Python assertions also checked trailing whitespace/fences in both untracked amended docs, which Git diff alone cannot cover.
- Main status was empty. Main, code, and docs indexes were all empty. No commit, stage, push, PR, merge, rebase, credential operation, Slack send, production service operation, or existing-stream/session mutation occurred.
- Red regression command/result is not run. Focused implementation-green command/result is not run. Baseline success is not implementation red/green evidence. Disposable runtime result is pending/not run.

TRACK 1 STATUS: implementing | stack=S1 | commit=3acf0f0 baseline-only (no implementation commit) | red=no green=no suite=pass | disposable=pending

Progress-file update is complete for this checkpoint. The supervisor tool is unavailable, so the writer returns normally for parent acknowledgement before implementation continues.

## Current limitations

S1-S6 are unimplemented. No implementation regression or disposable runtime/F-DCR round trip has run. Pi-web matching source and bot adapter ownership are still pending discovery, not proven unavailable. There are no companion patches or pi-web branch/head yet. Earlier catalog reviews are historical, and no independent review of this Z15 amendment is claimed. The parent remains the reporting/review owner. This is a required reporting checkpoint, not a product-decision gate or a completion claim.

# Track 1 implementation progress

## Contract and resume point

GO at 2026-10-23 11:35 SGT authorizes implementation. Z15 wins over earlier artifact layouts. Source base is pi-stack 3acf0f01e6084a317b89cef3a86f4781e60877cf. Code worktree is /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix on feat/streams-must-fix. Its current head is 1ce95048c30f51d38e62c5165e3e1261363dd1f5, the first S1 implementation commit. Docs stay uncommitted for Grok Bot.

Resume here after compaction, not from the old catalog summary. Parent acknowledged the docs/105-test baseline checkpoint and supplied the matching pi-web tag. Source pin/compatibility is now verified. Exactly one implementation commit is complete, `streams: publish snapshots and scope automatic commits`, at 1ce95048c30f51d38e62c5165e3e1261363dd1f5. Its immediate parent red, focused green, and full offline suite are recorded below. No subagent_supervisor tool is available, so this continuation returns the required one-commit checkpoint. After parent acknowledgement, the next commit is `streams: parse STATE Goals and update the current objective only`, with its new regression first on parent 1ce9504. S1 and S1-S6 are not complete.

## Designed workflow

- [x] Read the Principles section of poteto-mode.
- [x] Phase A: Frame. Done means S1, S2, S2a, S3, S4, S5, S6 committed locally with a parent-red regression and green/full-suite evidence per commit, plus isolated disposable checks and an F-DCR round trip. Partial or blocked verification is not completion.
- [x] Phase B: Design the workflow. Catalog/artifact tiers and baseline checked; matching pi-web source pinned and compatibility verified. One writer owns each isolated checkout. The approved boundaries remain the implementation contract.
- [ ] Phase C: Run the loop. Each catalog commit starts with its regression on the parent, then the smallest fix, focused green, full offline suite, diff review, and local commit with evidence.
- [ ] S1. First of five catalog commits complete for snapshots/scoped staging. STATE parsing, Log/rule operations, templates/defaults, and full-SID handovers remain.
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

- pi-stack base: 3acf0f01e6084a317b89cef3a86f4781e60877cf. Current feat/streams-must-fix head: 1ce95048c30f51d38e62c5165e3e1261363dd1f5. Only the exact authorized worktree received source/test/commit writes. TODO.md and PLAN.md remain untracked process artifacts. Main remains clean at the base.
- pi-web source: https://github.com/jmfederico/pi-web.git tag v1.202607.3 at 9b8728a5d626dbc69e321e563b970d44f4000a68. Checkout is /home/alphalab/Projects/worktrees/pi-web-streams-must-fix on local feat/streams-must-fix, clean at that revision with no source edits or commits. Clone used GIT_TERMINAL_PROMPT=0 and an empty credential helper. No npm install or runtime provisioning was needed for this unit.
- Compatibility: source and installed package.json are identical, version 1.202607.3. Installed maps for piSessionService, sessionCommandService, sessionRoutes, and sessionArchiveStore point to the matching source paths. Every mapped source line/column is valid, and maximum mapped lines match the tagged files exactly at 4184, 377, 675, and 297. Maps omit sourcesContent, so an initial embedded-source comparison failed with KeyError and was replaced by the supported path/position check. This is source-map/package compatibility, not a reproducible-build byte comparison. Installed files remained read-only.
- Bot deployment: locate source without guessing. If unavailable on options-01, store exact companion patch files in this progress folder and record them here.

## Commit evidence

| Stack | Title | SHA | Parent red test | Focused green | Full offline suite | Disposable check |
|---|---|---|---|---|---|---|
| S1, commit 1 of 5 | streams: publish snapshots and scope automatic commits | 1ce95048c30f51d38e62c5165e3e1261363dd1f5 | `python3 -m unittest discover -s pi-streams/tests -p test_persistence_git.py -v` on unchanged parent 3acf0f0, exit 1. 11 tests, 21 failures and 1 unsupported-API error. | Same command, final 16 tests OK, exit 0. Focused close suite also 3 tests OK. | `python3 -m unittest discover -s pi-streams/tests`, final 121 tests OK, exit 0. | Pending. S1 stack incomplete. No real pi-web/model task effects or F-DCR check yet. |

## Historical docs and baseline checkpoint evidence

This checkpoint was acknowledged by the parent before the implementation continuation. The statements below describe that baseline-only point, not the current commit count.

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

## S1 first-commit checkpoint

The 11-test regression module was written and run before production-source edits on immediate parent 3acf0f0. Actual failures included truncated snapshots, missing registration repair, captured binaries/data/foreign staged content, and changed caller index after a failed commit. An initial identity-error injection assumed Git rejects empty email, which it did not. The test was corrected to inject a Git commit failure and rerun red on the unchanged parent. The retained authoritative parent output is `/tmp/pi-streams-s1-persistence.DgBVyC/red-final.log`.

Implementation changes are limited to engine/project.py, engine/threads.py, engine/cli.py, and tests/test_persistence_git.py. Existing snapshot writers now share unique same-directory temporary files, file sync, atomic replace, and directory sync. Create retry idempotently repairs its row without overwriting owned documents. Automatic commits use exact known/approved paths, private indexes, real-index exclusion, binary/path validation, staged-overlap refusal, and an expected-parent ref update. `close` explicitly supplies only its validated handover paths rather than staging a directory. No default budgets/caps or STATE-layout change entered this commit.

An initial full suite ran 116 tests and exposed one close-handover caller failure. It was corrected without weakening that test. Additional edge cases cover lock ownership, outside symlinks, initial seeding, explicit approvals, rename source/destination reconciliation, and a ref-published/index-unconfirmed result. Final focused output is `/tmp/pi-streams-s1-persistence.DgBVyC/green-final.log` with 16 tests OK. Final full output is `/tmp/pi-streams-s1-persistence.DgBVyC/full-suite-final.log` with 121 tests OK. All commands used PYTHONDONTWRITEBYTECODE=1 and private verification homes. These are actual parent-red and candidate-green results, not the earlier 105-test baseline.

All applicable repository check scripts passed. `bash -n install.sh`, `check-cross-repo.sh`, `check-subagents.sh` with smoke disabled/private HOME, `check-update-pstack.sh`, and `check-conform-skills.sh` are retained in repository-checks-final.log. The isolated `check-overlay.sh` output is overlay-check.log. That installer fixture unsets XDG_CONFIG_HOME so its per-HOME assumptions use only private HOME-derived .config paths; XDG_DATA_HOME/XDG_STATE_HOME remain private, PATH is /usr/bin:/bin, and service/package actions are stubbed. README command extraction and git diff whitespace checks also passed. No nested Pi/subagent or live model call occurred.

The final source diff was manually reviewed and cleaned before committing. Rename detection was disabled for path enumeration so both sides reconcile correctly. No deslop/control-cli leaf skill is installed in the available skill directories, so no formal skill run is claimed. No child review was launched. The parent owns the required review gate.

Automatic engine commits use commit-tree and an expected-old ref update, so they do not run arbitrary repository commit hooks. That is a deliberate safety choice for this bounded automatic path; normal explicit user commits are unchanged. HEAD and Git's index are separate publications, not one filesystem transaction. If the ref is published but index publication fails, the helper reports the exact commit and unconfirmed index, preserves foreign content, and does not create a duplicate on retry. A hard process death can leave the ordinary Git index lock; unknown locks are refused rather than removed. Inspect/reconcile that exceptional state rather than blindly replaying mutations. Text/path allowlisting cannot prove arbitrary text contains no dataset. Those limits are not represented as solved.

TRACK 1 STATUS: implementing | stack=S1 | commit=1ce9504 streams: publish snapshots and scope automatic commits | red=yes green=yes suite=pass | disposable=pending

Progress-file update is complete. This continuation contains exactly one local implementation commit and returns its checkpoint for parent review/reporting. No next commit has started.

## Current limitations

Only the first S1 commit is implemented. The rest of S1, S2, S2a, S3, S4, S5, and S6 remain. No actual isolated pi-web task-effect check or F-DCR round trip has run. Pi-web source is pinned and compatible but unbuilt/unmodified; native maintenance/recovery capabilities are not yet implemented or verified. Bot owning source/route discovery and companion patches remain pending. No production activation, deployment, installed edit, credential operation, Slack send, existing-stream/session mutation, push, PR, merge, or other-branch rebase occurred. Parent review is still required.

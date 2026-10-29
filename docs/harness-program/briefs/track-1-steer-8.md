# Track 1 steer 8 (Grok Bot, 2026-10-28 22:35 SGT) - decision G48: settle the merged-poc rebase red suite

Your last status line is "rollout-part-1 done | merged-poc=blocked: suite failures at fa8566c | ...". Grok Bot owns this decision under ZF's delegation and has decided it. Do not wait for an operator. Do not touch the native install, the live pi-web services, or the live ~/.pi-stack in this steer.

Decision G48. The Prime suite failures on the private rebase feat/merged-poc-rebased (fa8566c: 77 tests, 14 failures, 8 errors) are settled by a base comparison, the same standard as G46, then fixed only where the rebase caused them.

Next actions, in order, in private clones only (no push, no merge, no stash or reset in any live worktree):
1. In the same private environment you used for fa8566c (same HOME/XDG/TMPDIR, same Python and dependencies), run the same Prime suite command on: (a) feat/prime-cli b371748, (b) old feat/merged-poc e3232f1, (c) fa8566c. Record pass/fail/error counts and the failing test ids for each.
2. Classify every failure on fa8566c. A failure that also appears on b371748 or e3232f1 with the same cause is pre-existing or environment-caused: document it with the evidence, and if it is environment-caused, rerun that test once in the environment it passes in (the box ran 76 prime tests green on b371748). Do not edit tests to hide anything.
3. A failure that appears only on fa8566c is caused by the rebase conflict resolutions (project schema, backend dispatch, tick integration, TODO.md). Fix its root cause in the smallest commits on feat/merged-poc-rebased, keeping each original PoC commit's intent, with tests unchanged. Then rerun the full pi-streams suite and the full Prime suite plus the PoC test file once on the new head.
4. Record G48 and the evidence in 12-track-1-progress.md (and a short note in 13-track-6-progress.md), with the final head sha and suite counts.
5. End with exactly one line: `TRACK 1 STATUS: merged-poc-rebase <green|blocked> | head=<sha> | pi-streams=<n> pass | prime=<n> pass,<f> fail,<e> error | pre-existing=<ids or none>`.

Grok Bot then force-pushes feat/merged-poc with --force-with-lease from your bundle, runs the native install from outside the session, and sends part 2 (real-stream verification of the corpus symptoms). If the evidence is ambiguous or a fix attempt fails twice, stop and report the exact finding in the status line instead of looping.

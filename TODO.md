# Track 6 progress

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [ ] Phase C: Run the loop.
- [x] Unit 1. Implement the Z15 stream writer and focused behavior tests.
- [x] Unit 2. Expose public stock transport and owned sessions.
- [x] Unit 3. Save and refresh messages, wake eligible work, and stop best effort.
- [x] Unit 4. Dispatch clean poteto workers with handover and kickoff only.
- [x] Unit 5. Own percentage-triggered save, compact, readback, and resume.
- [ ] Unit 6. Close only computed results and stage owned paths.
- [ ] Unit 7. Install stock Prime and pi-stack under an isolated external prefix.
- [ ] Unit 8. Prove intake through compaction to checked close with the shared verifier.
- [ ] Phase D: Keep the audit trail.
- [ ] Phase E: Verify and hand back.
- [ ] Opening a PR. skip: The user permits local commits only and forbids pushes and PRs.

The implementation and verification contract is in `PLAN.md`. The canonical decisions, commit SHAs, checks and evidence paths are in `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/13-track-6-progress.md`. Historical track-2 work remains in the merged CLI branch history and artifact 20.

## Serial implementation owner

The retained owner continues Units 2 through 8 without children or unit-only returns. The parent owns independent review. Each ordered commit still requires focused tests and both full suites. This supersedes the original fresh-per-unit workflow after runner `660682b8-9446-46d1-b39b-70d2122effb2` returned only a launch receipt.

## Unit 1 verification

Commit `ea6ef52187a6b23a6ee68df7ae3b893881ff9f6c` has subject `state: implement the Z15 stream writer`. This full-SHA note is an unstaged post-commit report update.

New functionality adds typed Goals, Rules and immutable entries, exact parsing, checked updates, original saves, history-first Log retention, Prime templates and linked-worktree locks. Existing Pi templates remain unchanged. Reused project Git/config/registry helpers and kernel flock; no new index or task store.

Evidence is under `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/evidence/`.

- `unit-1-before.log` records old creation failing the missing-current-work assertion and the linked-worktree lock error before correction.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests -p test_prime_state.py` passed 31 tests in `unit-1-focused.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests` passed 136 tests in `unit-1-streams.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` passed 71 tests in `unit-1-root.log`.
- Exact section-4 AGENTS bytes, Python syntax and `git diff --check` passed in `unit-1-static.log`.

Unit 2 passed 39 focused tests, 144 stream tests and 72 root tests. Logs are `evidence/unit-2-{focused,streams,root}.log`. The shared transport owns protocol 7/schema 30, pending commands and interleaved events. The thin CLI preserves compatibility projections and error outcomes. Prime session creation refuses thinking clamps. The parent-reported path escape has a failing regression and now rejects destination/ancestor symlinks and registered Prime paths outside the project stream directory.

Unit 2 commit is `ffbacff02fb2d2dc689ad216b6f3cfc5da3a779b`. Unit 3 passed 48 focused, 153 stream and 72 root tests in `evidence/unit-3-{focused,streams,root}.log`.

Unit 3 commit is `c3555ce4b8188e9d6962f1d5609e7ee9c11b3bbe`. Unit 4 passed 49 focused, 154 stream and 72 root tests in `evidence/unit-4-{focused,streams,root}.log`. Worker assignment and existing thread registry are saved before the exact unwrapped handover/kickoff. Native product instructions remain untouched; returned summaries are saved only in stream Log.

Unit 4 commit is `e82609ec59be46d36fe9eccdd4c704827ac71d52`. Unit 5 passed 62 focused, 167 stream and 72 root tests in `evidence/unit-5-{focused,streams,root}.log`. Percentage and explicit requests share one controller. Checked save precedes pause, idle/queue recheck and direct compact. Readback verifies the current branch and exact owned disk entry. A parked-input fixture proves release-before-await. Native runtime proof remains pending.

Next is Unit 6. Prime creation currently takes an explicit `backend="prime"` and persists it in `stream.toml`. Project-level backend settings remain Unit 2. Writers accept `locked=True` for callers already holding the stream lock. Successful computed completion remains blocked until Unit 6 supplies its actual closing checks. Explicit cancellation or informational explanation uses a complete linked answer and later trusted human source. Broad legacy staging remains unchanged until Unit 6. No native inference or authentication check was attempted.

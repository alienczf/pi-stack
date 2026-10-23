# Track 6 progress

- [x] Read the Principles section of the poteto-mode skill.
- [x] Phase A: Frame.
- [x] Phase B: Design the workflow.
- [x] Phase C: Run the loop.
- [x] Unit 1. Implement the Z15 stream writer and focused behavior tests.
- [x] Unit 2. Expose public stock transport and owned sessions.
- [x] Unit 3. Save and refresh messages, wake eligible work, and stop best effort.
- [x] Unit 4. Dispatch clean poteto workers with handover and kickoff only.
- [x] Unit 5. Own percentage-triggered save, compact, readback, and resume.
- [x] Unit 6. Close only computed results and stage owned paths.
- [x] Unit 7. Install stock Prime and pi-stack under an isolated external prefix.
- [x] Unit 8. Implement the shared native verifier and offline proof-stage negatives.
- [ ] Native gate. BLOCKED on operator Codex login. Final clean install, init and doctor passed. The verifier reached the real missing-auth reply and stopped its owned daemon. Native PASS remains unclaimed.
- [x] Phase D: Keep the audit trail.
- [x] Phase E: Verify and hand back. Offline and installation checks passed; native acceptance is explicitly BLOCKED.
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

Unit 4 commit is `e82609ec59be46d36fe9eccdd4c704827ac71d52`. Unit 5 passed 62 focused, 167 stream and 72 root tests in `evidence/unit-5-{focused,streams,root}.log`. Percentage and explicit requests share one controller. Checked save precedes pause, idle/queue recheck and direct compact. Readback verifies the current branch and exact owned disk entry. Unit 8 later corrected the fixture's quoted-body matching and explicitly proved that continuation input really parks until release. Native runtime proof remains pending.

Unit 5 commit is `064e65dc27951395c2509a51182191701dd8e615`. Unit 6 passed 70 focused, 175 stream and 72 root tests in `evidence/unit-6-{focused,streams,root}.log`. Closing executes an allowlisted local Python check outside the lock and rechecks source, target, report and proof before publication. Raw claimed completion is refused. Narrow staging leaves scratch and runtime settings untouched and refuses foreign staged paths.

Unit 6 commit is `4d5dfc3954128aded35b63af3d21b8b4315b1c13`. Unit 7 passed 76 focused, 181 stream and 72 root tests in `evidence/unit-7-{focused,streams,root}.log`. Installer fixture checks are offline, not stock build proof. The README's private prerequisite commands installed Cargo/rustc 1.99.1 under the authorized prefix only; `evidence/unit-7-private-prerequisites.log` retains output. Final clean clone, real install/init/doctor/verify remain Unit 8 gates.

Unit 7 commit is `35bcb645ad9160b77bc3d23df00190aaf83b71c9`. Unit 8 passed 7 shared-verifier tests, 85 focused Prime tests, 197 stream tests and 72 root tests in `evidence/unit-8-{focused,streams,root}.log`. Final overlay, isolated-installer, README-command, exact eleven-prompt, syntax and whitespace gates passed in `evidence/unit-8-final-gates.log`.

The verifier refuses an existing session/socket or retained attempt, captures actual native command ordering and disk proof, and reports missing authentication as BLOCKED. It does not automate login or copy credentials. Final native installation is verified. Inference remains BLOCKED by the actual `No API key found for openai-codex` response. The first native attempt built stock Prime and passed init/doctor, then failed before session creation on Python's long Unix-socket path handling. Unit 8 now mirrors stock's Linux directory-fd addressing and its same-socket regression passes. The initial attempt was preserved as `native-attempt-1-prefix` and `native-attempt-1-checkout`; only its private build cache was reused. The selected fixture percentage is 0.1. Its finite repeated inert context data is intended to exceed 500 tokens in the explicit 500000-token model window; only an actual native percentage crossing can pass.

The second native test ran at `491f1633ae1175a8952a5b8861d2c8febd8bfa2a` and reached the real Codex authentication refusal. Final self-review also reproduced two stop-scope failures. A worker stop incorrectly paused unrelated stream work, and a stream with no objective failed to record its pause. The final Unit 8 correction limits worker stops to matching assignments and permits a paused null objective, as the section-5 schema allows. Both regressions and both suites are green. The final SHA and repeated native outcome are recorded in the canonical progress document.

Final native evidence is `evidence/unit-8-clean-{install,init,doctor,verify}.log`, `evidence/unit-8-native-summary.json` and `<prefix>/reports/weekend-poc-poc.json`. The native transcript records the requested model and `xhigh`. Observed usage crossed 0.1 percent to 4.4306 percent, but authentication failed before DCR or inference; no save/compact/resume or checked-close success is claimed. The native session and all fixture bytes remain retained, and the owned daemon was shut down and waited.

Clean HOME is `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home`. The operator alone may run `HOME=/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home /home/alphalab/.cache/pi-stack-track6/20261023T172837Z/home/pi-stack-merged-poc-test/bin/prime-agent`, then enter `/login` in the bare TUI. No login was automated. After login, use a newly initialized stream identifier rather than replaying or adopting the retained failed attempt. Native steer, worker kickoff, stale refusal, self-review and the complete percentage/save/compact/readback/resume/close sequence remain unproved. Independent review is still required.

Existing-path corrections in Unit 8 have before-fix evidence in `unit-8-steer-before.log`, `unit-8-parked-before.log`, `unit-8-state-path-before.log` and `unit-8-worker-path-before.log`. They cover human steering while another prompt is pending, a genuinely parked continuation, and symlink ancestors at writer/worker boundaries. No staged runtime data or credentials are part of these commits.

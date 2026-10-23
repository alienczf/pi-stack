# Track 6 progress

## Scope and exit condition

Build revised 51 section 8 as eight ordered, tested local commits on `feat/merged-poc`. Prove the documented install in a fresh clone and clean HOME. Real inference must demonstrate the requested steer, clean worker handover and kickoff, percentage-triggered save/compact/disk-readback/resume, stale-message rejection, stream adversarial self-review and computed close. Offline fixtures do not prove native inference. Stop at an operator-owned Codex login if that is the only remaining requirement.

## Current state

- Worktree created at `/home/alphalab/Projects/worktrees/pi-stack-merged-poc` from local main `3acf0f01e6084a317b89cef3a86f4781e60877cf`.
- Read-only `feat/prime-cli` at `6bc1242` merged locally as `23640e5d24501afb88da1e2eb5487a89001eac93`.
- The eight-unit plan, acceptance checks, ownership and throughput checkpoint are in the new worktree's `PLAN.md` and `TODO.md`.
- Preparation commit `198e433b19259eb56eec9b512b36b1247ffd519a` has a green baseline of 105 stream tests and 71 root tests. `baseline-root-standalone.log` supersedes the earlier incomplete combined root log; that partial log is not a code failure.
- Unit 1 is implemented and locally committed as `ea6ef52187a6b23a6ee68df7ae3b893881ff9f6c`. Its focused tests, 136-test stream suite and 71-test root suite passed. No native session or authentication probe was attempted.
- Git, Python 3.12.3, a C compiler and uv are on PATH. Cargo and rustc were not found on PATH or the targeted user tool locations. Installer prerequisite work must remain isolated and documented. No global setup was changed.

## Evidence paths

Run directory is `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/`.

- `evidence/baseline-streams.log` records 105 tests passing.
- `evidence/baseline-root.log` is incomplete from the timed-out combined command and is superseded by `evidence/baseline-root-standalone.log`, which passed 71 tests.
- `evidence/unit-1-before.log` records the old creation format failing the missing-current-work assertion and the linked-worktree lock raising `NotADirectoryError` before correction.
- `evidence/unit-1-focused.log` records 31 new state/creation/lock tests passing.
- `evidence/unit-1-streams.log` records all 136 stream tests passing.
- `evidence/unit-1-root.log` records all 71 root tests passing.
- `evidence/unit-1-static.log` records exact section-4 AGENTS template bytes, Python syntax and `git diff --check` passing.
- `evidence/unit-1-commit.log` records the local commit. The final full-SHA note in `TODO.md` and this progress update are deliberately unstaged post-commit reports.
- `evidence/unit-1-final.log` records the full SHA, committed paths, `git diff --check`, `git diff --cached --exit-code`, the authorized progress-file diff check and no staged files.
- Clean HOME will be `home/` under this run directory. Fresh clone will be `home/pi-stack-merged-poc`. Installer prefix will be `home/pi-stack-merged-poc-test`.

## Commit stack

| Unit | Commit | Verification |
|---|---|---|
| Foundation | `23640e5d24501afb88da1e2eb5487a89001eac93`; preparation `198e433b19259eb56eec9b512b36b1247ffd519a` | Baseline passed 105 stream tests and 71 root tests. |
| 1. State writer | `ea6ef52187a6b23a6ee68df7ae3b893881ff9f6c` | VERIFIED. 31 focused tests, 136 stream tests, 71 root tests, exact role template, syntax and diff checks passed. |
| 2. Prime transport | `ffbacff02fb2d2dc689ad216b6f3cfc5da3a779b` | 39 focused, 144 stream and 72 root tests passed. `evidence/unit-2-{focused,streams,root}.log`. |
| 3. Messages, wake and stop | `c3555ce4b8188e9d6962f1d5609e7ee9c11b3bbe` | 48 focused, 153 stream and 72 root tests passed. `evidence/unit-3-{focused,streams,root}.log`. |
| 4. Clean workers | `e82609ec59be46d36fe9eccdd4c704827ac71d52` | 49 focused, 154 stream and 72 root tests passed. `evidence/unit-4-{focused,streams,root}.log`. |
| 5. Owned compaction | `064e65dc27951395c2509a51182191701dd8e615` | 62 focused, 167 stream and 72 root tests passed. `evidence/unit-5-{focused,streams,root}.log`. Offline only. |
| 6. Computed close | awaiting commit | 70 focused, 175 stream and 72 root tests passed. `evidence/unit-6-{focused,streams,root}.log`. |
| 7. Isolated install | pending | pending |
| 8. PoC verifier | pending | pending |

## Decisions

| UTC time | Decision | One-line reason | Evidence | Result |
|---|---|---|---|---|
| 2026-10-23T17:28:37Z | Merge the CLI branch into a new branch cut from local main. | Preserve the gated CLI history and avoid mutating its read-only worktree. | `23640e5` | Created. |
| 2026-10-23T17:28:37Z | Follow 51 section 8 without another architecture bakeoff. | Its revised design already selects the protocol, storage and install contract. | `51-design-merged.md` section 8 | Eight serial units planned. |
| 2026-10-23T17:28:37Z | Use one fresh same-model child per implementation unit and a final independent validation child. | Shared state and transport invariants need one writer, while fresh context limits carryover mistakes. | New worktree `PLAN.md` | Planned. |
| 2026-10-23T17:28:37Z | Use this Decisions section instead of a second decision ledger. | The user named this document as the canonical progress and decision trail. | Track 6 brief | Applied. |
| 2026-10-23T17:28:37Z | Keep runtime evidence and the clean installation in a unique persistent cache directory. | It survives reboot and isolates the live installation, streams and credentials. | `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/` | Created. |
| 2026-10-23T17:28:37Z | Run all children on openai-codex/gpt-6.1-sol at xhigh. | The brief forbids model or provider changes even for process-skill reviews. | Session PI_MODEL and PI_PROVIDER | Applied. |
| 2026-10-23T17:57:42Z | Unit 1 start continued the existing 2026-10-23T17:28:37Z plan without children or a design bakeoff. | The assigned writer owns only one settled implementation unit. | `PLAN.md`; Unit 1 task; `ea6ef52187a6b23a6ee68df7ae3b893881ff9f6c` | Applied. |
| 2026-10-23T17:57:42Z | Model Goals, Work, Rule, Entry and State as typed values before writing logic. | Model the Domain keeps the Markdown boundary and preservation rules in one module. | `pi-streams/engine/state.py` | Implemented. |
| 2026-10-23T17:57:42Z | Reuse original command/purpose filenames and reject changed text, durable target, sender or lane. | Make Operations Idempotent requires retries to preserve the first local identity without promising native deduplication. | `pi-streams/tests/test_prime_state.py`; `evidence/unit-1-focused.log` | Verified before and after rotation. |
| 2026-10-23T17:57:42Z | Preserve exact retired ruling text as a hashed text-proof entry and publish history first. | A source-linked retirement cannot discard bytes when history or STATE publication fails. | `state.py::update_state`; `evidence/unit-1-focused.log` | Verified with I/O and partial-publication failures. |
| 2026-10-23T17:57:42Z | Use `result.status` cancelled or informational with a complete linked answer and later trusted human source; reject claimed complete answers. | Source accounting is needed now, while actual computed completion belongs to Unit 6. | `state.py::_explained`; partial-answer and cancellation tests | Verified. |
| 2026-10-23T17:57:42Z | Persist stream-local backend selection now and leave project-level Prime configuration for Unit 2. | Creation and upgrade need a durable template choice without changing legacy Pi defaults. | `project.py::StreamConfig/create_stream/upgrade_stream` | Legacy suites green. |
| 2026-10-23T17:57:42Z | Resolve each lock through Git's absolute per-worktree Git directory and allow already-locked writers. | Linked worktrees have a `.git` file, and live send callers must not acquire a second flock. | `evidence/unit-1-before.log`; `evidence/unit-1-focused.log` | Red before correction, green afterward. |
| 2026-10-23T17:57:42Z | Keep tests at the public writer/file boundary and run focused checks before both complete suites. | Test Behavior, Not Implementation and Prove It Works require retained-byte and failure observations, not a fixture-only claim. | `evidence/unit-1-{focused,streams,root,static}.log` | 31, 136 and 71 tests passed. |
| 2026-10-23T17:57:42Z | Commit only Unit 1 after all checks, then leave full-SHA report updates unstaged. | Sequence work into verifiable units avoids a second bookkeeping commit or a self-referential commit hash. | `evidence/unit-1-commit.log`; `TODO.md` | One local unit commit, no staged files. |
| 2026-10-23T17:57:42Z | Perform the diff and comment review inline; no installed deslop skill was found. | The child cannot spawn reviewers or alter installed process skills, and the parent owns independent acceptance review. | Unit 1 source diff; `evidence/unit-1-static.log` | Self-review complete; independent review remains required. |

| 2026-10-23T18:02:07Z | Supersede the fresh-per-unit launch plan with one retained serial implementation owner for Units 2 through 8. | The workflow returned a launch receipt and ended, so resuming the known owner avoids duplicate writers and preserves its in-flight report and source context. | Workflow `660682b8-9446-46d1-b39b-70d2122effb2`; child `1174ac5f-0e47-483a-a1df-82a6595351fc` | Remaining units assigned to the same owner. |

| 2026-10-23T18:03:04Z | Resume the retained owner's checkout for all remaining units, without nested workers. | The queued correction was printed rather than executed, and the parent explicitly revived this context. | Workflow `660682b8-9446-46d1-b39b-70d2122effb2`; retained run `1174ac5f-0e47-483a-a1df-82a6595351fc`; current follow-up | Applied; PLAN and TODO use one serial owner. |
| 2026-10-23T18:03:04Z | Keep a single transport in `engine/prime.py` and move compatibility projections to `engine/prime_compat.py`. | A thin bin entry can preserve imported CLI helpers while live hooks share one multiplexed connection. | `evidence/unit-2-focused.log`; `evidence/unit-2-root.log` | Verified. |
| 2026-10-23T18:03:04Z | Require schema 30 and update the old owned supervisor fixture to advertise it. | The original CLI accepted schema 29; enforcing the public contract must not silently grandfather an incomplete fixture hello. | `evidence/unit-2-before.log`; `tests/test_prime_tools.py` | Failed before correction, both suites green afterward. |
| 2026-10-23T18:03:04Z | Reject symlink paths before resolving and require registered Prime streams to stay in their project stream directory. | Resolving first erased the symlink identity and allowed writes into a foreign directory. | `evidence/parent-state-path-review.log`; `evidence/unit-2-path-before.log`; `test_prime_state.py` | Destination, ancestor and registered-path regression passes. |

| 2026-10-23T18:03:04Z | Use pending-message values to separate locked socket writes from unlocked reply waits. | State must be saved and freshly wrapped before a send, but pause release and other commands must remain possible while waiting. | `engine/prime.py::PendingMessage`; `evidence/unit-3-focused.log` | New behavior verified. |
| 2026-10-23T18:03:04Z | Run Prime ticks outside the legacy all-stream lock and reuse the existing registry and tick entry. | Inference must not hold unrelated stream locks, and a second task clock is unnecessary. | `engine/tick.py`; `evidence/unit-3-streams.log` | Legacy and Prime cases green. |
| 2026-10-23T18:03:04Z | Preserve uncertain sends and expose abort replies without a termination promise. | A timeout is not native failure or permission to replay, and abort cannot promise rollback. | `evidence/unit-3-focused.log` | Duplicate, stale, timeout and abort checks pass. |

| 2026-10-23T18:03:04Z | Reuse the existing thread registry and save each source-bound worker assignment before kickoff. | Clean sessions need no copied stream files, but the stream must retain full identities and exact handed-over wording. | `engine/threads.py::spawn_prime_worker`; `evidence/unit-4-focused.log` | Worker and stream-chosen reviewer paths verified. |
| 2026-10-23T18:03:04Z | Keep summary review guidance solely in stream AGENTS and optional reviewer text. | Native run success is not task completion, and no hook may force a reviewer. | `templates/prime/AGENTS.md`; `evidence/unit-4-focused.log` | Product instructions unchanged; summaries retained in stream Log. |

| 2026-10-23T18:03:04Z | Use the same DCR Log/history entries for percentage and explicit requests and retain a busy request's first observation. | No second controller or task database is needed, and busy observations cannot authorize a maintenance abort or duplicate native compact. | `engine/prime.py::check_compaction/run_compaction`; `evidence/unit-5-focused.log` | Verified offline. |
| 2026-10-23T18:03:04Z | Require a new checked update during the save turn, then pause and recheck native activity before direct compact. | A successful model reply alone does not prove STATE was saved, and pause must not precede the save turn. | `evidence/unit-5-focused.log` | Missing save, stop, busy and failure cases refuse compact or resume. |
| 2026-10-23T18:03:04Z | Verify one new current-branch compaction against the exact owned native transcript before choosing input. | In-memory tree entries are not persistence proof; newer saved human input takes priority over automatic resume. | `engine/prime.py::read_compaction_entry`; `evidence/unit-5-focused.log` | Missing, off-branch, ambiguous and wrong-summary entries rejected. |
| 2026-10-23T18:03:04Z | Write followUp while paused and release the retained connection's pause before awaiting its result. | A queued prompt cannot finish while pickup is paused. | Parked-prompt socket fixture in `test_prime_compaction.py` | No deadlock; one continuation. |
| 2026-10-23T18:03:04Z | Clone pinned stock Prime unchanged into the authorized cache for exact wire-format inspection. | Native tree and transcript shapes must come from the selected revision rather than a guessed fixture. | `prime-reference` at `8aac8692456c00c01d4e53e60e6d3347a3506559` under the run directory | No existing source or sessions touched. |

| 2026-10-23T18:03:04Z | Execute named local Python checks outside the stream lock and bind actual argv/cwd/exit/output to immutable source, target and report proof. | A claimed green test cannot close work, while a concurrent instruction change must still stop publication. | `checks/state.py`; `evidence/unit-6-focused.log` | Wrong sources, target/report/proof, failed checks and changed instructions leave work open. |
| 2026-10-23T18:03:04Z | Support unittest or one tracked `check_`/`test_` Python script, not shell or scheduler replay. | The new check boundary must reject uncertain job submission rather than execute arbitrary claimed tests. | `checks/state.py::run_check`; `evidence/unit-6-focused.log` | Safe local checks and a valid alternative pass; this is validation, not an OS sandbox. |
| 2026-10-23T18:03:04Z | Define excerpt proof ranges as inclusive one-based LF line ranges and verify their exact bytes. | An excerpt cannot silently stand for an unretained full proof. | `test_prime_close.py` | Incorrect range rejected; exact Unicode excerpt accepted. |
| 2026-10-23T18:03:04Z | Stage only enumerated owned files or explicit authorized paths and refuse foreign staged content before index writes. | The old broad staging captured scratch and Prime settings in a behavioral reproduction. | `evidence/unit-6-before.log`; `evidence/unit-6-focused.log` | Legacy suites remain green; scratch and runtime data stay untracked. |

## Orchestration correction

The first asynchronous workflow returned the Unit 1 launch receipt instead of awaiting completion. Its later units were not launched. Unit 1 completed successfully, but a queued follow-up was printed after its final result instead of being executed. No duplicate writer was started. The parent resumes that exact implementation owner with the remaining seven-unit scope because its checkout, uncommitted report note and source context are retained. The parent will perform final independent artifact inspection and rerun verification directly. Installed orchestration tooling is outside the permitted write scope and remains unchanged.

The workflow receipt is `660682b8-9446-46d1-b39b-70d2122effb2`. The owned child is `1174ac5f-0e47-483a-a1df-82a6595351fc`. Its retained session is `/home/alphalab/.pi/agent/sessions/subagents/1bf3550c-6241-4f45-be16-256972c71aa9/run-0/session.jsonl`.

## Unit 1 checks and reuse

All commands ran in `/home/alphalab/Projects/worktrees/pi-stack-merged-poc` with runtime logs outside Git.

- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests -p test_prime_state.py` passed 31 tests in 3.381 seconds. Evidence is `evidence/unit-1-focused.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests` passed 136 tests in 98.410 seconds. Evidence is `evidence/unit-1-streams.log`.
- `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests` passed 71 tests in 34.353 seconds. Evidence is `evidence/unit-1-root.log`.
- A local Python check compared the full AGENTS template with section 4, parsed the three affected Python files with `ast.parse`, and ran `git diff --check`. Evidence is `evidence/unit-1-static.log`. `git diff --cached --check` also passed before commit.
- Reused existing project Git, config, registry and template helpers, the empty thread registry schema, and kernel flock. There is no new task database or history index. Existing Pi templates are unchanged.
- All state APIs and Prime templates are new functionality. The creation-format assertion and linked-worktree lock have explicit failing-before-fix evidence.

## Remaining

Implement and verify Units 2 through 8. Unit 2 must wire project-level backend settings and keep durable IDs separate from routing IDs. Unit 3 should use `check_state`/`check_current_text`, exact `read_entry` text and `locked=True` inside its final send lock. Writer results include the saved `entry` basename for internal callers. Unit 6 must add actual computed completion to source accounting and replace broad legacy staging; that path is intentionally unchanged in Unit 1. No native runtime claim follows from offline state tests. Independent review is still required. Carry the two unstaged post-commit report updates forward without creating another Unit 1 commit. Resolve only build prerequisites that can be supplied without touching a live installation and without hiding undocumented setup. Run the exact README install commands with the authorized local clone substitution. Select and record the test percentage. Stop and report usage/quota errors. Never automate or copy the operator's Prime Codex login.

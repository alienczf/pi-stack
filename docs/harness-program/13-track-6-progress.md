# Track 6 progress

## Scope and exit condition

Build revised 51 section 8 as eight ordered, tested local commits on `feat/merged-poc`. Prove the documented install in a fresh clone and clean HOME. Real inference must demonstrate the requested steer, clean worker handover and kickoff, percentage-triggered save/compact/disk-readback/resume, stale-message rejection, stream adversarial self-review and computed close. Offline fixtures do not prove native inference. Stop at an operator-owned Codex login if that is the only remaining requirement.

## Current state

- Worktree created at `/home/alphalab/Projects/worktrees/pi-stack-merged-poc` from local main `3acf0f01e6084a317b89cef3a86f4781e60877cf`.
- Read-only `feat/prime-cli` at `6bc1242` merged locally as `23640e5d24501afb88da1e2eb5487a89001eac93`.
- The eight-unit plan, acceptance checks, ownership and throughput checkpoint are in the new worktree's `PLAN.md` and `TODO.md`.
- Baseline stream suite passed 105 tests. The combined baseline command timed out during the root suite, so its partial output is not a pass. A standalone root-suite run follows before implementation.
- Git, Python 3.12.3, a C compiler and uv are on PATH. Cargo and rustc were not found on PATH or the targeted user tool locations. Installer prerequisite work must remain isolated and documented. No global setup was changed.

## Evidence paths

Run directory is `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/`.

- `evidence/baseline-streams.log` records 105 tests passing.
- `evidence/baseline-root.log` is incomplete from the timed-out combined command and is superseded by the standalone rerun.
- Clean HOME will be `home/` under this run directory. Fresh clone will be `home/pi-stack-merged-poc`. Installer prefix will be `home/pi-stack-merged-poc-test`.

## Commit stack

| Unit | Commit | Verification |
|---|---|---|
| Foundation | `23640e5` | Merge only. Baseline stream suite passed. Root-suite check pending. |
| 1. State writer | pending | pending |
| 2. Prime transport | pending | pending |
| 3. Messages, wake and stop | pending | pending |
| 4. Clean workers | pending | pending |
| 5. Owned compaction | pending | pending |
| 6. Computed close | pending | pending |
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

## Remaining

Implement and verify all eight units. Resolve only build prerequisites that can be supplied without touching a live installation and without hiding undocumented setup. Run the exact README install commands with the authorized local clone substitution. Select and record the test percentage. Stop and report usage/quota errors. Never automate or copy the operator's Prime Codex login.

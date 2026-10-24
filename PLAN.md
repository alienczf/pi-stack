# Track 6 merged proof of concept

## Definition of done

Build section 8 of `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/51-design-merged.md` as eight ordered local commits on `feat/merged-poc`. Every unit includes behavioral tests and leaves both existing suites green. Run the documented isolated installation from a fresh branch clone. Real Prime inference must prove steer, clean worker handover and kickoff, percentage-triggered save/compact/disk-readback/resume, stale-message rejection, stream self-review, and computed close. A missing operator-owned Codex login is BLOCKED, never PASS.

## Authority

Write source only in this worktree. The only permitted write in the docs worktree is `docs/harness-program/13-track-6-progress.md`. Runtime evidence belongs under `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z/`. Do not mutate existing sessions, streams, sockets, services, upstream source, credentials, or other worktrees. Do not push, open a PR, merge a PR, or contact GitHub. Grok Bot owns any later track-1 rebase. Stop and report a usage or quota failure. Use only `openai-codex/gpt-6.1-sol` at xhigh for authoring subagents and the native coordinator. G40 explicitly authorizes `openai-codex/gpt-6-luna` at xhigh for all native stream workers. Do not substitute a provider or model on failure.

## Data shape and ownership

STATE has exactly Goals, Rules, and Log. Immutable exact entries move to history before pruning Log beyond 30. A retained command UUID binds its original text, target, and lane. Prime's durable session ID is distinct from the routing ID. One multiplexed transport owns public protocol 7/schema 30 commands. Compaction progress lives in stream Log/history, not another database. Workers own no state files and receive only the specified context handover and kickoff.

## Build order

1. `state: implement the Z15 stream writer`. Exact checked updates, original preservation, history-first rotation, Prime stream templates, and linked-worktree locks.
2. `prime: expose public stock transport and owned sessions`. Reuse the CLI's validated command shapes in one multiplexed engine transport. Keep compatibility projections working through a thin entry point.
3. `streams: save and refresh messages, wake and stop`. Save before socket write, fresh stream wrapper, stale checks, existing-tick wake, and best-effort native abort.
4. `workers: use clean poteto handover and kickoff`. Independent assigned worktrees, no state files, assignment before kickoff, and returned summaries in the stream Log.
5. `compaction: own percentage, save, compact and resume`. Disable both stock controllers before construction. One percentage/explicit sequence, native pause, persisted-entry proof, and one current-input/resume message.
6. `checks: close only computed results and stage owned paths`. Execute safe local checks outside the lock, bind source/target/report/proof, recheck before publication, and refuse foreign staged content.
7. `install: isolate a stock Prime PoC on an external machine`. Early `--merged-poc` dispatch, explicit settings, pinned unchanged Prime with matching runtime sidecar, confined wrappers, and exact README commands.
8. `poc: prove intake through compaction to checked close`. Shared init/doctor/verify implementation, rerunnable driver, negative tests for proof stages, and the clean install/inference gate.

## Workflow and rigor

The merged design is settled. Do not spend another design exploration on alternatives that section 8 already selects. Use one retained background implementation owner for the remaining seven commits, serially in this worktree. The original workflow returned its first child's launch receipt instead of awaiting completion, so its later children never launched. Resume only that known owner, which retains the checkout, report edit and source context. The child inspects each seam and validates before committing each unit. The parent independently inspects actual files, CLI behavior, final diff and evidence and reruns verification. No child launches children.

Capture failing-before-fix behavior for existing paths. Label genuinely absent APIs as new functionality. Unit checks are `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s pi-streams/tests` and `PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests`, with focused tests first. Final gates additionally run `bash scripts/check-overlay.sh`, `bash scripts/check-prime-install.sh`, `python3 scripts/check-readme-commands.py`, syntax checks, and `git diff --check`.

## Throughput checkpoint

- Blocking first steps. Read the ratified design, compaction evidence, rulings and Prime CLI work. Create the requested worktree from local main and merge the read-only CLI branch. Record the unmodified baseline before source edits.
- Independent workstreams. Source implementation is serial because the state, transport, sender, compaction and close functions share invariants. Parent inspection is read-only while a child writes. The final validator starts after implementation ends.
- Shared mutable state. One child owns both this worktree and the progress document at a time. No parent source or progress writes overlap that child. Runtime artifacts use a unique retained cache directory and never a live installation.
- Smallest safe decomposition. Follow the eight specified commits. Reuse the existing CLI, registry, tick and poteto source installer. Build the required rerunnable verification scripts instead of substituting narrative claims.

## Test installation

Run directory is `/home/alphalab/.cache/pi-stack-track6/20261023T172837Z`. Set clean HOME to its `home` directory. Clone the local branch into `$HOME/pi-stack-merged-poc` and set `POC_ROOT=$HOME/pi-stack-merged-poc-test`. Use the README commands otherwise unchanged. Set `POC_MODEL=openai-codex/gpt-6.1-sol`, `POC_THINKING=xhigh`, and choose and record an explicit `POC_PERCENT` that the fixture can genuinely cross. Never copy credentials. Report the exact wrapper login command for the operator if native execution stops at authentication.

## G39 and G40 continuation

G39 confirms the operator's Codex login in the retained clean HOME. Preserve its auth file, onboarding settings and all prior streams/sessions. Do not archive or replace the authenticated prefix. A new disposable stream and its own dedicated daemon/socket carry the native test. Existing login sessions and daemons remain untouched.

G40 changes the default data values, not the state or transport architecture. Keep `Project.coordinator` and `Project.threads` as independent `ModelSettings`. Resolve omitted stream settings to `openai-codex/gpt-6.1-sol` plus `xhigh`, and omitted worker settings to `openai-codex/gpt-6-luna` plus `xhigh`. Explicit configuration and spawn arguments still win. Installer defaults, source metadata/config, public creation, clean-worker handover/kickoff, verifier reports and README commands must use the same choices. The percentage remains explicitly selected, with no default.

Add literal behavioral regressions at both actual create envelopes and override tests. Commit the green default change locally before the native gate. Use the completed authentication in place, never copy it to a fresh prefix. If installation ownership metadata needs updating, make that an explicit narrow, tested operation that verifies previous owned content and preserves unknown files and user onboarding fields. Do not bypass doctor or falsify source identity to make a verification pass.

Run the complete native acceptance sequence with the new models. Choose and record the fixture percentage before creating its session. A low threshold can remain exceeded after compaction because the exact original is still in STATE; do not repeatedly compact or mutate the threshold during a proof. Any incomplete or unknown native result remains unproved. Stop immediately on actual quota/usage failure, without retry or provider substitution.

## Process overrides

The user's same-model limit overrides cross-model advice in process skills. The required Decisions section in the progress document is the canonical decision trail, not an additional TSV. The explicit no-push/no-PR instruction skips Opening a PR. Missing optional process skills do not authorize editing their installed copies outside this task's write scope.

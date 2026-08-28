# Jig init version 1 contract

This reference defines the product boundary and data contract for `jig init`. The controller and later Jig playbooks must conform to it. The schemas under [`schemas/v1/`](schemas/v1/) are the machine-readable form of the JSON artifacts.

## Product boundary

Jig prepares one whole Git repository for sustained work by Pi agents. Version 1 ends after one first improvement step reaches `kept`, `reverted`, or `no-eligible-candidate`. It does not implement a recurring runner, a scheduler, automatic learning, automatic remediation, or automatic merge.

The Git top level is the only supported scope. A command from any subdirectory resolves the same top level. A package selector, a path argument that requests a subtree, or any other package-scope request fails before state changes. A monorepo can be initialized only as one repository.

## Ownership boundary

One writer owns each mutable artifact at a time.

| Owner | Decisions and writes |
|---|---|
| Human operator | The values, exceptions, amendments, and ratification in `COMMANDMENTS.md`. The operator also owns merge decisions. |
| Jig skill | Repository interpretation, interview presentation, feature and ownership interpretation, candidate recommendations, poteto routing, and semantic synthesis. |
| Python controller | Repository resolution, locks, manifest transitions, path and symlink containment, hashes, worktrees, receipts, and the terminal first-step outcome. |
| Isolated worker | Product changes allowed by one selected proposal. The worker cannot write controller state, `COMMANDMENTS.md`, active proof definitions, or verdicts. |
| Independent verifier or judge | High-blast-radius verdicts, behavioral verdicts, and contradiction findings. |

The model cannot mark its own work `kept`. The controller records a terminal outcome only from external receipts that satisfy the proposal.

## Canonical paths

`COMMANDMENTS.md` at the Git root is the only COMMANDMENTS path. Jig does not read or write a second copy under `.pi/`.

The target repository contains these artifacts:

| Path | Writer | Required state | Purpose |
|---|---|---|---|
| `COMMANDMENTS.md` | Human operator through the ratification flow | `commandments-ratified` and later | Stable commandment IDs, hard and directional values, proof, exceptions, owner, version, and ratification. |
| `.pi/jig/manifest.json` | Python controller | `surveying` and later | Schema version, repository identity, current state, transition receipts, hashes, verification receipts, first-step status, and tool versions. |
| `.pi/jig/profile.json` | Jig skill, committed by the controller after validation | `awaiting-commandments` and later | Cited observations, unknowns, and failure-mode applicability. |
| `.pi/jig/steps/0001/selection.json` | Jig skill, committed by the controller after validation | `step-selecting` and later | Every candidate, every eligibility result, ranking evidence, the selected ID, and the controller receipt. |
| `.pi/jig/steps/0001/proposal.json` | Jig skill, committed by the controller after validation | Only when a candidate is selected | The selected change, proof, rollback, blast radius, poteto playbook, and eval decision. The file exists before product edits. |
| `.pi/jig/steps/0001/result.json` | Python controller | Every terminal first-step outcome | Revisions, commands, hashes, execution location, verdict, and one terminal outcome. |
| `.pi/skills/jig-verification/SKILL.md` | Jig skill, committed by the controller after validation | `verification-ready` and later | The Pi-native Launch, Doctor, Drive, Evidence, Cleanup, and Helpers contract. |
| `.pi/skills/jig-verification/references/features/index.md` | Jig skill, committed by the controller after validation | `verification-ready` and later | The maintained feature index and protected user path. |
| `.pi/skills/jig-verification/references/features/<feature-id>.md` | Jig skill, committed by the controller after validation | `verification-ready` and later | One feature's owner, route or command, public entry point, allowed dependencies, drive procedure, evidence, and last result. |
| `AGENTS.md` | Jig skill on first creation, then repository maintainers | `verification-ready` and later | Short pointers to `COMMANDMENTS.md`, the verification skill, the feature index, the repository check, and the canonical placement relevant to the first step. |

Jig preserves unrelated content in an existing `AGENTS.md`. After init, Jig treats the file as repository-maintained and reports a missing or stale pointer instead of regenerating the file on a rerun.

The manifest records the repository-native check command. The command can be a project script or a package target. It must work without the operator's pstack checkout. If the first step adds a guard, the command passes on the corrected tree, fails on a seeded violation, names the rule or file, and runs in CI before the guard becomes required.

## Init states

The absence of `.pi/jig/manifest.json` is the `absent` state. File existence never proves any later state.

```text
absent
  -> surveying
  -> awaiting-commandments
  -> commandments-ratified
  -> verification-building
  -> verification-ready
  -> step-selecting
  -> step-running
  -> initialized
```

Any active state can move to `failed-<state>` with an evidence receipt. A rerun validates owned artifacts and resumes from the last valid boundary. It does not infer completion from partial files.

The transitions require the following evidence:

| Transition | Required evidence |
|---|---|
| `absent -> surveying` | One Git root, an acquired init lock, recorded source revision and dirty summary, and a new validated manifest. |
| `surveying -> awaiting-commandments` | A valid profile, a recorded source revision, and an interview template with no generated human values. |
| `awaiting-commandments -> commandments-ratified` | One completed interview, all required human answers, explicit full-file ratification, and the `COMMANDMENTS.md` hash. |
| `commandments-ratified -> verification-building` | A current COMMANDMENTS hash, contained reserved output paths, a protected user path, and a recorded cleanup owner. The controller writes this transition before generation starts. |
| `verification-building -> verification-ready` | A valid verification skill, feature coverage for the protected path, a passing Doctor, a passing Drive-to-Evidence run, successful Cleanup, and artifact hashes. |
| `verification-ready -> step-selecting` | Current baseline evidence and a current COMMANDMENTS hash. |
| `step-selecting -> step-running` | One eligible selected candidate, a valid proposal written before edits, an isolated worktree, and a fresh Pi session. |
| `step-selecting -> initialized` | No eligible candidates, a rejection reason for every candidate, a valid `result.json`, no proposal, no worktree, and no diff receipt. |
| `step-running -> initialized` | Before and after evidence, the product regression floor, seeded proof when applicable, any required independent verdict, and a controller decision of `kept` or `reverted`. |

The controller writes `initialized` last through atomic replacement. A different source revision invalidates stale runtime evidence. A different candidate head invalidates its prior verdict.

## First-step states

The first step has its own state derived from the three step artifacts:

```text
unselected
  -> selecting
  -> no-eligible-candidate
  -> proposed
  -> running
  -> kept | reverted
```

`selection.json` always exists after selection completes. `selectedCandidateId` is `null` only when every candidate is ineligible. That path writes `result.json` with `no-eligible-candidate` and creates no `proposal.json`, worktree, baseline pin, or diff receipt.

A selected candidate must clear every eligibility gate. It is ineligible when it conflicts with a hard commandment, needs an unanswered product choice, lacks reproducible evidence or a real proof path, can change its own constraints, exceeds the allowed blast radius, lacks safe rollback, or requires recurring-run behavior.

For a selected candidate, the controller validates `proposal.json` before it creates the worktree. The proposal fixes the commandment IDs, active proof, rollback, and eval decision. The worker cannot change those fields. Init stops after the first terminal outcome and never selects a second candidate.

## Command table

All supported forms use the Python standard-library controller for validation and state transitions. They differ in how Pi resources enter the process.

| Command | Environment | Semantics |
|---|---|---|
| `jig init` | New shell-launched Pi process | The shell resolves the trusted pi-stack installation and delegates to the controller. The controller starts Pi with `--no-approve`, `--no-context-files`, `--no-extensions`, `--no-prompt-templates`, `--no-skills`, and one explicit `--skill <trusted-jig-skill>` argument. It records `resourceIsolation` as `isolated-shell`. |
| `/skill:jig init` | Current Pi session | The Jig skill calls the controller in current-session mode and performs semantic work in the current session. It never launches `pi -p` from Bash. The controller still owns every transition and validation. It records `resourceIsolation` as `inherited-session` because already-loaded project resources cannot be removed. |
| `/jig init` | Current Pi session through the `jig.md` prompt template | The template expands to an instruction to invoke `/skill:jig init`. It has the same state and safety contract as `/skill:jig init`, including the `inherited-session` receipt. It is not a separate engine. |

Only `init` is a version 1 mutating verb. Unknown verbs, legacy flags, package selectors, and extra positional arguments exit with status 2 before a manifest write. Read-only `status` or `check` commands can be added later only if init needs them. They cannot advance state.

A current-session invocation is convenient, but it cannot claim the resource isolation of the shell command. The command reports that difference instead of implying route parity.

## Safe repository loading

Shell init treats every project resource as untrusted. It does not depend on the global `defaultProjectTrust` value. It loads the trusted Jig skill by an explicit installation path and disables discovered skills, extensions, prompt templates, and context files. Repository instructions such as `AGENTS.md`, `.pi/settings.json`, and project skills are read only as survey data after the controller resolves and contains their paths.

The controller rejects output paths that are absolute, contain a parent traversal, resolve outside the Git root, or pass through an untrusted symlink. It writes a temporary file in the destination directory, validates and flushes the file, then atomically replaces the destination. It never removes unknown state.

These process flags do not make a hostile repository safe from every system interaction. Operators must use an operating-system sandbox without credentials or network access for hostile input.

## Pstack reference boundary

Jig uses canonical installed pstack skills for procedures that pstack owns. It references, rather than copies, the following logical paths:

- `pstack/skills/create-verification-skill/SKILL.md` for the runtime verification skill.
- `pstack/skills/poteto-mode/playbooks/refactoring.md` for structural migrations.
- `pstack/skills/poteto-mode/playbooks/bug-fix.md` for reproduced defects.
- `pstack/skills/poteto-mode/playbooks/feature.md` for new command behavior or deterministic guards.
- `pstack/skills/poteto-mode/playbooks/eval.md` for agent-behavior claims.
- The matching pstack performance playbook for measured slowness.

The running Jig skill resolves these paths from its installed pstack resources. The controller does not vendor pstack instructions or import pstack as a Python library. Target-repository artifacts can store the logical path, but they cannot store an absolute pstack checkout path. The generated verification skill and repository-native checks use only target-local files, installed Pi skill invocation names, and the target repository's own toolchain.

Deterministic checks prove schemas, containment, transitions, idempotency, and seeded guard failures. Runtime verification proves a user-facing path. A blinded pstack Eval proves an agent-behavior claim. One proof type cannot substitute for another.

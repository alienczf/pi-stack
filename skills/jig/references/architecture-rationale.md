# Jig init architecture rationale

## Problem

Current Jig delegates the repository survey and completion judgment to one Pi session. A partial `interview.md` can appear complete, project resources load before the survey, and the shell, skill command, and prompt template do not share state semantics. Version 1 needs semantic repository interpretation without asking the model to own locks, containment, atomic writes, or its own keep verdict.

## Caller's view

A repository owner starts init from any directory inside one Git repository:

```sh
jig init
```

The command resolves the Git top level, creates or resumes `.pi/jig/manifest.json`, and stops at `awaiting-commandments` until the operator answers one interview and ratifies `COMMANDMENTS.md`. A later invocation resumes from the last validated boundary. A package-only request fails before any state change.

Inside an existing Pi session, the owner can run either command:

```text
/skill:jig init
/jig init
```

Both current-session forms use the same controller state transitions as the shell form. They report inherited project resources because an active session cannot unload resources that Pi already loaded.

## Chosen shape

Version 1 has four parts:

1. The Jig Pi skill owns semantic work and internal init playbooks.
2. A thin shell entry point resolves the trusted installation and calls the controller.
3. A Python standard-library controller owns deterministic state, safety, and receipts.
4. Target-local verification artifacts own durable product proof after init.

The controller is a deep boundary with a small command interface. It hides repository resolution, schema validation, locking, stale-owner checks, atomic replacement, path containment, hashes, worktrees, and transition rules. The skill sees domain artifacts instead of filesystem and process details. The shell contains no interview or state logic.

The core data shapes are a manifest state machine, a cited repository profile, a candidate selection record, an optional immutable proposal, and a terminal result. These shapes put lifecycle rules in data instead of distributing them across prompt branches. The manifest remains controller-owned. The skill can propose semantic content, but the controller validates and commits it.

The controller uses Python because pi-stack already requires Python 3. Standard-library code adds no package installation, lockfile, transpilation, or Node module resolution to the trusted startup path. Python also provides direct filesystem, subprocess, hashing, JSON, and atomic replacement support. This choice does not authorize controller implementation in this unit.

`COMMANDMENTS.md` lives at the Git root. One visible path makes human ownership clear and gives `AGENTS.md`, the manifest, the verification skill, and future workers one stable reference. The controller hashes the file but never generates, forces, or amends its values.

Shell init starts a fresh Pi process with target project discovery disabled and the trusted Jig skill loaded explicitly. The two Pi commands run in the active session and record weaker isolation honestly. Both routes still pass all state changes through the controller. A running Pi agent never starts another `pi -p` process.

Pstack remains an installed procedure dependency of Jig, not a target-repository runtime dependency. Jig stores logical pstack paths for routing and reads the canonical installed sources when needed. It does not copy their bodies. Generated target artifacts contain no absolute pstack checkout path.

## State and concurrency decision

The repository manifest is the single controller-owned source of init state. A lock serializes that one real shared writer. Human intent is separate in `COMMANDMENTS.md`. Worker code is separate in an isolated worktree. Active eval definitions and verdicts stay outside worker write scope.

This separation removes most shared writes before locking. The remaining lock protects only controller state for one Git root. Every transition uses validated input hashes and an atomic replacement. Reruns reconcile existing receipts and converge from the last valid boundary. File existence alone never advances state.

## Tradeoffs accepted

- We accept two honest safety levels in exchange for both a hardened shell path and useful in-session commands.
- We accept a Python controller beside the Pi skill in exchange for deterministic crash recovery and containment that prompt prose cannot provide.
- We accept one repository-wide scope in exchange for one unambiguous manifest, lock, COMMANDMENTS file, and writer boundary.
- We accept logical pstack references that require an installed pstack environment during Jig work in exchange for avoiding copied procedures and checkout-specific target files.
- We accept a fixed first-step artifact layout in exchange for schemas and receipts that later units can validate without prose interpretation.

## Rejected alternatives

### Keep state in the skill and shell

A pure skill with shell bookkeeping is closest to current Jig, but it exposes transition order, partial-file recovery, path checks, and verdict rules to the model and shell callers. The interface looks small only because the safety policy leaks into prose. It cannot provide reliable idempotency or one engine-backed contract.

### Use a TypeScript controller

TypeScript would match Pi's implementation language, but pi-stack does not otherwise require a project Node dependency for its own scripts. It would add package resolution, a build or runtime loader choice, and dependency maintenance to the trusted path. Python 3 already exists as an installer prerequisite and handles the required deterministic work with its standard library.

### Embed Pi or use RPC as the primary controller API

Embedding the Pi SDK would require a Node controller and couple Jig state to Pi session internals. A long-lived RPC controller would add protocol framing, process lifetime, and recovery state before version 1 needs them. Starting one isolated Pi process from the human shell is smaller. Current-session skill calls avoid recursive Pi entirely.

### Implement Jig as a project extension

A Pi extension could register `/jig` as executable code, but project extensions require trust and run during startup. That is the wrong security boundary for surveying an unfamiliar repository. A global extension would also add an always-loaded lifecycle for a command that only needs a skill, a shell entry point, and a deterministic helper.

### Give each package its own state

Package scope would put several manifests, locks, and COMMANDMENTS files under one Git history while root instructions and CI still span packages. Package workers could then disagree about shared files and evidence. Version 1 resolves the whole Git root and rejects package-only requests instead.

### Vendor pstack procedures into Jig or the target

Copied playbooks would drift from the canonical pstack rules. Absolute checkout paths would make generated repositories machine-specific. Jig references logical canonical paths and emits target-local verification instead.

### Add the recurring runner now

A scheduler or repeated candidate loop would hide whether init can complete one evidence-backed transition. It would also require budgets, queue ownership, repeated human intent checks, and promotion policy. Version 1 stops after one terminal first-step outcome.

## Costs and risks

The Python controller becomes a security-sensitive component and needs fixture coverage for stale locks, interrupted writes, corrupt state, symlink escapes, and source revision changes.

The Draft 2020-12 schemas are the normative rules for each JSON document's shape, formats, and same-document conditions. Development and CI use a conforming Draft 2020-12 validator with format checking to verify the schemas and every example. That validator is not a controller runtime dependency. At runtime, the Python standard-library controller implements the subset of schema operators used by version 1 and applies those rules whenever it reads or writes an artifact. CI must compare the controller's results with the conforming validator on the same valid and invalid examples.

The controller separately validates cross-document links and filesystem facts that JSON Schema cannot prove. These checks include referenced file hashes, contained resolved paths, contiguous transition history, and whether `selectedCandidateId` names an eligible candidate. The controller applies them after each document passes schema validation.

Current-session commands can run after project resources have influenced the session. The manifest receipt and command output must keep that limitation visible. Operators who need isolation must use `jig init` from the shell. A hostile repository still requires an operating-system sandbox.

One repository-wide scope can be coarse for large monorepos. That cost is preferable to ambiguous shared state in version 1. A later package design needs explicit ownership for root files, cross-package commands, and repository-wide COMMANDMENTS before it can replace this boundary.

## Next implementation step

Implement the Python controller through `awaiting-commandments` against the version 1 schemas, then prove interruption recovery and project-resource isolation with fixtures.

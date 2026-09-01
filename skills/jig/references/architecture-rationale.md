# Jig repository configurator rationale

## Chosen shape

Jig has one job. It turns an operator interview into a repository Principle, delegates verification generation to pstack, and stops.

The durable domain shape is one version 2 configured-repository manifest. It records one repository, one ratified Principle, one pstack-generated verification skill, one public route, and one state-machine position. Product changes do not belong in that model.

The Python standard-library controller remains because exact digest ratification, route ownership, path containment, atomic writes, crash recovery, and idempotent settings merges are deterministic boundaries. The model owns repository interpretation. Pstack owns verification procedure design and proof.

## Canonical skill tree

Pstack already generates project skills under `.cursor/skills`. Jig keeps that location canonical. Pi's project settings load `../.cursor/skills`, which lets both harnesses read the same files. A second generated copy or symlink would create ownership and drift questions without adding a capability.

The repository Principle is a real skill named `principle-repository`. Its broad description makes it relevant to every nontrivial repository task. The pi-stack overlay also tells poteto agents to read trusted project `principle-*` skills after pstack's built-in Principles.

## Removed responsibilities

The old first-step engine duplicated normal poteto routing, worktree isolation, proof, review, and result handling. The old runtime-verification engine copied the contract already owned by `create-verification-skill`. Both made Jig responsible for doing repository work rather than configuring the repository.

Version 2 deletes those APIs instead of preserving compatibility paths. A version 1 manifest fails with preservation guidance because its terminal states and receipts have different meanings.

## Accepted tradeoff

The old controller certified a custom runtime receipt. Version 2 certifies configuration boundaries only. Pstack's generator owns the live proof. The terminal word is therefore `configured`, not `verified`, `kept`, or `reverted`.

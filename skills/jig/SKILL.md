---
name: jig
description: Fit THIS git repo with a closed vocabulary, import walls, and a user-run refactor plan. Use for /jig, /skill:jig, "jig this repo". Never auto-trigger.
disable-model-invocation: true
---

# Jig

Fit this git repo so a cold agent takes the conventional path. You write drafts. You do not rewrite the tree.

Read [interview.md](references/interview.md), [failure-modes.md](references/failure-modes.md), and [lexicon-style.md](references/lexicon-style.md) before Pass 1.

The version 1 init contract is [init-contract.md](references/init-contract.md). Its design choices and rejected alternatives are in [architecture-rationale.md](references/architecture-rationale.md).

## Init

For `init`, follow [the internal init playbook](playbooks/init.md). All forms use `.pi/jig/manifest.json` and `bin/jigctl.py`. A current Pi session records `inherited-session` and never starts `pi -p` from Bash. The shell launcher records `isolated-shell`.

Stop at the controller's implemented boundary. Do not infer human intent, select recommended defaults, approve a candidate, or write root `COMMANDMENTS.md` outside the deterministic ratification command. After ratification, route runtime verification through the canonical create-verification procedure and the [target boundary](references/runtime-verification.md).

## Pass 0. One git repo

Cwd must be inside one git repo. `git rev-parse --show-toplevel` must succeed. Operate only on that root. Do not walk parent directories. Do not `find` sibling `.git` dirs.

If this repo contains `registry.md`, `siblings.tsv`, `.pi/registry.md`, `.pi/siblings.tsv`, or scripts that call `pi -p` or `subagent` with another cwd, it is a coordinator. List other repos as external systems. Do not read those trees for coding conventions. Do not copy their nouns into this repo's `AGENTS.md`. The lexicon here is dispatch, registry, brief, report.

## Pass 1. Interview

Read-only tools first (`read`, `grep`, `find`, `ls`, `bash`). Skip `private_key.pem`, `public_key.pem`, `.env`, `auth.json`, and other key material. Then write `.pi/jig/interview.md` that answers every question in [interview.md](references/interview.md), including the extra five (nouns, import rights, placement crimes, score [failure-modes.md](references/failure-modes.md), giant files / legacy / inline imports / `any`).

Score every failure id. `absent`, `present-unencoded`, or `already-guarded`. Cite `file:line` for `present-*`.

## Pass 2. Drafts

Write only under `.pi/jig/`.

- `interview.md` from Pass 1.
- `AGENTS.md.draft`. Short. Pointer to the lexicon. One writer. Isolated new files. Prove command. "Use the lexicon nouns. Do not mint synonyms." No essay. No duplicated failure-mode table.
- `tutorial.md.draft`. Tutorial mode from technical-writing. First command. How to add one X using the nouns. What the learner should see.
- `lexicon.md.draft`. Running prose, 5 to 12 nouns that define each other. Follow [lexicon-style.md](references/lexicon-style.md). Not a glossary-only file.
- `refactor.md.draft`. Executable plan. Max five hottest `present-unencoded` hits. Jig will NOT `git mv`. Each item names goal, files, from-name, to-name, caller grep (code, strings, SQL, prose, back-links), pin command before the move, prove command after, playbook `pstack/skills/poteto-mode/playbooks/refactoring.md`. Rename items first. Import-graph walls second. Extractions third. Pin is a characterization test, snapshot, or replay. Typecheck is not a pin.
- `modes.md.draft`. Table. Smell in THIS repo to skill or playbook path. Only rows with evidence. Always include `/skill:how` before edit if P1 scored present. Always include `playbooks/refactoring.md` when a rename or extract is in `refactor.md.draft`.
- `deferred-ci.md`. List only. Import direction. No inline imports. Exhaustive switch. Ban of the local `useEffect` equivalent if found. Do not write `.github/` or eslint config on this pass.

## Pass 3. Cold-agent placement test

Pretend you are a new agent asked to add a small X named in the tutorial. You may read only the lexicon, the tutorial, and the three example features. If you would put the file in the wrong directory or import the wrong barrel, fix the drafts.

## Flags

- No flags, and `.pi/jig/interview.md` already exists. Print `already fitted. --iterate to refresh the refactor plan.` Exit 0. Do not rewrite.
- `--iterate`. Re-score failure-modes. Refresh lexicon, refactor, and modes drafts. Keep landed `AGENTS.md` unless `--apply` is also set.
- `--force`. Regen all drafts.
- `--apply`. Copy AGENTS, tutorial, and lexicon to the paths the drafts name. Never apply `refactor.md`.

Do not `git add`, `git commit`, or `git mv`. Do not execute the rename. The user runs poteto-mode refactoring against `.pi/jig/refactor.md`.

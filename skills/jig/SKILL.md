---
name: jig
description: Interview an operator to configure one Git repository with an initial repository Principle and pstack verification. Use only for explicit /skill:jig init or /jig init.
disable-model-invocation: true
---

# Jig

Accept only the exact argument `init`. Reject a missing argument, flag, path, package name, or extra argument before the controller writes state.

Read the canonical [public-route matrix](references/public-routes.json), [v2 contract](references/init-contract.md), and [init playbook](playbooks/init.md). Follow the playbook through at most one `configured` result.

## Resolve the controller

If `JIG_RESOURCE_ISOLATION` is `isolated-shell`, require `JIG_CONTROLLER` and `JIG_CREATE_VERIFICATION_SKILL` to name regular installed files. This route exists only inside the fresh Pi process started by the human `jig init` launcher.

Otherwise use `inherited-session`. Resolve the controller as `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py`. Resolve pstack's generator as `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/skills-pstack/create-verification-skill/SKILL.md`. A current Pi session never starts another Pi process from Bash.

Run `start` with the selected `resourceIsolation` before semantic work. If the manifest owns the other route, stop and print the recovery command from the route matrix.

## Ownership

The controller owns locks, state transitions, contained paths, initial hashes, atomic publication, project skill-path registration, and the terminal configuration record.

The target operator owns `.cursor/skills/principle-repository/SKILL.md`. Jig compiles the approved interview into that fixed initial Principle. Never infer an answer, weaken a value, publish the file directly, or ratify without approval of the displayed candidate digest.

Pstack's `reflect` owns later general skill learning and approved skill edits. It does not run during init. Pstack's `create-verification-skill` owns verification discovery, generation, live proof, and cleanup. Pstack's `maintain-verification-skill` owns later verification audits and corrections.

Jig never selects, edits, verifies, or merges a product-code improvement. Report `configured` only when the controller returns it.

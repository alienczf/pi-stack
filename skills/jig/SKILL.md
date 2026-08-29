---
name: jig
description: Initialize one whole Git repository through target COMMANDMENTS, runtime verification, and one controller-owned first improvement result. Use only for explicit /skill:jig init or /jig init.
disable-model-invocation: true
---

# Jig

Accept only the exact argument `init`. Reject a missing argument, a flag, a package name, a path, or an extra argument before you run the controller. Version 1 initializes the whole Git root.

Read the canonical [public-route matrix](references/public-routes.json), [init contract](references/init-contract.md), and [init playbook](playbooks/init.md). Follow the playbook through at most one terminal result.

## Resolve the controller and route

If `JIG_RESOURCE_ISOLATION` is `isolated-shell`, require `JIG_CONTROLLER` to name a regular installed `jigctl.py` file. This route exists only inside the fresh Pi process started by the human `jig init` launcher.

Otherwise use `inherited-session`. Resolve the controller as `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py`. A current Pi session never starts `pi -p` or another Pi process from Bash.

Run `start` with the selected `resourceIsolation` before semantic work. If the manifest owns the other route, stop without changing it. An `isolated-shell` manifest resumes with `jig init`. An `inherited-session` manifest resumes with `/skill:jig init` or `/jig init`.

## Ownership

The controller owns locks, transitions, hashes, path containment, worktrees, proof execution, and terminal outcomes. Use only its documented operations and exact JSON input files or standard input contracts.

The target operator owns `COMMANDMENTS.md`. Never infer an answer, publish the file directly, weaken a value, or ratify without approval of the displayed candidate digest.

The selected worker writes only in the controller-owned worktree. The worker cannot write `COMMANDMENTS.md`, `.pi/jig`, active proof definitions, or its own verdict. Never merge.

Report `initialized` only when the controller returns `kept`, `reverted`, or `no-eligible-candidate`. Do not offer or run a second step.

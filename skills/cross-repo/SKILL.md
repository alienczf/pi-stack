---
name: cross-repo
description: Coordinate an explicitly requested task across named Git repositories with subagents. Use only for /skill:cross-repo or /cross-repo.
disable-model-invocation: true
---

# Cross-repo

Run this workflow only when the user invokes it directly. The request sets the target repositories, the task, and whether each target may be edited.

## Coordinate

1. Take repository paths from the arguments. When no paths are given, use `registry.md` or `siblings.tsv` from the current repository if either exists. Otherwise ask for the targets.
2. Resolve each target to its Git root. Read the instructions inside that repository before delegating work there.
3. Split the request by repository. Use read-only agents for investigation. Keep one writer per repository when edits are requested.
4. Launch the children in one `workflowScript` and set `cwd` for each target. Review their artifacts or diffs before synthesizing the result.
5. Report the combined result and any unresolved dependency between repositories.

Use the `subagent` tool for children. A running agent does not launch `pi -p` from Bash.

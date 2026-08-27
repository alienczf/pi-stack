---
description: Dispatch subagents to targets listed in this git repo's registry
---
Read the cross-repo skill and execute it. Targets come from registry.md or siblings.tsv in the current git repo only. One `subagent` call per listed path with `cwd` set, or one `workflowScript` with `runs.all`. Do not run `pi -p` from bash. Each child writes a report file. The parent synthesizes and does not edit child trees. If this repo has no registry, stop and say so.

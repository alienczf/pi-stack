---
description: Dispatch pi -p to targets listed in this git repo's registry
---
Read the cross-repo skill and execute it. Targets come from registry.md or siblings.tsv in the current git repo only. One `pi -p` per listed path with cwd set by `cd`. Child tools are read, grep, find, ls, bash. Each child writes a report file. The parent synthesizes and does not edit child trees. If this repo has no registry, stop and say so.

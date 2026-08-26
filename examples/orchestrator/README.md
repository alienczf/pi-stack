# Sample coordinator repo

This directory is sample output of a git repo you jig like any other repo. It is not a workspace root. Do not copy these files onto a folder that contains other git repos as children. Pi loads `AGENTS.md` walking up from cwd, including directories above a git root. An ancestor file leaks into every child.

Put instance topology in a git repo you own. List targets in `registry.md` or `siblings.tsv` at that repo's root. `install.sh` does not copy this example anywhere.

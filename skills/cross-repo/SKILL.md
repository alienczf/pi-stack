---
name: cross-repo
description: Dispatch one pi -p per target listed in this git repo's registry.md or siblings.tsv. Parent owns briefs and synthesis, never child code. Use for /skill:cross-repo or a question that spans two git repos. Never auto-trigger.
disable-model-invocation: true
---

# Cross-repo

You are the coordinator in the current git repo. You own briefs and the synthesis. You do not edit other trees.

pi-stack does not know the user's folder layout. Targets come from a registry in this repository only.

## Dispatch

1. `git rev-parse --show-toplevel` must succeed. If it fails, stop.
2. Look for `registry.md` or `siblings.tsv` at that git root, or `.pi/registry.md` / `.pi/siblings.tsv` under it. Do not read `../AGENTS.md`. Do not walk parent directories. Do not `find` sibling `.git` dirs.
3. If none of those files exist, stop. Say there is no registry in this git repo. Tell the user to add `registry.md` here with explicit name and path rows. Do not invent paths.
4. Parse only rows that name a path. Skip placeholders that still say `/absolute/path/to/`. If every row is a placeholder, stop and say the registry has no real targets.
5. For each remaining row, start one child:
   `cd "$path" && pi -p --approve --no-session --tools read,grep,find,ls,bash --append-system-prompt "Follow ./AGENTS.md in this repo only. Do not edit. Write the report to the path in the prompt using bash redirection."`
   The report path is an absolute file under this coordinator repo, `.pi/cross-repo/<name>.md`. Create that directory first. The child may write only that file.
6. Wait for every report. Synthesize in `.pi/cross-repo/synthesis.md` in this repo. Quote report paths. Do not paste child trees.

## Rules

- Parent does not edit files inside a target git repo.
- Each child reads its own jig. A missing jig is a report finding.
- Stay in the foreground. Use tmux if a child must outlive one prompt. Do not background bash.
- Never MCP.

---
name: cross-repo
description: Coordinate work across two or more git repos. One pi -p child per repo writes a report file. Parent owns briefs and synthesis, never child code. Use for /skill:cross-repo, two jigs, or a parent folder with more than one git root.
disable-model-invocation: true
---

# Cross-repo

You are the coordinator. You own briefs and the synthesis. You do not edit child trees.

This skill is for two or more git repos that must stay separate. Trading layouts often look like infra, research, and algo. Those domains do not share a jig. Do not copy nouns from one child into another.

## Dispatch

1. Name each child git repo. The user listed them, or they sit one level under the current folder as their own `.git` roots. Do not walk `$HOME`.
2. Write one brief per child under `.pi/cross-repo/` (create it at the parent). If that directory is not writable, write under `/tmp/pi-stack-cross-repo/`.
3. Start one child per repo with `pi -p`. Set cwd with `cd "$repo"`. Do not pass `pi -c`. That flag continues a session.
4. Give each child write tools only for its report file. The report path is `.pi/cross-repo/<name>.md` in the parent, or `/tmp/pi-stack-cross-repo/<name>.md`.
5. Wait for every report. Then synthesize in `.pi/cross-repo/synthesis.md`. Quote report paths. Do not paste child trees.

## Rules

- Parent does not edit files inside a child git repo.
- Each child reads its own jig and lexicon. A missing jig is a report finding, not a reason to invent a shared vocabulary.
- Stay in the foreground. Use tmux if a child must outlive one prompt. Do not background bash.

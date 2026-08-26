# Pi overlay adapter

This file maps Cursor verbs onto Pi. It is process, not repo architecture. Fit a git repo with `/skill:jig`.

## Verb map

`Task` is `pi -p`. Set cwd with `cd` in the shell command. Do not pass `pi -c`. That flag continues a session.

`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.

Plan mode is `PLAN.md` in the working tree.

MCP is `gh`, `git`, or `curl`. If none of those can do the job, skip it. Never MCP.

`/loop` and `/goal` are prompt templates under `~/.pi/agent/prompts/`.

`poteto-agent` is `pi -p --append-system-prompt` that tells the child to read `__PSTACK__/skills/poteto-mode/SKILL.md` in full, including the Principles index.

Never background bash. Use tmux if you need a long-running process.

Keep the `read` tool enabled.

## Extra matches

Two git repos or two jigs. Read the cross-repo skill. Do not use `playbooks/investigation.md`.

The user says to execute the jig refactor plan. Read `__PSTACK__/skills/poteto-mode/SKILL.md` and copy `__PSTACK__/skills/poteto-mode/playbooks/refactoring.md`. The plan file is `.pi/jig/refactor.md`. Pin before any `mv`.

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

If the question spans two git repos, use `/skill:cross-repo`. Do not use pstack `playbooks/investigation.md`.

Do not place `AGENTS.md` in a directory that has multiple domain git repos as children. Ancestor files still load in Pi. Coding rules there leak.

The user says to execute the jig refactor plan. Read `__PSTACK__/skills/poteto-mode/SKILL.md` and copy `__PSTACK__/skills/poteto-mode/playbooks/refactoring.md`. The plan file is `.pi/jig/refactor.md`. Pin before any `mv`.

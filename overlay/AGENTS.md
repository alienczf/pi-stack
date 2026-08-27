# Pi overlay adapter

This file maps Cursor verbs onto Pi. It is process, not repo architecture. Fit a git repo with `/skill:jig`.

## Verb map

`Task` is the `subagent` tool from pi-subagents. One child is `{ agent, task }`. Several children are one `{ workflowScript }` with `await runs.all`. Set `cwd` when the child must run in another tree. Do not run `pi -p` from bash. That nested process blocks the parent and has no fleet status. `--tools` that omit `subagent` is how that bash spawn happens. jig.sh is a human launcher and may pin tools. Agents inside Pi may not. `pi -c` continues a session. It is not cwd.

Builtin agents. `scout` recon. `researcher` web and docs. `worker` edits. `reviewer` checks. `oracle` second opinion, no edits. `delegate` when the child should behave like the parent. `poteto-agent` is `delegate` or `worker` whose task says to read `__PSTACK__/skills/poteto-mode/SKILL.md` in full, including the Principles index.

Leave `async` on. That is the default. `async:false` only when this turn cannot continue without the child. Do not sleep-poll. Use `subagent_wait` only when this turn must consume the result.

Do not pin child models to `cursor/*` unless that provider is authenticated. A missing pattern warns and the child waits on a model that never comes. Use `inherit` or a listed `provider/id`. Call `{ action: "models" }` before an explicit model.

`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.

Plan mode is `PLAN.md` in the working tree.

`read` and `edit` are hash-anchored by pi-hashline-edit. Copy `LINE#HASH` prefixes from `read` into `edit`. Do not guess line numbers.

Public web is `web_search` and `fetch_content`. `gh`, `git`, and `curl` cover private or authenticated URLs those tools cannot reach. Never MCP.

`/loop` and `/goal` are prompt templates under `~/.pi/agent/prompts/`.

Never background bash. Use tmux if you need a long-running process that is not a subagent.

Keep the `read` tool enabled.

## Extra matches

If the question spans two git repos, use `/skill:cross-repo`. Do not use pstack `playbooks/investigation.md`.

Do not place `AGENTS.md` in a directory that has multiple domain git repos as children. Ancestor files still load in Pi. Coding rules there leak.

The user says to execute the jig refactor plan. Read `__PSTACK__/skills/poteto-mode/SKILL.md` and copy `__PSTACK__/skills/poteto-mode/playbooks/refactoring.md`. The plan file is `.pi/jig/refactor.md`. Pin before any `mv`.

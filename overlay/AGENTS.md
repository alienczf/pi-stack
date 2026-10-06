# Pi overlay adapter

This file maps Cursor verbs onto Pi. It is process, not repository architecture. Repository principles and repeated mistakes belong to pstack's `correct`.

## Verb map

`Task` is the `subagent` tool from pi-subagents. One child is `{ agent, task }`. Several children are one `{ workflowScript }` with `await runs.all`. Set `cwd` when the child must run in another tree. Do not run `pi -p` from bash. That nested process blocks the parent and has no fleet status. `--tools` that omit `subagent` is how that bash spawn happens. Agents inside Pi may not pin tools. `pi -c` continues a session. It is not cwd.

When delegation is needed, use only `{ agent: "poteto-agent", task }`. `install.sh` installs this child in `~/.pi/agent/agents/`, disables builtins, and retires the six old role profiles. Give the child a bounded implementation, investigation, or read-only task instead of selecting a different persona. Do not use a parallel worker+reviewer workflow as the default bug-fix loop. Tiny known-mechanism fixes stay parent-inline.

The child reads poteto-mode in full and decides reversible details without supervisor gates. It returns missing authorization or genuine product ambiguity in its normal result before taking the blocked action. New sessions see the installed settings and prompts. Existing children keep their old prompts until respawn.

Leave `async` on. That is the default. `async:false` only when this turn cannot continue without the child. Do not sleep-poll. Use blocking `subagent_wait` only when this turn must consume the result.

Do not pin child models to `cursor/*` unless that provider is authenticated. A missing pattern warns and the child waits on a model that never comes. Use `inherit` or a listed `provider/id`. Call `{ action: "models" }` before an explicit model.

`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.

Plan mode is `PLAN.md` in the working tree.

Use the built-in `read` and `edit` tools. Read the current file before editing. Match the exact text to replace.

Public web is `web_search` and `fetch_content`. `gh`, `git`, and `curl` cover private or authenticated URLs those tools cannot reach. Never MCP.

`/loop` is a one-shot prompt template, not a timer. For an async child, register `subagent_wait` with `nonBlocking: true` when you need a completion wake, then return control.

Never background bash. Use tmux if you need a long-running process that is not a subagent.

Keep the `read` tool enabled.

## Repository skills

Use pstack's `correct` for repository principles and for a mistake that repeats. Rank the fix as architecture, then types, lints, tests, and docs last. `create-verification-skill` builds repository verification, and `maintain-verification-skill` keeps it current. Use `/skill:reflect` after later work to turn durable learnings into approved skill edits. A running agent never launches `pi -p`.

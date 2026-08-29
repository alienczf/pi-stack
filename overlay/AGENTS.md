# Pi overlay adapter

This file maps Cursor verbs onto Pi. It is process, not repository architecture. Initialize one whole Git repository with `/skill:jig init`.

## Verb map

`Task` is the `subagent` tool from pi-subagents. One child is `{ agent, task }`. Several children are one `{ workflowScript }` with `await runs.all`. Set `cwd` when the child must run in another tree. Do not run `pi -p` from bash. That nested process blocks the parent and has no fleet status. `--tools` that omit `subagent` is how that bash spawn happens. jig.sh is a human launcher and may pin tools. Agents inside Pi may not. `pi -c` continues a session. It is not cwd.

These names are pstack-aligned user overrides that install.sh writes to `~/.pi/agent/agents/`. `scout` is the how explorer. `researcher` is web and why. `worker` is the poteto-agent writer. `reviewer` is interrogate checks. `oracle` is the how explainer and second opinion. `delegate` is the poteto-agent child that stays close to the parent. `poteto-agent` is `delegate` or `worker` whose task says to read `__PSTACK__/skills/poteto-mode/SKILL.md` in full, including the Principles index. The dest files also say that themselves.

Leave `async` on. That is the default. `async:false` only when this turn cannot continue without the child. Do not sleep-poll. Use blocking `subagent_wait` only when this turn must consume the result.

Do not pin child models to `cursor/*` unless that provider is authenticated. A missing pattern warns and the child waits on a model that never comes. Use `inherit` or a listed `provider/id`. Call `{ action: "models" }` before an explicit model.

`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.

Plan mode is `PLAN.md` in the working tree.

`read` and `edit` are hash-anchored by pi-hashline-edit. Copy `LINE#HASH` prefixes from `read` into `edit`. Do not guess line numbers.

Public web is `web_search` and `fetch_content`. `gh`, `git`, and `curl` cover private or authenticated URLs those tools cannot reach. Never MCP.

`/loop` is a one-shot prompt template, not a timer. `/goal` comes from `@narumitw/pi-goal`. For pstack autonomous runs, replace the Cursor `/loop` wake step with `/goal` settled continuation. Start `/goal <objective>` with a checkable exit predicate. Call `goal_complete` only after evidence proves the predicate. Call `goal_blocked` only for a repeated genuine impasse.
When progress depends on an external event, arrange its non-Goal wake message first. For an async child, register `subagent_wait` with `nonBlocking: true`. Then call `goal_wait` alone with `resume_after_ms` only as a bounded fallback. A time-only wake uses `goal_wait` with `resume_after_ms`. Do not use `goal_wait` for ordinary unfinished work.

Never background bash. Use tmux if you need a long-running process that is not a subagent.

Keep the `read` tool enabled.

## Extra matches

If the question spans two git repos, use `/skill:cross-repo`. Do not use pstack `playbooks/investigation.md`.

Do not place `AGENTS.md` in a directory that has multiple domain git repos as children. Ancestor files still load in Pi. Coding rules there leak.

## Jig handoff

Use `jig init` from the human shell for a fresh resource-isolated Pi campaign. Use `/skill:jig init` or `/jig init` inside the current trusted Pi session. A running agent never launches `pi -p`.

Every route uses the installed controller at `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py`. Preserve the manifest's `resourceIsolation` value. An `isolated-shell` campaign resumes with `jig init`. An `inherited-session` campaign resumes with `/skill:jig init` or `/jig init`.

Target-repository COMMANDMENTS are mandatory. Stop at `awaiting-commandments` until the target operator supplies one complete response and explicitly ratifies the displayed candidate digest. The controller may finish one first step as `kept`, `reverted`, or `no-eligible-candidate`. Never offer a second step or merge automatically.

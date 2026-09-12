# Pi overlay adapter

This file maps Cursor verbs onto Pi. It is process, not repository architecture. Initialize one whole Git repository with `/skill:jig init`.

## Verb map

`Task` is the `subagent` tool from pi-subagents. One child is `{ agent, task }`. Several children are one `{ workflowScript }` with `await runs.all`. Set `cwd` when the child must run in another tree. Do not run `pi -p` from bash. That nested process blocks the parent and has no fleet status. `--tools` that omit `subagent` is how that bash spawn happens. jig.sh is a human launcher and may pin tools. Agents inside Pi may not. `pi -c` continues a session. It is not cwd.

When delegation is needed, use only `{ agent: "poteto-agent", task }`. `install.sh` installs this child in `~/.pi/agent/agents/`, disables builtins, and retires the six old role profiles. Give the child a bounded implementation, investigation, or read-only task instead of selecting a different persona. Do not use a parallel worker+reviewer workflow as the default bug-fix loop. Tiny known-mechanism fixes stay parent-inline.

The child reads poteto-mode in full and decides reversible details without supervisor gates. It returns missing authorization or genuine product ambiguity in its normal result before taking the blocked action. New sessions see the installed settings and prompts. Existing children keep their old prompts until respawn.

Leave `async` on. That is the default. `async:false` only when this turn cannot continue without the child. Do not sleep-poll. Use blocking `subagent_wait` only when this turn must consume the result.

Use the parent's model for every child. Do not fan out across model types or select models by role. This policy overrides model defaults in imported skills and playbooks. Same-model parallel work is allowed for disjoint workstreams with separate ownership. Use parent-inline or sequential sketches for design alternatives, then let the parent pick if needed. No runner competition or judge is required.

Read architect, poteto-mode, and principle-exhaust-the-design-space from `__SKILLS_PSTACK__`, not raw pstack. Installation and refresh reapply these Pi-specific overlays. Other imported skills remain upstream copies subject to this adapter's model policy.

`TodoWrite` is `TODO.md` in the working tree. Do not register a todo tool.

Plan mode is `PLAN.md` in the working tree.

Use the built-in `read` and `edit` tools. Read the current file before editing. Match the exact text to replace.

Public web is `web_search` and `fetch_content`. `gh`, `git`, and `curl` cover private or authenticated URLs those tools cannot reach. Never MCP.

`/loop` is a one-shot prompt template, not a timer. For an async child, register `subagent_wait` with `nonBlocking: true` when you need a completion wake, then return control.

Never background bash. Use tmux if you need a long-running process that is not a subagent.

Keep the `read` tool enabled.

## Jig handoff

Use `jig init` from the human shell for a fresh resource-isolated Pi campaign. Use `/skill:jig init` or `/jig init` inside the current trusted Pi session. A running agent never launches `pi -p`.

Every route uses the installed controller at `${PI_CODING_AGENT_DIR:-${PI_AGENT_DIR:-$HOME/.pi/agent}}/jig/bin/jigctl.py`. Preserve the manifest's `resourceIsolation` value. An `isolated-shell` campaign resumes with `jig init`. An `inherited-session` campaign resumes with `/skill:jig init` or `/jig init`.

Repository Principles are mandatory. Stop at `awaiting-principles` until the target operator supplies one complete response and explicitly ratifies the displayed candidate digest. Pstack's `create-verification-skill` builds repository verification, and `maintain-verification-skill` keeps it current. Use `/skill:reflect` after later work to turn durable learnings into approved skill edits. Jig stops at `configured` and never selects or performs a product-code improvement.

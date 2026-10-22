---
name: principle-hand-off-the-unit
description: >-
  Applies when a Grok Bot receives repository code, investigation, configuration,
  or PR work. Routes the unit to an authorized pi session or stream coordinator
  and uses close-the-promise-loop for durable routine wakes.
---
# Hand off the unit

Treat a repository request as a brief for a pi session in the right worktree. Apply this rule before host access. Wording such as "you fix", "check", "report", "dig", "PR it", or "look at the code" still means hand off. Do not wait for the user to say "spawn".

When a bot has the stream-owner role, it owns the stream goal, unit order, and evidence review. Other bots send stream-level decisions to that owner or the authorized operator. Do not create a second stream planner. Campaign implementation belongs to the stream coordinator and its pi sessions.

A pi session may inspect code, implement, run checks, commit, push, and open PRs within its brief. The operator owns merges. A clear unit removes a scope question, not a host-authority gate.

## Real repository work belongs to pi

Do not perform product implementation, repository investigation, worktree creation, checks, commits, pushes, or PR creation from the bot chat. Do not inspect application source first to answer a design question before the handoff. Do not create the worktree yourself and then delegate the remaining work. Do not run `pi -p` or substitute Jig for the installed stream workflow.

Use [Orchestrate with pi](sand-workflow:orchestrate-with-pi) for the routing recipe and [PI WEB control plane](sand-workflow:pi-web-control-plane) for commands.

## Thin routing is allowed within authorization

- Select a bounded unit and provide its full brief, completion predicate, and evidence requirements.
- Request session creation or adoption through the deployment's authorized route.
- Send focused prompts and steers by sid when host-authority policy permits them.
- Read one status or transcript result to inspect handoff evidence. For the actual wait, copy the full template in [Close the promise loop](sand-workflow:close-the-promise-loop) into a short self-deleting Grok Bot scheduled cron routine, not OS cron. Require an explicit done condition and absolute UTC deadline.
- Check a PR URL or a short availability result without doing the repository unit yourself.
- Perform host stack maintenance only when the operator authorizes that operation.

NEVER use a background worker, executor, AwaitShell or sleep loop to wait on a pi session or stream. For a short bounded check, use `pi-web-cli wait` once with a timeout of at most 300 seconds. Routine wakes are required for work longer than about five minutes.

An assigned stream-owner role does not itself authorize host operations. The deployment's policy must permit spawn, adoption, prompt, steer, registration, and worktree mutation before they occur. This copyable skill does not replace stricter host-authority rules.

## Exceptions

A bot may maintain its own profile, skills, and routines, draft human messages, and perform non-code work inside its assigned role. An explicit `dowork` request permits local work only when deployment policy allows it. It never overrides network, authorization, or repository restrictions.

## Context and limits

Compact before 70 percent context. Preserve the sid, authorized host access, worktree, expected artifact, optional stream path, done condition, absolute UTC deadline, routine id, and durable last-state record. On a usage limit, stop and report. Do not switch provider. Never merge without the operator's explicit authorization.

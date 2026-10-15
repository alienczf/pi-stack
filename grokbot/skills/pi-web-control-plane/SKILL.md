---
name: pi-web-control-plane
description: >-
  Controls pi sessions through pi-web-cli using the bot's authorized PI host
  access. Use for session spawn, prompt, status inspection, steer, and routine
  handoff. Use pi-async-wait for waits instead of bot-side status polling.
---
# PI WEB control plane

Use PI WEB to create, prompt, inspect, and steer pi sessions. For a multi-thread campaign, prefer the host's pi-streams `/stream` workflow through its owning coordinator. Do not invent `pi exec` or `pi rpc`. Do not run `pi -p`, use intercom or `broker.sock`, or substitute Jig for streams.

Use whatever authorized pi-web-cli access this deployment provides. Run the commands on the PI host or through its existing access wrapper. Do not assume a host name, network route, wrapper path, or local access to the host's loopback API. This skill does not grant host authority.

## Commands

```bash
pi-web-cli list --cwd /absolute/worktree
pi-web-cli spawn /absolute/worktree
pi-web-cli prompt <sid> /poteto
pi-web-cli prompt <sid> "/goal <checkable predicate>"
pi-web-cli status <sid>
pi-web-cli prompt <sid> "<focused correction>" --steer
```

`prompt` reads stdin when the text argument is absent. `list` requires `--cwd`. `PI_WEB_URL` selects the API endpoint, defaulting to `http://127.0.0.1:8504` on the PI host. Do not call a browser SPA route and treat its HTML as an API response.

## Host records

- PI WEB owns the session API and session host.
- Session transcripts normally live under `~/.pi/agent/sessions/` on the PI host.
- `pi-streams` owns its registered project index and stream repositories.
- A stream repository's `STATE.md`, `ALERTS.md`, and `STREAM.md` carry campaign state. An empty global alert index alone does not prove health.

## Default orchestration

1. For a campaign, hand the full brief to the authorized stream coordinator. For a single unit, have pi create an isolated worktree and create or adopt its session.
2. Do not create code worktrees on the bot's disk. Do not share a dirty tree across units.
3. For a single session, send `/poteto`, then the work goal. Respect this deployment's prompt and host-authority gates.
4. After the accepted work prompt or steer, follow [Pi async wait](sand-workflow:pi-async-wait). Prefer a webhook routine. Use a deadline-bound, self-deleting cron routine if a webhook is unavailable. Never replace this handoff with a background worker, executor, AwaitShell, or sleep loop.
5. If a session is already live, target its sid rather than create a duplicate. Cancel an obsolete watcher before you rearm after a steer.
6. Have pi produce and open the PR within its brief. Do not merge. The operator authorizes merges.

A one-off status or transcript check can verify evidence. It is not a durable wake mechanism. A short check may use `pi-web-cli wait` once with a timeout of at most 300 seconds, per pi-async-wait.

Compact before 70% context. On a usage limit, stop and report without a provider change.

Policy is in [Hand off the unit](sand-workflow:principle-hand-off-the-unit). The routing recipe is in [Orchestrate with pi](sand-workflow:orchestrate-with-pi).

---
name: PI WEB control plane
description: >-
  Use when spawning, prompting, or checking pi sessions on options-01. PI WEB
  (127.0.0.1:8504 via pi-web-cli over Twingate SSH) is the control plane;
  pi-streams /stream is the campaign harness.
---
# PI WEB control plane

Use this whenever a Grok Bot must spawn, prompt, or poll a pi coding session on `hpc180-options-01`. PI WEB is the session control plane (spawn, prompt, status, steer). For multi-thread campaigns prefer **pi-streams** `/stream` ([Orchestrate with pi](sand-workflow:orchestrate-with-pi)). Do not invent `pi exec` / `pi rpc`. Do not `pi -p`. Do not use intercom / `broker.sock`. Do not use Jig.

SSH first over **Twingate userspace**: `/home/box/.local/bin/options-01-ssh` or `pi-web-cli-remote`. Then run commands **on the host**. `http://127.0.0.1:8504` is loopback only. Reach recipe: [Alphalab access](sand-workflow:alphalab-access).

## Lever

Remote: `/home/alphalab/.local/bin/pi-web-cli`  
Box wrapper: `/home/box/.local/bin/pi-web-cli-remote` (SSH via Twingate)

```bash
pi-web-cli-remote list --cwd /abs/worktree
pi-web-cli-remote spawn /abs/worktree
pi-web-cli-remote prompt <sid> /poteto
pi-web-cli-remote prompt <sid> "/goal <checkable predicate>"
pi-web-cli-remote status <sid>
options-01-ssh '/home/alphalab/.local/bin/pi-web-cli list --cwd /abs/worktree'
options-01-ssh 'PATH="$HOME/.local/share/pi-node/current/bin:$PATH" pi-streams doctor'
```

`prompt` accepts stdin if the text arg is omitted. `list` without `--cwd` fails: the API requires cwd.

Do not `POST /api/local/sessions` (SPA HTML). Do not curl 8504 from this computer.

## Host processes

- PI WEB UI/API: `127.0.0.1:8504`
- Session host: `pi-web-sessiond`
- Binaries: `/home/alphalab/.local/share/pi-node/current/bin/{pi,pi-web,pi-web-server,pi-web-sessiond}` (put on PATH for non-interactive shells)
- Session jsonl: `~/.pi/agent/sessions/--escaped-cwd--/<timestamp>_<id>.jsonl`
- Streams: `~/.local/bin/pi-streams`, index `~/.config/pi-streams`, timer `pi-streams-tick.timer`

## Default orchestration

1. Campaigns: `/stream` via pi-streams (coordinator + threads). Single units: one git worktree + `pi-web-cli spawn`.
2. Never create worktrees on this computer's disk. Have pi create them.
3. Single session: `prompt` `/poteto`, then `/goal <checkable predicate>`.
4. Check `status` once. To wait, use [Close the promise loop](sand-workflow:close-the-promise-loop) (self-deleting routine), never a background worker / AwaitShell / sleep loop. For streams, the routine reads the stream repo's `STATE.md` / `ALERTS.md`.
5. If already live, `prompt` again by session id. Do not use intercom.
6. Do not merge. `@claude` on a PR only when GitHub is usable.

Policy: [Hand Off the Unit](sand-workflow:principle-hand-off-the-unit). Flow: [Orchestrate with pi](sand-workflow:orchestrate-with-pi).

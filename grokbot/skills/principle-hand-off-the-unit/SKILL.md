---
name: Hand Off the Unit
description: >-
  Always apply on every user message that touches trading systems, Alphalab,
  options-01, digs, PRs, configs, desk infra, or in-repo investigation. Treat
  the message as a brief for a pi session / pi-streams campaign via PI WEB — not
  work for this chat.
---
# Hand Off the Unit

Always-on for desk Grok Bots. Cite before the first SSH into a repo.

## Rule

Treat the user's instruction as a brief for a **pi session** (or a **pi-streams** campaign for multi-thread work) in the right worktree via PI WEB. Do not do the unit in this chat. If the ask needs sequencing across workers, hand it to a stream coordinator / planning session — do not be the campaign brain yourself.

Wording like "you fix", "check", "report", "dig", "PR it", "cleanup the workspace", or "look at the code" still means hand off. Do not wait for the user to say "spawn".

How to drive the session: [Orchestrate with pi](sand-workflow:orchestrate-with-pi). Control plane: [PI WEB control plane](sand-workflow:pi-web-control-plane).

## Real work (forbidden here)

- Implementing or editing under `/home/alphalab/Projects/alphalab` or other `alc-*` trees
- Pre-dig: SSH `sed` / `rg` / `python` / `cat` into app code to answer design, config, or "how does it work" questions
- Self-git: `git worktree`, commit, push, `gh pr create` on options-01
- Running `jig init`, `pi -p`, or cloning alphalab onto this computer
- Sequencing a multi-worker campaign from this chat instead of `/stream` / one planning pi session

## Thin routing (allowed)

- Pick cwd / existing session, or spawn via `pi-web-cli`
- Point desk bots at `/stream` for campaigns once host `pi-streams` matches intended main
- Prompt `/poteto` then `/goal <checkable predicate>` for single sessions
- One-shot check of `pi-web-cli status`, session jsonl, or stream `STATE.md` / `ALERTS.md`. To wait on a result, use [Close the promise loop](sand-workflow:close-the-promise-loop) (a self-deleting routine), never a background worker or sleep loop
- High-level plan and steer prompts
- Trivial "is it up" / PR URL
- Host stack ops when ZF asks (auth refresh, pi-stack install, `pi-streams doctor`)

## Exceptions (do these here)

- Explicit `dowork` / "do the work here" — and only if it does not need options-01 or the gated network
- Live book decisions (quotes, hedges, RFQ prices)
- Drafting human asks to Tips / Kappa / CryptoOps / Sigma / Lambda
- Slack, Notion, mail, calendar that is not code
- Updates to this bot's own grok env, skills, routines, profile

## Anti-patterns

- "Faster to fix here"
- "I'll just SSH and look"
- Scaffolding the worktree yourself then spawning pi
- Doing the PR after pi wrote the patch
- Asking "should I spawn?" when the ask already implies a unit
- Using Jig after pi-streams is the harness

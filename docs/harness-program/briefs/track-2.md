/skill:poteto-mode

# Harness program, track 2: agentic CLI access to prime-agent

This is the /poteto entry point, loaded as the poteto-mode skill. Work in poteto style throughout.

**End state:** a WORKING prime CLI on branch `feat/prime-cli`, at parity with pi-web-cli for what pi-stack needs, and verified against a real prime-agent server. A design alone doesn't meet it. Make your own decisions and log them. Don't wait on ZF.

**Your two outputs:**
1. The design, `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/20-prime-cli-design.md`. Write this first, and don't commit it, because Grok Bot collects it.
2. The implementation, in the code worktree `/home/alphalab/Projects/worktrees/pi-stack-prime-cli` on branch `feat/prime-cli` (cut from main 3acf0f0). Commit there in small local commits. **Don't push**, because Grok Bot pushes. Touch no other branch.

## The problem

Grok Bot and the target box always sit on separate machines. Grok Bot reaches options-01 only via `options-01-ssh` (Twingate userspace SSH) and drives pi through `pi-web-cli` (on the host: `~/.local/bin/pi-web-cli`, a client for the PI WEB control plane at 127.0.0.1:8504; subcommands list, spawn, prompt [--steer|--follow-up], status, commands, stop, abort, queue-clear, archive, messages, model, thinking-level, answer, all JSON out). On the box, `pi-web-cli-remote` wraps that over SSH. pi-stack's skills and prompts (`stream`, `cross-repo`, `loop`) and pi-streams' tick also depend on that surface.

PrimeIntellect's prime-agent (https://github.com/PrimeIntellect-ai/prime-agent) is a self-improving RLM agent for coding and long-running autonomous tasks, with a long-running server. ZF wants agentic CLI and network access to it, with the **pi-web-cli command surface and the skills interface kept consistent**. Then the two cross-compatible with low changeover friction, and a skill or Grok Bot routine can switch backends without rewriting itself. **No GUI.**

## Do this

1. Study prime-agent: clone it under `~/Projects/` (or reuse an existing clone) and read its server API, session model, streaming, queueing and steering, compaction, auth and config. Read the prime-stack stream's files at `/home/alphalab/Projects/pi-stack/streams/prime-stack/` for prior context, **read-only**. Don't prompt its coordinator `01a16177-96a3-7923-bfe9-55fbc3774482`, because it is unratified and mid-kickoff.
2. Design (artifact 20):
   - Map **each** pi-web-cli command and its JSON shape to prime-agent's API (a table: command, pi semantics, prime equivalent, gap, shim).
   - List the requirements pi-stack actually depends on: spawn with a cwd, prompt/steer/follow-up, a status with isStreaming, pendingMessageCount and contextUsage, messages, model and thinking level, abort/stop, archive, list by cwd, and answer for interactive questions. Also list the gaps.
   - Propose the transport (SSH-tunnelled local HTTP like PI WEB, or another option, with reasons), auth (no secrets in git or in argv), and the remote wrapper (a `prime-cli-remote` that mirrors `pi-web-cli-remote`).
   - Choose a backend-neutral surface: one CLI name or a `--backend` flag, plus a skill-level contract, with each mechanism's LAYER per 02-principles.
   - Note that porting **streams** onto prime waits for track 1's fixes to land (P2), so it isn't in scope here. Say what the CLI must expose so that the later port is mechanical.
   - Open question for ZF, **non-blocking**: caladan. pi-stack has no caladan branch, and pi-bot has `caladan` at bb39dc0. Say what, if anything, in it matters for this CLI. Read pi-bot's caladan branch from `~/Projects/pi-bot` or the `~/Projects/worktrees/pi-bot-caladan-*` worktrees, read-only.
3. Implement on `feat/prime-cli`, for example as `bin/` plus a small module, with the same packaging pi-stack uses for its other tools. Add tests that run without a network, plus a real-server check script.
4. Verify against a **real** prime-agent server that you run yourself on options-01 under your own user (no sudo, no system services, and no secrets printed or committed). Use the same provider and model, openai-codex/gpt-6.1-sol, if prime-agent can be pointed at it. If it can't run without credentials you don't have, stop at that point and report exactly what's missing. Do the end-to-end check for each mapped command and record the transcript (small text) in the design doc's Verification section.
5. End the design doc with **Decisions** (each with a reason), the **Gaps** left open, and a **Parity checklist** marking each pi-web-cli command as done, shimmed or missing.

Expect about 2–4 hours. If a usage limit stops you, stop and report, with no provider switch.

## Common rules (all three harness-program tracks)

You are one of three parallel sessions in ZF's **harness program** for pi-stack, started 2026-10-23 by Grok Bot. Grok Bot owns every decision in this program. Make your own calls, log each one in your artifact's "Decisions" section with a short reason, and don't wait on ZF.

**Read first, in full:**
- `docs/harness-program/00-brief-verbatim.md`, ZF's brief. A ~4.5k-character gap in it is marked; don't guess at its content.
- `docs/harness-program/01-scope.md`, the three tracks and how they're ordered.
- `docs/harness-program/02-principles.md`, layer affinity. Every mechanism you propose gets `LAYER n` plus a reason.
- `docs/harness-program/03-decisions.md`, D1–D9, P1–P7 and G1–G12.

These files are in the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program` (branch `docs/harness-program`). A copy is in `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/context/harness-program/`.

**Evidence base** (all under `/home/alphalab/Projects/pi-stack/streams/pi-streams-harness/`):
- `context/stall-corpus-2026-10-22.md`: 75 ZF steering rows, F1–F12
- `context/interrogations/A-mechanical-2026-10-22.md`, `B-goal-integrity-2026-10-22.md`, `C-control-loop-2026-10-22.md`
- `context/research/deep-research-2026-10-23.md`
- `context/updates/2026-10-22-1743-sgt/issue-3{3,4,5,6}.json`, the pi-stack issues #33–#36. `gh` may be unauthenticated on this host, so use these snapshots.
- `DECISIONS.md` and `context/zf-brief.md`
- the pi-stack source in your cwd `/home/alphalab/Projects/pi-stack/pi-stack` (main @ 3acf0f0), mainly `pi-streams/`, `overlay/`, `skills/`, `prompts/`, `docs/design/`. The installed copy is `~/.pi-stack`.
- live stream repos under `/home/alphalab/Projects/alphalab/streams/` and `/home/alphalab/Projects/pi-stack/streams/`, read-only. Sample big files (the 654 STATE.md is 10 MB) with head, grep and wc. Never cat them whole.

**Hard limits:**
- Don't prompt, steer, stop, rotate, archive or spawn any *other* existing session or stream. That covers the pi-streams-harness coordinator and the prime-stack coordinator `01a16177-96a3-7923-bfe9-55fbc3774482`. Run only `pi-streams status`/`doctor` against streams. You may use your own subagents on the same model (openai-codex/gpt-6.1-sol).
- Don't push to GitHub, open PRs, or comment on issues. Grok Bot is the only pusher. Commit locally on your own branch only where your track says so.
- Touch no auth or credentials, and never print tokens or secrets.
- On a usage limit or quota error, **stop and report** in your final message. Never switch provider or model.
- No default budgets or caps (D1). Git holds code, docs and small reports, never data.
- Only edit the files your track names. Leave everything else in the docs worktree alone, because the other tracks share it.

**Status line.** When you finish (or stop), end your final reply with one line:
`TRACK <n> STATUS: <done|blocked|partial> | artifact=<path> | next=<one line>`
Grok Bot reads that line and updates `docs/harness-program/STATUS.md`. Don't edit STATUS.md yourself.

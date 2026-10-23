# 03 — Decisions

ZF's decisions are recorded first, with their source. Grok Bot's own calls follow. Under ZF's 09:12 SGT update, Grok Bot owns all decisions in this program and ZF is not carded. Each call has a short reason. Later calls get the next G number, and superseded calls stay with a `SUPERSEDED by Gn` note.

## ZF decisions D1–D4 (2026-10-22 17:43 SGT, pi-stack #33–#36)

- **D1, #33.** Reject default resource and token budgeting as context bloat. It's opt-in at most. Remove kickoff Q5's demand to "get each cap as a number", and stop coordinators inventing CPU, RAM and disk guards.
- **D2, #34.** The coordinator context target is 252k, down from about 484k effective. ZF left the mechanism open, and G4 below sets it.
- **D3, #35.** Compact-and-continue vs compact-and-spawn-new is a design question, not instrumentation. Recommend separately for coordinators and threads.
- **D4, #36.** Old-session artifacts are an artifact-management design question, not instrumentation. D7 reframes it.

## ZF answers, 2026-10-23 08:52 SGT (D5–D9 in the pi-streams-harness stream)

These are numbered to match section 4 of the deep-research report.

1. "Sure let's go." This is **D5**: implementation is authorized in principle. At 09:09 SGT ZF withdrew the research build plan as the goal, and this program replaces it.
2. "What failure are we considering". The question was open, and **G5** decides it.
3. "Assume it never happens. Stream owns whatever that's in its own work tree folders. When using other repos as tools, grab the artifacts and park them back under owned worktree or risk losing it". This is **D6**, with no precedence machinery.
4. "I think it's more useful to design how/when to compact/review ruleset". This is **D7**: #36 becomes the compaction and ruleset-review design. Nothing deletes transcripts automatically.
5. "Yes stream show know more than I do. But I do want to know what I asked for, so concat findings?" This is **D8**: report each ask, its status and its concatenated findings.
6. "I think these are impossible to define without some kind of workflow definitions?" This is **D9**: independent review waits for a minimal workflow-definition shape, which goes to track 3.

## ZF program decisions (2026-10-23 09:09 and 09:12 SGT)

- **P1.** There are three tracks, per `01-scope.md`. Track 1 fixes pi-streams itself first.
- **P2.** Porting streams onto prime waits for track 1 to land.
- **P3.** Proposals that are too frameworky are pushed back. Review pi-stack's own principles and playbooks first.
- **P4.** Layer affinity, per `02-principles.md`, governs every fix and design.
- **P5.** Track 1's catalog is ZF's only review point. After his go-ahead: implement, merge to main, and rebase every branch.
- **P6.** Track 2's end state is a working prime CLI on `feat/prime-cli`, verified against a real prime-agent server.
- **P7.** Grok Bot owns all decisions. Log them here and don't card ZF.

## Grok Bot calls

- **G1. Where the program lives.** It lives in GitHub, on branch `docs/harness-program` of alienczf/pi-stack under `docs/harness-program/`, as a draft PR that's never merged without ZF. A tracking issue "Harness program" carries a checklist per track. `/workspace/harness-program/` on the Grok Bot box mirrors it, and `context/harness-program/` in the pi-streams-harness stream holds a read-only input copy. *Reason:* the pi-streams-harness stream is the broken thing, so it can't be the program's memory. GitHub survives every host and session. The box mirror lets every Grok Bot read it without a network round trip.
- **G2. Who writes to git.** Track sessions write artifact files in host worktrees and commit locally. Only Grok Bot pushes, from the box, using the pi-bot HTTPS credential, and pulls the files or bundles through `options-01-ssh`. *Reason:* the host holds no pi-bot GitHub credential, and a single pusher avoids concurrent pushes to one branch.
- **G3. Host worktrees.** The docs worktree is `/home/alphalab/Projects/worktrees/pi-stack-harness-program`, on branch `docs/harness-program`. The track 2 code worktree is `/home/alphalab/Projects/worktrees/pi-stack-prime-cli`, on branch `feat/prime-cli` cut from main 3acf0f0. The main clone stays at main. This follows the host convention `~/Projects/worktrees/<repo>-<name>`. *Reason:* the sessions' cwd remains the pi-stack clone, as briefed, while their writes stay isolated per D6.
- **G4. How 252k is enforced (D2).** The harness imposes it: the coordinator compacts in place at a request-boundary check of 252k, with no user check. Threads keep pi defaults for now. *Reason:* principle "impose and measure". ZF named only the coordinator. Measure in the wild, then revisit threads.
- **G5. Same-provider auto-recovery (ZF's decision 2).** Grok Bot decision, 09:15 SGT: **ADOPT all five classes as drafted.** This replaces stop-and-report as the pi-streams *harness* default.
  1. Codex usage limit: wait for the reset time, retry the saved step once, otherwise re-park.
  2. Expired Codex login: alert once, never touch credentials, and resume on a real sign-in signal or ZF saying "auth fixed".
  3. Tool login expiry, such as gcloud: park only the affected lane, resume when that login check passes, and reconcile submitted jobs before retrying.
  4. Full disk: report the path and owner, with no cleanup and no caps. Resume when the write probe succeeds, and send the alert from off-host.
  5. Other model errors: park them under their own label.
  Across all five: never switch provider, never re-run an uncertain job, and never resume cancelled or gated work. *Reason:* ZF wants streams that march without him as the clock, and the corpus shows stop-and-report causing about 10 of the 75 stalls. The *operator* rule for Grok Bot and these program sessions is unchanged: on a usage limit, stop and report.
- **G6. Track 1 implementation.** After ZF's go-ahead, track 1 is implemented by a fresh pi session on a branch stack. The pi-streams-harness stream doesn't do it. *Reason:* its tick and coordinator are the subject of the fixes. The stream stays parked at `ratified: no` until track 1 lands.
- **G7. Track 2 verification target.** The session runs prime-agent's server itself, under its own user on options-01 with no sudo, and checks it end to end through the remote wrapper from the Grok Bot box. No credentials or data go in git. *Reason:* "real server" is the bar, and options-01 is the target box.
- **G8. Caladan.** Track 2 builds from pi-stack main. Caladan (pi-bot caladan at bb39dc0, with no pi-stack branch) is an open question for ZF and doesn't block. *Reason:* nothing in the CLI surface depends on it.
- **G9. prime-stack stream.** Leave its coordinator `01a16177` untouched. Track 2 may read its files, but doesn't prompt it. *Reason:* it is unratified and mid-kickoff.
- **G10. Session model.** openai-codex/gpt-6.1-sol at xhigh, cwd `/home/alphalab/Projects/pi-stack/pi-stack`, entered through `/poteto`. Subagents use the same model. *Reason:* ZF's brief. Same provider only.
- **G11. Brief integrity.** Each brief is copied to the host as a file and then sent as the prompt text. The SHA-256 of the user message received is checked against the file. *Reason:* an earlier stdin send dropped content.
- **G12. Gap in 00.** `00-brief-verbatim.md` marks about 4,482 elided characters explicitly rather than reconstructing them. *Reason:* verbatim means verbatim, and the parent conversation can fill the gap.
- **G13. /poteto entry.** Sessions start with `/skill:poteto-mode` followed by the brief, which is what the `/poteto` prompt loads. *Reason:* the `/poteto` prompt template takes no arguments, so a brief appended to it could be dropped. The skill form carries the brief in the same message, as the earlier interrogations did.
- **G14. pi-streams-harness goal reset.** That stream has D5–D9 recorded, its interview is fully pending, and its DECISIONS.md has a stale "Resume at GOAL" section. When track 1's must-fix plan is ratified by ZF's go-ahead, reset that stream's goal from `01-scope.md`, and retire the stale section at the same time. Until then, leave it parked. *Reason:* one goal source, and no restarting a kickoff that the scope will change again.
- **G15. Remote tooling.** `pi-web-cli-remote` restarts Twingate on every call (`--ensure-tg`) and causes SSH banner timeouts. Use `options-01-ssh` without `--ensure-tg` for repeated calls, and restart Twingate only when a call fails to connect. This is a track 1 fix candidate. *Reason:* observed timeouts on repeated calls.

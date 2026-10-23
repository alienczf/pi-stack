# 03 — Decisions

ZF's decisions are recorded first, with their source. Grok Bot's own calls follow. Under ZF's 09:12 SGT update, Grok Bot owns all decisions in this program and ZF is not carded. Each call has a short reason. Later calls get the next G number, and superseded calls stay with a `SUPERSEDED by Gn` note.

## ZF decisions D1–D4 (2026-10-22 17:43 SGT, pi-stack #33–#36)

- **D1, #33.** Reject default resource and token budgeting as context bloat. It's opt-in at most. Remove kickoff Q5's demand to "get each cap as a number", and stop coordinators inventing CPU, RAM and disk guards.
- **D2, #34.** The coordinator context target is 252k, down from about 484k effective. **SUPERSEDED by Z3** (dump, compact, resume at >= 150k).
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

## ZF first-pass calls on "what actually breaks" (t211u, 2026-10-23 09:22 SGT)

These were relayed by the parent Grok Bot. ZF's words are in `00-brief-verbatim.md`, and more calls are coming. The track 1 catalog is not sent for review until it reflects all of them.

- **Z1. Fix tick liveness.** When a stream is being driven, the tick aggressively pushes it forward and turns unfinished work into the next action, instead of only relaying changes. This is a track 1 item. Quota and auth recovery stays a separate item under G5.
- **Z2. Lifecycle design goes to track 3.** Per-ask lifecycle, the coordinator grading its own homework (context decay), and constraint lifetimes belong to the lifecycle workflow design. They move to track 3, not track 1.
- **Z3. Context policy: dump, compact, resume. SUPERSEDES D2's 252k target and G4.** On every tick where the coordinator is taking a turn and its context is >= **150k**, the tick doesn't kill or interrupt it. Instead it runs one three-in-one action:
  - (a) DUMP: the agent updates STATE.md, TODO and all relevant stream status and progress artifacts, and writes its own resume prompt for the same session after compaction.
  - (b) COMPACT the same session.
  - (c) RESUME it with that resume prompt.
  Prefer compacting early; ZF will watch token use from outside. Issue #34 is updated to match.
- **Z4. Alerts and waits go to ZF by Slack DM, as quietly as possible.** The format is `<stream-id>:: <message>`, sent to ZF only. BossOps was dropped. Keep them as quiet as possible to avoid notification fatigue. This sets the alert route for G5.
- **Z5. Steer delivery acknowledgement stays in track 1.** An ack counts only once the coordinator has consumed and applied the steer. "Accepted for transport" doesn't count.

## Grok Bot calls

- **G1. Where the program lives.** It lives in GitHub, on branch `docs/harness-program` of alienczf/pi-stack under `docs/harness-program/`, as a draft PR that's never merged without ZF. A tracking issue "Harness program" carries a checklist per track. `/workspace/harness-program/` on the Grok Bot box mirrors it, and `context/harness-program/` in the pi-streams-harness stream holds a read-only input copy. *Reason:* the pi-streams-harness stream is the broken thing, so it can't be the program's memory. GitHub survives every host and session. The box mirror lets every Grok Bot read it without a network round trip.
- **G2. Who writes to git.** Track sessions write artifact files in host worktrees and commit locally. Only Grok Bot pushes, from the box, using the pi-bot HTTPS credential, and pulls the files or bundles through `options-01-ssh`. *Reason:* the host holds no pi-bot GitHub credential, and a single pusher avoids concurrent pushes to one branch.
- **G3. Host worktrees.** The docs worktree is `/home/alphalab/Projects/worktrees/pi-stack-harness-program`, on branch `docs/harness-program`. The track 2 code worktree is `/home/alphalab/Projects/worktrees/pi-stack-prime-cli`, on branch `feat/prime-cli` cut from main 3acf0f0. The main clone stays at main. This follows the host convention `~/Projects/worktrees/<repo>-<name>`. *Reason:* the sessions' cwd remains the pi-stack clone, as briefed, while their writes stay isolated per D6.
- **G4. SUPERSEDED by Z3.** How 252k is enforced (D2). The harness imposes it: the coordinator compacts in place at a request-boundary check of 252k, with no user check. Threads keep pi defaults for now. *Reason:* principle "impose and measure". ZF named only the coordinator. Measure in the wild, then revisit threads.
- **G5. Same-provider auto-recovery (ZF's decision 2). NARROWED by Z11: only the usage limit stays wait-and-retry; classes 2–5 take the Z11 park-and-F-DCR path.** Grok Bot decision, 09:15 SGT: **ADOPT all five classes as drafted.** This replaces stop-and-report as the pi-streams *harness* default.
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
- **G16. "#37" means corpus row 37.** In the research and in the track 1 brief, "#37" (the evidence-path archive bug) refers to row 37 of the stall corpus, the 654 receipts held in an archived session. It isn't a GitHub issue, and pi-stack #37 is this program's draft PR. The briefs stay byte-identical to what was sent. *Reason:* to avoid a false cross-reference.

## ZF calls on the tick, DCR and the state/history structure (t212u, 2026-10-23 09:56 SGT)

ZF's decisions, restated. His words are in `00b-zf-messages-verbatim.md`, section t212u. Binding on track 1.

- **Z6. Drive-mode tick re-injects the goal.** While a stream is driven, whenever the tick sees a stalled session or stream it always re-injects `/poteto-mode <current goal>`. Re-injecting is always safe, so the tick does not try to detect why it stalled (token allocation and so on). Remedies happen autonomously at the stream level, not the session level. (t212u)
- **Z7. Goal model.** Each stream has exactly one North Star objective. It mutates over time and is never marked completed or uncompleted. Under it sits the current (immediate) objective, and under that the parallel worker sessions. (t212u)
- **Z8. DCR (dump, compact, resume) is one action. Refines Z3.** (1) Sync the current stream state into the local artifacts. (2) Compact the same session. (3) Resume with a fixed template prompt that first tells the agent to read the current-state artifacts, by path, and then `/poteto-mode <current goal>`. The 150k trigger from Z3 still applies. The fixed template with a load-state step replaces Z3's free-form, agent-written resume prompt. (t212u)
- **Z9. State and history structure.** The current-state artifact is append-only, with one entry per completed piece of work or failure mode hit. Each entry is a `### <timestamp> <one-line commit-style subject>` header, then a body with as much context as the agent finds relevant, like a git log. It keeps only the most recent entries. The tick rotates the overflow into a history folder, one file per rotated entry, named with a timestamp prefix plus a slug, so `ls` gives the chronological summarized history and an agent opens specific files for detail. This mirrors skill loading. ZF considered and dropped history_full/history_index files and a git-commit store. Names, cap and the fate of STATE.md/STREAM.md are G17. (t212u)
- **Z10. Two fix classes.** (a) Mechanical failures and (b) artifact health. Track 1's catalog must address both. (t212u)

- **Z11. Physical and environment failure modes: park, alert, then F-DCR.** SSO, auth or login, disk or resource exhaustion, and outages. The human resolves these; agents don't. (t213u)
  1. On hitting one, log the last good turn id (the last unbroken turn before the failure) for the stream and for every affected spawned worker session, one file per session, e.g. `failures/<session-id>.lastgood`. The file existing means "parked on failure", and its content is the last good turn id. Several can exist at once. pi has turn ids, and prime should too; the design must verify both.
  2. Default: never touch the harness environment. No new rules, skills or memory are written in response to the failure, because that causes behavior drift. The only exception is when the human's ratification message explicitly asks for it, and then that content goes into the continuation prompt.
  3. Alert ZF in the Z4 format. ZF fixes the issue and then sends a ratified notice.
  4. On ratify, run **F-DCR** (fork, dump, compact, resume): fork the session at the last good turn id, then run DCR (Z8) on the fork, treating the failure like a provider outage. Once the fork is confirmed streaming, delete the original session and its error-handling turns (noise; the fork keeps everything before the failure), then remove the lastgood file.
  Layer: tick/engine code for detect, record, fork, DCR and wipe; the re-injected stream prompt carries "don't self-remedy env failures, park and log". Interaction with G5: a usage limit stays wait-and-retry; the other classes now take the F-DCR path. **Z11 narrows G5** for classes 2–5.

- **Z12. Track 3 designs from five inputs; ZF's remedies are candidates, not truth.** The high-level design session (track 3, `01a16658`) takes five inputs: (1) the local failure corpus and interrogations A/B/C, (2) ZF's remedies Z1–Z11 as candidates, (3) the balance of local failures no ZF remedy covers, (4) the internet corpus plus the deep research (its evidence, not its framework), (5) pi-stack's guiding principles. It produces three proposals with pros and cons, plus any blocking decisions for ZF. ZF's remedies get the same rigor as everything else, and the design session decides whether any proposal incorporates them. (t214u, paraphrased)

**ZF done dictating candidate fixes, 2026-10-23 10:01 SGT.** Z11 closes his three-part list (continuation: Z6/Z8; state: Z9; failure modes: Z11). The track 1 catalog can now go to first-pass review once it reflects Z1–Z11.

## Grok Bot calls (continued)

- **G17. Z9 names, cap, and what happens to STATE.md and STREAM.md.** Grok Bot decision, 09:59 SGT.
  - Current-state file: **`ACTIONS.md`** in the stream folder. History folder: **`history/`** next to it, one file per rotated entry named `history/<YYYYMMDDTHHMMZ>-<slug>.md` (UTC, so `ls` sorts chronologically). *Reason:* "STATE" is the misnomer ZF named; an action log is what Z9 describes. `history/` can't be read as "to-do actions", and it doesn't collide with `log/`, which is tick machinery and gitignored.
  - Cap: **30 entries** in `ACTIONS.md`; the tick moves the oldest overflow to `history/` on every tick, the agent never does. *Reason:* ZF's first number; entries carry free-length bodies, so the smaller cap protects the per-turn load. Measure, then revisit.
  - **STATE.md is retired.** Migration: split today's STATE.md at its `##` headers into `history/` files (timestamp from git log of that section, else the migration time), seed `ACTIONS.md` with one migration entry, then delete STATE.md. Engine and template references (AGENTS.md step 1/5, `rotate_coordinator`'s "Read STATE.md", kickoff Plan step, `PROTECTED_STREAM_FILES`) move to ACTIONS.md.
  - **STREAM.md stays the ratified charter**, and its GOAL section is Z7's North Star. Add one `CURRENT` section (one paragraph, the immediate objective) that the coordinator may rewrite in place; everything else stays ZF-only. Amendment paragraphs that accreted under `ratified:` move to DECISIONS.md, leaving STREAM.md as the current charter only. The DCR template and Z6 re-inject use `CURRENT`, falling back to GOAL. *Reason:* one goal source the tick can read mechanically, without a new file.
  - Track 1 may refine the mechanics, but not the names or the cap, without logging a new call here.
- **G18. Track 1 stays the MVP path, not blocked on track 3.** Grok Bot decision, 10:08 SGT. Track 1 implements Z1–Z11 as ZF dictated them. In the track 1 first-pass review, each Z-derived fix carries track 3's verdict (adopt, modify or reject, with its reason) when one exists by then; otherwise it is marked "no track 3 verdict yet". The review is not held for track 3. *Reason:* ZF's end state is fixes landed on main without blocking on him or on research. Z12 makes his remedies candidates for the design, not for the MVP, and a later track 3 verdict can become a follow-up fix.

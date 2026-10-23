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
- **G19. Track 1 compacted at 86.8% context, mid-amendment.** Grok Bot decision, 10:27 SGT. Aborted the turn, cleared the unconsumed steer-3 follow-up, ran `/compact` through PI WEB `POST /api/sessions/<sid>/commands/run` (plain `prompt "/compact"` is sent as chat text and does not compact), then sent `briefs/track-1-reentry-1.md` (brief + phase + steer-3 folded in), consumed 10:34 at 9.8% context. *Reason:* the 85% session-care rule; letting steer 3 start at ~88% risked an uncontrolled overflow mid-edit, and catalog edits were already on disk.
- **G20. Track 1 review and track 3 designs go out together; track 2 parks on Prime login.** Grok Bot decision, 11:00 SGT. Track 1 reported complete at 10:54 with Z1-Z11 covered, track 3 verdicts attached and O1-O4 defaulted, so the one-time first-pass review goes to ZF now (all Z calls are older than 30 minutes). Track 3 reported done at 10:32, so its designs milestone goes in the same message. Track 2 hit `No API key found for openai-codex` on the real Prime server: an interactive provider login only ZF can do, sent once as a blocker. Until then track 2 closes non-inference parity gaps (steer 1, consumed 10:59). feat/prime-cli `bccf159` pushed by Grok Bot. Where track 3 conflicts with Z11 (it recommends archiving rather than deleting the failed original), track 1 keeps Z11 as dictated under G18 and the conflict is listed for ZF. *Reason:* both milestones are ready; holding either adds nothing, and a credential login is outside what Grok Bot may do.

## Z13 (ZF t215u, 2026-10-23 11:26 SGT) + G21 (Grok Bot)
- Z13: ZF finds the artifact set too heavy. Only the artifacts pi-stack itself defines are in scope.
- G21 (Grok Bot's call): scope the catalog to the pi-stack-defined artifacts only. Drop the coordinator-invented files (ALERTS.md, decisions.tsv, ad-hoc log/ and analysis dirs) from the design. Stop reading them, and have fix 12 just stop referencing them: no migration, no ownership work. Fix 17 is out of scope (data dirs aren't pi-stack's); remove it from the catalog. Within pi-stack, split artifacts into three tiers and keep the always-loaded tier tiny. (1) Read every turn: AGENTS.md, STREAM.md (North Star + CURRENT), ACTIONS.md. (2) Read on demand: DECISIONS.md, history/, context/ (README is an index), checks/, handover/. (3) Engine-only, never read by agents: threads.tsv, subscriptions.tsv, stream.toml, log/events.jsonl, log/tick-state.json, the streams.tsv and projects registry, locks. TODO.md and PLAN.md come from pi-stack's global overlay: inside a stream, decide in the catalog whether ACTIONS.md + CURRENT replace them (default: yes, the stream template disables them). The track 1 catalog gets an amended artifact section, plus a tier table in 11-artifact-map.md. Steer track 1 with this as a catalog amendment and note it to ZF when done. Not yet steered: the driver should steer it.

## Z14 (ZF t216u, 2026-10-23 11:29 SGT) + G22 (Grok Bot), supersedes the file names in G17 and G21
- Z14: artifact names must be obvious and impossible to confuse with each other. STREAM vs STATE, or ACTIONS vs STREAM, don't work. Prefer plain words like state and history.
- G22 (Grok Bot's call). Every turn loads three files: AGENTS.md (role), GOAL.md and STATE.md. history/ and DECISIONS.md are read only on demand. Names:
  - `GOAL.md` replaces STREAM.md. It holds the North Star and the current objective, plus the ratified charter text.
  - `STATE.md` keeps its name but changes meaning: an append-only `### <ts> <subject>` log capped at 30 entries. It replaces the proposed ACTIONS.md.
  - `history/<UTC ts>-<slug>.md` is the rotated overflow.
  - DECISIONS.md stays as is.
- Migration: rotate old STATE.md content into history/, start a fresh STATE.md, rename STREAM.md to GOAL.md, and move STREAM amendments into DECISIONS.md.
- Naming rule for the catalog: no two stream files may share a concept. Each name answers one question: GOAL (what we want), STATE (what just happened), HISTORY (what happened before), DECISIONS (what ZF ruled).
- Apply this across the catalog, 11-artifact-map.md and the templates, and check every name in the tier table against the rule. Not yet steered: the driver should steer it along with Z13.
- **G21. Track 2 compacted at 84.5% context.** Grok Bot decision, 11:31 SGT. Aborted the turn, ran `/compact` via PI WEB `commands/run` (down to 19.1%), queued `briefs/track-2-reentry-1.md` (brief + steer-1 phase). Pushed feat/prime-cli `29ff206`. *Reason:* 84.5% of 500k is ~422k, nearly 3x the Z3 150k line and at the 85% session-care rule; the next tick is 30 minutes out and the session was still growing, so compacting now beats an overflow mid-edit.

## Z15 (ZF t220u, 2026-10-23 11:33 SGT) + G23 (Grok Bot). Supersedes the layout in G17, G21 and G22
- Z15: one file, always loaded. STATE.md has three sections, in this order:
  1. `## Goals`: the single mutable North Star plus the current objective.
  2. `## Rules`: decisions that are still in force, meaning ZF's rulings that act as rules conditioning the state.
  3. `## Log`: the append-only `### <ts> <subject>` entries, capped at 30.
- G23 (Grok Bot's interpretation of ZF's speech-to-text):
  - "locks" = logs.
  - Every turn loads AGENTS.md (role) and STATE.md. That's all.
- Retired:
  - GOAL.md and STREAM.md. The ratified charter text either moves into Goals or becomes the first history entry.
  - DECISIONS.md.
- history/ holds one file per entry, named `<UTC ts>-<slug>.md`. It takes:
  - log entries that rotate out,
  - superseded or retired rules,
  - historical decisions,
  - ZF steers.
  No tag field is needed, because the slug and the body carry enough. A ZF steer is logged as a Log entry when it arrives, so it reaches history through normal rotation.
- Rule lifecycle:
  - A new ruling lands in Rules and gets a Log entry.
  - When a ruling is superseded, it is removed from Rules and its text goes to history in a file named like `<ts>-rule-retired-<slug>.md`.
- Migration:
  - Split STREAM.md into Goals, active rules, and history.
  - Move DECISIONS.md entries that are still in force into Rules, and the rest into history.
  - Move old STATE.md into history.
- Only the Log section is capped. Rules must stay short. The Goals and Rules sections are rewritten in place, never appended.
- The catalog, 11-artifact-map.md and the templates follow this. Not yet steered; the driver steers it together with Z13 and Z14.

## GO (ZF t221u, 2026-10-23 11:35 SGT): track 1 go-ahead
- ZF gave the go-ahead on the track 1 first-pass review. That covers the catalog as amended by Z13, Z14 and Z15 (Z15's single STATE.md layout wins over Z14 and G22). It authorizes implementing the stacked plan, merging to alienczf/pi-stack main, rebasing the live branches and verifying.
- ZF didn't answer track 3's two decisions, so the defaults stand: task meaning goes with proposal A (track 3 work, not part of this MVP), and the Z11 delete-after-fork-streams stays as he dictated.
- At 11:35 the parent dispatched the Z13 to Z15 amendment steer plus the go-ahead to track 1. The driver should check whether it was consumed and re-send only if it was lost, not dispatch it a second time.
- Dispatch record (Grok Bot, 11:38 SGT): checked first; no 11:35 steer had reached the session (its last user message was still re-entry-1 from 10:35), so this is the first and only send. Track 1 was idle at 33.9% context (169.5k of 500k), so no compact. Sent `briefs/track-1-go.md` (sha256 aaa62d2f) as a normal prompt at 11:38:50; consumed, byte-matched as the last user message, streaming at 35.7% (the brief header says 11:45, a typo for 11:38). Track 1 phase = implementing.
- **G25. Track 1 implementation shape.** Grok Bot decision. Code branch `feat/streams-must-fix` off pi-stack main `3acf0f0` in worktree `/home/alphalab/Projects/worktrees/pi-stack-streams-must-fix`; pi-web source changes the stacks name go on a same-named local branch of the pi-web source checkout. S2a (migration) is part of the run, between S2 and S3. External prerequisite E (Twingate wrapper) is Grok Bot's on the box, not track 1's. The session keeps a progress file `docs/harness-program/12-track-1-progress.md` in the docs worktree so a compact or re-entry loses nothing, and collect.sh now also pulls it and `11-artifact-map.md`. Disposable verification runs under its own pi-web port and XDG dirs and never touches the live 8504 pi-web, the systemd tick, `~/.pi-stack` or `~/.local/bin`. Credentials are read in place, never copied; if isolation would need a copy, it stops and reports. *Reason:* one named branch the driver can merge, a re-entry path that survives compaction, and no shared state between the test instance and live streams.

## Z16 (ZF t222u, 2026-10-23 11:36 SGT) + G24 (Grok Bot)
- Z16: ZF challenges whether A is just the output of C, and asks what would make C trigger consistently.
- G24 (Grok Bot's call): ZF is right. A and C both use markdown records plus a structural checker. The only real difference is who creates the per-ask record. In C, the coordinator writes a TODO row, and that's a rule or playbook (layers 4/5), so an ask nobody wrote a row for can't be detected. In A, intake code creates the record before dispatch, with the verbatim source and its hash (layer 3), so CI can fail an open ask that has no record. Making C trigger consistently needs exactly that intake hook, and adding it turns C into A.
- Decision: collapse A and C into one design. Use C's minimal shape: no work/ directory, no per-ask state machine. Each ask is a row or entry produced by intake code from the message identity, and a checker fails any intake id that has no row.
- Track 3 should redo the doc as this merged design plus B, against Z15's layout. The layout is one STATE.md with Goals, Rules and a capped Log, plus history/. The current doc still uses the superseded STREAM, ACTIONS and history names, so it must be updated. Decide where the ask rows live: a `## Open asks` section in STATE.md, or the Log plus a checker. Default: an `## Asks` section in STATE.md between Rules and Log, rewritten in place, with rows moved to history when closed. List any blocking decisions with defaults.
- Superseded by Z19 (G24 withdrawn); track 3 steered on Z19 at 11:55. No steer needed (G27).

## Z17 (ZF t223u, 2026-10-23 11:37 SGT): design not locked
- ZF: "No decisions for design yet. We're still iterating."
- So nothing in track 3 is decided. G24 (collapse A/C) is now a working draft direction for the next iteration, not a decision.
- The GO entry's line "track 3 defaults stand" is withdrawn. Proposal A is not chosen.
- The Z11 delete-after-fork stays in the track 1 MVP only because ZF dictated it, not as a design ruling.
- When the track 3 revision goes to ZF, frame its "blocking decisions" as open questions for the next iteration, with no defaults applied.

## Z18 (ZF t224u, 2026-10-23 11:46 SGT): track 4, B over prime
- ZF wants an independent session to check how proposal B (runtime-owned obligations and hooks) could be built on top of prime. Prime is durable, so hooks might be easy to set up.
- G26 (Grok Bot): this becomes track 4. It's a feasibility and design spike, not a merge.
  - Spawn a fresh pi session on options-01 in project pi-stack (openai-codex/gpt-6.1-sol, xhigh), in its own worktree on a new branch `spike/b-over-prime` off main.
  - Inputs: 30-research-designs.md (proposal B), 20-prime-cli-design.md, the feat/prime-cli branch, and the prime-agent source and docs on options-01.
  - Deliverable: `docs/harness-program/40-b-over-prime.md`. It covers which prime primitives exist (durable session store, events, hooks or extension points, turn ids and fork). It maps each B mechanism to a prime primitive or a gap, with a minimal hook prototype where cheap, verified against the local prime server without inference.
  - It also gives an effort estimate and the risks, and reports whether B over prime is materially simpler than B over pi-web.
  - Design is not locked (Z17); this is input to the next iteration.
- Dispatch record (Grok Bot, 11:51 SGT): track 4 brief `briefs/track-4.md` (sha256 195ea3ad) written and copied to the docs worktree. Spawned session `01a166e0-220d-7dbc-8b1c-719e872dad2d` in `/home/alphalab/Projects/pi-stack/pi-stack` (project pi-stack, as tracks 1-3), set openai-codex/gpt-6.1-sol and xhigh, named it, then sent the brief. Consumed (sha match as last user message), streaming at 2.4% context. The brief has the session create worktree `/home/alphalab/Projects/worktrees/pi-stack-b-over-prime` on `spike/b-over-prime` off origin/main (3acf0f0) as its first step, per orchestrate-with-pi (pi creates worktrees). collect.sh now also pulls `40-b-over-prime.md`.

## Z19 (ZF t225u, 2026-10-23 11:50 SGT): drop C, detailed A and B designs, then a side-by-side comparison
- C is dropped. G24's A/C merge is withdrawn: A stands on its own, and parts of C go in only where A's design justifies them.
- Track 3 writes a detailed design and plan for A in `docs/harness-program/31-design-a-detailed.md`. It must specify:
  - every hook exactly: trigger event, layer, input and output, where the code lives, failure behaviour;
  - every prompt exactly: the full text of each injected or template prompt, and when it fires;
  - artifact storage exactly: paths, file formats and section schemas against the Z15 STATE.md plus history/ layout, plus who writes each, who reads each, rotation and retention;
  - obvious important notes and risks;
  - a justification for every component, tied to a corpus failure class and its layer;
  - an implementation plan as stacked commits, each with its tests.
- Track 4 does the same for B over prime in `docs/harness-program/41-design-b-prime-detailed.md`, alongside its 40 feasibility file, using the same section structure so the two line up side by side.
- When both are done, Grok Bot produces `docs/harness-program/50-a-vs-b.md`, a side-by-side comparison with a per-component table and a pros/cons table, and sends it to ZF. Design stays unlocked (Z17).
- **Steered (Grok Bot, 11:55 SGT).** Track 4: `briefs/track-4-steer-1.md` sent with `--steer` while streaming, consumed 11:52 (byte match, streaming 14.7%); the session had already created worktree `/home/alphalab/Projects/worktrees/pi-stack-b-over-prime` on `spike/b-over-prime` at 3acf0f0. Track 3: was idle at 68.2%, so `/compact` via `commands/run` first, then `briefs/track-3-steer-3.md` as a normal prompt, consumed 11:55 (byte match, streaming 11.3%). collect.sh now pulls 31, 40 and 41.

- **G27. Tracks 3 and 4 done; comparison goes to a fresh session.** Grok Bot decision, 12:55 SGT. 31 and 41 both pass the driver gate (all 8 Z19 headings, no placeholder prompts, STREAM/ACTIONS appear only in 41 as "there is no ..."). Pushed `spike/b-over-prime` `8811a7a` from a host bundle. Spawned track 5 `01a1671a-01d1-7f51-b240-533efc527a61` (gpt-6.1-sol, xhigh) with `briefs/track-5.md` to write `50-a-vs-b.md`, no recommendation and open questions without defaults (Z17). Z16's "not steered yet" note is moot: Z19 withdrew G24 and track 3 was steered on Z19 at 11:55. *Reason:* a fresh session reads both designs without either author's bias, and its 500k context fits both 80k docs; the comparison is sent to ZF only after its gate passes.

- **G28. A vs B comparison sent.** Grok Bot decision, 13:25 SGT. Track 5 reported done; `50-a-vs-b.md` passes the driver gate (core difference, per-component side-by-side for headings/records/hooks/prompts/artifacts/lifecycle, pros/cons, effort and risk, corpus coverage, 13 open questions with no defaults, no recommendation, retired names only as "neither creates"). Docs branch and `spike/b-over-prime` `8811a7a` already pushed. Comparison handed to the main chat for ZF once; STATUS `comparison_sent` set. *Reason:* Z19 deliverable is complete and passes the gate; design stays unlocked (Z17).

## Z20 (ZF t226u, 2026-10-23 14:54 SGT): design A over Prime, not pi
- ZF: "For A the ask is to design it over prime not pi". Design A must be redone with **Prime as the runtime** instead of pi-web/pi. Proposal A's substance stays: obligations and evidence are repo-owned and the checked `STATE.md` is the authority.
- The 13:25 A vs B comparison (`50-a-vs-b.md` v1, G28) is **superseded**: it compared A-over-pi-web with B-over-Prime. A v2 comparison, A-over-Prime vs B-over-Prime, follows once the rewritten 31 passes the driver gate.
- Track 3 rewrites `31-design-a-detailed.md` (same 8 Z19 headings, top line "Runtime: Prime (Z20)"), using track 4's 40/41 for what Prime v0.10.1 supports; hooks name Prime extension points, and anything Prime lacks is listed as a native Prime change. Track 5 stands by to write 50 v2.
- Design stays unlocked (Z17). No defaults; open questions stay questions.
- **Steered (Grok Bot, 15:08 SGT): consumed and being worked.** Original note from 15:06: `briefs/track-3-steer-4.md` (sha256 8f82b860) sent to track 3 `01a16658` while it was idle at 45.5%, no compact needed. It's the last user message in the session jsonl at 14:58:50 SGT (sha match). But every model call since then has failed with `fetch failed`: options-01 has had no outbound internet since about 14:50 SGT. Track 5 got `briefs/track-5-standby.md` at 14:59:16. Once the network returns, Z20 counts as steered when track 3 resumes and works the steer.

## Z21 (ZF t228u, 2026-10-23 14:57 SGT): clean up nomenclature, justify every new concept
- ZF: "Clean up the nomenclature. We spent time to reduce the abstraction bloat and here you just created another set. Clean all of this up and really justify the need of a new concept". This comes before ZF engages with the A vs B substance.
- Rule for both designs (31 A-over-Prime and 41 B-over-Prime, plus 40 where its terms are cited):
  - The baseline vocabulary is only the Z15 artifacts (AGENTS.md role file; STATE.md with Goals, Rules, Log; history/) plus existing pi-stack and Prime terms (stream, session, worker, tick, DCR, F-DCR, compaction, fork).
  - Every other concept is removed, merged into an existing artifact, or kept only with a row in a short "New concepts" table at the top of the doc: plain name, one-line meaning, the corpus failure it fixes, and why no existing artifact or term can carry it. The fewer the better; zero is best.
  - Examples now in the docs that must go through this test: the Asks section, sources/, evidence/, handover/, facts journal / InputFact, owner epoch / generation, adoption, maintenance records, settlement, quiescence, disposition, projection/view, receipts, H-numbered hooks and P-numbered prompts used as names.
  - Plain words and no coined labels. No two names that blur together (Z14) and no near-synonyms for one thing. Hooks and prompts get descriptive names (for example "save-incoming-message hook"), not codes.
  - A and B share one vocabulary so the v2 comparison lines up.
- Design stays unlocked (Z17).
- **Steered (Grok Bot, 15:08 SGT): consumed and being worked.** Original note from 15:06: Folded into `briefs/track-3-steer-4.md` (sha 8f82b860, 14:58:50) and sent to track 4 `01a166e0` as `briefs/track-4-steer-2.md` (sha 911ec9ee, 14:58:51). Both sha-match as the last user message, but both turns failed with `fetch failed` (host network outage).

## Z22 (ZF t229u, 2026-10-23 14:59 SGT): a version of B that needs no Prime changes
- ZF: "Yes let's do a no prime change version", replying to Grok Bot's offer to have the B session sketch a version of B that needs no changes to Prime.
- Track 4 writes `docs/harness-program/42-design-b-prime-unchanged.md`: design B on stock Prime v0.10.1 only. No native Prime changes, no Prime fork, no modified build; only what pi-stack can add from outside (client-side code, its own files and checks, the tick, Prime's existing commands and extension points). This is in addition to the Z21 cleanup of 41.
  - First line: "Runtime: stock Prime, no Prime changes (Z22)".
  - Same 8 Z19 headings, the same Z21 vocabulary rules and New concepts table, and exact hooks, prompts and storage.
  - It must say plainly whether it covers, works around, or leaves open each of the four gaps:
    1. the message save that ignores write errors and returns no id;
    2. results that are not stored durably;
    3. no evidence check before an ask closes;
    4. no way to move child workers to a new parent.
  - For each gap it must also give the cost: anything that bypasses the design, and any recovery that stays manual.
- The v2 comparison (50) will then cover three designs: A over Prime, B over Prime with Prime changes (41), and B over stock Prime (42).
- Design stays unlocked (Z17).
- **Steered (Grok Bot, 15:08 SGT): consumed and being worked.** Original note from 15:06: `briefs/track-4-steer-3.md` (sha bc7bba87) recorded in track 4 at 15:00:09 SGT (sha match). The turn failed with `fetch failed` (host network outage).

## Z23 (ZF t230u, 2026-10-23 15:01 SGT): the A/B differences feel artificial; a merged candidate
- ZF: "Tbh so far the differences feels artificial? Feels like we can easily arrive at a merged solution where most of the deterministic behaviour goes into hooking prime, ignore corner cases like login and fringe failure. Less deterministic stuff stays in repo?"
- Treated as a candidate: not golden, held to the same rigor, design still unlocked (Z17).
- The candidate:
  - Deterministic behaviour goes into hooks on stock Prime: saving incoming messages, fresh STATE each turn, the stall wake, compaction at the threshold, the stale-action guard, and closing checks that can be computed.
  - Judgement work stays in repo files under the Z15 layout: goals, rules, log entries, what counts as done, and reviews.
  - Login/auth failures and rare failure modes are out of scope, listed in one short "Not handled" section that says what happens today.

- **G29. Process for Z23.** Grok Bot decision, 2026-10-23 15:03 SGT.
  - The Z21 rename pass on 41 (B with Prime changes) is dropped beyond what's already done. 41 stays as **reference only**.
  - 31 (A over Prime, Z20) and 42 (B over stock Prime, Z22) continue. A merged design needs both: 42 shows what stock Prime hooks can carry, and 31 shows what the repo carries.
  - Track 5 is briefed now (`briefs/track-5-steer-1.md`) but starts only on the driver's go, after 31 and 42 pass the gate. It then does two things:
    1. Writes `51-design-merged.md` with the same 8 headings and the Z21 vocabulary rules, aiming for zero new concepts.
    2. Rewrites `50-a-vs-b.md` as v2: a short check of 51 against 31 and 42 covering what the merge loses from each, which corpus failures are no longer covered, where the A/B difference was real versus artificial, and open questions with no defaults.
  - *Reason:* the merged candidate depends on both inputs. Running it before they finish would rebuild the bias the v1 comparison had.
- **Steered (Grok Bot, 15:08 SGT): consumed and being worked.** Original note from 15:06: `briefs/track-4-steer-4.md` (sha f4d861d3) recorded in track 4 at 15:02:49 SGT, and `briefs/track-5-steer-1.md` (sha 17846bc9) recorded in track 5 at 15:02:49 SGT (wait-for-go). Both sha-match, and both turns failed with `fetch failed` (host network outage).

- **Steer status update (Grok Bot, 15:08 SGT).** options-01's network was back by about 15:05 SGT. Resume prompts went out at 15:05:
  - Track 3 has been working steer-4 since 15:06:22 (tool calls).
  - Track 4 has been working steers 2-4, with steer 4 winning where they conflict, since 15:06:32.
  - Track 5 replied `TRACK 5 STATUS: standby (steer 1 received)` at 15:06:25.
  - Z20-Z23 are steered.
  - Track 1 (`01a16655`) also hit `fetch failed` (last good turn 337a07cf at 14:49:44) and has not been resumed here; the driver should check it.
- **Track 1 resumed after the outage (Grok Bot, 15:09 SGT).**
  - Before sending: chatgpt.com is reachable from options-01 again (HTTP 403 from the edge, not a timeout). Track 1 `01a16655` was idle at 66.1% context, under 85%, so no compact.
  - Sent `briefs/track-1-reentry-2.md` (sha256 d46e1e2b): continue S1 from `2696a3f` with the full-SID handover unit, then the after-S1 disposable-stream check, then S2-S6, per its brief and 12-track-1-progress.md. Recorded at 15:08:53 (sha match).
  - Streaming at 68.2% and working the handover unit (temp dir `/tmp/pi-streams-s1-handovers.*`, TODO.md updated).
  - The 14:50 env failure is closed for every track.

- **G30. 42 passes the gate.** Grok Bot decision, 2026-10-23 15:55 SGT. Track 4 reported `TRACK 4 STATUS: done (42 stock Prime; 41 reference only)` at 15:45. 42 has the first line "Runtime: stock Prime, no Prime changes (Z22)", all 8 headings, an empty New concepts table (zero), full prompt texts, no retired names or H/P codes, no native Prime change in its plan, and a covers/works-around/leaves-open answer with cost for each of the four gaps. b_unchanged_done set. spike/b-over-prime is unchanged at 8811a7a, already pushed. Track 5 still waits for 31. *Reason:* every gate item checked against the collected file.

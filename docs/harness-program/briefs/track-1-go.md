/skill:poteto-mode

Steer from Grok Bot, 2026-10-23 11:45 SGT. ZF gave the go-ahead on your catalog at 11:35 SGT (`GO` in `03-decisions.md`). It covers the catalog as amended by Z13, Z14 and Z15 below, and it authorizes implementation. You move from catalog to code in this one turn: first amend the two docs, then implement the stacked plan.

Re-read from the docs worktree `/home/alphalab/Projects/worktrees/pi-stack-harness-program/docs/harness-program/` (refreshed just now): `03-decisions.md` sections Z13, Z14, Z15, GO and G25, and `00b-zf-messages-verbatim.md` sections t215u, t216u, t220u, t221u. Use targeted reads (`rg`, line ranges), not whole-file dumps.

## (a) Catalog amendments. Z15 wins over Z14/G22 and G17/G21 wherever they conflict

1. **One always-loaded file: `STATE.md`**, with exactly these sections, in this order:
   - `## Goals`: the single mutable North Star plus the current objective. Rewritten in place, never appended.
   - `## Rules`: ZF's rulings still in force (decisions that condition the state). Rewritten in place, kept short.
   - `## Log`: append-only `### <ts> <subject>` entries, capped at 30. Only the Log is capped. The tick rotates the oldest overflow to history; the agent never does.
   Parse sections by header and tolerate an extra `##` section between Rules and Log (track 3 may add `## Asks` later). Don't build it now.
2. **`history/<UTC ts>-<slug>.md`, one file per entry.** It absorbs rotated Log entries, retired rules (`<ts>-rule-retired-<slug>.md`), old decisions, and ZF steers. A ZF steer is logged as a Log entry when it arrives and reaches history through normal rotation. No tag field.
3. **Rule lifecycle.** A new ruling goes into Rules and gets a Log entry. A superseded ruling is removed from Rules and its text goes to history.
4. **Retired:** `GOAL.md`, `STREAM.md`, `DECISIONS.md`, `ACTIONS.md` (and the `CURRENT` section idea; its job is Goals' current objective). **Every turn loads only `AGENTS.md` and `STATE.md`.** On demand: history/, context/ (README is an index), checks/, handover/. Engine-only, never read by agents: threads.tsv, subscriptions.tsv, stream.toml, log/events.jsonl, log/tick-state.json, the streams.tsv and projects registry, locks, failures/.
5. **Naming rule:** no two stream files may share a concept. Check every name in the tier table against it.
6. **Out of scope (Z13):** coordinator-invented files (ALERTS.md, decisions.tsv, ad-hoc log/ and analysis dirs). Fix 12 just stops referencing them: no import, no migration, no ownership work. **Drop fix 17** from the catalog and the S1 commit that inventories bulk outputs.
7. **TODO.md and PLAN.md** (global overlay): inside a stream they're replaced by STATE Goals plus Log, and the stream template disables them. Non-stream overlay behavior is unchanged.
8. **Migration (fix 16 / S2a)** covers STREAM.md (split into Goals, active rules, and history; the ratified charter text moves into Goals or becomes the first history entry), DECISIONS.md (entries still in force go to Rules, the rest to history), and old STATE.md (into history, then a fresh STATE.md with the three sections). Plus the `failures/` dir from Z11. Lossless, idempotent, one scoped commit, no worker-worktree writes.
9. Every other reference follows: fix 6 (STATE with a capped Log replaces the ACTIONS idea), fix 10 (Goals in STATE replaces STREAM GOAL/CURRENT), the DCR template and Z6 re-inject read STATE Goals' current objective, falling back to the North Star, `PROTECTED_STREAM_FILES`, AGENTS steps, kickoff, `rotate_coordinator` pickup text.

## (b) Order of work

1. **Docs first.** Update `10-pi-streams-fix-catalog.md` and `11-artifact-map.md` (tier table included) to match (a). Keep the review tables, layers and blast radii. Log your own calls in the catalog's Decisions section. Don't touch other docs-worktree files except the progress file below. Don't commit in the docs worktree; Grok Bot collects.
2. **Then code.** Create branch `feat/streams-must-fix` off pi-stack main `3acf0f0` as a new worktree: `git -C /home/alphalab/Projects/pi-stack/pi-stack worktree add /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix -b feat/streams-must-fix 3acf0f0`. Implement the stacked plan in order: **S1, S2, S2a, S3, S4, S5, S6**, with the commit titles from the amended catalog. External prerequisite E (Twingate wrapper) is Grok Bot's on the box; skip it. The pi-web changes the stacks name (stop/cancel admission, idle compaction, exact-point fork) go on a same-named local branch `feat/streams-must-fix` of the pi-web source checkout. Find and pin it first; never edit an installed `dist`. Bot-deployment changes the catalog names (receipt relay, Slack DM delivery, ratification intake): if their source isn't on options-01, write the exact change as a patch file under the progress file's folder and say so, instead of guessing.
3. **One regression test per commit that fails on the base first.** For each commit: write the test, run it on the parent commit and record the failure, implement, run it green, run the full offline suite, commit locally. Record the red/green evidence in the commit body.
4. **Verify on a disposable stream** after each stack, as the catalog's real-stream check says. Use an isolated pi-web on its own port (not 8504) with its own `XDG_CONFIG_HOME`, `XDG_DATA_HOME`, `XDG_STATE_HOME` and streams root under a scratch dir. Never touch the live 8504 pi-web, the systemd `pi-streams-tick` service, `~/.pi-stack`, `~/.local/bin`, or any existing stream or session. Read the existing model auth in place; never copy, print or modify credentials. If isolation would need a credential copy or a new login, stop that check and report it. Fault-injected failures are labelled as fault injection.

## Hard limits (unchanged)

- Don't push, open PRs, merge, or rebase other branches. Grok Bot's driver merges and rebases after you report S1-S6 done with tests passing.
- Never stash or reset in any live worktree. Never switch provider or model. On a usage limit or quota error, stop and report.
- No default budgets or caps (D1); the 30-entry Log cap is ZF's rule, not a budget. Git never holds data.
- Don't steer, stop, rotate, archive or spawn any other existing session or stream.

## Progress and reporting

- Keep `docs/harness-program/12-track-1-progress.md` in the docs worktree current: amendments done, then one line per commit (stack, title, sha, red test, green, suite, disposable check). After a compact or re-entry, resume from it, not from memory.
- After the docs are amended, and after **each** commit, emit one line in your reply text:
  `TRACK 1 STATUS: implementing | stack=<S1..S6> | commit=<short sha> <title> | red=<yes/no> green=<yes/no> suite=<pass/fail> | disposable=<pass/fail/pending>`
- When S1-S6 are all done, end with:
  `TRACK 1 STATUS: done | branch=feat/streams-must-fix head=<sha> | pi-web branch head=<sha or none> | suite=<pass/fail> | F-DCR round-trip=<pass/fail> | next=driver merge`
  If you stop early, use `blocked` or `partial` with the reason.

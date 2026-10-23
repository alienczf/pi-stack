# 11. Stream artifact map

Grok Bot, 2026-10-23 09:58 SGT, for ZF's t212u ask. Sources: pi-stack `main` @ 3acf0f0 (`pi-streams/templates/stream/`, `pi-streams/templates/thread-brief.md`, `skills/stream*/SKILL.md`, `pi-streams/engine/{tick,threads,project,doctor}.py`, `overlay/{AGENTS,APPEND_SYSTEM}.md`, `docs/design/pi-streams.md` §3–§7). Reality: the 12 streams in `~/.config/pi-streams/streams.tsv` on options-01, read at 10:05 SGT (byte sizes; ÷4 ≈ tokens).

"Every turn" means the template `AGENTS.md` (step 1) or the overlay system prompt tells the agent to read it on each turn or each session start.

## Per stream (stream folder, its own git repo)

| File | Supposed to hold | Writer | Reader / when | Observed |
|---|---|---|---|---|
| `AGENTS.md` | Coordinator role, 5 per-turn rules | `new` (template) | pi system prompt, every session | 0.7 KB; 4 of 12 hand-edited (≤3.8 KB) |
| `STREAM.md` | Ratified charter: GOAL…NO-GO | Kickoff, then ZF only | Coord every turn; thread at spawn; engine (ratified marker) | Accretes amendments: 654 66 KB, vola 12 KB |
| `STATE.md` | Working state "kept short": plan, threads, waiting-on, next | Coord, rewrite each turn | Coord every turn; new coord after rotate | Newest-first `##` pile, never pruned: vola 181 KB/741 lines, 654 19 KB |
| `DECISIONS.md` | ZF's rulings, append-only | Coord (kickoff, concessions) | On demand | 654 202 KB, vola 178 KB, fill 172 KB |
| `context/` + `README.md` | Lasting how-to, gotchas, prefs (harvest) | Coord at close/milestones | README every turn; files on demand | 654 README 212 KB; vola 298 files |
| `threads.tsv` | One row per session: role, worktree, status | Engine (spawn/adopt/rotate/close); tick status | Tick every 5 min; coord on demand | Fine; 654 8 KB |
| `subscriptions.tsv` | Watches: source, when, action | Coord, only on ZF ask | Tick every 5 min | Header only in all 12 (no watches) |
| `checks/` | Acceptance scripts | Coord / threads | Coord to accept "done" | 0–189 files; used as scratch |
| `handover/<role>.md` | Thread exit note (pause-safely) | Thread before stop/close | Coord at close/harvest | Many variants per role (`-r2-r1`) |
| `stream.toml` | Project name, pi-stack rev, remote | `new`, `upgrade` | Engine, doctor | Fine |
| `log/events.jsonl` | Tick events (gitignored) | Tick, append | Coord: newest lines every turn | Fine (≤216 KB) |
| `log/tick-state.json` | Tick memory: seen, pending, outages | Tick only | Tick; doctor freshness | Fine |
| `log/` (other) | Nothing specified | Coord/threads ad hoc | Nobody | Dump ground: 654 34 GB (19 MB message dumps) |
| `.git/pi-streams.lock` | Per-stream writer lock | Engine/tick | Engine/tick | Fine |

## Not pi-streams, but loaded in every stream

| File | Supposed to hold | Writer | Reader / when | Observed |
|---|---|---|---|---|
| `TODO.md` | Progress (overlay: "TodoWrite is TODO.md") | Any agent | Overlay: read when present, every session | 654 465 KB/2263 lines; vola 113 KB |
| `PLAN.md` | Plan mode (overlay) | Any agent | Overlay: read when present, every session | 654 255 KB; vola 90 KB |

## Invented per stream (no pi-stack source)

| File | Used as | Observed |
|---|---|---|
| `ALERTS.md` | Coord's own alert/blocker log | 8 of 12; 654 294 KB |
| `decisions.tsv` | Coord's own decision ledger | 5 of 12; vola 123 KB |
| `METRICS.md`, `streamlog/`, `analysis/`, `evidence/`, `delivery/` | Ad hoc | 654 `analysis/` 47 GB |

## Index (`~/.config/pi-streams/`, not a git repo)

| File | Supposed to hold | Writer | Reader / when | Observed |
|---|---|---|---|---|
| `homes` | Index dirs the tick reads | `init` | Engine, tick | 1 home |
| `projects/<name>.toml` | Root, pi-web URL, models, caps, repos | `init` | Engine, tick, kickoff scout | 3 + 2 `.bak` |
| `streams.tsv` | id, path, project | `new` | Tick, engine, kickoff | 12 streams |
| `ALERTS` | Outage and claim lines for Grok Bot | Tick | Grok Bot routine | Empty now |
| `.pi-streams.lock` | Index lock | Engine/tick | Engine/tick | Fine |
| worktree `.stream` | Pointer to stream dir | `thread spawn/adopt` | Engine | Also sits in vola's stream dir |

## Separation-of-duty notes

1. **ZF's guess is half right.** STATE.md is behaving as long-term history loaded every turn: coordinators prepend `##` sections ("Resumed after…", "PAUSED by ZF…") and never prune, so vola's is 181 KB. But STREAM.md is not the current state. It is the ratified charter. It bloats differently, with amendments piling up under `ratified:` (654: 66 KB).
2. **No "10 MB STATE.md" exists.** 654's STATE.md is 19 KB. The real per-turn load in 654 is TODO.md 465 KB + PLAN.md 255 KB + context/README 212 KB + STREAM.md 66 KB + STATE.md 19 KB ≈ 1 MB ≈ 250k tokens if read in full. That is above the 150k DCR trigger before any work starts.
3. **Four files do one job.** STATE.md, TODO.md, PLAN.md and the invented ALERTS.md all end up as "current plus history" logs. TODO/PLAN come from the global overlay, not pi-streams, so the stream rules and the overlay rules overlap with no owner.
4. **Rotation and DCR both point at STATE.md** (`rotate_coordinator`: "Read STATE.md, then continue"), so the bloated file is exactly what a fresh context loads first.
5. **Nothing bounds the write-only areas.** `log/`, `checks/`, `handover/` and `context/` have no size or retention rule (654 `log/` 34 GB), and DECISIONS.md is append-only with no index.

## What Z9 / G17 changes

`ACTIONS.md` (append-only, 30 newest `### <ts> <subject>` entries, tick-rotated) replaces STATE.md. `history/<YYYYMMDDTHHMMZ>-<slug>.md` takes the overflow, one file per entry. STREAM.md stays the charter with GOAL as North Star plus a coordinator-editable `CURRENT` paragraph, and its amendments move to DECISIONS.md. Bounding TODO.md/PLAN.md, context/README.md and `log/` is artifact-health work (Z10b) for the track 1 catalog.

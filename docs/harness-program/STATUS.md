---
# Machine-readable harness-program status. The driving routine reads this YAML front matter every run.
# Times are Asia/Singapore (UTC+8). Only Grok Bot edits this file.
program: harness-program
repo: alienczf/pi-stack
docs_branch: docs/harness-program
pr: https://github.com/alienczf/pi-stack/pull/37
tracking_issue: https://github.com/alienczf/pi-stack/issues/38
box_mirror: /workspace/harness-program
host_docs_worktree: /home/alphalab/Projects/worktrees/pi-stack-harness-program
host_input_copy: /home/alphalab/Projects/pi-stack/streams/pi-streams-harness/context/harness-program
updated: 2026-10-23T14:25+08:00 (driver run: T1 streaming 62.4% ctx, active 14:12, S1 commit 4 (templates) in worktree after d1d4602, no compact while streaming; T2 idle blocked on Prime login, feat/prime-cli 6bc1242 unchanged; T3-T5 done; comparison already sent; no unsteered Z entries)
tracks:
  - id: 1
    name: pi-streams must-fix catalog
    session: 01a16655-5cfd-78c2-bf5f-e08c47e1665e
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: implementing
    milestones_sent: [track-1-review-ready 2026-10-23T11:01+08:00]
    go_ahead: 2026-10-23T11:35+08:00 (ZF t221u, GO in 03)
    started: 2026-10-23T09:17+08:00
    expected_done: 2026-10-23T18:00+08:00
    artifact: docs/harness-program/10-pi-streams-fix-catalog.md
    brief: docs/harness-program/briefs/track-1.md
    steers: [docs/harness-program/briefs/track-1-steer-1.md, docs/harness-program/briefs/track-1-steer-2.md, docs/harness-program/briefs/track-1-steer-3.md, docs/harness-program/briefs/track-1-reentry-1.md, docs/harness-program/briefs/track-1-go.md]
    steer_note: 10:27 context 86.8% -> aborted, cleared unconsumed steer-3, /compact via PI WEB commands/run (G19). 10:34 re-entry-1 (brief + phase + steer-3 folded in, sha 742d71f3) consumed, streaming, context 9.8%. Compact recipe - curl -X POST 127.0.0.1:8504/api/sessions/<sid>/commands/run -d {"text":"/compact"} on the host; pi-web-cli prompt "/compact" does NOT compact. 11:38 go steer (briefs/track-1-go.md, sha aaa62d2f; Z13-Z15 amendments + implement S1-S6) sent while idle at 33.9%, consumed (byte match), streaming at 35.7%.
    inputs: [docs/harness-program/11-artifact-map.md]
    code_branch: feat/streams-must-fix (off main 3acf0f0; pi-web source gets a same-named local branch)
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-streams-must-fix
    progress: docs/harness-program/12-track-1-progress.md
    brief_sha256_verified: true
    gate: Session reports S1-S6 done (TRACK 1 STATUS done line) with the full suite and F-DCR round-trip passing.
    next_action: Each run, read the latest TRACK 1 STATUS line and 12-track-1-progress.md; compact via commands/run if context > 60% at an idle boundary and re-enter from the progress file. When it reports done, the driver merges feat/streams-must-fix (and the pi-web branch) to main, rebases live branches, verifies. Grok Bot does Twingate wrapper prerequisite E on the box.
  - id: 2
    name: prime-agent CLI (design + feat/prime-cli)
    session: 01a16656-ddcb-76c7-a44b-c7298bcb0198
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: blocked-on-prime-codex-login (non-inference parity gaps in progress, steer-1 consumed 10:59)
    milestones_sent: [track-2-blocker-prime-login 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:19+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/20-prime-cli-design.md
    code_branch: feat/prime-cli
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-prime-cli
    brief: docs/harness-program/briefs/track-2.md
    steers: [docs/harness-program/briefs/track-2-steer-1.md, docs/harness-program/briefs/track-2-reentry-1.md]
    steer_note: 11:31 context 84.5% (~422k) -> aborted, /compact via commands/run (G21), now 19.1%; session auto-continued its in-flight verification. reentry-1 consumed (11:52); session idle at ~3% context, 71 offline tests pass, reports TRACK 2 STATUS blocked on ZF Prime login.
    brief_sha256_verified: true
    blocked_on: ZF interactive openai-codex login for Prime on options-01 (blocker note sent once, 11:01)
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    pushed: feat/prime-cli 6bc1242 (2026-10-23 11:58, driver)
    next_action: When idle, collect, push feat/prime-cli again. After ZF logs Prime in, run the inference verification script from the design doc and the off-host wrapper check from the box, then send the track-2-working milestone. Streams-on-prime port waits for track 1 to merge.
  - id: 3
    name: problem-state research + three designs
    session: 01a16658-09d0-7fcc-9815-7ac75f2cbb29
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: done (TRACK 3 STATUS done 12:27; 31 passed driver gate 12:55: 8 headings, no placeholder prompts, no retired names)
    milestones_sent: [track-3-designs-ready 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/31-design-a-detailed.md (after 30-research-designs.md)
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md, docs/harness-program/briefs/track-3-steer-2.md, docs/harness-program/briefs/track-3-steer-3.md]
    brief_sha256_verified: true
    steer_note: steer-1 consumed (09:53). steer-2 (Z12 five inputs, coverage table, three proposals, blocking decisions) consumed 10:11 (sha match, streaming, pending 0).
    next_action: Z19 - C dropped, G24 withdrawn. Wait for TRACK 3 STATUS done on 31-design-a-detailed.md (8 headings, Z15 layout); compact via commands/run if > 60% at idle. When both 31 and 41 are done, Grok Bot writes 50-a-vs-b.md and sends it to ZF (design unlocked, Z17).
  - id: 4
    name: proposal B over prime (feasibility spike)
    session: 01a166e0-220d-7dbc-8b1c-719e872dad2d
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: done (TRACK 4 STATUS done 12:32; 40 verdict partly; 41 passed driver gate 12:55)
    pushed: spike/b-over-prime 8811a7a (2026-10-23 12:53, driver)
    started: 2026-10-23T11:51+08:00
    expected_done: 2026-10-23T15:30+08:00
    artifact: docs/harness-program/40-b-over-prime.md, then docs/harness-program/41-design-b-prime-detailed.md
    brief: docs/harness-program/briefs/track-4.md
    steers: [docs/harness-program/briefs/track-4-steer-1.md]
    brief_sha256_verified: true (195ea3ad, byte match as last user message)
    code_branch: spike/b-over-prime (off origin/main 3acf0f0; worktree created by the session, confirmed 11:52)
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-b-over-prime
    session_cwd: /home/alphalab/Projects/pi-stack/pi-stack (same as tracks 1-3; pi creates the worktree per orchestrate-with-pi)
    inputs: [docs/harness-program/30-research-designs.md, docs/harness-program/20-prime-cli-design.md, feat/prime-cli, /home/alphalab/Projects/prime-agent, docs/harness-program/02-principles.md]
    gate: TRACK 4 STATUS done line with 40 covering (a)-(d) and 41 with the Z19 8 headings; spike commits local only. Design not locked (Z17), input only.
    next_action: Each run, read the latest TRACK 4 STATUS line; confirm the worktree and branch exist; compact via commands/run if context > 60% at an idle boundary. When done, collect 40 and 41, push spike/b-over-prime from a bundle; with 31 also done, write 50-a-vs-b.md and send ZF (no decision framing).
  - id: 5
    name: A vs B side-by-side comparison (Z19)
    session: 01a1671a-01d1-7f51-b240-533efc527a61
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: done (TRACK 5 STATUS done ~13:20; 50 passed driver gate 13:25)
    started: 2026-10-23T12:53+08:00
    expected_done: 2026-10-23T14:00+08:00
    artifact: docs/harness-program/50-a-vs-b.md
    brief: docs/harness-program/briefs/track-5.md (sha256 e546f734)
    gate: TRACK 5 STATUS done; 50 has core difference, per-component side-by-side, pros/cons, effort and risk, corpus coverage, open questions without defaults.
    next_action: When done and gate passes, collect, push docs branch, send ZF the A vs B comparison (core difference paragraph, side-by-side table, pros/cons table, open questions, links to 31, 41, 50), then set comparison_sent below. Never resend.
comparison_sent: 2026-10-23T13:25+08:00 (handed to main chat via WakeParent; never resend)
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | implementing, S1 commit 3 `d1d4602` (61.7% ctx) | `10-pi-streams-fix-catalog.md` + `feat/streams-must-fix` | S1-S6 done, then driver merges |
| 2 prime CLI | `01a16656` | blocked on Prime codex login; non-inference gaps in progress | `20-prime-cli-design.md` + `feat/prime-cli` (`6bc1242` pushed) | ZF logs Prime in, then inference verification |
| 3 research | `01a16658` | done (31 gate passed 12:55) | `30-research-designs.md`, `31-design-a-detailed.md` | none; feeds track 5 |
| 4 B over prime | `01a166e0` | done (41 gate passed 12:55) | `40-b-over-prime.md`, `41-design-b-prime-detailed.md` + `spike/b-over-prime` (`8811a7a` pushed) | none; feeds track 5 |
| 5 A vs B | `01a1671a` | done (50 gate passed 13:25) | `50-a-vs-b.md` | A vs B comparison sent 13:25; never resend |

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

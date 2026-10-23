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
updated: 2026-10-23T15:06+08:00 (Z20-Z23 logged; steers recorded on T3/T4/T5 but every inference call fails with fetch failed; options-01 has no outbound internet since ~14:50 (curl to chatgpt.com/github.com times out). Last good turns - T1 337a07cf 14:49:44, T3 e8fc7a93 12:27:44, T4 d92ba0f9 12:32:59, T5 2142b033 13:06:50. Once the network is back, send a one-line resume to T3, T4 and T1; T5 waits for its go)
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
    phase: "A-over-Prime rewrite + Z21 naming cleanup (steer-4 recorded 14:58:50, not yet worked - host network outage). Comparison v1 superseded (Z20)."
    milestones_sent: [track-3-designs-ready 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/31-design-a-detailed.md (after 30-research-designs.md)
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md, docs/harness-program/briefs/track-3-steer-2.md, docs/harness-program/briefs/track-3-steer-3.md, docs/harness-program/briefs/track-3-steer-4.md]
    brief_sha256_verified: true
    steer_note: steer-1 consumed (09:53). steer-2 (Z12 five inputs, coverage table, three proposals, blocking decisions) consumed 10:11 (sha match, streaming, pending 0).
    next_action: "Z20+Z21. Wait for 'TRACK 3 STATUS: done (A over Prime)'. Gate - first line 'Runtime: Prime (Z20)', 8 headings, New concepts table near the top (fewest rows), hooks name Prime extension points, native Prime changes listed, no retired names or H/P codes. When 31 and 42 both pass, send track 5 'GO track 5 steer 1'."
  - id: 4
    name: proposal B over prime (feasibility spike)
    session: 01a166e0-220d-7dbc-8b1c-719e872dad2d
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: "42 B-over-stock-Prime (Z22); 41 reference only (G29, Z21 rename stopped). steer-2 recorded 14:58:51, steer-3 15:00:09, steer-4 15:02:49; not yet worked (host network outage)"
    pushed: spike/b-over-prime 8811a7a (2026-10-23 12:53, driver)
    started: 2026-10-23T11:51+08:00
    expected_done: 2026-10-23T15:30+08:00
    artifact: docs/harness-program/40-b-over-prime.md, docs/harness-program/41-design-b-prime-detailed.md (reference only), docs/harness-program/42-design-b-prime-unchanged.md
    brief: docs/harness-program/briefs/track-4.md
    steers: [docs/harness-program/briefs/track-4-steer-1.md, docs/harness-program/briefs/track-4-steer-2.md, docs/harness-program/briefs/track-4-steer-3.md, docs/harness-program/briefs/track-4-steer-4.md]
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
    phase: "standby for 51 merged + 50 v2 (standby 14:59:16, steer-1 recorded 15:02:49; do not start until driver go)"
    started: 2026-10-23T12:53+08:00
    expected_done: 2026-10-23T14:00+08:00
    artifact: docs/harness-program/50-a-vs-b.md
    brief: docs/harness-program/briefs/track-5.md (sha256 e546f734)
    steers: [docs/harness-program/briefs/track-5-standby.md, docs/harness-program/briefs/track-5-steer-1.md]
    gate: TRACK 5 STATUS done; 50 has core difference, per-component side-by-side, pros/cons, effort and risk, corpus coverage, open questions without defaults.
    next_action: "Z23/G29. When 31 and 42 pass the gate, send 'GO track 5 steer 1' (briefs/track-5-steer-1.md, sha 17846bc9, recorded 15:02:49). Gate - 51 first line, 8 headings, New concepts table (target zero), Not handled section; 50 v2 covers losses vs 31 and 42, uncovered F-numbers, real vs artificial, open questions with no defaults."
comparison_sent: 2026-10-23T13:25+08:00 (v1, handed to main chat via WakeParent; never resend; superseded by Z20)
comparison_v1_superseded: true
a_over_prime_done: false
naming_cleanup_done:
  '31': false
  '41': "dropped - G29, 41 reference only"
b_unchanged_done: false
merged_done: false
comparison_v2_sent: false
reference_only: [docs/harness-program/41-design-b-prime-detailed.md]
env_failure:
  open: 2026-10-23T14:50+08:00
  kind: "options-01 outbound network outage - every inference call returns fetch failed"
  last_good_turn: {T1: 337a07cf, T2: 7705e817, T3: e8fc7a93, T4: d92ba0f9, T5: 2142b033}
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | implementing, S1 commit 4 `2696a3f` (66.0% ctx) | `10-pi-streams-fix-catalog.md` + `feat/streams-must-fix` | S1-S6 done, then driver merges |
| 2 prime CLI | `01a16656` | blocked on Prime codex login; non-inference gaps in progress | `20-prime-cli-design.md` + `feat/prime-cli` (`6bc1242` pushed) | ZF logs Prime in, then inference verification |
| 3 research | `01a16658` | A-over-Prime rewrite + naming cleanup (Z20, Z21) | `31-design-a-detailed.md` | done line, then gate; feeds 51 |
| 4 B over prime | `01a166e0` | 42 B over stock Prime (Z22); 41 reference only | `40`, `41` (reference), `42-design-b-prime-unchanged.md` | done line, then gate; feeds 51 |
| 5 merged + v2 | `01a1671a` | standby (Z23) | `51-design-merged.md`, `50-a-vs-b.md` v2 | go after 31 and 42 pass |

**Open env failure (14:50):** options-01 has no outbound internet, so every inference call returns `fetch failed`. Steers are recorded but not yet worked.

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

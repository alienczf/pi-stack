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
updated: 2026-10-23T11:39+08:00
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
    steer_note: 11:31 context 84.5% (~422k) -> aborted, /compact via commands/run (G21), now 19.1%; session auto-continued its in-flight verification. reentry-1 queued 11:39 (pending 1) - next run confirm consumed, re-send if lost.
    brief_sha256_verified: true
    blocked_on: ZF interactive openai-codex login for Prime on options-01 (blocker note sent once, 11:01)
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    pushed: feat/prime-cli 29ff206 (2026-10-23 11:39)
    next_action: When idle, collect, push feat/prime-cli again. After ZF logs Prime in, run the inference verification script from the design doc and the off-host wrapper check from the box, then send the track-2-working milestone. Streams-on-prime port waits for track 1 to merge.
  - id: 3
    name: problem-state research + three designs
    session: 01a16658-09d0-7fcc-9815-7ac75f2cbb29
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: done (designs sent)
    milestones_sent: [track-3-designs-ready 2026-10-23T11:01+08:00]
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/30-research-designs.md
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md, docs/harness-program/briefs/track-3-steer-2.md]
    brief_sha256_verified: true
    steer_note: steer-1 consumed (09:53). steer-2 (Z12 five inputs, coverage table, three proposals, blocking decisions) consumed 10:11 (sha match, streaming, pending 0).
    next_action: None until ZF answers the two blocking decisions (defaults A, and no auto-delete). Leave session idle.
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | implementing (ZF go 11:35, steer consumed 11:39) | `10-pi-streams-fix-catalog.md` + `feat/streams-must-fix` | S1-S6 done, then driver merges |
| 2 prime CLI | `01a16656` | blocked on Prime codex login; non-inference gaps in progress | `20-prime-cli-design.md` + `feat/prime-cli` (`29ff206` pushed) | ZF logs Prime in, then inference verification |
| 3 research | `01a16658` | done, designs sent 11:01 | `30-research-designs.md` | ZF answers two blocking decisions |

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.

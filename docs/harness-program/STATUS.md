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
updated: 2026-10-23T10:12+08:00
tracks:
  - id: 1
    name: pi-streams must-fix catalog
    session: 01a16655-5cfd-78c2-bf5f-e08c47e1665e
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: catalog-amending (v1 done 09:5x with Z1-Z5; amending for Z6-Z11)
    started: 2026-10-23T09:17+08:00
    expected_done: 2026-10-23T11:30+08:00
    artifact: docs/harness-program/10-pi-streams-fix-catalog.md
    brief: docs/harness-program/briefs/track-1.md
    steers: [docs/harness-program/briefs/track-1-steer-1.md, docs/harness-program/briefs/track-1-steer-2.md, docs/harness-program/briefs/track-1-steer-3.md]
    steer_note: steer-2 (Z6-Z10, G17, 11-artifact-map) consumed 10:00 (sha match, turn started). steer-3 (Z11) queued as follow-up 10:06 while busy (pendingMessageCount=1); confirm it is consumed next run. Context 387k/500k at 10:10.
    inputs: [docs/harness-program/11-artifact-map.md]
    brief_sha256_verified: true
    gate: ZF first-pass review of the catalog. ZF finished dictating at 10:01 (Z1-Z11). Send once the catalog reflects Z1-Z11; per G18 mark each Z-derived fix with track 3's verdict if one exists, never wait for track 3.
    next_action: When the session goes idle with "TRACK 1 STATUS", confirm steer-3 consumed, pull the artifact, check it against Z1-Z11 and G17/G18, commit it to the docs branch, then send it to ZF for review.
  - id: 2
    name: prime-agent CLI (design + feat/prime-cli)
    session: 01a16656-ddcb-76c7-a44b-c7298bcb0198
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: design
    started: 2026-10-23T09:19+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/20-prime-cli-design.md
    code_branch: feat/prime-cli
    code_worktree: /home/alphalab/Projects/worktrees/pi-stack-prime-cli
    brief: docs/harness-program/briefs/track-2.md
    brief_sha256_verified: true
    blocked_on: null
    open_questions: [caladan (pi-bot caladan bb39dc0; no pi-stack branch), non-blocking]
    next_action: When idle, pull the design doc, commit it to the docs branch, then bundle feat/prime-cli from the host and push it from the box. Streams-on-prime port waits for track 1 to merge.
  - id: 3
    name: problem-state research + three designs
    session: 01a16658-09d0-7fcc-9815-7ac75f2cbb29
    host: options-01
    model: openai-codex/gpt-6.1-sol@xhigh
    phase: three-proposals (redefined by Z12)
    started: 2026-10-23T09:21+08:00
    expected_done: 2026-10-23T13:30+08:00
    artifact: docs/harness-program/30-research-designs.md
    inputs: [docs/harness-program/31-x-corpus-seed.md]
    brief: docs/harness-program/briefs/track-3.md
    steers: [docs/harness-program/briefs/track-3-steer-1.md, docs/harness-program/briefs/track-3-steer-2.md]
    brief_sha256_verified: true
    steer_note: steer-1 consumed (09:53). steer-2 (Z12 five inputs, coverage table, three proposals, blocking decisions) consumed 10:11 (sha match, streaming, pending 0).
    next_action: When idle with "TRACK 3 STATUS", pull 30-research-designs.md (and 30a), commit it, give ZF the three proposals, pros/cons table and blocking decisions, and attach per-Z verdicts to the track 1 review (G18).
---

# Harness program status

| Track | Session | Phase | Artifact | Next |
|---|---|---|---|---|
| 1 fix catalog | `01a16655` | amending for Z6–Z11 | `10-pi-streams-fix-catalog.md`, `11-artifact-map.md` | Confirm steer 3, collect, check against Z1–Z11, send to ZF |
| 2 prime CLI | `01a16656` | design | `20-prime-cli-design.md` + `feat/prime-cli` | Collect the design, push the branch |
| 3 research | `01a16658` | three proposals (Z12) | `30-research-designs.md` | Collect, send ZF proposals + blocking decisions |

The canonical copy is on GitHub. The box mirror is `/workspace/harness-program/STATUS.md`.
